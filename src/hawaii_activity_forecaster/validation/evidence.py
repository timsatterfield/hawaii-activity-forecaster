"""Deterministic synthetic evidence validation, separate from safety/eligibility."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Sequence

from hawaii_activity_forecaster.harness.policy import CATEGORY_SOURCES, Category, PolicyConfiguration
from hawaii_activity_forecaster.harness.synthetic import DispatchBinding
from hawaii_activity_forecaster.models import BeachCatalog, EnvironmentalFinding, EvidenceIssue, InvestigationState
from hawaii_activity_forecaster.models.enums import (
    AgentType, InvestigationStatus, MeasurementType, ValidationStatus,
)
from hawaii_activity_forecaster.models.permissions import OCEAN_SOURCES, WEATHER_SOURCES
from hawaii_activity_forecaster.tools.synthetic import RetrievalGap


class EvidenceValidationError(ValueError):
    """Invalid validation context; no authoritative update may be committed."""


@dataclass(frozen=True)
class EvidenceDecision:
    finding_id: str
    rule_id: str | None
    beach_id: str | None
    category: Category | None
    status: ValidationStatus
    reasons: tuple[str, ...]
    # Temporal overlap does not infer advisory geographic applicability or safety.
    advisory_overlaps: tuple[tuple[str, bool | None], ...] = ()


@dataclass(frozen=True)
class CategoryCoverage:
    beach_id: str
    category: Category
    priority: str
    covered: bool
    accepted_finding_ids: tuple[str, ...]
    limited_finding_ids: tuple[str, ...]
    rejected_finding_ids: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CandidateEvidenceCoverage:
    beach_id: str
    categories: tuple[CategoryCoverage, ...]

    @property
    def mandatory_categories_covered(self) -> bool:
        """Category coverage only; never SUFFICIENT evidence, safety or eligibility."""
        return all(item.covered for item in self.categories if item.priority == "MANDATORY")


@dataclass(frozen=True)
class EvidenceValidationReport:
    state: InvestigationState
    reference_time: datetime
    decisions: tuple[EvidenceDecision, ...]
    candidates: tuple[CandidateEvidenceCoverage, ...]
    conflicted_finding_ids: tuple[str, ...]


_RANK = {ValidationStatus.ACCEPTED: 0, ValidationStatus.LIMITED: 1, ValidationStatus.REJECTED: 2}
_CHECKS = {
    Category.OFFICIAL_ADVISORIES: "OFFICIAL_ADVISORY_CHECK_COMPLETE",
    Category.WATER_QUALITY_ADVISORY_CHECK: "WATER_CONTACT_ADVISORY_CHECK_COMPLETE",
}
# Verify provenance of existing required geographic/activity fields. This does
# not choose the still-open minimum optional attributes for beach activation.
_CATALOG_CORE = {"beach_id", "name", "region", "locality", "latitude", "longitude", "supported_activities", "lifeguard_status"}
_CATALOG_MATERIAL = {
    "shoreline_orientation", "coastline_exposure", "shore_type", "entry_characteristics",
    "reef_presence", "known_hazards", "activity_notes", "access_notes",
    "location_notes", "reef_notes", "lifeguard_notes", "aliases",
}


def _worst(statuses):
    return max(statuses, key=_RANK.__getitem__)


def _catalog_reasons(beach, activity, reference):
    if beach is None:
        return ("CATALOG_RECORD_MISSING",)
    reasons = []
    local_date = reference.astimezone(timezone(timedelta(hours=-10))).date()
    if beach.catalog_status != "VERIFIED":
        reasons.append("CATALOG_NOT_VERIFIED")
    if activity not in beach.supported_activities:
        reasons.append("ACTIVITY_UNSUPPORTED")
    if beach.last_verified > local_date:
        reasons.append("CATALOG_VERIFICATION_IN_FUTURE")
    required = _CATALOG_CORE | {field for field in _CATALOG_MATERIAL
                                if getattr(beach, field) not in (None, [], "")}
    supported = {field for source in beach.sources if source.accessed_at <= local_date
                 for field in source.supports_fields if source.url.strip()}
    if not required <= supported:
        reasons.append("CATALOG_ATTRIBUTE_PROVENANCE_MISSING")
    return tuple(sorted(reasons))


def _base(finding, state, reference):
    reasons = []
    rejected = False
    if finding.investigation_id != state.investigation_id:
        reasons.append("INVESTIGATION_MISMATCH")
        rejected = True
    sources = WEATHER_SOURCES if finding.agent_type == AgentType.WEATHER else OCEAN_SOURCES
    if finding.source_id not in sources or not (finding.source_reference and finding.source_reference.strip()):
        reasons.append("SOURCE_OR_PROVENANCE_INVALID")
        rejected = True
    if finding.retrieval_status in {"ERROR", "UNAVAILABLE"}:
        reasons.append("RETRIEVAL_UNAVAILABLE")
        rejected = True
    if (finding.retrieved_at > reference
            or (finding.issued_at is not None and finding.issued_at > min(reference, finding.retrieved_at))
            or (finding.observed_at is not None and finding.observed_at > min(reference, finding.retrieved_at))):
        reasons.append("SOURCE_TIMESTAMPS_INVALID")
        rejected = True
    if finding.retrieval_status == "PARTIAL" or finding.missing_fields:
        reasons.append("INCOMPLETE_FINDING")
    if not (finding.measurements or finding.descriptive_findings or finding.advisories
            or (finding.finding_type == "ADVISORY" and finding.advisories is not None)):
        reasons.append("CONTENT_MISSING")
    for measurement in finding.measurements or ():
        if measurement.measurement_type == MeasurementType.SURF_HEIGHT and measurement.measurement_convention not in {"FACE", "HAWAIIAN_BACK"}:
            reasons.append("SURF_CONVENTION_UNKNOWN")
    status = ValidationStatus.REJECTED if rejected else ValidationStatus.LIMITED if reasons else ValidationStatus.ACCEPTED
    return status, reasons


def _catalog_support(premise, beaches, activity, reference):
    local_date = reference.astimezone(timezone(timedelta(hours=-10))).date()
    for ref in premise.catalog_field_refs:
        beach = beaches.get(ref.beach_id)
        if (beach is None or _catalog_reasons(beach, activity, reference)
                or ref.field not in type(beach).model_fields
                or getattr(beach, ref.field) in (None, [], "")
                or not any(ref.field in source.supports_fields and source.accessed_at <= local_date
                           and source.url.strip() for source in beach.sources)):
            return False
    return True


def _judge(finding, rule, beach_id, state, catalog, reference):
    status, reasons = _base(finding, state, reference)
    def limit(reason):
        nonlocal status
        status = _worst((status, ValidationStatus.LIMITED))
        reasons.append(reason)
    def reject(reason):
        nonlocal status
        status = ValidationStatus.REJECTED
        reasons.append(reason)
    if finding.source_id not in CATEGORY_SOURCES.get(rule.category, set()):
        reject("CATEGORY_SOURCE_MISMATCH")
    if finding.beach_id is not None and finding.beach_id != beach_id:
        reject("BEACH_SCOPE_MISMATCH")
    if finding.coverage_type in {"LOCAL_AREA", "REGIONAL", "OFFSHORE"} and not finding.coverage_id:
        limit("GEOGRAPHIC_IDENTIFIER_MISSING")
    if finding.coverage_type in {"LOCAL_AREA", "REGIONAL"} and _catalog_reasons(catalog.get(beach_id), state.activity, reference):
        limit("REGIONAL_CATALOG_SUPPORT_UNVERIFIED")
    contextual = (rule.temporal_rule == "CONTEXT_ONLY" or finding.coverage_type == "OFFSHORE"
                  or finding.source_id in {"NDBC", "HWT_NARRATIVE"})
    if contextual:
        limit("CONTEXT_ONLY")
        if finding.finding_type == "OBSERVATION" and finding.observed_at is None:
            limit("OBSERVATION_TIME_MISSING")
    else:
        expected = {"FORECAST", "ADVISORY"} if rule.temporal_rule == "COVERS_TARGET_WINDOW" else {"REPORT"}
        if finding.finding_type not in expected:
            reject("TEMPORAL_RULE_TYPE_MISMATCH")
        if finding.issued_at is None:
            limit("ISSUANCE_TIME_MISSING")
        if finding.valid_from is None or finding.valid_until is None:
            limit("VALIDITY_WINDOW_MISSING")
        elif not (finding.valid_from <= state.target_time_window.start and finding.valid_until >= state.target_time_window.end):
            reject("TARGET_WINDOW_NOT_COVERED")
    overlaps = []
    for advisory in finding.advisories or ():
        if advisory.effective_from is None or advisory.effective_until is None:
            overlaps.append((advisory.advisory_id, None))
            limit("ADVISORY_TIME_UNKNOWN")
        else:
            overlaps.append((advisory.advisory_id, advisory.effective_from < advisory.effective_until
                             and advisory.effective_from < state.target_time_window.end
                             and advisory.effective_until > state.target_time_window.start))
    return EvidenceDecision(finding.finding_id, rule.rule_id, beach_id, rule.category, status,
                            tuple(sorted(set(reasons))), tuple(sorted(overlaps)))


def validate_evidence(
    state: InvestigationState, *, catalog: BeachCatalog, policy: PolicyConfiguration,
    bindings: Sequence[DispatchBinding], reference_time: datetime, request_step: int = 1,
    retrieval_gaps: Sequence[RetrievalGap] = (),
) -> EvidenceValidationReport:
    """Validate only observed runtime findings, using approved synthetic mappings.

    No templates, expected assertions, source-count threshold or live-provider age
    limits enter this function. It returns a detached logical snapshot; the caller
    records actual events before committing it. Terminal states are not writable.
    """
    state = InvestigationState.model_validate(state.model_dump())
    catalog = BeachCatalog.model_validate(catalog.model_dump())
    policy = PolicyConfiguration.model_validate(policy.model_dump())
    if (state.status not in {InvestigationStatus.INVESTIGATING, InvestigationStatus.EVALUATING}
            or state.activity is None or state.target_time_window is None
            or not isinstance(reference_time, datetime) or reference_time.utcoffset() is None
            or type(request_step) is not int or request_step < 1):
        raise EvidenceValidationError("Active normalized investigation and aware reference time required")
    profiles = [profile for profile in policy.evidence_profiles if profile.activity == state.activity]
    if len(profiles) != 1:
        raise EvidenceValidationError("Activity evidence profile missing")
    beaches = {beach.beach_id: beach for beach in catalog.root}
    if any(not set(rule.beach_ids) <= set(beaches) for rule in policy.evidence_rules):
        raise EvidenceValidationError("Evidence rule references an unknown catalog beach")
    refs = {}
    calls = {}
    for binding in bindings:
        if binding.runtime_investigation_id != state.investigation_id or binding.request_step != request_step:
            continue
        if not binding.runtime_tool_call_id or not binding.operation_id or type(binding.attempt) is not int or binding.attempt < 1:
            raise EvidenceValidationError("Invalid dispatch binding identity")
        descriptor = (binding.operation_id, binding.attempt, binding.source_fixture_id)
        if calls.setdefault(binding.runtime_tool_call_id, descriptor) != descriptor:
            raise EvidenceValidationError("Ambiguous runtime call binding")
        for material in binding.findings:
            if not binding.source_fixture_id:
                raise EvidenceValidationError("Finding binding lacks source fixture identity")
            value = (binding.source_fixture_id, material.template_finding_id, binding.runtime_tool_call_id)
            previous = refs.setdefault(material.runtime_finding_id, value)
            if previous != value:
                raise EvidenceValidationError("Ambiguous runtime finding binding")
    observed = defaultdict(list)
    all_findings = state.weather_findings + state.ocean_findings
    decisions = []
    for finding in sorted(all_findings, key=lambda f: f.finding_id):
        bound = refs.get(finding.finding_id)
        if bound is not None:
            observed[bound[:2]].append(finding.finding_id)
        rules = [rule for rule in policy.evidence_rules
                 if bound is not None and (rule.source_fixture_id, rule.finding_id) == bound[:2]]
        applicable = [(rule, beach_id) for rule in rules for beach_id in rule.beach_ids
                      if beach_id in state.candidate_beach_ids]
        if not applicable:
            status, reasons = _base(finding, state, reference_time)
            status = ValidationStatus.REJECTED if bound is None else _worst((status, ValidationStatus.LIMITED))
            reasons.append("RUNTIME_BINDING_MISSING" if bound is None else "APPLICABILITY_RULE_MISSING")
            decisions.append(EvidenceDecision(finding.finding_id, None, None, None, status, tuple(sorted(set(reasons)))))
        else:
            decisions.extend(_judge(finding, rule, beach_id, state, beaches, reference_time)
                             for rule, beach_id in applicable)
    # Explicit supported synthetic materiality declarations only. Do not infer
    # material conflict thresholds by comparing incomparable numbers or prose.
    conflicted = set()
    for premise in policy.premises:
        if (premise.fact_type != "MATERIAL_SAFETY_CONFLICT_PRESENT" or not premise.value
                or premise.activity != state.activity or premise.time_window != state.target_time_window
                or not _catalog_support(premise, beaches, state.activity, reference_time)):
            continue
        support = []
        for ref in premise.finding_refs:
            matches = [d.finding_id for d in decisions if d.beach_id == premise.beach_id
                       and d.finding_id in observed[(ref.source_fixture_id, ref.finding_id)]
                       and d.status != ValidationStatus.REJECTED]
            if not matches:
                break
            support.extend(matches)
        else:
            conflicted.update(support)
            decisions = [EvidenceDecision(
                d.finding_id, d.rule_id, d.beach_id, d.category,
                _worst((d.status, ValidationStatus.LIMITED)), tuple(sorted(set(d.reasons) | {"MATERIAL_CONFLICT"})),
                d.advisory_overlaps,
            ) if d.finding_id in support and d.beach_id == premise.beach_id else d for d in decisions]
    # One shared Finding has one validation_status. Conservatively propagate its
    # worst intended-use verdict so LIMITED/REJECTED material is never counted
    # as accepted support elsewhere merely through another rule.
    worst = defaultdict(list)
    for decision in decisions:
        worst[decision.finding_id].append(decision.status)
    decisions = [EvidenceDecision(
        d.finding_id, d.rule_id, d.beach_id, d.category, _worst(worst[d.finding_id]),
        tuple(sorted(set(d.reasons) | ({"OTHER_USE_LIMITATION"} if d.status != _worst(worst[d.finding_id]) else set()))),
        d.advisory_overlaps,
    ) for d in decisions]
    decisions.sort(key=lambda d: (d.finding_id, d.rule_id or "", d.beach_id or ""))
    checks = defaultdict(set)
    for premise in policy.premises:
        if (premise.fact_type not in _CHECKS.values() or not premise.value or premise.activity != state.activity
                or premise.time_window != state.target_time_window
                or not _catalog_support(premise, beaches, state.activity, reference_time)):
            continue
        category = next(category for category, fact in _CHECKS.items() if fact == premise.fact_type)
        supporting = []
        for ref in premise.finding_refs:
            ids = {d.finding_id for d in decisions if d.beach_id == premise.beach_id and d.category == category
                   and d.status == ValidationStatus.ACCEPTED and d.finding_id in observed[(ref.source_fixture_id, ref.finding_id)]}
            if not ids:
                break
            supporting.extend(ids)
        else:
            if supporting:
                checks[(premise.beach_id, category)].update(supporting)
    profile = profiles[0]
    candidates = []
    for beach_id in sorted(state.candidate_beach_ids):
        categories = []
        for category in sorted(Category):
            scoped = [d for d in decisions if d.beach_id == beach_id and d.category == category]
            accepted = {d.finding_id for d in scoped if d.status == ValidationStatus.ACCEPTED}
            reasons = set()
            if category in _CHECKS:
                accepted &= checks[(beach_id, category)]
                if not accepted:
                    reasons.add("COMPLETE_CHECK_SUPPORT_MISSING")
            if category == Category.VERIFIED_BEACH_CHARACTERISTICS:
                reasons.update(_catalog_reasons(beaches.get(beach_id), state.activity, reference_time))
                covered = not reasons
            else:
                covered = bool(accepted)
                if not covered:
                    reasons.add("ACCEPTED_CATEGORY_SUPPORT_MISSING")
            priority = "MANDATORY" if category in profile.mandatory else "RELEVANT" if category in profile.relevant else "OPTIONAL"
            categories.append(CategoryCoverage(
                beach_id, category, priority, covered, tuple(sorted(accepted)),
                tuple(sorted({d.finding_id for d in scoped if d.status == ValidationStatus.LIMITED})),
                tuple(sorted({d.finding_id for d in scoped if d.status == ValidationStatus.REJECTED})), tuple(sorted(reasons)),
            ))
        candidates.append(CandidateEvidenceCoverage(beach_id, tuple(categories)))
    statuses = defaultdict(list)
    for decision in decisions:
        statuses[decision.finding_id].append(decision.status)
    updated_findings = {f.finding_id: EnvironmentalFinding.model_validate({
        **f.model_dump(), "validation_status": _worst(statuses[f.finding_id]),
    }) for f in all_findings}
    coverage = {(c.beach_id, item.category): item.covered for c in candidates for item in c.categories}
    issues = {issue.issue_id: issue for issue in state.unresolved_evidence_issues}
    for gap in retrieval_gaps:
        if (gap.investigation_id != state.investigation_id or gap.request_revision != state.request_revision
                or gap.target_time_window != state.target_time_window):
            continue
        if gap.gap_id in issues:
            issue = issues[gap.gap_id]
            issues[gap.gap_id] = EvidenceIssue.model_validate({**issue.model_dump(), "resolved": bool(gap.candidate_beach_ids)
                and all(coverage.get((beach, gap.category), False) for beach in gap.candidate_beach_ids)})
    for candidate in candidates:
        for item in candidate.categories:
            scope = [state.investigation_id, state.request_revision, candidate.beach_id, item.category,
                     state.target_time_window.start.astimezone(timezone.utc).isoformat(),
                     state.target_time_window.end.astimezone(timezone.utc).isoformat()]
            issue_id = "evidence-" + sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()
            if item.covered and issue_id not in issues:
                continue
            ids = sorted(set(item.accepted_finding_ids + item.limited_finding_ids + item.rejected_finding_ids))
            conflict = any(d.beach_id == candidate.beach_id and d.category == item.category and "MATERIAL_CONFLICT" in d.reasons for d in decisions)
            codes = {reason for d in decisions if d.beach_id == candidate.beach_id and d.category == item.category for reason in d.reasons}
            kind = ("CONFLICTING" if conflict else "STALE" if "TARGET_WINDOW_NOT_COVERED" in codes else
                    "COVERAGE_MISMATCH" if codes & {"BEACH_SCOPE_MISMATCH", "CONTEXT_ONLY", "GEOGRAPHIC_IDENTIFIER_MISSING"} else
                    "INVALID" if item.rejected_finding_ids else "MISSING")
            issues[issue_id] = EvidenceIssue(
                issue_id=issue_id, issue_type=kind, finding_ids=ids,
                affected_beach_ids=[candidate.beach_id], description=f"Synthetic {item.priority.lower()} evidence category: {item.category}",
                resolved=item.covered,
            )
    updated = InvestigationState.model_validate({
        **state.model_dump(), "weather_findings": [updated_findings[key] for key in sorted(updated_findings) if updated_findings[key].agent_type == AgentType.WEATHER],
        "ocean_findings": [updated_findings[key] for key in sorted(updated_findings) if updated_findings[key].agent_type == AgentType.OCEAN],
        "unresolved_evidence_issues": [issues[key] for key in sorted(issues)],
    })
    return EvidenceValidationReport(updated, reference_time, tuple(decisions), tuple(candidates), tuple(sorted(conflicted)))
