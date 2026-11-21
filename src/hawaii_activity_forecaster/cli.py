"""Application information, component demonstrations and opt-in agent execution."""

import argparse
import asyncio
import sys
import json
from dataclasses import asdict
from collections.abc import Sequence
from pathlib import Path

from . import __version__


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested command; model execution requires explicit opt-in."""
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
    reliability = commands.add_parser("reliability", help="summarize existing validated traces without model calls")
    reliability.add_argument("paths", type=Path, nargs="+", help="JSONL files or directories (recursive)")
    reliability.add_argument("--reports", type=Path, nargs="+", default=[], help="optional saved scenario JSON files or directories")
    reliability.add_argument("--format", choices=("markdown", "json"), default="markdown")
    run = commands.add_parser("run", help="model-driven natural-language investigation of synthetic fixture data")
    run.add_argument("request", nargs="?", help="natural-language request, or prompt interactively")
    run.add_argument("--fixtures", type=Path, required=True, metavar="PATH", help="explicit saturday-release fixture root")
    run.add_argument("--case", choices=("favorable", "advisory", "outage", "recovery"), default="favorable")
    run.add_argument("--config", type=Path, required=True, metavar="PATH")
    target = run.add_mutually_exclusive_group()
    target.add_argument("--live", action="store_true", help="execute the configured OpenAI target using local credentials")
    target.add_argument("--local", action="store_true", help="execute the configured local Ollama target without an API key")
    run.add_argument("--interactive", action="store_true", help="accept post-terminal follow-ups in this process")
    run.add_argument("--max-investigations", type=int, choices=range(1, 11), default=3, metavar="1..10")
    run.add_argument("--trace-directory", type=Path, metavar="PATH")
    evaluation = commands.add_parser("evaluate", help="preflight a scenario and report independent evaluation readiness")
    evaluation.add_argument("scenario_id")
    evaluation.add_argument("--fixtures", type=Path, required=True, metavar="PATH")
    runner = evaluation.add_mutually_exclusive_group()
    runner.add_argument("--component", action="store_true", help="execute an explicit authored synthetic runtime; full acceptance remains blocked")
    runner.add_argument("--agent", action="store_true", help="execute the model-driven agent runtime; requires --config and --live or --local")
    evaluation.add_argument("--config", type=Path, metavar="PATH", help="enabled synthetic-release configuration for --agent")
    agent_target = evaluation.add_mutually_exclusive_group()
    agent_target.add_argument("--live", action="store_true", help="with --agent: the configured OpenAI target (paid calls)")
    agent_target.add_argument("--local", action="store_true", help="with --agent: the configured local Ollama target")
    evaluation.add_argument("--trace-directory", type=Path, metavar="PATH")
    web = commands.add_parser("web", help="local loopback web interface over the same workflow (optional)")
    web.add_argument("--fixtures", type=Path, required=True, metavar="PATH",
                     help="authored scenario-pack-v1 directory for the demonstrations")
    web.add_argument("--release-fixtures", type=Path, metavar="PATH",
                     help="saturday-release fixture root; required with --live or --local")
    web.add_argument("--config", type=Path, metavar="PATH", help="explicit local TOML configuration")
    web_target = web.add_mutually_exclusive_group()
    web_target.add_argument("--live", action="store_true", help="allow runs on the configured OpenAI target (paid calls)")
    web_target.add_argument("--local", action="store_true", help="allow runs on the configured local Ollama target")
    web.add_argument("--case", choices=("favorable", "advisory", "outage", "recovery"), default="favorable")
    web.add_argument("--max-investigations", type=int, choices=range(1, 11), default=3, metavar="1..10")
    web.add_argument("--trace-directory", type=Path, metavar="PATH")
    web.add_argument("--evidence", type=Path, metavar="PATH",
                     help="published evidence package (default: docs/evaluation-evidence)")
    web.add_argument("--port", type=int, default=8765, metavar="PORT", help="loopback port (default 8765; 0 picks one)")
    arguments = parser.parse_args(argv)
    if arguments.command == "web":
        if (arguments.live or arguments.local) and (arguments.config is None or arguments.release_fixtures is None):
            parser.error("--live and --local require --config and --release-fixtures")
        if not 0 <= arguments.port <= 65535:
            parser.error("--port must be between 0 and 65535")
        from .web.cli import web_command
        return web_command(arguments)
    if arguments.command == "reliability":
        from .observability.reliability import build_reliability_report, render_markdown
        report = build_reliability_report(arguments.paths, report_inputs=arguments.reports)
        print(json.dumps(report, indent=2) if arguments.format == "json" else render_markdown(report), end="\n" if arguments.format == "json" else "")
        return 1 if report["issues"] else 0
    if arguments.command == "run":
        from .agents.cli import run_command
        from .config import ConfigurationError
        from .fixtures import FixtureLoadError
        from .model_runtime.provider import ProviderError
        try:
            return asyncio.run(run_command(arguments))
        except ConfigurationError:
            print("Cannot load a valid release configuration.", file=sys.stderr)
            return 2
        except ProviderError as error:
            print(f"Model access unavailable: {error}. Configure local access; no automatic retry was attempted.", file=sys.stderr)
            return 2
        except FixtureLoadError:
            print("Cannot load the synthetic release fixture data.", file=sys.stderr)
            return 2
        except (KeyboardInterrupt, EOFError):
            print("Stopped. An interrupted investigation cannot be resumed.", file=sys.stderr)
            return 130
        except Exception:
            print("Technical error: no validated result is available for this investigation.", file=sys.stderr)
            return 1
    if arguments.command == "evaluate":
        from .harness.evaluation import evaluate_scenario
        if not arguments.agent and (arguments.config or arguments.live or arguments.local):
            parser.error("--config, --live and --local require --agent")
        if arguments.agent:
            from .agents.cli import TargetSelectionError, evaluate_agent_command
            from .config import ConfigurationError
            from .model_runtime.provider import ProviderError
            if arguments.config is None:
                parser.error("--agent requires --config")
            try:
                report = asyncio.run(evaluate_agent_command(arguments))
            except TargetSelectionError as error:
                print(str(error), file=sys.stderr)
                return 2
            except ConfigurationError:
                print("Cannot load a valid release configuration.", file=sys.stderr)
                return 2
            except ProviderError as error:
                print(f"Model access unavailable: {error}. Configure local access; no automatic retry was attempted.", file=sys.stderr)
                return 2
        elif arguments.component:
            from .harness.execution import execute_scenario
            from .demo import authored_component_runner
            from .config.settings import TraceSettings
            case = {"SC-004": "advisory", "SC-010": "outage"}.get(arguments.scenario_id)
            report = asyncio.run(execute_scenario(arguments.fixtures, arguments.scenario_id,
                runtime=authored_component_runner(case) if case else None,
                trace_settings=TraceSettings(directory=arguments.trace_directory) if arguments.trace_directory else None))
        else:
            if arguments.trace_directory is not None:
                parser.error("--trace-directory requires --component or --agent")
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
