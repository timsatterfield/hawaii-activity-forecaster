"""CLI presentation acceptance criteria using fictional validated results only."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from hawaii_activity_forecaster.models import InvestigationState, RecommendationResult
from hawaii_activity_forecaster.orchestration import SkeletonReport
from hawaii_activity_forecaster.orchestration.budgets import BudgetSnapshot
from hawaii_activity_forecaster.presentation import PresentationError, render_report
from hawaii_activity_forecaster.recommendations import (
    ResultValidationSnapshot, build_result, validate_result,
)
from hawaii_activity_forecaster.validation import evaluate_safety, validate_evidence
from authored_graph_samples import run_authored_graph
from result_samples import GENERATED, result_context


@pytest.fixture
def advisory():
    report, scenario = run_authored_graph("SC-004", safety_evaluation=True, result_generation=True)
    application = scenario.application
    return report, application.catalog, application.policy_configuration


def committed(context):
    """A synthetic terminal report built from a separately validated active basis."""
    result = validate_result(build_result(context, generated_at=GENERATED), context, now=GENERATED)
    state = InvestigationState.model_validate(context.state.model_dump() | {
        "status": "COMPLETED" if result.outcome == "RECOMMENDATIONS" else "ABSTAINED",
        "outcome": result.outcome, "result_id": result.result_id,
        "completion_reason": "Validated " + result.outcome, "updated_at": GENERATED + timedelta(seconds=1),
    })
    budgets = BudgetSnapshot(iterations=state.iteration_count, tool_calls=state.tool_call_count, model_calls=0,
                             reserved_tool_calls=0, reserved_model_calls=0, retries=state.retry_count,
                             fallbacks=0, active_specialists=0, closed=True)
    return SkeletonReport(state, budgets, (), True, context.bindings, context.evidence, context.safety,
                          result=result, result_validation=ResultValidationSnapshot(
                              context.state, "ASSESSMENT_COMPLETE", None, context.request_step))


def reassess(context, data, *, request_step=1):
    evidence = validate_evidence(InvestigationState.model_validate(data), catalog=context.catalog, policy=context.policy,
                                 bindings=context.bindings, reference_time=context.evidence.reference_time,
                                 request_step=request_step)
    safety = evaluate_safety(evidence, catalog=context.catalog, policy=context.policy,
                             bindings=context.bindings, request_step=request_step)
    state = InvestigationState.model_validate(safety.state.model_dump() | {
        "status": "EVALUATING", "updated_at": context.state.updated_at,
    })
    return replace(context, state=state, evidence=evidence, safety=safety, request_step=request_step)


def test_recommendations_show_activity_time_reasons_actual_evidence_and_attribution(advisory):
    report, catalog, policy = advisory
    output = render_report(report, catalog=catalog, policy=policy)
    assert "SYNTHETIC TEST OUTPUT: fictional locations and conditions" in output
    assert "not for real activity planning" in output
    assert "Activity: Snorkeling" in output
    assert "2026-11-17 08:00 HST (UTC-10:00)" in output
    assert "2026-11-17 11:00 HST (UTC-10:00)" in output
    assert "- Fictional Test Beach B (SYNTHETIC)" in output
    recommended, _, excluded = output.partition("Not recommended (excluded):")
    assert "Fictional Test Beach A (SYNTHETIC)" not in recommended  # Never offered as a recommendation...
    assert "Fictional Test Beach A (SYNTHETIC): an applicable official water-contact" in excluded  # ...but disclosed.
    recommendation = report.result.recommendations[0]
    assert recommendation.recommendation_reason in output
    assert recommendation.environmental_summary in output
    assert "National Weather Service weather" in output
    assert "Hawaii DOH Clean Water Branch" in output
    assert "Wind speed: 8 kn" in output
    assert "Surf height: 1–2 ft (wave-face convention)" in output
    assert "Swell height: 3 ft" in output
    assert "Measurement time: 2026-11-17 08:00" in output
    assert "Retrieved: 2026-11-16 09:00" in output
    assert "Issued: 2026-11-16 08:30" in output
    assert "(regional)" in output and "not a direct beach observation" in output
    assert "Missing optional evidence: underwater visibility information." in output
    assert "https://example.invalid/haf/sc-004/marine_forecast" in output
    assert "Hawaii Activity Forecaster synthetic fixture authors" in output
    assert "Accessed: 2026-11-16; catalog verified: 2026-11-16" in output
    # Original source text/URLs may contain fixture IDs; internal runtime IDs
    # and policy identifiers are not added as presentation fields.
    for value in (report.result.result_id, report.state.investigation_id,
                  recommendation.assessment_id, recommendation.recommendation_id,
                  *recommendation.supporting_finding_ids,
                  *(p.policy_id for a in report.state.assessments for p in a.policy_results)):
        assert value not in output


def test_abstention_explains_evidence_limits_without_claiming_unfavorable_conditions():
    report, scenario = run_authored_graph("SC-010", safety_evaluation=True, result_generation=True)
    app = scenario.application
    output = render_report(report, catalog=app.catalog, policy=app.policy_configuration)
    assert "No recommendation\n" in output and report.result.explanation in output
    assert "Affected locations:" in output and "Fictional Test Beach D (SYNTHETIC)" in output
    assert "Unresolved questions:" in output
    assert "Missing mandatory evidence: surf and wave information." in output
    assert "Missing mandatory evidence: current and persistent-hazard information." in output
    assert "Next steps:" in output
    assert "Technical error" not in output and "Recommendations (" not in output
    assert "TEST_BEACH_A:" not in output
    assert report.budgets.tool_calls == 8
    assert scenario.execution_readiness.outcome == "BLOCKED"


def test_rendering_is_read_only_and_does_not_record_events_or_consume_work():
    events = []
    report, scenario = run_authored_graph("SC-004", safety_evaluation=True, result_generation=True, record_event=events.append)
    before = deepcopy(report)
    recorded = deepcopy(events)
    app = scenario.application
    first = render_report(report, catalog=app.catalog, policy=app.policy_configuration)
    assert render_report(report, catalog=app.catalog, policy=app.policy_configuration) == first
    assert report == before and events == recorded
    assert report.state.status == "COMPLETED" and report.budgets.closed
    assert report.budgets.tool_calls == 6 and report.budgets.model_calls == 0


def test_mixed_disclosure_and_outside_area_explanation_are_preserved():
    context = result_context(("TEST_BEACH_A", "TEST_BEACH_B"), mixed=("TEST_BEACH_A",), preferred_area="Kihei")
    report = committed(context)
    output = render_report(report, catalog=context.catalog, policy=context.policy)
    assert "Suitability: Mixed; evidence: sufficient" in output
    assert "Synthetic poor visibility must be disclosed" in output
    outside = next(r for r in report.result.recommendations if r.beach_id == "TEST_BEACH_B")
    assert outside.recommendation_reason in output and "Outside the preferred area" in output


def test_original_source_metadata_advisory_periods_notes_and_safe_terminal_text():
    context = result_context()
    data = context.evidence.state.model_dump()
    marine = next(f for f in data["ocean_findings"] if f["source_id"] == "NWS_MARINE")
    window = context.state.target_time_window
    marine["coverage_description"] = "Fictional region\n\x1b[31mreported area\x1b[0m"
    marine["measurements"][0].update(measurement_time=window.start,
                                      measurement_notes="Synthetic wave-face reading; not Hawaiian-back height")
    notice = dict(advisory_id="fictional-notice", issuer="Fictional bulletin publisher",
                  advisory_type="Fictional informational notice", severity="Informational (synthetic)",
                  affected_area="Fictional reporting region", effective_from=window.start, effective_until=window.end,
                  source_reference="https://example.invalid/informational-notice")
    marine["advisories"] = [notice, notice | {
        "advisory_id": "expired-notice", "advisory_type": "Expired fictional notice",
        "effective_from": window.start - timedelta(days=2), "effective_until": window.start - timedelta(days=1),
    }]
    context = reassess(context, data)
    report = committed(context)
    output = render_report(report, catalog=context.catalog, policy=context.policy)
    assert "Reported advisories:" in output
    assert "Fictional informational notice — Fictional bulletin publisher" in output
    assert "Source area: Fictional reporting region" in output
    assert "Effective: 2026-11-19 09:00 HST (UTC-10:00) to 2026-11-19 11:00 HST (UTC-10:00)" in output
    assert "Reported severity: Informational (synthetic)" in output
    assert "Reference: https://example.invalid/informational-notice" in output
    assert "Measurement notes: Synthetic wave-face reading; not Hawaiian-back height" in output
    assert "Expired fictional notice" not in output
    assert "\x1b" not in output and "Coverage: Fictional region [31mreported area[0m (regional)" in output


def test_explicit_request_step_is_retained_for_read_only_validation():
    context = result_context()
    context = replace(context, bindings=tuple(replace(binding, request_step=2) for binding in context.bindings))
    context = reassess(context, context.evidence.state.model_dump(), request_step=2)
    report = committed(context)
    assert report.result_validation.request_step == 2
    assert "Recommendations (" in render_report(report, catalog=context.catalog, policy=context.policy)


def test_ties_and_three_location_cap_do_not_become_numeric_ranks():
    context = result_context(("TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_C", "TEST_BEACH_D"))
    report = committed(context)
    output = render_report(report, catalog=context.catalog, policy=context.policy)
    assert output.count("\n- Fictional TEST_BEACH_") == 3
    assert "Fictional TEST_BEACH_D (SYNTHETIC)" not in output
    assert "no finer rank" in output and "three-location limit" in output
    assert "1. Fictional" not in output and "rank: 1" not in output.lower()


@pytest.mark.parametrize("field,value", [
    ("source_references", ["invented-source"]),
    ("supporting_finding_ids", ["missing-finding"]),
    ("environmental_summary", "Guaranteed safe at a real Maui beach"),
    ("limitations", []),
    ("rank", 1),
])
def test_mutated_but_structurally_valid_results_never_render(advisory, field, value):
    report, catalog, policy = advisory
    data = report.result.model_dump()
    data["recommendations"][0][field] = value
    report = replace(report, result=RecommendationResult.model_validate(data))
    with pytest.raises(PresentationError, match="No validated result"):
        render_report(report, catalog=catalog, policy=policy)


@pytest.mark.parametrize("change", [
    "missing-result", "missing-basis", "missing-evidence", "missing-safety", "trace-failed",
    "unclosed", "active", "reserved", "counter", "terminal-id", "revision", "basis-terminal", "request-step",
])
def test_incomplete_uncommitted_or_stale_reports_fail_closed(advisory, change):
    report, catalog, policy = advisory
    if change == "missing-result":
        report = replace(report, result=None)
    elif change == "missing-basis":
        report = replace(report, result_validation=None)
    elif change == "missing-evidence":
        report = replace(report, evidence_report=None)
    elif change == "missing-safety":
        report = replace(report, safety_report=None)
    elif change == "trace-failed":
        report = replace(report, trace_writable=False)
    elif change in {"unclosed", "active", "reserved", "counter"}:
        kwargs = {"unclosed": {"closed": False}, "active": {"active_specialists": 1},
                  "reserved": {"reserved_tool_calls": 1}, "counter": {"tool_calls": 7}}[change]
        report = replace(report, budgets=replace(report.budgets, **kwargs))
    elif change in {"terminal-id", "revision"}:
        kwargs = {"result_id": "wrong-result"} if change == "terminal-id" else {"request_revision": 2}
        report = replace(report, state=InvestigationState.model_validate(report.state.model_dump() | kwargs))
    elif change == "basis-terminal":
        report = replace(report, result_validation=replace(report.result_validation, state=report.state))
    else:
        report = replace(report, result_validation=replace(report.result_validation, request_step=2))
    with pytest.raises(PresentationError):
        render_report(report, catalog=catalog, policy=policy)


def test_mutable_nested_proposals_and_stale_grounding_are_rechecked(advisory):
    report, catalog, policy = advisory
    report.result.recommendations[0].source_references.append("caller-owned mutation")
    with pytest.raises(PresentationError):
        render_report(report, catalog=catalog, policy=policy)
    context = result_context(mixed=("TEST_BEACH_A",))
    report = committed(context)
    changed = context.policy.model_validate(context.policy.model_dump() | {"mixed_permissions": []})
    with pytest.raises(PresentationError):
        render_report(report, catalog=context.catalog, policy=changed)


def test_sanitized_error_is_distinct_and_needs_no_environmental_claims(monkeypatch):
    import hawaii_activity_forecaster.orchestration.skeleton as graph
    def fail(context):
        raise RuntimeError("SECRET synthetic private execution detail")
    monkeypatch.setattr(graph, "compare_candidates", fail)
    report, _ = run_authored_graph("SC-004", safety_evaluation=True, result_generation=True)
    output = render_report(report)
    assert "Technical error\nAn application execution error prevented a validated result." in output
    assert "SYNTHETIC TEST OUTPUT" in output and "Activity: Snorkeling" in output
    assert "SECRET" not in output and "No recommendation\n" not in output
    assert "Suitability:" not in output and "Source" not in output
    assert report.budgets.tool_calls == 6 and report.state.status == "FAILED"


@pytest.mark.parametrize("field,value", [("error_summary", "SECRET private exception"),
                                        ("error_code", "RESULT_VALIDATION_FAILED")])
def test_error_payload_must_still_match_its_trusted_failure_basis(monkeypatch, field, value):
    import hawaii_activity_forecaster.orchestration.skeleton as graph
    def fail(context):
        raise RuntimeError("SECRET runtime error")
    monkeypatch.setattr(graph, "compare_candidates", fail)
    report, _ = run_authored_graph("SC-004", safety_evaluation=True, result_generation=True)
    corrupted = RecommendationResult.model_validate(report.result.model_dump() | {field: value})
    with pytest.raises(PresentationError):
        render_report(replace(report, result=corrupted))


@pytest.mark.parametrize("event_type", ["RESULT_VALIDATED", "INVESTIGATION_COMPLETED"])
def test_trace_failure_cannot_fall_back_to_a_proposed_result(event_type):
    def fail(event):
        if event.event_type == event_type:
            raise OSError("private trace error")
    report, scenario = run_authored_graph("SC-004", safety_evaluation=True, result_generation=True, record_event=fail)
    app = scenario.application
    assert report.result is None and report.result_validation is None
    with pytest.raises(PresentationError):
        render_report(report, catalog=app.catalog, policy=app.policy_configuration)
