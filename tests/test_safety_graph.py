"""Policy/assessment graph component checks, never full acceptance results."""

import asyncio

import pytest

from hawaii_activity_forecaster.orchestration import run_synthetic_tool_graph
from authored_graph_samples import run_authored_graph
from specialist_samples import BEACH, catalog, normalized, request
from test_evidence_graph import wind_context
from tool_samples import action, inputs, operation


@pytest.mark.parametrize("scenario_id", ["SC-004", "SC-010"])
def test_authored_policy_assessments_are_derived_without_publishing_recommendations(scenario_id):
    events = []
    report, scenario = run_authored_graph(scenario_id, safety_evaluation=True, record_event=events.append)
    assert report.safety_report is not None
    assert "evaluate_safety" in report.visited_nodes
    assessments = {a.beach_id: a for a in report.state.assessments}
    if scenario_id == "SC-004":
        assert assessments["TEST_BEACH_A"].eligibility == "EXCLUDED"
        assert assessments["TEST_BEACH_A"].environmental_suitability == "UNFAVORABLE"
        assert assessments["TEST_BEACH_A"].evidence_quality == "SUFFICIENT"
        assert assessments["TEST_BEACH_B"].eligibility == "ELIGIBLE"
        assert assessments["TEST_BEACH_B"].environmental_suitability == "FAVORABLE"
        assert report.budgets.tool_calls == 6
        assert any(e.event_type == "CANDIDATE_EXCLUDED" for e in events)
        assert any(e.event_type == "CANDIDATE_ELIGIBLE" for e in events)
    else:
        assert all(a.eligibility == "NEEDS_INVESTIGATION" for a in assessments.values())
        assert all(a.evidence_quality == "INSUFFICIENT" for a in assessments.values())
        assert report.budgets.tool_calls == 8 and report.budgets.retries == 1 and report.budgets.fallbacks == 2
    assert report.state.status == "FAILED" and report.state.outcome == "ERROR"
    assert report.state.completion_reason == "RESULT_VALIDATION_NOT_IMPLEMENTED"
    assert report.budgets.model_calls == 0
    assert all(f"revision-{report.state.request_revision}" in a.assessment_version for a in assessments.values())
    assert any(e.event_type == "POLICY_EVALUATED" for e in events)
    assert any(e.event_type == "CANDIDATE_ASSESSED" for e in events)
    assert not any(e.event_type in {"RESULT_VALIDATED", "INVESTIGATION_COMPLETED", "INVESTIGATION_ABSTAINED"} for e in events)
    assert scenario.execution_readiness.outcome == "BLOCKED"


@pytest.mark.parametrize("failure_at", ["POLICY_EVALUATED", "CANDIDATE_ASSESSED", "CANDIDATE_ELIGIBLE"])
def test_policy_trace_failure_suppresses_assessments_and_closes_execution(failure_at):
    def recorder(event):
        if event.event_type == failure_at:
            raise OSError("synthetic trace failure")
    report, _ = run_authored_graph("SC-004", safety_evaluation=True, record_event=recorder)
    assert report.state.completion_reason == "TRACE_WRITE_FAILED"
    assert report.safety_report is None and report.state.assessments == []
    assert report.budgets.closed and report.budgets.tool_calls == 6


def test_next_cycle_invalidates_prior_assessment_and_reevaluates_actual_new_findings():
    events = []
    def plan(snapshot):
        if snapshot.iteration_count >= 2:
            return ()
        return (request(investigation_id=snapshot.investigation_id, issued_at=snapshot.updated_at,
                        request_id=f"weather-{snapshot.iteration_count}"),)
    def tools(parent):
        zone = "SYNTHETIC_ZONE" if parent.request_id == "weather-0" else "SECOND_ZONE"
        return (action(parent.request_id + "-call", zone=zone),)
    report = asyncio.run(run_synthetic_tool_graph(
        normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,), plan=plan, tool_plan=tools,
        driver_inputs=inputs(operation(), operation(op_id="second", zone="SECOND_ZONE")),
        evidence_policy=wind_context(), safety_evaluation=True, record_event=events.append,
    ))
    assessed = [e for e in events if e.event_type == "CANDIDATE_ASSESSED"]
    assert len(assessed) == 2
    assert assessed[0].details["assessment_id"] != assessed[1].details["assessment_id"]
    assert any(assessed[0].details["assessment_id"] in e.details.get("invalidated_assessment_ids", []) for e in events)
    assert len(report.state.assessments) == 1
    assert report.state.assessments[0].assessment_id == assessed[-1].details["assessment_id"]
    assert len(report.state.weather_findings) == 2 and report.budgets.tool_calls == 2


def test_policy_enabled_five_cycle_bound_preserves_unknowns_and_actual_zero_call_count():
    def plan(snapshot):
        return (request(investigation_id=snapshot.investigation_id, issued_at=snapshot.updated_at,
                        request_id=f"weather-{snapshot.iteration_count}"),)
    report = asyncio.run(run_synthetic_tool_graph(
        normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,), plan=plan, tool_plan=lambda parent: (),
        driver_inputs=inputs(), evidence_policy=wind_context(), safety_evaluation=True, record_event=lambda event: None,
    ))
    assert report.visited_nodes.count("evaluate_safety") == report.budgets.iterations == 5
    assert report.state.completion_reason == "ITERATION_LIMIT_REACHED"
    assert report.state.assessments[0].eligibility == "NEEDS_INVESTIGATION"
    assert report.state.assessments[0].evidence_quality == "INSUFFICIENT"
    assert report.budgets.tool_calls == report.budgets.model_calls == 0


def test_safety_flag_requires_explicit_policy_before_execution():
    with pytest.raises(ValueError):
        asyncio.run(run_synthetic_tool_graph(
            normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,), plan=lambda state: (),
            tool_plan=lambda parent: (), driver_inputs=inputs(), record_event=lambda event: None,
            safety_evaluation=True,
        ))
