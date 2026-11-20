"""V2 preflight/oracle separation tests; no twelve-scenario execution claims."""

from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from hawaii_activity_forecaster.fixtures import FixtureLoadError, load_fixture_inputs
from hawaii_activity_forecaster.harness import load_scenario
from harness_samples import EXPECTED, SCENARIO, SID, V1, make_package, read, write


@pytest.fixture
def package(tmp_path):
    return make_package(tmp_path)


def test_v2_loads_without_changing_v1_api(package):
    bundle = load_scenario(package, SID)
    assert bundle.definition.scenario_id == SID
    assert bundle.definition.expected_results.scenario_id == SID
    assert bundle.application.user_request == "Synthetic snorkeling request"
    assert len(bundle.application.catalog.root) == 5
    assert len(bundle.driver.source_responses) == 8
    assert bundle.execution_readiness.outcome == "BLOCKED"
    assert "genuine model-driven run" in bundle.execution_readiness.reason
    assert "--agent" in bundle.execution_readiness.reason
    assert len(load_fixture_inputs(V1).catalog.root) == 5
    with pytest.raises(FixtureLoadError):
        load_fixture_inputs(package)
    with pytest.raises(FixtureLoadError):
        load_scenario(V1, SID)


def test_expected_values_and_paths_are_only_in_harness_evaluator_projection(package):
    expected = read(package, EXPECTED)
    # Add an unmistakable oracle value on a valid text field.
    expected["assertions"][0].update(field="/assessment_basis", expected="ORACLE_CANARY_DO_NOT_SHARE")
    write(package, EXPECTED, expected)
    bundle = load_scenario(package, SID)
    for projection in (bundle.application, bundle.driver):
        text = projection.model_dump_json()
        assert "ORACLE_CANARY_DO_NOT_SHARE" not in text
        assert "expected_results" not in text
        assert EXPECTED not in text
        assert "assertions" not in text
        assert "artifact_digests" not in text
    assert "ORACLE_CANARY_DO_NOT_SHARE" in bundle.evaluator.model_dump_json()
    assert bundle.evaluator.artifact_digests[EXPECTED] == hashlib.sha256((package / EXPECTED).read_bytes()).hexdigest()


def test_snapshots_survive_file_and_nested_object_mutation(package):
    bundle = load_scenario(package, SID)
    bundle.application.catalog.root.clear()
    bundle.evaluator.expected_results.assertions.clear()
    bundle.driver.source_responses.clear()
    (package / EXPECTED).write_text("broken after preflight")
    assert len(bundle.application.catalog.root) == 5
    assert len(bundle.evaluator.expected_results.assertions) == 1
    assert len(bundle.driver.source_responses) == 8


@pytest.mark.parametrize("field", ["fixture_format_version", "fixture_package_version", "schema_version", "policy_version", "harness_contract_version"])
def test_unknown_manifest_versions_rejected_before_other_reads(package, field):
    manifest = read(package, "manifest.json")
    manifest[field] = "future-version"
    write(package, "manifest.json", manifest)
    with pytest.raises(FixtureLoadError, match="version"):
        load_scenario(package, SID)


@pytest.mark.parametrize("path,field,value", [
    (SCENARIO, "scenario_id", "wrong"), (SCENARIO, "test_status", "PARTIALLY_BLOCKED"),
    (SCENARIO, "catalog_fixture", "../outside.json"), (SCENARIO, "policy_configuration", EXPECTED),
    (EXPECTED, "scenario_id", "another-scenario"),
    ("policies/unit.json", "harness_contract_version", "future"),
    ("behaviors/unit.json", "harness_contract_version", "future"),
    ("source_sets/weather.json", "agent_type", "OCEAN"),
])
def test_cross_file_errors_fail_preflight(package, path, field, value):
    data = read(package, path)
    data[field] = value
    write(package, path, data)
    with pytest.raises(FixtureLoadError):
        load_scenario(package, SID)


