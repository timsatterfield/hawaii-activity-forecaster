"""SRQ/SRS/ST and LG contract-boundary tests with fictional inputs."""

from datetime import timedelta
from itertools import permutations

import pytest

from hawaii_activity_forecaster.models import InvestigationState
from hawaii_activity_forecaster.orchestration import (
    SpecialistContractError, SpecialistDelivery, SpecialistExchange,
)
from specialist_samples import BEACH, NOW, catalog, finding, request, response, state


def setup(*requests):
    snapshot = state()
    exchange = SpecialistExchange(snapshot, catalog())
    return exchange, exchange.authorize(snapshot, requests or (request(),), now=NOW)


def delivery(value, **updates):
    return SpecialistDelivery(value.request_id, value.attempt_number, value, **updates)


@pytest.mark.parametrize("updates, reason", [
    ({"investigation_id": "other"}, "REQUEST_CORRELATION_INVALID"),
    ({"request_revision": 2}, "REQUEST_CORRELATION_INVALID"),
    ({"schema_version": "future"}, "REQUEST_CORRELATION_INVALID"),
    ({"candidate_beach_ids": ["UNKNOWN"]}, "CANDIDATE_SCOPE_INVALID"),
    ({"candidate_beach_ids": ["TEST_BEACH_B"]}, "CANDIDATE_SCOPE_INVALID"),
    ({"candidate_beach_ids": []}, "CANDIDATE_SCOPE_INVALID"),
    ({"target_time_window": {"start": NOW, "end": NOW + timedelta(hours=1)}}, "TARGET_WINDOW_INVALID"),
    ({"issued_at": NOW + timedelta(seconds=1)}, "REQUEST_EXPIRED_OR_NOT_ISSUED"),
    ({"deadline_at": NOW}, "REQUEST_EXPIRED_OR_NOT_ISSUED"),
    ({"attempt_number": 2}, "INITIAL_ATTEMPT_INVALID"),
    ({"requested_evidence": []}, "EVIDENCE_SCOPE_INVALID"),
    ({"requested_evidence": [{"requirement_id": "r", "evidence_type": "UNKNOWN", "priority": "REQUIRED"}]}, "EVIDENCE_SCOPE_INVALID"),
    ({"requested_evidence": [{"requirement_id": "r", "evidence_type": "WATER_QUALITY_ADVISORY_CHECK", "priority": "REQUIRED"}]}, "EVIDENCE_SCOPE_INVALID"),
    ({"requested_evidence": [{"requirement_id": "r", "evidence_type": "VERIFIED_BEACH_CHARACTERISTICS", "priority": "REQUIRED"}]}, "EVIDENCE_SCOPE_INVALID"),
])
def test_unauthorized_request_is_not_registered(updates, reason):
    original = state()
    before = original.model_dump_json()
    exchange = SpecialistExchange(original, catalog())
    bad = request(**updates)
    with pytest.raises(SpecialistContractError, match=reason):
        exchange.authorize(original, (bad,), now=NOW)
    assert original.model_dump_json() == before
    rejected = exchange.merge(original, (delivery(response(bad)),), now=NOW)
    assert rejected.rejections[0].reason == "UNKNOWN_REQUEST"
    assert rejected.state == original


def test_authorization_is_atomic_and_at_most_one_request_per_role():
    exchange, snapshot = setup()
    with pytest.raises(SpecialistContractError):
        exchange.authorize(snapshot, (request("OCEAN"), request("OCEAN", request_id="second-ocean")), now=NOW)
    assert exchange.merge(snapshot, (delivery(response(request("OCEAN"))),), now=NOW).rejections[0].reason == "UNKNOWN_REQUEST"


@pytest.mark.parametrize("field, value, reason", [
    ("request_id", "unknown", "RESPONSE_CORRELATION_INVALID"),
    ("investigation_id", "old-investigation", "OUTDATED_RESPONSE"),
    ("request_revision", 2, "OUTDATED_RESPONSE"),
    ("attempt_number", 2, "OUTDATED_RESPONSE"),
    ("schema_version", "future", "RESPONSE_CORRELATION_INVALID"),
    ("started_at", NOW - timedelta(seconds=1), "RESPONSE_TIMING_INVALID"),
    ("completed_at", NOW + timedelta(seconds=1), "RESPONSE_TIMING_INVALID"),
])
def test_correlated_response_fields_are_checked_before_merging(field, value, reason):
    exchange, snapshot = setup()
    payload = response().model_dump()
    payload[field] = value
    if field == "investigation_id":
        payload["findings"][0]["investigation_id"] = value
    result = exchange.merge(snapshot, (SpecialistDelivery("WEATHER-request", 1, payload),), now=NOW)
    assert result.rejections[0].reason == reason
    assert result.state.weather_findings == []
    assert result.state.assessments == snapshot.assessments
    if reason == "OUTDATED_RESPONSE":
        assert result.state == snapshot


