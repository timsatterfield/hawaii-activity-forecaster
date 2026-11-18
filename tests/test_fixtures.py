"""Independent structural checks for synthetic inputs (FX-001..010, design §18).

These are loader tests, not execution of SC-001 through SC-012.
"""

from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from hawaii_activity_forecaster.fixtures import (
    FixtureLoadError, UnsupportedFixtureVersionError, load_fixture_inputs,
)
from hawaii_activity_forecaster.fixtures import loading

PACKAGE = Path(__file__).resolve().parents[1] / "fixtures"
CATALOG = "catalogs/synthetic-maui-v1.json"
WEATHER = "sources/weather/weather-forecast.json"
PARTIAL = "sources/weather/weather-partial.json"
OCEAN = "sources/ocean/ocean-marine-forecast.json"


@pytest.fixture
def package(tmp_path):
    return Path(shutil.copytree(PACKAGE, tmp_path / "fixtures"))


def read(root, path):
    return json.loads((root / path).read_text())


def write(root, path, data):
    (root / path).write_text(json.dumps(data) + "\n")


def test_catalog_matches_five_approved_fictional_beaches():
    inputs = load_fixture_inputs(PACKAGE)
    # Independent inventory from acceptance specification §16.1, not generated from code.
    expected = {
        "TEST_BEACH_A": ("SOUTH_MAUI", "Kihei", {"SWIMMING", "SNORKELING"}),
        "TEST_BEACH_B": ("SOUTH_MAUI", "Wailea", {"SWIMMING", "SNORKELING", "SUP"}),
        "TEST_BEACH_C": ("WEST_MAUI", "Napili", {"SWIMMING", "SNORKELING"}),
        "TEST_BEACH_D": ("WEST_MAUI", "Kaanapali", {"SWIMMING", "SNORKELING", "SUP"}),
        "TEST_BEACH_E": ("SOUTH_MAUI", "Makena", {"SWIMMING"}),
    }
    assert {b.beach_id: (b.region, b.locality, set(b.supported_activities)) for b in inputs.catalog.root} == expected
    for beach in inputs.catalog.root:
        assert "SYNTHETIC" in beach.name
        assert "SYNTHETIC" in beach.location_notes
        assert beach.catalog_status == "VERIFIED"
        assert beach.lifeguard_status == "UNKNOWN"
        assert beach.sources
        for source in beach.sources:
            assert source.publisher == "Hawaii Activity Forecaster synthetic fixture authors"
            assert source.url.startswith("https://example.invalid/")
            assert {"latitude", "longitude", "supported_activities"} <= set(source.supports_fields)
    assert "difficult entry" in inputs.catalog.root[4].access_notes


def test_version_metadata_and_fixed_clock_are_preserved():
    inputs = load_fixture_inputs(PACKAGE)
    assert inputs.manifest.fixture_format_version == "1.0.0"
    assert inputs.manifest.fixture_package_version == "1.0.0"
    assert inputs.manifest.schema_version == "0.1"
    assert inputs.manifest.policy_version == "0.2"
    assert inputs.manifest.synthetic is True
    assert inputs.manifest.reference_time.isoformat() == "2026-11-16T09:00:00-10:00"
    assert inputs.manifest.target_time_window.start.isoformat() == "2026-11-17T08:00:00-10:00"
    assert inputs.manifest.target_time_window.end.isoformat() == "2026-11-17T11:00:00-10:00"
    assert all(r.retrieved_at == inputs.manifest.reference_time for r in inputs.source_responses.values())


def test_source_inventory_and_statuses_are_explicit():
    inputs = load_fixture_inputs(PACKAGE)
    assert {key: response.retrieval_status for key, response in inputs.source_responses.items()} == {
        "weather-forecast": "SUCCESS", "weather-partial": "PARTIAL", "weather-unavailable": "UNAVAILABLE",
        "ocean-marine-forecast": "SUCCESS", "ocean-advisory": "SUCCESS",
        "ocean-advisory-unavailable": "UNAVAILABLE", "ocean-offshore-observation": "SUCCESS",
        "ocean-old-report": "SUCCESS",
    }
    for response in inputs.source_responses.values():
        assert response.source_reference.startswith("https://example.invalid/")
        for finding in response.findings:
            assert finding.validation_status == "PENDING"
            assert finding.investigation_id == "SYNTHETIC_INPUT_EXAMPLES_V1"
            assert finding.source_reference.startswith("https://example.invalid/")


