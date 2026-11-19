"""PR/RR validation, comparison and abstention checks on synthetic contexts."""

from dataclasses import replace
from datetime import timedelta

import pytest

from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.models import InvestigationState, RecommendationResult
from hawaii_activity_forecaster.recommendations import (
    ResultValidationError, build_error_result, build_result, compare_candidates, validate_error_result, validate_result,
)
from hawaii_activity_forecaster.validation import evaluate_safety, validate_evidence
from result_samples import GENERATED, result_context


def recalculate(context, *, state=None, policy=None):
    state = state or context.evidence.state
    policy = policy or context.policy
    evidence = validate_evidence(state, catalog=context.catalog, policy=policy, bindings=context.bindings,
                                 reference_time=context.evidence.reference_time)
    safety = evaluate_safety(evidence, catalog=context.catalog, policy=policy, bindings=context.bindings)
    current = InvestigationState.model_validate(safety.state.model_dump() | {"status": "EVALUATING", "updated_at": context.state.updated_at})
    return replace(context, state=current, evidence=evidence, safety=safety, policy=policy)


def test_grounded_result_contains_only_current_eligible_support_and_provenance():
    context = result_context()
    before = context.state.model_dump_json()
    result = build_result(context, generated_at=GENERATED)
    assert result.outcome == "RECOMMENDATIONS" and len(result.recommendations) == 1
    recommendation = result.recommendations[0]
    assert recommendation.beach_id == "TEST_BEACH_A" and recommendation.rank is None
    assert recommendation.assessment_id == context.safety.assessments[0].assessment_id
    assert recommendation.recommended_time_window == context.state.target_time_window
    assert recommendation.environmental_suitability == "FAVORABLE" and recommendation.evidence_quality == "SUFFICIENT"
    assert "NWS_MARINE" in recommendation.source_references and "catalog-TEST_BEACH_A" in recommendation.source_references
    assert any("not a direct beach observation" in item for item in recommendation.limitations)
    assert recommendation.supporting_finding_ids
    assert context.state.model_dump_json() == before
    assert validate_result(result, context, now=GENERATED) == result
    assert build_result(context, generated_at=GENERATED) == result


def test_equal_candidates_are_unranked_repeatable_and_limited_to_three_without_padding():
    beaches = ("TEST_BEACH_E", "TEST_BEACH_B", "TEST_BEACH_D", "TEST_BEACH_A", "TEST_BEACH_C")
    context = result_context(beaches)
    comparison = compare_candidates(context)
    assert len(comparison.groups) == 1 and len(comparison.groups[0]) == 5
    result = build_result(context, generated_at=GENERATED)
    assert [r.beach_id for r in result.recommendations] == ["TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_C"]
    assert all(r.rank is None for r in result.recommendations)
    assert len(comparison.omitted_assessment_ids) == 2
    assert any("no finer rank" in limitation for limitation in result.general_limitations)
    assert any("three-location limit" in limitation for limitation in result.general_limitations)
    data = result.model_dump()
    data["recommendations"].append(data["recommendations"][0] | {"recommendation_id": "fourth", "beach_id": "TEST_BEACH_D"})
    with pytest.raises(ResultValidationError):
        validate_result(data, context, now=GENERATED)


def test_comparison_uses_suitability_and_area_without_weighting_their_tradeoff():
    context = result_context(("TEST_BEACH_A", "TEST_BEACH_B"), mixed=("TEST_BEACH_A",), preferred_area="Kihei")
    comparison = compare_candidates(context)
    assert len(comparison.groups) == 1  # Preferred MIXED vs outside FAVORABLE.
    result = build_result(context, generated_at=GENERATED)
    outside = next(r for r in result.recommendations if r.beach_id == "TEST_BEACH_B")
    assert "Outside the preferred area" in outside.recommendation_reason
    mixed = next(r for r in result.recommendations if r.beach_id == "TEST_BEACH_A")
    assert mixed.environmental_suitability == "MIXED"
    assert "Synthetic poor visibility must be disclosed" in mixed.warnings
    assert all(r.rank is None for r in result.recommendations)
    same_area = result_context(("TEST_BEACH_A", "TEST_BEACH_B"), mixed=("TEST_BEACH_B",))
    groups = compare_candidates(same_area).groups
    assert len(groups) == 2
    assert groups[0] == (next(a.assessment_id for a in same_area.safety.assessments if a.beach_id == "TEST_BEACH_A"),)
    area_only = result_context(("TEST_BEACH_A", "TEST_BEACH_B"), preferred_area="Wailea")
    assert compare_candidates(area_only).groups[0] == (next(a.assessment_id for a in area_only.safety.assessments if a.beach_id == "TEST_BEACH_B"),)


