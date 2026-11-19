"""SL-T01..04/06..09: normalized session control, not full SC-012 acceptance."""

import asyncio
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from hawaii_activity_forecaster.demo import run_demo, run_session_demo
from hawaii_activity_forecaster.models import InvestigationState, NormalizedRequest, RecommendationResult
from hawaii_activity_forecaster.orchestration import (
    SessionError, SessionManager, run_skeleton, run_specialist_graph,
)
from hawaii_activity_forecaster.presentation import render_report
from specialist_samples import catalog, response
from test_specialist_graph import plan_for

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/scenario-pack-v1"
EXPLICIT = {"activity", "target_date", "target_time_window", "preferred_area", "experience_level", "soft_preferences"}


def normalized(**changes):
    return NormalizedRequest.model_validate(dict(
        original_request="Fictional snorkeling request near Kihei, with intermediate experience and calm-water preference",
        activity="SNORKELING", target_date="2026-11-17",
        target_time_window={"start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"},
        preferred_area="Kihei", experience_level="INTERMEDIATE", hard_constraints=[],
        soft_preferences=[{"preference": "calm water"}], clarification_needed=False, clarification_questions=[],
    ) | changes)


def runner(case="advisory", *, events=None, admissions=None):
    async def execute(admission):
        if admissions is not None:
            admissions.append(admission)
        output = await run_demo(case, FIXTURES, session_request=admission,
                                record_event=events.append if events is not None else None)
        return output.report
    return execute


def start(session, request=None, **kwargs):
    return asyncio.run(session.start(request if request is not None else normalized(),
                                    user_provided_fields=kwargs.pop("explicit", EXPLICIT), **kwargs))


def follow(session, changes=None, **kwargs):
    return asyncio.run(session.follow_up("Actually, prefer Wailea in this fictional example.",
                                        changes=changes if changes is not None else {"preferred_area": "Wailea"}, **kwargs))


def test_initial_admission_starts_with_identity_zero_budgets_and_no_inherited_state():
    session = SessionManager()
    assert session.request_revision == 0 and session.current is None and session.investigations == ()
    events, admissions = [], []
    report = start(session, run=runner(events=events, admissions=admissions))
    admission = admissions[0]
    assert session.request_revision == admission.request_revision == report.state.request_revision == 1
    assert session.session_id == admission.session_id == report.state.session_id
    assert admission.previous_investigation_id is None
    initial = events[0]
    assert initial.event_type == "INVESTIGATION_STARTED" and initial.details["status"] == "INITIALIZING"
    assert {initial.details[key] for key in ("iteration_count", "tool_call_count", "retry_count", "model_call_count")} == {0}
    assert initial.details["fallback_attempted"] is False
    assert initial.details["investigation_id"] == report.state.investigation_id
    assert "REQUEST_REVISED" not in [e.event_type for e in events]
    assert report.state.status == "COMPLETED" and report.budgets.tool_calls == 6


def test_geographic_follow_up_preserves_values_and_reassesses_without_mutating_history():
    session = SessionManager()
    events, admissions = [], []
    execute = runner(events=events, admissions=admissions)
    first = start(session, run=execute)
    frozen_first = deepcopy(first)
    first_events = deepcopy(events)
    second = follow(session, run=execute)
    assert first == frozen_first and events[:len(first_events)] == first_events
    assert first.state.investigation_id != second.state.investigation_id
    assert first.state.session_id == second.state.session_id == session.session_id
    assert [r.state.request_revision for r in session.investigations] == [1, 2]
    assert first.state.preferred_area == "Kihei" and second.state.preferred_area == "Wailea"
    for name in ("activity", "target_date", "target_time_window", "experience_level", "hard_constraints", "soft_preferences"):
        assert getattr(second.state, name) == getattr(first.state, name)
    assert second.state.original_request == "Actually, prefer Wailea in this fictional example."
    assert first.state.assessments and second.state.assessments
    assert {a.assessment_id for a in first.state.assessments}.isdisjoint(a.assessment_id for a in second.state.assessments)
    assert all(a.investigation_id == second.state.investigation_id for a in second.state.assessments)
    assert "Outside the preferred area" in first.result.recommendations[0].recommendation_reason
    assert "Matches the requested catalog area" in second.result.recommendations[0].recommendation_reason
    assert all(r.budgets.tool_calls == 6 and r.budgets.iterations == 1 for r in (first, second))
    # Earlier findings retain their original IDs, parents, timestamps and metadata.
    old = first.state.weather_findings + first.state.ocean_findings
    new = second.state.weather_findings + second.state.ocean_findings
    assert {f.finding_id for f in old}.isdisjoint(f.finding_id for f in new)
    assert all(f.investigation_id == first.state.investigation_id for f in old)
    assert all(f.investigation_id == second.state.investigation_id for f in new)
    assert sorted(f.retrieved_at for f in old) == sorted(f.retrieved_at for f in new)
    assert admissions[1].previous_investigation_id == first.state.investigation_id
    assert admissions[1].changed_fields == ("preferred_area",)


