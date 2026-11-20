"""Observability §§12/15.5: honest denominators, failure evidence and read-only reporting."""

import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import shutil

import pytest

from hawaii_activity_forecaster.agents.data import load_release_data
from hawaii_activity_forecaster.agents.scenario import execute_agent_scenario
from hawaii_activity_forecaster.agents.session import AgentSession
from hawaii_activity_forecaster.cli import main
from hawaii_activity_forecaster.config import TraceSettings
from hawaii_activity_forecaster.observability.reliability import build_reliability_report, render_markdown
from release_samples import adapter
from trace_samples import output

ROOT = Path(__file__).resolve().parents[1]


def model_run(tmp_path, text, *, failure=None, profile=None):
    options = {} if profile is None else dict(profile=profile)
    session = AgentSession(load_release_data(ROOT / "fixtures/saturday-release"), adapter([], failure=failure, **options),
                           trace_settings=TraceSettings(directory=tmp_path))
    try:
        return asyncio.run(session.ask(text))
    finally:
        session.close()


def scenario_run(tmp_path, scenario="SC-004", *, root=None):
    result = asyncio.run(execute_agent_scenario(root or ROOT / "fixtures/scenario-pack-v1", scenario,
        adapter=adapter([]), trace_settings=TraceSettings(directory=tmp_path / "traces")))
    path = tmp_path / "report.json"
    path.write_text(json.dumps(asdict(result)))
    return result, path


def test_authored_abstention_is_success_and_duplicate_copies_do_not_inflate_counts(tmp_path):
    a = output(tmp_path / "a")
    b = output(tmp_path / "b", "outage")
    shutil.copyfile(a.report.trace_path, tmp_path / "copy.jsonl")
    original = {p: p.read_bytes() for p in tmp_path.rglob("*.jsonl")}
    report = build_reliability_report([tmp_path, a.report.trace_path])
    assert not report["issues"] and report["valid_investigations"] == 2 and report["duplicate_traces"] == 1
    group, = report["trace_groups"]
    assert group["execution_mode"] == "AUTHORED_COMPONENT" and group["profile_id"] == "NO_MODEL_PROFILE"
    assert group["statuses"] == {"ABSTAINED": 1, "COMPLETED": 1}
    assert group["operational_success"] == dict(numerator=2, denominator=2, rate=1)
    assert group["tool_calls"]["total"] == 14 and group["model_calls"]["total"] == 0
    assert all(path.read_bytes() == contents for path, contents in original.items())
    assert b.report.result.outcome == "NO_RECOMMENDATION"


def test_clarification_is_not_a_terminal_failure_or_latency_sample(tmp_path):
    result = model_run(tmp_path, "Where tomorrow morning?")
    assert result.state.status == "AWAITING_CLARIFICATION"
    report = build_reliability_report([tmp_path])
    assert not report["issues"]
    group, = report["trace_groups"]
    assert group["execution_mode"] == "OFFLINE_TRANSPORT"
    assert group["statuses"] == {"AWAITING_CLARIFICATION": 1}
    assert group["operational_success"] == dict(numerator=0, denominator=0, rate=None)
    assert group["terminal_duration_ms"]["count"] == 0 and group["terminal_duration_ms"]["median"] is None
    assert group["model_calls"]["total"] == 1 and group["tool_calls"]["total"] == 0


def test_model_failure_and_authored_execution_stay_in_separate_groups(tmp_path):
    model_run(tmp_path / "model", "Where should I swim tomorrow morning?", failure="normalize_request")
    output(tmp_path / "authored")
    report = build_reliability_report([tmp_path])
    assert not report["issues"] and len(report["trace_groups"]) == 2
    group = next(g for g in report["trace_groups"] if g["execution_mode"] == "OFFLINE_TRANSPORT")
    assert group["operational_success"] == dict(numerator=0, denominator=1, rate=0)
    assert group["statuses"] == {"FAILED": 1}
    assert any(f["stage"] == "normalize_request" and f["code"] == "MODEL_RATE_LIMIT" for f in group["failure_events"])
    assert all("private provider error" not in json.dumps(f) for f in group["failure_events"])


