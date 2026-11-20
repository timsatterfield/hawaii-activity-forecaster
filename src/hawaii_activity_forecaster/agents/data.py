"""Small explicit synthetic release configuration using existing fixture contracts."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from pydantic import Field

from hawaii_activity_forecaster.config.settings import ConfigurationModel
from hawaii_activity_forecaster.fixtures import load_fixture_inputs
from hawaii_activity_forecaster.fixtures.loading import FixtureLoadError, _input_path, _read_json, _validated
from hawaii_activity_forecaster.harness.behavior import BehaviorScript
from hawaii_activity_forecaster.harness.contracts import DriverInputs
from hawaii_activity_forecaster.harness.policy import CATEGORY_SOURCES, PolicyConfiguration
from hawaii_activity_forecaster.harness.preflight import check_policy, check_script, check_sources
from hawaii_activity_forecaster.models import BeachCatalog, TimeRange
from hawaii_activity_forecaster.models.permissions import OCEAN_SOURCES, WEATHER_SOURCES
from hawaii_activity_forecaster.tools import ToolAction

CASES = ("favorable", "advisory", "outage", "recovery")


class ToolSettings(ConfigurationModel):
    target_windows: list[TimeRange] = Field(min_length=1)
    actions: list[ToolAction] = Field(min_length=1)


@dataclass(frozen=True)
class ReleaseData:
    reference_time: datetime
    _catalog: str = field(repr=False)
    _policy: str = field(repr=False)
    _driver: str = field(repr=False)
    _tools: str = field(repr=False)

    @property
    def catalog(self) -> BeachCatalog:
        return BeachCatalog.model_validate_json(self._catalog)

    @property
    def policy(self) -> PolicyConfiguration:
        return PolicyConfiguration.model_validate_json(self._policy)

    @property
    def driver(self) -> DriverInputs:
        return DriverInputs.model_validate_json(self._driver)

    @property
    def target_windows(self) -> tuple[TimeRange, ...]:
        return tuple(ToolSettings.model_validate_json(self._tools).target_windows)

    def options(self, role: str, candidates: tuple[str, ...], window: TimeRange) -> tuple[ToolAction, ...]:
        if role not in {"WEATHER", "OCEAN"}:
            raise FixtureLoadError("Unknown synthetic source role")
        settings = ToolSettings.model_validate_json(self._tools)
        if window not in settings.target_windows:
            raise FixtureLoadError("The synthetic dataset does not cover this requested time window.")
        scope = set(candidates)
        sources = WEATHER_SOURCES if role == "WEATHER" else OCEAN_SOURCES
        # One frozen batch per request for regional queries; individual official
        # water checks retain their actual beach scope. No script enumeration.
        return tuple(a for a in settings.actions if a.source_id in sources and
                     (set(a.candidate_beach_ids) == scope or
                      a.source_id == "HI_DOH_CWB" and set(a.candidate_beach_ids) <= scope))


def load_release_data(root: str | Path, case: str = "favorable") -> ReleaseData:
    if case not in CASES:
        raise FixtureLoadError("Unknown synthetic environment")
    root = Path(root).resolve()
    area = root / case
    if not area.resolve().is_relative_to(root):
        raise FixtureLoadError("Synthetic data path escapes its root")
    fixtures = load_fixture_inputs(area)
    policy = _validated(PolicyConfiguration, _read_json(_input_path(area, "policy.json", "")), "release policy")
    script = _validated(BehaviorScript, _read_json(_input_path(area, "behavior.json", "")), "release behavior")
    tools = _validated(ToolSettings, _read_json(_input_path(root, "tools.json", "")), "tool settings")
    registry = {entry.fixture_id: entry for entry in fixtures.manifest.source_fixtures}
    check_sources(registry, fixtures.source_responses, fixtures.catalog)
    check_script(script, registry, fixtures.source_responses,
                 SimpleNamespace(user_request=script.requests[0].user_request, reference_time=fixtures.manifest.reference_time))
    check_policy(policy, fixtures.source_responses, fixtures.catalog, script)
    ids = {b.beach_id for b in fixtures.catalog.root}
    if len({a.action_id for a in tools.actions}) != len(tools.actions):
        raise FixtureLoadError("Duplicate tool option")
    for action in tools.actions:
        if (not set(action.candidate_beach_ids) <= ids or
                any(action.source_id not in CATEGORY_SOURCES[c] for c in action.requested_evidence)):
            raise FixtureLoadError("Tool configuration exceeds approved source/catalog scope")
    driver = DriverInputs(script=script, source_responses=fixtures.source_responses, malformed_responses={})
    return ReleaseData(fixtures.manifest.reference_time, fixtures.catalog.model_dump_json(), policy.model_dump_json(),
                       driver.model_dump_json(exclude_unset=True), tools.model_dump_json())