def test_missing_evidence_is_not_an_absent_advisory_assertion():
    inputs = load_fixture_inputs(PACKAGE)
    unavailable = inputs.source_responses["ocean-advisory-unavailable"]
    assert unavailable.findings == []
    assert unavailable.missing_evidence == ["water_quality_advisory_check"]
    advisory = inputs.source_responses["ocean-advisory"].findings[0]
    assert advisory.beach_id == "TEST_BEACH_A"
    assert advisory.advisories[0].advisory_id == "SYNTHETIC_ADVISORY_A"
    assert advisory.advisories[0].advisory_type == "Synthetic water-contact avoidance advisory"
    assert advisory.validation_status == "PENDING"


def test_measurements_preserve_surf_swell_values_and_geographic_scope():
    inputs = load_fixture_inputs(PACKAGE)
    marine = inputs.source_responses["ocean-marine-forecast"].findings[0]
    surf, swell = marine.measurements
    assert surf.measurement_type == "SURF_HEIGHT"
    assert (surf.value.min, surf.value.max, surf.unit, surf.measurement_convention) == (1, 2, "ft", "FACE")
    assert (swell.measurement_type, swell.value, swell.unit) == ("SWELL_HEIGHT", 3, "ft")
    offshore = inputs.source_responses["ocean-offshore-observation"].findings[0]
    assert offshore.coverage_type == "OFFSHORE"
    assert offshore.beach_id is None
    assert offshore.measurements[0].measurement_type == "SWELL_HEIGHT"
    assert offshore.observed_at.isoformat() == "2026-11-16T08:00:00-10:00"


def test_old_report_is_loaded_without_being_promoted_to_accepted_evidence():
    inputs = load_fixture_inputs(PACKAGE)
    old = inputs.source_responses["ocean-old-report"].findings[0]
    assert old.retrieved_at > old.issued_at
    assert old.valid_until < inputs.manifest.target_time_window.start
    assert old.validation_status == "PENDING"
    assert old.finding_type == "REPORT"
    assert old.descriptive_findings == ["SYNTHETIC qualitative visibility report for a prior date."]


def test_partial_response_preserves_available_findings_and_missing_fields():
    response = load_fixture_inputs(PACKAGE).source_responses["weather-partial"]
    assert response.missing_evidence == ["wind_direction"]
    assert response.findings[0].missing_fields == ["wind_direction"]
    assert response.findings[0].retrieval_status == "PARTIAL"
    assert response.findings[0].validation_status == "PENDING"


