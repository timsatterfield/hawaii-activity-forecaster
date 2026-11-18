"""SH-OD-004/005/007/008: contract validation, not scenario acceptance."""

from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from hawaii_activity_forecaster.harness import (
    Assertion, BehaviorAttempt, BehaviorScript, EvidenceProfile, PolicyConfiguration, Premise,
)
from hawaii_activity_forecaster.harness.assertions import field_type, pointer_tokens, Target
from harness_samples import assertion, make_package, read


@pytest.fixture
def package(tmp_path):
    return make_package(tmp_path)


def test_assertions_round_trip_explicit_null_and_blocked_metadata():
    data = assertion(target="investigation_state", selector={"request_step": 1}, field="/activity", expected=None)
    model = Assertion.model_validate(data)
    assert Assertion.model_validate_json(model.model_dump_json(exclude_unset=True)) == model
    data.update(test_status="BLOCKED", blocking_reason="Real provider is undecided")
    assert Assertion.model_validate(data).test_status == "BLOCKED"


@pytest.mark.parametrize("updates", [
    {"expected": 1}, {"expected": True}, {"expected": "invented-eligibility"},
    {"field": "/private_chain_of_thought"}, {"field": "eligibility"}, {"field": "/"},
    {"field": "/eligibility/~2"}, {"selector": {"request_step": True}},
    {"selector": {"request_step": 1, "sequence_number": 1}}, {"mandatory": "true"},
    {"target": "model_internals"}, {"operator": "EVAL"}, {"test_status": "PASS"},
    {"blocking_reason": "active cannot be blocked"}, {"test_status": "BLOCKED"},
    {"test_status": "PARTIALLY_BLOCKED"}, {"test_status": "DISABLED"},
    {"expected_ref": {"target": "investigation_state", "selector": {"request_step": 1}, "field": "/activity"}},
])
def test_malformed_assertions_rejected(updates):
    with pytest.raises(ValidationError):
        Assertion.model_validate(assertion(**updates))


@pytest.mark.parametrize("operator", ["EXISTS", "ABSENT"])
def test_presence_operators_forbid_comparison_operands(operator):
    data = assertion(operator=operator)
    with pytest.raises(ValidationError):
        Assertion.model_validate(data)
    del data["field"], data["expected"]
    assert Assertion.model_validate(data).operator == operator


@pytest.mark.parametrize("value", [-1, True, 1.0, "1", None])
def test_counts_require_nonnegative_integer(value):
    data = assertion(operator="COUNT_AT_MOST", expected=value)
    del data["field"]
    with pytest.raises(ValidationError):
        Assertion.model_validate(data)


def test_membership_requires_array_and_correct_element_type():
    data = assertion(operator="INCLUDES", field="/supporting_finding_ids", expected="finding-1")
    assert Assertion.model_validate(data)
    with pytest.raises(ValidationError):
        Assertion.model_validate(dict(data, expected=True))
    with pytest.raises(ValidationError):
        Assertion.model_validate(dict(data, field="/eligibility"))


def test_cross_observation_comparison_is_typed():
    data = assertion(target="harness_execution", selector={"request_step": 2}, operator="SAME_AS", field="/session_id")
    del data["expected"]
    data["expected_ref"] = {"target": "harness_execution", "selector": {"request_step": 1}, "field": "/session_id"}
    assert Assertion.model_validate(data)
    data["expected_ref"]["field"] = "/request_revision"
    with pytest.raises(ValidationError):
        Assertion.model_validate(data)


@pytest.mark.parametrize("pointer", ["/details/secret", "/details/arguments_summary/token", "/details", "/related_ids/-1", "/related_ids/*"])
def test_unapproved_trace_pointers_are_rejected(pointer):
    with pytest.raises(ValueError):
        field_type(Target.TRACE_EVENT, pointer)


def test_trace_details_and_nested_typed_fields_are_supported():
    assert field_type(Target.TRACE_EVENT, "/details/total_tool_calls")
    assert field_type(Target.INVESTIGATION_STATE, "/assessments/0/policy_results/0/result")
    assert pointer_tokens("/field~1name") == ["field/name"]


@pytest.mark.parametrize("behavior,fields", [
    ("SUCCESS", {"response_fixture_id": "source"}), ("PARTIAL", {"response_fixture_id": "source"}),
    ("UNAVAILABLE", {"response_fixture_id": "source"}), ("ERROR", {"response_fixture_id": "source"}),
    ("DUPLICATE", {"response_fixture_id": "source", "delivery_count": 2}),
    ("MALFORMED", {"raw_response_path": "malformed/invalid.json", "invalid_fields": ["/retrieved_at"]}),
])
def test_behavior_specific_shapes(behavior, fields):
    value = BehaviorAttempt(attempt=1, behavior=behavior, simulated_duration_ms=10_000, **fields)
    assert BehaviorAttempt.model_validate_json(value.model_dump_json(exclude_unset=True)) == value
    with pytest.raises(ValidationError):
        BehaviorAttempt.model_validate(dict(value.model_dump(exclude_unset=True), simulated_duration_ms=10_001))


