"""Deterministic HM/EL/CA policy acceptance checks with fictional evidence."""

from dataclasses import replace
from datetime import timedelta

import pytest

from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.models import BeachCatalog, InvestigationState
from hawaii_activity_forecaster.validation import SafetyEvaluationError, evaluate_safety
from evidence_samples import change_finding
from safety_samples import context, evidence, fact, mixed_context
from specialist_samples import BEACH, WINDOW


def assess(snapshot, catalog, policy, bindings):
    validated = evidence(snapshot, catalog, policy, bindings)
    return evaluate_safety(validated, catalog=catalog, policy=policy, bindings=bindings)


def policy_result(assessment, policy_id):
    return next(result for result in assessment.policy_results if result.policy_id == policy_id)


@pytest.mark.parametrize("activity", ["SWIMMING", "SNORKELING", "SUP"])
def test_explicitly_supported_conditions_can_qualify_without_optional_visibility(activity):
    snapshot, catalog, policy, bindings = context(activity)
    before = snapshot.model_dump_json()
    report = assess(snapshot, catalog, policy, bindings)
    assessment = report.assessments[0]
    assert (assessment.eligibility, assessment.environmental_suitability, assessment.evidence_quality) == ("ELIGIBLE", "FAVORABLE", "SUFFICIENT")
    assert not assessment.disqualifying_policy_ids and not assessment.unresolved_policy_ids
    assert assessment.recommended_next_actions == ["READY_FOR_COMPARISON"]
    assert any("UNDERWATER_VISIBILITY" in limitation for limitation in assessment.evidence_limitations)
    assert report.state.status == snapshot.status and report.state.outcome is None
    assert snapshot.model_dump_json() == before
    assert report.state.assessments == list(report.assessments)
    assert report.request_revision == snapshot.request_revision


@pytest.mark.parametrize("name,policy_id,activity", [
    ("WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT", "HM-WATER-001", "SWIMMING"),
    ("DISQUALIFYING_SURF_PRESENT", "HM-SURF-004", "SNORKELING"),
    ("DANGEROUS_CURRENT_PRESENT", "HM-CURRENT-004", "SWIMMING"),
    ("DISQUALIFYING_WEATHER_PRESENT", "HM-WEATHER-003", "SWIMMING"),
    ("DANGEROUS_OFFSHORE_WIND_PRESENT", "HM-WIND-002", "SUP"),
    ("DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT", "HM-BEACH-004", "SWIMMING"),
])
def test_verified_disqualifying_failure_overrides_positive_support(name, policy_id, activity):
    snapshot, catalog, policy, bindings = context(activity)
    result = assess(snapshot, catalog, fact(policy, name, value=True), bindings).assessments[0]
    assert policy_id in result.disqualifying_policy_ids
    assert result.eligibility == "EXCLUDED" and result.environmental_suitability == "UNFAVORABLE"
    assert result.evidence_quality == "SUFFICIENT"  # Known adverse conditions are still evidence.
    assert policy_result(result, policy_id).result == "FAIL"


@pytest.mark.parametrize("name,policy_id", [
    ("DISQUALIFYING_SURF_PRESENT", "HM-SURF-004"), ("DANGEROUS_CURRENT_PRESENT", "HM-CURRENT-004"),
    ("DISQUALIFYING_WEATHER_PRESENT", "HM-WEATHER-003"),
    ("DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT", "HM-BEACH-004"),
    ("MATERIAL_SAFETY_CONFLICT_PRESENT", "ES-009"),
])
def test_missing_hazard_fact_is_unknown_and_blocks_eligibility(name, policy_id):
    snapshot, catalog, policy, bindings = context()
    assessment = assess(snapshot, catalog, fact(policy, name, remove=True), bindings).assessments[0]
    assert policy_result(assessment, policy_id).result == "UNKNOWN"
    assert assessment.eligibility == "NEEDS_INVESTIGATION"
    assert assessment.evidence_quality == "LIMITED"


@pytest.mark.parametrize("value", [None, False])
def test_absent_or_false_activity_support_never_becomes_favorable(value):
    snapshot, catalog, policy, bindings = context()
    policy = fact(policy, "ACTIVITY_SUPPORTING_CONDITIONS_PRESENT", remove=value is None, value=False)
    assessment = assess(snapshot, catalog, policy, bindings).assessments[0]
    assert assessment.environmental_suitability == "UNDETERMINED"
    assert assessment.eligibility == "NEEDS_INVESTIGATION" and assessment.evidence_quality == "SUFFICIENT"


def test_no_received_data_is_insufficient_despite_authored_premises_and_high_counters():
    snapshot, catalog, policy, bindings = context()
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {
        "weather_findings": [], "ocean_findings": [], "iteration_count": 5, "tool_call_count": 12,
    })
    assessment = assess(snapshot, catalog, policy, bindings).assessments[0]
    assert assessment.eligibility == "NEEDS_INVESTIGATION"
    assert assessment.evidence_quality == "INSUFFICIENT"
    assert assessment.environmental_suitability == "UNDETERMINED"
    assert not assessment.supporting_finding_ids


