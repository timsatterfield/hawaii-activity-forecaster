"""Explicit v2 loading with one-read snapshots and separate projections."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from hawaii_activity_forecaster.fixtures.loading import (
    FixtureLoadError, UnsupportedFixtureVersionError, _finite_float, _input_path,
    _reject_constant, _unique_json_object, _validated,
)
from hawaii_activity_forecaster.models import BeachCatalog, EnvironmentalToolResponse

from .behavior import BehaviorScript, RequestStep
from .contracts import (
    ApplicationInputs, DriverInputs, EvaluatorInputs, ExecutionReadiness,
    HarnessManifest, ScenarioFile, SourceSet, TestScenario,
)
from .assertions import ExpectedResults
from .policy import PolicyConfiguration
from .preflight import (
    check_assertion_refs, check_malformed, check_policy, check_script,
    check_sources, require, requirement_refs,
)

_V2 = {"fixture_format_version": "2.0.0", "fixture_package_version": "1.6.0",
       "schema_version": "0.1", "policy_version": "0.2", "harness_contract_version": "1.0.0"}
_POLICY = {"harness_contract_version": "1.0.0", "policy_version": "0.2",
           "policy_configuration_version": "synthetic-policy-1.0.0"}


class _Snapshots:
    def __init__(self, root: Path):
        self.root = root
        self.raw: dict[Path, bytes] = {}
        self.digests: dict[str, str] = {}

    def read(self, reference: str, area: str):
        path = _input_path(self.root, reference, area)
        if path not in self.raw:
            try:
                self.raw[path] = path.read_bytes()
            except OSError:
                raise FixtureLoadError("Cannot read a required harness artifact.") from None
        content = self.raw[path]
        self.digests[path.relative_to(self.root).as_posix()] = hashlib.sha256(content).hexdigest()
        try:
            return json.loads(content.decode("utf-8"), object_pairs_hook=_unique_json_object,
                              parse_float=_finite_float, parse_constant=_reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            raise FixtureLoadError("Invalid harness JSON.") from None

    def model(self, model, reference, area, versions=None):
        raw = self.read(reference, area)
        if versions and isinstance(raw, dict):
            for field, version in versions.items():
                if field in raw and isinstance(raw[field], str) and raw[field] != version:
                    raise UnsupportedFixtureVersionError(f"Unsupported harness version: {field}.")
        return _validated(model, raw, model.__name__)


def _snapshot(model) -> bytes:
    # Preserve explicit expected:null while omitting unused behavior/operand fields.
    return model.model_dump_json(exclude_unset=True).encode("utf-8")


@dataclass(frozen=True)
class LoadedScenario:
    """Harness-owned snapshots. Pass only .application to application code.

    Each access returns a fresh validated copy, isolating nested mutable values.
    This is a data-flow boundary, not a process/filesystem sandbox.
    """
    _definition: bytes
    _application: bytes
    _driver: bytes
    _evaluator: bytes

    @property
    def definition(self) -> TestScenario:
        return TestScenario.model_validate_json(self._definition)

    @property
    def application(self) -> ApplicationInputs:
        return ApplicationInputs.model_validate_json(self._application)

    @property
    def driver(self) -> DriverInputs:
        return DriverInputs.model_validate_json(self._driver)

    @property
    def evaluator(self) -> EvaluatorInputs:
        return EvaluatorInputs.model_validate_json(self._evaluator)

    @property
    def execution_readiness(self) -> ExecutionReadiness:
        status = self.definition.test_status
        if status == "DISABLED":
            return ExecutionReadiness(outcome="NOT_RUN", reason="Scenario definition is disabled.")
        if status == "BLOCKED":
            return ExecutionReadiness(outcome="BLOCKED", reason="Scenario definition is blocked.")
        return ExecutionReadiness(outcome="BLOCKED", reason=(
            "Full acceptance requires a genuine model-driven run: 'hafi evaluate --agent' with "
            "'--live' or '--local'. Preflight alone executes nothing; '--component' runs authored "
            "plans, and offline model transport is a component check."
        ))


def load_scenario(root: str | Path, scenario_id: str) -> LoadedScenario:
    """Preflight one registered scenario; never execute or return an acceptance PASS."""
    try:
        package_root = Path(root).resolve()
    except (OSError, ValueError, RuntimeError):
        raise FixtureLoadError("Cannot resolve harness package root.") from None
    reader = _Snapshots(package_root)
    manifest = reader.model(HarnessManifest, "manifest.json", "", _V2)
    for entry in manifest.scenarios:
        require(entry.path == f"scenarios/{entry.scenario_id}/scenario.json", "Scenario registration path/ID mismatch.")
        _input_path(package_root, entry.path, "scenarios")
    registrations = {s.scenario_id: s for s in manifest.scenarios}
    require(scenario_id in registrations, "Scenario is not registered in this package.")
    scenario = reader.model(ScenarioFile, registrations[scenario_id].path, f"scenarios/{scenario_id}")
    require(scenario.scenario_id == scenario_id, "Scenario ID does not match registration.")
    require(scenario.catalog_fixture == manifest.catalog_fixture, "Scenario catalog differs from manifest.")
    requirement_refs(scenario.requirement_ids)

    registry = {s.fixture_id: s for s in manifest.source_fixtures}
    selected = {}
    for ref, agent in ((scenario.weather_fixture, "WEATHER"), (scenario.ocean_fixture, "OCEAN")):
        if ref is None:
            continue
        source_set = reader.model(SourceSet, ref, "source_sets", {"harness_contract_version": "1.0.0"})
        require(source_set.agent_type == agent, "Source set belongs to another specialist domain.")
        for fixture_id in source_set.source_fixture_ids:
            require(fixture_id in registry, "Source set references an unregistered fixture.")
            require(registry[fixture_id].agent_type == source_set.agent_type, "Source-set entry has wrong domain.")
            require(fixture_id not in selected, "Source selected more than once.")
            selected[fixture_id] = registry[fixture_id]
    catalog = reader.model(BeachCatalog, scenario.catalog_fixture, "catalogs")
    policy = reader.model(PolicyConfiguration, scenario.policy_configuration, "policies", _POLICY)
    responses = {key: reader.model(EnvironmentalToolResponse, entry.path, f"sources/{entry.agent_type.value.lower()}")
                 for key, entry in selected.items()}
    check_sources(registry, responses, catalog)

    if scenario.tool_behavior is None:
        script = BehaviorScript(harness_contract_version="1.0.0", requests=[RequestStep(
            request_step=1, user_request=scenario.user_request, reference_time=scenario.reference_time,
        )], operations=[])
    else:
        script = reader.model(BehaviorScript, scenario.tool_behavior.script, "behaviors", {"harness_contract_version": "1.0.0"})
    check_script(script, registry, responses, scenario)
    check_policy(policy, responses, catalog, script)
    malformed = {}
    for operation in script.operations:
        for attempt in operation.attempts:
            if attempt.behavior == "MALFORMED":
                raw = reader.read(attempt.raw_response_path, "malformed")
                check_malformed(attempt, raw)
                malformed[attempt.raw_response_path] = raw

    expected_path = f"scenarios/{scenario_id}/expected.json"
    require(scenario.expected_results.path == expected_path, "Expected results path must belong to this scenario.")
    expected = reader.model(ExpectedResults, expected_path, f"scenarios/{scenario_id}", {"harness_contract_version": "1.0.0"})
    for assertion in expected.assertions:
        check_assertion_refs(assertion, script, responses, catalog)
    definition_data = scenario.model_dump(exclude_unset=True)
    definition_data["expected_results"] = expected
    definition = _validated(TestScenario, definition_data, "resolved TestScenario")
    application = ApplicationInputs(user_request=scenario.user_request, reference_time=scenario.reference_time,
                                    catalog=catalog, policy_configuration=policy)
    driver = DriverInputs(script=script, source_responses=responses, malformed_responses=malformed)
    evaluator = EvaluatorInputs(expected_results=expected, artifact_digests=reader.digests)
    return LoadedScenario(_snapshot(definition), _snapshot(application), _snapshot(driver), _snapshot(evaluator))
