"""RI-T09/14..18/21..22 raw component integration, not full M1 acceptance."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime

import pytest

from hawaii_activity_forecaster.models import BeachCatalog
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.orchestration import SessionManager
from hawaii_activity_forecaster.presentation import PresentationError, render_report
from interpretation_samples import proposal, window
from raw_graph_samples import AB, REFERENCE, follow, initial_proposal, plan, scenario, start


def test_raw_admission_normalization_and_dispatch_share_one_investigation():
    session = SessionManager()
    events, interpreted, planned = [], [], []
    def interpret(inputs):
        interpreted.append(inputs)
        assert session.request_revision == 1 and session.current is None
        assert [e.event_type for e in events] == ["INVESTIGATION_STARTED", "REQUEST_RECEIVED"]
        assert not hasattr(inputs, "models") and not hasattr(inputs, "script")
        return initial_proposal()
    def choose(inputs):
        planned.append(inputs)
        assert inputs.investigation_candidate_ids == inputs.planning_order == AB
        assert tuple(inputs.state.candidate_beach_ids) == (*AB, "TEST_BEACH_E")
        assert tuple(inputs.state.remaining_candidate_ids) == AB
        return plan(inputs)
    report = asyncio.run(start(session, interpreter=interpret, planner=choose, events=events))
    assert report.state.status == "COMPLETED", report.state.completion_reason
    assert report.result.outcome == "RECOMMENDATIONS"
    assert [r.beach_id for r in report.result.recommendations] == ["TEST_BEACH_B"]
    assert report.budgets.iterations == 1 and report.budgets.tool_calls == 6 and report.budgets.model_calls == 0
    assert report.request_receipt.investigation_id == interpreted[0].investigation_id == report.state.investigation_id
    assert report.request_receipt.request == session.current.request
    assert {e.details["investigation_id"] for e in events} == {report.state.investigation_id}
    assert {e.request_revision for e in events} == {1}
    assert report.visited_nodes[:4] == ("initialize_investigation", "normalize_request", "select_candidates", "validate_request")
    normalized = next(e for e in events if e.event_type == "REQUEST_NORMALIZED")
    assert normalized.details["assumed_fields"] == ["target_time_window"]
    assert normalized.details["reference_time"] == REFERENCE.isoformat()
    assert normalized.details["origins"]
    selected = next(e for e in events if e.details.get("contract") == "candidate_selection")
    assert selected.details["investigation_candidate_ids"] == list(AB)
    assert selected.details["decisions"][0]["sources"][0]["supports_fields"]
    assert {a.beach_id: a.eligibility for a in report.state.assessments} == {
        "TEST_BEACH_A": "EXCLUDED", "TEST_BEACH_B": "ELIGIBLE", "TEST_BEACH_E": "UNSUPPORTED",
    }
    rendered = render_report(report, catalog=scenario().application.catalog, policy=scenario().application.policy_configuration)
    assert "Assumed daypart window" in rendered and "not for real activity planning" in rendered
    assert not any(e.details.get("synthetic_adapter") for e in events)


def test_post_terminal_raw_followup_preserves_absolute_context_origins_and_history():
    async def exercise():
        session = SessionManager()
        first = await start(session)
        before = deepcopy(first)
        events = []
        text = "Near Napili instead."
        second = await follow(session, text, reference_time=datetime.fromisoformat("2026-11-17T07:00:00-10:00"),
                              data=proposal(text, {"preferred_area": "Napili"}, {"preferred_area": "Near Napili"}), events=events)
        assert first == before and session.investigations[0] == before
        assert second.state.status == "COMPLETED", second.state.completion_reason
        assert first.state.session_id == second.state.session_id == session.session_id
        assert first.state.investigation_id != second.state.investigation_id
        assert second.state.request_revision == 2
        for field in ("activity", "target_date", "target_time_window", "hard_constraints", "experience_level"):
            assert getattr(second.state, field) == getattr(first.state, field)
        origin = next(o for o in second.request_receipt.origins if o.field == "target_time_window")
        assert origin.source == "INHERITED" and origin.assumed and origin.default_rule == "morning"
        assert origin.inherited_from == first.state.investigation_id
        assert session.current.assumed_fields == {"target_time_window"}
        assert second.budgets.tool_calls == 6 and second.budgets.iterations == 1 and second.budgets.model_calls == 0
        assert not ({f.finding_id for f in first.state.weather_findings + first.state.ocean_findings}
                    & {f.finding_id for f in second.state.weather_findings + second.state.ocean_findings})
        revised = next(e for e in events if e.event_type == "REQUEST_REVISED")
        assert revised.related_ids == [first.state.investigation_id]
        assert revised.details["previous_request_revision"] == 1
        assert "Assumed daypart window" in " ".join(second.result.general_warnings)
        # Returned receipts/requests/history cannot be mutated into session authority.
        second.request_receipt.request.hard_constraints.clear()
        second.state.hard_constraints.clear()
        assert session.investigations[1].state.hard_constraints == before.state.hard_constraints
    asyncio.run(exercise())


@pytest.mark.parametrize("catalog_change,assessment_ids", [
    (lambda records: [], ()),
    (lambda records: [b | {"catalog_status": "DISABLED"} for b in records], ()),
    (lambda records: [b for b in records if b["beach_id"] == "TEST_BEACH_E"], ("TEST_BEACH_E",)),
])
def test_grounded_empty_dispatch_selection_abstains_without_fake_assessments(catalog_change, assessment_ids):
    sample = scenario()
    catalog = BeachCatalog.model_validate(catalog_change(sample.application.catalog.model_dump()))
    events = []
    def no_work(inputs):
        pytest.fail("An empty investigation selection must not invoke the planner")
    text = "Snorkel tomorrow morning."
    data = proposal(text, {"activity": "SNORKELING", "target_date": "2026-11-17", "target_time_window": window()},
                    {"activity": "Snorkel", "target_date": "tomorrow", "target_time_window": "morning"})
    policy = PolicyConfiguration.model_validate(sample.application.policy_configuration.model_dump() |
                                                {"evidence_rules": [], "premises": []})
    report = asyncio.run(start(SessionManager(), text=text, data=data, catalog=catalog, planner=no_work, events=events, policy=policy))
    assert report.state.status == "ABSTAINED", report.state.completion_reason
    assert report.result.no_recommendation_reason == "NO_ELIGIBLE_CANDIDATES"
    assert report.result_validation.stop_reason == "NO_SUPPORTED_CANDIDATES"
    assert report.budgets.iterations == report.budgets.tool_calls == report.budgets.model_calls == 0
    assert tuple(report.state.candidate_beach_ids) == assessment_ids
    assert tuple(a.beach_id for a in report.state.assessments) == assessment_ids
    assert all(a.eligibility == "UNSUPPORTED" for a in report.state.assessments)
    assert not report.tool_bindings and not report.result.unresolved_issues
    assert report.result.general_limitations and "catalog" in report.result.explanation
    assert not any(e.event_type in {"TOOL_CALLED", "CANDIDATE_EXCLUDED", "AGENT_STARTED"} for e in events)
    kinds = [e.event_type for e in events]
    assert kinds.index("RESULT_VALIDATED") < kinds.index("INVESTIGATION_ABSTAINED")
    assert "No recommendation" in render_report(report, catalog=catalog, policy=policy)


@pytest.mark.parametrize("corruption", ["scope", "receipt", "clock", "catalog", "origin", "stop", "disclosure"])
def test_presenter_rechecks_raw_receipt_selection_and_disclosures(corruption):
    sample = scenario()
    report = asyncio.run(start(SessionManager()))
    if corruption == "scope":
        report = replace(report, selection=replace(report.selection, investigation_candidate_ids=()))
    elif corruption == "receipt":
        report = replace(report, request_receipt=replace(report.request_receipt, investigation_id="old-investigation"))
    elif corruption == "clock":
        report = replace(report, request_context=replace(report.request_context, reference_time=datetime.fromisoformat("2026-11-16T10:00:00-10:00")))
    elif corruption == "catalog":
        report.request_context.catalog.root[0].sources.clear()
    elif corruption == "origin":
        report = replace(report, request_receipt=replace(report.request_receipt, origins=()))
    elif corruption == "stop":
        report = replace(report, result_validation=replace(report.result_validation, stop_reason="NO_SUPPORTED_CANDIDATES"))
    else:
        report.result.general_warnings.pop()
    with pytest.raises(PresentationError):
        render_report(report, catalog=sample.application.catalog, policy=sample.application.policy_configuration)


def test_soft_preference_preserves_all_candidates_and_discloses_unfinished_work():
    text = "Snorkel tomorrow morning near Napili; prefer calm water."
    data = proposal(text, {"activity": "SNORKELING", "target_date": "2026-11-17", "target_time_window": window(),
                           "preferred_area": "Napili", "soft_preferences": [{"kind": "CALM_WATER"}]},
                    {"activity": "Snorkel", "target_date": "tomorrow", "target_time_window": "morning",
                     "preferred_area": "near Napili", "soft_preferences": "prefer calm water"})
    orders = []
    def choose(inputs):
        orders.append(inputs.planning_order)
        return plan(inputs)  # Explicit component work on A/B; no oracle-driven work selection.
    report = asyncio.run(start(SessionManager(), text=text, data=data, planner=choose))
    assert report.state.status == "COMPLETED", report.state.completion_reason
    assert orders[0] == ("TEST_BEACH_C", "TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_D")
    assert len(report.state.candidate_beach_ids) == 5 and len(report.selection.investigation_candidate_ids) == 4
    assert [r.beach_id for r in report.result.recommendations] == ["TEST_BEACH_B"]
    assert report.result.recommendations[0].preference_alignment == []
    assert any("UNKNOWN" in item for item in report.result.general_limitations)
    unfinished = next(item for item in report.result.general_limitations if "remain incomplete" in item)
    catalog = scenario().application.catalog
    for beach in catalog.root:
        if beach.beach_id in {"TEST_BEACH_C", "TEST_BEACH_D"}:
            assert beach.name in unfinished
    assert "Outside the preferred area" in report.result.recommendations[0].recommendation_reason