def test_missing_truncated_and_conflicting_inputs_remain_visible_without_payloads(tmp_path):
    result = output(tmp_path / "good")
    path = result.report.trace_path
    # Different bytes for the same investigation are conservatively conflicting,
    # even when both event streams independently validate.
    events = [json.loads(line) for line in path.read_text().splitlines()]
    (tmp_path / "reformatted.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (tmp_path / "bad.jsonl").write_text('PRIVATE_PAYLOAD sk-private-example')
    (tmp_path / "nested.jsonl").write_text("[" * 5000 + "\n")
    report = build_reliability_report([tmp_path, tmp_path / "missing.jsonl"])
    assert report["valid_investigations"] == 0
    assert {i["code"] for i in report["issues"]} == {
        "INPUT_NOT_FOUND_OR_WRONG_TYPE", "TRACE_INVALID_OR_UNREADABLE", "TRACE_IDENTITY_CONFLICT"}
    assert "PRIVATE_PAYLOAD" not in json.dumps(report) and "sk-private-example" not in render_markdown(report)


def test_saved_report_is_digest_bound_deduplicated_and_does_not_turn_mock_into_live(tmp_path):
    result, path = scenario_run(tmp_path)
    original = path.read_bytes()
    (tmp_path / "report-copy.json").write_text(json.dumps(asdict(result), indent=2))
    report = build_reliability_report([tmp_path / "traces"], report_inputs=[tmp_path])
    assert not report["issues"] and report["duplicate_reports"] == 1
    scenario, = report["scenario_groups"]
    assert scenario["recorded_outcomes"] == dict(PASS=0, FAIL=0, BLOCKED=1, NOT_RUN=0)
    assert scenario["execution_modes"] == ["OFFLINE_TRANSPORT"] and path.read_bytes() == original
    data = asdict(result)
    data["scenario"]["trace_digests"] = [[1, "0" * 64]]
    path.write_text(json.dumps(data))
    report = build_reliability_report([tmp_path / "traces"], report_inputs=[path])
    assert not report["scenario_groups"] and report["issues"][0]["code"] == "REPORT_INVALID_OR_UNBOUND"


def test_operational_recommendation_can_have_failed_acceptance_assertions(tmp_path):
    root = tmp_path / "pack"
    shutil.copytree(ROOT / "fixtures/scenario-pack-v1", root)
    path = root / "agent_tools/SC-004.json"
    options = json.loads(path.read_text())
    options["actions"] = [a for a in options["actions"] if a["action_id"] != "WATER_TEST_BEACH_A"]
    path.write_text(json.dumps(options))
    result, report_path = scenario_run(tmp_path, root=root)
    assert result.scenario.outcome == "FAIL"
    report = build_reliability_report([tmp_path / "traces"], report_inputs=[report_path])
    assert not report["issues"]
    assert report["trace_groups"][0]["operational_success"]["numerator"] == 1
    assert report["scenario_groups"][0]["recorded_outcomes"]["FAIL"] == 1


def test_multistep_report_is_one_scenario_and_two_investigations(tmp_path):
    _, path = scenario_run(tmp_path, "SC-012")
    report = build_reliability_report([tmp_path / "traces"], report_inputs=[path])
    assert not report["issues"] and report["valid_investigations"] == 2
    assert report["scenario_groups"][0]["runs"] == 1
    assert report["scenario_groups"][0]["optional_blocked"] == 1
    assert report["trace_groups"][0]["model_calls"]["total"] == 10


@pytest.mark.parametrize("mutation", ["mode", "counts", "conflicting", "ambiguous", "private-error"])
def test_untrustworthy_report_metadata_never_enters_scenario_totals(tmp_path, mutation):
    result, path = scenario_run(tmp_path)
    data = asdict(result)
    if mutation == "mode":
        data["execution_modes"] = ["LIVE_PROVIDER"]
    elif mutation == "counts":
        data["scenario"]["counts"]["PASS"] = 999
    elif mutation == "private-error":
        path.write_text('{"scenario": "PRIVATE_REQUEST_TEXT"}')
    else:
        other = deepcopy(data)
        if mutation == "conflicting":
            other["scenario"]["category"] = "ANOTHER_CATEGORY"
        else:
            other["scenario"]["scenario_id"] = "SC-999"
        (tmp_path / "other.json").write_text(json.dumps(other))
    if mutation not in {"conflicting", "ambiguous", "private-error"}:
        path.write_text(json.dumps(data))
    report = build_reliability_report([tmp_path / "traces"], report_inputs=[tmp_path])
    assert report["issues"] and not report["scenario_groups"]
    assert "PRIVATE_REQUEST_TEXT" not in json.dumps(report)


def test_cli_is_read_only_needs_no_provider_and_returns_nonzero_for_bad_inputs(tmp_path, monkeypatch, capsys):
    output(tmp_path)
    monkeypatch.setattr("hawaii_activity_forecaster.model_runtime.provider.create_adapter",
                        lambda *a, **k: pytest.fail("No model access during reporting"))
    assert main(["reliability", str(tmp_path), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["valid_investigations"] == 1
    assert main(["reliability", str(tmp_path)]) == 0
    markdown = capsys.readouterr().out
    assert "Operational success" in markdown and "AUTHORED_COMPONENT" in markdown
    assert main(["reliability", str(tmp_path / "empty")]) == 1
    assert "INPUT_NOT_FOUND_OR_WRONG_TYPE" in capsys.readouterr().out


def test_profile_and_recorded_mode_are_distinct_dimensions_not_network_proof(tmp_path):
    from hawaii_activity_forecaster.model_runtime.targets import SATURDAY_PROFILE_V6, SATURDAY_PROFILE
    model_run(tmp_path / "old", "Where tomorrow morning?", profile=SATURDAY_PROFILE_V6)
    model_run(tmp_path / "current", "Where tomorrow morning?")
    result = model_run(tmp_path / "relabeled", "Where tomorrow morning?")
    # Explicitly relabeled test data, as in test_model_trace_validation.py.
    # It exercises metadata grouping only and provides no live-provider evidence.
    events = [json.loads(line) for line in result.trace_path.read_text().splitlines()]
    events[0]["details"]["configuration"]["model_profile"]["execution_mode"] = "LIVE_PROVIDER"
    events[0]["details"]["component_probe"] = False
    for event in events:
        if event["details"].get("contract") == "model_dispatch":
            event["details"]["execution_mode"] = "LIVE_PROVIDER"
    result.trace_path.write_text("".join(json.dumps(e) + "\n" for e in events))
    report = build_reliability_report([tmp_path])
    assert not report["issues"]
    assert {(g["profile_id"], g["execution_mode"]) for g in report["trace_groups"]} == {
        (SATURDAY_PROFILE_V6, "OFFLINE_TRANSPORT"), (SATURDAY_PROFILE, "OFFLINE_TRANSPORT"),
        (SATURDAY_PROFILE, "LIVE_PROVIDER")}
    assert "trace-declared" in render_markdown(report)


def test_valid_nonterminal_prefix_has_no_success_denominator(tmp_path):
    sample = output(tmp_path)
    lines = sample.report.trace_path.read_text().splitlines()
    sample.report.trace_path.write_text("\n".join(lines[:2]) + "\n")
    report = build_reliability_report([tmp_path])
    assert not report["issues"]
    group, = report["trace_groups"]
    assert group["statuses"] == {"INCOMPLETE": 1}
    assert group["operational_success"]["denominator"] == 0


def test_optional_failures_remain_visible_in_saved_report_summary(tmp_path):
    root = tmp_path / "pack"
    shutil.copytree(ROOT / "fixtures/scenario-pack-v1", root)
    path = root / "agent_tools/SC-007.json"
    options = json.loads(path.read_text())
    options["actions"] = [a for a in options["actions"] if a["action_id"] != "STORE_REPORT_ABCD"]
    path.write_text(json.dumps(options))
    _, path = scenario_run(tmp_path, "SC-007", root=root)
    report = build_reliability_report([tmp_path / "traces"], report_inputs=[path])
    assert not report["issues"]
    scenario, = report["scenario_groups"]
    assert scenario["optional_failures"] == 6 and scenario["optional_blocked"] == 1
    assert scenario["recorded_outcomes"]["BLOCKED"] == 1  # Offline transport is never full acceptance.


def test_legacy_accounting_double_is_separate_from_authored_and_sdk_transport(tmp_path):
    from hawaii_activity_forecaster.orchestration import SessionManager, SyntheticModelAdapter
    from raw_graph_samples import initial_proposal
    from test_trace_graph import raw_start
    async def respond(operation, inputs):
        return initial_proposal()
    session = SessionManager()
    try:
        result = asyncio.run(raw_start(session, tmp_path / "legacy", model_adapter=SyntheticModelAdapter(respond)))
    finally:
        session.close()
    assert result.state.status == "COMPLETED"
    output(tmp_path / "authored")
    report = build_reliability_report([tmp_path])
    assert not report["issues"]
    assert {g["execution_mode"] for g in report["trace_groups"]} == {"AUTHORED_COMPONENT", "SYNTHETIC_ADAPTER"}
