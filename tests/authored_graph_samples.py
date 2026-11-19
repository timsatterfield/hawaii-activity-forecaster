"""Explicit authored dispatch plans shared by component tests; no oracle access."""

import asyncio
from pathlib import Path

from hawaii_activity_forecaster.harness import load_scenario
from hawaii_activity_forecaster.models import NormalizedRequest, SpecialistInvestigationRequest
from hawaii_activity_forecaster.orchestration import run_synthetic_tool_graph
from hawaii_activity_forecaster.tools import ToolAction


def run_authored_graph(scenario_id, *, safety_evaluation=False, record_event=None, result_generation=False):
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
        driver_inputs=scenario.driver, evidence_policy=application.policy_configuration,
        record_event=record_event or (lambda event: None), safety_evaluation=safety_evaluation,
        result_generation=result_generation,
    ))
    return report, scenario
