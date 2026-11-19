"""Owned admission/receipt correlation and post-terminal-only raw revisions."""

import asyncio
from dataclasses import replace
from datetime import datetime

import pytest

from hawaii_activity_forecaster.orchestration import SessionError, SessionManager, SyntheticModelAdapter
from interpretation_samples import proposal, window
from raw_graph_samples import REFERENCE, TEXT, follow, initial_proposal, runner, scenario, start


@pytest.mark.parametrize("tamper", ["text", "identity", "revision", "clock", "catalog", "origins", "selection", "values", "prior"])
def test_session_replays_receipt_against_owned_admission_before_committing(tamper):
    async def corrupt(admission):
        report = await runner()(admission)
        if tamper == "text":
            report = replace(report, request_context=replace(report.request_context, original_request="Swim instead"))
        elif tamper == "identity":
            report = replace(report, request_receipt=replace(report.request_receipt, investigation_id="other"))
        elif tamper == "revision":
            report = replace(report, request_receipt=replace(report.request_receipt, request_revision=2))
        elif tamper == "clock":
            report = replace(report, request_context=replace(report.request_context, reference_time=datetime.fromisoformat("2026-11-16T10:00:00-10:00")))
        elif tamper == "catalog":
            report.request_context.catalog.root[0].sources.clear()
        elif tamper == "origins":
            report = replace(report, request_receipt=replace(report.request_receipt, origins=()))
        elif tamper == "selection":
            report = replace(report, selection=replace(report.selection, assessment_candidate_ids=()))
        elif tamper == "values":
            request = report.request_receipt.request.model_copy(update={"preferred_area": "Napili"})
            report = replace(report, request_receipt=replace(report.request_receipt, _request=request.model_dump_json().encode()))
        else:
            report = replace(report, request_context=replace(report.request_context, previous_investigation_id="unrelated"))
        return report
    session = SessionManager()
    with pytest.raises(SessionError, match="correlated"):
        asyncio.run(session.start_raw(TEXT, catalog=scenario().application.catalog, reference_time=REFERENCE, run=corrupt))
    assert not session.investigations and session.current is None
    with pytest.raises(SessionError, match="cannot accept more"):
        asyncio.run(start(session))


def test_terminal_failure_before_receipt_can_accept_a_complete_new_raw_request():
    async def exercise():
        session = SessionManager()
        calls = []
        async def fail(operation, inputs):
            calls.append(operation)
            raise RuntimeError("synthetic interpreter failure")
        first = await start(session, model_adapter=SyntheticModelAdapter(fail))
        assert first.state.status == "FAILED" and first.request_receipt is None
        assert first.state.activity is None and first.result is None
        second = await follow(session, TEXT, data=initial_proposal())
        assert second.state.status == "COMPLETED" and second.state.request_revision == 2
        assert second.request_context.inherited is None
        assert second.request_context.previous_investigation_id == first.state.investigation_id
        assert second.budgets.model_calls == 0 and second.budgets.tool_calls == 6
        assert calls == ["normalize_request"] and len(session.investigations) == 2
    asyncio.run(exercise())


def test_raw_ambiguity_and_elapsed_daypart_clarify_without_results_or_resumption():
    async def exercise(text, data, clock):
        session = SessionManager()
        events = []
        report = await start(session, text=text, data=data, reference_time=clock, events=events)
        assert report.state.status == "AWAITING_CLARIFICATION", report.state.completion_reason
        assert report.state.clarification_questions
        assert report.result is None and report.selection is None and report.result_validation is None
        assert report.budgets.iterations == report.budgets.tool_calls == report.budgets.model_calls == 0
        assert report.state.candidate_beach_ids == report.state.assessments == []
        assert not any(e.event_type in {"TOOL_CALLED", "AGENT_STARTED"} for e in events)
        with pytest.raises(SessionError, match="clarification resumption"):
            await follow(session, TEXT, data=initial_proposal())
        with pytest.raises(SessionError, match="follow_up_raw"):
            await session.follow_up(TEXT, changes={}, run=lambda admission: None)
    text = "Paddling tomorrow morning."
    data = proposal(text, {"target_date": "2026-11-17", "target_time_window": window()},
                    {"target_date": "tomorrow", "target_time_window": "morning"}, unresolved=["Paddling"])
    asyncio.run(exercise(text, data, REFERENCE))
    text = "Snorkel today afternoon only South Maui."
    # Today's already-started default stays 12:00–16:00; it is not clipped/rolled.
    data = proposal(text, {"activity": "SNORKELING", "target_date": "2026-11-17",
                           "target_time_window": window(start="12:00", end="16:00"),
                           "hard_constraints": [{"kind": "LOCATION_RESTRICTION", "scope": "REGION", "value": "SOUTH_MAUI"}]},
                    {"activity": "Snorkel", "target_date": "today", "target_time_window": "afternoon", "hard_constraints": "only South Maui"})
    asyncio.run(exercise(text, data, datetime.fromisoformat("2026-11-17T13:00:00-10:00")))


def test_active_raw_request_refuses_reentry_and_close_until_its_run_returns():
    async def exercise():
        session, entered, release = SessionManager(), asyncio.Event(), asyncio.Event()
        async def respond(operation, inputs):
            entered.set()
            await release.wait()
            return initial_proposal()
        task = asyncio.create_task(start(session, model_adapter=SyntheticModelAdapter(respond)))
        await asyncio.wait_for(entered.wait(), timeout=1)
        with pytest.raises(SessionError, match="terminal outcome"):
            await follow(session, "Near Napili instead.", data=proposal("Near Napili instead.", {"preferred_area": "Napili"}, {"preferred_area": "Near Napili"}))
        with pytest.raises(SessionError, match="active investigation"):
            session.close()
        release.set()
        report = await task
        assert report.state.status == "COMPLETED"
        session.close()
        with pytest.raises(SessionError, match="cannot accept more"):
            await follow(session, TEXT, data=initial_proposal())
    asyncio.run(exercise())


def test_raw_followup_daypart_replacement_keeps_assumed_precision_in_session():
    async def exercise():
        session = SessionManager()
        first = await start(session)
        text = "Tomorrow morning instead."
        data = proposal(text, {"target_date": "2026-11-18", "target_time_window": window("2026-11-18")},
                        {"target_date": "Tomorrow", "target_time_window": "morning"})
        # No source calls are authored for Nov 18; retain genuine missing-evidence
        # assessments rather than replay Nov 17's fixtures as current support.
        second = await follow(session, text, reference_time=datetime.fromisoformat("2026-11-17T07:00:00-10:00"),
                              data=data, planner=lambda inputs: ())
        assert second.state.status == "ABSTAINED", second.state.completion_reason
        assert second.state.target_time_window.model_dump(mode="json") == window("2026-11-18")
        assert first.state.target_time_window.model_dump(mode="json") == window()
        origin = next(o for o in second.request_receipt.origins if o.field == "target_time_window")
        assert origin.source == "DEFAULT" and origin.assumed
        assert "target_time_window" not in session.current.user_provided_fields
        assert session.current.assumed_fields == {"target_time_window"}
        assert second.budgets.model_calls == second.budgets.tool_calls == second.budgets.iterations == 0
        assert second.result.no_recommendation_reason == "INSUFFICIENT_EVIDENCE"
        assert "Assumed daypart window" in " ".join(second.result.general_warnings)
    asyncio.run(exercise())
