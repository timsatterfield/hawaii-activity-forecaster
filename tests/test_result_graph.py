"""Validated synthetic graph outcomes; not CLI or full scenario acceptance."""

import asyncio

import pytest

from hawaii_activity_forecaster.models import NormalizedRequest, RecommendationResult
from hawaii_activity_forecaster.orchestration import run_synthetic_tool_graph
from authored_graph_samples import run_authored_graph
from specialist_samples import BEACH, catalog, normalized, request
from test_evidence_graph import wind_context
from tool_samples import inputs


@pytest.mark.parametrize("scenario_id,outcome,status", [
    ("SC-004", "RECOMMENDATIONS", "COMPLETED"), ("SC-010", "NO_RECOMMENDATION", "ABSTAINED"),
])
def test_authored_component_outcomes_are_validated_before_terminal_commit(scenario_id, outcome, status):
    events = []
    report, scenario = run_authored_graph(scenario_id, safety_evaluation=True, result_generation=True, record_event=events.append)
    assert report.result is not None and report.result.outcome == outcome
    assert report.state.status == status and report.state.outcome == outcome
    assert report.result.result_id == report.state.result_id
    assert report.result.request_revision == report.state.request_revision
    assert report.budgets.closed and report.budgets.model_calls == 0
    assert report.comparison is not None
    assert report.visited_nodes[-4:] == ("compare_candidates", "construct_result", "validate_result", "finalize_investigation")
    if scenario_id == "SC-004":
        assert [r.beach_id for r in report.result.recommendations] == ["TEST_BEACH_B"]
        assert report.result.recommendations[0].rank is None
        assert report.budgets.tool_calls == 6
        # The excluded candidate's advisory is not misrepresented as applying to B.
        assert report.result.recommendations[0].advisory_references == []
        terminal = "INVESTIGATION_COMPLETED"
    else:
        assert not report.result.recommendations
        assert report.result.no_recommendation_reason == "INSUFFICIENT_EVIDENCE"
        assert report.result.explanation and report.result.unresolved_issues
        assert report.budgets.tool_calls == 8 and report.budgets.retries == 1 and report.budgets.fallbacks == 2
        terminal = "INVESTIGATION_ABSTAINED"
    kinds = [e.event_type for e in events]
    assert kinds.index("RESULT_VALIDATED") < kinds.index(terminal)
    assert next(e for e in events if e.event_type == terminal).details["result_id"] == report.result.result_id
    assert scenario.execution_readiness.outcome == "BLOCKED"


@pytest.mark.parametrize("scenario_id,fail_at", [
    ("SC-004", "RESULT_VALIDATED"), ("SC-004", "INVESTIGATION_COMPLETED"),
    ("SC-010", "INVESTIGATION_ABSTAINED"),
])
def test_result_or_terminal_trace_failure_suppresses_the_result(scenario_id, fail_at):
    def recorder(event):
        if event.event_type == fail_at:
            raise OSError("synthetic disk failure")
    report, _ = run_authored_graph(scenario_id, safety_evaluation=True, result_generation=True, record_event=recorder)
    assert report.result is None
    assert report.state.status == "FAILED" and report.state.outcome == "ERROR"
    assert report.state.completion_reason == "TRACE_WRITE_FAILED"
    assert not report.trace_writable and report.budgets.closed
    assert report.state.assessments == []


def test_invalid_proposed_result_becomes_a_valid_sanitized_error(monkeypatch):
    import hawaii_activity_forecaster.orchestration.skeleton as module
    original = module.build_result
    def corrupt(*args, **kwargs):
        proposal = original(*args, **kwargs).model_dump()
        proposal["recommendations"][0]["source_references"] = ["invented-source"]
        return RecommendationResult.model_validate(proposal)
    monkeypatch.setattr(module, "build_result", corrupt)
    events = []
    report, _ = run_authored_graph("SC-004", safety_evaluation=True, result_generation=True, record_event=events.append)
    assert report.result is not None and report.result.outcome == "ERROR"
    assert report.result.error_code == "RESULT_VALIDATION_FAILED"
    assert report.state.completion_reason == "RESULT_VALIDATION_FAILED"
    assert not report.result.recommendations and report.state.status == "FAILED"
    assert report.state.result_id == report.result.result_id
    validated = [e for e in events if e.event_type == "RESULT_VALIDATED"]
    assert len(validated) == 1 and validated[0].details["outcome"] == "ERROR"
    assert not any(e.event_type == "INVESTIGATION_COMPLETED" for e in events)