def test_excluded_candidates_cannot_fill_the_recommendation_count():
    context = result_context(("TEST_BEACH_A", "TEST_BEACH_B"))
    data = context.policy.model_dump()
    for premise in data["premises"]:
        if premise["beach_id"] == "TEST_BEACH_A" and premise["fact_type"] == "DANGEROUS_CURRENT_PRESENT":
            premise["value"] = True
    context = recalculate(context, policy=PolicyConfiguration.model_validate(data))
    result = build_result(context, generated_at=GENERATED)
    assert [r.beach_id for r in result.recommendations] == ["TEST_BEACH_B"]
    assert len(compare_candidates(context).selected_assessment_ids) == 1
    data = result.model_dump()
    excluded = next(a for a in context.safety.assessments if a.beach_id == "TEST_BEACH_A")
    data["recommendations"][0].update(beach_id=excluded.beach_id, assessment_id=excluded.assessment_id)
    with pytest.raises(ResultValidationError):
        validate_result(data, context, now=GENERATED)


@pytest.mark.parametrize("tamper", [
    lambda data: data.update(request_revision=2),
    lambda data: data.update(investigation_id="old-investigation"),
    lambda data: data.update(summary="These real beaches are guaranteed safe"),
    lambda data: data.update(general_warnings=[]),
    lambda data: data.update(error_code="unrelated-error"),
    lambda data: data["recommendations"][0].update(assessment_id="stale-assessment"),
    lambda data: data["recommendations"][0].update(beach_id="TEST_BEACH_B"),
    lambda data: data["recommendations"][0].update(rank=1),
    lambda data: data["recommendations"][0]["recommended_time_window"].update(
        end=data["recommendations"][0]["recommended_time_window"]["end"] + timedelta(hours=1)),
    lambda data: data["recommendations"][0].update(source_references=["unverified-source"]),
    lambda data: data["recommendations"][0].update(supporting_finding_ids=["not-received"]),
    lambda data: data["recommendations"][0].update(limitations=[]),
    lambda data: data["recommendations"][0].update(environmental_summary="Regional forecasts are direct beach observations"),
])
def test_result_validator_rejects_stale_references_unbacked_prose_and_missing_disclosures(tamper):
    context = result_context()
    result = build_result(context, generated_at=GENERATED)
    data = result.model_dump()
    tamper(data)
    with pytest.raises(ResultValidationError):
        validate_result(data, context, now=GENERATED)


def test_mixed_permission_and_disclosure_are_independently_rechecked():
    context = result_context(mixed=("TEST_BEACH_A",))
    result = build_result(context, generated_at=GENERATED)
    data = result.model_dump()
    data["recommendations"][0]["warnings"] = []
    with pytest.raises(ResultValidationError):
        validate_result(data, context, now=GENERATED)
    changed = PolicyConfiguration.model_validate(context.policy.model_dump() | {"mixed_permissions": []})
    with pytest.raises(ResultValidationError):
        validate_result(result, replace(context, policy=changed), now=GENERATED)


def test_no_recommendation_explains_hazards_constraints_and_insufficient_evidence():
    base = result_context()
    data = base.policy.model_dump()
    for premise in data["premises"]:
        if premise["fact_type"] == "DANGEROUS_CURRENT_PRESENT":
            premise["value"] = True
    hazardous = recalculate(base, policy=PolicyConfiguration.model_validate(data))
    result = build_result(hazardous, generated_at=GENERATED)
    assert result.outcome == "NO_RECOMMENDATION" and result.no_recommendation_reason == "APPLICABLE_HAZARDS"
    assert not result.recommendations and result.explanation
    constrained = recalculate(base, state=InvestigationState.model_validate(base.evidence.state.model_dump() | {"hard_constraints": [{"opaque": "request"}]}))
    assert build_result(constrained, generated_at=GENERATED).no_recommendation_reason == "UNRESOLVED_CONSTRAINTS"
    missing = recalculate(base, state=InvestigationState.model_validate(base.evidence.state.model_dump() | {"weather_findings": [], "ocean_findings": []}))
    result = build_result(missing, generated_at=GENERATED)
    assert result.no_recommendation_reason == "INSUFFICIENT_EVIDENCE" and result.unresolved_issues
    assert result.outcome != "ERROR"


def test_limit_does_not_upgrade_candidates_and_cannot_be_claimed_before_actual_limit():
    base = result_context()
    missing = recalculate(base, state=InvestigationState.model_validate(base.evidence.state.model_dump() | {
        "weather_findings": [], "ocean_findings": [], "iteration_count": 5,
    }))
    result = build_result(missing, generated_at=GENERATED, stop_reason="ITERATION_LIMIT_REACHED")
    assert result.no_recommendation_reason == "INVESTIGATION_LIMIT_REACHED"
    assert validate_result(result, missing, now=GENERATED, stop_reason="ITERATION_LIMIT_REACHED") == result
    with pytest.raises(ResultValidationError):
        build_result(base, generated_at=GENERATED, stop_reason="ITERATION_LIMIT_REACHED")


