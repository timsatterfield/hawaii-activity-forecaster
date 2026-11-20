"""Closed, sanitized failure categories for specialist and request-interpretation failures.

Observability §§7.2/10.4 call for a structured, sanitized error category. Only the
fixed codes below are ever emitted: never exception messages, model text, option
identifiers, spans or payloads. Classification uses exception types plus the fixed
messages raised by trusted validators; anything unrecognized is ``UNCLASSIFIED``.
"""

from hawaii_activity_forecaster.model_runtime.errors import ERROR_CODES

# Fixed ToolPlanError messages raised by the trusted runtime and dispatcher.
TOOL_PLAN_CODES = {
    "Duplicate configured tool option": "PLAN_OPTION_DUPLICATE",
    "Recovery cannot be relabeled as a new original": "PLAN_RECOVERY_CONDITION_INVALID",
    "Recovery does not reference its configured original": "PLAN_RECOVERY_ORIGIN_MISMATCH",
    "A query cannot be a second original": "PLAN_DUPLICATE_ORIGINAL",
    "Recovery must reference an earlier action": "PLAN_RECOVERY_ORDER_INVALID",
    "Retry changes scope or retries a retry": "PLAN_RETRY_INVALID",
    "Fallback must address one required gap through another permitted source": "PLAN_FALLBACK_INVALID",
    "Action IDs cannot be reused": "PLAN_ACTION_ID_REUSED",
    "Tool action exceeds delegated scope": "PLAN_SCOPE_EXCEEDED",
    "Delegation exceeds the selected investigation scope": "DELEGATION_SCOPE_EXCEEDED",
    "Specialist delegation expired": "DELEGATION_EXPIRED",
    "Tool plan already registered": "TOOL_EXECUTION_STATE_INVALID",
    "Unregistered or repeated specialist tool execution": "TOOL_EXECUTION_STATE_INVALID",
    "Inactive tool execution": "TOOL_EXECUTION_STATE_INVALID",
    "Tool execution is closed": "TOOL_EXECUTION_STATE_INVALID",
}

# Fixed RequestValidationError messages raised by request validation/verification.
REQUEST_CODES = {
    "Source span is outside the utterance.": "REQUEST_SPAN_OUT_OF_RANGE",
    "Source span does not support this field.": "REQUEST_SPAN_FIELD_MISMATCH",
    "A changed value lacks its relevant source span.": "REQUEST_SPAN_MISSING",
    "Duplicate source spans": "REQUEST_SPAN_DUPLICATE",
    "Proposed change is not supported by its clause.": "REQUEST_CHANGE_UNSUPPORTED",
    "Proposal omitted a supported change.": "REQUEST_CHANGE_OMITTED",
    "Removal is not supported by the current utterance.": "REQUEST_REMOVAL_UNSUPPORTED",
    "Proposed location is not in the catalog.": "REQUEST_LOCATION_UNKNOWN",
    "Proposed area is not uniquely resolved.": "REQUEST_AREA_AMBIGUOUS",
    "Daypart requires explicit hours.": "REQUEST_DAYPART_HOURS_REQUIRED",
    "Request proposal or its supporting context could not be validated.": "REQUEST_PROPOSAL_INVALID",
    "Synthetic interpreter did not return a proposal.": "REQUEST_PROPOSAL_MISSING",
    "Invalid request descriptor.": "REQUEST_DESCRIPTOR_INVALID",
    "Unsupported request-rule profile.": "REQUEST_RULE_PROFILE_UNSUPPORTED",
    "Invalid request-validation context.": "REQUEST_CONTEXT_INVALID",
    "Request receipt is stale or inconsistent.": "REQUEST_CONTEXT_INVALID",
    "Candidate selection requires an unambiguous validated request.": "REQUEST_SELECTION_INVALID",
    "Candidate selection audit is stale or inconsistent.": "REQUEST_SELECTION_INVALID",
}

_SHARED = frozenset({"UNCLASSIFIED", "MODEL_CALL_FAILED", "BUDGET_EXHAUSTED"}) | ERROR_CODES
AGENT_FAILURE_CODES = frozenset(TOOL_PLAN_CODES.values()) | _SHARED | {
    "PLAN_OPTION_UNKNOWN", "DELEGATION_TIMEOUT", "TOOL_OPTIONS_UNAVAILABLE",
    "SCRIPTED_OPERATION_UNMATCHED", "SPECIALIST_CONTRACT_INVALID"}
REQUEST_FAILURE_CODES = frozenset(REQUEST_CODES.values()) | _SHARED | {"REQUEST_SCHEMA_INVALID"}


def _model_code(error):
    from hawaii_activity_forecaster.model_runtime.contracts import ProposalError
    from hawaii_activity_forecaster.model_runtime.provider import ProviderError
    from hawaii_activity_forecaster.orchestration.model_calls import ModelCallError
    if isinstance(error, (ProposalError, ProviderError)):
        return str(error) if str(error) in ERROR_CODES else "MODEL_CALL_FAILED"
    if isinstance(error, ModelCallError):
        return "MODEL_CALL_FAILED"
    return None


def _budget(error):
    from hawaii_activity_forecaster.orchestration.budgets import BudgetError
    return "BUDGET_EXHAUSTED" if isinstance(error, BudgetError) else None


def agent_failure_code(error: BaseException) -> str:
    """Category for a failed specialist delegation; never includes error text."""
    from hawaii_activity_forecaster.fixtures import FixtureLoadError
    from hawaii_activity_forecaster.harness.synthetic import ScriptDispatchError
    from hawaii_activity_forecaster.orchestration.specialists import SpecialistContractError
    from hawaii_activity_forecaster.tools import ToolPlanError
    if isinstance(error, ToolPlanError):
        return TOOL_PLAN_CODES.get(str(error), "UNCLASSIFIED")
    if isinstance(error, ScriptDispatchError):
        return "SCRIPTED_OPERATION_UNMATCHED"
    if isinstance(error, FixtureLoadError):
        return "TOOL_OPTIONS_UNAVAILABLE"
    if isinstance(error, SpecialistContractError):
        return "SPECIALIST_CONTRACT_INVALID"
    if isinstance(error, TimeoutError):
        return "DELEGATION_TIMEOUT"
    if isinstance(error, KeyError):
        return "PLAN_OPTION_UNKNOWN"  # A proposed option absent from the legal lookup.
    return _model_code(error) or _budget(error) or "UNCLASSIFIED"


def request_failure_field(error: BaseException) -> str | None:
    """The closed request field a rejection concerns, when the validator names one."""
    from hawaii_activity_forecaster.interpretation.contracts import VALUE_FIELDS, RequestValidationError
    field = getattr(error, "field", None) if isinstance(error, RequestValidationError) else None
    return field if field in VALUE_FIELDS else None


def request_failure_code(error: BaseException) -> str:
    """Category for a rejected request interpretation; never includes error text."""
    from pydantic import ValidationError
    from hawaii_activity_forecaster.interpretation.contracts import RequestValidationError
    if isinstance(error, RequestValidationError):
        return REQUEST_CODES.get(str(error), "UNCLASSIFIED")
    if isinstance(error, ValidationError):
        return "REQUEST_SCHEMA_INVALID"
    return _model_code(error) or _budget(error) or "UNCLASSIFIED"