@pytest.mark.parametrize("payload", [None, {}, {"recommendations": ["forbidden"]}])
def test_malformed_payload_and_unauthorized_extra_output_are_rejected(payload):
    exchange, snapshot = setup()
    result = exchange.merge(snapshot, (SpecialistDelivery("WEATHER-request", 1, payload),), now=NOW)
    assert result.rejections[0].reason == "RESPONSE_SCHEMA_INVALID"
    assert result.state.weather_findings == []


def test_response_cannot_impersonate_other_parallel_branch():
    exchange, snapshot = setup(request(), request("OCEAN"))
    result = exchange.merge(snapshot, (SpecialistDelivery("WEATHER-request", 1, response(request("OCEAN"))),), now=NOW)
    assert result.rejections[0].reason == "RESPONSE_CORRELATION_INVALID"
    assert result.state.ocean_findings == []


@pytest.mark.parametrize("updates", [
    {"source_id": "NWS_MARINE"}, {"source_id": "NWS_ALERTS"},
    {"coverage_type": "BEACH", "beach_id": "TEST_BEACH_B"},
])
def test_findings_cannot_escape_source_category_or_candidate_scope(updates):
    exchange, snapshot = setup()
    result = exchange.merge(snapshot, (delivery(response(findings=[finding(**updates)])),), now=NOW)
    assert result.rejections[0].reason == "FINDING_SCOPE_INVALID"
    assert result.state.weather_findings == []


def test_order_independent_merge_preserves_scope_timestamps_gaps_and_errors():
    weather, ocean = request(), request("OCEAN")
    gap = {"gap_id": "gap-1", "gap_type": "MISSING", "related_finding_ids": [], "description": "Explicit synthetic missing check"}
    error = {"error_id": "error-1", "error_code": "SOURCE_UNAVAILABLE", "message": "Synthetic outage", "retryable": False}
    w = response(weather, status="PARTIAL", unresolved_gaps=[gap], errors=[error])
    o = response(ocean)
    snapshots = []
    for batch in permutations((delivery(w), delivery(o))):
        exchange, snapshot = setup(weather, ocean)
        result = exchange.merge(snapshot, batch, now=NOW)
        assert not result.rejections
        assert result.accepted_response_ids == tuple(sorted([w.response_id, o.response_id]))
        assert result.state.weather_findings[0] == w.findings[0]
        assert result.state.ocean_findings[0] == o.findings[0]
        assert result.state.weather_findings[0].beach_id is None
        assert result.state.weather_findings[0].coverage_type == "REGIONAL"
        assert result.state.unresolved_evidence_issues[0].issue_id == "gap-1"
        assert result.state.active_errors[0]["message"] == error["message"]
        assert result.state.hard_constraints == snapshot.hard_constraints
        assert result.state.status == snapshot.status
        snapshots.append(result.state.model_dump_json())
    assert snapshots[0] == snapshots[1]


def test_exact_replay_has_no_effect_even_on_updated_at_and_detaches_payload():
    exchange, snapshot = setup()
    payload = response()
    first = exchange.merge(snapshot, (delivery(payload),), now=NOW + timedelta(seconds=1))
    duplicate = exchange.merge(first.state, (delivery(payload),), now=NOW + timedelta(seconds=2))
    assert duplicate.duplicate_response_ids == (payload.response_id,)
    assert duplicate.state == first.state
    assert snapshot.weather_findings == []
    payload.findings[0].descriptive_findings.append("later callback mutation")
    assert first.state.weather_findings[0].descriptive_findings != payload.findings[0].descriptive_findings


def test_findings_are_deduplicated_across_different_response_ids_and_validation_is_not_delegated():
    exchange, snapshot = setup()
    first = exchange.merge(snapshot, (delivery(response()),), now=NOW)
    promoted = finding(validation_status="ACCEPTED")
    duplicate = exchange.merge(first.state, (delivery(response(response_id="new-delivery", findings=[promoted])),), now=NOW)
    assert len(duplicate.state.weather_findings) == 1
    assert duplicate.state.weather_findings[0].validation_status == "PENDING"
    assert duplicate.state.assessments == []


