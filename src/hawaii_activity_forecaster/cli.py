"""Application information CLI for the M1.1-A bootstrap."""

import argparse
from collections.abc import Sequence

from . import __version__


def main(argv: Sequence[str] | None = None) -> int:
    """Display application information without starting an investigation."""
    parser = argparse.ArgumentParser(
        prog="hafi",
        description="Hawaii Activity Forecaster — CMU Agentic AI Systems capstone",
    )
    parser.add_argument(
        "--version", "-V", action="version",
        version=f"hawaii-activity-forecaster {__version__}",
    )
    parser.parse_args(argv)
    print(f"Hawaii Activity Forecaster {__version__}")
    print("M1.1-A project bootstrap. Environmental recommendations are not available.")
    return 0
