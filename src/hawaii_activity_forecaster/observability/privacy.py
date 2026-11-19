"""Small structured trace projections; raw requests/responses are never retained.

Producers must supply controlled identifiers, rule outcomes and validator summaries,
not arbitrary source/model prose. This is not a general-purpose PII classifier.
"""

import re
from urllib.parse import urlsplit, urlunsplit

from hawaii_activity_forecaster.models import TraceEvent

# Explicitly reviewed structured details. Unknown fields are omitted, including
# raw text, opaque constraint payloads, SDK messages, prompts and model reasoning.
_FIELDS = frozenset("""
investigation_id session_id request_revision model_call_count tool_call_count iteration_count retry_count
fallback_count fallback_attempted active_specialists reserved_tool_calls reserved_model_calls
component_probe status trace_metadata schema_version configuration_version policy_version
model_identifier configuration limits timeouts environment_mode remote_tracing_enabled policy_configuration_version
max_coordinator_iterations max_environmental_tool_invocations max_retries_per_failed_invocation
max_fallback_attempts_per_evidence_gap max_concurrent_specialists max_recommendations
max_llm_invocations llm_request_seconds synthetic_tool_seconds
reference_time rule_profile previous_investigation_id previous_request_revision prior_status
changed_fields user_provided_fields assumed_fields context_digest origins field entry_index source
span assumed default_rule inherited_from limitation_count question_count
contract valid reason request_id request_ids response_id response_ids attempt_number
response_correlation agent_type iteration issued_at deadline_at target_time_window start end
candidate_beach_ids investigation_candidate_ids assessment_candidate_ids planning_order
request_digest decisions beach_id reasons sources source_id publisher url accessed_at
supports_fields last_verified invalidated_assessment_ids requested_evidence requirement_id
evidence_type priority finding_ids supporting_finding_ids missing_evidence_count error_codes
retrieval_status execution_status tool_call_id tool_name specialist_attempt operation_id
operation_attempt original_tool_call_id gap_id duration_ms elapsed_ms virtual_completed_at
delivery_count result_reference_ids source_fixture_id simulated_duration_ms arguments_summary geographic_scope zone
finding_id rule_id category validation_status validation_rule_ids validation_reasons
coverage_type coverage_id observed_at retrieved_at valid_from valid_until
assessment_id assessment_ids assessment_version policy_id result explanation
eligibility environmental_suitability evidence_quality activity applied_policy_ids
decision_reasons disqualifying_policy_ids unresolved_policy_ids recommended_next_actions
result_id outcome stop_reason error_code final_status recommended_beach_ids
recommendation_count completion_reason no_recommendation_reason total_iterations
total_tool_calls total_retries total_fallbacks total_model_calls total_duration_ms
budget_kind configured_limit synthetic_adapter operation call_id phase
normalized_request_summary target_date preferred_area_specified experience_level
hard_constraint_count soft_preference_count location_restrictions kind scope value
raw_request_retained raw_payloads_retained
""".split())
_SENSITIVE = re.compile(r"(?i)(chain.?of.?thought|reasoning|credential|password|secret|authorization|api.?key|access.?token|prompt|raw.?response|headers)")
_TOKEN = re.compile(r"(?i)\b(?:bearer\s+\S+|(?:api[_ -]?key|password|token|secret)\s*[:=]\s*\S+|sk-[a-z0-9_-]{8,})")
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")


def _clean(value):
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()
                if key in _FIELDS and not _SENSITIVE.search(key)}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, str):
        if value.startswith(("https://", "http://")):
            parsed = urlsplit(value)
            # Attribution keeps scheme/host/path; credentials, query and fragment
            # are unnecessary in the authoritative event stream.
            value = urlunsplit((parsed.scheme, parsed.netloc.rsplit("@", 1)[-1], parsed.path, "", ""))
        return _EMAIL.sub("[REDACTED]", _TOKEN.sub("[REDACTED]", value))
    return value


def sanitize_event(event: TraceEvent) -> TraceEvent:
    """Detach an event and retain only small approved structured diagnostics."""
    data = TraceEvent.model_validate(event.model_dump()).model_dump(mode="json")
    original = data["details"]
    details = _clean(original)
    if "original_request" in original:
        details["raw_request_retained"] = False
    if "questions" in original:
        details["question_count"] = len(original["questions"])
    if "limitations" in original:
        details["limitation_count"] = len(original["limitations"])
    if "normalized_request" in original:
        request = original["normalized_request"]
        names = ("activity", "target_date", "target_time_window", "experience_level")
        summary = {name: request.get(name) for name in names}
        summary.update(
            hard_constraint_count=len(request.get("hard_constraints", [])),
            soft_preference_count=len(request.get("soft_preferences", [])),
            preferred_area_specified=request.get("preferred_area") is not None,
            location_restrictions=[{"kind": "LOCATION_RESTRICTION", "scope": item["scope"], "entry_index": index}
                                   for index, item in enumerate(request.get("hard_constraints", []))
                                   if set(item) == {"kind", "scope", "value"} and item["kind"] == "LOCATION_RESTRICTION"
                                   and isinstance(item["scope"], str) and item["scope"] in {"REGION", "LOCALITY", "BEACH"}],
        )
        details["normalized_request_summary"] = _clean(summary)
        details["raw_request_retained"] = False
    data["details"] = details
    return TraceEvent.model_validate(data)