@pytest.mark.parametrize("changed_id", ["response", "finding", "gap", "error"])
def test_changed_content_under_stable_id_quarantines_all_variants_independent_of_order(changed_id):
    base = response().model_dump()
    other = response(response_id="other-response").model_dump()
    if changed_id == "response":
        other["response_id"] = base["response_id"]
        other["findings"][0]["descriptive_findings"] = ["different material"]
    elif changed_id == "finding":
        other["findings"][0]["descriptive_findings"] = ["different material"]
    else:
        field = "unresolved_gaps" if changed_id == "gap" else "errors"
        item = ({"gap_id": "shared-gap", "gap_type": "MISSING", "related_finding_ids": [], "description": "first"}
                if changed_id == "gap" else
                {"error_id": "shared-error", "error_code": "SOURCE_TIMEOUT", "message": "first", "retryable": True})
        base[field] = [item]
        other[field] = [{**item, "description" if changed_id == "gap" else "message": "changed"}]
    snapshots = []
    for payloads in permutations((base, other)):
        exchange, snapshot = setup()
        result = exchange.merge(snapshot, tuple(SpecialistDelivery("WEATHER-request", 1, p) for p in payloads), now=NOW)
        assert len(result.rejections) == 2
        assert {r.reason for r in result.rejections} == {"IDENTIFIER_CONTENT_CONFLICT"}
        assert not result.state.weather_findings
        snapshots.append(result.state.model_dump_json())
    assert snapshots[0] == snapshots[1]


def test_independent_conflicting_findings_survive_and_changed_existing_id_cannot_overwrite():
    exchange, snapshot = setup()
    first = exchange.merge(snapshot, (delivery(response()),), now=NOW)
    different = finding(finding_id="independent", descriptive_findings=["Opposite synthetic report"])
    second = exchange.merge(first.state, (delivery(response(response_id="second", findings=[different])),), now=NOW)
    assert len(second.state.weather_findings) == 2
    changed = finding(descriptive_findings=["Changed existing report"])
    result = exchange.merge(second.state, (delivery(response(response_id="third", findings=[changed])),), now=NOW)
    assert result.rejections[0].reason == "IDENTIFIER_CONTENT_CONFLICT"
    assert result.state.weather_findings == second.state.weather_findings


@pytest.mark.parametrize("failure", ["callback", "ERROR", "UNAVAILABLE", "invalid"])
def test_one_specialist_failure_preserves_valid_sibling_findings(failure):
    w, o = request(), request("OCEAN")
    exchange, snapshot = setup(w, o)
    if failure == "callback":
        bad = SpecialistDelivery(w.request_id, 1, execution_failed=True)
    elif failure == "invalid":
        bad = SpecialistDelivery(w.request_id, 1, {})
    else:
        bad = delivery(response(w, status=failure, findings=[], errors=[{
            "error_id": "weather-error", "error_code": "SOURCE_UNAVAILABLE", "message": "Synthetic outage", "retryable": False,
        }]))
    merged = exchange.merge(snapshot, (bad, delivery(response(o))), now=NOW)
    assert len(merged.state.ocean_findings) == 1
    assert not merged.state.weather_findings
    assert {p.request_id: p.request_status for p in merged.state.pending_evidence_requests} == {
        w.request_id: "FAILED", o.request_id: "COMPLETED",
    }


def test_superseded_attempt_cannot_affect_current_state():
    exchange, snapshot = setup()
    second = request(attempt_number=2, issued_at=NOW + timedelta(seconds=1))
    snapshot = exchange.authorize(snapshot, (second,), now=NOW + timedelta(seconds=1))
    stale = exchange.merge(snapshot, (delivery(response()),), now=NOW + timedelta(seconds=2))
    assert stale.rejections[0].reason == "OUTDATED_ATTEMPT"
    assert stale.state == snapshot
    current = exchange.merge(snapshot, (delivery(response(second)),), now=NOW + timedelta(seconds=2))
    assert len(current.state.weather_findings) == 1


@pytest.mark.parametrize("inactive", ["terminal", "revision", "closed", "expired"])
def test_inactive_investigation_rejects_all_effects(inactive):
    exchange, snapshot = setup()
    changes = {}
    if inactive == "terminal":
        changes = dict(status="FAILED", outcome="ERROR", result_id="stop", completion_reason="Synthetic stop")
    elif inactive == "revision":
        changes = dict(request_revision=2)
    elif inactive == "closed":
        exchange.close()
    else:
        changes = dict(deadline_at=NOW)
    snapshot = InvestigationState.model_validate({**snapshot.model_dump(), **changes})
    merged = exchange.merge(snapshot, (delivery(response()),), now=NOW)
    assert merged.state == snapshot
    assert merged.rejections
    with pytest.raises(SpecialistContractError):
        exchange.authorize(snapshot, (request("OCEAN"),), now=NOW)


