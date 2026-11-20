"""Read actual JSONL events and independently check correlation/completeness.

No expected scenario events are replayed or used to fill a missing record. Partial
files are never repaired; a valid nonterminal prefix has complete=False.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from hawaii_activity_forecaster.config.settings import InvestigationLimits
from hawaii_activity_forecaster.models import InvestigationTrace, TraceEvent
from hawaii_activity_forecaster.models.permissions import OCEAN_SOURCES, WEATHER_SOURCES
from hawaii_activity_forecaster.harness.policy import CATEGORY_SOURCES
from .privacy import sanitize_event
from .storage import TERMINAL
from .model_validation import ModelTraceLedger, MODEL, PROFILE_METADATA, TRACE_MODES


class TraceValidationError(ValueError):
    """A static diagnostic code only; never echo rejected JSON or local paths."""


@dataclass(frozen=True)
class TraceMetrics:
    duration_ms: int
    iterations: int
    specialist_requests: int
    tool_calls: int
    model_calls: int
    retries: int
    fallbacks: int
    evidence_accepted: int
    evidence_limited: int
    evidence_rejected: int
    candidates_considered: int
    candidates_investigated: int
    eligible_candidates: int
    excluded_candidates: int
    unresolved_candidates: int
    outcome: str | None


@dataclass(frozen=True)
class TraceValidation:
    trace_id: str
    event_count: int
    digest: str
    complete: bool
    metrics: TraceMetrics


def _require(condition, code):
    if not condition:
        raise TraceValidationError(code)


def _decode(payload: bytes) -> InvestigationTrace:
    try:
        _require(bool(payload) and payload.endswith(b"\n"), "TRACE_EMPTY_OR_TRUNCATED")
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("Duplicate JSON key")
                value[key] = item
            return value
        def invalid_constant(value):
            raise ValueError("Nonfinite JSON number")
        events = [TraceEvent.model_validate(json.loads(line.decode("utf-8"), object_pairs_hook=unique,
                                                       parse_constant=invalid_constant))
                  for line in payload.split(b"\n")[:-1]]
        first, last = events[0], events[-1]
        metadata = first.details["trace_metadata"]
        _require(set(metadata) == {"schema_version", "configuration_version", "policy_version", "model_identifier"},
                 "TRACE_METADATA_INVALID")
        return InvestigationTrace(
            trace_id=first.trace_id, investigation_id=first.details["investigation_id"],
            started_at=first.timestamp, completed_at=last.timestamp if last.event_type in TERMINAL else None,
            final_status=TERMINAL.get(last.event_type), events=events, **metadata,
        )
    except TraceValidationError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, IndexError):
        raise TraceValidationError("TRACE_FORMAT_INVALID") from None


def read_trace(path: str | Path) -> InvestigationTrace:
    """Read the logical schema from a pure event JSONL file and its start metadata."""
    try:
        trace = _decode(Path(path).read_bytes())
        validate_trace(trace)
        return trace
    except OSError:
        raise TraceValidationError("TRACE_UNREADABLE") from None


def validate_trace(trace: InvestigationTrace, *, state=None, result=None, budgets=None,
                   bindings=(), evidence=None, safety=None) -> TraceMetrics:
    """Verify actual event relationships and, when supplied, current runtime truth.

    End-state checks add completeness requirements for normal successful outcomes.
    An actual FAILED terminal may legitimately have no result or normalization.
    """
    try:
        return _validate(trace, state, result, budgets, bindings, evidence, safety)
    except TraceValidationError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, IndexError):
        raise TraceValidationError("TRACE_EVENT_DETAILS_INVALID") from None


def _validate(trace, state, result, budgets, bindings, evidence, safety):
    trace = InvestigationTrace.model_validate(trace.model_dump())
    events = trace.events
    _require(bool(events) and events[0].event_type == "INVESTIGATION_STARTED", "TRACE_START_MISSING")
    first, last = events[0], events[-1]
    session, revision = first.details["session_id"], first.request_revision
    _require(first.details["trace_metadata"] == dict(schema_version=trace.schema_version,
             configuration_version=trace.configuration_version, policy_version=trace.policy_version,
             model_identifier=trace.model_identifier), "TRACE_METADATA_MISMATCH")
    _require(trace.schema_version == trace.configuration_version == "0.1"
             and trace.policy_version in {"0.2", "not-applied"} and trace.model_identifier in {None, MODEL},
             "TRACE_VERSION_UNSUPPORTED")
    model_profile = first.details["configuration"].get("model_profile")
    if trace.model_identifier is not None:
        _require(isinstance(model_profile, dict)
                 and set(model_profile) == set(PROFILE_METADATA)
                 and model_profile["execution_mode"] in TRACE_MODES
                 and model_profile == {**PROFILE_METADATA, "execution_mode": model_profile["execution_mode"]},
                 "TRACE_MODEL_CONFIGURATION_INVALID")
    _require(first.details["configuration"]["limits"] == InvestigationLimits().model_dump(), "TRACE_CONFIGURATION_INVALID")
    assessment_scope = set(first.details["candidate_beach_ids"])
    investigation_scope = assessment_scope.copy()
    agents, agent_done, tools, tool_done, models, model_done = {}, set(), {}, {}, {}, set()
    provider_models = ModelTraceLedger(_require)
    observed_findings, merged_findings, finding_sources = set(), set(), {}
    evidence_decisions, policies, assessments, validations = {}, {}, {}, {}
    retries, fallbacks, limits_seen = set(), set(), set()
    fallback_gaps = {}
    normalized = received = False
    response_contracts = set()
    terminal = None
    for sequence, event in enumerate(events, 1):
        d, kind = event.details, event.event_type
        _require(event.sequence_number == sequence, "TRACE_SEQUENCE_GAP")
        _require(event.timestamp >= trace.started_at, "TRACE_EVENT_TIME_INVALID")
        _require((event.trace_id, d.get("investigation_id"), d.get("session_id"), event.request_revision) ==
                 (trace.trace_id, trace.investigation_id, session, revision), "TRACE_IDENTITY_MISMATCH")
        _require(event == sanitize_event(event), "TRACE_PRIVACY_PROJECTION_INVALID")
        _require(terminal is None, "TRACE_EVENT_AFTER_TERMINAL")
        if kind == "INVESTIGATION_STARTED":
            _require(sequence == 1 and d["status"] == "INITIALIZING", "TRACE_START_INVALID")
            _require(all(d[name] == 0 for name in ("iteration_count", "tool_call_count", "model_call_count", "retry_count")),
                     "TRACE_INITIAL_COUNTERS_INVALID")
        elif kind == "REQUEST_RECEIVED":
            _require(not received, "TRACE_DUPLICATE_REQUEST")
            received = True
        elif kind == "REQUEST_NORMALIZED":
            _require(received and not normalized, "TRACE_DUPLICATE_OR_UNADMITTED_NORMALIZATION")
            normalized = True
        elif kind == "AGENT_STARTED":
            key = d["request_id"], d["attempt_number"]
            _require(key not in agents and d["agent_type"] in {"WEATHER", "OCEAN"}, "TRACE_SPECIALIST_START_INVALID")
            _require(normalized, "TRACE_DISPATCH_BEFORE_NORMALIZATION")
            _require(event.actor == d["agent_type"] and bool(d["candidate_beach_ids"])
                     and set(d["candidate_beach_ids"]) <= investigation_scope, "TRACE_SPECIALIST_SCOPE_INVALID")
            agents[key] = d
        elif kind in {"AGENT_COMPLETED", "AGENT_FAILED"}:
            key = d["request_id"], d["attempt_number"]
            _require(key in agents and key not in agent_done, "TRACE_SPECIALIST_OUTCOME_UNCORRELATED")
            _require(event.actor == d["agent_type"] == agents[key]["agent_type"], "TRACE_SPECIALIST_ROLE_MISMATCH")
            agent_done.add(key)
        elif kind == "TOOL_CALLED":
            call, key = d["tool_call_id"], (d["request_id"], d["specialist_attempt"])
            _require(call not in tools and key in agents and key not in agent_done, "TRACE_TOOL_START_UNCORRELATED")
            parent = agents[key]
            sources = WEATHER_SOURCES if d["agent_type"] == "WEATHER" else OCEAN_SOURCES
            _require(event.actor == d["agent_type"] == parent["agent_type"] and d["source_id"] in sources
                     and d["tool_name"] == d["source_id"]
                     and all(d["source_id"] in CATEGORY_SOURCES.get(c, set()) for c in d["requested_evidence"])
                     and set(d["candidate_beach_ids"]) <= set(parent["candidate_beach_ids"])
                     and set(d["requested_evidence"]) <= {r["evidence_type"] for r in parent["requested_evidence"]}
                     and d["target_time_window"] == parent["target_time_window"], "TRACE_TOOL_SCOPE_INVALID")
            tools[call] = d
        elif kind in {"TOOL_COMPLETED", "TOOL_FAILED"}:
            call = d["tool_call_id"]
            _require(call in tools and call not in tool_done, "TRACE_TOOL_OUTCOME_UNCORRELATED")
            _require(all(d[name] == tools[call][name] for name in (
                "request_id", "specialist_attempt", "agent_type", "source_id", "tool_name",
                "candidate_beach_ids", "requested_evidence", "target_time_window")), "TRACE_TOOL_CORRELATION_INVALID")
            _require(d["duration_ms"] >= 0 and d["execution_status"] in {"SUCCESS", "PARTIAL", "ERROR", "TIMEOUT"},
                     "TRACE_TOOL_OUTCOME_INVALID")
            tool_done[call] = d
            _require(not set(d["result_reference_ids"]) & observed_findings, "TRACE_FINDING_ID_REUSED")
            observed_findings.update(d["result_reference_ids"])
            finding_sources.update({fid: d["source_id"] for fid in d["result_reference_ids"]})
        elif kind in {"RETRY_INITIATED", "FALLBACK_INITIATED"}:
            call, original = d["tool_call_id"], d["original_tool_call_id"]
            _require(original in tool_done and tool_done[original]["execution_status"] in {"ERROR", "TIMEOUT", "PARTIAL"},
                     "TRACE_RECOVERY_WITHOUT_FAILURE")
            target = retries if kind == "RETRY_INITIATED" else fallbacks
            _require(call not in target, "TRACE_DUPLICATE_RECOVERY")
            target.add(call)
            if kind == "FALLBACK_INITIATED":
                fallback_gaps.setdefault(d["gap_id"], []).append(call)
        elif kind == "EVIDENCE_RECEIVED":
            _require(set(d["finding_ids"]) <= observed_findings, "TRACE_FINDING_NOT_OBSERVED")
            merged_findings.update(d["finding_ids"])
        elif kind in {"EVIDENCE_VALIDATED", "EVIDENCE_REJECTED"}:
            _require(d["finding_id"] in merged_findings, "TRACE_VALIDATION_FINDING_INVALID")
            _require(d["source_id"] == finding_sources[d["finding_id"]], "TRACE_FINDING_SOURCE_MISMATCH")
            _require(d["validation_status"] in {"ACCEPTED", "LIMITED", "REJECTED"}
                     and d["valid"] == (d["validation_status"] != "REJECTED")
                     and (kind == "EVIDENCE_REJECTED") == (d["validation_status"] == "REJECTED"), "TRACE_EVIDENCE_STATUS_INVALID")
            _require(d["validation_rule_ids"] == ([d["rule_id"]] if d["rule_id"] else [])
                     and d["validation_reasons"] == d["reasons"] and bool(d["source_id"]), "TRACE_EVIDENCE_ATTRIBUTION_MISSING")
            evidence_decisions[d["finding_id"], d.get("rule_id"), d.get("beach_id"), d.get("category")] = d
        elif kind == "POLICY_EVALUATED":
            _require(set(d["supporting_finding_ids"]) <= merged_findings
                     and d["result"] in {"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"}
                     and bool(d["explanation"]), "TRACE_POLICY_BASIS_INVALID")
            policies[d["assessment_id"], d["policy_id"]] = d
        elif kind == "CANDIDATE_ASSESSED":
            _require(d["beach_id"] in assessment_scope
                     and all((d["assessment_id"], policy) in policies for policy in d["applied_policy_ids"])
                     and bool(d["decision_reasons"]), "TRACE_ASSESSMENT_POLICY_MISSING")
            _require(all(policies[d["assessment_id"], policy]["beach_id"] == d["beach_id"]
                         for policy in d["applied_policy_ids"]), "TRACE_POLICY_CANDIDATE_MISMATCH")
            if d["eligibility"] == "ELIGIBLE":
                _require(d["evidence_quality"] == "SUFFICIENT" and not d["disqualifying_policy_ids"]
                         and not d["unresolved_policy_ids"] and all(policies[d["assessment_id"], policy]["result"]
                         in {"PASS", "NOT_APPLICABLE"} for policy in d["applied_policy_ids"]), "TRACE_ELIGIBILITY_POLICY_MISMATCH")
            assessments[d["assessment_id"]] = d
        elif kind in {"CANDIDATE_EXCLUDED", "CANDIDATE_ELIGIBLE"}:
            assessment = assessments.get(d["assessment_id"])
            expected = "EXCLUDED" if kind == "CANDIDATE_EXCLUDED" else "ELIGIBLE"
            _require(assessment is not None and assessment["beach_id"] == d["beach_id"]
                     and assessment["eligibility"] == expected, "TRACE_CANDIDATE_TRANSITION_INVALID")
            if expected == "EXCLUDED":
                _require(d["disqualifying_policy_ids"] == assessment["disqualifying_policy_ids"], "TRACE_EXCLUSION_BASIS_INVALID")
                _require(all(policies[d["assessment_id"], policy]["result"] == "FAIL"
                             for policy in d["disqualifying_policy_ids"]), "TRACE_EXCLUSION_POLICY_MISMATCH")
        elif kind == "RESULT_VALIDATED":
            _require(type(d["valid"]) is bool, "TRACE_RESULT_VALIDATION_OUTCOME_MISSING")
            if d["valid"]:
                _require(set(d["assessment_ids"]) <= set(assessments), "TRACE_RESULT_ASSESSMENT_INVALID")
                validations[d["result_id"]] = d
        elif kind == "INVESTIGATION_LIMIT_REACHED":
            if d["budget_kind"] == "fallback_per_evidence_gap":
                calls = fallback_gaps.get(d["gap_id"], [])
                _require(d["configured_limit"] == InvestigationLimits().max_fallback_attempts_per_evidence_gap
                         and len(calls) == d["configured_limit"]
                         and all(call in tool_done and tool_done[call]["execution_status"] in {"ERROR", "TIMEOUT", "PARTIAL"}
                                 and d["category"] in tools[call]["requested_evidence"]
                                 and d["candidate_beach_ids"] == tools[call]["candidate_beach_ids"]
                                 for call in calls), "TRACE_RECOVERY_LIMIT_UNGROUNDED")
            limits_seen.add(d["budget_kind"])
        elif kind == "CONTRACT_VALIDATED" and d.get("contract") == "candidate_selection" and d["valid"]:
            _require(not agents, "TRACE_SELECTION_AFTER_DISPATCH")
            assessment_scope = set(d["assessment_candidate_ids"])
            investigation_scope = set(d["investigation_candidate_ids"])
            _require(investigation_scope <= assessment_scope
                     and set(d["planning_order"]) == investigation_scope, "TRACE_SELECTION_SCOPE_INVALID")
        elif kind == "CONTRACT_VALIDATED" and d.get("contract") == "specialist_response":
            response_contracts.add((d["request_id"], d["attempt_number"]))
        elif kind == "CONTRACT_VALIDATED" and d.get("contract") == "synthetic_model_dispatch":
            call = d["call_id"]
            _require(d["synthetic_adapter"] is True, "TRACE_MODEL_ADAPTER_UNIDENTIFIED")
            if d["phase"] == "AUTHORIZED":
                _require(call not in models and call not in provider_models.authorized, "TRACE_MODEL_CALL_DUPLICATED")
                models[call] = d
            else:
                _require(call in models and call not in model_done and d["phase"] in {"RETURNED", "FAILED"},
                         "TRACE_MODEL_OUTCOME_UNCORRELATED")
                model_done.add(call)
        elif kind == "CONTRACT_VALIDATED" and d.get("contract") == "model_dispatch":
            provider_models.observe(d, metadata=trace.model_identifier, profile=model_profile, received=received,
                                    normalized=normalized, legacy_calls=models)
        elif kind in TERMINAL:
            terminal = event
    complete = terminal is not None
    model_count = len(models) + len(provider_models.dispatched)
    if complete:
        provider_models.finish()
        d = terminal.details
        expected_outcome = {"COMPLETED": "RECOMMENDATIONS", "ABSTAINED": "NO_RECOMMENDATION", "FAILED": "ERROR"}[trace.final_status]
        _require(d["final_status"] == trace.final_status and d["outcome"] == expected_outcome
                 and bool(d["completion_reason"]), "TRACE_TERMINAL_OUTCOME_INVALID")
        _require(set(tools) == set(tool_done) and set(agents) == agent_done and set(models) == model_done,
                 "TRACE_UNFINISHED_OPERATIONS")
        _require(set(agents) <= response_contracts, "TRACE_SPECIALIST_CONTRACT_MISSING")
        _require(retries | fallbacks <= set(tools), "TRACE_RECOVERY_CALL_MISSING")
        _require((d["total_tool_calls"], d["total_model_calls"], d["total_retries"], d["total_fallbacks"]) ==
                 (len(tools), model_count, len(retries), len(fallbacks)), "TRACE_FINAL_COUNTERS_INVALID")
        limits = InvestigationLimits()
        _require(0 <= d["total_iterations"] <= limits.max_coordinator_iterations
                 and len(tools) <= limits.max_environmental_tool_invocations and model_count <= limits.max_llm_invocations,
                 "TRACE_BUDGET_EXCEEDED")
        if trace.final_status != "FAILED":
            _require(normalized and d["result_id"] in validations, "TRACE_FINAL_RESULT_NOT_VALIDATED")
            _require({a["beach_id"] for a in assessments.values()} == assessment_scope,
                     "TRACE_CANDIDATE_ASSESSMENT_MISSING")
        if d.get("result_id") in validations:
            _require(validations[d["result_id"]]["outcome"] == expected_outcome, "TRACE_RESULT_OUTCOME_MISMATCH")
            chosen = [assessments[key] for key in validations[d["result_id"]]["assessment_ids"]]
            _require([a["beach_id"] for a in chosen] == d["recommended_beach_ids"]
                     and all(a["eligibility"] == "ELIGIBLE" and a["evidence_quality"] == "SUFFICIENT"
                             and a["environmental_suitability"] in {"FAVORABLE", "MIXED"} for a in chosen),
                     "TRACE_RESULT_ELIGIBILITY_INVALID")
        _require(d["recommendation_count"] == len(d["recommended_beach_ids"]), "TRACE_RECOMMENDATION_COUNT_INVALID")
        _require((expected_outcome == "RECOMMENDATIONS") == bool(d["recommended_beach_ids"])
                 and len(d["recommended_beach_ids"]) <= limits.max_recommendations, "TRACE_RESULT_CARDINALITY_INVALID")
        if d.get("stop_reason") == "ITERATION_LIMIT_REACHED":
            _require("coordinator_iterations" in limits_seen, "TRACE_ITERATION_LIMIT_EVENT_MISSING")
    if state is not None:
        _require((state.investigation_id, state.session_id, state.request_revision) ==
                 (trace.investigation_id, session, revision), "TRACE_STATE_IDENTITY_MISMATCH")
        _require(state.created_at <= first.timestamp <= state.updated_at and last.timestamp <= state.updated_at,
                 "TRACE_STATE_TIME_MISMATCH")
        _require(set(state.candidate_beach_ids) == assessment_scope and state.schema_version == trace.schema_version,
                 "TRACE_STATE_SCOPE_MISMATCH")
        if complete:
            _require((state.status, state.outcome, state.result_id, state.completion_reason) ==
                     (trace.final_status, last.details["outcome"], last.details.get("result_id"), last.details["completion_reason"]),
                     "TRACE_STATE_TERMINAL_MISMATCH")
            _require((state.iteration_count, state.tool_call_count, state.retry_count) ==
                     (last.details["total_iterations"], len(tools), len(retries)), "TRACE_STATE_COUNTERS_MISMATCH")
        else:
            _require(state.status == "AWAITING_CLARIFICATION" and last.event_type == "CLARIFICATION_REQUESTED"
                     and not tools and not agents and result is None, "TRACE_STATE_TERMINAL_MISSING")
        if state.status in {"COMPLETED", "ABSTAINED"}:
            for assessment in state.assessments:
                recorded = assessments.get(assessment.assessment_id)
                _require(recorded is not None and all(recorded[name] == getattr(assessment, name) for name in (
                    "beach_id", "activity", "eligibility", "evidence_quality", "environmental_suitability", "assessment_version",
                    "decision_reasons", "disqualifying_policy_ids")), "TRACE_CURRENT_ASSESSMENT_MISSING")
                for policy in assessment.policy_results:
                    recorded_policy = policies.get((assessment.assessment_id, policy.policy_id))
                    _require(recorded_policy is not None and recorded_policy["result"] == policy.result
                             and recorded_policy["supporting_finding_ids"] == policy.supporting_finding_ids,
                             "TRACE_CURRENT_POLICY_MISSING")
            if evidence is not None:
                for decision in evidence.decisions:
                    key = decision.finding_id, decision.rule_id, decision.beach_id, decision.category
                    _require(key in evidence_decisions and evidence_decisions[key]["validation_status"] == decision.status
                             and evidence_decisions[key]["reasons"] == list(decision.reasons), "TRACE_CURRENT_EVIDENCE_MISSING")
    if budgets is not None:
        _require(budgets.closed and not budgets.active_specialists and not budgets.reserved_tool_calls
                 and not budgets.reserved_model_calls, "TRACE_BUDGET_NOT_CLOSED")
        _require((budgets.tool_calls, budgets.model_calls, budgets.retries, budgets.fallbacks) ==
                 (len(tools), model_count, len(retries), len(fallbacks)), "TRACE_RUNTIME_COUNTERS_MISMATCH")
    if bindings:
        _require({b.runtime_tool_call_id for b in bindings} == set(tools), "TRACE_TOOL_BINDING_MISMATCH")
        for binding in bindings:
            _require({f.runtime_finding_id for f in binding.findings} ==
                     set(tool_done[binding.runtime_tool_call_id]["result_reference_ids"]), "TRACE_FINDING_BINDING_MISMATCH")
    if result is not None:
        _require(complete and (result.result_id, result.outcome, result.investigation_id, result.request_revision) ==
                 (last.details["result_id"], last.details["outcome"], trace.investigation_id, revision), "TRACE_RESULT_IDENTITY_MISMATCH")
        _require([r.beach_id for r in result.recommendations] == last.details["recommended_beach_ids"]
                 and result.result_id in validations, "TRACE_RESULT_SELECTION_MISMATCH")
    latest = {a["beach_id"]: a for a in assessments.values()}
    eligible = sum(a["eligibility"] == "ELIGIBLE" for a in latest.values())
    excluded = sum(a["eligibility"] == "EXCLUDED" for a in latest.values())
    unresolved = sum(a["eligibility"] == "NEEDS_INVESTIGATION" for a in latest.values())
    per_finding = {}
    priority = {"ACCEPTED": 0, "LIMITED": 1, "REJECTED": 2}
    for decision in evidence_decisions.values():
        fid, status = decision["finding_id"], decision["validation_status"]
        if priority[status] >= priority.get(per_finding.get(fid), -1):
            per_finding[fid] = status
    statuses = list(per_finding.values())
    duration = int(((trace.completed_at or last.timestamp) - trace.started_at).total_seconds() * 1000)
    iterations = last.details["total_iterations"] if complete else max(e.details["iteration_count"] for e in events)
    investigated = {key for call in tools.values() for key in call["candidate_beach_ids"]}
    return TraceMetrics(duration, iterations, len(agents), len(tools), model_count, len(retries), len(fallbacks),
                        statuses.count("ACCEPTED"), statuses.count("LIMITED"), statuses.count("REJECTED"),
                        len(assessment_scope), len(investigated), eligible, excluded, unresolved,
                        last.details.get("outcome") if complete else None)


def inspect_trace(path: str | Path, **context) -> TraceValidation:
    """Validate exactly the bytes read; this receipt binds later presentation checks."""
    try:
        payload = Path(path).read_bytes()
    except OSError:
        raise TraceValidationError("TRACE_UNREADABLE") from None
    trace = _decode(payload)
    metrics = validate_trace(trace, **context)
    return TraceValidation(trace.trace_id, len(trace.events), sha256(payload).hexdigest(),
                           trace.final_status is not None, metrics)
