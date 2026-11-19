"""Explicit normalized merge, current-text authority and inherited precision."""

from dataclasses import replace
from datetime import datetime

import pytest

from hawaii_activity_forecaster.interpretation import RequestValidationError, validate_request, verify_request
from interpretation_samples import context, morning, proposal, span, window


def parent():
    text = "Snorkel tomorrow afternoon only South Maui; prefer calm water. I'm intermediate."
    ctx = context(text)
    hard = {"kind": "LOCATION_RESTRICTION", "scope": "REGION", "value": "SOUTH_MAUI"}
    data = proposal(text, {"activity": "SNORKELING", "target_date": "2026-11-17", "target_time_window": window(start="12:00", end="16:00"),
                          "hard_constraints": [hard], "soft_preferences": [{"kind": "CALM_WATER"}], "experience_level": "INTERMEDIATE"},
                    {"activity": "Snorkel", "target_date": "tomorrow", "target_time_window": "afternoon", "hard_constraints": "only South Maui",
                     "soft_preferences": "prefer calm water", "experience_level": "intermediate"})
    result = validate_request(data, ctx)
    assert not result.request.clarification_needed
    return ctx, result


def child(text, previous, **kwargs):
    return context(text, investigation_id="follow-up-investigation", request_revision=2, inherited=previous,
                   prior_status="COMPLETED", **kwargs)


def test_geographic_only_followup_preserves_absolute_window_constraints_and_default_origin():
    old_ctx, previous = parent()
    before = previous.request.model_dump_json()
    text = "Actually, let's look near Napili instead."
    ctx = child(text, previous, reference_time=datetime.fromisoformat("2026-11-17T09:00:00-10:00"))
    receipt = validate_request(proposal(text, {"preferred_area": "Napili"}, {"preferred_area": "near Napili"}), ctx)
    assert not receipt.request.clarification_needed
    assert receipt.request.target_time_window == previous.request.target_time_window
    for field in ("activity", "target_date", "experience_level", "hard_constraints", "soft_preferences"):
        assert getattr(receipt.request, field) == getattr(previous.request, field)
    assert receipt.request.original_request == text and receipt.request.preferred_area == "Napili"
    origin = next(o for o in receipt.origins if o.field == "target_time_window")
    assert origin.source == "INHERITED" and origin.assumed and origin.default_rule == "afternoon"
    assert origin.inherited_from == previous.investigation_id and origin.span is None
    assert receipt.changed_fields == ("preferred_area",)
    assert previous.request.model_dump_json() == before and verify_request(previous, old_ctx) == previous


def test_explicit_new_daypart_uses_current_clock_but_retains_assumed_hour_precision():
    _, previous = parent()
    text = "Tomorrow morning instead."
    ctx = child(text, previous, reference_time=datetime.fromisoformat("2026-11-17T09:00:00-10:00"))
    receipt = validate_request(proposal(text, {"target_date": "2026-11-18", "target_time_window": window("2026-11-18")},
                                       {"target_date": "Tomorrow", "target_time_window": "morning"}), ctx)
    assert not receipt.request.clarification_needed and receipt.request.target_date.isoformat() == "2026-11-18"
    origin = next(o for o in receipt.origins if o.field == "target_time_window")
    assert origin.source == "DEFAULT" and origin.assumed and origin.default_rule == "morning"
    assert "target_time_window" not in receipt.user_provided_fields


def test_explicit_hours_without_date_keep_inherited_day_and_override_precision():
    _, previous = parent()
    text = "Try from 1 to 3 p.m. instead."
    receipt = validate_request(proposal(text, {"target_time_window": window(start="13:00", end="15:00")},
                                       {"target_time_window": "from 1 to 3 p.m."}), child(text, previous))
    assert not receipt.request.clarification_needed
    assert receipt.request.target_date == previous.request.target_date
    assert receipt.assumed_fields == set() and "target_time_window" in receipt.user_provided_fields


def test_date_only_revision_moves_window_without_inventing_new_hours():
    _, previous = parent()
    text = "Try on 2026-11-18 instead."
    receipt = validate_request(proposal(text, {"target_date": "2026-11-18"}, {"target_date": "2026-11-18"}), child(text, previous))
    assert not receipt.request.clarification_needed
    assert receipt.request.target_time_window.model_dump(mode="json") == window("2026-11-18", "12:00", "16:00")
    assert receipt.assumed_fields == {"target_time_window"}


