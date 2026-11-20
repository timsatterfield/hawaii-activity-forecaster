"""Explicit OpenAI/local-model CLI for the bounded synthetic release."""

import sys

from hawaii_activity_forecaster.config import load_config
from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.model_runtime.provider import create_adapter
from hawaii_activity_forecaster.presentation import render_report
from .data import load_release_data
from .session import AgentSession


class TargetSelectionError(ValueError):
    """Explicit opt-in is missing or inconsistent; nothing was dispatched."""


def configured_target(arguments):
    """Return (config, adapter) only after explicit, matching opt-in."""
    if not (arguments.live or arguments.local):
        raise TargetSelectionError("Model execution requires --live (OpenAI) or --local (Ollama) and an enabled configuration.")
    config = load_config(arguments.config)
    if not config.llm.enabled:
        raise TargetSelectionError("Load an explicit enabled synthetic-release configuration with --config.")
    if config.llm.provider != ("openai" if arguments.live else "ollama"):
        raise TargetSelectionError("The execution switch must match the configured provider: --live for OpenAI, --local for Ollama.")
    return config, create_adapter(config.llm)


async def run_command(arguments) -> int:
    try:
        config, adapter = configured_target(arguments)
    except TargetSelectionError as error:
        print(str(error), file=sys.stderr)
        return 2
    data = load_release_data(arguments.fixtures, arguments.case)
    settings = config.trace if arguments.trace_directory is None else TraceSettings(directory=arguments.trace_directory)
    limit = arguments.max_investigations
    session = AgentSession(data, adapter, trace_settings=settings, max_investigations=limit)
    print("Model-driven investigation of SYNTHETIC environmental data only.")
    print(f"Model target: {config.llm.provider} / {config.llm.model_identifier}.")
    print(f"Fixture clock: {data.reference_time.isoformat()}; no real conditions are retrieved.")
    print("Available synthetic windows: " + "; ".join(
        f"{window.start.isoformat()} to {window.end.isoformat()}" for window in data.target_windows))
    print(f"This process permits at most {limit} investigations; model/tool limits apply to each.")
    text = arguments.request
    status = 0
    try:
        for index in range(limit):
            if text is None:
                try:
                    text = input("Request: " if index == 0 else "Follow-up (or /quit): ").strip()
                except EOFError:
                    break
            if not text or text.casefold() in {"/quit", "/exit"}:
                break
            report = await session.ask(text)
            if report.state.status == "AWAITING_CLARIFICATION":
                print("Clarification needed:")
                for question in report.state.clarification_questions:
                    print("- " + question)
                print("Submit a complete clarified request in a new run; active clarification resumption is deferred.")
                status = 2
            elif report.result is None:
                print("Technical error: no validated result is available. " + report.state.completion_reason, file=sys.stderr)
                status = 1
            else:
                print(render_report(report, catalog=data.catalog, policy=data.policy), end="")
                status = 1 if report.result.outcome == "ERROR" else 0
            if report.trace_path:
                print(f"Local trace: {report.trace_path}")
            if not arguments.interactive or status:
                break
            text = None
    finally:
        session.close()
    return status


async def evaluate_agent_command(arguments):
    """Run one registered scenario through the model-driven runtime; JSON report."""
    from hawaii_activity_forecaster.agents.scenario import execute_agent_scenario
    config, adapter = configured_target(arguments)
    settings = config.trace if arguments.trace_directory is None else TraceSettings(directory=arguments.trace_directory)
    print(f"Model-driven registered scenario {arguments.scenario_id}: SYNTHETIC data only; "
          f"target {config.llm.provider} / {config.llm.model_identifier}.", file=sys.stderr)
    return await execute_agent_scenario(arguments.fixtures, arguments.scenario_id, adapter=adapter, trace_settings=settings)
