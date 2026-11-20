"""Registered-scenario execution through the model-driven agent runtime.

Each ACTIVE scenario declares an explicit tool allowlist in
``agent_tools/<scenario_id>.json``. Its options are never derived from behavior
scripts at runtime: preflight only checks that every declared option is answerable
by the already-validated script, so an option cannot invent permissions or reach an
unscripted query. The model sees option identifiers through the existing runtime
contracts, never scripts, outcomes, expected files or evaluator objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Literal

from hawaii_activity_forecaster.config.settings import ConfigurationModel, TraceSettings
from hawaii_activity_forecaster.fixtures.loading import (
    FixtureLoadError, _finite_float, _input_path, _reject_constant, _unique_json_object, _validated,
)
from hawaii_activity_forecaster.harness.execution import ExecutionEvaluation, _failure, execute_scenario
from hawaii_activity_forecaster.harness.loading import load_scenario
from hawaii_activity_forecaster.harness.policy import CATEGORY_SOURCES
from hawaii_activity_forecaster.models import TimeRange
from hawaii_activity_forecaster.models.permissions import OCEAN_SOURCES, WEATHER_SOURCES
from hawaii_activity_forecaster.tools import ToolAction

from .execution import run_agent_investigation
from .runtime import AgentRuntime

_SCENARIO_ID = re.compile(r"SC-\d{3}")


class ScenarioToolSettings(ConfigurationModel):
    harness_contract_version: Literal["1.0.0"]
    scenario_id: str
    target_windows: list[TimeRange]
    actions: list[ToolAction]


def _role(source_id: str) -> str:
    if source_id in WEATHER_SOURCES:
        return "WEATHER"
    if source_id in OCEAN_SOURCES:
        return "OCEAN"
    raise FixtureLoadError("Agent tool option uses an unknown source role.")


@dataclass(frozen=True)
class ScenarioTools:
    scenario_id: str
    digest: str
    _settings: str = field(repr=False)

    @property
    def settings(self) -> ScenarioToolSettings:
        return ScenarioToolSettings.model_validate_json(self._settings)

    def options(self, role: str, candidates: tuple[str, ...], window: TimeRange) -> tuple[ToolAction, ...]:
        """Options inside the actual delegated scope; regional batches never widen it."""
        if role not in {"WEATHER", "OCEAN"}:
            raise FixtureLoadError("Unknown synthetic source role")
        settings = self.settings
        if window not in settings.target_windows:
            raise FixtureLoadError("The scenario dataset does not cover this requested time window.")
        scope = set(candidates)
        return tuple(a for a in settings.actions
                     if _role(a.source_id) == role and set(a.candidate_beach_ids) <= scope)


def _check(settings: ScenarioToolSettings, loaded) -> None:
    catalog = {b.beach_id for b in loaded.application.catalog.root}
    script = loaded.driver.script
    actions = {a.action_id: a for a in settings.actions}
    if (not settings.actions or not settings.target_windows or len(actions) != len(settings.actions)
            or len(set(map(str, settings.target_windows))) != len(settings.target_windows)):
        raise FixtureLoadError("Agent tool allowlist is empty or has duplicate entries.")
    for action in settings.actions:
        role = _role(action.source_id)
        if (not set(action.candidate_beach_ids) <= catalog
                or len(set(action.candidate_beach_ids)) != len(action.candidate_beach_ids)
                or any(action.source_id not in CATEGORY_SOURCES[c] for c in action.requested_evidence)):
            raise FixtureLoadError("Agent tool option exceeds approved source/catalog scope.")
        origin_id = action.retry_of or action.fallback_of
        if origin_id is not None:
            origin = actions.get(origin_id)
            if origin is None or origin.retry_of or origin.fallback_of:
                raise FixtureLoadError("Recovery option must reference a declared original option.")
            if action.retry_of and (origin.source_id, sorted(origin.candidate_beach_ids), sorted(origin.requested_evidence),
                                    origin.geographic_scope) != (action.source_id, sorted(action.candidate_beach_ids),
                                    sorted(action.requested_evidence), action.geographic_scope):
                raise FixtureLoadError("Retry option must repeat its original query.")
            if action.fallback_of and (len(action.requested_evidence) != 1
                    or not set(action.requested_evidence) <= set(origin.requested_evidence)
                    or set(action.candidate_beach_ids) != set(origin.candidate_beach_ids)
                    or action.source_id == origin.source_id or _role(origin.source_id) != role):
                raise FixtureLoadError("Fallback option must address one original category through another source.")
        answerable = False
        for step in script.requests:
            for window in settings.target_windows:
                key = (step.request_step, role, action.source_id, tuple(sorted(action.candidate_beach_ids)),
                       tuple(sorted(action.requested_evidence)), window.start, window.end,
                       json.dumps(action.geographic_scope, sort_keys=True))
                matches = [op for op in script.operations if op.match_key() == key]
                if len(matches) > 1:
                    raise FixtureLoadError("Agent tool option matches an ambiguous scripted operation.")
                if matches:
                    if action.retry_of and len(matches[0].attempts) < 2:
                        raise FixtureLoadError("Retry option has no scripted second attempt.")
                    answerable = True
        if not answerable:
            raise FixtureLoadError("Agent tool option is not answerable by the scenario script.")


def load_scenario_tools(root: str | Path, scenario_id: str) -> ScenarioTools:
    """Preflight one explicit allowlist against the snapshot-validated scenario."""
    if type(scenario_id) is not str or not _SCENARIO_ID.fullmatch(scenario_id):
        raise FixtureLoadError("Invalid scenario identifier.")
    root = Path(root).resolve()
    loaded = load_scenario(root, scenario_id)
    path = _input_path(root, f"agent_tools/{scenario_id}.json", "agent_tools")
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_object,
                          parse_float=_finite_float, parse_constant=_reject_constant)
    except OSError:
        raise FixtureLoadError("Cannot read the scenario's agent tool allowlist.") from None
    except (ValueError, UnicodeError, RecursionError):
        raise FixtureLoadError("Invalid agent tool allowlist JSON.") from None
    settings = _validated(ScenarioToolSettings, data, "agent tool allowlist")
    if settings.scenario_id != scenario_id:
        raise FixtureLoadError("Agent tool allowlist belongs to another scenario.")
    _check(settings, loaded)
    return ScenarioTools(scenario_id, sha256(raw).hexdigest(), settings.model_dump_json())


def agent_scenario_runner(adapter, tools: ScenarioTools):
    """One fresh Coordinator/specialist runtime per admitted request step."""
    async def execute(inputs):
        return await run_agent_investigation(
            inputs.admission, runtime=AgentRuntime(adapter, tools.options), driver_inputs=inputs.driver_inputs,
            policy=inputs.policy, trace_settings=inputs.trace_settings, request_step=inputs.request_step)
    return execute


async def execute_agent_scenario(root, scenario_id, *, adapter,
                                 trace_settings: TraceSettings | None = None) -> ExecutionEvaluation:
    """Preflight scenario and allowlist before any model call, then evaluate captures.

    Full-scenario PASS additionally requires the evaluator to verify, from each
    authoritative trace, a live or local model target; offline transport stays BLOCKED.
    """
    try:
        loaded = load_scenario(root, scenario_id)
    except Exception:
        return await execute_scenario(root, scenario_id, runtime=None, mode="AGENT_RUNTIME")
    if loaded.definition.test_status != "ACTIVE":
        return await execute_scenario(root, scenario_id, runtime=None, mode="AGENT_RUNTIME")
    try:
        tools = load_scenario_tools(root, scenario_id)
    except FixtureLoadError:
        result = _failure(scenario_id, "FIXTURE_INVALID")
        return ExecutionEvaluation(result.outcome, "AGENT_RUNTIME", (), None, result)
    result = await execute_scenario(root, scenario_id, runtime=agent_scenario_runner(adapter, tools),
                                    trace_settings=trace_settings, mode="AGENT_RUNTIME")
    return replace(result, tool_allowlist_digest=tools.digest)
