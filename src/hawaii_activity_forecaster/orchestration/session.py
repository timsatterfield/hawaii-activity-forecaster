"""In-memory admission of normalized requests and post-terminal refinements.

Runtime metadata only: no new logical schema, language parser, persisted session,
cross-investigation evidence cache, or active-investigation resumption.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from threading import RLock
from typing import TYPE_CHECKING
from uuid import uuid4

from hawaii_activity_forecaster.config.settings import InvestigationLimits
from hawaii_activity_forecaster.models import InvestigationState, NormalizedRequest, RecommendationResult
from hawaii_activity_forecaster.models.investigation import TERMINAL_OUTCOMES

if TYPE_CHECKING:
    from .skeleton import SkeletonReport

_REQUEST_FIELDS = frozenset(NormalizedRequest.model_fields)
_VALUE_FIELDS = _REQUEST_FIELDS - {"original_request", "clarification_needed", "clarification_questions"}
_CHANGES = _REQUEST_FIELDS - {"original_request"}


class SessionError(ValueError):
    """Session admission or correlation failed; no environmental conclusion."""


@dataclass(frozen=True)
class SessionRequest:
    """Detached admission metadata for one fresh graph invocation.

    Values are already normalized by the caller. Field-level origin declarations
    distinguish explicit user values from assumptions; no JSON constraint meaning
    is inferred here. Accessing .request returns a fresh validated snapshot.
    """

    session_id: str
    request_revision: int
    previous_investigation_id: str | None
    user_provided_fields: frozenset[str]
    changed_fields: tuple[str, ...]
    _request: bytes = field(repr=False)

    @property
    def request(self) -> NormalizedRequest:
        return NormalizedRequest.model_validate_json(self._request)

    @property
    def assumed_fields(self) -> frozenset[str]:
        values = self.request.model_dump()
        return frozenset(name for name in _VALUE_FIELDS - self.user_provided_fields
                         if values[name] is not None and values[name] != [])

    def check(self, request: NormalizedRequest) -> None:
        """Reject mismatched admission before graph initialization or dispatch."""
        if (type(self.request_revision) is not int or self.request_revision < 1
                or not isinstance(self.session_id, str) or not self.session_id.strip()
                or not self.user_provided_fields <= _VALUE_FIELDS
                or not set(self.changed_fields) <= _CHANGES
                or (self.request_revision == 1) != (self.previous_investigation_id is None)
                or (self.previous_investigation_id is not None and
                    (not isinstance(self.previous_investigation_id, str) or not self.previous_investigation_id.strip()))
                or self.request != request):
            raise SessionError("Request does not match its session admission.")


SessionRunner = Callable[[SessionRequest], Awaitable["SkeletonReport"]]


def _normalized(request: NormalizedRequest) -> NormalizedRequest:
    try:
        data = NormalizedRequest.model_validate(request.model_dump()).model_dump()
        if (data["target_date"] is not None and data["target_time_window"] is not None
                and data["target_date"] != request.target_time_window.start.astimezone(timezone(timedelta(hours=-10))).date()):
            raise ValueError("Requested date and Hawaii time window disagree")
        # Match the graph's clarification guard without assuming missing values.
        if data["activity"] is None or data["target_time_window"] is None or data["clarification_questions"]:
            data["clarification_needed"] = True
        if data["clarification_needed"] and not data["clarification_questions"]:
            data["clarification_questions"] = ["Please clarify the unresolved request details before investigation."]
        return NormalizedRequest.model_validate(data)
    except (ValueError, TypeError, AttributeError):
        raise SessionError("The normalized request is invalid.") from None


class SessionManager:
    """One process-local session; each admitted request runs once with fresh state.

    The injected runner selects candidates and executes the existing graph with
    session_request=admission. No previous report/findings are passed to it.
    Returned snapshots are detached, so callers cannot mutate session history.
    """

    def __init__(self):
        self._session_id = str(uuid4())
        self._revision = 0
        self._context: SessionRequest | None = None
        self._reports: list[SkeletonReport] = []
        self._busy = False
        self._blocked = False
        self._closed = False
        self._lock = RLock()

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def request_revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def current(self) -> SessionRequest | None:
        with self._lock:
            return self._context

    @property
    def investigations(self) -> tuple[SkeletonReport, ...]:
        with self._lock:
            return deepcopy(tuple(self._reports))

    def _available(self):
        if self._closed or self._blocked:
            raise SessionError("This session cannot accept more work; start a new session.")
        if self._busy:
            raise SessionError("Follow-ups require the current investigation to reach a terminal outcome.")

    async def start(self, request: NormalizedRequest, *, user_provided_fields: Collection[str],
                    run: SessionRunner) -> SkeletonReport:
        """Admit the first caller-normalized request, declaring explicit fields."""
        with self._lock:
            self._available()
            if self._revision:
                raise SessionError("A session's initial request can only be started once.")
            request = _normalized(request)
            try:
                explicit = frozenset(user_provided_fields)
            except (TypeError, ValueError):
                raise SessionError("User-provided fields must name normalized request values.") from None
            if isinstance(user_provided_fields, str) or not explicit <= _VALUE_FIELDS:
                raise SessionError("User-provided fields must name normalized request values.")
            context = self._admit(request, explicit, ())
        return await self._execute(context, run)

    async def follow_up(self, original_request: str, *, changes: Mapping[str, object],
                        run: SessionRunner) -> SkeletonReport:
        """Replace only explicitly supplied fields; omitted values are preserved.

        Nullable values can be cleared with None and lists with []. Lists are
        explicit whole-field replacements; no constraint/preference DSL is added.
        """
        with self._lock:
            self._available()
            if not self._reports or self._reports[-1].state.status not in TERMINAL_OUTCOMES:
                raise SessionError("Follow-ups require a terminal investigation; clarification resumption is deferred.")
            if not isinstance(changes, Mapping) or not set(changes) <= _CHANGES:
                raise SessionError("Follow-up changes must name normalized request fields.")
            data = self._context.request.model_dump() | deepcopy(dict(changes)) | {"original_request": original_request}
            try:
                request = _normalized(NormalizedRequest.model_validate(data))
            except (ValueError, TypeError):
                raise SessionError("The normalized follow-up is invalid.") from None
            explicit = self._context.user_provided_fields | (set(changes) & _VALUE_FIELDS)
            context = self._admit(request, frozenset(explicit), tuple(sorted(changes)))
        return await self._execute(context, run)

    def _admit(self, request, explicit, changed):
        self._revision += 1
        prior = self._reports[-1].state.investigation_id if self._reports else None
        self._context = SessionRequest(self._session_id, self._revision, prior, explicit, changed,
                                       request.model_dump_json().encode("utf-8"))
        self._busy = True
        return self._context

    def _check_report(self, report, context):
        report = deepcopy(report)
        state = InvestigationState.model_validate(report.state.model_dump())
        budgets = report.budgets
        limits = InvestigationLimits()
        if ((state.session_id, state.request_revision) != (context.session_id, context.request_revision)
                or state.investigation_id in {r.state.investigation_id for r in self._reports}
                or NormalizedRequest.model_validate({key: getattr(state, key) for key in _REQUEST_FIELDS}) != context.request
                or state.status not in {*TERMINAL_OUTCOMES, "AWAITING_CLARIFICATION"}
                or not budgets.closed or budgets.active_specialists or budgets.reserved_tool_calls or budgets.reserved_model_calls
                or (state.iteration_count, state.tool_call_count, state.retry_count, state.fallback_attempted) !=
                   (budgets.iterations, budgets.tool_calls, budgets.retries, bool(budgets.fallbacks))
                or (state.max_iterations, state.max_tool_calls, state.max_retries) !=
                   (limits.max_coordinator_iterations, limits.max_environmental_tool_invocations, limits.max_retries_per_failed_invocation)
                or state.iteration_count > limits.max_coordinator_iterations
                or state.tool_call_count > limits.max_environmental_tool_invocations
                or not 0 <= budgets.model_calls <= limits.max_llm_invocations
                or any(f.investigation_id != state.investigation_id for f in state.weather_findings + state.ocean_findings)):
            raise SessionError("The investigation report does not match the admitted request.")
        if report.result is not None:
            result = RecommendationResult.model_validate(report.result.model_dump())
            if ((result.investigation_id, result.request_revision, result.result_id, result.outcome) !=
                    (state.investigation_id, state.request_revision, state.result_id, state.outcome)
                    or not report.trace_writable or report.result_validation is None):
                raise SessionError("The result does not match the session investigation.")
        elif state.status in {"COMPLETED", "ABSTAINED"}:
            raise SessionError("A successful terminal investigation requires a validated result.")
        if state.status == "AWAITING_CLARIFICATION" and (report.result is not None or state.tool_call_count or state.assessments):
            raise SessionError("Clarification cannot publish a result or inherit an assessment.")
        return report

    async def _execute(self, context, run):
        try:
            report = self._check_report(await run(context), context)
            with self._lock:
                self._reports.append(report)
            return deepcopy(report)
        except Exception:
            with self._lock:
                self._blocked = True
            raise SessionError("Session execution did not return a correlated investigation; start a new session.") from None
        except BaseException:
            # Cancellation/interruption has no approved terminal representation.
            # Do not invent one, reopen history, or admit another active request.
            with self._lock:
                self._blocked = True
            raise
        finally:
            with self._lock:
                self._busy = False

    def close(self) -> None:
        """End admission after work returns; this is not cancellation or storage."""
        with self._lock:
            if self._busy:
                raise SessionError("An active investigation cannot be interrupted by closing its session.")
            self._closed = True
