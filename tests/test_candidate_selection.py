"""RI-T09..11/16 component coverage; audits are not assessments or acceptance runs."""

from copy import deepcopy
from dataclasses import replace

import pytest

from hawaii_activity_forecaster.models import BeachCatalog
from hawaii_activity_forecaster.interpretation import RequestValidationError, select_candidates, validate_request, verify_selection
from interpretation_samples import context, morning, proposal, window


def sup():
    text = "Paddleboard tomorrow morning in South Maui."
    ctx = context(text)
    item = {"kind": "LOCATION_RESTRICTION", "scope": "REGION", "value": "SOUTH_MAUI"}
    data = proposal(text, {"activity": "SUP", "target_date": "2026-11-17", "target_time_window": window(), "hard_constraints": [item]},
                    {"activity": "Paddleboard", "target_date": "tomorrow", "target_time_window": "morning", "hard_constraints": "in South Maui"})
    return ctx, data


def test_sc003_pools_distinguish_unsupported_assessment_from_dispatch():
    ctx, data = sup()
    receipt = validate_request(data, ctx)
    audit = select_candidates(receipt, ctx)
    assert audit.assessment_candidate_ids == ("TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_E")
    assert audit.investigation_candidate_ids == audit.planning_order == ("TEST_BEACH_B",)
    decisions = {d.beach_id: d for d in audit.decisions}
    assert decisions["TEST_BEACH_A"].reasons == decisions["TEST_BEACH_E"].reasons == ("ACTIVITY_UNSUPPORTED",)
    assert decisions["TEST_BEACH_C"].reasons == ("OUTSIDE_HARD_LOCATION",)
    assert decisions["TEST_BEACH_B"].sources[0].publisher
    assert decisions["TEST_BEACH_B"].sources[0].supports_fields
    assert decisions["TEST_BEACH_B"].last_verified == "2026-11-16"
    assert verify_selection(audit, receipt, ctx) == audit
    # A selector cannot fabricate domain assessment eligibility.
    assert not hasattr(audit, "assessments") and not hasattr(audit, "outcome")


def test_soft_area_retains_full_pool_and_orders_planning_without_ranks_or_cap():
    ctx, data = morning()
    receipt = validate_request(data, ctx)
    audit = select_candidates(receipt, ctx)
    assert audit.assessment_candidate_ids == ("TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_C", "TEST_BEACH_D", "TEST_BEACH_E")
    assert audit.investigation_candidate_ids == ("TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_C", "TEST_BEACH_D")
    assert audit.planning_order == audit.investigation_candidate_ids
    assert not hasattr(audit, "rank")
    text = "Near Napili instead."
    ctx2 = context(text, inherited=receipt, prior_status="COMPLETED", request_revision=2, investigation_id="second")
    second = validate_request(proposal(text, {"preferred_area": "Napili"}, {"preferred_area": "Near Napili"}), ctx2)
    assert select_candidates(second, ctx2).planning_order == ("TEST_BEACH_C", "TEST_BEACH_A", "TEST_BEACH_B", "TEST_BEACH_D")


@pytest.mark.parametrize("change,reason", [
    ({"catalog_status": "NEEDS_REVIEW"}, "CATALOG_NOT_VERIFIED"),
    ({"catalog_status": "DISABLED"}, "CATALOG_NOT_VERIFIED"),
    ({"last_verified": "2026-11-17"}, "CATALOG_VERIFICATION_IN_FUTURE"),
    ({"sources": []}, "CATALOG_ATTRIBUTE_PROVENANCE_MISSING"),
])
def test_unverified_or_unattributable_records_are_audit_only(change, reason):
    ctx, data = morning()
    records = ctx.catalog.model_dump()
    records[0].update(change)
    ctx = replace(ctx, catalog=BeachCatalog.model_validate(records))
    receipt = validate_request(data, ctx)
    audit = select_candidates(receipt, ctx)
    assert "TEST_BEACH_A" not in audit.assessment_candidate_ids and "TEST_BEACH_A" not in audit.investigation_candidate_ids
    assert reason in next(d for d in audit.decisions if d.beach_id == "TEST_BEACH_A").reasons