@pytest.mark.parametrize("change", ["revision", "window", "constraint", "terminal", "assessment", "finding"])
def test_current_state_must_match_revalidated_assessment_basis(change):
    context = result_context()
    data = context.state.model_dump()
    if change == "revision":
        data["request_revision"] = 2
    elif change == "window":
        data["target_time_window"]["end"] += timedelta(hours=1)
    elif change == "constraint":
        data["hard_constraints"] = [{"result": "PASS"}]
    elif change == "terminal":
        data.update(status="COMPLETED", outcome="RECOMMENDATIONS", result_id="old", completion_reason="done")
    elif change == "assessment":
        data["assessments"][0]["assessment_id"] = "edited"
    else:
        data["weather_findings"][0]["descriptive_findings"] = ["Changed stable evidence payload"]
    with pytest.raises(ResultValidationError):
        compare_candidates(replace(context, state=InvestigationState.model_validate(data)))


def test_error_results_are_sanitized_and_require_trusted_failure_context():
    context = result_context()
    result = build_error_result(context.state, generated_at=GENERATED, error_code="INVESTIGATION_EXECUTION_FAILED")
    assert result.outcome == "ERROR" and not result.recommendations
    assert validate_error_result(result, context.state, now=GENERATED, error_code="INVESTIGATION_EXECUTION_FAILED") == result
    with pytest.raises(ResultValidationError):
        validate_result(result, context, now=GENERATED)
    with pytest.raises(ResultValidationError):
        build_error_result(context.state, generated_at=GENERATED, error_code="SOURCE_UNAVAILABLE")
    with pytest.raises(ResultValidationError):
        validate_error_result(result, context.state, now=GENERATED, error_code="RESULT_VALIDATION_FAILED")
    with pytest.raises(ResultValidationError):
        validate_error_result(result.model_dump() | {"error_summary": "private stack trace"}, context.state,
                              now=GENERATED, error_code="INVESTIGATION_EXECUTION_FAILED")


def test_future_or_naive_generation_time_and_mutation_cannot_bypass_validation():
    context = result_context()
    with pytest.raises(ResultValidationError):
        build_result(context, generated_at=GENERATED.replace(tzinfo=None))
    result = build_result(context, generated_at=GENERATED)
    with pytest.raises(ResultValidationError):
        validate_result(result, context, now=GENERATED - timedelta(seconds=1))
    result.recommendations[0].source_references.append("caller mutation")
    with pytest.raises(ResultValidationError):
        validate_result(result, context, now=GENERATED)
    assert "caller mutation" not in build_result(context, generated_at=GENERATED).recommendations[0].source_references


def test_conflict_and_unsupported_abstention_reasons_describe_actual_basis():
    base = result_context()
    data = base.policy.model_dump()
    for premise in data["premises"]:
        if premise["fact_type"] == "MATERIAL_SAFETY_CONFLICT_PRESENT":
            premise["value"] = True
    conflicting = recalculate(base, policy=PolicyConfiguration.model_validate(data))
    assert build_result(conflicting, generated_at=GENERATED).no_recommendation_reason == "CONFLICTING_EVIDENCE"
    missing_positive = base.policy.model_dump()
    missing_positive["premises"] = [p for p in missing_positive["premises"] if p["fact_type"] != "ACTIVITY_SUPPORTING_CONDITIONS_PRESENT"]
    undecided = recalculate(base, policy=PolicyConfiguration.model_validate(missing_positive))
    assert build_result(undecided, generated_at=GENERATED).no_recommendation_reason == "NO_ELIGIBLE_CANDIDATES"


def test_budget_exhaustion_can_use_already_eligible_evidence_but_cannot_exceed_limits():
    base = result_context()
    bounded = recalculate(base, state=InvestigationState.model_validate(base.evidence.state.model_dump() | {
        "iteration_count": 5, "tool_call_count": 12,
    }))
    assert build_result(bounded, generated_at=GENERATED, stop_reason="ITERATION_LIMIT_REACHED").outcome == "RECOMMENDATIONS"
    for update in ({"iteration_count": 6}, {"tool_call_count": 13}, {"max_tool_calls": 100}):
        changed = recalculate(base, state=InvestigationState.model_validate(base.evidence.state.model_dump() | update))
        with pytest.raises(ResultValidationError):
            build_result(changed, generated_at=GENERATED)
