"""Durable admission, closed publication and retained interruption/failure traces."""

import asyncio
from dataclasses import replace

import pytest

from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.demo import run_demo
from hawaii_activity_forecaster.observability import JsonlTraceWriter, TraceValidationError, TraceWriteError, inspect_trace, read_trace
from hawaii_activity_forecaster.orchestration import SessionError, SessionManager, SyntheticModelAdapter, run_raw_synthetic_tool_graph
from interpretation_samples import REFERENCE, proposal
from raw_graph_samples import TEXT, initial_proposal, plan, scenario, tools
from trace_samples import FIXTURES, output, records


def raw_runner(directory, *, data=None, model_adapter=None, planner=plan):
    sample = scenario()
    async def execute(admission):
        return await run_raw_synthetic_tool_graph(
            admission, interpreter=None if model_adapter else lambda inputs: initial_proposal() if data is None else data,
            model_adapter=model_adapter, plan=planner, tool_plan=tools, driver_inputs=sample.driver,
            evidence_policy=sample.application.policy_configuration, trace_settings=TraceSettings(directory=directory),
        )
    return execute


def raw_start(session, directory, *, text=TEXT, **kwargs):
    return session.start_raw(text, catalog=scenario().application.catalog, reference_time=REFERENCE,
                             run=raw_runner(directory, **kwargs))


def test_unusable_trace_destination_prevents_all_dispatch_and_publication(tmp_path, monkeypatch):
    import hawaii_activity_forecaster.tools.synthetic as tool_module
    path = tmp_path / "private-parent"
    path.write_text("a file cannot contain investigation files")
    async def forbidden(*args, **kwargs):
        pytest.fail("A tool ran after authoritative trace startup failed")
    monkeypatch.setattr(tool_module.SyntheticToolDispatcher, "run", forbidden)
    calls = []
    async def respond(operation, inputs):
        calls.append(operation)
        return initial_proposal()
    report = asyncio.run(raw_start(SessionManager(), path, model_adapter=SyntheticModelAdapter(respond)))
    assert report.state.status == "FAILED" and report.state.completion_reason == "TRACE_WRITE_FAILED"
    assert report.state.activity is None and report.result is None and report.trace_validation is None
    assert not report.trace_writable and report.budgets.closed
    assert report.budgets.model_calls == report.budgets.tool_calls == 0 and calls == []
    assert path.read_text() == "a file cannot contain investigation files"


@pytest.mark.parametrize("fail_at,model_calls,tool_calls", [
    ("INVESTIGATION_STARTED", 0, 0), ("REQUEST_RECEIVED", 0, 0), ("AUTHORIZED", 0, 0),
    ("RETURNED", 1, 0), ("REQUEST_NORMALIZED", 1, 0), ("TOOL_CALLED", 1, 0),
    ("TOOL_COMPLETED", 1, 1), ("RESULT_VALIDATED", 1, 6), ("INVESTIGATION_COMPLETED", 1, 6),
])
def test_mandatory_runtime_append_failure_closes_work_and_keeps_actual_prefix(tmp_path, monkeypatch, fail_at, model_calls, tool_calls):
    original = JsonlTraceWriter.append
    recorded, calls = [], []
    def fail(self, event):
        if fail_at in {event.event_type, event.details.get("phase")}:
            raise TraceWriteError("private filesystem error payload")
        original(self, event)
        recorded.append(event.event_id)
    monkeypatch.setattr(JsonlTraceWriter, "append", fail)
    async def respond(operation, inputs):
        calls.append(operation)
        return initial_proposal()
    report = asyncio.run(raw_start(SessionManager(), tmp_path, model_adapter=SyntheticModelAdapter(respond)))
    assert report.state.status == "FAILED" and report.state.completion_reason == "TRACE_WRITE_FAILED"
    assert report.result is report.result_validation is report.trace_validation is None
    assert not report.trace_writable and report.budgets.closed
    assert report.budgets.model_calls == len(calls) == model_calls and report.budgets.tool_calls == tool_calls
    assert not report.budgets.active_specialists and not report.budgets.reserved_model_calls and not report.budgets.reserved_tool_calls
    assert report.trace_path.exists()
    actual = records(report.trace_path) if report.trace_path.stat().st_size else []
    assert [e["event_id"] for e in actual] == recorded
    assert not any(e["event_type"] in {"INVESTIGATION_FAILED", "INVESTIGATION_COMPLETED"} for e in actual)
    assert "private filesystem" not in repr(report) + report.trace_path.read_text()


