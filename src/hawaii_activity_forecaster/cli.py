"""Application information and validated synthetic component demonstrations."""

import argparse
import asyncio
import sys
import json
from dataclasses import asdict
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
    demo.add_argument("case", choices=("advisory", "outage", "session"), help="fixed fictional example")
    demo.add_argument("--fixtures", type=Path, required=True, metavar="PATH",
                      help="explicit path to the authored scenario-pack-v1 directory")
    demo.add_argument("--config", type=Path, metavar="PATH", help="explicit local TOML configuration")
    demo.add_argument("--trace-directory", type=Path, metavar="PATH", help="override the local JSONL trace directory")
    trace = commands.add_parser("trace", help="validate an existing local JSONL trace and show metrics")
    trace.add_argument("path", type=Path, metavar="PATH")
    evaluation = commands.add_parser("evaluate", help="preflight a scenario and report independent evaluation readiness")
    evaluation.add_argument("scenario_id")
    evaluation.add_argument("--fixtures", type=Path, required=True, metavar="PATH")
    evaluation.add_argument("--component", action="store_true", help="execute an explicit authored synthetic runtime; full acceptance remains blocked")
    evaluation.add_argument("--trace-directory", type=Path, metavar="PATH")
    arguments = parser.parse_args(argv)
    if arguments.command == "evaluate":
        from .harness.evaluation import evaluate_scenario
        if arguments.component:
            from .harness.execution import execute_scenario
            from .demo import authored_component_runner
            from .config.settings import TraceSettings
            case = {"SC-004": "advisory", "SC-010": "outage"}.get(arguments.scenario_id)
            report = asyncio.run(execute_scenario(arguments.fixtures, arguments.scenario_id,
                runtime=authored_component_runner(case) if case else None,
                trace_settings=TraceSettings(directory=arguments.trace_directory) if arguments.trace_directory else None))
        else:
            if arguments.trace_directory is not None:
                parser.error("--trace-directory requires --component")
            report = evaluate_scenario(arguments.fixtures, arguments.scenario_id)
        print(json.dumps(asdict(report), indent=2))
        return 0 if report.outcome == "PASS" else 1 if report.outcome == "FAIL" else 2
    if arguments.command == "trace":
        from .observability import TraceValidationError, inspect_trace
        try:
            validation = inspect_trace(arguments.path)
        except TraceValidationError as error:
            print(f"Trace validation failed: {error}", file=sys.stderr)
            return 1
        print(json.dumps(asdict(validation), indent=2))
        return 0 if validation.complete else 1
    if arguments.command == "demo":
        from .demo import DemoUnavailable, run_demo, run_session_demo
        from .fixtures import FixtureLoadError
        from .orchestration import SessionError
        from .presentation import PresentationError, render_report
        from .config import ConfigurationError, load_config
        from .config.settings import TraceSettings

        try:
            config = load_config(arguments.config)
            settings = config.trace if arguments.trace_directory is None else TraceSettings(directory=arguments.trace_directory)
            if arguments.case == "session":
                outputs = asyncio.run(run_session_demo(arguments.fixtures, trace_settings=settings)).investigations
            else:
                outputs = (asyncio.run(run_demo(arguments.case, arguments.fixtures, trace_settings=settings)),)
            if not outputs:
                raise PresentationError("No validated result is available.")
            # Buffer the entire response before any result is written. Rejected
            # results never leak partial recommendations, claims or diagnostics.
            rendered_parts = []
            for output in outputs:
                rendered = render_report(output.report, catalog=output.catalog, policy=output.policy)
                if arguments.case == "session":
                    state = output.report.state
                    stage = "initial request" if state.request_revision == 1 else "post-terminal follow-up"
                    rendered = f"Request revision {state.request_revision} — {stage}\n{rendered}"
                rendered_parts.append(rendered)
            rendered = "\n".join(rendered_parts)
        except ConfigurationError:
            print("Cannot load a valid application configuration.", file=sys.stderr)
            return 2
        except DemoUnavailable as error:
            print(str(error), file=sys.stderr)
            return 2
        except FixtureLoadError:
            print("Cannot load the synthetic fixture package. Check --fixtures and its validated contents.", file=sys.stderr)
            return 2
        except PresentationError:
            print("Technical error: no validated result is available for presentation.", file=sys.stderr)
            return 1
        except SessionError:
            print("Technical error: the synthetic session could not be completed.", file=sys.stderr)
            return 1
        except Exception:
            print("Technical error: the synthetic demonstration could not be completed.", file=sys.stderr)
            return 1
        failed = any(output.report.result.outcome == "ERROR" for output in outputs)
        print("Component demonstration only; full scenario acceptance is not enabled.\n" + rendered,
              end="", file=sys.stderr if failed else sys.stdout)
        return 1 if failed else 0
    print(f"Hawaii Activity Forecaster {__version__}")
    print("Environmental recommendations are not available.")
    print("Use 'hafi demo --help' for fictional component examples.")
    return 0
