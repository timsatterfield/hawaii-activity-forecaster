"""Approved deterministic interpretation/selection components; no general CLI."""

from .contracts import (
    PROFILE_ID, ContextLocation, InterpretationProposal, Interpreter, InterpreterInput,
    Origin, RemovedEntry, RequestContext, RequestValidationError, SourceSpan, TextSpan, ValidatedRequest,
)
from .profile import RequestRuleProfile
from .selection import CandidateSelection, CatalogSource, SelectionDecision, select_candidates, verify_selection
from .validation import interpret_request, validate_request, verify_request

__all__ = [
    "PROFILE_ID", "CandidateSelection", "CatalogSource", "ContextLocation", "InterpretationProposal", "Interpreter",
    "InterpreterInput", "Origin", "RemovedEntry", "RequestContext", "RequestRuleProfile", "RequestValidationError",
    "SelectionDecision", "SourceSpan", "TextSpan", "ValidatedRequest", "interpret_request", "select_candidates",
    "validate_request", "verify_request", "verify_selection",
]