@pytest.mark.parametrize("failure", ["fsync", "close"])
def test_final_durability_or_close_error_suppresses_a_result_even_if_terminal_bytes_exist(tmp_path, monkeypatch, failure):
    import hawaii_activity_forecaster.observability.storage as storage
    actual_append, actual_sync, actual_close = JsonlTraceWriter.append, storage.os.fsync, storage.os.close
    armed = [False]
    def append(self, event):
        if event.event_type == "INVESTIGATION_COMPLETED":
            armed[0] = True
        return actual_append(self, event)
    def sync(fd):
        if armed[0] and failure == "fsync":
            raise OSError("private filesystem failure")
        return actual_sync(fd)
    def close(fd):
        result = actual_close(fd)
        if armed[0] and failure == "close":
            raise OSError("private close failure")
        return result
    monkeypatch.setattr(JsonlTraceWriter, "append", append)
    monkeypatch.setattr(storage.os, "fsync", sync)
    monkeypatch.setattr(storage.os, "close", close)
    sample = output(tmp_path)
    assert sample.report.state.status == "FAILED" and sample.report.result is None
    assert not sample.report.trace_writable and sample.report.trace_validation is None
    assert sample.report.state.completion_reason == "TRACE_WRITE_FAILED"
    with pytest.raises(TraceValidationError):
        inspect_trace(sample.report.trace_path, state=sample.report.state)


def test_independent_prepublication_validation_detects_a_structurally_valid_bad_counter(tmp_path, monkeypatch):
    original = JsonlTraceWriter.append
    def corrupt(self, event):
        if event.event_type == "INVESTIGATION_COMPLETED":
            event = event.model_copy(update={"details": event.details | {"total_tool_calls": 7}})
        return original(self, event)
    monkeypatch.setattr(JsonlTraceWriter, "append", corrupt)
    sample = output(tmp_path)
    assert sample.report.result is None and sample.report.trace_validation is None
    assert sample.report.state.status == "FAILED" and sample.report.state.completion_reason == "TRACE_VALIDATION_FAILED"
    with pytest.raises(TraceValidationError, match="COUNTERS"):
        inspect_trace(sample.report.trace_path)


def test_post_terminal_followup_creates_new_file_and_preserves_previous_bytes(tmp_path):
    async def exercise():
        session = SessionManager()
        first = await raw_start(session, tmp_path)
        before = first.trace_path.read_bytes()
        text = "Near Napili instead."
        second = await session.follow_up_raw(text, catalog=scenario().application.catalog, reference_time=REFERENCE,
            run=raw_runner(tmp_path, data=proposal(text, {"preferred_area": "Napili"}, {"preferred_area": "Near Napili"})))
        assert first.state.status == second.state.status == "COMPLETED"
        assert first.trace_path != second.trace_path and len(list(tmp_path.glob("*.jsonl"))) == 2
        assert first.trace_path.read_bytes() == before
        a, b = read_trace(first.trace_path), read_trace(second.trace_path)
        assert a.trace_id != b.trace_id and a.investigation_id != b.investigation_id
        assert {e.request_revision for e in a.events} == {1} and {e.request_revision for e in b.events} == {2}
        revised = next(e for e in b.events if e.event_type == "REQUEST_REVISED")
        assert revised.details["previous_investigation_id"] == a.investigation_id
        assert revised.related_ids == [a.investigation_id]
        assert all(e.details["session_id"] == session.session_id for e in a.events + b.events)
    asyncio.run(exercise())


def test_clarification_closes_a_valid_partial_trace_without_fabricating_a_result(tmp_path):
    text = "Snorkel tomorrow."
    data = proposal(text, {"activity": "SNORKELING", "target_date": "2026-11-17"},
                    {"activity": "Snorkel", "target_date": "tomorrow"})
    report = asyncio.run(raw_start(SessionManager(), tmp_path, text=text, data=data))
    assert report.state.status == "AWAITING_CLARIFICATION" and report.result is None and report.trace_writable
    assert not report.trace_validation.complete
    trace = read_trace(report.trace_path)
    assert trace.final_status is trace.completed_at is None
    assert trace.events[-1].event_type == "CLARIFICATION_REQUESTED"
    assert not any(e.event_type in {"AGENT_STARTED", "TOOL_CALLED", "INVESTIGATION_FAILED"} for e in trace.events)


def test_normalization_failure_has_a_complete_failed_trace_without_invented_request_fields(tmp_path):
    async def respond(operation, inputs):
        raise RuntimeError("private model payload")
    report = asyncio.run(raw_start(SessionManager(), tmp_path, model_adapter=SyntheticModelAdapter(respond)))
    assert report.state.status == "FAILED" and report.result is None and report.trace_writable
    assert report.state.activity is None and report.state.target_time_window is None
    assert report.trace_validation.complete and report.trace_validation.metrics.model_calls == 1
    assert report.trace_validation.metrics.outcome == "ERROR"
    trace = read_trace(report.trace_path)
    assert trace.final_status == "FAILED" and trace.events[-1].event_type == "INVESTIGATION_FAILED"
    assert not any(e.event_type == "REQUEST_NORMALIZED" for e in trace.events)
    assert "private model payload" not in report.trace_path.read_text()