def test_each_investigation_has_separate_correlated_trace_events_and_revision():
    events = []
    session = SessionManager()
    first = start(session, run=runner(events=events))
    second = follow(session, run=runner(events=events))
    traces = {event.trace_id for event in events}
    assert len(traces) == 2
    for report in (first, second):
        subset = [e for e in events if e.details["investigation_id"] == report.state.investigation_id]
        assert subset and len({e.trace_id for e in subset}) == 1
        assert all(e.request_revision == report.state.request_revision and e.details["session_id"] == session.session_id for e in subset)
        assert [e.sequence_number for e in subset] == list(range(1, len(subset) + 1))
        assert subset[-1].event_type == "INVESTIGATION_COMPLETED"
        assert subset[-1].details["result_id"] == report.result.result_id
    revisions = [e for e in events if e.event_type == "REQUEST_REVISED"]
    assert len(revisions) == 1 and revisions[0].request_revision == 2
    assert revisions[0].related_ids == [first.state.investigation_id]
    assert revisions[0].details["previous_request_revision"] == 1
    assert revisions[0].details["changed_fields"] == ["preferred_area"]
    normalized_events = [e for e in events if e.event_type == "REQUEST_NORMALIZED"]
    assert [e.details["normalized_request"]["preferred_area"] for e in normalized_events] == ["Kihei", "Wailea"]
    assert all(e.details["normalized_request"]["soft_preferences"] == [{"preference": "calm water"}] for e in normalized_events)


def test_abstention_follow_up_resets_tool_retry_and_fallback_budgets():
    session = SessionManager()
    events = []
    first = start(session, run=runner("outage", events=events))
    assert first.state.status == "ABSTAINED"
    assert (first.budgets.tool_calls, first.budgets.retries, first.budgets.fallbacks) == (8, 1, 2)
    second = follow(session, run=runner(events=events))
    assert second.state.status == "COMPLETED"
    assert (second.budgets.tool_calls, second.budgets.retries, second.budgets.fallbacks) == (6, 0, 0)
    assert sum(r.budgets.tool_calls for r in session.investigations) == 14  # per-investigation limit, not per-session
    assert all(r.state.max_tool_calls == 12 and r.state.max_iterations == 5 and r.state.max_retries == 1
               for r in session.investigations)
    initial = next(e for e in events if e.event_type == "INVESTIGATION_STARTED" and e.request_revision == 2)
    assert initial.details["tool_call_count"] == initial.details["retry_count"] == 0
    assert initial.details["fallback_attempted"] is False
    assert session.investigations[0] == first


def test_follow_up_after_sanitized_technical_error_gets_a_new_investigation(monkeypatch):
    import hawaii_activity_forecaster.orchestration.skeleton as graph
    original = graph.compare_candidates
    def fail_once(context):
        if context.state.request_revision == 1:
            raise RuntimeError("SECRET synthetic execution problem")
        return original(context)
    monkeypatch.setattr(graph, "compare_candidates", fail_once)
    session = SessionManager()
    first = start(session, run=runner())
    assert first.state.status == "FAILED" and first.result.outcome == "ERROR"
    second = follow(session, run=runner())
    assert second.state.status == "COMPLETED" and second.state.request_revision == 2
    assert first.state.investigation_id != second.state.investigation_id
    assert "SECRET" not in str(session.investigations)


