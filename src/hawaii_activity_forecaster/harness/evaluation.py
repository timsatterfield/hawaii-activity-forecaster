"""Evaluator-only captured observations and deterministic assertion reporting.

Nothing here dispatches application/model/tool work. Expected values never enter
application inputs. Component assertion success is not full agentic acceptance:
scenario PASS also requires every capture's verified trace to record a genuine
live or local model target with actual model calls.
"""

from copy import deepcopy
from dataclasses import dataclass, field
import json
from hashlib import sha256
from typing import Literal

from .assertions import SELECTORS, ExecutionSummary, ExpectedResults, pointer_tokens
from .loading import load_scenario
from hawaii_activity_forecaster.fixtures import FixtureLoadError

Outcome = Literal["PASS", "FAIL", "BLOCKED", "NOT_RUN"]
GENUINE_MODEL_MODES = frozenset({"LIVE_PROVIDER", "LOCAL_PROVIDER"})


class CaptureError(ValueError):
    """Static missing/invalid observation diagnostic; no raw payloads."""


@dataclass(frozen=True)
class CapturedStep:
    request_step: int
    trace_digest: str
    bindings: tuple
    application_failed: bool
    input_digest: str
    driver_digest: str
    request_digest: str
    _records: bytes = field(repr=False)
    # Derived from the verified trace; the safe default is never a genuine model run.
    execution_mode: str = "AUTHORED_COMPONENT"
    model_invocation_count: int = 0

    @property
    def records(self):
        return json.loads(self._records)


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def capture_report(request_step, report, *, catalog, policy, driver_inputs) -> CapturedStep:
    """Detach runtime truth after independent trace/result checks, before evaluation.

    No expected file or scenario definition is accepted by this capture boundary.
    This is trusted in-process instrumentation, not a cryptographic credential.
    """
    from hawaii_activity_forecaster.observability import inspect_trace, read_trace
    from hawaii_activity_forecaster.presentation import render_report
    try:
        report = deepcopy(report)
        if type(request_step) is not int or request_step < 1 or report.trace_path is None:
            raise ValueError()
        checked = inspect_trace(report.trace_path, state=report.state, result=report.result, budgets=report.budgets,
                                bindings=report.tool_bindings, evidence=report.evidence_report, safety=report.safety_report)
        if checked != report.trace_validation or not checked.complete or not report.trace_writable:
            raise ValueError()
        if report.result is not None:
            if report.result_validation is None or not report.result_validation.authoritative_trace:
                raise ValueError()
            render_report(report, catalog=catalog, policy=policy)
            if report.result_validation.request_step != request_step:
                raise ValueError()
        trace = read_trace(report.trace_path)
        started = trace.events[0]
        if started.event_type != "INVESTIGATION_STARTED":
            raise ValueError()
        profile = started.details["configuration"].get("model_profile")
        execution_mode = profile["execution_mode"] if profile else "AUTHORED_COMPONENT"
        genuine = execution_mode in GENUINE_MODEL_MODES
        if (execution_mode not in GENUINE_MODEL_MODES | {"AUTHORED_COMPONENT", "OFFLINE_TRANSPORT"}
                or started.details.get("component_probe") is not (not genuine)
                or (profile is not None and report.budgets.model_calls < 1)):
            raise ValueError()
        active, maximum = set(), 0
        for event in trace.events:
            if event.event_type in {"AGENT_STARTED", "AGENT_COMPLETED", "AGENT_FAILED"}:
                key = event.details["request_id"], event.details["attempt_number"]
                if event.event_type == "AGENT_STARTED":
                    active.add(key)
                    maximum = max(maximum, len(active))
                else:
                    active.remove(key)
        if active or any(b.request_step != request_step for b in report.tool_bindings):
            raise ValueError()
        for binding in report.tool_bindings:
            operation = next(op for op in driver_inputs.script.operations if op.operation_id == binding.operation_id
                             and op.request_step == request_step)
            attempt = next(a for a in operation.attempts if a.attempt == binding.attempt)
            if attempt.response_fixture_id != binding.source_fixture_id:
                raise ValueError()
        state = report.state
        execution = ExecutionSummary(session_id=state.session_id, investigation_id=state.investigation_id,
            request_revision=state.request_revision, tool_invocation_count=report.budgets.tool_calls,
            model_invocation_count=report.budgets.model_calls, iteration_count=report.budgets.iterations,
            max_concurrent_specialists=maximum)
        records = {
            "investigation_state": [state.model_dump(mode="json")],
            "candidate_assessment": [a.model_dump(mode="json") for a in state.assessments],
            "environmental_finding": [f.model_dump(mode="json") for f in state.weather_findings + state.ocean_findings],
            "recommendation_result": [report.result.model_dump(mode="json")] if report.result else None,
            "recommendation": [r.model_dump(mode="json") for r in report.result.recommendations] if report.result else None,
            "trace_event": [e.model_dump(mode="json") for e in trace.events],
            "harness_execution": [execution.model_dump(mode="json")],
        }
        return CapturedStep(request_step, checked.digest, tuple(report.tool_bindings), state.status == "FAILED",
                            _digest([catalog.model_dump(mode="json"), policy.model_dump(mode="json")]),
                            _digest(driver_inputs.model_dump(mode="json", exclude_unset=True)), _digest(state.original_request),
                            json.dumps(records, allow_nan=False).encode(), execution_mode, report.budgets.model_calls)
    except Exception:
        raise CaptureError("CAPTURE_INVALID") from None