def test_unaccepted_or_wrong_category_support_cannot_establish_disqualifying_or_favorable_facts():
    snapshot, catalog, policy, bindings = context()
    snapshot = change_finding(snapshot, "run-marine", missing_fields=["surf_applicability"])
    policy = fact(policy, "DISQUALIFYING_SURF_PRESENT", value=True)
    assessment = assess(snapshot, catalog, policy, bindings).assessments[0]
    assert policy_result(assessment, "HM-SURF-004").result == "UNKNOWN"
    assert assessment.eligibility == "NEEDS_INVESTIGATION"
    wrong_category = fact(policy, "WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT", value=True,
                          finding_refs=[dict(source_fixture_id="wind", finding_id="template-wind")])
    assessment = assess(snapshot, catalog, wrong_category, bindings).assessments[0]
    assert policy_result(assessment, "HM-WATER-001").result == "UNKNOWN"


def advisory(**changes):
    return dict(advisory_id="test-advisory", issuer="Synthetic agency", advisory_type="Synthetic water-contact avoidance advisory",
                affected_area=BEACH, source_reference="https://example.invalid/synthetic-advisory",
                effective_from=WINDOW["start"], effective_until=WINDOW["end"]) | changes


def test_actual_official_advisory_overrides_false_hazard_premise_and_material_conflict():
    snapshot, catalog, policy, bindings = context()
    snapshot = change_finding(snapshot, "run-water", advisories=[advisory()])
    policy = fact(policy, "MATERIAL_SAFETY_CONFLICT_PRESENT", value=True)
    result = assess(snapshot, catalog, policy, bindings).assessments[0]
    assert policy_result(result, "HM-WATER-001").result == "FAIL"
    assert result.eligibility == "EXCLUDED" and result.environmental_suitability == "UNFAVORABLE"
    assert result.evidence_quality == "LIMITED"
    assert result.conflicting_finding_ids


@pytest.mark.parametrize("changes", [
    {"advisory_type": "Unclassified informational notice"},
    {"affected_area": "Unmapped regional advisory area"}, {"effective_until": None},
])
def test_ambiguous_official_notice_is_not_a_blanket_exclusion_or_a_pass(changes):
    snapshot, catalog, policy, bindings = context()
    snapshot = change_finding(snapshot, "run-water", advisories=[advisory(**changes)])
    result = assess(snapshot, catalog, policy, bindings).assessments[0]
    assert policy_result(result, "HM-WATER-001").result == "UNKNOWN"
    assert result.eligibility == "NEEDS_INVESTIGATION"


def test_expired_or_other_named_beach_advisory_does_not_automatically_exclude_this_candidate():
    snapshot, catalog, policy, bindings = context()
    for notice in (advisory(effective_until=WINDOW["start"], effective_from=WINDOW["start"] - timedelta(hours=1)),
                   advisory(affected_area="TEST_BEACH_B")):
        changed = change_finding(snapshot, "run-water", advisories=[notice])
        assert assess(changed, catalog, policy, bindings).assessments[0].eligibility == "ELIGIBLE"


def test_unknown_hard_constraints_are_not_trusted_even_with_caller_supplied_pass():
    snapshot, catalog, policy, bindings = context()
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {
        "hard_constraints": [{"constraint_id": "c", "result": "PASS", "description": "opaque input"}],
    })
    assessment = assess(snapshot, catalog, policy, bindings).assessments[0]
    assert assessment.hard_constraint_results[0].result == "UNKNOWN"
    assert assessment.eligibility == "NEEDS_INVESTIGATION"
    assert assessment.environmental_suitability == "FAVORABLE" and assessment.evidence_quality == "SUFFICIENT"
    assert assessment.recommended_next_actions == ["REQUEST_USER_CLARIFICATION"]


def test_soft_preferences_and_exact_geographic_match_cannot_override_exclusion():
    snapshot, catalog, policy, bindings = context()
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {
        "preferred_area": "Kihei", "soft_preferences": [{"alignment": "MATCH", "description": "prefer this beach"}],
    })
    assessment = assess(snapshot, catalog, fact(policy, "DANGEROUS_CURRENT_PRESENT", value=True), bindings).assessments[0]
    assert assessment.eligibility == "EXCLUDED" and assessment.geographic_preference_match == "PREFERRED_AREA"
    assert assessment.preference_results[0].alignment == "UNKNOWN"


def test_unsupported_activity_or_unverified_catalog_is_not_eligible():
    snapshot, catalog, policy, bindings = context()
    for changes in ({"supported_activities": ["SUP"]}, {"catalog_status": "DISABLED"}):
        data = catalog.model_dump()
        data[0] |= changes
        assessment = assess(snapshot, BeachCatalog.model_validate(data), policy, bindings).assessments[0]
        assert assessment.eligibility == "UNSUPPORTED" and assessment.evidence_quality == "INSUFFICIENT"


