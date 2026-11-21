"""Read-only validation and human-readable synthetic result presentation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from hawaii_activity_forecaster.models import BeachCatalog, InvestigationState, RecommendationResult
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.recommendations import ResultContext, validate_error_result, validate_result
from hawaii_activity_forecaster.observability import inspect_trace

if TYPE_CHECKING:
    from hawaii_activity_forecaster.orchestration import SkeletonReport

_HST = timezone(timedelta(hours=-10))
_ACTIVITIES = {"SWIMMING": "Swimming", "SNORKELING": "Snorkeling", "SUP": "Stand-up paddleboarding (SUP)"}
_PROVIDERS = {
    "NWS_WEATHER": "National Weather Service weather", "NWS_ALERTS": "National Weather Service alerts",
    "NWS_MARINE": "National Weather Service marine/surf", "HI_DOH_CWB": "Hawaii DOH Clean Water Branch",
    "NDBC": "National Data Buoy Center", "SNORKEL_STORE": "The Snorkel Store report",
    "HWT_VISIBILITY": "HawaiiWeatherToday visibility", "HWT_SURF": "HawaiiWeatherToday surf",
    "HWT_WIND": "HawaiiWeatherToday wind", "HWT_NARRATIVE": "HawaiiWeatherToday narrative",
}
_CATEGORIES = {
    "OFFICIAL_ADVISORIES": "official advisory information", "SURF_WAVE_CONDITIONS": "surf and wave information",
    "WIND_CONDITIONS": "wind information", "CURRENTS_PERSISTENT_HAZARDS": "current and persistent-hazard information",
    "WATER_QUALITY_ADVISORY_CHECK": "the water-contact advisory check", "VERIFIED_BEACH_CHARACTERISTICS": "verified beach characteristics",
    "UNDERWATER_VISIBILITY": "underwater visibility information",
}
_REASONS = {
    "INCOMPLETE_FINDING": "Some source information is incomplete.", "CONTENT_MISSING": "Source content is missing.",
    "SURF_CONVENTION_UNKNOWN": "The reported surf-height convention is unknown.",
    "SOURCE_TIMESTAMPS_INVALID": "Source timestamps could not be validated.",
    "SOURCE_OR_PROVENANCE_INVALID": "Source attribution could not be validated.",
    "RETRIEVAL_UNAVAILABLE": "Source evidence is unavailable.", "ISSUANCE_TIME_MISSING": "Source issuance time is missing.",
    "VALIDITY_WINDOW_MISSING": "Source applicability dates are missing.", "TARGET_WINDOW_NOT_COVERED": "Source evidence does not cover the requested period.",
    "GEOGRAPHIC_IDENTIFIER_MISSING": "The source reporting area is unspecified.",
    "REGIONAL_CATALOG_SUPPORT_UNVERIFIED": "Regional applicability lacks verified catalog support.",
    "CONTEXT_ONLY": "Some evidence provides context only.", "OBSERVATION_TIME_MISSING": "Observation time is unspecified.",
    "ADVISORY_TIME_UNKNOWN": "Advisory timing remains unresolved.", "MATERIAL_CONFLICT": "A material evidence conflict remains unresolved.",
    "OTHER_USE_LIMITATION": "The finding has an unresolved applicability limitation.",
    "BEACH_SCOPE_MISMATCH": "Evidence applies to a different beach.", "CATEGORY_SOURCE_MISMATCH": "The source does not support the requested evidence category.",
    "TEMPORAL_RULE_TYPE_MISMATCH": "The evidence type does not support the requested time interpretation.",
    "INVESTIGATION_MISMATCH": "The finding belongs to another investigation.",
    "RUNTIME_BINDING_MISSING": "A finding lacks observed retrieval provenance.", "APPLICABILITY_RULE_MISSING": "A finding lacks an approved applicability mapping.",
}
# Fixed wording for disqualifying safety policies (validation/safety.py _HAZARDS).
# Policy identifiers are never presentation fields; the trace keeps them.
_EXCLUSIONS = {
    "HM-WATER-001": "an applicable official water-contact avoidance advisory",
    "HM-SURF-004": "disqualifying surf conditions for this activity",
    "HM-CURRENT-004": "a dangerous current or persistent hazard",
    "HM-WEATHER-003": "an applicable official weather or marine warning",
    "HM-WIND-002": "dangerous offshore wind for this activity",
    "HM-BEACH-004": "a disqualifying beach characteristic",
}
_MEASUREMENTS = {
    "WIND_SPEED": "Wind speed", "WIND_DIRECTION": "Wind direction", "WIND_GUST": "Wind gust",
    "PRECIPITATION": "Precipitation", "AIR_TEMPERATURE": "Air temperature", "WEATHER_CONDITION": "Weather condition",
    "SWELL_HEIGHT": "Swell height", "SWELL_DIRECTION": "Swell direction", "SWELL_PERIOD": "Swell period",
    "SURF_HEIGHT": "Surf height", "WATER_VISIBILITY": "Water visibility", "WATER_TEMPERATURE": "Water temperature",
}


class PresentationError(ValueError):
    """No verified output may be displayed; expose no proposal or private payload."""


def _text(value: object) -> str:
    # Flatten user/source strings and suppress terminal control sequences. The
    # original contracts remain intact; this is display escaping, not evidence repair.
    text = str(value)
    return " ".join("".join(char if char in "\n\r\t" or (ord(char) >= 32 and not 127 <= ord(char) <= 159)
                            else "" for char in text).split())


def _time(value: datetime | None) -> str:
    return value.astimezone(_HST).strftime("%Y-%m-%d %H:%M HST (UTC-10:00)") if value is not None else "not supplied"


def _window(value) -> str:
    return f"{_time(value.start)} to {_time(value.end)}"


def _limitation(value: str) -> str:
    if value in _REASONS:
        return _REASONS[value]
    for prefix in ("Missing mandatory evidence: ", "Missing relevant evidence: ", "Missing optional evidence: "):
        if value.startswith(prefix) and value[len(prefix):] in _CATEGORIES:
            return prefix + _CATEGORIES[value[len(prefix):]] + "."
    return _text(value)


def _verified(report, catalog, policy):
    """Audit retained active validation data without reopening terminal state."""
    try:
        report = deepcopy(report)
        state = InvestigationState.model_validate(report.state.model_dump())
        result = RecommendationResult.model_validate(report.result.model_dump())
        basis = report.result_validation
        if basis is None or report.trace_writable is not True or report.budgets.closed is not True:
            raise ValueError("No completed validation record")
        prior = InvestigationState.model_validate(basis.state.model_dump())
        terminal = {"RECOMMENDATIONS": "COMPLETED", "NO_RECOMMENDATION": "ABSTAINED", "ERROR": "FAILED"}
        if (state.status != terminal[result.outcome] or state.result_id != result.result_id or state.outcome != result.outcome
                or result.generated_at > state.updated_at or report.budgets.active_specialists
                or report.budgets.reserved_tool_calls or report.budgets.reserved_model_calls
                or state.tool_call_count != report.budgets.tool_calls or state.retry_count != report.budgets.retries
                or state.iteration_count != report.budgets.iterations
                or state.fallback_attempted != bool(report.budgets.fallbacks)):
            raise ValueError("Terminal result or budget mismatch")
        final_fields = {"status", "updated_at", "outcome", "result_id", "completion_reason"}
        if state.model_dump(exclude=final_fields) != prior.model_dump(exclude=final_fields):
            raise ValueError("Terminal state differs from its validation basis")
        if basis.authoritative_trace and (report.trace_path is None or report.trace_validation is None):
            raise ValueError("The required authoritative trace receipt is absent")
        if report.trace_path is not None:
            observed = inspect_trace(report.trace_path, state=state, result=result, budgets=report.budgets,
                                     bindings=report.tool_bindings, evidence=report.evidence_report, safety=report.safety_report)
            if observed != report.trace_validation or not observed.complete:
                raise ValueError("Authoritative trace differs from its validated publication basis")
        if result.outcome == "ERROR":
            result = validate_error_result(result, prior, now=state.updated_at, error_code=basis.error_code,
                                           request_context=report.request_context, request_receipt=report.request_receipt)
        else:
            if report.evidence_report is None or report.safety_report is None or catalog is None or policy is None or basis.error_code is not None:
                raise ValueError("Grounding context is absent")
            catalog = BeachCatalog.model_validate(catalog.model_dump())
            policy = PolicyConfiguration.model_validate(policy.model_dump())
            context = ResultContext(prior, report.evidence_report, report.safety_report, catalog, policy,
                                    report.tool_bindings, request_step=basis.request_step,
                                    request_context=report.request_context, request_receipt=report.request_receipt,
                                    selection=report.selection)
            result = validate_result(result, context, now=state.updated_at, stop_reason=basis.stop_reason)
    except (ValueError, TypeError, AttributeError, KeyError, IndexError):
        raise PresentationError("No validated result is available for presentation.") from None
    return report, state, result, catalog


def _exclusion_reasons(state, beaches):
    """(beach_id, name, fixed reasons) for validated EXCLUDED candidates only."""
    items = []
    for assessment in sorted(state.assessments, key=lambda a: a.beach_id):
        if assessment.eligibility != "EXCLUDED" or assessment.beach_id not in beaches:
            continue
        reasons = [_EXCLUSIONS.get(policy_id, "a disqualifying safety policy")
                   for policy_id in assessment.disqualifying_policy_ids]
        for constraint in assessment.hard_constraint_results:
            kind, _, value = constraint.constraint_description.partition(": ")
            if constraint.result == "FAIL" and kind.startswith("Required ") and value:
                reasons.append(f"outside your required {kind.removeprefix('Required ')} "
                               f"({value.replace('_', ' ').title()})")
            elif constraint.result == "FAIL":
                reasons.append("a required condition you specified is not met")
        items.append((assessment.beach_id, beaches[assessment.beach_id].name, reasons or ["excluded by a safety policy"]))
    return items


def _exclusions(state, beaches):
    """Validated EXCLUDED candidates with fixed reasons; never recommendations or scores."""
    return [f"{name}: " + "; ".join(reasons) for _, name, reasons in _exclusion_reasons(state, beaches)]


def _section(lines, title, items, *, indent=""):
    items = list(dict.fromkeys(_text(item) for item in items if _text(item)))
    if items:
        lines.append(indent + title)
        lines.extend(indent + "  - " + item for item in items)


def _measurement(measurement) -> str:
    value = measurement.value
    rendered = f"{value.min}–{value.max}" if hasattr(value, "min") and hasattr(value, "max") else str(value)
    units = " " + measurement.unit if measurement.unit else ""
    convention = {"FACE": "wave-face convention", "HAWAIIAN_BACK": "Hawaiian-back convention"}.get(
        measurement.measurement_convention, measurement.measurement_convention)
    detail = f" ({convention})" if convention else ""
    return _text(f"{_MEASUREMENTS[measurement.measurement_type]}: {rendered}{units}{detail}")


def _evidence(lines, finding):
    provider = _PROVIDERS.get(finding.source_id, finding.source_id)
    lines.append(f"    - {_text(provider)} — {finding.finding_type.value.capitalize()}")
    lines.append(f"      Coverage: {_text(finding.coverage_description)} ({finding.coverage_type.value.lower().replace('_', ' ')})")
    if finding.valid_from is not None and finding.valid_until is not None:
        lines.append(f"      Applies: {_time(finding.valid_from)} to {_time(finding.valid_until)}")
    if finding.issued_at is not None:
        lines.append(f"      Issued: {_time(finding.issued_at)}")
    if finding.observed_at is not None:
        lines.append(f"      Observed: {_time(finding.observed_at)}")
    lines.append(f"      Retrieved: {_time(finding.retrieved_at)}")
    for measurement in finding.measurements or ():
        lines.append("      " + _measurement(measurement))
        if measurement.measurement_time is not None:
            lines.append("      Measurement time: " + _time(measurement.measurement_time))
        if measurement.measurement_notes:
            lines.append("      Measurement notes: " + _text(measurement.measurement_notes))
    if finding.source_reference:
        lines.append("      Reference: " + _text(finding.source_reference))


def render_report(report: SkeletonReport, *, catalog: BeachCatalog | None = None,
                  policy: PolicyConfiguration | None = None) -> str:
    """Render only a validated committed synthetic result; no I/O or new work."""
    report, state, result, catalog = _verified(report, catalog, policy)
    lines = ["Hawaii Activity Forecaster — synthetic result", *(_text(item) for item in result.general_warnings),
             "Activity: " + _ACTIVITIES[result.activity], "Requested time: " + _window(result.target_time_window), ""]
    if result.outcome == "ERROR":
        lines.extend(["Technical error", _text(result.error_summary)])
        return "\n".join(lines) + "\n"
    beaches = {beach.beach_id: beach for beach in catalog.root}
    if result.outcome == "NO_RECOMMENDATION":
        lines.extend(["No recommendation", _text(result.explanation)])
        _section(lines, "Affected locations:", [beaches[key].name for key in result.affected_beach_ids or () if key in beaches])
        _section(lines, "Not recommended (excluded):", _exclusions(state, beaches))
        issues = []
        for issue in result.unresolved_issues or ():
            prefix, separator, detail = issue.partition(": ")
            issues.append((beaches[prefix].name + separator + detail) if prefix in beaches else issue)
        _section(lines, "Unresolved questions:", issues)
        _section(lines, "Limitations:", [_limitation(item) for item in result.general_limitations])
        _section(lines, "Next steps:", result.next_step_suggestions or ())
        return "\n".join(lines) + "\n"
    lines.append("Recommendations (no finer rank is claimed)")
    findings = {f.finding_id: f for f in state.weather_findings + state.ocean_findings}
    for recommendation in result.recommendations:
        lines.extend(["", "- " + _text(recommendation.display_name),
                      f"  Suitability: {recommendation.environmental_suitability.value.capitalize()}; evidence: {recommendation.evidence_quality.value.lower()}",
                      "  Recommended time: " + _window(recommendation.recommended_time_window),
                      "  Why: " + _text(recommendation.recommendation_reason),
                      "  Evidence summary: " + _text(recommendation.environmental_summary)])
        _section(lines, "Warnings and disclosures:", recommendation.warnings, indent="  ")
        _section(lines, "Limitations:", [_limitation(item) for item in recommendation.limitations], indent="  ")
        _section(lines, "Preferences:", recommendation.preference_alignment, indent="  ")
        lines.append("  Environmental sources (synthetic fixtures):")
        for finding_id in recommendation.supporting_finding_ids:
            _evidence(lines, findings[finding_id])
        if recommendation.advisory_references:
            notices = {a.advisory_id: a for fid in recommendation.supporting_finding_ids for a in findings[fid].advisories or ()}
            lines.append("  Reported advisories:")
            for advisory_id in recommendation.advisory_references:
                advisory = notices[advisory_id]
                lines.extend(["    - " + _text(advisory.advisory_type) + " — " + _text(advisory.issuer),
                              "      Source area: " + _text(advisory.affected_area),
                              f"      Effective: {_time(advisory.effective_from)} to {_time(advisory.effective_until)}",
                              "      Reference: " + _text(advisory.source_reference)])
                if advisory.severity:
                    lines.append("      Reported severity: " + _text(advisory.severity))
        lines.append("  Catalog attribution:")
        beach = beaches[recommendation.beach_id]
        for source in beach.sources:
            if source.source_id in recommendation.source_references:
                lines.extend(["    - " + _text(source.publisher) + " — " + _text(source.title or source.publisher),
                              f"      Accessed: {source.accessed_at.isoformat()}; catalog verified: {beach.last_verified.isoformat()}",
                              "      Reference: " + _text(source.url)])
    lines.append("")
    _section(lines, "Not recommended (excluded):", _exclusions(state, beaches))
    _section(lines, "General limitations:", [_limitation(item) for item in result.general_limitations])
    return "\n".join(lines) + "\n"


# --- Structured view for the local web interface (M2 WEB-A) ---------------------
# report_view() shares _verified() and the fixed wording above with render_report(),
# so the web page can show only what the CLI would show. Policy identifiers and
# decision-reason strings stay in the trace; they are not presentation fields.

def _value(item) -> str:
    return str(getattr(item, "value", item))


def _when(value: datetime | None) -> dict | None:
    return None if value is None else {"iso": value.isoformat(), "display": _time(value)}


def _span(value) -> dict:
    return {"start": _when(value.start), "end": _when(value.end), "display": _window(value)}


def _finding_view(finding) -> dict:
    convention = {"FACE": "wave-face", "HAWAIIAN_BACK": "Hawaiian-back"}
    return {
        "finding_id": finding.finding_id,
        "agent": _value(finding.agent_type),
        "source_id": finding.source_id,
        "provider": _text(_PROVIDERS.get(finding.source_id, finding.source_id)),
        "finding_type": _value(finding.finding_type).capitalize(),
        "coverage": _text(finding.coverage_description),
        "coverage_type": _value(finding.coverage_type).lower().replace("_", " "),
        "beach_id": finding.beach_id,
        "valid_from": _when(finding.valid_from), "valid_until": _when(finding.valid_until),
        "issued_at": _when(finding.issued_at), "observed_at": _when(finding.observed_at),
        "retrieved_at": _when(finding.retrieved_at),
        "measurements": [_measurement(item) for item in finding.measurements or ()],
        "measurement_conventions": sorted({convention.get(m.measurement_convention, m.measurement_convention)
                                           for m in finding.measurements or () if m.measurement_convention}),
        "advisories": [{"type": _text(a.advisory_type), "issuer": _text(a.issuer), "area": _text(a.affected_area),
                        "effective": f"{_time(a.effective_from)} to {_time(a.effective_until)}",
                        "severity": _text(a.severity) if a.severity else None,
                        "reference": _text(a.source_reference)} for a in finding.advisories or ()],
        "retrieval_status": _value(finding.retrieval_status),
        "validation_status": _value(finding.validation_status),
        "limitations": [_limitation(_value(item)) for item in finding.limitations or ()],
        "reference": _text(finding.source_reference) if finding.source_reference else None,
    }


def _beach_view(assessment, beach, findings) -> dict:
    def listed(ids):
        return [findings[key] for key in ids if key in findings]
    return {
        "beach_id": assessment.beach_id,
        "name": _text(beach.name), "region": _text(_value(beach.region)), "locality": _text(beach.locality or ""),
        "latitude": float(beach.latitude) if beach.latitude is not None else None,
        "longitude": float(beach.longitude) if beach.longitude is not None else None,
        "eligibility": _value(assessment.eligibility),
        "environmental_suitability": _value(assessment.environmental_suitability),
        "evidence_quality": _value(assessment.evidence_quality),
        "geographic_preference_match": _value(assessment.geographic_preference_match)
            if assessment.geographic_preference_match is not None else None,
        "policy_checks": [{"result": _value(item.result), "explanation": _text(item.explanation)}
                          for item in assessment.policy_results],
        "hard_constraints": [{"description": _text(item.constraint_description), "result": _value(item.result)}
                             for item in assessment.hard_constraint_results],
        "preferences": [{"description": _text(item.preference_description), "alignment": _value(item.alignment),
                         "explanation": _text(item.explanation)} for item in assessment.preference_results],
        "evidence_limitations": [_limitation(_value(item)) for item in assessment.evidence_limitations],
        "safety_limitations": [_text(item) for item in assessment.safety_limitations],
        "remaining_questions": [_text(item) for item in assessment.remaining_questions],
        "supporting": listed(assessment.supporting_finding_ids),
        "conflicting": listed(assessment.conflicting_finding_ids),
        "rejected": listed(assessment.rejected_finding_ids),
        "catalog": {
            "shore_type": _text(_value(beach.shore_type)) if beach.shore_type else None,
            "reef_presence": _text(_value(beach.reef_presence)) if beach.reef_presence is not None else None,
            "lifeguard_status": _text(_value(beach.lifeguard_status)) if beach.lifeguard_status else None,
            "supported_activities": [_ACTIVITIES.get(_value(a), _value(a)) for a in beach.supported_activities],
            "last_verified": beach.last_verified.isoformat(),
            "sources": [{"publisher": _text(source.publisher), "title": _text(source.title or source.publisher),
                         "reference": _text(source.url), "accessed_at": source.accessed_at.isoformat()}
                        for source in beach.sources],
        },
    }


def report_view(report: SkeletonReport, *, catalog: BeachCatalog | None = None,
                policy: PolicyConfiguration | None = None) -> dict:
    """JSON-safe view of a validated committed result, under render_report()'s checks."""
    report, state, result, catalog = _verified(report, catalog, policy)
    view = {
        "investigation_id": state.investigation_id, "session_id": state.session_id,
        "request_revision": state.request_revision, "status": _value(state.status), "outcome": result.outcome,
        "activity": _ACTIVITIES[result.activity], "activity_code": result.activity,
        "window": _span(result.target_time_window),
        "general_warnings": [_text(item) for item in result.general_warnings],
        "general_limitations": list(dict.fromkeys(_limitation(item) for item in result.general_limitations)),
        "request": {
            "preferred_area": _text(state.preferred_area) if state.preferred_area else None,
            "experience_level": _value(state.experience_level).capitalize() if state.experience_level else None,
            "original": _text(state.original_request),
            "hard_constraints": [_text(", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in item.items()))
                                 for item in state.hard_constraints],
            "soft_preferences": [_text(item.get("preference") or ", ".join(f"{k}: {v}" for k, v in item.items()))
                                 for item in state.soft_preferences],
        },
        "usage": {"tool_calls": state.tool_call_count, "max_tool_calls": state.max_tool_calls,
                  "iterations": state.iteration_count, "max_iterations": state.max_iterations,
                  "retries": state.retry_count, "max_retries": state.max_retries,
                  "fallback_attempted": state.fallback_attempted},
        "recommendations": [], "exclusions": [], "beaches": [], "abstention": None, "error": None,
    }
    if result.outcome == "ERROR":
        view["error"] = {"summary": _text(result.error_summary)}
        return view
    beaches = {beach.beach_id: beach for beach in catalog.root}
    findings = {f.finding_id: _finding_view(f) for f in state.weather_findings + state.ocean_findings}
    view["beaches"] = [_beach_view(a, beaches[a.beach_id], findings)
                       for a in sorted(state.assessments, key=lambda a: a.beach_id) if a.beach_id in beaches]
    view["exclusions"] = [{"beach_id": key, "name": _text(name), "reasons": [_text(r) for r in reasons]}
                          for key, name, reasons in _exclusion_reasons(state, beaches)]
    if result.outcome == "NO_RECOMMENDATION":
        issues = []
        for issue in result.unresolved_issues or ():
            prefix, separator, detail = issue.partition(": ")
            issues.append(_text((beaches[prefix].name + separator + detail) if prefix in beaches else issue))
        view["abstention"] = {
            "explanation": _text(result.explanation),
            "affected": [_text(beaches[key].name) for key in result.affected_beach_ids or () if key in beaches],
            "unresolved": issues,
            "next_steps": [_text(item) for item in result.next_step_suggestions or ()],
        }
        return view
    for recommendation in result.recommendations:
        notices = {a.advisory_id: a for fid in recommendation.supporting_finding_ids
                   for a in (next((f for f in state.weather_findings + state.ocean_findings if f.finding_id == fid), None).advisories or ())}
        beach = beaches[recommendation.beach_id]
        view["recommendations"].append({
            "beach_id": recommendation.beach_id, "name": _text(recommendation.display_name),
            "environmental_suitability": recommendation.environmental_suitability.value,
            "evidence_quality": recommendation.evidence_quality.value,
            "window": _span(recommendation.recommended_time_window),
            "reason": _text(recommendation.recommendation_reason),
            "summary": _text(recommendation.environmental_summary),
            "warnings": list(dict.fromkeys(_text(item) for item in recommendation.warnings if _text(item))),
            "limitations": list(dict.fromkeys(_limitation(item) for item in recommendation.limitations)),
            "preferences": list(dict.fromkeys(_text(item) for item in recommendation.preference_alignment if _text(item))),
            "evidence": [findings[fid] for fid in recommendation.supporting_finding_ids],
            "advisories": [{"type": _text(notices[a].advisory_type), "issuer": _text(notices[a].issuer),
                            "area": _text(notices[a].affected_area),
                            "effective": f"{_time(notices[a].effective_from)} to {_time(notices[a].effective_until)}",
                            "reference": _text(notices[a].source_reference),
                            "severity": _text(notices[a].severity) if notices[a].severity else None}
                           for a in recommendation.advisory_references],
            "attribution": [{"publisher": _text(s.publisher), "title": _text(s.title or s.publisher),
                             "accessed_at": s.accessed_at.isoformat(), "verified": beach.last_verified.isoformat(),
                             "reference": _text(s.url)}
                            for s in beach.sources if s.source_id in recommendation.source_references],
        })
    return view
