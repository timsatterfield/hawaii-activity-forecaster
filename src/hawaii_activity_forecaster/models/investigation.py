"""Logical investigation snapshots (03 §5), without orchestration or transitions."""

from typing import Self

from pydantic import StrictBool, model_validator

from .assessment import CandidateAssessment
from .common import (
    CalendarDate, ContractModel, JsonObject, NonNegativeInt, PositiveInt,
    Text, TimeRange, Timestamp, chronological, unique,
)
from .enums import Activity, AgentType, ExperienceLevel, InvestigationStatus, IssueType, Outcome, RequestStatus
from .evidence import EnvironmentalFinding


class NormalizedRequest(ContractModel):
    original_request: Text
    activity: Activity | None = None
    target_date: CalendarDate | None = None
    target_time_window: TimeRange | None = None
    preferred_area: Text | None = None
    experience_level: ExperienceLevel | None = None
    hard_constraints: list[JsonObject]
    soft_preferences: list[JsonObject]
    clarification_needed: StrictBool
    clarification_questions: list[Text]


class EvidenceRequest(ContractModel):
    request_id: Text
    agent_type: AgentType
    candidate_beach_ids: list[Text]
    target_time_window: TimeRange
    request_status: RequestStatus


class EvidenceIssue(ContractModel):
    issue_id: Text
    issue_type: IssueType
    finding_ids: list[Text]
    affected_beach_ids: list[Text]
    description: Text
    resolved: StrictBool


TERMINAL_OUTCOMES = {
    InvestigationStatus.COMPLETED: Outcome.RECOMMENDATIONS,
    InvestigationStatus.ABSTAINED: Outcome.NO_RECOMMENDATION,
    InvestigationStatus.FAILED: Outcome.ERROR,
}


class InvestigationState(NormalizedRequest):
    # Logical field groups are flattened; no undocumented normalized_request envelope.
    investigation_id: Text
    session_id: Text
    schema_version: Text
    created_at: Timestamp
    updated_at: Timestamp
    status: InvestigationStatus
    request_revision: PositiveInt
    candidate_beach_ids: list[Text]
    assessments: list[CandidateAssessment]
    investigated_beach_ids: list[Text]
    remaining_candidate_ids: list[Text]
    weather_findings: list[EnvironmentalFinding]
    ocean_findings: list[EnvironmentalFinding]
    pending_evidence_requests: list[EvidenceRequest]
    unresolved_evidence_issues: list[EvidenceIssue]
    iteration_count: NonNegativeInt
    max_iterations: PositiveInt
    tool_call_count: NonNegativeInt
    max_tool_calls: PositiveInt
    retry_count: NonNegativeInt
    max_retries: NonNegativeInt
    deadline_at: Timestamp | None = None
    remaining_actions: list[JsonObject]
    active_errors: list[JsonObject]
    recovery_actions: list[JsonObject]
    fallback_attempted: StrictBool
    outcome: Outcome | None = None
    result_id: Text | None = None
    completion_reason: Text | None = None

    @model_validator(mode="after")
    def consistency(self) -> Self:
        chronological(self.created_at, self.updated_at, "investigation")
        unique(self.candidate_beach_ids, "candidate IDs")
        unique([a.assessment_id for a in self.assessments], "assessment IDs")
        findings = self.weather_findings + self.ocean_findings
        unique([f.finding_id for f in findings], "finding IDs")
        for domain, entries in ((AgentType.WEATHER, self.weather_findings), (AgentType.OCEAN, self.ocean_findings)):
            if any(f.agent_type != domain for f in entries):
                raise ValueError("finding stored in incorrect specialist domain")
        if any(a.investigation_id != self.investigation_id for a in self.assessments):
            raise ValueError("assessment belongs to a different investigation")
        if any(a.beach_id not in self.candidate_beach_ids for a in self.assessments):
            raise ValueError("assessment references a beach outside the candidate set")
        # Retry count is an investigation aggregate; max_retries is per failed invocation.
        # Do not compare them or implement dispatch budgets inside this schema.
        expected = TERMINAL_OUTCOMES.get(self.status)
        if expected is not None:
            if self.outcome != expected or not self.result_id or not self.completion_reason:
                raise ValueError("terminal state requires matching outcome, result_id and completion_reason")
            if self.status == InvestigationStatus.COMPLETED and (
                self.clarification_needed or self.activity is None or self.target_time_window is None
            ):
                raise ValueError("recommendations require an unambiguous activity and time window")
        elif any(v is not None for v in (self.outcome, self.result_id, self.completion_reason)):
            raise ValueError("nonterminal state cannot carry a final outcome")
        return self
