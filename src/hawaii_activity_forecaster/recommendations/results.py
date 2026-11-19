"""Controlled synthetic comparison/result construction and independent validation.

These components publish no CLI output and do not establish full scenario or
production trace readiness. Free-form model-generated claims are not validated.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pydantic import BaseModel

from hawaii_activity_forecaster.config.settings import InvestigationLimits
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.harness.synthetic import DispatchBinding
from hawaii_activity_forecaster.models import (
    BeachCatalog, CandidateAssessment, InvestigationState, Recommendation, RecommendationResult,
)
from hawaii_activity_forecaster.validation import EvidenceValidationReport, SafetyEvaluationReport, evaluate_safety

SYNTHETIC_WARNING = "SYNTHETIC TEST OUTPUT: fictional locations and conditions; not for real activity planning."
_ERROR_MESSAGES = {
    "RESULT_VALIDATION_FAILED": "The structured result could not be validated against the current investigation.",
    "INVESTIGATION_EXECUTION_FAILED": "An application execution error prevented a validated result.",
    "TRACE_WRITE_FAILED": "Required investigation events could not be recorded.",
}
_STOPS = {"ASSESSMENT_COMPLETE", "NO_FURTHER_ACTION", "ITERATION_LIMIT_REACHED"}


class ResultValidationError(ValueError):
    """The output is not grounded in the current trusted investigation."""


@dataclass(frozen=True)
class ResultContext:
    """Trusted active snapshots, not a new persisted logical schema."""

    state: InvestigationState
    evidence: EvidenceValidationReport
    safety: SafetyEvaluationReport
    catalog: BeachCatalog
    policy: PolicyConfiguration
    bindings: tuple[DispatchBinding, ...]
    request_step: int = 1


@dataclass(frozen=True)
class ResultValidationSnapshot:
    """Read-only preterminal basis retained for later presentation checks.

    This is runtime metadata, not a persisted schema or permission to resume.
    """

    state: InvestigationState
    stop_reason: str | None
    error_code: str | None
    request_step: int = 1


@dataclass(frozen=True)
class CandidateComparison:
    investigation_id: str
    request_revision: int
    groups: tuple[tuple[str, ...], ...]
    selected_assessment_ids: tuple[str, ...]
    omitted_assessment_ids: tuple[str, ...]
    criteria: tuple[str, ...] = ("environmental suitability", "canonical area preference")


def _digest(value):
    def encode(item):
        if isinstance(item, BaseModel):
            return item.model_dump()
        if isinstance(item, datetime):
            return item.astimezone(timezone.utc).isoformat()
        return str(item)
    return sha256(json.dumps(value, sort_keys=True, default=encode, separators=(",", ":")).encode()).hexdigest()


def _active(state, *, evaluating):
    valid = {"EVALUATING"} if evaluating else {"INITIALIZING", "INVESTIGATING", "EVALUATING"}
    if state.status not in valid or state.activity is None or state.target_time_window is None:
        raise ResultValidationError("A current normalized nonterminal investigation is required")
    if evaluating and state.clarification_needed:
        raise ResultValidationError("Unresolved request clarification prevents result construction")
    if evaluating:
        limits = InvestigationLimits()
        if (state.max_iterations != limits.max_coordinator_iterations
                or state.max_tool_calls != limits.max_environmental_tool_invocations
                or state.max_retries != limits.max_retries_per_failed_invocation
                or state.iteration_count > limits.max_coordinator_iterations
                or state.tool_call_count > limits.max_environmental_tool_invocations
                or state.retry_count > state.tool_call_count):
            raise ResultValidationError("Investigation execution counters or maxima violate the approved limits")


def _time(value, state, *, now=None):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ResultValidationError("An aware result timestamp is required")
    if value < max(state.created_at, state.updated_at):
        raise ResultValidationError("Result predates the current investigation snapshot")
    if now is not None:
        if not isinstance(now, datetime) or now.utcoffset() is None or value > now:
            raise ResultValidationError("Result timestamp is later than validation time")


def _checked(context: ResultContext) -> ResultContext:
    context = deepcopy(context)
    try:
        state = InvestigationState.model_validate(context.state.model_dump())
        _active(state, evaluating=True)
        canonical = evaluate_safety(context.evidence, catalog=context.catalog, policy=context.policy,
                                    bindings=context.bindings, request_step=context.request_step)
    except (ValueError, TypeError, AttributeError):
        raise ResultValidationError("Evidence and safety context could not be verified") from None
    if (canonical.assessments != context.safety.assessments or canonical.state != context.safety.state
            or context.safety.request_revision != state.request_revision):
        raise ResultValidationError("Safety report is stale or inconsistent")
    # A controller may advance INV -> EVAL and the update timestamp without
    # changing the assessment basis. No other scope/counter/input changes pass.
    excluded = {"updated_at", "status"}
    if state.model_dump(exclude=excluded) != canonical.state.model_dump(exclude=excluded):
        raise ResultValidationError("Current state differs from the assessed investigation")
    if state.updated_at < canonical.state.updated_at:
        raise ResultValidationError("Current state predates its assessments")
    return ResultContext(state, context.evidence, canonical, context.catalog, context.policy,
                         tuple(context.bindings), context.request_step)


def _dominates(left: CandidateAssessment, right: CandidateAssessment) -> bool:
    suitability = {"FAVORABLE": 1, "MIXED": 0}
    l, r = suitability[left.environmental_suitability], suitability[right.environmental_suitability]
    # No proximity or distance is inferred. Unknown/unrecognized comparisons
    # have no preference ordering; all eligible candidates already have SUFFICIENT.
    geo = {"PREFERRED_AREA": 1, "OUTSIDE_PREFERRED_AREA": 0}
    lg, rg = geo.get(left.geographic_preference_match), geo.get(right.geographic_preference_match)
    if (lg is None) != (rg is None):
        return False
    pairs = [(l, r)]
    if lg is not None and rg is not None:
        pairs.append((lg, rg))
    return all(a >= b for a, b in pairs) and any(a > b for a, b in pairs)


def _compare(context):
    remaining = {a.assessment_id: a for a in context.safety.assessments if a.eligibility == "ELIGIBLE"}
    groups = []
    while remaining:
        front = [a for a in remaining.values() if not any(_dominates(other, a) for other in remaining.values())]
        ordered = tuple(a.assessment_id for a in sorted(front, key=lambda a: a.beach_id))
        groups.append(ordered)
        for assessment_id in ordered:
            del remaining[assessment_id]
    all_ids = tuple(assessment_id for group in groups for assessment_id in group)
    cap = InvestigationLimits().max_recommendations
    return CandidateComparison(context.state.investigation_id, context.state.request_revision,
                               tuple(groups), all_ids[:cap], all_ids[cap:])


def compare_candidates(context: ResultContext) -> CandidateComparison:
    """Qualitative dominance groups; no forced rank within a group or scores.

    Catalog-ID order within a group is only repeatable presentation/truncation,
    never a suitability distinction. Favorable/outside versus MIXED/preferred
    remains a tradeoff, not a weighted total ordering.
    """
    return _compare(_checked(context))


def _recommendation(assessment, context):
    state = context.state
    beach = next(b for b in context.catalog.root if b.beach_id == assessment.beach_id)
    findings = {f.finding_id: f for f in state.weather_findings + state.ocean_findings}
    accepted = sorted(fid for fid in assessment.supporting_finding_ids if findings[fid].validation_status == "ACCEPTED")
    if not accepted:
        raise ResultValidationError("Eligible recommendation lacks accepted environmental evidence")
    scoped = [d for d in context.evidence.decisions if d.beach_id == beach.beach_id
              and d.status == "ACCEPTED" and d.finding_id in accepted]
    if not set(accepted) <= {d.finding_id for d in scoped}:
        raise ResultValidationError("Recommendation finding scope is not accepted for this candidate")
    warnings = list(assessment.safety_limitations)
    advisories = set()
    catalog_ids = {b.beach_id for b in context.catalog.root}
    for decision in scoped:
        finding = findings[decision.finding_id]
        overlap = dict(decision.advisory_overlaps)
        for advisory in finding.advisories or ():
            if overlap.get(advisory.advisory_id) is False:
                continue
            if advisory.affected_area in catalog_ids and advisory.affected_area != beach.beach_id:
                continue
            advisories.add(advisory.advisory_id)
            warnings.append(f"Reported advisory: {advisory.advisory_type}; source area: {advisory.affected_area}; issuer: {advisory.issuer}")
    local_date = context.evidence.reference_time.astimezone(timezone(timedelta(hours=-10))).date()
    sources = {findings[fid].source_id for fid in accepted} | {
        source.source_id for source in beach.sources if source.accessed_at <= local_date
    }
    kinds = sorted({findings[fid].finding_type.value.lower() for fid in accepted})
    geographic_limit = any(findings[fid].coverage_type != "BEACH" for fid in accepted)
    summary = "Synthetic policy interpretation based on accepted " + ", ".join(kinds) + " evidence for the requested period."
    limits = list(assessment.evidence_limitations)
    if geographic_limit:
        limits.append("Regional or area evidence retains its reported coverage; it is not a direct beach observation.")
    reason = (f"{assessment.environmental_suitability.value.capitalize()} suitability with sufficient evidence and resolved recommendation requirements.")
    if assessment.geographic_preference_match == "PREFERRED_AREA":
        reason += " Matches the requested catalog area."
    elif assessment.geographic_preference_match == "OUTSIDE_PREFERRED_AREA":
        reason += " Outside the preferred area; included because it meets the evidence and safety requirements."
    preferences = [p.explanation for p in assessment.preference_results if p.alignment in {"MATCH", "PARTIAL", "NO_MATCH"}]
    return Recommendation(
        recommendation_id="recommendation-" + _digest([assessment.assessment_id, state.target_time_window]),
        beach_id=beach.beach_id, assessment_id=assessment.assessment_id, rank=None, display_name=beach.name,
        environmental_suitability=assessment.environmental_suitability, evidence_quality=assessment.evidence_quality,
        recommended_time_window=state.target_time_window, supporting_finding_ids=accepted,
        advisory_references=sorted(advisories), recommendation_reason=reason, environmental_summary=summary,
        preference_alignment=preferences, warnings=sorted(set(warnings)), limitations=sorted(set(limits)),
        source_references=sorted(sources),
    )


def _abstention(context, stop_reason):
    assessments = context.safety.assessments
    if assessments and all(a.eligibility == "EXCLUDED" for a in assessments):
        return "APPLICABLE_HAZARDS", "All assessed candidates have verified disqualifying policy failures."
    if assessments and all(a.eligibility in {"EXCLUDED", "UNSUPPORTED"} for a in assessments):
        return "NO_ELIGIBLE_CANDIDATES", "Evaluated candidates are excluded by policy or outside verified beach/activity support."
    if any(a.conflicting_finding_ids for a in assessments):
        return "CONFLICTING_EVIDENCE", "Unresolved material evidence conflicts prevent a supported recommendation."
    if any(any(c.result != "PASS" for c in a.hard_constraint_results) for a in assessments):
        return "UNRESOLVED_CONSTRAINTS", "Hard user constraints require an approved interpretation or additional verification."
    if stop_reason == "ITERATION_LIMIT_REACHED" and any(a.eligibility == "NEEDS_INVESTIGATION" for a in assessments):
        return "INVESTIGATION_LIMIT_REACHED", "The investigation limit was reached with required questions still unresolved."
    if any(a.evidence_quality != "SUFFICIENT" for a in assessments):
        return "INSUFFICIENT_EVIDENCE", "Required evidence or safety-policy checks remain unresolved; additional verified evidence is needed."
    return "NO_ELIGIBLE_CANDIDATES", "No assessed candidate satisfies all current recommendation requirements."


def _assemble(context, generated_at, stop_reason):
    state = context.state
    _time(generated_at, state)
    if stop_reason not in _STOPS:
        raise ResultValidationError("Unknown trusted investigation stopping reason")
    if stop_reason == "ITERATION_LIMIT_REACHED" and state.iteration_count < state.max_iterations:
        raise ResultValidationError("Iteration-limit explanation contradicts the current counter")
    comparison = _compare(context)
    by_id = {a.assessment_id: a for a in context.safety.assessments}
    entries = [_recommendation(by_id[key], context) for key in comparison.selected_assessment_ids]
    data = dict(
        investigation_id=state.investigation_id, request_revision=state.request_revision,
        schema_version=state.schema_version, generated_at=generated_at, activity=state.activity,
        target_time_window=state.target_time_window, general_warnings=[SYNTHETIC_WARNING], recommendations=entries,
    )
    if entries:
        limitations = []
        if len(entries) < InvestigationLimits().max_recommendations:
            limitations.append(f"Only {len(entries)} evaluated candidate(s) met all recommendation requirements.")
        if comparison.omitted_assessment_ids:
            limitations.append("Additional eligible options were omitted by the three-location limit.")
        if any(len(group) > 1 for group in comparison.groups):
            limitations.append("Some eligible options have no established preference-based ordering; no finer rank is claimed.")
        data.update(outcome="RECOMMENDATIONS", summary=f"{len(entries)} synthetic recommendation(s) qualify for the requested activity and period.",
                    general_limitations=limitations)
    else:
        reason, explanation = _abstention(context, stop_reason)
        unresolved = sorted({f"{a.beach_id}: {result.explanation}" for a in context.safety.assessments
                             for result in a.policy_results if result.result == "UNKNOWN"})
        limits = sorted({note for a in context.safety.assessments for note in a.evidence_limitations + a.safety_limitations})
        data.update(outcome="NO_RECOMMENDATION", summary="No supported synthetic recommendation is available for the requested period.",
                    general_limitations=limits, no_recommendation_reason=reason, explanation=explanation,
                    affected_beach_ids=sorted(a.beach_id for a in context.safety.assessments), unresolved_issues=unresolved,
                    next_step_suggestions=["Resolve the documented evidence or constraint questions before starting a new investigation."])
    return RecommendationResult(result_id="result-" + _digest(data), **data)


def build_result(context: ResultContext, *, generated_at: datetime, stop_reason: str = "ASSESSMENT_COMPLETE") -> RecommendationResult:
    """Construct the controlled synthetic result; independent validation follows."""
    return _assemble(_checked(context), generated_at, stop_reason)


def validate_result(proposal: RecommendationResult, context: ResultContext, *, now: datetime,
                    stop_reason: str = "ASSESSMENT_COMPLETE") -> RecommendationResult:
    """Validate current references, grounding, disclosures, selection and text.

    Only this increment's deterministic templates are supported. Arbitrary prose
    cannot be declared grounded by checking IDs alone and is therefore rejected.
    """
    context = _checked(context)
    try:
        proposal = RecommendationResult.model_validate(proposal.model_dump() if isinstance(proposal, BaseModel) else deepcopy(proposal))
    except (ValueError, TypeError):
        raise ResultValidationError("Invalid result structure") from None
    _time(proposal.generated_at, context.state, now=now)
    expected = _assemble(context, proposal.generated_at, stop_reason)
    if proposal != expected:
        raise ResultValidationError("Result differs from the current grounded selection, context or required disclosures")
    return proposal


def build_error_result(state: InvestigationState, *, generated_at: datetime, error_code: str) -> RecommendationResult:
    """Sanitized operational failure, never a source-outage suitability verdict."""
    state = InvestigationState.model_validate(state.model_dump())
    _active(state, evaluating=False)
    _time(generated_at, state)
    if error_code not in _ERROR_MESSAGES:
        raise ResultValidationError("Unknown trusted operational failure code")
    data = dict(investigation_id=state.investigation_id, request_revision=state.request_revision,
                schema_version=state.schema_version, generated_at=generated_at, activity=state.activity,
                target_time_window=state.target_time_window, outcome="ERROR", summary=_ERROR_MESSAGES[error_code],
                recommendations=[], general_warnings=[SYNTHETIC_WARNING], general_limitations=[],
                error_code=error_code, error_summary=_ERROR_MESSAGES[error_code], recoverable=False)
    return RecommendationResult(result_id="result-" + _digest(data), **data)


def validate_error_result(proposal: RecommendationResult, state: InvestigationState, *, now: datetime,
                          error_code: str) -> RecommendationResult:
    try:
        proposal = RecommendationResult.model_validate(proposal.model_dump() if isinstance(proposal, BaseModel) else deepcopy(proposal))
    except (ValueError, TypeError):
        raise ResultValidationError("Invalid error result structure") from None
    _time(proposal.generated_at, state, now=now)
    expected = build_error_result(state, generated_at=proposal.generated_at, error_code=error_code)
    if proposal != expected:
        raise ResultValidationError("Error output is inconsistent with its trusted operational failure")
    return proposal