def test_timeout_threshold_and_fields_are_separate_from_response_status():
    assert BehaviorAttempt(attempt=1, behavior="TIMEOUT", simulated_duration_ms=11000)
    for updates in ({"simulated_duration_ms": 10000}, {"response_fixture_id": "not-delivered"},
                    {"simulated_duration_ms": True}, {"simulated_duration_ms": float("inf")}):
        with pytest.raises(ValidationError):
            BehaviorAttempt.model_validate(dict(attempt=1, behavior="TIMEOUT", simulated_duration_ms=11000) | updates)


@pytest.mark.parametrize("updates", [{"delivery_count": 1}, {"delivery_count": True}, {"raw_response_path": "malformed/x.json"}])
def test_duplicate_behavior_cannot_create_extra_or_ambiguous_fields(updates):
    with pytest.raises(ValidationError):
        BehaviorAttempt.model_validate(dict(attempt=1, behavior="DUPLICATE", simulated_duration_ms=1,
                                           response_fixture_id="source", delivery_count=2) | updates)


@pytest.mark.parametrize("pointer", ["", "/", "/*", "/findings/-1"])
def test_malformed_fault_locations_must_be_narrow(pointer):
    with pytest.raises(ValidationError):
        BehaviorAttempt(attempt=1, behavior="MALFORMED", simulated_duration_ms=1,
                        raw_response_path="malformed/x.json", invalid_fields=[pointer])


def test_scripts_reject_ambiguous_matches_and_invalid_sequences(package):
    script = read(package, "behaviors/unit.json")
    duplicate = deepcopy(script["operations"][0])
    duplicate["operation_id"] = "another-name-same-match"
    with pytest.raises(ValidationError):
        BehaviorScript.model_validate(dict(script, operations=script["operations"] + [duplicate]))
    script["requests"][0]["request_step"] = 2
    with pytest.raises(ValidationError):
        BehaviorScript.model_validate(script)


def test_profile_cannot_drop_or_hide_mandatory_categories(package):
    profile = read(package, "policies/unit.json")["evidence_profiles"][0]
    assert EvidenceProfile.model_validate(profile)
    profile["optional"].append(profile["mandatory"].pop())
    with pytest.raises(ValidationError):
        EvidenceProfile.model_validate(profile)


def test_policy_cannot_contain_final_verdicts_or_duplicate_premises(package):
    policy = read(package, "policies/unit.json")
    with pytest.raises(ValidationError):
        PolicyConfiguration.model_validate(dict(policy, eligibility="ELIGIBLE"))
    policy["premises"].append(deepcopy(policy["premises"][0]))
    policy["premises"][1]["premise_id"] = "other-id-same-meaning"
    policy["premises"][1]["value"] = False
    with pytest.raises(ValidationError):
        PolicyConfiguration.model_validate(policy)


def test_premises_need_explicit_typed_support(package):
    premise = read(package, "policies/unit.json")["premises"][0]
    for updates in ({"value": 1}, {"finding_refs": []}, {"limitation_code": "SYNTHETIC_POOR_VISIBILITY"},
                    {"fact_type": "NON_DISQUALIFYING_LIMITATION_PRESENT"}):
        with pytest.raises(ValidationError):
            Premise.model_validate(dict(premise, **updates))


@pytest.mark.parametrize("expected", [True, "1", 1.0])
def test_counter_equality_operand_is_not_coerced(expected):
    data = assertion(target="harness_execution", selector={"request_step": 1},
                     field="/tool_invocation_count", expected=expected)
    with pytest.raises(ValidationError):
        Assertion.model_validate(data)


def test_known_trace_arguments_object_can_be_compared_but_not_arbitrarily_traversed():
    assert Assertion.model_validate(assertion(target="trace_event", selector={"request_step": 1},
        field="/details/arguments_summary", expected={"source_id": "NWS_MARINE"}))


def test_membership_and_all_equals_do_not_allow_hidden_extra_operands():
    with pytest.raises(ValidationError):
        Assertion.model_validate(assertion(operator="ALL_EQUALS", expected_ref=None))
    assert Assertion.model_validate(assertion(operator="ALL_EQUALS"))


@pytest.mark.parametrize("status", ["BLOCKED", "PARTIALLY_BLOCKED", "DISABLED"])
def test_inactive_assertions_keep_explicit_reason(status):
    model = Assertion.model_validate(assertion(test_status=status, blocking_reason="missing-runtime-capability"))
    assert model.test_status == status
    assert model.blocking_reason == "missing-runtime-capability"


def test_retry_attempt_sequences_cannot_reset_original_allowance(package):
    script = read(package, "behaviors/unit.json")
    operation = script["operations"][0]
    operation["attempts"] = [
        {"attempt": 1, "behavior": "TIMEOUT", "simulated_duration_ms": 11000},
        {"attempt": 2, "behavior": "SUCCESS", "simulated_duration_ms": 1, "response_fixture_id": "ocean-marine-forecast"},
    ]
    assert BehaviorScript.model_validate(script)
    operation["attempts"].append(dict(operation["attempts"][1], attempt=3))
    with pytest.raises(ValidationError):
        BehaviorScript.model_validate(script)
