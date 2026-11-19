"""Dispatch subset enforcement, audited empty selections, and afternoon coverage."""

import asyncio
from dataclasses import replace
from datetime import datetime

import pytest

from hawaii_activity_forecaster.harness.contracts import DriverInputs
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.models import SpecialistInvestigationRequest
from hawaii_activity_forecaster.orchestration import SessionManager
from hawaii_activity_forecaster.presentation import render_report
from hawaii_activity_forecaster.tools import ToolAction
from hawaii_activity_forecaster.tools.synthetic import SyntheticToolDispatcher, ToolPlanError
from hawaii_activity_forecaster.orchestration import BudgetManager
from hawaii_activity_forecaster.harness.synthetic import SyntheticDriver
from evidence_samples import sample as evidence_sample
from interpretation_samples import proposal, window
from raw_graph_samples import REFERENCE, TEXT, afternoon_components, follow, initial_proposal, scenario, start


def sup_request(inputs, candidates=("TEST_BEACH_B",)):
    state = inputs.state
    if state.iteration_count:
        return ()
    return (SpecialistInvestigationRequest(
        request_id="SUP-weather", investigation_id=state.investigation_id, request_revision=state.request_revision,
        schema_version=state.schema_version, agent_type="WEATHER", candidate_beach_ids=list(candidates),
        target_time_window=state.target_time_window, requested_evidence=[dict(
            requirement_id="wind", evidence_type="WIND_CONDITIONS", priority="REQUIRED")],
        known_evidence_gaps=[], issued_at=state.updated_at, attempt_number=1,
    ),)


def sup_components():
    sample = scenario()
    driver = DriverInputs.model_validate(dict(
        script=dict(harness_contract_version="1.0.0", requests=[dict(
            request_step=1, user_request="SUP synthetic component", reference_time=REFERENCE)], operations=[dict(
                operation_id="SUP-wind", request_step=1, agent_type="WEATHER", source_id="NWS_WEATHER",
                candidate_beach_ids=["TEST_BEACH_B"], requested_evidence=["WIND_CONDITIONS"], target_time_window=window(),
                geographic_scope={"zone": "SYNTHETIC_SC-004_REGION"}, attempts=[dict(
                    attempt=1, behavior="SUCCESS", simulated_duration_ms=1, response_fixture_id="sc-004-wind")])]),
        source_responses={"sc-004-wind": sample.driver.source_responses["sc-004-wind"]}, malformed_responses={},
    ))
    policy = PolicyConfiguration.model_validate(evidence_sample()[2].model_dump() | {
        "premises": [], "evidence_rules": [dict(
            rule_id="SUP-wind", category="WIND_CONDITIONS", source_fixture_id="sc-004-wind",
            finding_id="SC-004_WEATHER_FORECAST", temporal_rule="COVERS_TARGET_WINDOW", beach_ids=["TEST_BEACH_B"])],
    })
    return driver, policy


