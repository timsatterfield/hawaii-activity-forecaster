"""Explicit synthetic component demonstrations, not scenario acceptance runs.

Plans are authored here and never inferred from scripts, source payloads or the
independent evaluator. Only the application and trusted-driver projections enter
the existing graph. No natural-language request interpretation is performed.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from hawaii_activity_forecaster.harness import load_scenario
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.models import (
    BeachCatalog, NormalizedRequest, SpecialistInvestigationRequest, TraceEvent,
)
from hawaii_activity_forecaster.orchestration import SkeletonReport, run_synthetic_tool_graph
from hawaii_activity_forecaster.tools import ToolAction

DemoCase = Literal["advisory", "outage"]
_SCENARIOS = {"advisory": "SC-004", "outage": "SC-010"}


class DemoUnavailable(ValueError):
    """Preflight prevents this component demonstration from running."""


@dataclass(frozen=True)
class DemoOutput:
    report: SkeletonReport
    catalog: BeachCatalog
    policy: PolicyConfiguration


async def run_demo(case: DemoCase, fixture_root: str | Path, *,
                   record_event: Callable[[TraceEvent], None] | None = None) -> DemoOutput:
    """Run one fixed fictional example; keep full acceptance readiness unchanged."""
    if case not in _SCENARIOS:
        raise DemoUnavailable("Unknown synthetic demonstration.")
    scenario_id = _SCENARIOS[case]
    scenario = load_scenario(fixture_root, scenario_id)
    status = scenario.definition.test_status
    if status != "ACTIVE":
        raise DemoUnavailable(f"Synthetic demonstration definition is {status}; it was not executed.")
    application = scenario.application
    candidates = (("TEST_BEACH_A", "TEST_BEACH_B") if case == "advisory" else
                  ("TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_C", "TEST_BEACH_D"))
    window = {"start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"}

    def plan(snapshot):
        if snapshot.iteration_count:
            return ()
        return tuple(SpecialistInvestigationRequest(
            request_id=role + "-delegation", investigation_id=snapshot.investigation_id,
            request_revision=snapshot.request_revision, schema_version=snapshot.schema_version, agent_type=role,
            candidate_beach_ids=list(candidates), target_time_window=window,
            requested_evidence=[dict(requirement_id=category, evidence_type=category,
                                     priority="OPTIONAL" if category == "UNDERWATER_VISIBILITY" else "REQUIRED")
                                for category in categories],
            known_evidence_gaps=[], issued_at=snapshot.updated_at, attempt_number=1,
        ) for role, categories in (
            ("WEATHER", ("OFFICIAL_ADVISORIES", "WIND_CONDITIONS")),
            ("OCEAN", ("SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS",
                       "WATER_QUALITY_ADVISORY_CHECK", "UNDERWATER_VISIBILITY")),
        ))

    def call(name, source, categories, beaches=candidates, zone=None, **recovery):
        return ToolAction(action_id=name, source_id=source, candidate_beach_ids=list(beaches),
                          requested_evidence=categories,
                          geographic_scope={"zone": zone or f"SYNTHETIC_{scenario_id}_REGION"}, **recovery)

    def tools(parent):
        if parent.agent_type == "WEATHER":
            return (call("alerts", "NWS_ALERTS", ["OFFICIAL_ADVISORIES"]),
                    call("wind", "NWS_WEATHER", ["WIND_CONDITIONS"]))
        marine = ["SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS"]
        if case == "outage":
            return (
                call("water", "HI_DOH_CWB", ["WATER_QUALITY_ADVISORY_CHECK"]),
                call("visibility", "HWT_VISIBILITY", ["UNDERWATER_VISIBILITY"]),
                call("marine", "NWS_MARINE", marine, zone="SYNTHETIC_SC010_REGION"),
                call("retry-marine", "NWS_MARINE", marine, zone="SYNTHETIC_SC010_REGION", retry_of="marine"),
                call("surf-fallback", "HWT_SURF", ["SURF_WAVE_CONDITIONS"], fallback_of="marine"),
                call("current-fallback", "SNORKEL_STORE", ["CURRENTS_PERSISTENT_HAZARDS"], fallback_of="marine"),
            )
        return (
            call("marine", "NWS_MARINE", marine),
            call("water-a", "HI_DOH_CWB", ["WATER_QUALITY_ADVISORY_CHECK"], ("TEST_BEACH_A",)),
            call("water-b", "HI_DOH_CWB", ["WATER_QUALITY_ADVISORY_CHECK"], ("TEST_BEACH_B",)),
            call("visibility", "HWT_VISIBILITY", ["UNDERWATER_VISIBILITY"]),
        )

    request = NormalizedRequest(original_request=application.user_request, activity="SNORKELING",
                                target_time_window=window, hard_constraints=[], soft_preferences=[],
                                clarification_needed=False, clarification_questions=[])
    # Memory recording is solely a component-test seam. This command does not
    # claim authoritative JSONL tracing or full scenario acceptance.
    events = []
    report = await run_synthetic_tool_graph(
        request, catalog=application.catalog, candidate_beach_ids=candidates, plan=plan, tool_plan=tools,
        driver_inputs=scenario.driver, evidence_policy=application.policy_configuration,
        record_event=record_event if record_event is not None else events.append,
        safety_evaluation=True, result_generation=True,
    )
    return DemoOutput(report, application.catalog, application.policy_configuration)
