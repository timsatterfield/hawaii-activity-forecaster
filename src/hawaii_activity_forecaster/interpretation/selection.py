"""Catalog selection/audit components; no dispatch, assessments or result routing."""

from dataclasses import dataclass

from hawaii_activity_forecaster.catalog import catalog_provenance_reasons, location_key, location_match
from .contracts import PROFILE_ID, RequestContext, RequestValidationError, ValidatedRequest
from .validation import checked_context, digest, verify_request


@dataclass(frozen=True)
class CatalogSource:
    source_id: str
    publisher: str
    url: str
    accessed_at: str
    supports_fields: tuple[str, ...]


@dataclass(frozen=True)
class SelectionDecision:
    beach_id: str
    reasons: tuple[str, ...]
    sources: tuple[CatalogSource, ...]
    last_verified: str


@dataclass(frozen=True)
class CandidateSelection:
    request_digest: str
    rule_profile: str
    assessment_candidate_ids: tuple[str, ...]
    investigation_candidate_ids: tuple[str, ...]
    planning_order: tuple[str, ...]
    decisions: tuple[SelectionDecision, ...]


def select_candidates(receipt: ValidatedRequest, context: RequestContext) -> CandidateSelection:
    context = checked_context(context)
    receipt = verify_request(receipt, context)
    request = receipt.request
    if request.clarification_needed or request.activity is None or request.target_time_window is None:
        raise RequestValidationError("Candidate selection requires an unambiguous validated request.")
    assessments, investigation, decisions = [], [], []
    preferred = []
    for beach in sorted(context.catalog.root, key=lambda b: b.beach_id):
        reasons = list(catalog_provenance_reasons(beach, context.reference_time))
        if not reasons and not all(location_match(item, beach) for item in request.hard_constraints):
            reasons.append("OUTSIDE_HARD_LOCATION")
        if not reasons:
            assessments.append(beach.beach_id)
            if request.activity not in beach.supported_activities:
                reasons.append("ACTIVITY_UNSUPPORTED")
            else:
                investigation.append(beach.beach_id)
                if request.preferred_area is not None and location_key(request.preferred_area) in {
                    location_key(beach.region.value), location_key(beach.locality),
                }:
                    preferred.append(beach.beach_id)
        decisions.append(SelectionDecision(beach.beach_id, tuple(reasons), tuple(
            CatalogSource(s.source_id, s.publisher, s.url, s.accessed_at.isoformat(), tuple(s.supports_fields))
            for s in beach.sources), beach.last_verified.isoformat()))
    order = tuple(preferred + [key for key in investigation if key not in preferred])
    return CandidateSelection(digest({"context": receipt.context_digest, "request": request,
                                     "origins": [o.__dict__ for o in receipt.origins]}), PROFILE_ID,
                              tuple(assessments), tuple(investigation), order, tuple(decisions))


def verify_selection(audit: CandidateSelection, receipt: ValidatedRequest, context: RequestContext) -> CandidateSelection:
    canonical = select_candidates(receipt, context)
    if audit != canonical:
        raise RequestValidationError("Candidate selection audit is stale or inconsistent.")
    return canonical
