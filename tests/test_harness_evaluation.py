"""SH-T06/13..17: independent comparisons, capture integrity and honest readiness."""

import asyncio
from dataclasses import replace
import json

import pytest

from hawaii_activity_forecaster import cli
from hawaii_activity_forecaster.demo import run_demo
from hawaii_activity_forecaster.harness import Assertion, ExpectedResults, load_scenario
from hawaii_activity_forecaster.harness.evaluation import CaptureError, capture_report, evaluate_assertions, evaluate_scenario, _equal
from hawaii_activity_forecaster.config.settings import TraceSettings
from trace_samples import FIXTURES


@pytest.fixture
def captured(tmp_path):
    sample = asyncio.run(run_demo("advisory", FIXTURES, trace_settings=TraceSettings(directory=tmp_path)))
    scenario = load_scenario(FIXTURES, "SC-004")
    capture = capture_report(1, sample.report, catalog=sample.catalog, policy=sample.policy, driver_inputs=scenario.driver)
    return capture, sample, scenario


def assertion(op="EQUALS", **changes):
    data = dict(assertion_id="unit", requirement_ids=["SH-T15"], mandatory=True, test_status="ACTIVE",
                target="investigation_state", selector={"request_step": 1}, operator=op)
    if op in {"EQUALS", "NOT_EQUALS", "ALL_EQUALS"}:
        data.update(field="/activity", expected="SNORKELING")
    if op in {"COUNT_EQUALS", "COUNT_AT_MOST"}:
        data["expected"] = 1
    return Assertion.model_validate(data | changes)


def evaluate(capture, *assertions):
    expected = ExpectedResults(harness_contract_version="1.0.0", scenario_id="unit", assertions=list(assertions))
    return evaluate_assertions(expected, (capture,))


@pytest.mark.parametrize("scenario_id,case", [("SC-004", "advisory"), ("SC-010", "outage")])
def test_authored_assertions_use_real_component_captures_without_claiming_scenario_pass(tmp_path, scenario_id, case):
    scenario = load_scenario(FIXTURES, scenario_id)
    sample = asyncio.run(run_demo(case, FIXTURES, trace_settings=TraceSettings(directory=tmp_path)))
    capture = capture_report(1, sample.report, catalog=sample.catalog, policy=sample.policy, driver_inputs=scenario.driver)
    component = evaluate_assertions(scenario.evaluator.expected_results, (capture,))
    assert component.outcome == "PASS"
    assert component.scope == "COMPONENT"
    assert component.counts["PASS"] == len(component.assertions)
    report = evaluate_scenario(FIXTURES, scenario_id, captures=(capture,))
    assert report.outcome == "BLOCKED" and report.category == "SCENARIO_ADAPTER_UNAVAILABLE"
    assert report.scope == "SCENARIO" and report.artifact_digests and report.trace_digests


@pytest.mark.parametrize("op,expected_outcome", [("EQUALS","PASS"),("NOT_EQUALS","FAIL"),("ALL_EQUALS","PASS"),
    ("COUNT_EQUALS","PASS"),("COUNT_AT_MOST","PASS"),("EXISTS","PASS"),("ABSENT","FAIL")])
def test_operator_semantics(captured, op, expected_outcome):
    assert evaluate(captured[0], assertion(op)).outcome == expected_outcome


@pytest.mark.parametrize("op,field,expected,outcome", [("INCLUDES","/candidate_beach_ids","TEST_BEACH_B","PASS"),
    ("EXCLUDES","/candidate_beach_ids","TEST_BEACH_B","FAIL"),
    ("EQUALS","/experience_level",None,"PASS")])
def test_membership_and_explicit_null(captured, op, field, expected, outcome):
    assert evaluate(captured[0], assertion(op,field=field,expected=expected)).outcome == outcome


@pytest.mark.parametrize("op", ["SAME_AS","DIFFERENT_FROM"])
def test_cross_actual_reference_cardinality_and_missing_step(captured, op):
    item = assertion("EXISTS").model_dump(exclude_unset=True) | dict(operator=op,field="/activity",
        expected_ref=dict(target="investigation_state",selector={"request_step":1},field="/activity"))
    a = Assertion.model_validate(item)
    assert evaluate(captured[0], a).outcome == ("PASS" if op == "SAME_AS" else "FAIL")
    item["expected_ref"]["selector"]["request_step"] = 2
    assert evaluate(captured[0], Assertion.model_validate(item)).assertions[0].reason == "CAPTURE_MISSING"


