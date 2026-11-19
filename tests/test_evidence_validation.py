"""EF/ES/FR/MC and SH evidence-rule checks; no eligibility decisions."""

from dataclasses import replace
from datetime import timedelta, timezone
from itertools import permutations

import pytest
from pydantic import ValidationError

from hawaii_activity_forecaster.harness.policy import Category, PolicyConfiguration
from hawaii_activity_forecaster.harness.synthetic import FindingBinding
from hawaii_activity_forecaster.models import BeachCatalog, EvidenceIssue, InvestigationState
from hawaii_activity_forecaster.tools.synthetic import RetrievalGap
from hawaii_activity_forecaster.validation import EvidenceValidationError, validate_evidence
from evidence_samples import change_finding, sample
from specialist_samples import BEACH, NOW, WINDOW


def validate(snapshot, catalog, policy, bindings, **kwargs):
    return validate_evidence(snapshot, catalog=catalog, policy=policy, bindings=bindings,
                             reference_time=kwargs.pop("reference_time", NOW), **kwargs)


def category(report, name, beach=BEACH):
    return next(item for candidate in report.candidates if candidate.beach_id == beach
                for item in candidate.categories if item.category == name)


def test_valid_observed_rules_cover_required_categories_without_assuming_visibility_or_safety():
    snapshot, catalog, policy, bindings = sample()
    original = snapshot.model_dump_json()
    result = validate(snapshot, catalog, policy, bindings)
    assert result.candidates[0].mandatory_categories_covered
    assert not category(result, "UNDERWATER_VISIBILITY").covered
    assert category(result, "UNDERWATER_VISIBILITY").priority == "OPTIONAL"
    assert all(f.validation_status == "ACCEPTED" for f in result.state.weather_findings + result.state.ocean_findings)
    assert result.state.assessments == []
    assert result.state.status == snapshot.status
    assert result.state.outcome is None
    assert result.state.hard_constraints == snapshot.hard_constraints
    assert snapshot.model_dump_json() == original
    assert result.state.tool_call_count == snapshot.tool_call_count
    for original_finding in snapshot.weather_findings + snapshot.ocean_findings:
        updated = next(f for f in result.state.weather_findings + result.state.ocean_findings if f.finding_id == original_finding.finding_id)
        assert updated.model_dump(exclude={"validation_status"}) == original_finding.model_dump(exclude={"validation_status"})


@pytest.mark.parametrize("change, reason, status", [
    ({"issued_at": None}, "ISSUANCE_TIME_MISSING", "LIMITED"),
    ({"valid_from": None}, "VALIDITY_WINDOW_MISSING", "LIMITED"),
    ({"valid_until": NOW}, "TARGET_WINDOW_NOT_COVERED", "REJECTED"),
    ({"valid_from": WINDOW["start"] + timedelta(seconds=1)}, "TARGET_WINDOW_NOT_COVERED", "REJECTED"),
    ({"retrieved_at": NOW + timedelta(seconds=1)}, "SOURCE_TIMESTAMPS_INVALID", "REJECTED"),
    ({"issued_at": NOW + timedelta(seconds=1)}, "SOURCE_TIMESTAMPS_INVALID", "REJECTED"),
    ({"observed_at": NOW + timedelta(seconds=1)}, "SOURCE_TIMESTAMPS_INVALID", "REJECTED"),
    ({"missing_fields": ["forecast_period"]}, "INCOMPLETE_FINDING", "LIMITED"),
    ({"retrieval_status": "PARTIAL"}, "INCOMPLETE_FINDING", "LIMITED"),
    ({"coverage_id": None}, "GEOGRAPHIC_IDENTIFIER_MISSING", "LIMITED"),
    ({"source_id": "NWS_MARINE"}, "SOURCE_OR_PROVENANCE_INVALID", "REJECTED"),
    ({"finding_type": "REPORT"}, "TEMPORAL_RULE_TYPE_MISMATCH", "REJECTED"),
])
def test_successful_retrieval_cannot_bypass_independent_checks(change, reason, status):
    snapshot, catalog, policy, bindings = sample()
    # Expired fixtures must remain chronologically valid as records.
    if "valid_until" in change:
        change = {**change, "valid_from": NOW - timedelta(hours=1)}
    changed = change_finding(snapshot, "run-wind", **change)
    result = validate(changed, catalog, policy, bindings)
    decision = next(d for d in result.decisions if d.finding_id == "run-wind")
    assert decision.status == status and reason in decision.reasons
    assert not category(result, "WIND_CONDITIONS").covered