def test_future_access_dates_and_missing_material_attribution_use_existing_checks():
    ctx, data = morning()
    records = ctx.catalog.model_dump()
    for source in records[0]["sources"]:
        source["accessed_at"] = "2026-11-17"
    for source in records[1]["sources"]:
        source["supports_fields"] = [key for key in source["supports_fields"] if key != "access_notes"]
    ctx = replace(ctx, catalog=BeachCatalog.model_validate(records))
    audit = select_candidates(validate_request(data, ctx), ctx)
    assert not {"TEST_BEACH_A", "TEST_BEACH_B"} & set(audit.investigation_candidate_ids)
    assert all("CATALOG_ATTRIBUTE_PROVENANCE_MISSING" in d.reasons for d in audit.decisions[:2])


def test_empty_supported_selection_is_auditable_without_claiming_abstention_or_hazard():
    text = "Paddleboard tomorrow morning at Fictional Test Beach E (SYNTHETIC)."
    ctx = context(text)
    item = {"kind": "LOCATION_RESTRICTION", "scope": "BEACH", "value": "TEST_BEACH_E"}
    data = proposal(text, {"activity": "SUP", "target_date": "2026-11-17", "target_time_window": window(), "hard_constraints": [item]},
                    {"activity": "Paddleboard", "target_date": "tomorrow", "target_time_window": "morning",
                     "hard_constraints": "at Fictional Test Beach E (SYNTHETIC)"})
    receipt = validate_request(data, ctx)
    audit = select_candidates(receipt, ctx)
    assert audit.assessment_candidate_ids == ("TEST_BEACH_E",) and audit.investigation_candidate_ids == ()
    assert verify_selection(audit, receipt, ctx) == audit
    assert not hasattr(audit, "no_recommendation_reason")
    empty = replace(ctx, catalog=BeachCatalog(root=[]), original_request="Swim tomorrow morning.")
    data = proposal(empty.original_request, {"activity": "SWIMMING", "target_date": "2026-11-17", "target_time_window": window()},
                    {"activity": "Swim", "target_date": "tomorrow", "target_time_window": "morning"})
    audit = select_candidates(validate_request(data, empty), empty)
    assert audit.assessment_candidate_ids == audit.investigation_candidate_ids == ()


@pytest.mark.parametrize("change", ["assessment", "dispatch", "order", "sources", "reasons", "profile", "digest"])
def test_audit_mutation_is_rejected(change):
    ctx, data = sup()
    receipt = validate_request(data, ctx)
    audit = select_candidates(receipt, ctx)
    if change == "assessment":
        bad = replace(audit, assessment_candidate_ids=("TEST_BEACH_B",))
    elif change == "dispatch":
        bad = replace(audit, investigation_candidate_ids=("TEST_BEACH_A", "TEST_BEACH_B"))
    elif change == "order":
        bad = replace(audit, planning_order=("TEST_BEACH_A",))
    elif change in {"sources", "reasons"}:
        first = replace(audit.decisions[0], **({"sources": ()} if change == "sources" else {"reasons": ()}))
        bad = replace(audit, decisions=(first, *audit.decisions[1:]))
    else:
        bad = replace(audit, **({"rule_profile": "other"} if change == "profile" else {"request_digest": "other"}))
    with pytest.raises(RequestValidationError):
        verify_selection(bad, receipt, ctx)


def test_selection_is_read_only_repeatable_and_snapshot_bound():
    ctx, data = morning()
    receipt = validate_request(data, ctx)
    before = deepcopy(ctx.catalog)
    first = select_candidates(receipt, ctx)
    assert first == select_candidates(receipt, ctx) and ctx.catalog == before
    ctx.catalog.root[0].supported_activities.clear()
    with pytest.raises(RequestValidationError):
        verify_selection(first, receipt, ctx)
