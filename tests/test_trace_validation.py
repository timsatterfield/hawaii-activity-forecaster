"""TL-001..012 / IT correlations and completeness of observed local events."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from hawaii_activity_forecaster.observability import TraceValidationError, inspect_trace, read_trace
from hawaii_activity_forecaster.presentation import PresentationError, render_report
from trace_samples import output, records, rewrite


@pytest.mark.parametrize("case,status,tools,retries,fallbacks", [
    ("advisory", "COMPLETED", 6, 0, 0), ("outage", "ABSTAINED", 8, 1, 2),
])
def test_actual_trace_schema_correlations_versions_metrics_and_terminal_match(tmp_path, case, status, tools, retries, fallbacks):
    sample = output(tmp_path, case)
    report = sample.report
    trace = read_trace(report.trace_path)
    validation = inspect_trace(report.trace_path, state=report.state, result=report.result, budgets=report.budgets,
                               bindings=report.tool_bindings, evidence=report.evidence_report, safety=report.safety_report)
    assert report.state.status == status, report.state.completion_reason
    assert validation == report.trace_validation and validation.complete
    assert trace.investigation_id == report.state.investigation_id and trace.final_status == status
    assert trace.configuration_version == trace.schema_version == "0.1" and trace.policy_version == "0.2"
    assert trace.model_identifier is None
    assert [e.sequence_number for e in trace.events] == list(range(1, len(trace.events) + 1))
    assert len({e.event_id for e in trace.events}) == validation.event_count
    assert validation.metrics.tool_calls == tools and validation.metrics.model_calls == 0
    assert validation.metrics.retries == retries and validation.metrics.fallbacks == fallbacks
    assert validation.metrics.specialist_requests == 2 and validation.metrics.duration_ms >= 0
    assert validation.metrics.evidence_accepted == len({f.finding_id for f in report.state.weather_findings + report.state.ocean_findings
                                                      if f.validation_status == "ACCEPTED"})
    if case == "advisory":
        assert validation.metrics.eligible_candidates == validation.metrics.excluded_candidates == 1
    else:
        assert validation.metrics.unresolved_candidates == 4
    last = trace.events[-1].details
    assert last["total_tool_calls"] == tools and last["total_iterations"] == report.budgets.iterations
    assert last["result_id"] == report.result.result_id
    assert last["recommended_beach_ids"] == [r.beach_id for r in report.result.recommendations]
    assert "SYNTHETIC TEST OUTPUT" in render_report(report, catalog=sample.catalog, policy=sample.policy)


def corrupt(items, tamper):
    def first(kind):
        return next(item for item in items if item["event_type"] == kind)
    if tamper == "tool-outcome-missing":
        items.remove(first("TOOL_COMPLETED"))
    elif tamper == "policy-missing":
        items.remove(first("POLICY_EVALUATED"))
    elif tamper == "candidate-missing":
        items.remove(first("CANDIDATE_ASSESSED"))
    elif tamper == "result-validation-missing":
        items.remove(first("RESULT_VALIDATED"))
    elif tamper == "normalization-missing":
        items.remove(first("REQUEST_NORMALIZED"))
    elif tamper == "tool-parent":
        first("TOOL_COMPLETED")["details"]["request_id"] = "old-delegation"
    elif tamper == "tool-source":
        first("TOOL_CALLED")["details"]["source_id"] = "NDBC"
    elif tamper == "finding":
        first("EVIDENCE_VALIDATED")["details"]["finding_id"] = "not-retrieved"
    elif tamper == "finding-source":
        first("EVIDENCE_VALIDATED")["details"]["source_id"] = "NDBC"
    elif tamper == "policy-support":
        first("POLICY_EVALUATED")["details"]["supporting_finding_ids"] = ["not-retrieved"]
    elif tamper == "wrong-actor":
        first("TOOL_CALLED")["actor"] = "CLI"
    elif tamper == "old-revision":
        first("TOOL_COMPLETED")["request_revision"] += 1
    elif tamper == "wrong-investigation":
        first("TOOL_COMPLETED")["details"]["investigation_id"] = "old-investigation"
    elif tamper == "duplicate-id":
        items[1]["event_id"] = items[0]["event_id"]
    elif tamper == "privacy":
        items[1]["details"]["api_key"] = "EXAMPLE_CREDENTIAL"
    elif tamper == "counter":
        items[-1]["details"]["total_tool_calls"] -= 1
    elif tamper == "outcome":
        items[-1]["details"]["outcome"] = "ERROR"
    elif tamper == "selected-beach":
        items[-1]["details"]["recommended_beach_ids"] = ["TEST_BEACH_A"]
    elif tamper == "after-terminal":
        items.append(deepcopy(items[1]))
        items[-1]["event_id"] = "extra-event"
    elif tamper == "version":
        items[0]["details"]["trace_metadata"]["configuration_version"] = "unapproved"
    return items


@pytest.mark.parametrize("tamper", [
    "tool-outcome-missing", "policy-missing", "candidate-missing", "result-validation-missing", "normalization-missing",
    "tool-parent", "tool-source", "finding", "finding-source", "policy-support", "wrong-actor", "old-revision",
    "wrong-investigation", "duplicate-id", "privacy", "counter", "outcome", "selected-beach", "after-terminal", "version",
])
def test_independent_reader_rejects_missing_or_tampered_material_events(tmp_path, tamper):
    sample = output(tmp_path)
    path = sample.report.trace_path
    rewrite(path, corrupt(records(path), tamper))
    with pytest.raises(TraceValidationError):
        inspect_trace(path)
    with pytest.raises(PresentationError):
        render_report(sample.report, catalog=sample.catalog, policy=sample.policy)


@pytest.mark.parametrize("damage", ["newline", "json", "utf8", "duplicate-key", "nonfinite", "gap", "empty"])
def test_reader_detects_corrupt_files_without_modifying_them(tmp_path, damage):
    path = output(tmp_path).report.trace_path
    payload = path.read_bytes()
    if damage == "newline":
        payload = payload[:-1]
    elif damage == "json":
        payload += b'{"broken":\n'
    elif damage == "utf8":
        payload = b'\xff\n'
    elif damage == "duplicate-key":
        payload = payload.replace(b'"event_id":', b'"event_id":"hidden-value","event_id":', 1)
    elif damage == "nonfinite":
        payload = payload.replace(b'"model_call_count":0', b'"model_call_count":NaN', 1)
    elif damage == "empty":
        payload = b""
    else:
        items = records(path)
        items[1]["sequence_number"] = 99
        payload = b"".join(json.dumps(item).encode() + b"\n" for item in items)
    path.write_bytes(payload)
    with pytest.raises(TraceValidationError):
        inspect_trace(path)
    assert path.read_bytes() == payload


def test_valid_partial_trace_has_no_fabricated_terminal_or_recommendation(tmp_path):
    sample = output(tmp_path)
    path = sample.report.trace_path
    items = records(path)
    rewrite(path, items[:5])
    trace = read_trace(path)
    validation = inspect_trace(path)
    assert trace.final_status is trace.completed_at is None
    assert validation.complete is False and validation.metrics.outcome is None
    assert not any(e.event_type.startswith("INVESTIGATION_COMPLETED") for e in trace.events)
    with pytest.raises(PresentationError):
        render_report(sample.report, catalog=sample.catalog, policy=sample.policy)


@pytest.mark.parametrize("tamper", ["delete", "valid-byte-change", "receipt", "path", "path-and-receipt", "state", "result"])
def test_presentation_checks_current_artifact_bytes_and_runtime_truth(tmp_path, tamper):
    sample = output(tmp_path)
    report = sample.report
    if tamper == "delete":
        report.trace_path.unlink()
    elif tamper == "valid-byte-change":
        # Same event values, different bytes: the retained publication receipt
        # must not silently authorize a replacement artifact.
        rewrite(report.trace_path, records(report.trace_path))
    elif tamper == "receipt":
        report = replace(report, trace_validation=None)
    elif tamper == "path":
        report = replace(report, trace_path=None)
    elif tamper == "path-and-receipt":
        report = replace(report, trace_path=None, trace_validation=None)
    elif tamper == "state":
        report = replace(report, state=report.state.model_copy(update={"session_id": "other-session"}))
    else:
        report = replace(report, result=report.result.model_copy(update={"result_id": "other-result"}))
    with pytest.raises(PresentationError):
        render_report(report, catalog=sample.catalog, policy=sample.policy)
