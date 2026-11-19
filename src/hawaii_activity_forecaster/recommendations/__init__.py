"""Qualitative eligible comparison and controlled synthetic structured results."""

from .results import (
    CandidateComparison, ResultContext, ResultValidationError, ResultValidationSnapshot, build_error_result, build_result,
    compare_candidates, validate_error_result, validate_result,
)

__all__ = [
    "CandidateComparison", "ResultContext", "ResultValidationError", "ResultValidationSnapshot", "build_error_result", "build_result",
    "compare_candidates", "validate_error_result", "validate_result",
]