@pytest.mark.parametrize("bad_scope", [None, "specialist", "tool"])
def test_sup_assesses_a_b_e_and_authorizes_retrieval_only_for_b(bad_scope):
    text = "SUP tomorrow morning only South Maui."
    data = initial_proposal(text, activity="SUP", verb="SUP")
    driver, policy = sup_components()
    events = []
    def choose(inputs):
        assert inputs.investigation_candidate_ids == inputs.planning_order == ("TEST_BEACH_B",)
        return sup_request(inputs, ("TEST_BEACH_A",) if bad_scope == "specialist" else ("TEST_BEACH_B",))
    def tools(parent):
        return (ToolAction(action_id="wind", source_id="NWS_WEATHER",
                           candidate_beach_ids=["TEST_BEACH_A" if bad_scope == "tool" else "TEST_BEACH_B"],
                           requested_evidence=["WIND_CONDITIONS"], geographic_scope={"zone": "SYNTHETIC_SC-004_REGION"}),)
    report = asyncio.run(start(SessionManager(), text=text, data=data, driver=driver, policy=policy,
                               planner=choose, tool_planner=tools, events=events))
    assert report.state.candidate_beach_ids == ["TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_E"]
    assert report.selection.investigation_candidate_ids == ("TEST_BEACH_B",)
    if bad_scope:
        assert report.state.status == "FAILED" and report.result.outcome == "ERROR"
        assert report.budgets.tool_calls == 0 and not report.tool_bindings
        assert not any(e.event_type in {"AGENT_STARTED", "TOOL_CALLED"} for e in events)
        rendered = render_report(report, catalog=scenario().application.catalog, policy=policy)
        assert "Technical error" in rendered and "Assumed daypart window" in rendered
        with pytest.raises(ValueError, match="No validated result"):
            render_report(replace(report, request_receipt=None), catalog=scenario().application.catalog, policy=policy)
    else:
        assert report.state.status == "ABSTAINED", report.state.completion_reason
        assert report.budgets.iterations == report.budgets.tool_calls == 1
        assert {a.beach_id: a.eligibility for a in report.state.assessments} == {
            "TEST_BEACH_A": "UNSUPPORTED", "TEST_BEACH_B": "NEEDS_INVESTIGATION", "TEST_BEACH_E": "UNSUPPORTED",
        }
        assert report.result.no_recommendation_reason == "INSUFFICIENT_EVIDENCE"
        assert report.result_validation.stop_reason == "NO_FURTHER_ACTION"
        assert report.state.pending_evidence_requests[0].candidate_beach_ids == ["TEST_BEACH_B"]
        assert len(report.tool_bindings) == 1
        called = [e for e in events if e.event_type == "TOOL_CALLED"]
        assert len(called) == 1 and called[0].details["candidate_beach_ids"] == ["TEST_BEACH_B"]
        assert "No recommendation" in render_report(report, catalog=scenario().application.catalog, policy=policy)


def test_forged_empty_selection_is_rejected_before_result_publication(monkeypatch):
    import hawaii_activity_forecaster.orchestration.skeleton as graph
    original = graph.select_candidates
    def empty(receipt, context):
        audit = original(receipt, context)
        return replace(audit, investigation_candidate_ids=(), planning_order=())
    monkeypatch.setattr(graph, "select_candidates", empty)
    events = []
    report = asyncio.run(start(SessionManager(), events=events))
    assert report.state.status == "FAILED" and report.result.outcome == "ERROR"
    assert report.selection is None and report.budgets.tool_calls == 0
    assert not any(e.event_type == "INVESTIGATION_ABSTAINED" for e in events)
    assert not any(e.details.get("contract") == "candidate_selection" and e.details.get("valid") for e in events)


def test_tool_boundary_independently_rejects_an_unsupported_parent():
    from specialist_samples import request
    driver, _ = sup_components()
    budgets = BudgetManager()
    dispatcher = SyntheticToolDispatcher(SyntheticDriver(driver), budgets, investigation_id="investigation-1",
        request_revision=1, reference_time=REFERENCE, emit=lambda *args, **kwargs: None,
        investigation_candidate_ids=("TEST_BEACH_B",))
    with pytest.raises(ToolPlanError, match="selected investigation scope"):
        dispatcher.register(request(), ())  # A is in the assessment pool, but not the dispatch pool.
    assert budgets.snapshot().tool_calls == budgets.snapshot().reserved_tool_calls == 0