@pytest.mark.parametrize("op", ["EQUALS","NOT_EQUALS","ALL_EQUALS","INCLUDES","EXCLUDES"])
def test_missing_pointer_fails_instead_of_comparing_to_null(captured, op):
    a = assertion(op, field="/candidate_beach_ids/99" if op not in {"INCLUDES","EXCLUDES"} else "/assessments/99/supporting_finding_ids",
                  expected="TEST_BEACH_B")
    result = evaluate(captured[0], a)
    assert result.outcome == "FAIL" and result.assertions[0].reason == "POINTER_MISSING"


@pytest.mark.parametrize("op", ["ALL_EQUALS","EQUALS","NOT_EQUALS"])
def test_empty_matches_are_not_vacuous_success(captured, op):
    a = assertion(op,target="candidate_assessment",selector={"request_step":1,"beach_id":"not-present"},field="/activity")
    assert evaluate(captured[0], a).outcome == "FAIL"


def test_unbound_and_ambiguous_finding_references_fail_even_absent(captured):
    cap = captured[0]
    a = assertion("ABSENT", target="environmental_finding", selector={"request_step":1,
        "source_fixture_id":"not-retrieved","template_finding_id":"not-bound"})
    assert evaluate(cap,a).assertions[0].reason == "REFERENCE_UNBOUND_OR_AMBIGUOUS"
    binding = next(b for b in cap.bindings if b.findings)
    selector = dict(request_step=1,source_fixture_id=binding.source_fixture_id,template_finding_id=binding.findings[0].template_finding_id)
    a = assertion("EXISTS", target="environmental_finding",selector=selector)
    duplicate = replace(binding, runtime_tool_call_id="different-call",operation_id="different-operation")
    ambiguous = replace(cap,bindings=cap.bindings+(duplicate,))
    assert evaluate(ambiguous,a).outcome == "FAIL"
    a = assertion("EXISTS",target="environmental_finding",selector=selector|dict(operation_id=binding.operation_id,attempt=binding.attempt))
    assert evaluate(ambiguous,a).outcome == "PASS"


@pytest.mark.parametrize("status,outcome", [("BLOCKED","BLOCKED"),("PARTIALLY_BLOCKED","BLOCKED"),("DISABLED","NOT_RUN")])
def test_inactive_assertions_and_mandatory_failure_precedence(captured,status,outcome):
    inactive = assertion(test_status=status,blocking_reason="Missing reviewed rule")
    assert evaluate(captured[0],inactive).outcome == outcome
    failed = assertion("NOT_EQUALS",assertion_id="failed")
    assert evaluate(captured[0],inactive,failed).outcome == "FAIL"


def test_optional_failure_reported_and_not_counted_as_mandatory_failure(captured):
    result = evaluate(captured[0],assertion(),assertion("NOT_EQUALS",assertion_id="optional",mandatory=False))
    assert result.outcome == "PASS" and result.counts["FAIL"] == 1 and result.counts["PASS"] == 1
    result = evaluate(captured[0],assertion(mandatory=False))
    assert result.outcome == "NOT_RUN"


def test_missing_collection_duplicate_steps_and_empty_attempt_are_failures(captured):
    cap = captured[0]
    records = cap.records
    records["recommendation"] = None
    missing = replace(cap,_records=json.dumps(records).encode())
    assert evaluate(missing,assertion("ABSENT",target="recommendation")).outcome == "FAIL"
    expected = ExpectedResults(harness_contract_version="1.0.0",scenario_id="unit",assertions=[assertion("ABSENT")])
    assert evaluate_assertions(expected,()).outcome == "FAIL"
    assert evaluate_assertions(expected,(cap,cap)).outcome == "FAIL"
    assert evaluate_assertions(expected,None).outcome == "BLOCKED"


