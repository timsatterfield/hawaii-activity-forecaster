"""Local tracing configuration, inspection and safe CLI errors."""

import json

import pytest

from hawaii_activity_forecaster import cli
from trace_samples import FIXTURES, output, records, rewrite


@pytest.mark.parametrize("case,files", [("advisory", 1), ("outage", 1), ("session", 2)])
def test_demos_use_explicit_local_directory_and_existing_rendering(case, files, tmp_path, capsys):
    directory = tmp_path / "local-events"
    assert cli.main(["demo", case, "--fixtures", str(FIXTURES), "--trace-directory", str(directory)]) == 0
    captured = capsys.readouterr()
    assert captured.err == "" and "SYNTHETIC TEST OUTPUT" in captured.out
    assert len(list(directory.glob("*.jsonl"))) == files
    for path in directory.glob("*.jsonl"):
        assert cli.main(["trace", str(path)]) == 0
        checked = capsys.readouterr()
        value = json.loads(checked.out)
        assert value["complete"] is True and value["metrics"]["tool_calls"] in {6, 8}
        assert value["metrics"]["model_calls"] == 0


@pytest.mark.parametrize("choice", ["toml", "environment", "command-line"])
def test_trace_directory_configuration_precedence(choice, tmp_path, monkeypatch, capsys):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config = config_dir / "app.toml"
    config.write_text('[trace]\ndirectory = "toml-events"\n')
    environment_dir, cli_dir = tmp_path / "environment-events", tmp_path / "cli-events"
    if choice != "toml":
        monkeypatch.setenv("HAF_TRACE_DIRECTORY", str(environment_dir))
    arguments = ["demo", "advisory", "--fixtures", str(FIXTURES), "--config", str(config)]
    if choice == "command-line":
        arguments += ["--trace-directory", str(cli_dir)]
    assert cli.main(arguments) == 0, capsys.readouterr().err
    chosen = config_dir / "toml-events" if choice == "toml" else environment_dir if choice == "environment" else cli_dir
    assert len(list(chosen.glob("*.jsonl"))) == 1
    for other in [config_dir / "toml-events", environment_dir, cli_dir]:
        assert other == chosen or not other.exists()


def test_invalid_configuration_and_unusable_destination_are_sanitized(tmp_path, capsys):
    config = tmp_path / "private-config.toml"
    config.write_text('private_api_key = "EXAMPLE_CREDENTIAL"\n')
    assert cli.main(["demo", "advisory", "--fixtures", str(FIXTURES), "--config", str(config)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "Cannot load a valid application configuration.\n"
    path = tmp_path / "private-destination"
    path.write_text("existing file")
    assert cli.main(["demo", "advisory", "--fixtures", str(FIXTURES), "--trace-directory", str(path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("Technical error:")
    assert all(value not in captured.err for value in ["private-destination", "EXAMPLE_CREDENTIAL", "Traceback", "No recommendation"])


@pytest.mark.parametrize("damage", ["partial", "invalid", "missing"])
def test_trace_inspection_does_not_report_incomplete_or_invalid_files_as_complete(damage, tmp_path, capsys):
    path = output(tmp_path).report.trace_path
    if damage == "partial":
        rewrite(path, records(path)[:3])
    elif damage == "invalid":
        path.write_text('{"api_key":"EXAMPLE_CREDENTIAL"}\n')
    else:
        path.unlink()
    assert cli.main(["trace", str(path)]) == 1
    captured = capsys.readouterr()
    if damage == "partial":
        assert json.loads(captured.out)["complete"] is False and captured.err == ""
    else:
        assert captured.out == "" and captured.err.startswith("Trace validation failed:")
        assert "EXAMPLE_CREDENTIAL" not in captured.err and str(path) not in captured.err