def test_trace_write_failure_preserves_diagnostics_and_new_work_gets_its_own_recorder():
    events = []
    def fail(event):
        if event.event_type == "RESULT_VALIDATED":
            raise OSError("SECRET trace failure")
        events.append(event)
    async def broken(admission):
        return (await run_demo("advisory", FIXTURES, session_request=admission, record_event=fail)).report
    session = SessionManager()
    first = start(session, run=broken)
    assert first.state.status == "FAILED" and first.result is None and not first.trace_writable
    before = deepcopy(events)
    second = follow(session, run=runner())
    assert second.state.status == "COMPLETED" and second.trace_writable
    assert events == before and session.investigations[0] == first


@pytest.mark.parametrize("event_type", ["REQUEST_REVISED", "REQUEST_NORMALIZED"])
def test_revision_or_normalization_recording_failure_stops_before_dispatch(event_type):
    session = SessionManager()
    first = start(session, run=runner())
    def fail(event):
        if event.event_type == event_type:
            raise OSError("SECRET synthetic recording error")
    async def execute(admission):
        return (await run_demo("advisory", FIXTURES, session_request=admission, record_event=fail)).report
    second = follow(session, run=execute)
    assert second.state.status == "FAILED" and second.state.completion_reason == "TRACE_WRITE_FAILED"
    assert second.result is None and not second.trace_writable
    assert second.budgets.tool_calls == second.budgets.model_calls == second.budgets.iterations == 0
    assert session.investigations[0] == first and second.state.request_revision == 2


def test_constraint_origin_metadata_is_preserved_without_converting_preferences():
    session = SessionManager()
    events = []
    initial = normalized(hard_constraints=[{"requirement": "fictional requirement requiring interpretation"}])
    explicit = {"activity", "target_time_window", "hard_constraints", "soft_preferences"}
    first = start(session, initial, explicit=explicit, run=runner(events=events))
    assert first.state.status == "ABSTAINED"  # opaque constraints still UNKNOWN
    assert session.current.assumed_fields == {"target_date", "preferred_area", "experience_level"}
    second = follow(session, run=runner(events=events))
    assert second.state.hard_constraints == initial.hard_constraints
    assert second.state.soft_preferences == initial.soft_preferences
    assert second.state.status == "ABSTAINED"
    assert session.current.user_provided_fields == explicit | {"preferred_area"}
    assert session.current.assumed_fields == {"target_date", "experience_level"}
    assert all(c.result == "UNKNOWN" for a in second.state.assessments for c in a.hard_constraint_results)
    latest = [e for e in events if e.event_type == "REQUEST_NORMALIZED"][-1]
    assert latest.details["assumed_fields"] == ["experience_level", "target_date"]


@pytest.mark.parametrize("changes", [
    {"preferred_area": None, "experience_level": None, "soft_preferences": []},
    {"activity": "SWIMMING"},
    {"target_date": "2026-11-18", "target_time_window": {
        "start": "2026-11-18T08:00:00-10:00", "end": "2026-11-18T11:00:00-10:00"}},
    {},
])
def test_explicit_updates_clears_or_repeated_request_only_replace_supplied_fields(changes):
    session = SessionManager()
    first = start(session, run=runner())
    second = follow(session, changes, run=runner())
    expected = normalized(**changes).model_dump(mode="json")
    actual = second.state.model_dump(mode="json")
    for name in NormalizedRequest.model_fields.keys() - {"original_request"}:
        assert actual[name] == expected[name]
    if "target_date" in changes:
        # The existing authored tool script permits only its fixed request
        # signature. A different window requires a different component fixture;
        # it cannot inherit prior eligibility or be rewritten to the old time.
        assert second.state.status == "FAILED" and not second.result.recommendations
        assert all(a.eligibility != "ELIGIBLE" for a in second.state.assessments)
        assert {a.assessment_id for a in first.state.assessments}.isdisjoint(a.assessment_id for a in second.state.assessments)
    assert second.state.request_revision == 2


