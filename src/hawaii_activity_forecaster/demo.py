"""Explicit synthetic component demonstrations, not scenario acceptance runs.

Plans are authored here and never inferred from scripts, source payloads or the
independent evaluator. Only application and trusted-driver projections enter the
graph. Authored proposals are checked inside raw admission; general conversational
execution and real model planning remain deferred.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from hawaii_activity_forecaster.harness import ApplicationInputs, load_scenario
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.models import (
    BeachCatalog, NormalizedRequest, SpecialistInvestigationRequest, TraceEvent,
)
from hawaii_activity_forecaster.orchestration import (
    SessionManager, SessionRequest, SkeletonReport, run_raw_synthetic_tool_graph, run_synthetic_tool_graph,
)
from hawaii_activity_forecaster.tools import ToolAction
from hawaii_activity_forecaster.config.settings import TraceSettings

DemoCase = Literal["advisory", "outage"]
_SCENARIOS = {"advisory": "SC-004", "outage": "SC-010"}


class DemoUnavailable(ValueError):
    """Preflight prevents this component demonstration from running."""


@dataclass(frozen=True)
class DemoOutput:
    report: SkeletonReport
    catalog: BeachCatalog
    policy: PolicyConfiguration


@dataclass(frozen=True)
class SessionDemoOutput:
    investigations: tuple[DemoOutput, ...]


def _load_demo(case: DemoCase, fixture_root: str | Path):
    if case not in _SCENARIOS:
        raise DemoUnavailable("Unknown synthetic demonstration.")
    scenario = load_scenario(fixture_root, _SCENARIOS[case])
    status = scenario.definition.test_status
    if status != "ACTIVE":
        raise DemoUnavailable(f"Synthetic demonstration definition is {status}; it was not executed.")
    return scenario


async def run_demo(case: DemoCase, fixture_root: str | Path, *,
                   record_event: Callable[[TraceEvent], None] | None = None,
                   session_request: SessionRequest | None = None,
                   trace_settings: TraceSettings | None = None) -> DemoOutput:
    """Run one fixed fictional example; keep full acceptance readiness unchanged."""
    scenario = _load_demo(case, fixture_root)
    application, driver = scenario.application, scenario.driver
    if session_request is not None:
        return await execute_authored_step(case, application, driver, session_request=session_request,
                                           record_event=record_event, trace_settings=trace_settings)
    session = SessionManager()
    async def execute(admission):
        return (await execute_authored_step(case, application, driver, admission=admission,
                                           record_event=record_event, trace_settings=trace_settings)).report
    report = await session.start_raw(application.user_request, catalog=application.catalog,
                                     reference_time=application.reference_time, run=execute)
    session.close()
    return DemoOutput(report, application.catalog, application.policy_configuration)


def authored_interpretation(inputs):
    """Authored morning/snorkeling fixture proposal, independently checked in-graph.

    No fixture behaviors, expected values or driver scripts are interpreter inputs.
    This deliberately narrow callback does not enable a general language interface.
    """
    text = inputs.original_request
    values = dict(activity="SNORKELING", target_date="2026-11-17", target_time_window={
        "start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"})
    supports = {"activity": "snorkel", "target_date": "tomorrow", "target_time_window": "morning"}
    if "near Kihei" in text:
        values["preferred_area"] = "Kihei"
        supports["preferred_area"] = "near Kihei"
    return dict(changed_values=values, source_spans=[dict(field=name, start=text.index(fragment),
        end=text.index(fragment) + len(fragment)) for name, fragment in supports.items()])


async def execute_authored_step(case, application, driver_inputs, *, admission=None, session_request=None,
                                record_event=None, trace_settings=None, request_step=1, interpreter=authored_interpretation):
    """Trusted component runner: only application/driver projections, no oracle."""
    scenario_id = _SCENARIOS[case]
    candidates = (("TEST_BEACH_A", "TEST_BEACH_B") if case == "advisory" else
                  ("TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_C", "TEST_BEACH_D"))
    if admission is None and session_request is None:
        raise DemoUnavailable("An admitted component request is required.")
    request = admission.request if admission is not None else session_request.request

    def plan(snapshot):
        if snapshot.iteration_count:
            return ()
        return tuple(SpecialistInvestigationRequest(
            request_id=role + "-delegation", investigation_id=snapshot.investigation_id,
            request_revision=snapshot.request_revision, schema_version=snapshot.schema_version, agent_type=role,
            candidate_beach_ids=list(candidates), target_time_window=snapshot.target_time_window,
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

    # The application path requires local JSONL. An explicitly supplied memory
    # recorder remains a component-test seam and claims no durable trace.
    if admission is not None:
        report = await run_raw_synthetic_tool_graph(
            admission, interpreter=interpreter, plan=lambda inputs: plan(inputs.state), tool_plan=tools,
            driver_inputs=driver_inputs, evidence_policy=application.policy_configuration,
            record_event=record_event, trace_settings=trace_settings, request_step=request_step,
        )
    else:
        report = await run_synthetic_tool_graph(
            request, catalog=application.catalog, candidate_beach_ids=candidates, plan=plan, tool_plan=tools,
            driver_inputs=driver_inputs, evidence_policy=application.policy_configuration,
            record_event=record_event, trace_settings=trace_settings, request_step=request_step,
            safety_evaluation=True, result_generation=True, session_request=session_request,
        )
    return DemoOutput(report, application.catalog, application.policy_configuration)


def authored_component_runner(case: DemoCase, *, interpreter=authored_interpretation):
    """Explicitly configure one existing authored plan; never infer one from scripts."""
    if case not in _SCENARIOS:
        raise DemoUnavailable("No authored component runtime is available.")
    async def execute(inputs):
        context = inputs.admission.context
        application = ApplicationInputs(user_request=context.original_request, reference_time=context.reference_time,
                                        catalog=context.catalog, policy_configuration=inputs.policy)
        return (await execute_authored_step(case, application, inputs.driver_inputs, admission=inputs.admission,
                    trace_settings=inputs.trace_settings, request_step=inputs.request_step, interpreter=interpreter)).report
    return execute


async def run_session_demo(fixture_root: str | Path, *,
                           record_event: Callable[[TraceEvent], None] | None = None,
                           trace_settings: TraceSettings | None = None) -> SessionDemoOutput:
    """Two authored normalized requests in one session, with independent retrievals.

    This is not SC-012 acceptance, a language interpreter, or persistent chat.
    No interpretation is derived from the fixture script or evaluator.
    """
    # Preflight before session admission preserves the CLI's usage/error split.
    _load_demo("advisory", fixture_root)
    session = SessionManager()
    outputs = []

    async def run(admission):
        output = await run_demo("advisory", fixture_root, record_event=record_event, session_request=admission,
                                trace_settings=trace_settings)
        outputs.append(output)
        return output.report

    initial = NormalizedRequest(
        original_request=("Fictional demo: snorkel on November 17, 2026, from 8 to 11 a.m. near Kihei. "
                          "I am intermediate and prefer calm water."),
        activity="SNORKELING", target_date="2026-11-17",
        target_time_window={"start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"},
        preferred_area="Kihei", experience_level="INTERMEDIATE", hard_constraints=[],
        soft_preferences=[{"preference": "calm water"}], clarification_needed=False, clarification_questions=[],
    )
    await session.start(initial, user_provided_fields={"activity", "target_date", "target_time_window", "preferred_area",
                                                       "experience_level", "soft_preferences"}, run=run)
    await session.follow_up("Actually, prefer Wailea instead in this fictional example.",
                            changes={"preferred_area": "Wailea"}, run=run)
    session.close()
    return SessionDemoOutput(tuple(outputs))