def test_present_templates_and_binding_without_received_finding_do_not_supply_evidence():
    snapshot, catalog, policy, bindings = sample()
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {"ocean_findings": []})
    result = validate(snapshot, catalog, policy, bindings)
    assert not category(result, "SURF_WAVE_CONDITIONS").covered
    assert not category(result, "WATER_QUALITY_ADVISORY_CHECK").covered
    assert not result.candidates[0].mandatory_categories_covered
    missing_binding = validate(*sample()[:3], ())
    assert all(d.status == "REJECTED" for d in missing_binding.decisions)
    assert not missing_binding.candidates[0].mandatory_categories_covered


@pytest.mark.parametrize("alter", ["foreign-investigation", "wrong-step", "wrong-template"])
def test_runtime_binding_identity_is_required(alter):
    snapshot, catalog, policy, bindings = sample()
    changed = []
    for binding in bindings:
        if alter == "foreign-investigation":
            binding = replace(binding, runtime_investigation_id="other")
        elif alter == "wrong-step":
            binding = replace(binding, request_step=2)
        else:
            binding = replace(binding, findings=tuple(FindingBinding("other-template", f.runtime_finding_id) for f in binding.findings))
        changed.append(binding)
    result = validate(snapshot, catalog, policy, changed)
    assert not result.candidates[0].mandatory_categories_covered
    assert not any(d.status == "ACCEPTED" for d in result.decisions)


def test_ambiguous_bindings_fail_closed_and_duplicate_binding_is_idempotent():
    snapshot, catalog, policy, bindings = sample()
    assert validate(snapshot, catalog, policy, bindings + bindings) == validate(snapshot, catalog, policy, bindings)
    with pytest.raises(EvidenceValidationError, match="Ambiguous"):
        validate(snapshot, catalog, policy, bindings + (replace(bindings[0], runtime_tool_call_id="different-call"),))


@pytest.mark.parametrize("source, coverage", [("NDBC", "OFFSHORE"), ("HWT_NARRATIVE", "REGIONAL")])
def test_contextual_sources_cannot_fulfill_mandatory_beach_categories(source, coverage):
    snapshot, catalog, policy, bindings = sample()
    if source == "NDBC":
        changed = change_finding(snapshot, "run-marine", source_id=source, coverage_type=coverage, finding_type="OBSERVATION", observed_at=NOW)
        target, cats = "marine", {"SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS"}
    else:
        changed = change_finding(snapshot, "run-wind", source_id=source, coverage_type=coverage)
        target, cats = "wind", {"WIND_CONDITIONS"}
    data = policy.model_dump()
    data["evidence_rules"] = [r | {"temporal_rule": "CONTEXT_ONLY"} if r["source_fixture_id"] == target else r for r in data["evidence_rules"]]
    result = validate(changed, catalog, PolicyConfiguration.model_validate(data), bindings)
    for cat in cats:
        assert not category(result, cat).covered
    assert all(f.coverage_type == coverage for f in result.state.weather_findings + result.state.ocean_findings if f.source_id == source)