def test_interruption_preserves_partial_records_without_inventing_terminal_events(tmp_path):
    async def exercise():
        entered, session = asyncio.Event(), SessionManager()
        async def respond(operation, inputs):
            entered.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(raw_start(session, tmp_path, model_adapter=SyntheticModelAdapter(respond)))
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        path, = tmp_path.glob("*.jsonl")
        validation = inspect_trace(path)
        assert not validation.complete and validation.metrics.outcome is None
        trace = read_trace(path)
        assert not any(e.event_type in {"INVESTIGATION_COMPLETED", "INVESTIGATION_FAILED"} for e in trace.events)
        with pytest.raises(SessionError):
            await raw_start(session, tmp_path)
    asyncio.run(exercise())


def test_parallel_specialists_can_complete_ocean_before_weather_with_valid_correlation(tmp_path, monkeypatch):
    from hawaii_activity_forecaster.tools.synthetic import SyntheticToolDispatcher
    original = SyntheticToolDispatcher.run
    async def exercise():
        ocean_done = asyncio.Event()
        async def reordered(self, parent):
            if parent.agent_type == "WEATHER":
                await ocean_done.wait()
            response = await original(self, parent)
            if parent.agent_type == "OCEAN":
                ocean_done.set()
            return response
        monkeypatch.setattr(SyntheticToolDispatcher, "run", reordered)
        sample = await run_demo("advisory", FIXTURES, trace_settings=TraceSettings(directory=tmp_path))
        assert sample.report.state.status == "COMPLETED"
        trace = read_trace(sample.report.trace_path)
        assert [e.actor for e in trace.events if e.event_type == "AGENT_COMPLETED"] == ["OCEAN", "WEATHER"]
        assert inspect_trace(sample.report.trace_path).complete
    asyncio.run(exercise())


def test_deleted_destination_is_detected_before_next_dispatch(tmp_path, monkeypatch):
    original = JsonlTraceWriter.append
    def remove(self, event):
        original(self, event)
        if event.event_type == "REQUEST_NORMALIZED":
            self.path.unlink()
    monkeypatch.setattr(JsonlTraceWriter, "append", remove)
    sample = output(tmp_path)
    assert sample.report.state.status == "FAILED" and sample.report.state.completion_reason == "TRACE_WRITE_FAILED"
    assert sample.report.result is None and sample.report.budgets.tool_calls == 0


def test_shared_model_budget_is_visible_as_synthetic_accounting_in_local_trace(tmp_path):
    from hawaii_activity_forecaster.orchestration import BudgetError
    async def respond(operation, inputs):
        return initial_proposal() if operation == "normalize_request" else {"synthetic": True}
    async def choose(inputs):
        for _ in range(11):
            await inputs.models.invoke("coordinator_plan", inputs.state)
        with pytest.raises(BudgetError):
            await inputs.models.invoke("coordinator_plan", inputs.state)
        return plan(inputs)
    report = asyncio.run(raw_start(SessionManager(), tmp_path, model_adapter=SyntheticModelAdapter(respond), planner=choose))
    assert report.state.status == "COMPLETED", report.state.completion_reason
    assert report.trace_validation.metrics.model_calls == 12 and report.trace_validation.metrics.tool_calls == 6
    assert report.trace_validation.metrics.iterations == 1
    trace = read_trace(report.trace_path)
    model_events = [e for e in trace.events if e.details.get("contract") == "synthetic_model_dispatch"]
    assert len(model_events) == 24 and all(e.details["synthetic_adapter"] for e in model_events)
    assert trace.model_identifier is None
    assert any(e.event_type == "INVESTIGATION_LIMIT_REACHED" and e.details["budget_kind"] == "model" for e in trace.events)


@pytest.mark.parametrize("tamper", ["missing-path", "missing-receipt", "changed-file"])
def test_session_commit_checks_authoritative_artifact_receipt(tmp_path, tamper):
    async def corrupt(admission):
        report = await raw_runner(tmp_path)(admission)
        if tamper == "missing-path":
            return replace(report, trace_path=None)
        if tamper == "missing-receipt":
            return replace(report, trace_validation=None)
        report.trace_path.write_bytes(report.trace_path.read_bytes() + b"\n")
        return report
    session = SessionManager()
    with pytest.raises(SessionError, match="correlated investigation"):
        asyncio.run(session.start_raw(TEXT, catalog=scenario().application.catalog, reference_time=REFERENCE, run=corrupt))
    assert session.investigations == ()


def test_ambient_or_unavailable_langsmith_does_not_replace_local_tracing(tmp_path, monkeypatch):
    from langsmith import Client
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "EXAMPLE_SECRET_CREDENTIAL")
    def no_remote(*args, **kwargs):
        pytest.fail("Local tracing attempted remote LangSmith transmission")
    monkeypatch.setattr(Client, "create_run", no_remote)
    monkeypatch.setattr(Client, "update_run", no_remote)
    sample = output(tmp_path)
    assert sample.report.state.status == "COMPLETED" and sample.report.trace_validation.complete
    assert "EXAMPLE_SECRET_CREDENTIAL" not in sample.report.trace_path.read_text()
