"""Observed synthetic evidence through LangGraph; full scenarios remain BLOCKED."""

import asyncio
from pathlib import Path

import pytest

from hawaii_activity_forecaster.harness import load_scenario
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.models import NormalizedRequest, SpecialistInvestigationRequest
from hawaii_activity_forecaster.orchestration import run_synthetic_tool_graph
from hawaii_activity_forecaster.tools import ToolAction
from evidence_samples import sample
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
    scenario = load_scenario(Path(__file__).resolve().parents[1] / "fixtures/scenario-pack-v1", scenario_id)
    application = scenario.application
    candidates = (("TEST_BEACH_A", "TEST_BEACH_B") if scenario_id == "SC-004" else
                  ("TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_C", "TEST_BEACH_D"))
    window = {"start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"}
    def plan(snapshot):
        if snapshot.iteration_count:
            return ()
        return tuple(SpecialistInvestigationRequest(
            request_id=role + "-delegation", investigation_id=snapshot.investigation_id,
            request_revision=snapshot.request_revision, schema_version=snapshot.schema_version, agent_type=role,
            candidate_beach_ids=list(candidates), target_time_window=window,
            requested_evidence=[dict(requirement_id=c, evidence_type=c,
                                     priority="OPTIONAL" if c == "UNDERWATER_VISIBILITY" else "REQUIRED") for c in categories],
            known_evidence_gaps=[], issued_at=snapshot.updated_at, attempt_number=1,
        ) for role, categories in (
            ("WEATHER", ("OFFICIAL_ADVISORIES", "WIND_CONDITIONS")),
            ("OCEAN", ("SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS", "WATER_QUALITY_ADVISORY_CHECK", "UNDERWATER_VISIBILITY")),
        ))
    def call(name, source, categories, beaches=candidates, zone=None, **recovery):
        return ToolAction(action_id=name, source_id=source, candidate_beach_ids=list(beaches),
                          requested_evidence=categories, geographic_scope={"zone": zone or f"SYNTHETIC_{scenario_id}_REGION"}, **recovery)
    def tools(parent):
        if parent.agent_type == "WEATHER":
            return (call("alerts", "NWS_ALERTS", ["OFFICIAL_ADVISORIES"]), call("wind", "NWS_WEATHER", ["WIND_CONDITIONS"]))
        if scenario_id == "SC-010":
            marine = ["SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS"]
            return (
                call("water", "HI_DOH_CWB", ["WATER_QUALITY_ADVISORY_CHECK"]),
                call("visibility", "HWT_VISIBILITY", ["UNDERWATER_VISIBILITY"]),
                call("marine", "NWS_MARINE", marine, zone="SYNTHETIC_SC010_REGION"),
                call("retry-marine", "NWS_MARINE", marine, zone="SYNTHETIC_SC010_REGION", retry_of="marine"),
                call("surf-fallback", "HWT_SURF", ["SURF_WAVE_CONDITIONS"], fallback_of="marine"),
                call("current-fallback", "SNORKEL_STORE", ["CURRENTS_PERSISTENT_HAZARDS"], fallback_of="marine"),
            )
        return (
            call("marine", "NWS_MARINE", ["SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS"]),
            call("water-a", "HI_DOH_CWB", ["WATER_QUALITY_ADVISORY_CHECK"], ("TEST_BEACH_A",)),
            call("water-b", "HI_DOH_CWB", ["WATER_QUALITY_ADVISORY_CHECK"], ("TEST_BEACH_B",)),
            call("visibility", "HWT_VISIBILITY", ["UNDERWATER_VISIBILITY"]),
        )
    normalized_input = NormalizedRequest(original_request=application.user_request, activity="SNORKELING",
                                         target_time_window=window, hard_constraints=[], soft_preferences=[],
                                         clarification_needed=False, clarification_questions=[])
    report = asyncio.run(run_synthetic_tool_graph(
        normalized_input, catalog=application.catalog, candidate_beach_ids=candidates, plan=plan, tool_plan=tools,
        driver_inputs=scenario.driver, evidence_policy=application.policy_configuration, record_event=lambda event: None,
    ))
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