@pytest.mark.parametrize("status,outcome", [("BLOCKED", "BLOCKED"), ("DISABLED", "NOT_RUN")])
def test_definition_readiness_is_never_a_passing_test(package, status, outcome):
    scenario = read(package, SCENARIO)
    scenario["test_status"] = status
    write(package, SCENARIO, scenario)
    assert load_scenario(package, SID).execution_readiness.outcome == outcome


def test_ordinary_response_cannot_be_invalid_contract(package):
    path = "sources/ocean/ocean-marine-forecast.json"
    response = read(package, path)
    del response["retrieved_at"]
    write(package, path, response)
    with pytest.raises(FixtureLoadError, match="EnvironmentalToolResponse"):
        load_scenario(package, SID)


def test_declared_malformed_payload_is_separate_and_fault_scoped(package):
    raw = read(package, "sources/ocean/ocean-marine-forecast.json")
    del raw["retrieved_at"]
    write(package, "malformed/unit.json", raw)
    script = read(package, "behaviors/unit.json")
    attempt = {"attempt": 1, "behavior": "MALFORMED", "simulated_duration_ms": 1,
               "raw_response_path": "malformed/unit.json", "invalid_fields": ["/retrieved_at"]}
    script["operations"][0]["attempts"] = [attempt]
    write(package, "behaviors/unit.json", script)
    bundle = load_scenario(package, SID)
    assert "retrieved_at" not in bundle.driver.malformed_responses["malformed/unit.json"]
    assert "malformed" not in bundle.application.model_dump_json()
    del raw["tool_call_id"]
    write(package, "malformed/unit.json", raw)
    with pytest.raises(FixtureLoadError, match="undeclared contract faults"):
        load_scenario(package, SID)


def test_malformed_behavior_cannot_point_to_valid_response(package):
    write(package, "malformed/valid.json", read(package, "sources/ocean/ocean-marine-forecast.json"))
    script = read(package, "behaviors/unit.json")
    script["operations"][0]["attempts"] = [{"attempt": 1, "behavior": "MALFORMED", "simulated_duration_ms": 1,
        "raw_response_path": "malformed/valid.json", "invalid_fields": ["/retrieved_at"]}]
    write(package, "behaviors/unit.json", script)
    with pytest.raises(FixtureLoadError, match="must actually violate"):
        load_scenario(package, SID)


def test_behavior_status_and_source_permissions_checked(package):
    script = read(package, "behaviors/unit.json")
    script["operations"][0]["attempts"][0]["behavior"] = "ERROR"
    write(package, "behaviors/unit.json", script)
    with pytest.raises(FixtureLoadError, match="status contradicts"):
        load_scenario(package, SID)


def test_declared_evidence_or_missing_coverage_is_required(package):
    policy = read(package, "policies/unit.json")
    policy["evidence_rules"] = [r for r in policy["evidence_rules"] if r["category"] != "OFFICIAL_ADVISORIES"]
    write(package, "policies/unit.json", policy)
    with pytest.raises(FixtureLoadError, match="lacks declared evidence"):
        load_scenario(package, SID)


@pytest.mark.parametrize("mutation", ["unknown_finding", "unknown_beach", "wrong_category", "wrong_temporal_type"])
def test_invalid_policy_bindings_rejected(package, mutation):
    policy = read(package, "policies/unit.json")
    rule = policy["evidence_rules"][0]
    if mutation == "unknown_finding":
        rule["finding_id"] = "missing"
    elif mutation == "unknown_beach":
        rule["beach_ids"] = ["UNKNOWN"]
    elif mutation == "wrong_category":
        rule["category"] = "WATER_QUALITY_ADVISORY_CHECK"
    else:
        rule["temporal_rule"] = "DECLARED_REPORT_WINDOW"
    write(package, "policies/unit.json", policy)
    with pytest.raises(FixtureLoadError):
        load_scenario(package, SID)


@pytest.mark.parametrize("selector", [{"request_step": 2}, {"request_step": 1, "beach_id": "UNKNOWN"}])
def test_assertion_selector_references_must_resolve(package, selector):
    expected = read(package, EXPECTED)
    expected["assertions"][0]["selector"] = selector
    write(package, EXPECTED, expected)
    with pytest.raises(FixtureLoadError):
        load_scenario(package, SID)