def test_capture_checks_artifact_and_detaches_observations(captured):
    cap,sample,scenario = captured
    cap.records["investigation_state"][0]["activity"]="SUP"
    assert cap.records["investigation_state"][0]["activity"]=="SNORKELING"
    sample.report.trace_path.unlink()
    with pytest.raises(CaptureError,match="CAPTURE_INVALID"):
        capture_report(1,sample.report,catalog=sample.catalog,policy=sample.policy,driver_inputs=scenario.driver)


def test_fixture_invalid_and_evaluator_error_are_distinct(tmp_path,monkeypatch):
    import hawaii_activity_forecaster.harness.evaluation as module
    assert evaluate_scenario(tmp_path,"SC-004").category=="FIXTURE_INVALID"
    def fail(*args,**kwargs):
        raise RuntimeError("private evaluator payload")
    monkeypatch.setattr(module,"load_scenario",fail)
    result=evaluate_scenario(FIXTURES,"SC-004")
    assert result.outcome=="FAIL" and result.category=="EVALUATOR_ERROR" and "private" not in repr(result)


def test_context_mismatch_cannot_pass_and_active_failure_dominates_runtime_blocker(captured):
    cap=captured[0]
    assert evaluate_scenario(FIXTURES,"SC-004",captures=(replace(cap,input_digest="wrong"),)).outcome=="FAIL"
    records=cap.records
    records["recommendation"]=[]
    result=evaluate_scenario(FIXTURES,"SC-004",captures=(replace(cap,_records=json.dumps(records).encode()),))
    assert result.outcome=="FAIL" and result.counts["FAIL"]>0


@pytest.mark.parametrize("left,right", [(True,1),(False,0),([True],[1]),({"x":True},{"x":1}),("1",1)])
def test_json_comparison_never_coerces_booleans_or_strings(left,right):
    assert not _equal(left,right)


def test_cli_readiness_report_does_not_dispatch(capsys,monkeypatch):
    import hawaii_activity_forecaster.demo as module
    async def forbidden(*args,**kwargs):
        pytest.fail("Readiness reporting dispatched application work")
    monkeypatch.setattr(module,"run_demo",forbidden)
    assert cli.main(["evaluate","SC-004","--fixtures",str(FIXTURES)])==2
    result=json.loads(capsys.readouterr().out)
    assert result["outcome"]=="BLOCKED" and result["counts"]["PASS"]==0


@pytest.mark.parametrize("status,outcome",[("BLOCKED","BLOCKED"),("DISABLED","NOT_RUN")])
def test_scenario_status_prevents_capture_evaluation(status,outcome,captured,monkeypatch):
    import hawaii_activity_forecaster.harness.evaluation as module
    loaded=captured[2]
    definition=loaded.definition.model_dump(mode="json",exclude_unset=True)|{"test_status":status}
    fake=replace(loaded,_definition=json.dumps(definition).encode())
    monkeypatch.setattr(module,"load_scenario",lambda *args:fake)
    result=evaluate_scenario(FIXTURES,"SC-004",captures=(captured[0],))
    assert result.outcome==outcome and result.counts["PASS"]==0


def test_cross_step_actual_comparisons(captured):
    first=captured[0]
    data=first.records
    data["investigation_state"][0]["investigation_id"]="new-investigation"
    second=replace(first,request_step=2,_records=json.dumps(data).encode())
    expected=ExpectedResults(harness_contract_version="1.0.0",scenario_id="unit",assertions=[
        Assertion.model_validate(dict(assertion_id="cross",requirement_ids=["SH-T18"],mandatory=True,test_status="ACTIVE",
            target="investigation_state",selector={"request_step":2},operator="DIFFERENT_FROM",field="/investigation_id",
            expected_ref=dict(target="investigation_state",selector={"request_step":1},field="/investigation_id")))])
    assert evaluate_assertions(expected,(first,second)).outcome=="PASS"


def test_optional_null_selector_keys_do_not_filter_out_all_records(captured):
    a=assertion("EXISTS",target="candidate_assessment",selector={"request_step":1,"beach_id":None,"activity":None})
    assert evaluate(captured[0],a).outcome=="PASS"
