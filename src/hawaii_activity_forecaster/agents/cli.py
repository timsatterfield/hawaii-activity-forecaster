"""Explicit OpenAI/local-model CLI for the bounded synthetic release."""

import sys

from hawaii_activity_forecaster.config import load_config
from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.model_runtime.provider import create_adapter
from hawaii_activity_forecaster.presentation import render_report
from .data import load_release_data
from .session import AgentSession


async def run_command(arguments) -> int:
    if not (arguments.live or arguments.local):
        print("Model execution requires --live (OpenAI) or --local (Ollama) and an enabled configuration.", file=sys.stderr)
        return 2
    config = load_config(arguments.config)
    if not config.llm.enabled:
        print("Load an explicit enabled synthetic-release configuration with --config.", file=sys.stderr)
        return 2
    if config.llm.provider != ("openai" if arguments.live else "ollama"):
        print("The execution switch must match the configured provider: --live for OpenAI, --local for Ollama.", file=sys.stderr)
        return 2
    data = load_release_data(arguments.fixtures, arguments.case)
    adapter = create_adapter(config.llm)
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
