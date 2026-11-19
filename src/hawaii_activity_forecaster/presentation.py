"""Read-only validation and human-readable synthetic result presentation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from hawaii_activity_forecaster.models import BeachCatalog, InvestigationState, RecommendationResult
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.recommendations import ResultContext, validate_error_result, validate_result

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


def _section(lines, title, items, *, indent=""):
    items = list(dict.fromkeys(_text(item) for item in items if _text(item)))
    if items:
        lines.append(indent + title)
        lines.extend(indent + "  - " + item for item in items)


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
        value = measurement.value
        rendered = f"{value.min}–{value.max}" if hasattr(value, "min") and hasattr(value, "max") else str(value)
        units = " " + measurement.unit if measurement.unit else ""
        convention = {"FACE": "wave-face convention", "HAWAIIAN_BACK": "Hawaiian-back convention"}.get(
            measurement.measurement_convention, measurement.measurement_convention)
        detail = f" ({convention})" if convention else ""
        lines.append("      " + _text(f"{_MEASUREMENTS[measurement.measurement_type]}: {rendered}{units}{detail}"))
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
    _section(lines, "General limitations:", [_limitation(item) for item in result.general_limitations])
    return "\n".join(lines) + "\n"
