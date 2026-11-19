"""Independent geographic constraint checks; catalog matches are not safety verdicts."""

import pytest
from datetime import timedelta

from hawaii_activity_forecaster.models import BeachCatalog, InvestigationState
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.recommendations import ResultContext, build_result
from hawaii_activity_forecaster.validation import evaluate_safety, validate_evidence
from hawaii_activity_forecaster.interpretation import select_candidates, validate_request
from interpretation_samples import REFERENCE
from result_samples import GENERATED, result_context
from safety_samples import context, fact
from specialist_samples import NOW
from test_candidate_selection import sup


@pytest.mark.parametrize("scope,value,outcome", [("REGION", "SOUTH_MAUI", "PASS"), ("REGION", "WEST_MAUI", "FAIL"),
                                              ("LOCALITY", "Kihei", "PASS"), ("LOCALITY", "Wailea", "FAIL"),
                                              ("BEACH", "TEST_BEACH_A", "PASS"), ("BEACH", "TEST_BEACH_B", "FAIL")])
def test_recognized_geography_is_evaluated_against_catalog_not_model_verdict(scope, value, outcome):
    state, catalog, policy, bindings = context("SNORKELING")
    descriptor = {"kind": "LOCATION_RESTRICTION", "scope": scope, "value": value}
    state = InvestigationState.model_validate(state.model_dump() | {"hard_constraints": [descriptor]})
    evidence = validate_evidence(state, catalog=catalog, policy=policy, bindings=bindings, reference_time=NOW)
    assessment = evaluate_safety(evidence, catalog=catalog, policy=policy, bindings=bindings).assessments[0]
    assert assessment.hard_constraint_results[0].result == outcome
    assert assessment.eligibility == ("ELIGIBLE" if outcome == "PASS" else "EXCLUDED")
    assert "Hard constraints require approved normalization" not in assessment.safety_limitations


@pytest.mark.parametrize("descriptor", [
    {"result": "PASS"}, {"kind": "CALM_WATER"}, {"kind": "UNKNOWN"},
    {"kind": "LOCATION_RESTRICTION", "scope": "LOCALITY", "value": "Atlantis"},
    {"kind": "LOCATION_RESTRICTION", "scope": "LOCALITY", "value": "Kihei", "result": "PASS"},
    {"kind": "LOCATION_RESTRICTION", "scope": [], "value": "Kihei"},
    {"kind": "UNINTERPRETED", "text": "must be calm"},
])
def test_legacy_unknown_or_malformed_constraints_never_acquire_pass_authority(descriptor):
    state, catalog, policy, bindings = context("SNORKELING")
    state = InvestigationState.model_validate(state.model_dump() | {"hard_constraints": [descriptor]})
    evidence = validate_evidence(state, catalog=catalog, policy=policy, bindings=bindings, reference_time=NOW)
    assessment = evaluate_safety(evidence, catalog=catalog, policy=policy, bindings=bindings).assessments[0]
    assert assessment.hard_constraint_results[0].result == "UNKNOWN" and assessment.eligibility != "ELIGIBLE"


def test_unverified_geography_stays_unknown_and_a_match_cannot_override_hazard():
    state, catalog, policy, bindings = context("SNORKELING")
    state = InvestigationState.model_validate(state.model_dump() | {"hard_constraints": [
        {"kind": "LOCATION_RESTRICTION", "scope": "LOCALITY", "value": "Kihei"},
    ]})
    data = catalog.model_dump()
    next(b for b in data if b["beach_id"] == "TEST_BEACH_A")["catalog_status"] = "NEEDS_REVIEW"
    unverified = BeachCatalog.model_validate(data)
    evidence = validate_evidence(state, catalog=unverified, policy=policy, bindings=bindings, reference_time=NOW)
    assessment = evaluate_safety(evidence, catalog=unverified, policy=policy, bindings=bindings).assessments[0]
    assert assessment.hard_constraint_results[0].result == "UNKNOWN" and assessment.eligibility != "ELIGIBLE"
    hazardous = fact(policy, "DANGEROUS_CURRENT_PRESENT", value=True)
    evidence = validate_evidence(state, catalog=catalog, policy=hazardous, bindings=bindings, reference_time=NOW)
    assessment = evaluate_safety(evidence, catalog=catalog, policy=hazardous, bindings=bindings).assessments[0]
    assert assessment.hard_constraint_results[0].result == "PASS" and assessment.eligibility == "EXCLUDED"


