"""Trusted specialist authorization and deterministic contract-level merging.

Findings remain PENDING. This component does not establish freshness, geographic
applicability, category completeness, eligibility, or environmental safety.
"""

from collections import defaultdict
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import json

from pydantic import BaseModel, ValidationError

from hawaii_activity_forecaster.harness.policy import CATEGORY_SOURCES
from hawaii_activity_forecaster.models import (
    BeachCatalog, EvidenceIssue, EvidenceRequest, InvestigationState,
    SpecialistInvestigationRequest, SpecialistInvestigationResponse,
)
from hawaii_activity_forecaster.models.enums import (
    AgentType, InvestigationStatus, RequestStatus, RetrievalStatus, ValidationStatus,
)
from hawaii_activity_forecaster.models.permissions import OCEAN_SOURCES, WEATHER_SOURCES


class SpecialistContractError(ValueError):
    """The proposed delegation is not authorized; do not dispatch it."""


@dataclass(frozen=True)
class SpecialistDelivery:
    """Origin metadata comes from the dispatcher, never from the specialist."""

    request_id: str
    attempt_number: int
    response: object = None
    execution_failed: bool = False


@dataclass(frozen=True)
class DeliveryRejection:
    request_id: str
    attempt_number: int
    response_id: str | None
    reason: str
    response_correlation: tuple[tuple[str, str | int], ...] = ()


@dataclass(frozen=True)
class MergeReport:
    state: InvestigationState
    accepted_response_ids: tuple[str, ...]
    duplicate_response_ids: tuple[str, ...]
    rejections: tuple[DeliveryRejection, ...]


def _rejection(delivery: SpecialistDelivery, reason: str, response=None) -> DeliveryRejection:
    """Keep schema-valid reported identities, never raw rejected payloads/errors."""
    if response is None:
        try:
            response = SpecialistInvestigationResponse.model_validate(_data(delivery.response))
        except (ValidationError, TypeError, ValueError):
            return DeliveryRejection(delivery.request_id, delivery.attempt_number, None, reason)
    fields = {"investigation_id", "request_revision", "request_id", "agent_type", "attempt_number"}
    correlation = tuple(sorted(response.model_dump(mode="json", include=fields).items()))
    return DeliveryRejection(delivery.request_id, delivery.attempt_number, response.response_id, reason, correlation)


def _data(value):
    return value.model_dump() if isinstance(value, BaseModel) else deepcopy(value)


def _fingerprint(value) -> str:
    data = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _finding_fingerprint(finding) -> str:
    # A callback has no authority over independent evidence-validation status.
    return _fingerprint(finding.model_copy(update={"validation_status": ValidationStatus.PENDING}))


def _replace(state: InvestigationState, now: datetime, **changes) -> InvestigationState:
    return InvestigationState.model_validate({**state.model_dump(), "updated_at": now, **changes})


