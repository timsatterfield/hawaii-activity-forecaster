"""Graph/tool integration only: authored scenario acceptance remains blocked."""

import asyncio
from pathlib import Path

import pytest

from hawaii_activity_forecaster.harness import load_scenario
from hawaii_activity_forecaster.models import NormalizedRequest, SpecialistInvestigationRequest
from hawaii_activity_forecaster.orchestration import run_synthetic_tool_graph
from hawaii_activity_forecaster.tools import ToolAction
from specialist_samples import BEACH, catalog, normalized, request
from tool_samples import action, inputs, operation


def plan(snapshot):
    if snapshot.iteration_count:
        return ()
    return tuple(request(role, investigation_id=snapshot.investigation_id, issued_at=snapshot.updated_at)
                 for role in ("WEATHER", "OCEAN"))


def test_both_domains_share_real_tool_budget_and_bindings_in_graph():
    data = inputs(operation(behaviors=("TIMEOUT", "SUCCESS")),
                  operation(op_id="ocean", source="NWS_MARINE", role="OCEAN", categories=("SURF_WAVE_CONDITIONS",)))
    def tools(parent):
        if parent.agent_type == "WEATHER":
            return (action(), action("weather-retry", retry_of="main"))
        return (action("ocean", source="NWS_MARINE", categories=("SURF_WAVE_CONDITIONS",)),)
    events = []
    report = asyncio.run(run_synthetic_tool_graph(
        normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,), plan=plan, tool_plan=tools,
        driver_inputs=data, record_event=events.append,
    ))
    assert report.budgets.tool_calls == report.state.tool_call_count == 3
    assert report.budgets.retries == report.state.retry_count == 1
    assert report.budgets.model_calls == 0 and report.budgets.iterations == 1
    assert len(report.state.weather_findings) == len(report.state.ocean_findings) == 1
    assert len(report.tool_bindings) == 3
    assert len({b.runtime_tool_call_id for b in report.tool_bindings}) == 3
    assert report.state.completion_reason == "VALIDATORS_NOT_IMPLEMENTED"
    called = [event for event in events if event.event_type == "TOOL_CALLED"]
    assert len(called) == 3 and all(e.details["specialist_attempt"] == 1 for e in called)
    assert not any(e.event_type in {"POLICY_EVALUATED", "EVIDENCE_VALIDATED", "RESULT_VALIDATED"} for e in events)


@pytest.mark.parametrize("failure_at", ["TOOL_CALLED", "TOOL_COMPLETED"])
def test_graph_recorder_failure_stops_tools_and_keeps_accurate_dispatched_counts(failure_at):
    def recorder(event):
        if event.event_type == failure_at:
            raise OSError("synthetic disk failure")
    def weather_only(snapshot):
        return plan(snapshot)[:1]
    report = asyncio.run(run_synthetic_tool_graph(
        normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,), plan=weather_only,
        tool_plan=lambda parent: (action(),), driver_inputs=inputs(), record_event=recorder,
    ))
    assert report.state.completion_reason == "TRACE_WRITE_FAILED"
    assert not report.trace_writable and report.budgets.closed
    assert report.budgets.tool_calls == report.state.tool_call_count == (0 if failure_at == "TOOL_CALLED" else 1)
    assert not report.state.weather_findings


def test_authored_sc010_outage_dispatch_and_recovery_without_reading_oracle():
    root = Path(__file__).resolve().parents[1] / "fixtures" / "scenario-pack-v1"
    scenario = load_scenario(root, "SC-010")
    application = scenario.application
    driver = scenario.driver
    candidates = ("TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_C", "TEST_BEACH_D")
    # Hand-authored trusted plan. It does not enumerate operations or expectations
    # to decide which sources, recoveries or candidates to investigate.
    window = {"start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"}
    def plan_requests(snapshot):
        if snapshot.iteration_count:
            return ()
        result = []
        for role, categories in (("WEATHER", ("OFFICIAL_ADVISORIES", "WIND_CONDITIONS")),
                                 ("OCEAN", ("SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS",
                                            "WATER_QUALITY_ADVISORY_CHECK", "UNDERWATER_VISIBILITY"))):
            result.append(SpecialistInvestigationRequest(
                request_id=role + "-delegation", investigation_id=snapshot.investigation_id,
                request_revision=snapshot.request_revision, schema_version=snapshot.schema_version, agent_type=role,
                candidate_beach_ids=list(candidates), target_time_window=window,
                requested_evidence=[dict(requirement_id=c, evidence_type=c,
                                         priority="OPTIONAL" if c == "UNDERWATER_VISIBILITY" else "REQUIRED") for c in categories],
                known_evidence_gaps=[], issued_at=snapshot.updated_at, attempt_number=1,
            ))
        return tuple(result)
    def call(name, source, categories, zone="SYNTHETIC_SC-010_REGION", **recovery):
        return ToolAction(action_id=name, source_id=source, candidate_beach_ids=list(candidates),
                          requested_evidence=categories, geographic_scope={"zone": zone}, **recovery)
    def tools(parent):
        if parent.agent_type == "WEATHER":
            return (call("alerts", "NWS_ALERTS", ["OFFICIAL_ADVISORIES"]), call("wind", "NWS_WEATHER", ["WIND_CONDITIONS"]))
        marine = ["SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS"]
        return (
            call("water", "HI_DOH_CWB", ["WATER_QUALITY_ADVISORY_CHECK"]),
            call("visibility", "HWT_VISIBILITY", ["UNDERWATER_VISIBILITY"]),
            call("marine", "NWS_MARINE", marine, "SYNTHETIC_SC010_REGION"),
            call("marine-retry", "NWS_MARINE", marine, "SYNTHETIC_SC010_REGION", retry_of="marine"),
            call("surf-fallback", "HWT_SURF", ["SURF_WAVE_CONDITIONS"], fallback_of="marine"),
            call("current-fallback", "SNORKEL_STORE", ["CURRENTS_PERSISTENT_HAZARDS"], fallback_of="marine"),
        )
    normalized_input = NormalizedRequest(original_request=application.user_request, activity="SNORKELING",
                                         target_time_window=window, hard_constraints=[], soft_preferences=[],
                                         clarification_needed=False, clarification_questions=[])
    report = asyncio.run(run_synthetic_tool_graph(
        normalized_input, catalog=application.catalog, candidate_beach_ids=candidates, plan=plan_requests,
        tool_plan=tools, driver_inputs=driver, record_event=lambda event: None,
    ))
    assert report.budgets.tool_calls == report.state.tool_call_count == 8
    assert report.budgets.retries == 1 and report.budgets.fallbacks == 2
    assert len(report.tool_bindings) == 8
    assert report.state.unresolved_evidence_issues
    assert report.state.weather_findings and report.state.ocean_findings
    assert report.state.status == "FAILED" and report.state.outcome == "ERROR"
    assert report.state.assessments == []
    assert scenario.execution_readiness.outcome == "BLOCKED"
