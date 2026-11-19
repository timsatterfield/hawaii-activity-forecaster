"""Deterministic synthetic safety policies and revision-bound assessments.

Only independently validated evidence and approved, supported synthetic premises
may establish a policy outcome. No numeric hazard thresholds or advice generation.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Sequence
from pydantic import BaseModel

from hawaii_activity_forecaster.harness.policy import Category, FactType, PolicyConfiguration
from hawaii_activity_forecaster.harness.synthetic import DispatchBinding
from hawaii_activity_forecaster.models import (
    BeachCatalog, CandidateAssessment, ConstraintResult, InvestigationState, PolicyResult, PreferenceResult,
)
from .evidence import EvidenceValidationReport, _catalog_support, validate_evidence


class SafetyEvaluationError(ValueError):
    """Invalid or stale evaluation context; no assessment may be committed."""


@dataclass(frozen=True)
class SafetyEvaluationReport:
    state: InvestigationState
    assessments: tuple[CandidateAssessment, ...]
    request_revision: int


# Existing requirement IDs identify the implemented policy decisions. The closed
# FactType vocabulary supplies hypothetical classifications, never final verdicts.
_HAZARDS = (
    (FactType.WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT, "HM-WATER-001", {Category.WATER_QUALITY_ADVISORY_CHECK}),
    (FactType.DISQUALIFYING_SURF_PRESENT, "HM-SURF-004", {Category.SURF_WAVE_CONDITIONS}),
    (FactType.DANGEROUS_CURRENT_PRESENT, "HM-CURRENT-004", {Category.CURRENTS_PERSISTENT_HAZARDS}),
    (FactType.DISQUALIFYING_WEATHER_PRESENT, "HM-WEATHER-003", {Category.OFFICIAL_ADVISORIES, Category.WIND_CONDITIONS}),
    (FactType.DANGEROUS_OFFSHORE_WIND_PRESENT, "HM-WIND-002", {Category.WIND_CONDITIONS}),
    (FactType.DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT, "HM-BEACH-004", set(Category)),
)


def _digest(value):
    def encode(item):
        if isinstance(item, BaseModel):
            return item.model_dump()
        if isinstance(item, datetime):
            return item.astimezone(timezone.utc).isoformat()
        return str(item)
    return sha256(json.dumps(value, sort_keys=True, default=encode, separators=(",", ":")).encode()).hexdigest()


def _constraint_results(state):
    # The input JsonObject vocabulary/normalization is still open. Do not adopt
    # an ad hoc DSL or trust caller-supplied result/eligibility keys as verdicts.
    return [ConstraintResult(
        constraint_id="constraint-" + _digest([state.investigation_id, state.request_revision, index, payload])[:24],
        constraint_description=f"Hard constraint {index + 1} requires approved normalization",
        result="UNKNOWN", explanation="No approved deterministic interpretation is available for this constraint input",
    ) for index, payload in enumerate(state.hard_constraints)]


def _preferences(state, beach, catalog):
    results = [PreferenceResult(
        preference_id="preference-" + _digest([state.investigation_id, state.request_revision, index, payload])[:24],
        preference_description=f"Soft preference {index + 1} requires approved normalization", alignment="UNKNOWN",
        explanation="Uninterpreted preference cannot override any safety or eligibility decision",
    ) for index, payload in enumerate(state.soft_preferences)]
    if state.preferred_area is None:
        return results, "NOT_SPECIFIED", []
    area = state.preferred_area.strip().casefold().replace("_", " ")
    known = {b.locality.casefold() for b in catalog.root} | {b.region.value.casefold().replace("_", " ") for b in catalog.root}
    if area not in known:
        return results, "NOT_SPECIFIED", ["Area preference has no approved canonical catalog match; no distance/nearby inference made"]
    matching = area in {beach.locality.casefold(), beach.region.value.casefold().replace("_", " ")}
    return results, "PREFERRED_AREA" if matching else "OUTSIDE_PREFERRED_AREA", []


class _CandidatePolicies:
    def __init__(self, report, policy, catalog, bindings, beach_id, request_step):
        self.report, self.policy, self.catalog = report, policy, catalog
        self.state, self.beach_id = report.state, beach_id
        self.decisions = [d for d in report.decisions if d.beach_id == beach_id]
        self.coverage = {c.category: c for candidate in report.candidates if candidate.beach_id == beach_id for c in candidate.categories}
        self.findings = {f.finding_id: f for f in self.state.weather_findings + self.state.ocean_findings}
        self.observed = {}
        for binding in bindings:
            if binding.runtime_investigation_id == self.state.investigation_id and binding.request_step == request_step:
                for finding in binding.findings:
                    self.observed.setdefault((binding.source_fixture_id, finding.template_finding_id), set()).add(finding.runtime_finding_id)
        self.premises = {p.fact_type: p for p in policy.premises if p.beach_id == beach_id
                         and p.activity == self.state.activity and p.time_window == self.state.target_time_window}
        self.results = {}
        self.mandatory = set()
        self.limitations = []

    def result(self, policy_id, outcome, ids, explanation, *, mandatory=True):
        self.results[policy_id] = PolicyResult(policy_id=policy_id, result=outcome,
                                              supporting_finding_ids=sorted(set(ids)), explanation=explanation)
        if mandatory:
            self.mandatory.add(policy_id)

    def fact(self, fact_type, categories, *, uncertainty=False):
        premise = self.premises.get(fact_type)
        if premise is None:
            return None, (), "Synthetic fact is not declared"
        if not _catalog_support(premise, self.catalog, self.state.activity, self.report.reference_time):
            return None, (), "Catalog premise support is unverified or missing"
        if any(isinstance(getattr(self.catalog[ref.beach_id], ref.field), str)
               and getattr(self.catalog[ref.beach_id], ref.field).casefold() == "unknown"
               for ref in premise.catalog_field_refs):
            return None, (), "An explicitly unknown catalog attribute cannot establish a resolved fact"
        if fact_type == FactType.DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT and not premise.catalog_field_refs:
            return None, (), "Persistent-characteristic classification requires attributable catalog field support"
        support = set()
        for ref in premise.finding_refs:
            observed = self.observed.get((ref.source_fixture_id, ref.finding_id), set())
            matches = set()
            for decision in self.decisions:
                if decision.finding_id not in observed or decision.category not in categories:
                    continue
                valid = decision.status == "ACCEPTED"
                if decision.status == "LIMITED":
                    # LIMITED data can expose uncertainty, never clear a hazard.
                    valid = (uncertainty and premise.value) or (premise.value and bool(decision.reasons)
                            and decision.finding_id in self.report.conflicted_finding_ids
                            and set(decision.reasons) <= {"MATERIAL_CONFLICT", "OTHER_USE_LIMITATION"})
                if valid:
                    matches.add(decision.finding_id)
            if not matches:
                return None, tuple(sorted(support)), "Required premise finding was not received and accepted for this candidate/use"
            support.update(matches)
        return premise.value, tuple(sorted(support)), "Explicit synthetic fact has actual scoped support"

    def official_records(self):
        """Known fixture vocabulary only; no generic advisory-text classifier.

        Other notices/unknown geography or timing remain unresolved, not blanket
        closures. An actual known applicable prohibition wins over false premises.
        """
        failures, uncertain = {}, {}
        for decision in self.decisions:
            if decision.category not in {Category.OFFICIAL_ADVISORIES, Category.WATER_QUALITY_ADVISORY_CHECK}:
                continue
            finding = self.findings[decision.finding_id]
            if finding.source_id not in {"HI_DOH_CWB", "NWS_ALERTS", "NWS_MARINE"} or decision.status == "REJECTED":
                continue
            for advisory in finding.advisories or ():
                overlap = dict(decision.advisory_overlaps).get(advisory.advisory_id)
                if overlap is False:
                    continue
                if advisory.affected_area in self.catalog and advisory.affected_area != self.beach_id:
                    continue
                policy_id = "HM-WATER-001" if finding.source_id == "HI_DOH_CWB" else "HM-WEATHER-003"
                trusted = decision.status == "ACCEPTED" or (decision.status == "LIMITED"
                    and set(decision.reasons) <= {"MATERIAL_CONFLICT", "OTHER_USE_LIMITATION"})
                known = (finding.source_id == "HI_DOH_CWB"
                         and advisory.advisory_type == "Synthetic water-contact avoidance advisory"
                         and finding.coverage_type == "BEACH" and finding.beach_id == self.beach_id
                         and advisory.affected_area == self.beach_id and overlap is True and trusted)
                target = failures if known else uncertain
                target.setdefault(policy_id, set()).add(finding.finding_id)
        return failures, uncertain

    def evaluate(self):
        catalog_ok = self.coverage[Category.VERIFIED_BEACH_CHARACTERISTICS].covered
        self.result("BC-007", "PASS" if catalog_ok else "UNKNOWN", (),
                    "Catalog/activity attribution is verified" if catalog_ok else "Verified catalog/activity support is unavailable")
        covered = all(c.covered for c in self.coverage.values() if c.priority == "MANDATORY")
        self.result("ES-V002", "PASS" if covered else "UNKNOWN",
                    [fid for c in self.coverage.values() if c.priority == "MANDATORY" for fid in c.accepted_finding_ids],
                    "Mandatory activity categories have accepted support" if covered else "Mandatory evidence categories remain unresolved")
        for category, policy_id in ((Category.OFFICIAL_ADVISORIES, "ES-005"), (Category.WATER_QUALITY_ADVISORY_CHECK, "HM-WATER-005")):
            item = self.coverage[category]
            self.result(policy_id, "PASS" if item.covered else "UNKNOWN", item.accepted_finding_ids,
                        "Explicit complete-check premise has accepted support" if item.covered else "Mandatory advisory-status check is unresolved")
        for fact_type, policy_id, categories in _HAZARDS:
            value, ids, explanation = self.fact(fact_type, categories)
            if fact_type == FactType.DANGEROUS_OFFSHORE_WIND_PRESENT and self.state.activity != "SUP":
                if fact_type not in self.premises:
                    self.result(policy_id, "NOT_APPLICABLE", (), "SUP-specific exposure rule does not establish another activity's wind hazard", mandatory=False)
                    continue
                if value is True:
                    self.result(policy_id, "UNKNOWN", ids, "Non-SUP offshore wind requires a documented activity-specific hazard classification")
                    continue
            result = "UNKNOWN" if value is None else "FAIL" if value else "PASS"
            if fact_type == FactType.WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT and value is False and not self.coverage[Category.WATER_QUALITY_ADVISORY_CHECK].covered:
                result, explanation = "UNKNOWN", "A false hazard premise cannot clear an incomplete mandatory water-contact check"
            self.result(policy_id, result, ids, explanation)
        true_advisories, unknown_advisories = self.official_records()
        for policy_id, ids in true_advisories.items():
            self.result(policy_id, "FAIL", ids, "Accepted applicable official water-contact avoidance advisory overrides favorable or false hazard claims")
        for policy_id, ids in unknown_advisories.items():
            if self.results[policy_id].result != "FAIL":
                self.result(policy_id, "UNKNOWN", ids, "Official advisory meaning, geography or timing requires explicit resolution; a notice is not automatically a closure")
        conflict, ids, explanation = self.fact(FactType.MATERIAL_SAFETY_CONFLICT_PRESENT, set(Category), uncertainty=True)
        scoped_conflicts = {d.finding_id for d in self.decisions if "MATERIAL_CONFLICT" in d.reasons}
        self.result("ES-009", "UNKNOWN" if conflict is not False or scoped_conflicts else "PASS", ids,
                    "Material conflict remains unresolved" if conflict or scoped_conflicts else explanation)
        support, ids, explanation = self.fact(FactType.ACTIVITY_SUPPORTING_CONDITIONS_PRESENT, set(Category))
        self.result("ES-007", "PASS" if support is True else "UNKNOWN", ids,
                    explanation if support is True else "Accepted positive activity-supporting conditions have not been established", mandatory=False)
        limitation, ids, explanation = self.fact(FactType.NON_DISQUALIFYING_LIMITATION_PRESENT, {Category.UNDERWATER_VISIBILITY})
        permission = next((p for p in self.policy.mixed_permissions if p.activity == self.state.activity
                           and p.limitation_code == "SYNTHETIC_POOR_VISIBILITY"), None)
        if FactType.NON_DISQUALIFYING_LIMITATION_PRESENT not in self.premises:
            self.result("HM-VIS-003", "NOT_APPLICABLE", (), "No reviewed non-disqualifying limitation is declared", mandatory=False)
        else:
            permitted = limitation is False or (limitation is True and permission is not None)
            self.result("HM-VIS-003", "PASS" if permitted else "UNKNOWN", ids,
                        "Reviewed non-disqualifying visibility limitation requires disclosure" if limitation is True and permission else
                        "MIXED visibility permission is missing" if limitation is True else explanation, mandatory=False)
            if limitation is True and permission:
                self.limitations.append(permission.disclosure)
        return catalog_ok, limitation, permission


def evaluate_safety(
    evidence: EvidenceValidationReport, *, catalog: BeachCatalog, policy: PolicyConfiguration,
    bindings: Sequence[DispatchBinding], request_step: int = 1,
) -> SafetyEvaluationReport:
    """Produce current Candidate Assessments without generating any final result.

    Revalidation guards against caller-forged or stale evidence reports. The fixed
    reference clock, actual bindings and full scope are required on every call.
    Opaque hard constraints remain UNKNOWN until their input interpretation is
    approved; source/model-provided PASS/FAIL fields cannot bypass this boundary.
    """
    catalog = BeachCatalog.model_validate(catalog.model_dump())
    policy = PolicyConfiguration.model_validate(policy.model_dump())
    canonical = validate_evidence(evidence.state, catalog=catalog, policy=policy, bindings=bindings,
                                  reference_time=evidence.reference_time, request_step=request_step)
    if (canonical.decisions != evidence.decisions or canonical.candidates != evidence.candidates
            or canonical.conflicted_finding_ids != evidence.conflicted_finding_ids or canonical.state != evidence.state):
        raise SafetyEvaluationError("Evidence report is stale or inconsistent with its validation context")
    state = canonical.state
    beaches = {beach.beach_id: beach for beach in catalog.root}
    if not set(state.candidate_beach_ids) <= set(beaches):
        raise SafetyEvaluationError("Candidate assessment requires a supported catalog record")
    assessments = []
    for beach_id in sorted(state.candidate_beach_ids):
        evaluator = _CandidatePolicies(canonical, policy, beaches, bindings, beach_id, request_step)
        catalog_ok, limitation, permission = evaluator.evaluate()
        policies = [evaluator.results[key] for key in sorted(evaluator.results)]
        failed = sorted(p.policy_id for p in policies if p.result == "FAIL")
        unresolved = sorted(p.policy_id for p in policies if p.result == "UNKNOWN")
        mandatory_unknown = [key for key in evaluator.mandatory if evaluator.results[key].result == "UNKNOWN"]
        missing_basis = any(not c.covered and not (c.accepted_finding_ids or c.limited_finding_ids)
                            for c in evaluator.coverage.values() if c.priority == "MANDATORY")
        covered = all(c.covered for c in evaluator.coverage.values() if c.priority == "MANDATORY")
        quality = "INSUFFICIENT" if missing_basis else "SUFFICIENT" if covered and not mandatory_unknown else "LIMITED"
        positive = evaluator.results["ES-007"].result == "PASS"
        suitability = ("UNFAVORABLE" if failed else "UNDETERMINED" if not positive else
                       "MIXED" if limitation is True else "UNDETERMINED" if limitation is None
                       and FactType.NON_DISQUALIFYING_LIMITATION_PRESENT in evaluator.premises else "FAVORABLE")
        constraints = _constraint_results(state)
        preferences, geography, area_notes = _preferences(state, beaches[beach_id], catalog)
        eligible = ("EXCLUDED" if failed or any(c.result == "FAIL" for c in constraints) else
                    "UNSUPPORTED" if not catalog_ok else
                    "ELIGIBLE" if quality == "SUFFICIENT" and suitability in {"FAVORABLE", "MIXED"}
                    and not unresolved and all(c.result == "PASS" for c in constraints)
                    and (suitability != "MIXED" or permission is not None) else "NEEDS_INVESTIGATION")
        scoped = evaluator.decisions
        rejected = {d.finding_id for d in scoped if d.status == "REJECTED"}
        supporting = ({d.finding_id for d in scoped if d.status == "ACCEPTED"}
                      | {fid for result in policies for fid in result.supporting_finding_ids}) - rejected
        conflicting = {d.finding_id for d in scoped if "MATERIAL_CONFLICT" in d.reasons}
        limits = sorted({reason for d in scoped for reason in d.reasons}
                        | {f"Missing {c.priority.lower()} evidence: {c.category}" for c in evaluator.coverage.values() if not c.covered}
                        | {note for fid in supporting for note in evaluator.findings[fid].limitations or ()})
        safety_notes = sorted(set(evaluator.limitations + area_notes + (["Hard constraints require approved normalization"] if constraints else [])))
        questions = [f"Resolve policy {key}" for key in unresolved] + [f"Clarify {c.constraint_id}" for c in constraints if c.result == "UNKNOWN"]
        reasons = [f"{eligible}: evidence={quality}; environmental suitability={suitability}"]
        if failed:
            reasons.append("Disqualifying policy failures take precedence: " + ", ".join(failed))
        if unresolved:
            reasons.append("Unresolved policy checks: " + ", ".join(unresolved))
        if constraints:
            reasons.append("Uninterpreted hard constraints are not treated as passing")
        actions = (["CONSIDER_ALTERNATIVE_BEACH"] if eligible in {"EXCLUDED", "UNSUPPORTED"} else
                   ["READY_FOR_COMPARISON"] if eligible == "ELIGIBLE" else
                   ["REQUEST_USER_CLARIFICATION"] if constraints else ["INVESTIGATE_ALTERNATIVE_SOURCE"])
        payload = dict(
            investigation_id=state.investigation_id, beach_id=beach_id, activity=state.activity,
            target_time_window=state.target_time_window, evaluated_at=canonical.reference_time,
            eligibility=eligible, environmental_suitability=suitability, evidence_quality=quality,
            supporting_finding_ids=sorted(supporting), conflicting_finding_ids=sorted(conflicting),
            rejected_finding_ids=sorted(rejected), evidence_limitations=limits,
            assessment_basis="Deterministic approved synthetic policies using actual validated evidence and scoped supported premises",
            hard_constraint_results=constraints, preference_results=preferences, geographic_preference_match=geography,
            policy_results=policies, disqualifying_policy_ids=failed, unresolved_policy_ids=unresolved,
            safety_limitations=safety_notes, decision_reasons=reasons, recommended_next_actions=actions,
            remaining_questions=questions,
        )
        fingerprint = _digest([
            state.request_revision, policy, payload, beaches[beach_id],
            [evaluator.findings[key] for key in sorted({d.finding_id for d in scoped})],
        ])
        assessments.append(CandidateAssessment(
            **payload, assessment_id="assessment-" + fingerprint,
            assessment_version=f"m1.4b/revision-{state.request_revision}/{fingerprint[:16]}",
        ))
    updated = InvestigationState.model_validate(state.model_dump() | {"assessments": [a.model_dump() for a in assessments]})
    return SafetyEvaluationReport(updated, tuple(assessments), state.request_revision)
