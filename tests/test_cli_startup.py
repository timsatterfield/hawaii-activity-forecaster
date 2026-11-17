"""Smoke checks for the installed package and bootstrap CLI."""

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

import hawaii_activity_forecaster


def test_package_import() -> None:
    assert hawaii_activity_forecaster.__version__ == version("hawaii-activity-forecaster")


@pytest.mark.parametrize(
    "command",
    [
        [sys.executable, "-m", "hawaii_activity_forecaster"],
        [str(Path(sys.executable).parent / "hafi")],
    ],
)
@pytest.mark.parametrize("arguments", [[], ["--version"], ["--help"]])
def test_cli_startup(command: list[str], arguments: list[str], tmp_path: Path) -> None:
    # Verify installation and the console entry point outside the repository.
    result = subprocess.run(
        [*command, *arguments], cwd=tmp_path,
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    if arguments == ["--help"]:
        assert "usage:" in result.stdout
    else:
        assert hawaii_activity_forecaster.__version__ in result.stdout
    if not arguments:
        assert "Environmental recommendations are not available." in result.stdout


def test_cli_rejects_investigation_request(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "hawaii_activity_forecaster", "snorkel tomorrow"],
        cwd=tmp_path, capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
    assert result.stdout == ""
