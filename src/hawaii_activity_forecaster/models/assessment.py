"""Candidate assessment records and intrinsic consistency rules (03 §4)."""

from typing import Self

from pydantic import model_validator

from .common import ContractModel, Text, TimeRange, Timestamp
from .enums import (
    Activity, ConstraintStatus, Eligibility, EnvironmentalSuitability, EvidenceQuality,
    GeographicPreferenceMatch, NextAction, PolicyStatus, PreferenceAlignment,
)


class ConstraintResult(ContractModel):
    constraint_id: Text
    constraint_description: Text
    result: ConstraintStatus
    explanation: Text


class PreferenceResult(ContractModel):
    preference_id: Text
    preference_description: Text
    alignment: PreferenceAlignment
    explanation: Text


class PolicyResult(ContractModel):
    policy_id: Text
    result: PolicyStatus
    supporting_finding_ids: list[Text]
    explanation: Text


class CandidateAssessment(ContractModel):
    assessment_id: Text
    investigation_id: Text
    beach_id: Text
    activity: Activity
    target_time_window: TimeRange
    evaluated_at: Timestamp
    eligibility: Eligibility
    environmental_suitability: EnvironmentalSuitability
    evidence_quality: EvidenceQuality
    supporting_finding_ids: list[Text]
    conflicting_finding_ids: list[Text]
    rejected_finding_ids: list[Text]
    evidence_limitations: list[Text]
    assessment_basis: Text
    hard_constraint_results: list[ConstraintResult]
    preference_results: list[PreferenceResult]
    geographic_preference_match: GeographicPreferenceMatch
    policy_results: list[PolicyResult]
    disqualifying_policy_ids: list[Text]
    unresolved_policy_ids: list[Text]
    safety_limitations: list[Text]
    decision_reasons: list[Text]
    recommended_next_actions: list[NextAction]
    remaining_questions: list[Text]
    assessment_version: Text

    @model_validator(mode="after")
    def consistency(self) -> Self:
        if set(self.supporting_finding_ids) & set(self.rejected_finding_ids):
            raise ValueError("rejected findings cannot positively support an assessment (CA-010)")
        failed_constraint = any(c.result == ConstraintStatus.FAIL for c in self.hard_constraint_results)
        if (failed_constraint or self.disqualifying_policy_ids) and self.eligibility != Eligibility.EXCLUDED:
            raise ValueError("disqualifying policies or failed hard constraints require EXCLUDED (CA-005/006)")
        if not self.decision_reasons:
            raise ValueError("assessment requires decision reasons (CA-012)")
        if self.eligibility == Eligibility.ELIGIBLE:
            if self.evidence_quality != EvidenceQuality.SUFFICIENT:
                raise ValueError("ELIGIBLE requires SUFFICIENT evidence (CA-004)")
            if self.environmental_suitability not in (
                EnvironmentalSuitability.FAVORABLE, EnvironmentalSuitability.MIXED,
            ):
                raise ValueError("ELIGIBLE cannot be unfavorable or undetermined (CA-015/016)")
            if self.unresolved_policy_ids or any(
                c.result != ConstraintStatus.PASS for c in self.hard_constraint_results
            ):
                raise ValueError("ELIGIBLE requires resolved policies and passing hard constraints")
        # MIXED permission and actual policy classifications require the later safety evaluator.
        return self