@dataclass(frozen=True)
class AssertionResult:
    assertion_id: str
    requirement_ids: tuple[str, ...]
    mandatory: bool
    outcome: Outcome
    reason: str


@dataclass(frozen=True)
class EvaluationReport:
    scenario_id: str
    scope: Literal["COMPONENT", "SCENARIO"]
    outcome: Outcome
    category: str
    assertions: tuple[AssertionResult, ...]
    counts: dict[str, int]
    artifact_digests: tuple[tuple[str, str], ...] = ()
    trace_digests: tuple[tuple[int, str], ...] = ()
    versions: tuple[tuple[str, str], ...] = (("harness_contract_version", "1.0.0"), ("schema_version", "0.1"),
        ("policy_version", "0.2"), ("configuration_version", "0.1"), ("fixture_format_version", "2.0.0"), ("fixture_package_version", "1.3.0"))


def _binding(capture, reference, *, finding):
    candidates = [b for b in capture.bindings if b.request_step == capture.request_step
        and ("operation_id" not in reference or (b.operation_id, b.attempt) == (reference["operation_id"], reference["attempt"]))
        and (not finding or b.source_fixture_id == reference["source_fixture_id"]
             and any(f.template_finding_id == reference["template_finding_id"] for f in b.findings))]
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) != 1:
        raise CaptureError("REFERENCE_UNBOUND_OR_AMBIGUOUS")
    binding = candidates[0]
    return ({f.runtime_finding_id for f in binding.findings if f.template_finding_id == reference["template_finding_id"]}
            if finding else {binding.runtime_tool_call_id})


def _select(target, selector, captures):
    selector = SELECTORS[target].model_validate(selector).model_dump(mode="json", exclude_none=True)
    capture = captures.get(selector["request_step"])
    if capture is None:
        raise CaptureError("CAPTURE_MISSING")
    values = capture.records.get(target)
    if values is None:
        raise CaptureError("COLLECTION_MISSING")
    for name in ("beach_id", "activity", "event_type", "actor"):
        if name in selector:
            values = [item for item in values if item.get(name) == selector[name]]
    if target == "environmental_finding" and ("source_fixture_id" in selector or "operation_id" in selector):
        if "source_fixture_id" in selector:
            ids = _binding(capture, selector, finding=True)
        else:
            call = _binding(capture, selector, finding=False)
            ids = {f.runtime_finding_id for b in capture.bindings if b.runtime_tool_call_id in call for f in b.findings}
        values = [item for item in values if item["finding_id"] in ids]
    if target == "trace_event":
        if "related_finding_ref" in selector:
            ids = _binding(capture, selector["related_finding_ref"], finding=True)
            values = [item for item in values if ids.intersection(item.get("related_ids") or [])]
        if "related_call_ref" in selector:
            ids = _binding(capture, selector["related_call_ref"], finding=False)
            values = [item for item in values if item["details"].get("tool_call_id") in ids or ids.intersection(item.get("related_ids") or [])]
    return values


