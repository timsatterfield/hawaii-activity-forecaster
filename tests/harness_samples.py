"""Temporary contract-only v2 packages, not authored SC-001..012 scenarios."""

import json
from pathlib import Path
import shutil

V1 = Path(__file__).resolve().parents[1] / "fixtures"
WINDOW = {"start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"}
NOW = "2026-11-16T09:00:00-10:00"
SID = "HARNESS-CONTRACT-UNIT"
SCENARIO = f"scenarios/{SID}/scenario.json"
EXPECTED = f"scenarios/{SID}/expected.json"


def read(root, path):
    return json.loads((root / path).read_text())


def write(root, path, value):
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value, indent=2) + "\n")


def assertion(**updates):
    base = {
        "assertion_id": "CONTRACT-A1", "requirement_ids": ["SH-T02", "SH-T14"], "mandatory": True,
        "test_status": "ACTIVE", "target": "candidate_assessment", "selector": {"request_step": 1, "beach_id": "TEST_BEACH_A"},
        "operator": "EQUALS", "field": "/eligibility", "expected": "EXCLUDED",
    }
    base.update(updates)
    return base


def make_package(tmp_path):
    root = tmp_path / "v2"
    shutil.copytree(V1, root)
    manifest = read(root, "manifest.json")
    manifest.update(fixture_format_version="2.0.0", fixture_package_version="1.4.0",
                    harness_contract_version="1.0.0", scenarios=[{"scenario_id": SID, "path": SCENARIO}])
    write(root, "manifest.json", manifest)
    for domain in ("WEATHER", "OCEAN"):
        write(root, f"source_sets/{domain.lower()}.json", {
            "harness_contract_version": "1.0.0", "agent_type": domain,
            "source_fixture_ids": [s["fixture_id"] for s in manifest["source_fixtures"] if s["agent_type"] == domain],
        })
    scenario = {
        "scenario_id": SID, "description": "Synthetic loader contract test, not an executable acceptance scenario",
        "requirement_ids": ["SH-T02", "SH-T14"], "user_request": "Synthetic snorkeling request",
        "reference_time": NOW, "catalog_fixture": manifest["catalog_fixture"],
        "weather_fixture": "source_sets/weather.json", "ocean_fixture": "source_sets/ocean.json",
        "tool_behavior": {"script": "behaviors/unit.json"}, "policy_configuration": "policies/unit.json",
        "expected_results": {"path": EXPECTED}, "test_status": "ACTIVE",
    }
    write(root, SCENARIO, scenario)
    bindings = [
        ("OFFICIAL_ADVISORIES", "ocean-marine-forecast", "SYNTHETIC_OCEAN_MARINE_FORECAST", "COVERS_TARGET_WINDOW"),
        ("SURF_WAVE_CONDITIONS", "ocean-marine-forecast", "SYNTHETIC_OCEAN_MARINE_FORECAST", "COVERS_TARGET_WINDOW"),
        ("WIND_CONDITIONS", "weather-forecast", "SYNTHETIC_WEATHER_FORECAST", "COVERS_TARGET_WINDOW"),
        ("CURRENTS_PERSISTENT_HAZARDS", "ocean-marine-forecast", "SYNTHETIC_OCEAN_MARINE_FORECAST", "COVERS_TARGET_WINDOW"),
        ("WATER_QUALITY_ADVISORY_CHECK", "ocean-advisory", "SYNTHETIC_OCEAN_ADVISORY", "COVERS_TARGET_WINDOW"),
        ("UNDERWATER_VISIBILITY", "ocean-old-report", "SYNTHETIC_OLD_REPORT", "DECLARED_REPORT_WINDOW"),
    ]
    policy = {
        "harness_contract_version": "1.0.0", "policy_version": "0.2",
        "policy_configuration_version": "synthetic-policy-1.0.0", "synthetic": True,
        "evidence_profiles": [{"activity": "SNORKELING", "mandatory": ["OFFICIAL_ADVISORIES", "SURF_WAVE_CONDITIONS",
            "CURRENTS_PERSISTENT_HAZARDS", "WATER_QUALITY_ADVISORY_CHECK", "VERIFIED_BEACH_CHARACTERISTICS"],
            "relevant": ["WIND_CONDITIONS"], "optional": ["UNDERWATER_VISIBILITY"]}],
        "evidence_rules": [{"rule_id": f"rule-{i}", "category": category, "source_fixture_id": source,
            "finding_id": finding, "temporal_rule": temporal, "beach_ids": ["TEST_BEACH_A"]}
            for i, (category, source, finding, temporal) in enumerate(bindings)],
        "premises": [{"premise_id": "unit-premise", "beach_id": "TEST_BEACH_A", "activity": "SNORKELING",
            "time_window": WINDOW, "fact_type": "ACTIVITY_SUPPORTING_CONDITIONS_PRESENT", "value": True,
            "finding_refs": [{"source_fixture_id": "ocean-marine-forecast", "finding_id": "SYNTHETIC_OCEAN_MARINE_FORECAST"}],
            "catalog_field_refs": [], "rationale": "Synthetic premise for structure validation only."}],
        "mixed_permissions": [],
    }
    write(root, "policies/unit.json", policy)
    write(root, "behaviors/unit.json", {
        "harness_contract_version": "1.0.0",
        "requests": [{"request_step": 1, "user_request": scenario["user_request"], "reference_time": NOW}],
        "operations": [{"operation_id": "unit-op", "request_step": 1, "agent_type": "OCEAN", "source_id": "NWS_MARINE",
            "candidate_beach_ids": ["TEST_BEACH_A"], "requested_evidence": ["SURF_WAVE_CONDITIONS"],
            "target_time_window": WINDOW, "geographic_scope": {"zone": "SYNTHETIC_REGION"},
            "attempts": [{"attempt": 1, "behavior": "SUCCESS", "simulated_duration_ms": 1,
                          "response_fixture_id": "ocean-marine-forecast"}]}],
    })
    write(root, EXPECTED, {"harness_contract_version": "1.0.0", "scenario_id": SID, "assertions": [assertion()]})
    return root