def test_activity_change_does_not_discard_constraints_or_convert_preferences():
    _, previous = parent()
    text = "What about swimming?"
    receipt = validate_request(proposal(text, {"activity": "SWIMMING"}, {"activity": "swimming"}), child(text, previous))
    assert not receipt.request.clarification_needed and receipt.request.activity == "SWIMMING"
    assert receipt.request.hard_constraints == previous.request.hard_constraints
    assert receipt.request.soft_preferences == previous.request.soft_preferences


def test_anywhere_is_fine_clears_only_soft_area_preference():
    ctx, data = morning()
    previous = validate_request(data, ctx)
    # Add a hard restriction in a second separately validated interpretation.
    text = "Only South Maui."
    item = {"kind": "LOCATION_RESTRICTION", "scope": "REGION", "value": "SOUTH_MAUI"}
    hard = validate_request(proposal(text, {"hard_constraints": [item]}, {"hard_constraints": text.removesuffix(".")}), child(text, previous))
    text = "Anywhere is fine."
    ctx = context(text, inherited=hard, prior_status="COMPLETED", request_revision=3, investigation_id="third-investigation")
    receipt = validate_request(proposal(text, {"preferred_area": None}, {"preferred_area": "Anywhere is fine"}), ctx)
    assert not receipt.request.clarification_needed
    assert receipt.request.preferred_area is None and receipt.request.hard_constraints == [item]


def test_precise_list_removal_preserves_other_entries_and_reindexes_origins():
    _, previous = parent()
    text = "Remove calm water preference."
    removed = span(text, "Remove calm water preference", field="soft_preferences", previous_index=0)
    receipt = validate_request(proposal(text, {"soft_preferences": []}, {}, removed=[removed]), child(text, previous))
    assert not receipt.request.clarification_needed and receipt.request.soft_preferences == []
    assert receipt.request.hard_constraints == previous.request.hard_constraints
    assert not any(o.field == "soft_preferences" for o in receipt.origins)


def test_unique_restriction_removal_is_supported_but_ambiguous_removal_clarifies():
    _, previous = parent()
    text = "Remove that restriction."
    data = proposal(text, {"hard_constraints": []}, {},
                    removed=[span(text, "Remove that restriction", field="hard_constraints", previous_index=0)])
    receipt = validate_request(data, child(text, previous))
    assert not receipt.request.hard_constraints and not receipt.request.clarification_needed
    text = "Only Kihei."
    extra = previous.request.hard_constraints + [{"kind": "LOCATION_RESTRICTION", "scope": "LOCALITY", "value": "Kihei"}]
    second = validate_request(proposal(text, {"hard_constraints": extra}, {"hard_constraints": "Only Kihei"}), child(text, previous))
    text = "Remove that restriction."
    ambiguous_ctx = context(text, inherited=second, prior_status="COMPLETED", request_revision=3, investigation_id="third")
    ambiguous = validate_request(proposal(text, {}, {}), ambiguous_ctx)
    assert ambiguous.request.clarification_needed and ambiguous.request.hard_constraints == extra


def test_explicit_nullable_clear_is_recorded_without_inventing_defaults():
    _, previous = parent()
    text = "Clear experience level."
    receipt = validate_request(proposal(text, {"experience_level": None}, {"experience_level": "Clear experience level"}), child(text, previous))
    assert receipt.request.experience_level is None and not receipt.request.clarification_needed


@pytest.mark.parametrize("change", [{"hard_constraints": []}, {"soft_preferences": []}, {"activity": "SUP"}, {"target_date": "2026-11-18"}])
def test_geographic_followup_cannot_erase_or_modify_unmentioned_values(change):
    _, previous = parent()
    text = "Near Napili instead."
    data = proposal(text, {"preferred_area": "Napili"} | change, {"preferred_area": "Near Napili"})
    with pytest.raises(RequestValidationError):
        validate_request(data, child(text, previous))


@pytest.mark.parametrize("kwargs", [{"prior_status": None}, {"prior_status": "AWAITING_CLARIFICATION"}, {"session_id": "other"},
                                  {"investigation_id": "synthetic-investigation"}, {"request_revision": 1}, {"request_revision": 3}])
def test_followup_scope_cannot_resume_old_work_or_skip_revision(kwargs):
    _, previous = parent()
    ctx = replace(child("Near Napili instead.", previous), **kwargs)
    with pytest.raises(RequestValidationError):
        validate_request(proposal(ctx.original_request, {"preferred_area": "Napili"}, {"preferred_area": "Near Napili"}), ctx)