def _pointer(record, pointer):
    try:
        value = record
        for token in pointer_tokens(pointer):
            value = value[int(token)] if isinstance(value, list) else value[token]
        return value
    except (KeyError, IndexError, TypeError, ValueError):
        raise CaptureError("POINTER_MISSING") from None


def _equal(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_equal(left[k], right[k]) for k in left)
    return left == right


def _test(assertion, captures):
    records = _select(assertion.target, assertion.selector, captures)
    op = assertion.operator
    if op in {"EXISTS", "ABSENT"}:
        return bool(records) if op == "EXISTS" else not records
    if op in {"COUNT_EQUALS", "COUNT_AT_MOST"}:
        return len(records) == assertion.expected if op == "COUNT_EQUALS" else len(records) <= assertion.expected
    if op == "ALL_EQUALS":
        return bool(records) and all(_equal(_pointer(record, assertion.field), assertion.expected) for record in records)
    if len(records) != 1:
        raise CaptureError("CARDINALITY_INVALID")
    actual = _pointer(records[0], assertion.field)
    if op in {"SAME_AS", "DIFFERENT_FROM"}:
        ref = assertion.expected_ref
        other = _select(ref.target, ref.selector, captures)
        if len(other) != 1:
            raise CaptureError("REFERENCE_CARDINALITY_INVALID")
        equal = _equal(actual, _pointer(other[0], ref.field))
        return equal if op == "SAME_AS" else not equal
    if op in {"INCLUDES", "EXCLUDES"}:
        if not isinstance(actual, list):
            raise CaptureError("ARRAY_REQUIRED")
        included = any(_equal(item, assertion.expected) for item in actual)
        return included if op == "INCLUDES" else not included
    equal = _equal(actual, assertion.expected)
    return equal if op == "EQUALS" else not equal