def test_report_needs_its_declared_window_and_retrieval_is_not_a_forecast():
    snapshot, catalog, policy, bindings = sample()
    changed = change_finding(snapshot, "run-marine", source_id="SNORKEL_STORE", finding_type="REPORT")
    data = policy.model_dump()
    data["evidence_rules"] = [r | {"temporal_rule": "DECLARED_REPORT_WINDOW"} if r["source_fixture_id"] == "marine" else r
                              for r in data["evidence_rules"] if r["category"] != "SURF_WAVE_CONDITIONS"]
    policy = PolicyConfiguration.model_validate(data)
    assert category(validate(changed, catalog, policy, bindings), "CURRENTS_PERSISTENT_HAZARDS").covered
    changed = change_finding(changed, "run-marine", valid_until=NOW, valid_from=NOW - timedelta(days=1))
    report = validate(changed, catalog, policy, bindings)
    assert not category(report, "CURRENTS_PERSISTENT_HAZARDS").covered
    assert any(issue.issue_type == "STALE" for issue in report.state.unresolved_evidence_issues)


@pytest.mark.parametrize("convention", [None, "UNKNOWN", "UNREVIEWED_METHOD"])
def test_unknown_surf_conventions_are_preserved_and_limited(convention):
    snapshot, catalog, policy, bindings = sample()
    changed = change_finding(snapshot, "run-marine", measurements=[{
        "measurement_type": "SURF_HEIGHT", "value": 2, "unit": "ft", "measurement_convention": convention,
    }])
    result = validate(changed, catalog, policy, bindings)
    assert not category(result, "SURF_WAVE_CONDITIONS").covered
    assert next(f for f in result.state.ocean_findings if f.finding_id == "run-marine").measurements[0].measurement_convention == convention


@pytest.mark.parametrize("change", ["no-premise", "false-premise", "unreceived-support"])
def test_empty_advisory_listing_never_implicitly_completes_check(change):
    snapshot, catalog, policy, bindings = sample()
    data = policy.model_dump()
    if change == "no-premise":
        data["premises"] = [p for p in data["premises"] if p["fact_type"] != "OFFICIAL_ADVISORY_CHECK_COMPLETE"]
    elif change == "false-premise":
        data["premises"] = [p | {"value": False} if p["fact_type"] == "OFFICIAL_ADVISORY_CHECK_COMPLETE" else p for p in data["premises"]]
    else:
        data["premises"] = [p | {"finding_refs": [{"source_fixture_id": "not-retrieved", "finding_id": "missing"}]}
                            if p["fact_type"] == "OFFICIAL_ADVISORY_CHECK_COMPLETE" else p for p in data["premises"]]
    result = validate(snapshot, catalog, PolicyConfiguration.model_validate(data), bindings)
    assert not category(result, "OFFICIAL_ADVISORIES").covered
    assert category(result, "WATER_QUALITY_ADVISORY_CHECK").covered


@pytest.mark.parametrize("change", ["unverified", "unsupported", "unattributed", "future-verification"])
def test_verified_catalog_coverage_checks_activity_and_field_attribution(change):
    snapshot, catalog, policy, bindings = sample()
    data = catalog.model_dump()
    beach = next(b for b in data if b["beach_id"] == BEACH)
    if change == "unverified":
        beach["catalog_status"] = "NEEDS_REVIEW"
    elif change == "unsupported":
        beach["supported_activities"] = ["SUP"]
    elif change == "future-verification":
        beach["last_verified"] = NOW.date() + timedelta(days=1)
    else:
        beach["sources"][0]["supports_fields"] = ["beach_id"]
    result = validate(snapshot, BeachCatalog.model_validate(data), policy, bindings)
    assert not category(result, "VERIFIED_BEACH_CHARACTERISTICS").covered
    assert not result.candidates[0].mandatory_categories_covered