class SpecialistExchange:
    """One investigation's trusted, sequential request/delivery ledger.

    Call from the graph's authorization and join nodes, not concurrently from
    branches. Public inputs and returned state are detached from private records.
    Registering a later attempt supersedes the earlier one but does not authorize
    execution, retries, tools, or budgets; those remain the dispatcher's concern.
    """

    def __init__(self, state: InvestigationState, catalog: BeachCatalog, *,
                 investigation_candidate_ids: tuple[str, ...] | None = None):
        catalog = BeachCatalog.model_validate(catalog.model_dump())
        self._beaches = frozenset(beach.beach_id for beach in catalog.root)
        self._dispatch_beaches = (self._beaches if investigation_candidate_ids is None
                                  else frozenset(investigation_candidate_ids))
        if investigation_candidate_ids is not None and not self._dispatch_beaches <= self._beaches & set(state.candidate_beach_ids):
            raise SpecialistContractError("CANDIDATE_SCOPE_INVALID")
        self._identity = (state.investigation_id, state.request_revision)
        self._requests: dict[str, SpecialistInvestigationRequest] = {}
        self._responses: dict[str, str] = {}
        self._artifacts: dict[tuple[str, str], str] = {}
        self._closed = False

    def close(self):
        self._closed = True

    def _active(self, state: InvestigationState, now: datetime):
        if (self._closed or (state.investigation_id, state.request_revision) != self._identity
                or state.status not in (InvestigationStatus.INVESTIGATING, InvestigationStatus.EVALUATING)):
            raise SpecialistContractError("INVESTIGATION_INACTIVE")
        if state.deadline_at is not None and now >= state.deadline_at:
            raise SpecialistContractError("INVESTIGATION_EXPIRED")

    def authorize(self, state: InvestigationState, requests: Sequence[SpecialistInvestigationRequest],
                  *, now: datetime) -> InvestigationState:
        """Validate the entire proposed batch before recording any delegation."""
        state = InvestigationState.model_validate(state.model_dump())
        self._active(state, now)
        if not set(state.candidate_beach_ids) <= self._beaches:
            raise SpecialistContractError("CANDIDATE_SCOPE_INVALID")
        checked = []
        roles, identifiers = set(), set()
        for raw in requests:
            try:
                request = SpecialistInvestigationRequest.model_validate(_data(raw))
            except (ValidationError, TypeError, ValueError):
                raise SpecialistContractError("REQUEST_SCHEMA_INVALID") from None
            if request.agent_type in roles or request.request_id in identifiers:
                raise SpecialistContractError("DUPLICATE_DELEGATION")
            roles.add(request.agent_type)
            identifiers.add(request.request_id)
            if (request.investigation_id != state.investigation_id
                    or request.request_revision != state.request_revision
                    or request.schema_version != state.schema_version):
                raise SpecialistContractError("REQUEST_CORRELATION_INVALID")
            if (not request.candidate_beach_ids
                    or not set(request.candidate_beach_ids) <= self._dispatch_beaches & set(state.candidate_beach_ids)):
                raise SpecialistContractError("CANDIDATE_SCOPE_INVALID")
            if request.target_time_window != state.target_time_window:
                raise SpecialistContractError("TARGET_WINDOW_INVALID")
            if request.issued_at > now or (request.deadline_at is not None and now >= request.deadline_at):
                raise SpecialistContractError("REQUEST_EXPIRED_OR_NOT_ISSUED")
            if (state.deadline_at is not None and
                    (request.deadline_at is None or request.deadline_at > state.deadline_at)):
                raise SpecialistContractError("DEADLINE_SCOPE_INVALID")
            sources = WEATHER_SOURCES if request.agent_type == AgentType.WEATHER else OCEAN_SOURCES
            if not request.requested_evidence or any(
                not CATEGORY_SOURCES.get(requirement.evidence_type, set()) & sources
                for requirement in request.requested_evidence
            ):
                raise SpecialistContractError("EVIDENCE_SCOPE_INVALID")
            known_findings = {f.finding_id for f in state.weather_findings + state.ocean_findings}
            if (len({gap.gap_id for gap in request.known_evidence_gaps}) != len(request.known_evidence_gaps)
                    or any(not set(gap.related_finding_ids) <= known_findings for gap in request.known_evidence_gaps)):
                raise SpecialistContractError("KNOWN_GAP_INVALID")
            previous = self._requests.get(request.request_id)
            if previous is None:
                if request.attempt_number != 1:
                    raise SpecialistContractError("INITIAL_ATTEMPT_INVALID")
            else:
                fields = {"attempt_number", "issued_at", "deadline_at"}
                if (request.attempt_number != previous.attempt_number + 1
                        or request.model_dump(exclude=fields) != previous.model_dump(exclude=fields)):
                    raise SpecialistContractError("ATTEMPT_OR_LOGICAL_REQUEST_INVALID")
            checked.append(request)
        pending = {r.request_id: r for r in state.pending_evidence_requests}
        for request in checked:
            pending[request.request_id] = EvidenceRequest(
                request_id=request.request_id, agent_type=request.agent_type,
                candidate_beach_ids=request.candidate_beach_ids,
                target_time_window=request.target_time_window, request_status=RequestStatus.PENDING,
            )
        updated = _replace(state, now, pending_evidence_requests=[pending[key] for key in sorted(pending)])
        self._requests.update({r.request_id: r for r in checked})
        return updated

    def _validate(self, state, delivery, now):
        request = self._requests.get(delivery.request_id)
        if request is None:
            raise SpecialistContractError("UNKNOWN_REQUEST")
        if delivery.attempt_number != request.attempt_number:
            raise SpecialistContractError("OUTDATED_ATTEMPT")
        if request.deadline_at is not None and now >= request.deadline_at:
            raise SpecialistContractError("RESPONSE_EXPIRED")
        if delivery.execution_failed:
            raise SpecialistContractError("SPECIALIST_EXECUTION_FAILED")
        try:
            response = SpecialistInvestigationResponse.model_validate(_data(delivery.response))
        except (ValidationError, ValueError, TypeError):
            raise SpecialistContractError("RESPONSE_SCHEMA_INVALID") from None
        if (response.investigation_id != state.investigation_id
                or response.request_revision != state.request_revision
                or response.attempt_number != request.attempt_number):
            raise SpecialistContractError("OUTDATED_RESPONSE")
        for field in ("request_id", "investigation_id", "request_revision", "schema_version", "agent_type", "attempt_number"):
            if getattr(response, field) != getattr(request, field):
                raise SpecialistContractError("RESPONSE_CORRELATION_INVALID")
        if (response.started_at < request.issued_at or response.completed_at > now
                or (request.deadline_at is not None and response.completed_at > request.deadline_at)):
            raise SpecialistContractError("RESPONSE_TIMING_INVALID")
        sources = WEATHER_SOURCES if request.agent_type == AgentType.WEATHER else OCEAN_SOURCES
        requested_sources = set().union(*(CATEGORY_SOURCES[r.evidence_type] for r in request.requested_evidence))
        for finding in response.findings:
            if (finding.source_id not in sources & requested_sources
                    or (finding.beach_id is not None and finding.beach_id not in request.candidate_beach_ids)):
                raise SpecialistContractError("FINDING_SCOPE_INVALID")
        if any(error.source_id is not None and error.source_id not in sources & requested_sources
               for error in response.errors):
            raise SpecialistContractError("ERROR_SOURCE_SCOPE_INVALID")
        known = {f.finding_id for f in state.weather_findings + state.ocean_findings + response.findings}
        if any(not set(gap.related_finding_ids) <= known for gap in response.unresolved_gaps):
            raise SpecialistContractError("GAP_REFERENCE_INVALID")
        # This is the only field the contract boundary normalizes. Source metadata,
        # measurements, geographic coverage and evidence timestamps remain intact.
        return SpecialistInvestigationResponse.model_validate({
            **response.model_dump(), "findings": [
                {**finding.model_dump(), "validation_status": ValidationStatus.PENDING}
                for finding in response.findings
            ],
        }), request

    @staticmethod
    def _artifacts_for(response, request):
        artifacts = []
        for finding in response.findings:
            artifacts.append((("finding", finding.finding_id), _finding_fingerprint(finding)))
        for gap in response.unresolved_gaps:
            issue = EvidenceIssue(
                issue_id=gap.gap_id, issue_type=gap.gap_type, finding_ids=gap.related_finding_ids,
                affected_beach_ids=sorted(request.candidate_beach_ids), description=gap.description, resolved=False,
            )
            artifacts.append((("gap", gap.gap_id), _fingerprint(issue)))
        for error in response.errors:
            artifacts.append((("error", error.error_id), _fingerprint(error)))
        return artifacts

    def merge(self, state: InvestigationState, deliveries: Sequence[SpecialistDelivery], *, now: datetime) -> MergeReport:
        """Validate a collected batch, quarantine collisions, then apply one write.

        Changed content under the same stable ID rejects every affected response
        in this batch, independent of arrival order. Previously committed content
        is immutable. Other responses, including the other specialist, survive.
        """
        state = InvestigationState.model_validate(state.model_dump())
        rejections = []
        try:
            self._active(state, now)
        except SpecialistContractError as error:
            return MergeReport(state, (), (), tuple(
                _rejection(d, str(error)) for d in deliveries
            ))
        candidates = []
        for delivery in deliveries:
            try:
                response, request = self._validate(state, delivery, now)
                candidates.append((delivery, response, request))
            except SpecialistContractError as error:
                rejections.append(_rejection(delivery, str(error)))
        # Compare to both prior state and prior deliveries, including findings that
        # independent validation might since have marked ACCEPTED/LIMITED/REJECTED.
        prior = dict(self._artifacts)
        for finding in state.weather_findings + state.ocean_findings:
            prior[("finding", finding.finding_id)] = _finding_fingerprint(finding)
        for issue in state.unresolved_evidence_issues:
            prior.setdefault(("gap", issue.issue_id), _fingerprint(issue))
        variants = defaultdict(set)
        for _, response, request in candidates:
            variants[("response", response.response_id)].add(_fingerprint(response))
            for key, fingerprint in self._artifacts_for(response, request):
                variants[key].add(fingerprint)
        prior.update({("response", key): value for key, value in self._responses.items()})
        collisions = {key for key, values in variants.items()
                      if len(values | ({prior[key]} if key in prior else set())) > 1}
        accepted, duplicates = [], []
        responses = dict(self._responses)
        artifacts = dict(self._artifacts)
        findings = {f.finding_id: f for f in state.weather_findings + state.ocean_findings}
        issues = {issue.issue_id: issue for issue in state.unresolved_evidence_issues}
        errors = {_fingerprint(error): error for error in state.active_errors}
        completed_requests, failed_requests = set(), set()
        for delivery, response, request in sorted(candidates, key=lambda item: item[1].response_id):
            material = self._artifacts_for(response, request)
            keys = {("response", response.response_id)} | {key for key, _ in material}
            if keys & collisions:
                rejections.append(_rejection(delivery, "IDENTIFIER_CONTENT_CONFLICT", response))
                continue
            if response.response_id in responses:
                duplicates.append(response.response_id)
                continue
            responses[response.response_id] = _fingerprint(response)
            artifacts.update(material)
            accepted.append(response.response_id)
            for finding in response.findings:
                findings.setdefault(finding.finding_id, finding)
            for gap in response.unresolved_gaps:
                issues.setdefault(gap.gap_id, EvidenceIssue(
                    issue_id=gap.gap_id, issue_type=gap.gap_type, finding_ids=gap.related_finding_ids,
                    affected_beach_ids=sorted(request.candidate_beach_ids), description=gap.description, resolved=False,
                ))
            for error in response.errors:
                row = {**error.model_dump(mode="json"), "request_id": request.request_id,
                       "attempt_number": request.attempt_number}
                errors[_fingerprint(row)] = row
            target = (failed_requests if response.status in (RetrievalStatus.ERROR, RetrievalStatus.UNAVAILABLE)
                      else completed_requests)
            target.add(request.request_id)
        for rejection in rejections:
            request = self._requests.get(rejection.request_id)
            # A stale/unknown envelope may be observed but cannot change even the
            # current request status or error list.
            if (request is None or rejection.attempt_number != request.attempt_number
                    or rejection.reason == "OUTDATED_RESPONSE"):
                continue
            failed_requests.add(request.request_id)
            row = {"error_id": f"{request.request_id}:{request.attempt_number}:{rejection.reason}",
                   "error_code": rejection.reason, "message": "Specialist delivery rejected",
                   "request_id": request.request_id, "attempt_number": request.attempt_number,
                   "retryable": False}
            errors[_fingerprint(row)] = row
        pending = []
        for entry in state.pending_evidence_requests:
            completed = entry.request_id in completed_requests or entry.request_status == RequestStatus.COMPLETED
            status = (RequestStatus.COMPLETED if completed else
                      RequestStatus.FAILED if entry.request_id in failed_requests else entry.request_status)
            pending.append({**entry.model_dump(), "request_status": status})
        changes = dict(
            weather_findings=[findings[key] for key in sorted(findings) if findings[key].agent_type == AgentType.WEATHER],
            ocean_findings=[findings[key] for key in sorted(findings) if findings[key].agent_type == AgentType.OCEAN],
            unresolved_evidence_issues=[issues[key] for key in sorted(issues)],
            active_errors=[errors[key] for key in sorted(errors)], pending_evidence_requests=pending,
        )
        # Exact replay and entirely stale batches have no logical state effect,
        # including updated_at. The graph records observation events separately.
        proposed = InvestigationState.model_validate({**state.model_dump(), **changes})
        changed = proposed != state and bool(accepted or failed_requests)
        updated = _replace(state, now, **changes) if changed else state
        self._responses, self._artifacts = responses, artifacts
        return MergeReport(updated, tuple(accepted), tuple(sorted(duplicates)), tuple(sorted(
            rejections, key=lambda r: (r.request_id, r.attempt_number, r.response_id or "", r.reason),
        )))
