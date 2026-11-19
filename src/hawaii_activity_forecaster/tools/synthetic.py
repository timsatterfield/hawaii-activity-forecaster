"""Scoped synthetic environmental dispatch and explicitly planned recovery only."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from threading import RLock
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import Field, ValidationError, model_validator

from hawaii_activity_forecaster.harness.policy import CATEGORY_SOURCES, Category
from hawaii_activity_forecaster.harness.synthetic import SyntheticDriver
from hawaii_activity_forecaster.models import (
    EnvironmentalToolRequest, EnvironmentalToolResponse, EvidenceGap, SpecialistError,
    SpecialistInvestigationRequest, SpecialistInvestigationResponse,
    TimeRange,
)
from hawaii_activity_forecaster.models.common import ContractModel, JsonObject, Text
from hawaii_activity_forecaster.models.enums import AgentType, TraceEventType, ValidationStatus
from hawaii_activity_forecaster.models.permissions import OCEAN_SOURCES, WEATHER_SOURCES

if TYPE_CHECKING:
    from hawaii_activity_forecaster.orchestration.budgets import BudgetManager


class ToolPlanError(ValueError):
    """A trusted tool plan violates scope or recovery constraints."""


@dataclass(frozen=True)
class RetrievalGap:
    """Trusted operational correlation; not an environmental policy verdict."""

    gap_id: str
    investigation_id: str
    request_revision: int
    category: Category
    candidate_beach_ids: tuple[str, ...]
    target_time_window: TimeRange


class ToolAction(ContractModel):
    """Explicit trusted plan, not a script-selected operation or model instruction."""

    action_id: Text
    source_id: Text
    candidate_beach_ids: list[Text] = Field(min_length=1)
    requested_evidence: list[Category] = Field(min_length=1)
    geographic_scope: JsonObject
    retry_of: Text | None = None
    fallback_of: Text | None = None

    @model_validator(mode="after")
    def shape(self):
        if (len(set(self.candidate_beach_ids)) != len(self.candidate_beach_ids)
                or len(set(self.requested_evidence)) != len(self.requested_evidence)
                or (self.retry_of is not None and self.fallback_of is not None)):
            raise ValueError("ambiguous tool action")
        return self


def _material(action: ToolAction):
    return (action.source_id, sorted(action.candidate_beach_ids), sorted(action.requested_evidence),
            json.dumps(action.geographic_scope, sort_keys=True))


class SyntheticToolDispatcher:
    """One investigation's trusted dispatcher, sharing its actual budget manager.

    Virtual delivery is synchronous and serialized under this lock. Specialist
    coroutines may overlap, but no lock is held across an await. Virtual clocks
    are per specialist execution so independent completion order cannot shift
    source applicability or the other branch's timeout clock.
    """

    def __init__(self, driver: SyntheticDriver, budgets: BudgetManager, *, investigation_id: str,
                 request_revision: int, reference_time: datetime, emit: Callable,
                 request_step: int = 1, investigation_candidate_ids: tuple[str, ...] | None = None):
        self.driver, self.budgets = driver, budgets
        self._identity = investigation_id, request_revision
        self._reference_time, self._emit_callback = reference_time, emit
        self._step = request_step
        self._dispatch_beaches = (None if investigation_candidate_ids is None else frozenset(investigation_candidate_ids))
        self._lock = RLock()
        self._plans = {}
        self._seen = set()
        self._ran = set()
        self._closed = False
        self._gap_scopes: dict[str, RetrievalGap] = {}

    @property
    def gap_scopes(self) -> tuple[RetrievalGap, ...]:
        with self._lock:
            return tuple(self._gap_scopes[key] for key in sorted(self._gap_scopes))

    def close(self):
        with self._lock:
            self._closed = True

    def _emit(self, event, **details):
        try:
            self._emit_callback(event, **details)
        except Exception:
            self._closed = True
            self.budgets.close()
            raise

    def register(self, parent: SpecialistInvestigationRequest, actions: Sequence[ToolAction]):
        parent = SpecialistInvestigationRequest.model_validate(parent.model_dump())
        actions = tuple(ToolAction.model_validate(a.model_dump()) for a in actions)
        with self._lock:
            if self._closed or (parent.investigation_id, parent.request_revision) != self._identity:
                raise ToolPlanError("Inactive tool execution")
            if self._dispatch_beaches is not None and not set(parent.candidate_beach_ids) <= self._dispatch_beaches:
                raise ToolPlanError("Delegation exceeds the selected investigation scope")
            key = parent.request_id, parent.attempt_number
            if key in self._plans:
                raise ToolPlanError("Tool plan already registered")
            prior = {}
            categories = {r.evidence_type for r in parent.requested_evidence}
            required = {r.evidence_type for r in parent.requested_evidence if r.priority == "REQUIRED"}
            sources = WEATHER_SOURCES if parent.agent_type == AgentType.WEATHER else OCEAN_SOURCES
            for action in actions:
                if action.action_id in prior or action.action_id in self._seen:
                    raise ToolPlanError("Action IDs cannot be reused")
                if (not set(action.candidate_beach_ids) <= set(parent.candidate_beach_ids)
                        or not set(action.requested_evidence) <= categories
                        or action.source_id not in sources
                        or any(action.source_id not in CATEGORY_SOURCES.get(c, set()) for c in action.requested_evidence)):
                    raise ToolPlanError("Tool action exceeds delegated scope")
                origin_id = action.retry_of or action.fallback_of
                if origin_id is not None:
                    origin = prior.get(origin_id)
                    if origin is None:
                        raise ToolPlanError("Recovery must reference an earlier action")
                    if action.retry_of is not None:
                        if origin.retry_of is not None or _material(origin) != _material(action):
                            raise ToolPlanError("Retry changes scope or retries a retry")
                    elif (origin.fallback_of is not None or len(action.requested_evidence) != 1
                          or not set(action.requested_evidence) <= required & set(origin.requested_evidence)
                          or set(action.candidate_beach_ids) != set(origin.candidate_beach_ids)
                          or action.source_id == origin.source_id):
                        raise ToolPlanError("Fallback must address one required gap through another permitted source")
                prior[action.action_id] = action
            self._plans[key] = parent, actions
            self._seen.update(prior)

    def _gap_id(self, parent, candidates, category):
        # No caller label, source or logical delegation ID can refresh the same
        # required category/candidate/window gap inside this investigation/revision.
        scope = [*self._identity, sorted(candidates), category,
                 parent.target_time_window.start.astimezone(timezone.utc).isoformat(),
                 parent.target_time_window.end.astimezone(timezone.utc).isoformat()]
        gap_id = "gap-" + sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()
        with self._lock:
            self._gap_scopes[gap_id] = RetrievalGap(
                gap_id, *self._identity, Category(category), tuple(sorted(candidates)),
                TimeRange.model_validate(parent.target_time_window.model_dump()),
            )
        return gap_id

    def _invoke(self, parent, action, elapsed, outcomes, gaps):
        with self._lock:
            if self._closed or self.budgets.snapshot().closed:
                raise ToolPlanError("Tool execution is closed")
            origin = outcomes.get(action.retry_of or action.fallback_of)
            if action.retry_of:
                if origin is None or not origin[1]:  # No retry of success/permanent failure.
                    return None
            gap_id = None
            if action.fallback_of:
                category = action.requested_evidence[0]
                gap_id = self._gap_id(parent, action.candidate_beach_ids, category)
                if origin is None or gap_id not in gaps:
                    return None
            now = datetime.now(timezone.utc)
            if parent.deadline_at is not None and now >= parent.deadline_at:
                raise ToolPlanError("Specialist delegation expired")
            call_id = str(uuid4())
            tool_request = EnvironmentalToolRequest(
                tool_call_id=call_id, investigation_id=parent.investigation_id, agent_type=parent.agent_type,
                source_id=action.source_id, requested_evidence=action.requested_evidence,
                target_time_window=parent.target_time_window, geographic_scope=action.geographic_scope,
                issued_at=self._reference_time + timedelta(milliseconds=elapsed),
            )
            operation_id, attempt = self.driver.peek(tool_request, tuple(action.candidate_beach_ids), self._step,
                                                     retry=action.retry_of is not None)
            self.budgets.reserve(call_id, "tool", retry_of=origin[0] if action.retry_of else None,
                                 fallback_gap=gap_id)
            details = dict(tool_call_id=call_id, request_id=parent.request_id,
                           specialist_attempt=parent.attempt_number, operation_id=operation_id,
                           operation_attempt=attempt, source_id=action.source_id,
                           tool_name=action.source_id, agent_type=parent.agent_type.value,
                           candidate_beach_ids=list(action.candidate_beach_ids),
                           requested_evidence=list(action.requested_evidence),
                           target_time_window=parent.target_time_window.model_dump(mode="json"))
            if action.retry_of:
                self._emit(TraceEventType.RETRY_INITIATED, **details, original_tool_call_id=origin[0], reason="RETRYABLE_TOOL_FAILURE")
            if action.fallback_of:
                self._emit(TraceEventType.FALLBACK_INITIATED, **details, gap_id=gap_id,
                           original_tool_call_id=origin[0], reason="REQUIRED_EVIDENCE_GAP")
            self._emit(TraceEventType.TOOL_CALLED, **details)
            self.budgets.dispatch(call_id)
            try:
                delivery = self.driver.deliver(tool_request, operation_id, attempt)
            except Exception:
                self.budgets.finish(call_id, failed=True, retryable=False)
                self._emit(TraceEventType.TOOL_FAILED, **details, execution_status="ERROR", duration_ms=0,
                           result_reference_ids=[], error_codes=["TOOL_EXECUTION_FAILED"], error_code="TOOL_EXECUTION_FAILED")
                raise
            finished = self._reference_time + timedelta(milliseconds=elapsed + delivery.elapsed_ms)
            response = None
            errors = []
            failure_code = "SOURCE_TIMEOUT" if delivery.timed_out else None
            if not delivery.timed_out:
                try:
                    responses = [EnvironmentalToolResponse.model_validate(payload) for payload in delivery.payloads]
                    response = responses[0]
                    if any(r != response for r in responses):
                        raise ValueError("Changed duplicate delivery")
                    if response.tool_call_id != call_id or response.source_id != action.source_id:
                        raise ValueError("Tool correlation mismatch")
                    for finding in response.findings:
                        if (finding.investigation_id != parent.investigation_id or finding.agent_type != parent.agent_type
                                or (finding.beach_id is not None and finding.beach_id not in action.candidate_beach_ids)):
                            raise ValueError("Tool finding exceeds scope")
                    errors = [SpecialistError.model_validate(error) for error in response.errors]
                    if response.retrieval_status == "ERROR" and not errors:
                        raise ValueError("Missing structured error")
                    if response.retrieval_status in {"PARTIAL", "UNAVAILABLE"} and not (errors or response.missing_evidence):
                        raise ValueError("Missing explicit incomplete coverage")
                except (ValidationError, ValueError, TypeError, IndexError):
                    response = None
                    failure_code = "SOURCE_RESPONSE_INVALID"
            if failure_code:
                errors = [SpecialistError(error_id=str(uuid4()), error_code=failure_code,
                                         message="Synthetic invocation timed out" if delivery.timed_out else "Invalid synthetic tool response",
                                         source_id=action.source_id, tool_call_id=call_id, retryable=True)]
            failed = response is None or response.retrieval_status in {"ERROR", "UNAVAILABLE"}
            retryable = failed and any(error.retryable for error in errors)
            self.budgets.finish(call_id, failed=failed, retryable=retryable)
            binding = next((b for b in self.driver.bindings if b.runtime_tool_call_id == call_id), None)
            self._emit(TraceEventType.TOOL_FAILED if failed else TraceEventType.TOOL_COMPLETED, **details,
                       elapsed_ms=delivery.elapsed_ms, virtual_completed_at=finished.isoformat(),
                       error_codes=[error.error_code for error in errors], error_code=errors[0].error_code if errors else None,
                       delivery_count=len(delivery.payloads),
                       duration_ms=max(0, int((datetime.now(timezone.utc) - now).total_seconds() * 1000)),
                       simulated_duration_ms=delivery.elapsed_ms,
                       source_fixture_id=binding.source_fixture_id if binding else None,
                       result_reference_ids=[f.runtime_finding_id for f in binding.findings] if binding else [],
                       execution_status="TIMEOUT" if delivery.timed_out else "ERROR" if failed else
                       "PARTIAL" if response.retrieval_status == "PARTIAL" else "SUCCESS",
                       retrieval_status=response.retrieval_status if response else None)
            return call_id, retryable, response, errors, delivery.elapsed_ms

    async def run(self, supplied: SpecialistInvestigationRequest) -> SpecialistInvestigationResponse:
        # Runtime import avoids a tools <-> orchestration package import cycle.
        from hawaii_activity_forecaster.orchestration.budgets import BudgetError
        key = supplied.request_id, supplied.attempt_number
        with self._lock:
            if key not in self._plans or key in self._ran:
                raise ToolPlanError("Unregistered or repeated specialist tool execution")
            self._ran.add(key)
            parent, actions = self._plans[key]
        started = datetime.now(timezone.utc)
        findings, errors, outcomes, gaps = {}, {}, {}, {}
        elapsed = 0
        # Required categories with no authorized retrieval stay explicitly missing.
        for requirement in parent.requested_evidence:
            if requirement.priority == "REQUIRED":
                gap_id = self._gap_id(parent, parent.candidate_beach_ids, requirement.evidence_type)
                gaps[gap_id] = (requirement.evidence_type, tuple(parent.candidate_beach_ids))
        await asyncio.sleep(0)
        for action in actions:
            try:
                result = self._invoke(parent, action, elapsed, outcomes, gaps)
            except BudgetError:
                error = SpecialistError(error_id=str(uuid4()), error_code="EXECUTION_LIMIT_REACHED",
                                        message="Environmental invocation allowance exhausted", retryable=False)
                errors[error.error_id] = error
                self._emit(TraceEventType.INVESTIGATION_LIMIT_REACHED, request_id=parent.request_id,
                           budget_kind="environmental_tool", configured_limit=12)
                for category in action.requested_evidence:
                    gaps[self._gap_id(parent, action.candidate_beach_ids, category)] = category, tuple(action.candidate_beach_ids)
                break
            if result is None:
                continue
            outcomes[action.action_id] = result
            _, _, response, received_errors, duration = result
            elapsed += duration
            for error in received_errors:
                errors[error.error_id] = error
            for category in action.requested_evidence:
                gap_id = self._gap_id(parent, action.candidate_beach_ids, category)
                if (response is None or response.retrieval_status != "SUCCESS"
                        or response.missing_evidence or response.errors):
                    gaps[gap_id] = category, tuple(action.candidate_beach_ids)
                else:
                    gaps.pop(gap_id, None)
            if response is not None:
                for finding in response.findings:
                    findings[finding.finding_id] = finding.model_copy(update={"validation_status": ValidationStatus.PENDING})
            await asyncio.sleep(0)
        explicit_gaps = [EvidenceGap(gap_id=key, gap_type="MISSING", related_finding_ids=[],
                                     description=f"Synthetic retrieval incomplete for {gaps[key][0]}; independent evidence validation is still required")
                         for key in sorted(gaps)]
        status = ("PARTIAL" if findings and (errors or explicit_gaps) else "ERROR" if errors and not findings
                  else "UNAVAILABLE" if explicit_gaps and not findings else "SUCCESS")
        return SpecialistInvestigationResponse(
            response_id=str(uuid4()), request_id=parent.request_id, investigation_id=parent.investigation_id,
            request_revision=parent.request_revision, schema_version=parent.schema_version,
            agent_type=parent.agent_type, attempt_number=parent.attempt_number, status=status,
            findings=[findings[key] for key in sorted(findings)], unresolved_gaps=explicit_gaps,
            errors=[errors[key] for key in sorted(errors)], started_at=started, completed_at=datetime.now(timezone.utc),
        )