@pytest.mark.parametrize("changes", [
    {"session_id": "injected"}, {"request_revision": 99}, {"weather_findings": []}, {"original_request": "override"},
    {"activity": "SURFING"}, {"hard_constraints": None}, {"preferred_area": ""},
    {"target_date": "2026-11-20"}, {"target_time_window": {"start": "yesterday", "end": "tomorrow"}},
    {"clarification_needed": "false"}, None,
])
def test_invalid_follow_up_never_dispatches_or_changes_current_context(changes):
    session = SessionManager()
    first = start(session, run=runner())
    before = session.current
    async def forbidden(context):
        pytest.fail("Invalid normalized changes dispatched")
    with pytest.raises(SessionError):
        asyncio.run(session.follow_up("Invalid fictional follow-up", changes=changes, run=forbidden))
    assert session.current == before and session.request_revision == 1
    assert session.investigations == (first,)


def test_snapshots_and_input_lists_cannot_mutate_current_context_or_history():
    session = SessionManager()
    request = normalized()
    first = start(session, request, run=runner())
    expected = session.investigations
    request.soft_preferences[0]["preference"] = "caller mutation"
    first.result.recommendations[0].warnings.append("caller mutation")
    session.investigations[0].state.soft_preferences.clear()
    session.current.request.soft_preferences.clear()
    assert session.investigations == expected
    assert session.current.request.soft_preferences == [{"preference": "calm water"}]
    with pytest.raises(FrozenInstanceError):
        session.current.request_revision = 80
    second = follow(session, run=runner())
    assert second.state.soft_preferences == [{"preference": "calm water"}]


@pytest.mark.parametrize("changes", [
    {"activity": None}, {"target_time_window": None},
    {"clarification_needed": True, "clarification_questions": ["Which fictional location did you mean?"]},
])
def test_material_ambiguity_preserves_context_but_never_recommends_or_resumes(changes):
    session = SessionManager()
    first = start(session, run=runner())
    events = []
    second = follow(session, changes, run=runner(events=events))
    assert second.state.status == "AWAITING_CLARIFICATION" and second.result is None
    assert second.state.clarification_needed and second.state.clarification_questions
    assert second.budgets.tool_calls == second.budgets.model_calls == second.budgets.iterations == 0
    assert second.state.assessments == second.state.weather_findings == second.state.ocean_findings == []
    assert second.state.experience_level == first.state.experience_level
    assert second.state.soft_preferences == first.state.soft_preferences
    assert [e.event_type for e in events][-1] == "CLARIFICATION_REQUESTED"
    with pytest.raises(SessionError, match="clarification resumption is deferred"):
        follow(session, run=runner())
    assert session.request_revision == 2 and session.investigations[0] == first


def test_initial_ambiguity_is_not_reinterpreted_as_a_terminal_outcome():
    session = SessionManager()
    report = start(session, normalized(activity=None), run=runner())
    assert report.state.status == "AWAITING_CLARIFICATION" and report.state.outcome is None
    assert report.state.result_id is None and report.budgets.tool_calls == 0
    with pytest.raises(SessionError):
        start(session, run=runner())


def test_active_investigation_refinements_and_session_close_cannot_interrupt_work():
    async def exercise():
        session = SessionManager()
        entered, release = asyncio.Event(), asyncio.Event()
        async def waiting(admission):
            entered.set()
            await release.wait()
            return await runner()(admission)
        task = asyncio.create_task(session.start(normalized(), user_provided_fields=EXPLICIT, run=waiting))
        await asyncio.wait_for(entered.wait(), timeout=2)
        before = session.current
        with pytest.raises(SessionError, match="terminal"):
            await session.follow_up("Interrupt", changes={"activity": "SWIMMING"}, run=runner())
        with pytest.raises(SessionError, match="terminal"):
            await session.start(normalized(), user_provided_fields=EXPLICIT, run=runner())
        with pytest.raises(SessionError, match="cannot be interrupted"):
            session.close()
        assert session.current == before and session.request_revision == 1
        release.set()
        report = await asyncio.wait_for(task, timeout=3)
        assert report.state.status == "COMPLETED"
        return session
    session = asyncio.run(exercise())
    assert follow(session, run=runner()).state.request_revision == 2


