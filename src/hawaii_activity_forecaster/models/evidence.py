"""Environmental evidence structures, separate from evidence acceptance (03 §3)."""

from typing import Self

from pydantic import model_validator

from .common import ContractModel, Number, NumberRange, Text, Timestamp, chronological
from .enums import (
    AgentType, CoverageType, FindingType, MeasurementType, RetrievalStatus,
    SourceId, ValidationStatus,
)


class Measurement(ContractModel):
    measurement_type: MeasurementType
    value: Number | NumberRange | Text
    unit: Text | None = None
    measurement_time: Timestamp | None = None
    measurement_notes: Text | None = None
    measurement_convention: Text | None = None

    @model_validator(mode="after")
    def numeric_unit(self) -> Self:
        if not isinstance(self.value, str) and self.unit is None:
            raise ValueError("numeric measurements require a unit")
        return self


class AdvisoryReference(ContractModel):
    advisory_id: Text
    issuer: Text
    advisory_type: Text
    severity: Text | None = None
    affected_area: Text
    effective_from: Timestamp | None = None
    effective_until: Timestamp | None = None
    source_reference: Text

    @model_validator(mode="after")
    def period(self) -> Self:
        chronological(self.effective_from, self.effective_until, "advisory")
        return self


class EnvironmentalFinding(ContractModel):
    finding_id: Text
    investigation_id: Text
    agent_type: AgentType
    source_id: Text
    source_reference: Text | None = None
    finding_type: FindingType
    coverage_type: CoverageType
    coverage_id: Text | None = None
    coverage_description: Text
    beach_id: Text | None = None
    coverage_notes: Text | None = None
    retrieved_at: Timestamp
    issued_at: Timestamp | None = None
    valid_from: Timestamp | None = None
    valid_until: Timestamp | None = None
    observed_at: Timestamp | None = None
    temporal_notes: Text | None = None
    measurements: list[Measurement] | None = None
    advisories: list[AdvisoryReference] | None = None
    descriptive_findings: list[Text] | None = None
    missing_fields: list[Text] | None = None
    retrieval_status: RetrievalStatus
    validation_status: ValidationStatus
    limitations: list[Text] | None = None
    error_code: Text | None = None
    error_message: Text | None = None

    @model_validator(mode="after")
    def structure(self) -> Self:
        chronological(self.valid_from, self.valid_until, "finding validity")
        if self.coverage_type == CoverageType.BEACH and self.beach_id is None:
            raise ValueError("BEACH coverage requires beach_id")
        if self.retrieval_status in (RetrievalStatus.SUCCESS, RetrievalStatus.PARTIAL):
            if self.source_id not in SourceId:
                raise ValueError("successful/partial finding requires approved source (EF-001)")
            if self.source_reference is None:
                raise ValueError("successful/partial finding requires source_reference (EF-012)")
        if self.retrieval_status in (RetrievalStatus.ERROR, RetrievalStatus.UNAVAILABLE):
            if self.measurements or self.advisories or self.descriptive_findings:
                raise ValueError("retrieval failure cannot supply environmental evidence (EF-010)")
        # Missing temporal data remains representable for subsequent evidence rejection.
        # A successful retrieval never changes validation_status automatically.
        return self