def test_loader_is_deterministic_without_environment_or_clock_defaults(monkeypatch, tmp_path):
    first = load_fixture_inputs(PACKAGE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TZ", "UTC")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    second = load_fixture_inputs(PACKAGE)
    assert first == second
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("field", ["fixture_format_version", "fixture_package_version", "schema_version", "policy_version"])
def test_unsupported_versions_fail_before_catalog_reads(package, field, monkeypatch):
    manifest = read(package, "manifest.json")
    manifest[field] = "future-version"
    write(package, "manifest.json", manifest)
    original = loading._read_json
    reads = []

    def tracked(path):
        reads.append(path)
        return original(path)

    monkeypatch.setattr(loading, "_read_json", tracked)
    with pytest.raises(UnsupportedFixtureVersionError, match=field):
        load_fixture_inputs(package)
    assert reads == [package / "manifest.json"]


@pytest.mark.parametrize("field", ["synthetic", "reference_time", "target_time_window", "catalog_fixture", "source_fixtures"])
def test_required_manifest_fields_cannot_be_omitted(package, field):
    manifest = read(package, "manifest.json")
    del manifest[field]
    write(package, "manifest.json", manifest)
    with pytest.raises(FixtureLoadError, match="manifest schema"):
        load_fixture_inputs(package)


@pytest.mark.parametrize("synthetic", [False, 1, "true", None])
def test_package_must_be_explicitly_synthetic(package, synthetic):
    manifest = read(package, "manifest.json")
    manifest["synthetic"] = synthetic
    write(package, "manifest.json", manifest)
    with pytest.raises(FixtureLoadError, match="manifest schema"):
        load_fixture_inputs(package)


@pytest.mark.parametrize("contents", ["[", '{"synthetic":true,"synthetic":false}',
                                      '{"data":NaN}', '{"data":Infinity}', '{"data":-Infinity}', '{"data":1e999}'])
def test_malformed_or_ambiguous_json_is_rejected(package, contents):
    (package / "manifest.json").write_text(contents)
    with pytest.raises(FixtureLoadError, match="Invalid fixture JSON"):
        load_fixture_inputs(package)


def test_non_utf8_fixture_is_rejected(package):
    (package / WEATHER).write_bytes(b'\xff')
    with pytest.raises(FixtureLoadError, match="Invalid fixture JSON"):
        load_fixture_inputs(package)


@pytest.mark.parametrize("path", ["manifest.json", CATALOG, WEATHER])
def test_missing_files_are_fixture_errors(package, path):
    (package / path).unlink()
    with pytest.raises(FixtureLoadError, match="Cannot read"):
        load_fixture_inputs(package)


def test_unreadable_input_is_a_fixture_error(package, monkeypatch):
    original = Path.read_text

    def unreadable(path, *args, **kwargs):
        if path.name == "synthetic-maui-v1.json":
            raise PermissionError("Synthetic permission failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable)
    with pytest.raises(FixtureLoadError, match="Cannot read"):
        load_fixture_inputs(package)


@pytest.mark.parametrize("reference", ["../outside.json", "/tmp/outside.json", "catalogs/../../outside.json",
    "catalogs\\outside.json", "https://example.invalid/catalog.json", "catalogs/file.txt", "expected.json",
    "catalogs-sibling/catalog.json", "catalogs/\x00bad.json"])
def test_catalog_references_are_confined_to_catalog_input_area(package, reference):
    manifest = read(package, "manifest.json")
    manifest["catalog_fixture"] = reference
    write(package, "manifest.json", manifest)
    with pytest.raises(FixtureLoadError):
        load_fixture_inputs(package)


def test_source_reference_cannot_read_expected_assertions(package):
    manifest = read(package, "manifest.json")
    manifest["source_fixtures"][0]["path"] = "scenarios/sc-001/expected.json"
    write(package, "manifest.json", manifest)
    with pytest.raises(FixtureLoadError, match="input area"):
        load_fixture_inputs(package)


@pytest.mark.parametrize("external", [False, True])
def test_symlinks_cannot_escape_input_area(package, tmp_path, external):
    target = (tmp_path if external else package) / "expected.json"
    target.write_text((package / CATALOG).read_text())
    (package / CATALOG).unlink()
    (package / CATALOG).symlink_to(target)
    with pytest.raises(FixtureLoadError, match="input area"):
        load_fixture_inputs(package)


def test_duplicate_catalog_ids_fail_preflight(package):
    catalog = read(package, CATALOG)
    catalog.append(deepcopy(catalog[0]))
    write(package, CATALOG, catalog)
    with pytest.raises(FixtureLoadError, match="catalog schema"):
        load_fixture_inputs(package)


@pytest.mark.parametrize("updates", [{"region": "EAST_MAUI"}, {"latitude": 91},
                                      {"supported_activities": ["SURFING"]}])
def test_invalid_catalog_attributes_fail_preflight(package, updates):
    catalog = read(package, CATALOG)
    catalog[0].update(updates)
    write(package, CATALOG, catalog)
    with pytest.raises(FixtureLoadError, match="catalog schema"):
        load_fixture_inputs(package)


def test_catalog_review_status_is_preserved_not_silently_filtered(package):
    catalog = read(package, CATALOG)
    catalog[0]["catalog_status"] = "NEEDS_REVIEW"
    write(package, CATALOG, catalog)
    assert load_fixture_inputs(package).catalog.root[0].catalog_status == "NEEDS_REVIEW"


@pytest.mark.parametrize("field", ["fixture_id", "path"])
def test_duplicate_manifest_references_are_rejected(package, field):
    manifest = read(package, "manifest.json")
    manifest["source_fixtures"][1][field] = manifest["source_fixtures"][0][field]
    write(package, "manifest.json", manifest)
    with pytest.raises(FixtureLoadError, match="manifest schema"):
        load_fixture_inputs(package)


def test_manifest_rejects_an_unauthorized_specialist_source_pair(package):
    manifest = read(package, "manifest.json")
    manifest["source_fixtures"][0]["source_id"] = "NWS_MARINE"
    write(package, "manifest.json", manifest)
    with pytest.raises(FixtureLoadError, match="unauthorized specialist/source pairing"):
        load_fixture_inputs(package)


def test_source_response_must_match_manifest_provider(package):
    manifest = read(package, "manifest.json")
    manifest["source_fixtures"][0]["source_id"] = "NWS_ALERTS"
    write(package, "manifest.json", manifest)
    with pytest.raises(FixtureLoadError, match="match the manifest source"):
        load_fixture_inputs(package)


def test_source_finding_must_match_specialist_domain(package):
    response = read(package, WEATHER)
    response["findings"][0]["agent_type"] = "OCEAN"
    write(package, WEATHER, response)
    with pytest.raises(FixtureLoadError, match="specialist domain"):
        load_fixture_inputs(package)


def test_unknown_beach_references_are_rejected(package):
    response = read(package, OCEAN)
    response["findings"][0]["beach_id"] = "UNKNOWN_BEACH"
    write(package, OCEAN, response)
    with pytest.raises(FixtureLoadError, match="absent from the fixture catalog"):
        load_fixture_inputs(package)


@pytest.mark.parametrize("duplicate", ["tool_call_id", "finding_id"])
def test_duplicate_ids_across_files_are_rejected(package, duplicate):
    first = read(package, WEATHER)
    second = read(package, PARTIAL)
    if duplicate == "tool_call_id":
        second["tool_call_id"] = first["tool_call_id"]
    else:
        second["findings"][0]["finding_id"] = first["findings"][0]["finding_id"]
    write(package, PARTIAL, second)
    with pytest.raises(FixtureLoadError, match="Duplicate"):
        load_fixture_inputs(package)


@pytest.mark.parametrize("mutation", ["missing_retrieved_at", "naive_timestamp", "reversed_range", "extra_recommendations"])
def test_malformed_source_contracts_fail_fixture_preflight(package, mutation):
    response = read(package, WEATHER)
    if mutation == "missing_retrieved_at":
        del response["retrieved_at"]
    elif mutation == "naive_timestamp":
        response["findings"][0]["retrieved_at"] = "2026-11-16T09:00:00"
    elif mutation == "reversed_range":
        response["findings"][0]["valid_until"] = "2026-11-15T09:00:00Z"
    else:
        response["recommendations"] = ["TEST_BEACH_A"]
    write(package, WEATHER, response)
    with pytest.raises(FixtureLoadError, match="source response schema"):
        load_fixture_inputs(package)


def test_expected_results_and_undeclared_files_are_never_discovered(package, monkeypatch):
    expected = package / "scenarios" / "sc-001" / "expected.json"
    expected.parent.mkdir(parents=True)
    expected.write_text("INTENTIONALLY INVALID; evaluator-only content")
    (package / "policies").mkdir()
    (package / "policies" / "unsupported.json").write_text("INTENTIONALLY INVALID")
    original = loading._read_json
    reads = []

    def track(path):
        reads.append(path)
        return original(path)

    monkeypatch.setattr(loading, "_read_json", track)
    inputs = load_fixture_inputs(package)
    assert expected not in reads
    assert len(reads) == 10  # manifest + catalog + eight declared responses
    assert len(inputs.source_responses) == 8


def test_expected_results_cannot_be_added_to_application_input_manifest(package):
    manifest = read(package, "manifest.json")
    manifest["expected_results"] = {"recommend": "TEST_BEACH_A"}
    write(package, "manifest.json", manifest)
    with pytest.raises(FixtureLoadError, match="manifest schema"):
        load_fixture_inputs(package)


def test_deeply_nested_nonmanifest_json_is_reported_as_fixture_error(package):
    (package / "manifest.json").write_text("[" * 2000 + "]" * 2000)
    # Python versions differ in whether decoding or the manifest schema rejects it.
    with pytest.raises(FixtureLoadError, match="Invalid"):
        load_fixture_inputs(package)