def test_raw_normalization_does_not_spend_one_of_the_five_coordinator_iterations():
    text = "SUP tomorrow morning only South Maui."
    driver, policy = sup_components()
    def choose(inputs):
        state = inputs.state
        return (SpecialistInvestigationRequest(
            request_id=f"cycle-{state.iteration_count}", investigation_id=state.investigation_id,
            request_revision=state.request_revision, schema_version=state.schema_version, agent_type="WEATHER",
            candidate_beach_ids=["TEST_BEACH_B"], target_time_window=state.target_time_window,
            requested_evidence=[dict(requirement_id="wind", evidence_type="WIND_CONDITIONS", priority="REQUIRED")],
            known_evidence_gaps=[], issued_at=state.updated_at, attempt_number=1,
        ),)
    report = asyncio.run(start(SessionManager(), text=text, data=initial_proposal(text, activity="SUP", verb="SUP"),
                               driver=driver, policy=policy, planner=choose, tool_planner=lambda parent: ()))
    assert report.state.status == "ABSTAINED", report.state.completion_reason
    assert report.result.no_recommendation_reason == "INVESTIGATION_LIMIT_REACHED"
    assert report.budgets.iterations == 5 and report.budgets.tool_calls == report.budgets.model_calls == 0
    assert report.visited_nodes.count("normalize_request") == 1
    assert report.visited_nodes.count("authorize_dispatch") == 5


@pytest.mark.parametrize("evidence_end,expected", [("16:00", "RECOMMENDATIONS"), ("14:00", "NO_RECOMMENDATION")])
def test_afternoon_result_requires_entire_default_window_and_discloses_precision(evidence_end, expected):
    driver, policy = afternoon_components(evidence_end)
    text = TEXT.replace("morning", "afternoon")
    clock = datetime.fromisoformat("2026-11-17T00:30:00+00:00")
    report = asyncio.run(start(SessionManager(), text=text, data=initial_proposal(text, daypart="afternoon"),
                               driver=driver, policy=policy, reference_time=clock))
    assert report.result.outcome == expected, report.state.completion_reason
    assert report.state.target_date.isoformat() == "2026-11-17"
    assert report.state.target_time_window.model_dump(mode="json") == window(start="12:00", end="16:00")
    assert report.budgets.tool_calls == 6 and report.budgets.model_calls == 0
    assert "Assumed daypart window" in " ".join(report.result.general_warnings)
    assert "12:00:00-10:00" in " ".join(report.result.general_warnings)
    if expected == "RECOMMENDATIONS":
        assert [r.beach_id for r in report.result.recommendations] == ["TEST_BEACH_B"]
    else:
        assert report.state.status == "ABSTAINED" and not report.result.recommendations
        assert any("TARGET_WINDOW_NOT_COVERED" in d.reasons for d in report.evidence_report.decisions)
        assert all(a.eligibility != "ELIGIBLE" for a in report.state.assessments)
    rendered = render_report(report, catalog=scenario().application.catalog, policy=policy)
    assert "16:00 HST" in rendered and "Assumed daypart window" in rendered


def test_afternoon_geographic_followup_preserves_absolute_interval_and_disclosure():
    async def exercise():
        driver, policy = afternoon_components()
        session = SessionManager()
        text = TEXT.replace("morning", "afternoon")
        first = await start(session, text=text, data=initial_proposal(text, daypart="afternoon"),
                            driver=driver, policy=policy, reference_time=datetime.fromisoformat("2026-11-17T00:30:00+00:00"))
        text = "Near Napili instead."
        second = await follow(session, text, data=proposal(text, {"preferred_area": "Napili"}, {"preferred_area": "Near Napili"}),
                              driver=driver, policy=policy, reference_time=datetime.fromisoformat("2026-11-17T11:00:00-10:00"))
        assert first.state.status == second.state.status == "COMPLETED"
        assert first.state.target_time_window == second.state.target_time_window
        origin = next(o for o in second.request_receipt.origins if o.field == "target_time_window")
        assert origin.source == "INHERITED" and origin.default_rule == "afternoon" and origin.assumed
        assert origin.inherited_from == first.state.investigation_id
        assert second.result.request_revision == 2
        assert "Assumed daypart window" in " ".join(second.result.general_warnings)
    asyncio.run(exercise())
