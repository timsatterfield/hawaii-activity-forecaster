"""Synthetic graph contract integration; no environmental tool or safety execution."""

import asyncio
from datetime import timedelta

import pytest
from langsmith.run_helpers import get_tracing_context

from hawaii_activity_forecaster.orchestration import run_specialist_graph
from specialist_samples import BEACH, catalog, normalized, request, response


def plan_for(roles=("WEATHER", "OCEAN")):
    def plan(snapshot):
        if snapshot.iteration_count:
            return ()
        return tuple(request(
            role, investigation_id=snapshot.investigation_id, schema_version=snapshot.schema_version,
            issued_at=snapshot.updated_at, target_time_window=snapshot.target_time_window,
        ) for role in roles)
    return plan


def run(specialist, plan=None, recorder=None, **kwargs):
    return asyncio.run(run_specialist_graph(
        normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,),
        plan=plan if plan is not None else plan_for(), specialist=specialist,
        record_event=recorder if recorder is not None else lambda event: None, **kwargs,
    ))


@pytest.mark.parametrize("first", ["WEATHER", "OCEAN"])
def test_actual_specialist_contracts_traverse_parallel_graph_and_merge_in_both_orders(first, monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    events = []
    completed = []

    async def exercise():
        both = asyncio.Event()
        first_done = asyncio.Event()
        entered = set()

        async def specialist(origin):
            assert get_tracing_context()["enabled"] is False
            entered.add(origin.agent_type)
            if len(entered) == 2:
                both.set()
            await asyncio.wait_for(both.wait(), timeout=2)
            if origin.agent_type != first:
                await asyncio.wait_for(first_done.wait(), timeout=2)
            completed.append(origin.agent_type)
            if origin.agent_type == first:
                first_done.set()
            return response(origin)

        return await run_specialist_graph(
            normalized(), catalog=catalog(), candidate_beach_ids=(BEACH,), plan=plan_for(),
            specialist=specialist, record_event=events.append,
        )

    report = asyncio.run(exercise())
    assert completed[0] == first
    assert len(report.state.weather_findings) == len(report.state.ocean_findings) == 1
    assert report.visited_nodes.count("validate_and_merge_specialist_responses") == 1
    assert report.budgets.iterations == 1
    assert report.budgets.model_calls == report.budgets.tool_calls == 0
    assert report.state.schema_version == "0.1"
    assert report.state.status == "FAILED"
    assert report.state.completion_reason == "VALIDATORS_NOT_IMPLEMENTED"
    assert report.state.assessments == []
    validated = [e for e in events if e.event_type == "CONTRACT_VALIDATED" and e.details["contract"] == "specialist_response"]
    assert len(validated) == 2
    assert all(e.details["request_id"] and e.details["attempt_number"] == 1 for e in validated)
    assert all(f.validation_status == "PENDING" for f in report.state.weather_findings + report.state.ocean_findings)


@pytest.mark.parametrize("failure", ["exception", "malformed", "wrong-origin"])
def test_failure_isolated_to_branch_and_valid_sibling_survives(failure):
    async def specialist(origin):
        if origin.agent_type == "WEATHER":
            if failure == "exception":
                raise RuntimeError("synthetic exception text must not be recorded")
            if failure == "malformed":
                return {"recommendations": ["must not be authoritative"]}
            return response(origin).model_dump() | {"request_id": "OCEAN-request"}
        return response(origin)

    events = []
    report = run(specialist, recorder=events.append)
    assert report.state.weather_findings == []
    assert len(report.state.ocean_findings) == 1
    assert report.state.active_errors
    assert report.state.assessments == []
    assert report.budgets.active_specialists == 0
    assert "synthetic exception text" not in str([e.model_dump() for e in events])


@pytest.mark.parametrize("role", ["WEATHER", "OCEAN"])
def test_single_specialist_dispatch_joins_without_invoking_undelegated_role(role):
    calls = []

    async def specialist(origin):
        calls.append(origin.agent_type)
        return response(origin)

    report = run(specialist, plan=plan_for((role,)))
    assert calls == [role]
    assert report.budgets.iterations == 1
    assert len(report.state.weather_findings + report.state.ocean_findings) == 1


def test_invalid_delegation_is_blocked_before_specialist_callback():
    async def forbidden(origin):
        pytest.fail("invalid request reached a specialist")

    def invalid(snapshot):
        return (request(investigation_id=snapshot.investigation_id, issued_at=snapshot.updated_at,
                        candidate_beach_ids=["TEST_BEACH_B"]),)

    report = run(forbidden, plan=invalid)
    assert report.state.completion_reason == "SPECIALIST_CONTRACT_FAILED"
    assert report.budgets.iterations == 0
    assert report.state.weather_findings == []


def test_planner_and_callback_cannot_mutate_authoritative_scope_or_preferences():
    def plan(snapshot):
        requests = plan_for(("WEATHER",))(snapshot)
        snapshot.hard_constraints.clear()
        snapshot.candidate_beach_ids.append("TEST_BEACH_B")
        return requests

    async def specialist(origin):
        origin.candidate_beach_ids.append("TEST_BEACH_B")
        return response(origin)

    report = run(specialist, plan=plan)
    assert report.state.hard_constraints == normalized().hard_constraints
    assert report.state.candidate_beach_ids == [BEACH]
    assert report.state.pending_evidence_requests[0].candidate_beach_ids == [BEACH]
    assert len(report.state.weather_findings) == 1


def test_contract_flow_retains_five_cycle_guard_and_deduplicates_repeated_evidence():
    def plan(snapshot):
        return (request(investigation_id=snapshot.investigation_id, issued_at=snapshot.updated_at,
                        request_id=f"request-{snapshot.iteration_count}"),)

    async def specialist(origin):
        return response(origin, status="PARTIAL", unresolved_gaps=[{
            "gap_id": "still-missing", "gap_type": "MISSING", "related_finding_ids": [],
            "description": "Synthetic unresolved evidence check",
        }])

    report = run(specialist, plan=plan)
    assert report.budgets.iterations == 5
    assert report.state.completion_reason == "ITERATION_LIMIT_REACHED"
    assert len(report.state.weather_findings) == 1
    assert len(report.state.unresolved_evidence_issues) == 1
    assert report.visited_nodes.count("validate_and_merge_specialist_responses") == 5


@pytest.mark.parametrize("stage", ["request", "response"])
def test_recorder_failure_blocks_contract_dispatch_or_commit(stage):
    calls = []

    def recorder(event):
        if event.event_type == "CONTRACT_VALIDATED" and event.details["contract"] == f"specialist_{stage}":
            raise OSError("synthetic disk failure")

    async def specialist(origin):
        calls.append(origin)
        return response(origin)

    report = run(specialist, recorder=recorder)
    assert report.state.completion_reason == "TRACE_WRITE_FAILED"
    assert not report.trace_writable
    assert report.budgets.closed
    assert not report.state.weather_findings and not report.state.ocean_findings
    assert len(calls) == (0 if stage == "request" else 2)


def test_deadline_timeout_is_isolated_and_cleans_up_callback(monkeypatch):
    import hawaii_activity_forecaster.orchestration.skeleton as module
    cleaned = []
    actual_wait_for = asyncio.wait_for

    async def deterministic_timeout(awaitable, timeout):
        assert 0 < timeout <= 30
        # Exercise actual cancellation with a zero scheduling timeout; no sleeps.
        return await actual_wait_for(awaitable, timeout=0)

    monkeypatch.setattr(module, "wait_for", deterministic_timeout)

    def plan(snapshot):
        w, o = plan_for()(snapshot)
        w = type(w).model_validate(w.model_dump() | {"deadline_at": snapshot.updated_at + timedelta(seconds=30)})
        return (w, o)

    async def specialist(origin):
        if origin.agent_type == "WEATHER":
            cleaned.append("weather-started")
        return response(origin)

    report = run(specialist, plan=plan)
    assert not cleaned  # Callback was cancelled before it started.
    assert report.state.weather_findings == []
    assert len(report.state.ocean_findings) == 1
    assert report.budgets.active_specialists == 0