def test_stale_or_forged_evidence_report_is_rejected_without_mutating_state():
    snapshot, catalog, policy, bindings = context()
    validated = evidence(snapshot, catalog, policy, bindings)
    before = validated.state.model_dump_json()
    forged = replace(validated, candidates=())
    with pytest.raises(SafetyEvaluationError):
        evaluate_safety(forged, catalog=catalog, policy=policy, bindings=bindings)
    assert validated.state.model_dump_json() == before
    with pytest.raises(ValueError):
        evaluate_safety(validated, catalog=catalog, policy=policy, bindings=())


def test_assessment_ids_are_idempotent_and_request_revision_bound_and_caller_mutations_detach():
    snapshot, catalog, policy, bindings = context()
    first = assess(snapshot, catalog, policy, bindings)
    assert first == assess(snapshot, catalog, policy, tuple(reversed(bindings)))
    assert first == evaluate_safety(evidence(first.state, catalog, policy, bindings), catalog=catalog, policy=policy, bindings=bindings)
    revised = InvestigationState.model_validate(snapshot.model_dump() | {"request_revision": 2})
    second = assess(revised, catalog, policy, bindings)
    assert first.assessments[0].assessment_id != second.assessments[0].assessment_id
    assert "revision-2" in second.assessments[0].assessment_version
    second_before = second.state.model_dump_json()
    first.state.assessments[0].decision_reasons.append("caller mutation")
    assert snapshot.assessments == []
    assert "caller mutation" not in first.assessments[0].decision_reasons
    assert second.state.model_dump_json() == second_before




def test_reviewed_mixed_requires_all_five_conditions_and_disclosure():
    assessment = assess(*mixed_context()).assessments[0]
    assert (assessment.eligibility, assessment.environmental_suitability, assessment.evidence_quality) == ("ELIGIBLE", "MIXED", "SUFFICIENT")
    assert "Synthetic poor visibility must be disclosed" in assessment.safety_limitations
    snapshot, catalog, policy, bindings = mixed_context()
    excluded = assess(snapshot, catalog, fact(policy, "DANGEROUS_CURRENT_PRESENT", value=True), bindings).assessments[0]
    assert excluded.eligibility == "EXCLUDED" and excluded.environmental_suitability == "UNFAVORABLE"
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {"hard_constraints": [{"opaque": "constraint"}]})
    assert assess(snapshot, catalog, policy, bindings).assessments[0].eligibility == "NEEDS_INVESTIGATION"


def test_unpermitted_mixed_is_not_excluded_or_promoted_to_eligible():
    assessment = assess(*mixed_context(permission=False)).assessments[0]
    assert assessment.eligibility == "NEEDS_INVESTIGATION" and assessment.environmental_suitability == "MIXED"
    assert assessment.evidence_quality == "SUFFICIENT"
    assert "HM-VIS-003" in assessment.unresolved_policy_ids


def test_non_sup_offshore_wind_is_policy_dependent_not_a_blanket_exclusion():
    snapshot, catalog, policy, bindings = context()
    data = policy.model_dump()
    data["premises"].append(dict(premise_id="offshore", beach_id=BEACH, activity="SWIMMING", time_window=WINDOW,
                                 fact_type="DANGEROUS_OFFSHORE_WIND_PRESENT", value=True,
                                 finding_refs=[dict(source_fixture_id="wind", finding_id="template-wind")],
                                 catalog_field_refs=[], rationale="Explicit hypothetical wind question for swimming"))
    assessment = assess(snapshot, catalog, PolicyConfiguration.model_validate(data), bindings).assessments[0]
    assert policy_result(assessment, "HM-WIND-002").result == "UNKNOWN"
    assert assessment.eligibility == "NEEDS_INVESTIGATION" and not assessment.disqualifying_policy_ids


def test_verified_exclusion_wins_even_when_other_mandatory_evidence_is_unavailable():
    snapshot, catalog, policy, bindings = context()
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {"ocean_findings": [f for f in snapshot.ocean_findings if f.finding_id != "run-water"]})
    assessment = assess(snapshot, catalog, fact(policy, "DISQUALIFYING_SURF_PRESENT", value=True), bindings).assessments[0]
    assert assessment.eligibility == "EXCLUDED" and assessment.environmental_suitability == "UNFAVORABLE"
    assert assessment.evidence_quality == "INSUFFICIENT"


def test_unknown_catalog_attributes_cannot_clear_persistent_hazard_policy():
    snapshot, catalog, policy, bindings = context()
    policy = fact(policy, "DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT",
                  catalog_field_refs=[dict(beach_id=BEACH, field="reef_presence")])
    assessment = assess(snapshot, catalog, policy, bindings).assessments[0]
    assert policy_result(assessment, "HM-BEACH-004").result == "UNKNOWN"
    assert assessment.eligibility == "NEEDS_INVESTIGATION"


def test_terminal_snapshot_cannot_be_reassessed_or_have_prior_results_reopened():
    snapshot, catalog, policy, bindings = context()
    validated = evidence(snapshot, catalog, policy, bindings)
    terminal = InvestigationState.model_validate(validated.state.model_dump() | {
        "status": "FAILED", "outcome": "ERROR", "result_id": "final-result", "completion_reason": "Synthetic end",
    })
    with pytest.raises(ValueError):
        evaluate_safety(replace(validated, state=terminal), catalog=catalog, policy=policy, bindings=bindings)