def test_beach_mapping_cannot_expand_scope_or_relabel_a_beach_specific_record():
    snapshot, catalog, policy, bindings = sample()
    data = snapshot.model_dump() | {"candidate_beach_ids": [BEACH, "TEST_BEACH_B"]}
    result = validate(InvestigationState.model_validate(data), catalog, policy, bindings)
    assert not category(result, "WIND_CONDITIONS", "TEST_BEACH_B").covered
    data = policy.model_dump()
    for rule in data["evidence_rules"]:
        if rule["source_fixture_id"] == "water":
            rule["beach_ids"] = ["TEST_BEACH_B"]
    result = validate(InvestigationState.model_validate(snapshot.model_dump() | {"candidate_beach_ids": ["TEST_BEACH_B"]}),
                      catalog, PolicyConfiguration.model_validate(data), bindings)
    assert any("BEACH_SCOPE_MISMATCH" in d.reasons for d in result.decisions)
    assert not category(result, "WATER_QUALITY_ADVISORY_CHECK", "TEST_BEACH_B").covered


def test_material_conflict_requires_observed_support_and_preserves_findings():
    snapshot, catalog, policy, bindings = sample()
    data = policy.model_dump()
    data["premises"].append(dict(
        premise_id="conflict", beach_id=BEACH, activity="SWIMMING", time_window=WINDOW,
        fact_type="MATERIAL_SAFETY_CONFLICT_PRESENT", value=True,
        finding_refs=[{"source_fixture_id": "marine", "finding_id": "template-marine"}],
        catalog_field_refs=[], rationale="Explicit hypothetical material conflict, no numeric threshold",
    ))
    policy = PolicyConfiguration.model_validate(data)
    result = validate(snapshot, catalog, policy, bindings)
    assert result.conflicted_finding_ids == ("run-marine",)
    assert not result.candidates[0].mandatory_categories_covered
    assert len(result.state.ocean_findings) == 2
    assert any(issue.issue_type == "CONFLICTING" for issue in result.state.unresolved_evidence_issues)
    assert not validate(snapshot, catalog, policy, tuple(b for b in bindings if b.source_fixture_id != "marine")).conflicted_finding_ids


def test_exact_advisory_temporal_overlap_is_reported_without_hazard_or_geographic_inference():
    snapshot, catalog, policy, bindings = sample()
    advisory = dict(advisory_id="synthetic-advisory", issuer="Synthetic agency", advisory_type="Hypothetical notice",
                    affected_area="Declared fictional area", source_reference="https://example.invalid/advisory",
                    effective_from=WINDOW["start"] - timedelta(hours=1), effective_until=WINDOW["start"])
    expired = change_finding(snapshot, "run-water", advisories=[advisory])
    result = validate(expired, catalog, policy, bindings)
    assert next(d for d in result.decisions if d.finding_id == "run-water").advisory_overlaps == (("synthetic-advisory", False),)
    advisory["effective_until"] = WINDOW["start"] + timedelta(seconds=1)
    result = validate(change_finding(snapshot, "run-water", advisories=[advisory]), catalog, policy, bindings)
    assert next(d for d in result.decisions if d.finding_id == "run-water").advisory_overlaps == (("synthetic-advisory", True),)
    assert not result.state.assessments
    advisory["effective_until"] = None
    result = validate(change_finding(snapshot, "run-water", advisories=[advisory]), catalog, policy, bindings)
    assert not category(result, "WATER_QUALITY_ADVISORY_CHECK").covered


def test_stable_results_idempotence_mutation_isolation_and_resolving_only_correlated_gaps():
    snapshot, catalog, policy, bindings = sample()
    gap = EvidenceIssue(issue_id="known-gap", issue_type="MISSING", finding_ids=[], affected_beach_ids=[BEACH], description="Opaque original gap", resolved=False)
    unknown = EvidenceIssue.model_validate(gap.model_dump() | {"issue_id": "unknown-gap"})
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {"unresolved_evidence_issues": [gap, unknown]})
    metadata = RetrievalGap(gap.issue_id, snapshot.investigation_id, snapshot.request_revision, Category.SURF_WAVE_CONDITIONS, (BEACH,), snapshot.target_time_window)
    result = validate(snapshot, catalog, policy, bindings, retrieval_gaps=(metadata,))
    statuses = {i.issue_id: i.resolved for i in result.state.unresolved_evidence_issues}
    assert statuses["known-gap"] and not statuses["unknown-gap"]
    assert validate(result.state, catalog, policy, bindings, retrieval_gaps=(metadata,)) == result
    for order in permutations(bindings):
        assert validate(snapshot, catalog, policy, order, retrieval_gaps=(metadata,)) == result
    result.state.weather_findings[0].descriptive_findings.append("caller mutation")
    assert "caller mutation" not in snapshot.weather_findings[0].descriptive_findings