def test_scenario_requirement_coverage_cannot_be_omitted(package):
    expected = read(package, EXPECTED)
    expected["assertions"][0]["requirement_ids"] = ["SH-T02"]
    write(package, EXPECTED, expected)
    with pytest.raises(FixtureLoadError, match="resolved TestScenario"):
        load_scenario(package, SID)


def test_unknown_requirement_refs_rejected(package):
    expected = read(package, EXPECTED)
    expected["assertions"][0]["requirement_ids"].append("INVENTED-999")
    write(package, EXPECTED, expected)
    with pytest.raises(FixtureLoadError, match="requirement identifier"):
        load_scenario(package, SID)


def test_expected_files_cannot_be_imported_as_other_artifacts(package):
    link = package / "policies" / "oracle-link.json"
    link.symlink_to(package / EXPECTED)
    scenario = read(package, SCENARIO)
    scenario["policy_configuration"] = "policies/oracle-link.json"
    write(package, SCENARIO, scenario)
    with pytest.raises(FixtureLoadError, match="input area"):
        load_scenario(package, SID)


def test_expected_results_are_validated_before_projection_is_returned(package):
    (package / EXPECTED).write_text('{"assertions": [], "assertions": [1]}')
    with pytest.raises(FixtureLoadError, match="Invalid harness JSON"):
        load_scenario(package, SID)


def test_initial_script_request_must_match_scenario(package):
    script = read(package, "behaviors/unit.json")
    script["requests"][0]["user_request"] = "substituted expected normalization"
    write(package, "behaviors/unit.json", script)
    with pytest.raises(FixtureLoadError, match="First script request"):
        load_scenario(package, SID)


def test_follow_up_requests_and_comparisons_are_preserved_without_running_session(package):
    script = read(package, "behaviors/unit.json")
    script["requests"].append({"request_step": 2, "user_request": "Near Napili instead", "reference_time": script["requests"][0]["reference_time"]})
    write(package, "behaviors/unit.json", script)
    expected = read(package, EXPECTED)
    expected["assertions"].append({
        "assertion_id": "session-same", "requirement_ids": ["SL-T02"], "mandatory": True,
        "test_status": "ACTIVE", "target": "harness_execution", "selector": {"request_step": 2},
        "operator": "SAME_AS", "field": "/session_id",
        "expected_ref": {"target": "harness_execution", "selector": {"request_step": 1}, "field": "/session_id"},
    })
    write(package, EXPECTED, expected)
    bundle = load_scenario(package, SID)
    assert bundle.driver.script.requests[1].user_request == "Near Napili instead"
    assert bundle.execution_readiness.outcome == "BLOCKED"


def test_missing_behavior_does_not_invent_environmental_dispatch(package):
    scenario = read(package, SCENARIO)
    del scenario["tool_behavior"]
    write(package, SCENARIO, scenario)
    assert load_scenario(package, SID).driver.script.operations == []


def test_explicit_scripted_gap_can_replace_undeclared_input_coverage(package):
    policy = read(package, "policies/unit.json")
    policy["evidence_rules"] = [r for r in policy["evidence_rules"] if r["category"] != "SURF_WAVE_CONDITIONS"]
    write(package, "policies/unit.json", policy)
    script = read(package, "behaviors/unit.json")
    script["operations"][0]["attempts"] = [{"attempt": 1, "behavior": "TIMEOUT", "simulated_duration_ms": 11000}]
    write(package, "behaviors/unit.json", script)
    assert load_scenario(package, SID).execution_readiness.outcome == "BLOCKED"