def test_nonterminal_ambiguity_and_elapsed_inherited_window_cannot_bypass_clarification():
    text = "Swim tomorrow."
    first = validate_request(proposal(text, {"activity": "SWIMMING", "target_date": "2026-11-17"},
                                     {"activity": "Swim", "target_date": "tomorrow"}), context(text))
    with pytest.raises(RequestValidationError):
        validate_request(proposal("Morning instead.", {}, {}), child("Morning instead.", first))
    _, previous = parent()
    text = "Near Napili instead."
    later = child(text, previous, reference_time=datetime.fromisoformat("2026-11-18T09:00:00-10:00"))
    result = validate_request(proposal(text, {"preferred_area": "Napili"}, {"preferred_area": "Near Napili"}), later)
    assert result.request.clarification_needed and result.request.target_time_window == previous.request.target_time_window


def test_unrelated_uninterpreted_preference_does_not_clear_existing_geography():
    ctx, data = morning()
    previous = validate_request(data, ctx)
    text = "Prefer more shade."
    item = {"kind": "UNINTERPRETED", "text": "Prefer more shade"}
    receipt = validate_request(proposal(text, {"soft_preferences": [item]}, {"soft_preferences": "Prefer more shade"}), child(text, previous))
    assert not receipt.request.clarification_needed and receipt.request.preferred_area == "Kihei"
    assert receipt.request.soft_preferences == [item] and receipt.limitations


def test_starting_location_context_is_preserved_with_original_investigation_reference():
    text = "I'm staying in Kihei. Snorkel tomorrow morning."
    ctx = context(text)
    previous = validate_request(proposal(text, {"activity": "SNORKELING", "target_date": "2026-11-17", "target_time_window": window()},
                                        {"activity": "Snorkel", "target_date": "tomorrow", "target_time_window": "morning"}), ctx)
    text = "Near Napili instead."
    current = validate_request(proposal(text, {"preferred_area": "Napili"}, {"preferred_area": "Near Napili"}), child(text, previous))
    location = current.starting_locations[0]
    assert location.value == "Kihei" and location.inherited_from == previous.investigation_id and location.span is None
    assert current.request.preferred_area == "Napili" and not current.request.hard_constraints
    text = "I'm staying in Atlantis."
    unknown_ctx = context(text, inherited=current, prior_status="COMPLETED", request_revision=3, investigation_id="third")
    unknown = validate_request(proposal(text, {}, {}), unknown_ctx)
    assert not unknown.starting_locations and unknown.request.preferred_area == "Napili"


def test_removing_one_of_two_constraints_reindexes_retained_entry_origin():
    _, previous = parent()
    text = "Only Kihei."
    items = previous.request.hard_constraints + [{"kind": "LOCATION_RESTRICTION", "scope": "LOCALITY", "value": "Kihei"}]
    second = validate_request(proposal(text, {"hard_constraints": items}, {"hard_constraints": "Only Kihei"}), child(text, previous))
    text = "Remove South Maui restriction."
    ctx = context(text, inherited=second, prior_status="COMPLETED", request_revision=3, investigation_id="third")
    removed = span(text, "Remove South Maui restriction", field="hard_constraints", previous_index=0)
    final = validate_request(proposal(text, {"hard_constraints": [items[1]]}, {}, removed=[removed]), ctx)
    assert final.request.hard_constraints == [items[1]] and not final.request.clarification_needed
    origins = [o for o in final.origins if o.field == "hard_constraints"]
    assert len(origins) == 1 and origins[0].entry_index == 0 and origins[0].inherited_from == second.investigation_id


def test_actual_failed_terminal_context_can_receive_a_new_complete_interpretation():
    text = "Swim tomorrow."
    previous = validate_request(proposal(text, {"activity": "SWIMMING", "target_date": "2026-11-17"},
                                        {"activity": "Swim", "target_date": "tomorrow"}), context(text))
    assert previous.request.clarification_needed
    text = "Morning instead."
    # The owning controller must attest an actual FAILED terminal outcome, not
    # relabel a pending clarification. No same-investigation resumption occurs.
    ctx = replace(child(text, previous), prior_status="FAILED")
    receipt = validate_request(proposal(text, {"target_time_window": window()}, {"target_time_window": "Morning"}), ctx)
    assert not receipt.request.clarification_needed and receipt.request.activity == "SWIMMING"
    assert receipt.investigation_id != previous.investigation_id and receipt.request_revision == 2
