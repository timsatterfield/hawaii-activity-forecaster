"""Installed CLI demos, preflight, sanitized failures and no partial rendering."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from hawaii_activity_forecaster import cli
from hawaii_activity_forecaster.demo import DemoUnavailable, run_demo
from hawaii_activity_forecaster.harness import LoadedScenario, load_scenario

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/scenario-pack-v1"


@pytest.mark.parametrize("command", [
    [sys.executable, "-m", "hawaii_activity_forecaster"], [str(Path(sys.executable).parent / "hafi")],
])
@pytest.mark.parametrize("case", ["advisory", "outage"])
def test_installed_demos_work_outside_repository(command, case, tmp_path):
    result = subprocess.run([*command, "demo", case, "--fixtures", str(FIXTURES)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "Component demonstration only; full scenario acceptance is not enabled." in result.stdout
    assert "SYNTHETIC TEST OUTPUT" in result.stdout and "Activity: Snorkeling" in result.stdout
    if case == "advisory":
        assert "- Fictional Test Beach B (SYNTHETIC)" in result.stdout
        assert "National Weather Service marine/surf" in result.stdout
        assert "https://example.invalid/" in result.stdout
    else:
        assert "No recommendation\n" in result.stdout and "Technical error" not in result.stdout


@pytest.mark.parametrize("arguments", [
    ["demo"], ["demo", "advisory"], ["demo", "real-beach", "--fixtures", str(FIXTURES)],
    ["snorkel tomorrow"], ["demo", "advisory", "--fixtures", str(FIXTURES), "--unblock"],
])
def test_usage_errors_do_not_start_work(arguments, capsys, monkeypatch):
    import hawaii_activity_forecaster.demo as demo
    async def forbidden(*args, **kwargs):
        pytest.fail("Invalid CLI usage dispatched an investigation")
    monkeypatch.setattr(demo, "run_demo", forbidden)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "usage:" in captured.err


def test_missing_fixture_package_is_a_sanitized_preflight_error(tmp_path, capsys):
    assert cli.main(["demo", "advisory", "--fixtures", str(tmp_path / "private-location")]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "Cannot load the synthetic fixture package" in captured.err
    assert "private-location" not in captured.err and "Traceback" not in captured.err


@pytest.mark.parametrize("status", ["BLOCKED", "DISABLED"])
def test_nonactive_definitions_do_not_execute(status, tmp_path, monkeypatch, capsys):
    import hawaii_activity_forecaster.demo as demo
    root = tmp_path / "pack"
    shutil.copytree(FIXTURES, root)
    manifest = json.loads((root / "manifest.json").read_text())
    registration = next(s for s in manifest["scenarios"] if s["scenario_id"] == "SC-004")
    scenario_path = root / registration["path"]
    definition = json.loads(scenario_path.read_text())
    definition["test_status"] = status
    scenario_path.write_text(json.dumps(definition))
    async def forbidden(*args, **kwargs):
        pytest.fail("A blocked/disabled definition executed")
    monkeypatch.setattr(demo, "run_synthetic_tool_graph", forbidden)
    assert cli.main(["demo", "advisory", "--fixtures", str(root)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and status in captured.err and "not executed" in captured.err


def test_demo_uses_component_projections_without_changing_acceptance_readiness(monkeypatch):
    def no_oracle(self):
        pytest.fail("The demo read independent evaluator expectations")
    monkeypatch.setattr(LoadedScenario, "evaluator", property(no_oracle))
    events = []
    output = asyncio.run(run_demo("advisory", FIXTURES, record_event=events.append))
    assert output.report.result.outcome == "RECOMMENDATIONS"
    assert output.report.budgets.model_calls == 0 and output.report.budgets.tool_calls == 6
    assert events[-1].event_type == "INVESTIGATION_COMPLETED"
    assert load_scenario(FIXTURES, "SC-004").execution_readiness.outcome == "BLOCKED"
    with pytest.raises(DemoUnavailable):
        asyncio.run(run_demo("unregistered", FIXTURES))


@pytest.mark.parametrize("failure", ["exception", "missing-result", "mutated-result", "trace-failed"])
def test_operational_or_validation_failures_emit_no_partial_recommendations(failure, monkeypatch, capsys):
    import hawaii_activity_forecaster.demo as demo
    output = asyncio.run(run_demo("advisory", FIXTURES))
    if failure == "missing-result":
        output = replace(output, report=replace(output.report, result=None))
    elif failure == "mutated-result":
        output.report.result.recommendations[0].source_references.append("SECRET invented source")
    elif failure == "trace-failed":
        output = replace(output, report=replace(output.report, trace_writable=False))
    async def substitute(*args, **kwargs):
        if failure == "exception":
            raise RuntimeError("SECRET token and stack trace")
        return output
    monkeypatch.setattr(demo, "run_demo", substitute)
    assert cli.main(["demo", "advisory", "--fixtures", str(FIXTURES)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("Technical error:")
    assert "SECRET" not in captured.err and "Fictional Test Beach B" not in captured.err
    assert "Traceback" not in captured.err and "No recommendation\n" not in captured.err


def test_validated_error_has_distinct_exit_status_and_sanitized_stderr(monkeypatch, capsys):
    import hawaii_activity_forecaster.orchestration.skeleton as graph
    def fail(context):
        raise RuntimeError("SECRET application failure")
    monkeypatch.setattr(graph, "compare_candidates", fail)
    assert cli.main(["demo", "advisory", "--fixtures", str(FIXTURES)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "Technical error\n" in captured.err
    assert "An application execution error prevented a validated result." in captured.err
    assert "SYNTHETIC TEST OUTPUT" in captured.err and "SECRET" not in captured.err
    assert "No recommendation\n" not in captured.err