def evaluate_assertions(expected: ExpectedResults, captures: tuple[CapturedStep, ...] | None) -> EvaluationReport:
    """Evaluate a snapshotted oracle against independently captured component data."""
    expected = ExpectedResults.model_validate_json(expected.model_dump_json(exclude_unset=True))
    observations = {} if captures is None else {c.request_step: c for c in captures}
    invalid = captures is not None and (not captures or len(observations) != len(captures))
    if invalid:
        observations = {}
    results = []
    for assertion in expected.assertions:
        if assertion.test_status == "DISABLED":
            outcome, reason = "NOT_RUN", assertion.blocking_reason
        elif assertion.test_status != "ACTIVE":
            outcome, reason = "BLOCKED", assertion.blocking_reason
        elif captures is None:
            outcome, reason = "BLOCKED", "EXECUTION_UNAVAILABLE"
        else:
            try:
                passed = _test(assertion, observations)
                outcome, reason = ("PASS", "MATCH") if passed else ("FAIL", "ASSERTION_MISMATCH")
            except CaptureError as error:
                outcome, reason = "FAIL", str(error)
            except Exception:
                outcome, reason = "FAIL", "EVALUATOR_ERROR"
        results.append(AssertionResult(assertion.assertion_id, tuple(assertion.requirement_ids), assertion.mandatory, outcome, reason))
    mandatory = [r.outcome for r in results if r.mandatory]
    category = "ASSERTIONS_EVALUATED"
    if invalid or any(c.application_failed for c in observations.values()):
        outcome, category = "FAIL", "CAPTURE_INVALID" if invalid else "APPLICATION_FAILURE"
    elif "FAIL" in mandatory:
        outcome = "FAIL"
    elif "BLOCKED" in mandatory:
        outcome = "BLOCKED"
    elif not mandatory or all(value == "NOT_RUN" for value in mandatory):
        outcome = "NOT_RUN"
    elif any(value != "PASS" for value in mandatory):
        outcome = "NOT_RUN"
    else:
        outcome = "PASS"
    if any(r.reason == "EVALUATOR_ERROR" for r in results):
        outcome, category = "FAIL", "EVALUATOR_ERROR"
    return EvaluationReport(expected.scenario_id, "COMPONENT", outcome, category, tuple(results),
        {value: sum(r.outcome == value for r in results) for value in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")},
        trace_digests=tuple(sorted((c.request_step, c.trace_digest) for c in observations.values())))


def _evaluate_scenario(root, scenario_id, *, captures=None) -> EvaluationReport:
    """Preflight and report scenario readiness; never dispatch an authored stub as ReAct."""
    from dataclasses import replace
    try:
        loaded = load_scenario(root, scenario_id)
    except FixtureLoadError:
        return EvaluationReport(scenario_id, "SCENARIO", "FAIL", "FIXTURE_INVALID", (), {k: 0 for k in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")})
    return evaluate_loaded(loaded, captures=captures)


def evaluate_loaded(loaded, *, captures=None) -> EvaluationReport:
    """Evaluate the preflight snapshot; never reopen expected artifacts after dispatch."""
    from dataclasses import replace
    scenario_id = loaded.definition.scenario_id
    expected = loaded.evaluator.expected_results
    status = loaded.definition.test_status
    if status != "ACTIVE":
        rows = tuple(AssertionResult(a.assertion_id, tuple(a.requirement_ids), a.mandatory,
                     "NOT_RUN" if status == "DISABLED" or a.test_status == "DISABLED" else "BLOCKED", "SCENARIO_" + status) for a in expected.assertions)
        report = EvaluationReport(scenario_id, "SCENARIO", "NOT_RUN" if status == "DISABLED" else "BLOCKED",
                                  "SCENARIO_" + status, rows, {k: sum(r.outcome == k for r in rows) for k in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")})
    else:
        report = replace(evaluate_assertions(expected, captures), scope="SCENARIO")
        if captures:
            application, driver = loaded.application, loaded.driver
            inputs = _digest([application.catalog.model_dump(mode="json"), application.policy_configuration.model_dump(mode="json")])
            drivers = _digest(driver.model_dump(mode="json", exclude_unset=True))
            states = [c.records["investigation_state"][0] for c in captures]
            if (any(c.input_digest != inputs or c.driver_digest != drivers or c.request_step > len(driver.script.requests)
                    or c.request_digest != _digest(driver.script.requests[c.request_step - 1].user_request) for c in captures)
                    or len({s["session_id"] for s in states}) != 1
                    or len({c.execution_mode for c in captures}) != 1
                    or len({s["investigation_id"] for s in states}) != len(states)
                    or any(s["request_revision"] != c.request_step for s, c in zip(states, captures))):
                report = replace(report, outcome="FAIL", category="CAPTURE_CONTEXT_MISMATCH")
        if report.outcome != "FAIL":
            modes = {c.execution_mode for c in captures} if captures else set()
            if modes and modes <= GENUINE_MODEL_MODES:
                pass  # Genuine model-driven captures: assertion aggregation stands.
            else:
                category = ("AGENT_EXECUTION_NOT_RUN" if not modes else
                            "AUTHORED_COMPONENT_SCOPE" if "AUTHORED_COMPONENT" in modes else "OFFLINE_MODEL_TRANSPORT")
                report = replace(report, outcome="BLOCKED" if report.outcome != "NOT_RUN" else "NOT_RUN",
                                 category=category)
    return replace(report, artifact_digests=tuple(sorted(loaded.evaluator.artifact_digests.items())))


def evaluate_scenario(root, scenario_id, *, captures: tuple[CapturedStep, ...] | None = None) -> EvaluationReport:
    """Report fixture errors, unavailable execution and evaluator faults separately."""
    try:
        return _evaluate_scenario(root, scenario_id, captures=captures)
    except Exception:
        return EvaluationReport(scenario_id, "SCENARIO", "FAIL", "EVALUATOR_ERROR", (),
                                {k: 0 for k in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")})
