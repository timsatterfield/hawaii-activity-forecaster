"""Component graph checks, not SC-004/SC-010 runtime or safety evaluations."""

import asyncio
from dataclasses import FrozenInstanceError

import pytest
from langsmith.run_helpers import get_tracing_context

from hawaii_activity_forecaster.models import NormalizedRequest
from hawaii_activity_forecaster.models.enums import AgentType, InvestigationStatus, Outcome, TraceEventType
from hawaii_activity_forecaster.orchestration import BranchSignal, run_skeleton


@pytest.fixture
def normalized_request():
    return NormalizedRequest(
        original_request="Synthetic swimming request", activity="SWIMMING",
        target_time_window={"start": "2026-11-18T09:00:00-10:00", "end": "2026-11-18T11:00:00-10:00"},
        hard_constraints=[], soft_preferences=[], clarification_needed=False,
        clarification_questions=[],
    )


def run(normalized_request, branch, recorder=None, **kwargs):
    return asyncio.run(run_skeleton(
        normalized_request, candidate_beach_ids=("synthetic-beach",), branch=branch,
        record_event=recorder if recorder is not None else lambda event: None, **kwargs,
    ))


@pytest.mark.parametrize("first", list(AgentType))
def test_parallel_fanout_fanin_and_early_stop(normalized_request, first, monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    events = []
    entered = set()
    completed = []

    async def exercise():
        both_entered = asyncio.Event()
        first_finished = asyncio.Event()

        async def branch(value):
            assert get_tracing_context()["enabled"] is False
            entered.add(value.agent_type)
            if len(entered) == 2:
                both_entered.set()
            await asyncio.wait_for(both_entered.wait(), timeout=2)
            if value.agent_type != first:
                await asyncio.wait_for(first_finished.wait(), timeout=2)
            with pytest.raises(FrozenInstanceError):
                value.iteration = 900
            completed.append(value.agent_type)
            if value.agent_type == first:
                first_finished.set()
            return BranchSignal(value.agent_type)

        return await run_skeleton(normalized_request, candidate_beach_ids=("synthetic-beach",),
                                  branch=branch, record_event=events.append)

    report = asyncio.run(exercise())
    assert completed == [first, next(role for role in AgentType if role != first)]
    assert report.state.status == InvestigationStatus.FAILED
    assert report.state.outcome == Outcome.ERROR
    assert report.state.completion_reason == "VALIDATORS_NOT_IMPLEMENTED"
    assert report.state.iteration_count == report.budgets.iterations == 1
    assert report.visited_nodes.count("decide_next_action") == 1
    assert report.visited_nodes[-1] == "finalize_investigation"
    assert report.budgets.tool_calls == report.budgets.model_calls == 0
    assert report.budgets.active_specialists == 0
    assert report.budgets.closed
    assert report.state.assessments == report.state.weather_findings == report.state.ocean_findings == []
    assert [event.sequence_number for event in events] == list(range(1, len(events) + 1))
    assert events[-1].event_type == TraceEventType.INVESTIGATION_FAILED
    assert not any(event.event_type in (TraceEventType.RESULT_VALIDATED, TraceEventType.POLICY_EVALUATED)
                   for event in events)


def test_five_cycles_not_ten_and_no_sixth_dispatch(normalized_request):
    calls = []

    async def branch(value):
        calls.append((value.iteration, value.agent_type))
        return BranchSignal(value.agent_type, needs_another_cycle=True)

    report = run(normalized_request, branch)
    assert len(calls) == 10
    assert {iteration for iteration, _ in calls} == {1, 2, 3, 4, 5}
    assert report.budgets.iterations == report.state.iteration_count == 5
    assert report.state.completion_reason == "ITERATION_LIMIT_REACHED"
    assert report.visited_nodes.count("decide_next_action") == 5


def test_latest_cycle_signals_control_conditional_loop(normalized_request):
    async def branch(value):
        return BranchSignal(value.agent_type, needs_another_cycle=value.iteration == 1)

    report = run(normalized_request, branch)
    assert report.budgets.iterations == 2
    assert report.state.completion_reason == "VALIDATORS_NOT_IMPLEMENTED"


@pytest.mark.parametrize("missing", ["activity", "target_time_window", "clarification"])
def test_initial_clarification_without_dispatch(normalized_request, missing):
    updates = {"clarification_needed": True} if missing == "clarification" else {missing: None}
    normalized_request = NormalizedRequest.model_validate({**normalized_request.model_dump(), **updates})

    async def forbidden(value):
        pytest.fail("clarification must precede branch dispatch")

    report = run(normalized_request, forbidden)
    assert report.state.status == InvestigationStatus.AWAITING_CLARIFICATION
    assert report.state.outcome is None
    assert report.state.result_id is None
    assert report.budgets.iterations == 0


@pytest.mark.parametrize("failure_at", [1, 2, 7])
def test_trace_failure_stops_new_dispatch_and_never_publishes_result(normalized_request, failure_at):
    events = []
    calls = []
    failed = False

    def recorder(event):
        nonlocal failed
        if event.sequence_number == failure_at:
            failed = True
            raise OSError("synthetic disk failure")
        events.append(event)

    async def branch(value):
        assert not failed, "new callback dispatched after recording failed"
        calls.append(value)
        return BranchSignal(value.agent_type, True)

    report = run(normalized_request, branch, recorder)
    assert report.state.status == InvestigationStatus.FAILED
    assert report.state.completion_reason == "TRACE_WRITE_FAILED"
    assert not report.trace_writable
    assert report.budgets.closed
    assert report.budgets.active_specialists == 0
    assert len(calls) <= (0 if failure_at <= 2 else 3)
    assert not any(event.event_type == TraceEventType.RESULT_VALIDATED for event in events)


@pytest.mark.parametrize("mode", ["wrong-role", "invalid-type", "exception"])
def test_invalid_or_failed_callback_cannot_mutate_authoritative_state(normalized_request, mode):
    async def branch(value):
        if mode == "exception":
            raise RuntimeError("synthetic callback failure")
        if mode == "invalid-type":
            return {"status": "COMPLETED", "assessments": ["unsafe mutation"]}
        return BranchSignal(AgentType.OCEAN if value.agent_type == AgentType.WEATHER else AgentType.WEATHER)

    report = run(normalized_request, branch)
    assert report.state.status == InvestigationStatus.FAILED
    assert report.state.completion_reason == "SKELETON_EXECUTION_FAILED"
    assert report.state.assessments == []
    assert report.budgets.active_specialists == 0


def test_fresh_run_does_not_reopen_or_mutate_previous_terminal_run(normalized_request):
    async def branch(value):
        return BranchSignal(value.agent_type)

    first = run(normalized_request, branch, session_id="synthetic-session")
    snapshot = first.state.model_dump_json()
    second = run(normalized_request, branch, session_id="synthetic-session")
    assert first.state.model_dump_json() == snapshot
    assert first.state.investigation_id != second.state.investigation_id
    assert first.state.result_id != second.state.result_id
    assert first.state.session_id == second.state.session_id
    assert first.budgets.iterations == second.budgets.iterations == 1


def test_failed_branch_cancels_inflight_sibling_before_return(normalized_request):
    cleaned_up = []

    async def exercise():
        ocean_entered = asyncio.Event()

        async def branch(value):
            if value.agent_type == AgentType.WEATHER:
                await asyncio.wait_for(ocean_entered.wait(), timeout=2)
                raise RuntimeError("synthetic specialist failure")
            ocean_entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned_up.append(value.agent_type)

        return await run_skeleton(normalized_request, candidate_beach_ids=("synthetic-beach",),
                                  branch=branch, record_event=lambda event: None)

    report = asyncio.run(exercise())
    assert cleaned_up == [AgentType.OCEAN]
    assert report.budgets.active_specialists == 0
    assert report.state.completion_reason == "SKELETON_EXECUTION_FAILED"


def test_empty_candidates_stop_without_dispatch(normalized_request):
    async def forbidden(value):
        pytest.fail("no candidates must not dispatch")

    report = asyncio.run(run_skeleton(normalized_request, candidate_beach_ids=(), branch=forbidden,
                                     record_event=lambda event: None))
    assert report.state.completion_reason == "NO_SELECTED_CANDIDATES"
    assert report.budgets.iterations == 0
