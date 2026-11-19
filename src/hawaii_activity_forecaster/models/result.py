"""Structured outcomes and local result invariants (03 §6)."""

from typing import Literal, Self

from pydantic import StrictBool, model_validator

from .common import ContractModel, PositiveInt, Text, TimeRange, Timestamp, unique
from .enums import Activity, EnvironmentalSuitability, EvidenceQuality, NoRecommendationReason, Outcome


class Recommendation(ContractModel):
    recommendation_id: Text
    beach_id: Text
    assessment_id: Text
    rank: PositiveInt | None = None
    display_name: Text
    environmental_suitability: Literal[EnvironmentalSuitability.FAVORABLE, EnvironmentalSuitability.MIXED]
    evidence_quality: Literal[EvidenceQuality.SUFFICIENT]
    recommended_time_window: TimeRange
    supporting_finding_ids: list[Text]
    advisory_references: list[Text]
    recommendation_reason: Text
    environmental_summary: Text
    preference_alignment: list[Text]
    warnings: list[Text]
    limitations: list[Text]
    source_references: list[Text]


class RecommendationResult(ContractModel):
    result_id: Text
    investigation_id: Text
    request_revision: PositiveInt
    schema_version: Text
    generated_at: Timestamp
    activity: Activity
    target_time_window: TimeRange
    outcome: Outcome
    summary: Text
    recommendations: list[Recommendation]
    general_warnings: list[Text]
    general_limitations: list[Text]
    next_step_suggestions: list[Text] | None = None
    no_recommendation_reason: NoRecommendationReason | None = None
    explanation: Text | None = None
    affected_beach_ids: list[Text] | None = None
    unresolved_issues: list[Text] | None = None
    suggested_alternatives: list[Text] | None = None
    error_code: Text | None = None
    error_summary: Text | None = None
    recoverable: StrictBool | None = None

    @model_validator(mode="after")
    def outcome_structure(self) -> Self:
        if self.outcome == Outcome.RECOMMENDATIONS:
            if not 1 <= len(self.recommendations) <= 3:
                raise ValueError("RECOMMENDATIONS requires one to three entries (RR-003)")
        elif self.recommendations:
            raise ValueError("NO_RECOMMENDATION and ERROR require no recommendations (RR-004)")
        if self.outcome == Outcome.NO_RECOMMENDATION:
            if self.no_recommendation_reason is None or self.explanation is None:
                raise ValueError("NO_RECOMMENDATION requires reason and explanation (RR-015)")
        if self.outcome == Outcome.ERROR:
            if self.error_code is None or self.error_summary is None or self.recoverable is None:
                raise ValueError("ERROR requires error_code, error_summary and recoverable")
        unique([r.recommendation_id for r in self.recommendations], "recommendation IDs")
        unique([r.beach_id for r in self.recommendations], "recommended beaches")
        # Current assessment eligibility, grounding and MIXED permission are checked
        # against external records by recommendations.validate_result.
        return self
