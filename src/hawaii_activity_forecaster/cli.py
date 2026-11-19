"""Application information and validated synthetic component demonstrations."""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__


def main(argv: Sequence[str] | None = None) -> int:
    """Display information or one explicitly requested fictional demonstration."""
    parser = argparse.ArgumentParser(
        prog="hafi",
        description="Hawaii Activity Forecaster — CMU Agentic AI Systems capstone",
    )
    parser.add_argument(
        "--version", "-V", action="version",
        version=f"hawaii-activity-forecaster {__version__}",
    )
    commands = parser.add_subparsers(dest="command")
    demo = commands.add_parser("demo", help="show a validated synthetic component example")
    demo.add_argument("case", choices=("advisory", "outage"), help="fixed fictional example")
    demo.add_argument("--fixtures", type=Path, required=True, metavar="PATH",
                      help="explicit path to the authored scenario-pack-v1 directory")
    arguments = parser.parse_args(argv)
    if arguments.command == "demo":
        from .demo import DemoUnavailable, run_demo
        from .fixtures import FixtureLoadError
        from .presentation import PresentationError, render_report

        try:
            output = asyncio.run(run_demo(arguments.case, arguments.fixtures))
            # Buffer the entire response before any result is written. Rejected
            # results never leak partial recommendations, claims or diagnostics.
            rendered = render_report(output.report, catalog=output.catalog, policy=output.policy)
        except DemoUnavailable as error:
            print(str(error), file=sys.stderr)
            return 2
        except FixtureLoadError:
            print("Cannot load the synthetic fixture package. Check --fixtures and its validated contents.", file=sys.stderr)
            return 2
        except PresentationError:
            print("Technical error: no validated result is available for presentation.", file=sys.stderr)
            return 1
        except Exception:
            print("Technical error: the synthetic demonstration could not be completed.", file=sys.stderr)
            return 1
        failed = output.report.result.outcome == "ERROR"
        print("Component demonstration only; full scenario acceptance is not enabled.\n" + rendered,
              end="", file=sys.stderr if failed else sys.stdout)
        return 1 if failed else 0
    print(f"Hawaii Activity Forecaster {__version__}")
    print("Environmental recommendations are not available.")
    print("Use 'hafi demo --help' for fictional component examples.")
    return 0
