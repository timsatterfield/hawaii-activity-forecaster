"""Independent synthetic evidence validation; safety policy remains separate."""

from .evidence import (
    CandidateEvidenceCoverage, CategoryCoverage, EvidenceDecision, EvidenceValidationError,
    EvidenceValidationReport, validate_evidence,
)

__all__ = [
    "CandidateEvidenceCoverage", "CategoryCoverage", "EvidenceDecision", "EvidenceValidationError",
    "EvidenceValidationReport", "validate_evidence",
]