def test_application_exception_is_not_reported_as_environmental_abstention(monkeypatch):
    import hawaii_activity_forecaster.orchestration.skeleton as module
    def fail(context):
        raise RuntimeError("private execution details and credentials must not appear")
    monkeypatch.setattr(module, "compare_candidates", fail)
    report, _ = run_authored_graph("SC-004", safety_evaluation=True, result_generation=True)
    assert report.result.outcome == "ERROR" and report.result.error_code == "INVESTIGATION_EXECUTION_FAILED"
    assert report.state.completion_reason == "INVESTIGATION_EXECUTION_FAILED"
    assert "private execution" not in report.result.model_dump_json()
    assert report.state.status == "FAILED" and report.budgets.tool_calls == 6


def test_iteration_exhaustion_abstains_without_upgrading_unknown_candidates():
    def plan(snapshot):
        return (request(investigation_id=snapshot.investigation_id, issued_at=snapshot.updated_at,
                        request_id=f"request-{snapshot.iteration_count}"),)
    request_input = NormalizedRequest.model_validate(normalized().model_dump() | {"hard_constraints": []})
    report = asyncio.run(run_synthetic_tool_graph(
        request_input, catalog=catalog(), candidate_beach_ids=(BEACH,), plan=plan,
        tool_plan=lambda parent: (), driver_inputs=inputs(), evidence_policy=wind_context(),
        safety_evaluation=True, result_generation=True, record_event=lambda event: None,
    ))
    assert report.result.outcome == "NO_RECOMMENDATION"
    assert report.result.no_recommendation_reason == "INVESTIGATION_LIMIT_REACHED"
    assert report.state.status == "ABSTAINED"
    assert report.budgets.iterations == 5 and report.budgets.tool_calls == 0
    assert report.state.assessments[0].eligibility == "NEEDS_INVESTIGATION"


def test_clarification_has_no_invented_activity_result_and_result_mode_requires_safety():
    ambiguous = NormalizedRequest.model_validate(normalized().model_dump() | {"activity": None, "clarification_needed": True})
    report = asyncio.run(run_synthetic_tool_graph(
        ambiguous, catalog=catalog(), candidate_beach_ids=(BEACH,), plan=lambda state: (),
        tool_plan=lambda parent: (), driver_inputs=inputs(), evidence_policy=wind_context(),
        safety_evaluation=True, result_generation=True, record_event=lambda event: None,
    ))
    assert report.state.status == "AWAITING_CLARIFICATION" and report.result is None
    assert report.state.result_id is None and report.budgets.tool_calls == 0
    with pytest.raises(ValueError):
        asyncio.run(run_synthetic_tool_graph(
            normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,), plan=lambda state: (),
            tool_plan=lambda parent: (), driver_inputs=inputs(), evidence_policy=wind_context(),
            result_generation=True, record_event=lambda event: None,
        ))


def test_unrecovered_specialist_execution_fault_is_an_error_not_an_environmental_abstention(monkeypatch):
    from hawaii_activity_forecaster.harness.synthetic import SyntheticDriver
    from tool_samples import action
    def fail(*args, **kwargs):
        raise RuntimeError("private synthetic driver failure")
    monkeypatch.setattr(SyntheticDriver, "deliver", fail)
    def plan(snapshot):
        if snapshot.iteration_count:
            return ()
        return (request(investigation_id=snapshot.investigation_id, issued_at=snapshot.updated_at),)
    report = asyncio.run(run_synthetic_tool_graph(
        normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,), plan=plan,
        tool_plan=lambda parent: (action(),), driver_inputs=inputs(), evidence_policy=wind_context(),
        safety_evaluation=True, result_generation=True, record_event=lambda event: None,
    ))
    assert report.result.outcome == "ERROR" and report.result.error_code == "INVESTIGATION_EXECUTION_FAILED"
    assert not report.result.recommendations
    assert report.state.status == "FAILED" and report.budgets.tool_calls == 1
    assert "private synthetic driver failure" not in report.result.model_dump_json()
