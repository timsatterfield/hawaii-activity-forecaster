"""RI-T17/18 accounting doubles; no live provider, SDK, or model BehaviorScript."""

import asyncio

import pytest

from hawaii_activity_forecaster.config.settings import LLMSettings
from hawaii_activity_forecaster.orchestration import BudgetError, SessionManager, SyntheticModelAdapter
from raw_graph_samples import initial_proposal, plan, start


def test_normalization_and_later_work_share_twelve_model_slots_without_reset():
    events, calls, gateways = [], [], []
    async def respond(operation, inputs):
        calls.append(operation)
        return initial_proposal() if operation == "normalize_request" else {"synthetic": True}
    async def choose(inputs):
        gateways.append(inputs.models)
        assert inputs.state.iteration_count == 0
        for _ in range(11):
            await inputs.models.invoke("coordinator_plan", inputs.state)
        with pytest.raises(BudgetError, match="model invocation limit"):
            await inputs.models.invoke("coordinator_plan", inputs.state)
        return plan(inputs)
    adapter = SyntheticModelAdapter(respond)
    report = asyncio.run(start(SessionManager(), model_adapter=adapter, planner=choose, events=events))
    assert report.state.status == "COMPLETED", report.state.completion_reason
    assert report.budgets.model_calls == len(calls) == 12
    assert calls[0] == "normalize_request" and calls[1:] == ["coordinator_plan"] * 11
    assert report.budgets.iterations == 1 and report.budgets.tool_calls == 6
    assert report.budgets.retries == report.budgets.fallbacks == 0
    normalized = next(e for e in events if e.event_type == "REQUEST_NORMALIZED")
    assert normalized.details["model_call_count"] == 1 and normalized.details["tool_call_count"] == 0
    tools = [e for e in events if e.event_type == "TOOL_CALLED"]
    assert len(tools) == 6 and all(e.details["model_call_count"] == 12 for e in tools)
    model_events = [e for e in events if e.details.get("contract") == "synthetic_model_dispatch"]
    assert len(model_events) == 24 and all(e.details["synthetic_adapter"] is True for e in model_events)
    with pytest.raises(BudgetError, match="closed"):
        asyncio.run(gateways[0].invoke("coordinator_plan", {}))
    assert len(calls) == 12
    # A new investigation owns a fresh ledger; it does not reuse the old gateway.
    second = asyncio.run(start(SessionManager(), model_adapter=adapter))
    assert second.state.status == "COMPLETED" and second.budgets.model_calls == 1
    assert second.state.investigation_id != report.state.investigation_id
    assert LLMSettings().enabled is False and LLMSettings().provider is None


@pytest.mark.parametrize("failure", ["malformed", "exception", "timeout"])
def test_normalization_operational_failure_charges_once_and_invents_no_context(failure, monkeypatch):
    import hawaii_activity_forecaster.orchestration.model_calls as module
    calls, timeouts, events = [], [], []
    original_wait_for = module.wait_for
    async def short_timeout(awaitable, *, timeout):
        timeouts.append(timeout)
        return await original_wait_for(awaitable, timeout=0.01)
    if failure == "timeout":
        monkeypatch.setattr(module, "wait_for", short_timeout)
    async def respond(operation, inputs):
        calls.append(operation)
        if failure == "malformed":
            return {"changed_values": {"activity": "SUP"}, "validated": True, "secret": "private-adapter-payload"}
        if failure == "exception":
            raise RuntimeError("private-adapter-payload")
        await asyncio.Event().wait()
    report = asyncio.run(start(SessionManager(), model_adapter=SyntheticModelAdapter(respond), events=events))
    assert report.state.status == "FAILED" and report.result is None
    assert report.state.activity is None and report.state.target_time_window is None
    assert report.state.candidate_beach_ids == report.state.assessments == []
    assert report.budgets.model_calls == 1 and report.budgets.iterations == report.budgets.tool_calls == 0
    assert calls == ["normalize_request"] and report.budgets.closed
    assert not report.budgets.reserved_model_calls and not report.budgets.active_specialists
    assert report.trace_writable
    assert not any(e.event_type in {"REQUEST_NORMALIZED", "AGENT_STARTED", "TOOL_CALLED", "RETRY_INITIATED"} for e in events)
    assert "private-adapter-payload" not in repr(events) + repr(report)
    if failure == "timeout":
        assert timeouts == [30]
        assert any(e.details.get("error_code") == "MODEL_TIMEOUT" for e in events)


@pytest.mark.parametrize("failure_at,charged", [
    ("INVESTIGATION_STARTED", 0), ("REQUEST_RECEIVED", 0), ("AUTHORIZED", 0),
    ("RETURNED", 1), ("REQUEST_NORMALIZED", 1), ("candidate_selection", 1),
    ("RESULT_VALIDATED", 1), ("INVESTIGATION_COMPLETED", 1),
])
def test_required_trace_failure_blocks_dispatch_or_publication(failure_at, charged):
    calls = []
    async def respond(operation, inputs):
        calls.append(operation)
        return initial_proposal()
    def record(event):
        if failure_at in {event.event_type, event.details.get("phase"), event.details.get("contract")}:
            raise OSError("private-adapter-payload")
    report = asyncio.run(start(SessionManager(), model_adapter=SyntheticModelAdapter(respond), recorder=record))
    assert report.state.status == "FAILED" and report.state.completion_reason == "TRACE_WRITE_FAILED"
    assert report.result is None and report.result_validation is None
    assert report.budgets.model_calls == len(calls) == charged
    assert report.budgets.tool_calls == (6 if failure_at in {"RESULT_VALIDATED", "INVESTIGATION_COMPLETED"} else 0)
    assert not report.trace_writable and report.budgets.closed and report.state.assessments == []
    assert not report.budgets.reserved_model_calls and not report.budgets.reserved_tool_calls
    assert "private-adapter-payload" not in repr(report)