@pytest.mark.parametrize("kind", ["old-investigation", "old-revision"])
def test_stale_specialist_response_cannot_enter_the_follow_up(kind):
    session = SessionManager()
    saved = []
    events = []
    def plan(snapshot):
        return tuple(request.model_validate(request.model_dump() | {"request_revision": snapshot.request_revision})
                     for request in plan_for(("WEATHER",))(snapshot))
    async def specialist(origin):
        if not saved:
            saved.append(response(origin))
            return saved[0]
        old = saved[0]
        if kind == "old-revision":
            # An otherwise current response carrying the old revision, rather
            # than relabeling the saved finding's original parent identity.
            old = response(origin, request_revision=saved[0].request_revision)
        return old.model_validate(old.model_dump() | {"status": "PARTIAL", "errors": [{
            "error_id": "stale-error", "error_code": "SOURCE_UNAVAILABLE", "message": "SECRET raw diagnostic",
            "retryable": False,
        }]})
    async def execute(admission):
        # The shared test plan stops after its first cycle.
        def bounded(snapshot):
            return () if snapshot.iteration_count else plan(snapshot)
        return await run_specialist_graph(admission.request, catalog=catalog(), candidate_beach_ids=("TEST_BEACH_A",),
                                          plan=bounded, specialist=specialist, session_request=admission,
                                          record_event=events.append)
    first = start(session, run=execute)
    assert first.state.weather_findings
    before = deepcopy(first)
    second = follow(session, run=execute)
    assert second.state.weather_findings == second.state.ocean_findings == second.state.assessments == []
    assert second.state.preferred_area == "Wailea" and second.state.request_revision == 2
    rejected = [e for e in events if e.request_revision == 2 and e.event_type == "CONTRACT_VALIDATED"
                and e.details.get("contract") == "specialist_response" and e.details.get("valid") is False]
    assert rejected and saved[0].investigation_id == first.state.investigation_id
    assert rejected[0].details["response_id"] == saved[0].response_id
    observed = rejected[0].details["response_correlation"]
    assert observed["request_revision"] == 1
    assert observed["investigation_id"] == (first.state.investigation_id if kind == "old-investigation" else second.state.investigation_id)
    assert observed["request_id"] == saved[0].request_id and observed["attempt_number"] == 1
    assert rejected[0].details["reason"] == "OUTDATED_RESPONSE"
    assert "SECRET" not in str([e.model_dump() for e in events])
    assert first == before and session.investigations[0] == before


@pytest.mark.parametrize("damage", ["revision", "session", "request", "old-report", "budget", "result", "foreign-finding"])
def test_mismatched_or_stale_runner_reports_cannot_replace_session_history(damage):
    session = SessionManager()
    first = start(session, run=runner())
    async def corrupt(admission):
        report = await runner()(admission)
        if damage == "old-report":
            return first
        if damage == "budget":
            return replace(report, budgets=replace(report.budgets, closed=False))
        if damage == "result":
            return replace(report, result=RecommendationResult.model_validate(report.result.model_dump() | {"request_revision": 1}))
        data = report.state.model_dump()
        if damage == "foreign-finding":
            data["weather_findings"][0]["investigation_id"] = first.state.investigation_id
        else:
            data.update({"revision": {"request_revision": 1}, "session": {"session_id": "other-session"},
                         "request": {"preferred_area": "other-area"}}[damage])
        return replace(report, state=InvestigationState.model_validate(data))
    with pytest.raises(SessionError, match="correlated investigation"):
        follow(session, run=corrupt)
    assert session.investigations == (first,)
    with pytest.raises(SessionError, match="start a new session"):
        follow(session, run=runner())


