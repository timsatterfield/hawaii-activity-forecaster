"""Preflight, owned snapshots, raw lifecycle and honest authored execution reports."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from hawaii_activity_forecaster import cli
from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.demo import authored_component_runner, authored_interpretation
from hawaii_activity_forecaster.harness.execution import execute_scenario
from hawaii_activity_forecaster.harness.loading import LoadedScenario
from hawaii_activity_forecaster.observability import JsonlTraceWriter, TraceValidationError, TraceWriteError, inspect_trace, read_trace
from hawaii_activity_forecaster.orchestration import BudgetManager
from interpretation_samples import proposal
from trace_samples import FIXTURES, records, rewrite


def execute(tmp_path, sid="SC-004", *, runtime=None, root=FIXTURES):
    return asyncio.run(execute_scenario(root, sid, runtime=runtime,
                                        trace_settings=TraceSettings(directory=tmp_path / "traces")))


@pytest.mark.parametrize("sid,case,count,calls", [("SC-004","advisory",84,6),("SC-010","outage",61,8)])
def test_connected_components_pass_without_becoming_full_agentic_acceptance(tmp_path,sid,case,count,calls):
    result=execute(tmp_path,sid,runtime=authored_component_runner(case))
    assert result.mode=="AUTHORED_COMPONENT" and result.attempted_steps==(1,)
    assert result.component.outcome=="PASS" and result.component.counts["PASS"]==count
    assert result.outcome==result.scenario.outcome=="BLOCKED"
    assert result.scenario.category=="SCENARIO_ADAPTER_UNAVAILABLE"
    assert result.scenario.artifact_digests and len(result.scenario.trace_digests)==1
    path,=(tmp_path/"traces").glob("*.jsonl")
    audit=inspect_trace(path)
    assert audit.complete and audit.metrics.tool_calls==calls and audit.metrics.model_calls==0
    assert audit.metrics.iterations==1
    trace=read_trace(path)
    normalized=next(e for e in trace.events if e.event_type=="REQUEST_NORMALIZED")
    assert normalized.details["assumed_fields"]==["target_time_window"]
    if case=="outage":
        limits=[e for e in trace.events if e.event_type=="INVESTIGATION_LIMIT_REACHED"]
        assert len(limits)==2
        assert {e.details["budget_kind"] for e in limits}=={"fallback_per_evidence_gap"}
        assert all(e.details["configured_limit"]==1 for e in limits)
        assert trace.events[-1].details["stop_reason"]=="NO_FURTHER_ACTION"
        assert trace.events[-1].details["no_recommendation_reason"]=="INSUFFICIENT_EVIDENCE"
    else:
        assert not any(e.event_type=="INVESTIGATION_LIMIT_REACHED" for e in trace.events)


@pytest.mark.parametrize("status,outcome",[("BLOCKED","BLOCKED"),("DISABLED","NOT_RUN"),("INVALID","FAIL")])
def test_preflight_and_readiness_gates_prevent_all_runtime_work(tmp_path,status,outcome):
    root=tmp_path/"pack"
    shutil.copytree(FIXTURES,root)
    file=root/"scenarios/SC-004/scenario.json"
    data=json.loads(file.read_text())
    data["test_status"]=status
    file.write_text(json.dumps(data))
    async def forbidden(inputs):
        pytest.fail("Preflight/readiness failure dispatched runtime work")
    result=execute(tmp_path,root=root,runtime=forbidden)
    assert result.outcome==outcome and result.attempted_steps==() and result.component is None
    assert not (tmp_path/"traces").exists()
    if status=="INVALID":
        assert result.scenario.category=="FIXTURE_INVALID"


def test_missing_runtime_is_blocked_without_trace_creation(tmp_path):
    result=execute(tmp_path)
    assert result.outcome=="BLOCKED" and result.component is None and result.attempted_steps==()
    assert not (tmp_path/"traces").exists()


def test_oracle_snapshot_never_enters_runtime_and_is_not_reloaded_after_dispatch(tmp_path,monkeypatch):
    root=tmp_path/"pack"
    shutil.copytree(FIXTURES,root)
    expected=root/"scenarios/SC-004/expected.json"
    reads=[]
    original=Path.read_bytes
    def read(path):
        if path==expected:
            reads.append(1)
        return original(path)
    monkeypatch.setattr(Path,"read_bytes",read)
    original_evaluator=LoadedScenario.evaluator.fget
    in_runtime=[False]
    def evaluator(self):
        assert not in_runtime[0], "Runtime accessed evaluator projection"
        return original_evaluator(self)
    monkeypatch.setattr(LoadedScenario,"evaluator",property(evaluator))
    delegate=authored_component_runner("advisory")
    async def runtime(inputs):
        in_runtime[0]=True
        try:
            for name in ("evaluator","definition","expected_results","artifact_digests","scenario"):
                assert not hasattr(inputs,name)
            assert not hasattr(inputs.admission,"findings")
            expected.write_text("invalid after preflight; must never be read again")
            return await delegate(inputs)
        finally:
            in_runtime[0]=False
    result=execute(tmp_path,root=root,runtime=runtime)
    assert result.component.outcome=="PASS" and result.outcome=="BLOCKED" and reads==[1]


@pytest.mark.parametrize("fault",["exception","missing-report","mutated-report"])
def test_failure_after_admission_is_fail_not_dependency_blocker(tmp_path,fault):
    delegate=authored_component_runner("advisory")
    async def runtime(inputs):
        if fault=="exception":
            raise RuntimeError("private runtime payload")
        if fault=="missing-report":
            return None
        report=await delegate(inputs)
        return replace(report,trace_validation=None)
    result=execute(tmp_path,runtime=runtime)
    assert result.outcome=="FAIL" and result.component.outcome=="FAIL" and result.attempted_steps==(1,)
    assert result.scenario.category=="APPLICATION_FAILURE"
    assert "private runtime payload" not in repr(result)


def test_trace_failure_stops_execution_and_cannot_become_a_pass(tmp_path,monkeypatch):
    original=JsonlTraceWriter.append
    def fail(self,event):
        if event.event_type=="TOOL_CALLED":
            raise TraceWriteError("private trace payload")
        return original(self,event)
    monkeypatch.setattr(JsonlTraceWriter,"append",fail)
    result=execute(tmp_path,runtime=authored_component_runner("advisory"))
    assert result.outcome=="FAIL" and result.scenario.category=="CAPTURE_INVALID"
    assert result.component.counts["PASS"]==0
    assert "private trace payload" not in repr(result)


def test_fallback_capacity_is_based_on_dispatch_not_reservations_or_script_availability():
    budget=BudgetManager()
    assert not budget.fallback_allowance_exhausted("gap")
    budget.reserve("fallback","tool",fallback_gap="gap")
    assert not budget.fallback_allowance_exhausted("gap")
    budget.dispatch("fallback")
    budget.finish("fallback",failed=True)
    assert budget.fallback_allowance_exhausted("gap")
    assert not budget.fallback_allowance_exhausted("different-gap")
    budget.close()
    assert budget.fallback_allowance_exhausted("gap")


def test_followup_uses_fresh_investigation_and_budget_without_reopening_prior_trace(tmp_path):
    root=tmp_path/"pack"
    shutil.copytree(FIXTURES,root)
    behavior=root/"behaviors/sc-004.json"
    data=json.loads(behavior.read_text())
    data["requests"].append(dict(request_step=2,user_request="Near Napili instead.",reference_time="2026-11-16T09:15:00-10:00"))
    data["operations"] += [op|dict(operation_id=op["operation_id"]+"-step2",request_step=2) for op in data["operations"]]
    behavior.write_text(json.dumps(data))
    def interpret(inputs):
        if inputs.request_revision==1:
            return authored_interpretation(inputs)
        text=inputs.original_request
        return proposal(text,{"preferred_area":"Napili"},{"preferred_area":"Near Napili"})
    delegate=authored_component_runner("advisory",interpreter=interpret)
    reports=[]
    async def runtime(inputs):
        if reports:
            old,old_bytes=reports[0]
            assert old.trace_path.read_bytes()==old_bytes
            assert inputs.admission.inherited.request.preferred_area=="Kihei"
        report=await delegate(inputs)
        reports.append((report,report.trace_path.read_bytes()))
        return report
    result=execute(tmp_path,root=root,runtime=runtime)
    assert result.attempted_steps==(1,2) and result.component.outcome=="PASS" and result.outcome=="BLOCKED"
    first,second=[r for r,_ in reports]
    assert first.state.session_id==second.state.session_id
    assert first.state.investigation_id!=second.state.investigation_id
    assert (first.state.request_revision,second.state.request_revision)==(1,2)
    assert first.state.preferred_area=="Kihei" and second.state.preferred_area=="Napili"
    assert first.state.target_time_window==second.state.target_time_window
    assert first.budgets.tool_calls==second.budgets.tool_calls==6
    assert reports[0][0].trace_path.read_bytes()==reports[0][1]
    assert len(result.scenario.trace_digests)==2


def test_cli_component_execution_requires_opt_in_and_reports_both_scopes(tmp_path,capsys):
    assert cli.main(["evaluate","SC-004","--fixtures",str(FIXTURES)])==2
    assert "component" not in json.loads(capsys.readouterr().out)
    assert cli.main(["evaluate","SC-004","--fixtures",str(FIXTURES),"--component","--trace-directory",str(tmp_path)])==2
    report=json.loads(capsys.readouterr().out)
    assert report["mode"]=="AUTHORED_COMPONENT" and report["component"]["outcome"]=="PASS"
    assert report["scenario"]["outcome"]==report["outcome"]=="BLOCKED"


@pytest.mark.parametrize("field,value",[("gap_id","not-dispatched"),("configured_limit",2),
    ("category","OFFICIAL_ADVISORIES"),("candidate_beach_ids",[])])
def test_reader_rejects_fabricated_recovery_exhaustion(tmp_path,field,value):
    result=execute(tmp_path,"SC-010",runtime=authored_component_runner("outage"))
    assert result.component.outcome=="PASS"
    path,=(tmp_path/"traces").glob("*.jsonl")
    items=records(path)
    event=next(e for e in items if e["event_type"]=="INVESTIGATION_LIMIT_REACHED")
    event["details"][field]=value
    rewrite(path,items)
    with pytest.raises(TraceValidationError,match="RECOVERY_LIMIT_UNGROUNDED"):
        inspect_trace(path)
