"""Closed, sanitized failure categories on AGENT_FAILED and rejected interpretations."""

import asyncio
import json
import re
import shutil
from pathlib import Path

import pytest

from hawaii_activity_forecaster.agents.scenario import execute_agent_scenario
from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.interpretation.contracts import RequestValidationError
from hawaii_activity_forecaster.model_runtime.contracts import ProposalError
from hawaii_activity_forecaster.model_runtime.provider import ProviderError
from hawaii_activity_forecaster.model_runtime.targets import SATURDAY_PROFILE_V2
from hawaii_activity_forecaster.observability import inspect_trace
from hawaii_activity_forecaster.observability.failure_codes import (
    AGENT_FAILURE_CODES, REQUEST_CODES, REQUEST_FAILURE_CODES, TOOL_PLAN_CODES,
    agent_failure_code, request_failure_code,
)
from hawaii_activity_forecaster.orchestration.budgets import BudgetError
from hawaii_activity_forecaster.tools import ToolPlanError
from release_samples import adapter

SRC = Path(__file__).resolve().parents[1] / "src" / "hawaii_activity_forecaster"
ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "scenario-pack-v1"


def raised(error_class):
    pattern = re.compile(rf'raise {error_class}\(\s*"([^"]+)"')
    return {m.group(1) for path in SRC.rglob("*.py") for m in pattern.finditer(path.read_text())}


@pytest.mark.parametrize("error_class,codes", [("ToolPlanError", TOOL_PLAN_CODES), ("RequestValidationError", REQUEST_CODES)])
def test_every_fixed_validator_message_has_a_code(error_class, codes):
    messages = raised(error_class)
    assert messages and messages <= set(codes), sorted(messages - set(codes))


@pytest.mark.parametrize("error,code", [
    (ToolPlanError("Recovery does not reference its configured original"), "PLAN_RECOVERY_ORIGIN_MISMATCH"),
    (ToolPlanError("unexpected text"), "UNCLASSIFIED"),
    (KeyError("MODEL_INVENTED_OPTION_ID"), "PLAN_OPTION_UNKNOWN"),
    (TimeoutError("delegation expired before dispatch"), "DELEGATION_TIMEOUT"),
    (ProviderError("MODEL_TIMEOUT"), "MODEL_TIMEOUT"),
    (ProposalError("MODEL_INPUT_LIMIT"), "MODEL_CALL_FAILED"),
    (BudgetError("limit"), "BUDGET_EXHAUSTED"),
    (RuntimeError("private provider error near Kihei"), "UNCLASSIFIED"),
])
def test_agent_codes_are_closed_and_never_echo_error_text(error, code):
    assert agent_failure_code(error) == code and code in AGENT_FAILURE_CODES


@pytest.mark.parametrize("error,code", [
    (RequestValidationError("Source span does not support this field."), "REQUEST_SPAN_FIELD_MISMATCH"),
    (RequestValidationError("I'm intermediate near Kihei"), "UNCLASSIFIED"),
    (ProviderError("MODEL_HTTP_INPUT_INVALID"), "MODEL_HTTP_INPUT_INVALID"),
    (ValueError("Actually, let's look near Napili"), "UNCLASSIFIED"),
])
def test_request_codes_are_closed_and_never_echo_error_text(error, code):
    assert request_failure_code(error) == code and code in REQUEST_FAILURE_CODES


def events(directory):
    return [json.loads(line) for path in sorted(Path(directory).glob("*.jsonl"))
            for line in path.read_text().splitlines()]


def test_rejected_ocean_plan_records_its_category(tmp_path):
    """SC-010 with SURF_ABCD declared as an original: the planner labels it a fallback."""
    root = tmp_path / "pack"
    shutil.copytree(ROOT, root)
    path = root / "agent_tools" / "SC-010.json"
    tools = json.loads(path.read_text())
    for action in tools["actions"]:
        if action["action_id"] == "SURF_ABCD":
            action.pop("fallback_of")
    path.write_text(json.dumps(tools))
    result = asyncio.run(execute_agent_scenario(root, "SC-010", adapter=adapter([]),
                                                trace_settings=TraceSettings(directory=tmp_path / "traces")))
    assert result.outcome == "FAIL"
    failed = [e for e in events(tmp_path / "traces") if e["event_type"] == "AGENT_FAILED"]
    assert [e["details"]["error_code"] for e in failed] == ["PLAN_RECOVERY_CONDITION_INVALID"]
    assert "SURF_ABCD" not in json.dumps(failed)
    for trace in (tmp_path / "traces").glob("*.jsonl"):
        assert inspect_trace(trace)  # The independent validator accepts the coded failure.


def test_oversized_follow_up_records_the_model_input_category(tmp_path):
    asyncio.run(execute_agent_scenario(ROOT, "SC-012", adapter=adapter([], profile=SATURDAY_PROFILE_V2),
                                       trace_settings=TraceSettings(directory=tmp_path)))
    rejected = [e["details"] for e in events(tmp_path) if e["event_type"] == "CONTRACT_VALIDATED"
                and e["details"].get("contract") == "request_interpretation" and e["details"].get("valid") is False]
    assert [d["error_code"] for d in rejected] == ["MODEL_HTTP_INPUT_INVALID"]


def test_validator_rejects_codes_outside_the_vocabulary(tmp_path):
    from hawaii_activity_forecaster.observability import TraceValidationError
    asyncio.run(execute_agent_scenario(ROOT, "SC-012", adapter=adapter([], profile=SATURDAY_PROFILE_V2),
                                       trace_settings=TraceSettings(directory=tmp_path)))
    path = max(tmp_path.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    lines = path.read_text().splitlines()
    for index, line in enumerate(lines):
        event = json.loads(line)
        if event["details"].get("contract") == "request_interpretation" and event["details"].get("valid") is False:
            event["details"]["error_code"] = "FREE TEXT"
            lines[index] = json.dumps(event)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(TraceValidationError, match="TRACE_REQUEST_ERROR_CODE_INVALID"):
        inspect_trace(path)


def test_specific_validation_messages_survive_validate_request():
    """A specific rejection must not collapse into the generic catch-all message."""
    from hawaii_activity_forecaster.interpretation import validate_request
    from interpretation_samples import morning
    ctx, data = morning()
    data["source_spans"] = [s for s in data["source_spans"] if s["field"] != "preferred_area"]  # Omit Kihei's span.
    with pytest.raises(RequestValidationError) as caught:
        validate_request(data, ctx)
    from hawaii_activity_forecaster.observability.failure_codes import request_failure_field
    assert request_failure_code(caught.value) == "REQUEST_SPAN_MISSING"
    assert request_failure_field(caught.value) == "preferred_area"  # A closed field name, never the value.


def test_field_names_are_closed_and_never_carry_values():
    from hawaii_activity_forecaster.observability.failure_codes import request_failure_field
    assert request_failure_field(RequestValidationError("x", field="preferred_area")) == "preferred_area"
    assert request_failure_field(RequestValidationError("x", field="near Kihei")) is None
    assert request_failure_field(ValueError("x")) is None