def test_finding_and_call_assertion_aliases_resolve_against_declared_operations(package):
    expected = read(package, EXPECTED)
    expected["assertions"].append({
        "assertion_id": "event-ref", "requirement_ids": ["IT-004"], "mandatory": True,
        "test_status": "ACTIVE", "target": "trace_event", "operator": "EXISTS", "selector": {
            "request_step": 1, "event_type": "TOOL_COMPLETED",
            "related_call_ref": {"operation_id": "unit-op", "attempt": 1},
            "related_finding_ref": {"source_fixture_id": "ocean-marine-forecast",
                "template_finding_id": "SYNTHETIC_OCEAN_MARINE_FORECAST", "operation_id": "unit-op", "attempt": 1},
        },
    })
    write(package, EXPECTED, expected)
    assert load_scenario(package, SID)
    expected["assertions"][-1]["selector"]["related_call_ref"]["attempt"] = 2
    write(package, EXPECTED, expected)
    with pytest.raises(FixtureLoadError, match="binding is unresolved"):
        load_scenario(package, SID)


@pytest.mark.parametrize("kind", ["source", "call", "finding", "domain"])
def test_source_template_identity_integrity(package, kind):
    path = "sources/weather/weather-partial.json"
    response = read(package, path)
    if kind == "source":
        response["source_id"] = "NWS_ALERTS"
        response["findings"][0]["source_id"] = "NWS_ALERTS"
    elif kind == "call":
        response["tool_call_id"] = read(package, "sources/weather/weather-forecast.json")["tool_call_id"]
    elif kind == "finding":
        response["findings"][0]["finding_id"] = "SYNTHETIC_WEATHER_FORECAST"
    else:
        response["findings"][0]["agent_type"] = "OCEAN"
    write(package, path, response)
    with pytest.raises(FixtureLoadError):
        load_scenario(package, SID)


def test_offshore_context_cannot_be_relabelled_as_beach_evidence(package):
    policy = read(package, "policies/unit.json")
    policy["evidence_rules"][1].update(source_fixture_id="ocean-offshore-observation",
        finding_id="SYNTHETIC_OFFSHORE_OBSERVATION", temporal_rule="COVERS_TARGET_WINDOW")
    write(package, "policies/unit.json", policy)
    with pytest.raises(FixtureLoadError, match="Offshore/context"):
        load_scenario(package, SID)


def test_tool_error_inner_shape_and_status_are_checked(package):
    path = "sources/ocean/ocean-marine-forecast.json"
    response = read(package, path)
    response["retrieval_status"] = "ERROR"
    response["errors"] = [{"error_id": "unit-error", "error_code": "SOURCE_TIMEOUT",
        "message": "Synthetic failure", "retryable": True, "source_id": response["source_id"],
        "tool_call_id": response["tool_call_id"]}]
    write(package, path, response)
    script = read(package, "behaviors/unit.json")
    script["operations"][0]["attempts"][0]["behavior"] = "ERROR"
    write(package, "behaviors/unit.json", script)
    assert load_scenario(package, SID)
    response["errors"][0]["retryable"] = "yes"
    write(package, path, response)
    with pytest.raises(FixtureLoadError, match="tool error structure"):
        load_scenario(package, SID)


def test_expected_file_traversal_and_unrelated_scenario_import_are_rejected(package):
    scenario = read(package, SCENARIO)
    scenario["expected_results"]["path"] = "scenarios/other/expected.json"
    write(package, SCENARIO, scenario)
    with pytest.raises(FixtureLoadError, match="belong to this scenario"):
        load_scenario(package, SID)


def test_unregistered_scenario_and_manifest_reference_duplicates_are_rejected(package):
    with pytest.raises(FixtureLoadError, match="not registered"):
        load_scenario(package, "OTHER")
    manifest = read(package, "manifest.json")
    manifest["scenarios"].append(deepcopy(manifest["scenarios"][0]))
    write(package, "manifest.json", manifest)
    with pytest.raises(FixtureLoadError, match="HarnessManifest"):
        load_scenario(package, SID)


def test_unknown_nested_values_do_not_echo_provider_content(package):
    response = read(package, "sources/weather/weather-forecast.json")
    response["private_instruction"] = "SYNTHETIC_CANARY_DO_NOT_LOG"
    write(package, "sources/weather/weather-forecast.json", response)
    with pytest.raises(FixtureLoadError) as failure:
        load_scenario(package, SID)
    assert "SYNTHETIC_CANARY_DO_NOT_LOG" not in str(failure.value)
