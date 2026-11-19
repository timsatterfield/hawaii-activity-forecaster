"""Authored raw integration inputs. No evaluator/oracle is used to choose work."""

from pathlib import Path

from hawaii_activity_forecaster.harness import load_scenario
from hawaii_activity_forecaster.harness.contracts import DriverInputs
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.models import SpecialistInvestigationRequest
from hawaii_activity_forecaster.orchestration import run_raw_synthetic_tool_graph
from hawaii_activity_forecaster.tools import ToolAction
from interpretation_samples import REFERENCE, proposal, window

SOUTH = {"kind": "LOCATION_RESTRICTION", "scope": "REGION", "value": "SOUTH_MAUI"}
AB = ("TEST_BEACH_A", "TEST_BEACH_B")
TEXT = "Snorkel tomorrow morning only South Maui. I'm intermediate."


def scenario():
    return load_scenario(Path(__file__).resolve().parents[1] / "fixtures/scenario-pack-v1", "SC-004")


def initial_proposal(text=TEXT, *, activity="SNORKELING", verb="Snorkel", daypart="morning"):
    changes = {"activity": activity, "target_date": "2026-11-17",
               "target_time_window": window(start="12:00", end="16:00") if daypart == "afternoon" else window(),
               "hard_constraints": [SOUTH]}
    supports = {"activity": verb, "target_date": "tomorrow", "target_time_window": daypart,
                "hard_constraints": "only South Maui"}
    if "intermediate" in text:
        changes["experience_level"] = "INTERMEDIATE"
        supports["experience_level"] = "intermediate"
    return proposal(text, changes, supports)


def plan(inputs):
    snapshot = inputs.state
    if snapshot.iteration_count:
        return ()
    return tuple(SpecialistInvestigationRequest(
        request_id=role + "-delegation", investigation_id=snapshot.investigation_id,
        request_revision=snapshot.request_revision, schema_version=snapshot.schema_version, agent_type=role,
        candidate_beach_ids=list(AB), target_time_window=snapshot.target_time_window,
        requested_evidence=[dict(requirement_id=c, evidence_type=c,
                                 priority="OPTIONAL" if c == "UNDERWATER_VISIBILITY" else "REQUIRED") for c in categories],
        known_evidence_gaps=[], issued_at=snapshot.updated_at, attempt_number=1,
    ) for role, categories in (
        ("WEATHER", ("OFFICIAL_ADVISORIES", "WIND_CONDITIONS")),
        ("OCEAN", ("SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS", "WATER_QUALITY_ADVISORY_CHECK", "UNDERWATER_VISIBILITY")),
    ))


def tools(parent):
    def call(name, source, categories, beaches=AB):
        return ToolAction(action_id=name, source_id=source, candidate_beach_ids=list(beaches),
                          requested_evidence=categories, geographic_scope={"zone": "SYNTHETIC_SC-004_REGION"})
    if parent.agent_type == "WEATHER":
        return (call("alerts", "NWS_ALERTS", ["OFFICIAL_ADVISORIES"]), call("wind", "NWS_WEATHER", ["WIND_CONDITIONS"]))
    return (
        call("marine", "NWS_MARINE", ["SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS"]),
        call("water-a", "HI_DOH_CWB", ["WATER_QUALITY_ADVISORY_CHECK"], ("TEST_BEACH_A",)),
        call("water-b", "HI_DOH_CWB", ["WATER_QUALITY_ADVISORY_CHECK"], ("TEST_BEACH_B",)),
        call("visibility", "HWT_VISIBILITY", ["UNDERWATER_VISIBILITY"]),
    )


def runner(data=None, *, events=None, planner=plan, interpreter=None, model_adapter=None,
           policy=None, driver=None, recorder=None, tool_planner=tools):
    sample = scenario()
    normalizer = interpreter
    if normalizer is None and model_adapter is None:
        normalizer = lambda inputs: data if data is not None else initial_proposal()
    async def execute(admission):
        return await run_raw_synthetic_tool_graph(
            admission, interpreter=normalizer,
            model_adapter=model_adapter, plan=planner, tool_plan=tool_planner,
            driver_inputs=driver or sample.driver, evidence_policy=policy or sample.application.policy_configuration,
            record_event=recorder or (events.append if events is not None else lambda event: None),
        )
    return execute


async def start(session, *, text=TEXT, catalog=None, reference_time=REFERENCE, **kwargs):
    return await session.start_raw(text, catalog=catalog if catalog is not None else scenario().application.catalog,
                                   reference_time=reference_time, run=runner(**kwargs))


async def follow(session, text, *, reference_time=REFERENCE, **kwargs):
    return await session.follow_up_raw(text, catalog=scenario().application.catalog, reference_time=reference_time,
                                       run=runner(**kwargs))


def afternoon_components(evidence_end="16:00"):
    """Test-only authored variant: full request, explicit source coverage interval.

    It is not a change to the approved SC-004 fixture or a full afternoon scenario.
    Classification premises require accepted evidence for the entire request.
    """
    sample = scenario()
    target = window(start="12:00", end="16:00")
    source_window = window(start="12:00", end=evidence_end)
    data = sample.driver.model_dump(mode="json", exclude_unset=True)
    for operation in data["script"]["operations"]:
        operation["target_time_window"] = target
    for response in data["source_responses"].values():
        for finding in response["findings"]:
            finding.update(valid_from=source_window["start"], valid_until=source_window["end"])
            for measurement in finding.get("measurements") or ():
                measurement["measurement_time"] = source_window["start"]
            for advisory in finding.get("advisories") or ():
                advisory.update(effective_from=source_window["start"], effective_until=source_window["end"])
    policy = sample.application.policy_configuration.model_dump(mode="json")
    for premise in policy["premises"]:
        premise["time_window"] = target
    return DriverInputs.model_validate(data), PolicyConfiguration.model_validate(policy)
