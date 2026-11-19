"""Observed synthetic evidence through LangGraph; full scenarios remain BLOCKED."""

import asyncio

import pytest

from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.orchestration import run_synthetic_tool_graph
from evidence_samples import sample
from authored_graph_samples import run_authored_graph
from specialist_samples import BEACH, catalog, normalized, request
from tool_samples import action, inputs


def wind_context():
    _, _, policy, _ = sample()
    data = policy.model_dump()
    data["evidence_rules"] = [r | {"source_fixture_id": "NWS_WEATHER-SUCCESS", "finding_id": "WEATHER-finding"}
                              for r in data["evidence_rules"] if r["category"] == "WIND_CONDITIONS"]
    return PolicyConfiguration.model_validate(data)


def wind_plan(snapshot):
    if snapshot.iteration_count:
        return ()
    return (request(investigation_id=snapshot.investigation_id, issued_at=snapshot.updated_at),)


def run_wind(recorder, policy=None, plan=wind_plan):
    return asyncio.run(run_synthetic_tool_graph(
        normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,), plan=plan,
        tool_plan=lambda parent: (action(),), driver_inputs=inputs(), record_event=recorder,
        evidence_policy=policy if policy is not None else wind_context(),
    ))


def test_graph_evaluates_actual_received_evidence_and_reports_missing_mandatory_categories():
    events = []
    result = run_wind(events.append)
    assert result.evidence_report is not None
    assert result.state.weather_findings[0].validation_status == "ACCEPTED"
    assert not result.evidence_report.candidates[0].mandatory_categories_covered
    assert result.budgets.tool_calls == result.state.tool_call_count == 1
    assert result.budgets.model_calls == 0
    assert "validate_evidence" in result.visited_nodes
    assert result.state.status == "FAILED" and result.state.completion_reason == "VALIDATORS_NOT_IMPLEMENTED"
    assert any(event.event_type == "EVIDENCE_VALIDATED" for event in events)
    assert not any(event.event_type in {"POLICY_EVALUATED", "RESULT_VALIDATED"} for event in events)
    assert not result.state.assessments


def test_evidence_event_failure_never_commits_validation_status_or_starts_more_calls():
    def fail(event):
        if event.event_type == "EVIDENCE_VALIDATED":
            raise OSError("synthetic write failure")
    report = run_wind(fail)
    assert report.state.completion_reason == "TRACE_WRITE_FAILED"
    assert report.evidence_report is None
    assert report.budgets.closed and report.budgets.tool_calls == 1
    assert report.state.weather_findings[0].validation_status == "PENDING"


def test_missing_activity_profile_is_blocked_before_retrieval():
    data = wind_context().model_dump()
    data["evidence_profiles"] = [p for p in data["evidence_profiles"] if p["activity"] != "SWIMMING"]
    report = run_wind(lambda event: None, PolicyConfiguration.model_validate(data))
    assert report.state.status == "FAILED"
    assert report.budgets.tool_calls == 0 and not report.tool_bindings
    assert report.evidence_report is None


def test_five_evidence_cycles_terminate_before_sixth_without_framework_recursion_failure():
    def plan(snapshot):
        return (request(investigation_id=snapshot.investigation_id, issued_at=snapshot.updated_at,
                        request_id=f"request-{snapshot.iteration_count}"),)
    # No planned sources: every iteration honestly remains missing evidence.
    report = asyncio.run(run_synthetic_tool_graph(
        normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,), plan=plan,
        tool_plan=lambda parent: (), driver_inputs=inputs(), evidence_policy=wind_context(),
        record_event=lambda event: None,
    ))
    assert report.budgets.iterations == 5 and report.budgets.tool_calls == 0
    assert report.state.completion_reason == "ITERATION_LIMIT_REACHED"
    assert report.visited_nodes.count("validate_evidence") == 5


@pytest.mark.parametrize("scenario_id, expected_calls, categories_covered", [("SC-004", 6, True), ("SC-010", 8, False)])
def test_authored_category_coverage_is_independent_of_eligibility_and_outage_counts(scenario_id, expected_calls, categories_covered):
    report, scenario = run_authored_graph(scenario_id)
    assert report.evidence_report is not None
    assert all(c.mandatory_categories_covered == categories_covered for c in report.evidence_report.candidates)
    assert report.budgets.tool_calls == expected_calls and report.budgets.iterations == 1
    if categories_covered:
        assert any(i.resolved for i in report.state.unresolved_evidence_issues if i.issue_id.startswith("gap-"))
        assert any(overlap is True for d in report.evidence_report.decisions for _, overlap in d.advisory_overlaps)
    else:
        assert report.budgets.retries == 1 and report.budgets.fallbacks == 2
        assert any(not i.resolved for i in report.state.unresolved_evidence_issues)
    assert report.state.assessments == []
    assert report.state.status == "FAILED" and report.state.outcome == "ERROR"
    assert scenario.execution_readiness.outcome == "BLOCKED"