def test_expired_request_rejects_late_response():
    origin = request(deadline_at=NOW + timedelta(seconds=1))
    exchange, snapshot = setup(origin)
    merged = exchange.merge(snapshot, (delivery(response(origin)),), now=NOW + timedelta(seconds=2))
    assert merged.rejections[0].reason == "RESPONSE_EXPIRED"
    assert not merged.state.weather_findings


def test_mutated_model_is_revalidated_and_authorized_request_is_detached():
    origin = request()
    exchange, snapshot = setup(origin)
    origin.candidate_beach_ids.append("OUTSIDE")
    valid = response(request())
    merged = exchange.merge(snapshot, (delivery(valid),), now=NOW)
    assert not merged.rejections
    bad = response(response_id="mutated-model")
    bad.findings.append(finding(finding_id="invalid-parent", investigation_id="other-investigation"))
    rejected = exchange.merge(merged.state, (delivery(bad),), now=NOW)
    assert rejected.rejections[0].reason == "RESPONSE_SCHEMA_INVALID"
    assert rejected.state.weather_findings == merged.state.weather_findings


def test_changed_response_replay_does_not_overwrite_previously_committed_material():
    exchange, snapshot = setup()
    original = response()
    first = exchange.merge(snapshot, (delivery(original),), now=NOW)
    changed = response(findings=[finding(descriptive_findings=["changed stable payload"])])
    result = exchange.merge(first.state, (delivery(changed),), now=NOW + timedelta(seconds=1))
    assert result.rejections[0].reason == "IDENTIFIER_CONTENT_CONFLICT"
    assert result.state.weather_findings == first.state.weather_findings
    assert result.state.pending_evidence_requests[0].request_status == "COMPLETED"


def test_trusted_validation_status_is_preserved_when_pending_finding_is_delivered_again():
    exchange, snapshot = setup()
    original = response()
    first = exchange.merge(snapshot, (delivery(original),), now=NOW)
    trusted = first.state.model_dump()
    trusted["weather_findings"][0]["validation_status"] = "REJECTED"
    trusted_state = InvestigationState.model_validate(trusted)
    replay = response(response_id="new-id-same-evidence")
    merged = exchange.merge(trusted_state, (delivery(replay),), now=NOW + timedelta(seconds=1))
    assert merged.state.weather_findings[0].validation_status == "REJECTED"
    assert not merged.rejections


def test_gap_and_error_references_are_checked_without_inventing_evidence():
    exchange, snapshot = setup()
    gap = {"gap_id": "gap", "gap_type": "MISSING", "related_finding_ids": ["unknown-finding"], "description": "Synthetic gap"}
    with pytest.raises(SpecialistContractError, match="KNOWN_GAP_INVALID"):
        exchange.authorize(snapshot, (request("OCEAN", known_evidence_gaps=[gap]),), now=NOW)
    missing = response(unresolved_gaps=[gap])
    merged = exchange.merge(snapshot, (delivery(missing),), now=NOW)
    assert merged.rejections[0].reason == "GAP_REFERENCE_INVALID"
    assert merged.state.unresolved_evidence_issues == []
    bad_error = response(errors=[{"error_id": "error", "error_code": "SOURCE_TIMEOUT", "message": "Synthetic",
                                  "source_id": "NWS_MARINE", "retryable": True}])
    merged = exchange.merge(snapshot, (delivery(bad_error),), now=NOW)
    assert merged.rejections[0].reason == "ERROR_SOURCE_SCOPE_INVALID"


def test_later_attempt_cannot_expand_logical_request_scope_or_skip_numbers():
    exchange, snapshot = setup()
    for updates in ({"attempt_number": 3}, {"attempt_number": 2, "candidate_beach_ids": [BEACH, "TEST_BEACH_B"]}):
        with pytest.raises(SpecialistContractError):
            exchange.authorize(snapshot, (request(**updates),), now=NOW)


def test_investigation_deadline_bounds_delegation_deadline():
    original = InvestigationState.model_validate(state().model_dump() | {"deadline_at": NOW + timedelta(seconds=10)})
    exchange = SpecialistExchange(original, catalog())
    for deadline in (None, NOW + timedelta(seconds=20)):
        with pytest.raises(SpecialistContractError, match="DEADLINE_SCOPE_INVALID"):
            exchange.authorize(original, (request(deadline_at=deadline),), now=NOW)


def test_identical_deliveries_within_batch_do_not_duplicate_any_material():
    exchange, snapshot = setup()
    payload = response()
    result = exchange.merge(snapshot, (delivery(payload), delivery(payload)), now=NOW)
    assert result.accepted_response_ids == result.duplicate_response_ids == (payload.response_id,)
    assert len(result.state.weather_findings) == 1
    assert not result.rejections