def test_unexpected_runner_exception_or_cancellation_never_fabricates_a_terminal_state():
    session = SessionManager()
    async def fail(context):
        raise RuntimeError("SECRET runner exception")
    with pytest.raises(SessionError) as caught:
        start(session, run=fail)
    assert "SECRET" not in str(caught.value) and session.investigations == ()
    with pytest.raises(SessionError, match="start a new session"):
        follow(session, run=runner())
    async def exercise():
        session = SessionManager()
        entered = asyncio.Event()
        async def cancelled(context):
            entered.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(session.start(normalized(), user_provided_fields=EXPLICIT, run=cancelled))
        await asyncio.wait_for(entered.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert session.investigations == ()
        with pytest.raises(SessionError, match="start a new session"):
            await session.follow_up("Try again", changes={}, run=runner())
    asyncio.run(exercise())


@pytest.mark.parametrize("fields", ["activity", {"request_revision"}, {"unknown"}, None, [None]])
def test_invalid_provenance_declaration_does_not_admit_a_request(fields):
    session = SessionManager()
    with pytest.raises(SessionError):
        start(session, explicit=fields, run=runner())
    assert session.request_revision == 0 and session.current is None


def test_closed_and_new_sessions_do_not_resume_prior_work():
    session = SessionManager()
    with pytest.raises(SessionError):
        follow(session, run=runner())
    first = start(session, run=runner())
    with pytest.raises(SessionError):
        start(session, run=runner())
    session.close()
    with pytest.raises(SessionError, match="start a new session"):
        follow(session, run=runner())
    new = SessionManager()
    second = start(new, run=runner())
    assert new.session_id != session.session_id and new.request_revision == 1
    assert first.state.investigation_id != second.state.investigation_id
    with pytest.raises(SessionError):
        start(SessionManager(), first.state, run=runner())  # a prior state is not a normalized new request


@pytest.mark.parametrize("damage", [
    "request", "session-override", "revision-zero", "revision-bool", "prior-on-first", "missing-prior", "unknown-field",
])
def test_graph_rejects_mismatched_session_admission_before_recording_or_dispatch(damage):
    session = SessionManager()
    first = start(session, run=runner())
    context = session.current
    request = context.request
    kwargs = {}
    if damage == "request":
        request = normalized(preferred_area="Napili")
    elif damage == "session-override":
        kwargs["session_id"] = "other-session"
    else:
        changes = {"revision-zero": {"request_revision": 0}, "revision-bool": {"request_revision": True},
                   "prior-on-first": {"previous_investigation_id": first.state.investigation_id},
                   "missing-prior": {"request_revision": 2}, "unknown-field": {"user_provided_fields": frozenset({"unknown"})}}
        context = replace(context, **changes[damage])
    events = []
    async def forbidden(branch):
        pytest.fail("Mismatched session admission dispatched a specialist")
    with pytest.raises(ValueError):
        asyncio.run(run_skeleton(request, candidate_beach_ids=("TEST_BEACH_A",), branch=forbidden,
                                 record_event=events.append, session_request=context, **kwargs))
    assert events == [] and session.investigations == (first,)


def test_session_component_demo_renders_two_revisions_without_claiming_sc012_acceptance():
    events = []
    output = asyncio.run(run_session_demo(FIXTURES, record_event=events.append))
    first, second = output.investigations
    assert first.report.state.session_id == second.report.state.session_id
    assert [entry.report.state.request_revision for entry in output.investigations] == [1, 2]
    for entry in output.investigations:
        assert entry.report.budgets.tool_calls == 6 and entry.report.budgets.model_calls == 0
        assert "SYNTHETIC TEST OUTPUT" in render_report(entry.report, catalog=entry.catalog, policy=entry.policy)
    assert any(e.event_type == "REQUEST_REVISED" for e in events)