def test_actual_unsupported_assessments_are_not_substituted_with_selector_audit():
    ctx, data = sup()
    receipt = validate_request(data, ctx)
    audit = select_candidates(receipt, ctx)
    state = InvestigationState(
        **receipt.request.model_dump(), investigation_id=receipt.investigation_id, session_id=receipt.session_id,
        schema_version="0.1", created_at=REFERENCE, updated_at=REFERENCE, status="INVESTIGATING", request_revision=1,
        candidate_beach_ids=list(audit.assessment_candidate_ids), assessments=[], investigated_beach_ids=[],
        remaining_candidate_ids=list(audit.investigation_candidate_ids), weather_findings=[], ocean_findings=[],
        pending_evidence_requests=[], unresolved_evidence_issues=[], iteration_count=0, max_iterations=5,
        tool_call_count=0, max_tool_calls=12, retry_count=0, max_retries=1, remaining_actions=[], active_errors=[],
        recovery_actions=[], fallback_attempted=False,
    )
    _, _, policy, _ = context("SUP")  # independent component profile; SC-004 is snorkeling-only
    evidence = validate_evidence(state, catalog=ctx.catalog, policy=policy, bindings=(), reference_time=REFERENCE)
    safety = evaluate_safety(evidence, catalog=ctx.catalog, policy=policy, bindings=())
    actual = {a.beach_id: a for a in safety.assessments}
    assert actual["TEST_BEACH_A"].eligibility == actual["TEST_BEACH_E"].eligibility == "UNSUPPORTED"
    assert actual["TEST_BEACH_B"].eligibility == "NEEDS_INVESTIGATION"  # support alone establishes no eligibility
    assert "INVESTIGATE_ALTERNATIVE_SOURCE" in actual["TEST_BEACH_B"].recommended_next_actions
    assert all(a.hard_constraint_results[0].result == "PASS" for a in actual.values())
    assert safety.state.tool_call_count == 0


def test_recognized_calm_preference_is_unknown_and_disclosed_even_with_favorable_support():
    base = result_context()
    state = InvestigationState.model_validate(base.evidence.state.model_dump() | {"soft_preferences": [{"kind": "CALM_WATER"}]})
    evidence = validate_evidence(state, catalog=base.catalog, policy=base.policy, bindings=base.bindings,
                                 reference_time=base.evidence.reference_time)
    safety = evaluate_safety(evidence, catalog=base.catalog, policy=base.policy, bindings=base.bindings)
    assessment = safety.assessments[0]
    assert assessment.eligibility == "ELIGIBLE" and assessment.environmental_suitability == "FAVORABLE"
    assert assessment.preference_results[0].alignment == "UNKNOWN"
    assert "does not establish" in assessment.preference_results[0].explanation
    current = InvestigationState.model_validate(safety.state.model_dump() | {"status": "EVALUATING", "updated_at": base.state.updated_at})
    result = build_result(ResultContext(current, evidence, safety, base.catalog, base.policy, base.bindings), generated_at=GENERATED)
    assert any("Calm-water preference alignment is UNKNOWN" in note for note in result.recommendations[0].warnings)


def test_partial_afternoon_evidence_is_not_extended_to_the_default_window():
    # Explicit component evidence remains on its original validity interval.
    state, catalog, policy, bindings = context("SNORKELING")
    start = state.target_time_window.start.replace(hour=12)
    target = {"start": start, "end": start + timedelta(hours=4)}
    data = state.model_dump() | {"target_time_window": target}
    for domain in ("weather_findings", "ocean_findings"):
        for finding in data[domain]:
            finding.update(valid_from=start, valid_until=start + timedelta(hours=2))
    expanded = InvestigationState.model_validate(data)
    policy = PolicyConfiguration.model_validate(policy.model_dump() | {
        "premises": [p.model_dump() | {"time_window": target} for p in policy.premises],
    })
    evidence = validate_evidence(expanded, catalog=catalog, policy=policy, bindings=bindings, reference_time=NOW)
    safety = evaluate_safety(evidence, catalog=catalog, policy=policy, bindings=bindings)
    assert safety.assessments[0].eligibility != "ELIGIBLE"
    assert any("TARGET_WINDOW_NOT_COVERED" in d.reasons for d in evidence.decisions)
    assert safety.state.weather_findings[0].valid_until == start + timedelta(hours=2)