@pytest.mark.parametrize("status", ["FAILED", "COMPLETED", "ABSTAINED"])
def test_terminal_investigations_cannot_be_revalidated(status):
    snapshot, catalog, policy, bindings = sample()
    outcome = {"FAILED": "ERROR", "COMPLETED": "RECOMMENDATIONS", "ABSTAINED": "NO_RECOMMENDATION"}[status]
    terminal = InvestigationState.model_validate(snapshot.model_dump() | {"status": status, "outcome": outcome, "result_id": "final", "completion_reason": "Synthetic stop"})
    before = terminal.model_dump_json()
    with pytest.raises(EvidenceValidationError):
        validate(terminal, catalog, policy, bindings)
    assert terminal.model_dump_json() == before


@pytest.mark.parametrize("activity, priority", [("SWIMMING", "RELEVANT"), ("SNORKELING", "RELEVANT"), ("SUP", "MANDATORY")])
def test_activity_matrix_requires_wind_for_sup_without_promoting_optional_visibility(activity, priority):
    snapshot, catalog, policy, bindings = sample()
    catalog_data = catalog.model_dump()
    next(b for b in catalog_data if b["beach_id"] == BEACH)["supported_activities"] = ["SWIMMING", "SNORKELING", "SUP"]
    catalog = BeachCatalog.model_validate(catalog_data)
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {"activity": activity})
    assert validate(snapshot, catalog, policy, bindings).candidates[0].mandatory_categories_covered
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {"weather_findings": [f for f in snapshot.weather_findings if f.finding_id != "run-wind"]})
    result = validate(snapshot, catalog, policy, bindings)
    assert category(result, "WIND_CONDITIONS").priority == priority
    assert result.candidates[0].mandatory_categories_covered == (activity != "SUP")
    assert category(result, "UNDERWATER_VISIBILITY").priority == "OPTIONAL"


def test_fixed_reference_and_equivalent_timezones_produce_identical_verdicts_without_provider_age_thresholds():
    snapshot, catalog, policy, bindings = sample()
    a = validate(snapshot, catalog, policy, bindings)
    b = validate(snapshot, catalog, policy, bindings, reference_time=NOW.astimezone(timezone(timedelta(hours=-10))))
    assert a == b
    # An old issuance time is not an invented provider-specific expiration when
    # the explicitly declared validity still covers the requested interval.
    older = change_finding(snapshot, "run-wind", issued_at=NOW - timedelta(days=5))
    assert category(validate(older, catalog, policy, bindings), "WIND_CONDITIONS").covered


def test_invalid_schema_is_revalidated_and_malformed_context_cannot_mutate_input():
    snapshot, catalog, policy, bindings = sample()
    snapshot.weather_findings.append(snapshot.ocean_findings[0])
    before = snapshot.model_dump_json()
    with pytest.raises(ValidationError):
        validate(snapshot, catalog, policy, bindings)
    assert snapshot.model_dump_json() == before
    snapshot, catalog, policy, bindings = sample()
    with pytest.raises(EvidenceValidationError):
        validate(snapshot, catalog, policy, bindings, reference_time=NOW.replace(tzinfo=None))
    with pytest.raises(EvidenceValidationError):
        validate(snapshot, catalog, policy, (replace(bindings[0], runtime_tool_call_id=""),))
