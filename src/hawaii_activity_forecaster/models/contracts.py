"""Specialist and external-tool data contracts (04 §§3, 4, 7)."""

from typing import Self

from pydantic import StrictBool, model_validator

from .common import (
    ContractModel, JsonObject, NonNegativeInt, PositiveInt, Text, TimeRange,
    Timestamp, chronological, unique,
)
from .enums import AgentType, EvidencePriority, IssueType, RetrievalStatus, SourceId
from .evidence import EnvironmentalFinding


class EvidenceRequirement(ContractModel):
    requirement_id: Text
    evidence_type: Text  # Vocabulary remains open (MAP-OD-002).
    priority: EvidencePriority
    reason: Text | None = None


class EvidenceGap(ContractModel):
    gap_id: Text
    gap_type: IssueType
    related_finding_ids: list[Text]
    description: Text


class SpecialistError(ContractModel):
    error_id: Text
    error_code: Text  # The specification lists proposed, non-exhaustive codes.
    message: Text
    source_id: Text | None = None
    tool_call_id: Text | None = None
    retryable: StrictBool


class SpecialistInvestigationRequest(ContractModel):
    request_id: Text
    investigation_id: Text
    request_revision: PositiveInt
    schema_version: Text
    agent_type: AgentType
    candidate_beach_ids: list[Text]
    target_time_window: TimeRange
    requested_evidence: list[EvidenceRequirement]
    known_evidence_gaps: list[EvidenceGap]
    issued_at: Timestamp
    attempt_number: PositiveInt
    deadline_at: Timestamp | None = None

    @model_validator(mode="after")
    def consistency(self) -> Self:
        chronological(self.issued_at, self.deadline_at, "specialist deadline")
        unique(self.candidate_beach_ids, "candidate IDs")
        unique([r.requirement_id for r in self.requested_evidence], "evidence requirement IDs")
        return self


class SpecialistInvestigationResponse(ContractModel):
    response_id: Text
    request_id: Text
    investigation_id: Text
    request_revision: PositiveInt
    schema_version: Text
    agent_type: AgentType
    attempt_number: PositiveInt
    status: RetrievalStatus
    findings: list[EnvironmentalFinding]
    unresolved_gaps: list[EvidenceGap]
    errors: list[SpecialistError]
    started_at: Timestamp
    completed_at: Timestamp

    @model_validator(mode="after")
    def consistency(self) -> Self:
        chronological(self.started_at, self.completed_at, "specialist execution")
        unique([f.finding_id for f in self.findings], "finding IDs")
        for finding in self.findings:
            if finding.investigation_id != self.investigation_id or finding.agent_type != self.agent_type:
                raise ValueError("finding investigation and domain must match response (SRS-002/004)")
        if self.status == RetrievalStatus.ERROR and not self.errors:
            raise ValueError("ERROR response requires structured errors (SRS-008)")
        if self.status == RetrievalStatus.PARTIAL and not (self.unresolved_gaps or self.errors):
            raise ValueError("PARTIAL response must identify incomplete work (SRS-009)")
        return self


class EnvironmentalToolRequest(ContractModel):
    tool_call_id: Text
    investigation_id: Text
    source_id: SourceId
    agent_type: AgentType
    requested_evidence: list[Text]
    target_time_window: TimeRange
    geographic_scope: JsonObject
    issued_at: Timestamp


class EnvironmentalToolResponse(ContractModel):
    tool_call_id: Text
    source_id: SourceId
    retrieval_status: RetrievalStatus
    retrieved_at: Timestamp
    source_reference: Text | None = None
    findings: list[EnvironmentalFinding]
    missing_evidence: list[Text]
    errors: list[JsonObject]
    duration_ms: NonNegativeInt

    @model_validator(mode="after")
    def consistency(self) -> Self:
        unique([f.finding_id for f in self.findings], "finding IDs")
        if any(f.source_id != self.source_id for f in self.findings):
            raise ValueError("finding source must match tool response")
        return self
