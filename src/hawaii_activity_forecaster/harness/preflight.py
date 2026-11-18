"""Cross-artifact validation. Does not accept evidence or evaluate policy facts."""

from pydantic import ValidationError

from hawaii_activity_forecaster.fixtures.loading import FixtureLoadError, _OCEAN_SOURCES, _WEATHER_SOURCES
from hawaii_activity_forecaster.models import EnvironmentalToolResponse, SpecialistError
from hawaii_activity_forecaster.models.enums import AgentType, CoverageType, FindingType, SourceId

from .assertions import SELECTORS, TraceSelector, pointer_tokens
from .policy import CATEGORY_SOURCES, Category, FactType
from .requirements import REQUIREMENT_IDS


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureLoadError(message)


def requirement_refs(ids) -> None:
    require(set(ids) <= REQUIREMENT_IDS, "Unknown approved requirement identifier.")


def domain(source, agent) -> None:
    require(source in (_WEATHER_SOURCES if agent == AgentType.WEATHER else _OCEAN_SOURCES),
            "Unauthorized specialist/source pairing.")


def check_sources(registry, responses, catalog) -> None:
    beaches = {b.beach_id for b in catalog.root}
    calls, findings = set(), set()
    error_codes = {"SOURCE_UNAVAILABLE", "SOURCE_TIMEOUT", "SOURCE_RESPONSE_INVALID", "SOURCE_ACCESS_DENIED",
                   "CONTRACT_VALIDATION_FAILED", "UNSUPPORTED_EVIDENCE_REQUEST", "EXECUTION_LIMIT_REACHED", "INTERNAL_ERROR"}
    for fixture_id, response in responses.items():
        entry = registry[fixture_id]
        domain(entry.source_id, entry.agent_type)
        require(response.source_id == entry.source_id, "Response provider does not match source registration.")
        require(response.tool_call_id not in calls, "Duplicate tool call ID across source templates.")
        calls.add(response.tool_call_id)
        for finding in response.findings:
            require(finding.finding_id not in findings, "Duplicate finding ID across source templates.")
            findings.add(finding.finding_id)
            require(finding.agent_type == entry.agent_type, "Finding domain does not match its registered source.")
            require(finding.beach_id is None or finding.beach_id in beaches, "Finding references unknown beach.")
        if response.retrieval_status == "ERROR":
            require(bool(response.errors), "ERROR response requires structured errors.")
        if response.retrieval_status == "PARTIAL":
            require(bool(response.missing_evidence or response.errors), "PARTIAL response requires explicit gaps/errors.")
        if response.retrieval_status == "UNAVAILABLE":
            require(bool(response.missing_evidence or response.errors), "UNAVAILABLE response requires an explicit gap/error.")
        for raw in response.errors:
            try:
                error = SpecialistError.model_validate(raw)
            except ValidationError:
                raise FixtureLoadError("Invalid synthetic tool error structure.") from None
            require(error.error_code in error_codes, "Unsupported synthetic tool error code.")
            require(error.source_id is None or error.source_id == response.source_id, "Error source mismatch.")
            require(error.tool_call_id is None or error.tool_call_id == response.tool_call_id, "Error call mismatch.")


def finding_for(ref, responses):
    require(ref.source_fixture_id in responses, "Finding reference uses an unselected source.")
    matches = [f for f in responses[ref.source_fixture_id].findings if f.finding_id == ref.finding_id]
    require(len(matches) == 1, "Unresolved template finding reference.")
    return matches[0]


def check_policy(policy, responses, catalog, script) -> None:
    beaches = {b.beach_id: b for b in catalog.root}
    profiles = {p.activity: p for p in policy.evidence_profiles}
    for permission in policy.mixed_permissions:
        requirement_refs(permission.requirement_ids)
    for rule in policy.evidence_rules:
        finding = finding_for(rule, responses)
        require(set(rule.beach_ids) <= set(beaches), "Evidence rule references unknown beach.")
        require(finding.source_id in CATEGORY_SOURCES[rule.category], "Unsupported category/source mapping.")
        if finding.coverage_type == CoverageType.BEACH:
            require(set(rule.beach_ids) == {finding.beach_id}, "BEACH evidence cannot map to another beach.")
        if finding.coverage_type == CoverageType.OFFSHORE or finding.source_id in {SourceId.NDBC, SourceId.HWT_NARRATIVE}:
            require(rule.temporal_rule == "CONTEXT_ONLY", "Offshore/context sources cannot establish beach evidence.")
        if rule.temporal_rule == "COVERS_TARGET_WINDOW":
            require(finding.finding_type in {FindingType.FORECAST, FindingType.ADVISORY}, "Window rule cannot convert a report/observation into a forecast.")
        if rule.temporal_rule == "DECLARED_REPORT_WINDOW":
            require(finding.finding_type == FindingType.REPORT, "Report window requires REPORT evidence.")
    for premise in policy.premises:
        require(premise.beach_id in beaches, "Premise references unknown beach.")
        require(premise.activity in profiles, "Premise activity lacks an evidence profile.")
        for ref in premise.finding_refs:
            finding = finding_for(ref, responses)
            require(finding.beach_id is None or finding.beach_id == premise.beach_id,
                    "Premise cannot relabel another beach's finding.")
        for ref in premise.catalog_field_refs:
            beach = beaches[ref.beach_id]
            require(ref.field in type(beach).model_fields and getattr(beach, ref.field) not in (None, [], ""),
                    "Catalog field support is absent or unknown.")
    scoped = {p.beach_id for p in policy.premises} | {b for op in script.operations for b in op.candidate_beach_ids}
    for beach_id in scoped:
        require(beach_id in beaches, "Operation references unknown beach.")
        for profile in profiles.values():
            if profile.activity not in beaches[beach_id].supported_activities:
                continue  # An intentional UNSUPPORTED combination is a valid test input.
            for category in profile.mandatory + profile.relevant + profile.optional:
                if category == Category.VERIFIED_BEACH_CHARACTERISTICS:
                    continue
                declared = any(r.category == category and beach_id in r.beach_ids for r in policy.evidence_rules)
                explicit_gap = any(beach_id in op.candidate_beach_ids and category in op.requested_evidence
                                   and any(a.behavior in {"UNAVAILABLE", "ERROR", "TIMEOUT", "MALFORMED"} for a in op.attempts)
                                   for op in script.operations)
                require(declared or explicit_gap, "Scoped category lacks declared evidence or explicit missing coverage.")


def check_script(script, registry, responses, scenario) -> None:
    require(script.requests[0].user_request == scenario.user_request and
            script.requests[0].reference_time == scenario.reference_time,
            "First script request must match TestScenario.")
    for op in script.operations:
        domain(op.source_id, op.agent_type)
        for category in op.requested_evidence:
            require(category in CATEGORY_SOURCES and op.source_id in CATEGORY_SOURCES[category],
                    "Operation uses an unauthorized evidence category/source mapping.")
        for attempt in op.attempts:
            if attempt.response_fixture_id is None:
                continue
            require(attempt.response_fixture_id in responses, "Behavior refers to an unselected response fixture.")
            response = responses[attempt.response_fixture_id]
            entry = registry[attempt.response_fixture_id]
            require(entry.agent_type == op.agent_type and entry.source_id == op.source_id,
                    "Behavior response does not match operation specialist/provider.")
            allowed = {"SUCCESS", "PARTIAL"} if attempt.behavior == "DUPLICATE" else {attempt.behavior}
            require(response.retrieval_status in allowed, "Response status contradicts declared behavior.")
            require(all(f.beach_id is None or f.beach_id in op.candidate_beach_ids for f in response.findings),
                    "Behavior response exceeds operation candidate scope.")


def check_malformed(attempt, raw) -> None:
    try:
        EnvironmentalToolResponse.model_validate(raw)
    except ValidationError as error:
        allowed = [pointer_tokens(pointer) for pointer in attempt.invalid_fields]
        for item in error.errors(include_input=False, include_context=False):
            location = [str(part) for part in item["loc"]]
            require(bool(location) and any(location[:len(path)] == path for path in allowed),
                    "Malformed payload has undeclared contract faults.")
    else:
        raise FixtureLoadError("MALFORMED payload must actually violate the tool contract.")


def check_assertion_refs(assertion, script, responses, catalog) -> None:
    requirement_refs(assertion.requirement_ids)
    beaches = {b.beach_id for b in catalog.root}
    refs = [assertion] + ([assertion.expected_ref] if assertion.expected_ref is not None else [])
    for ref in refs:
        selector = SELECTORS[ref.target].model_validate(ref.selector)
        require(selector.request_step <= len(script.requests), "Assertion refers to an absent request step.")
        if getattr(selector, "beach_id", None) is not None:
            require(selector.beach_id in beaches, "Assertion references unknown beach.")
        nested = [selector]
        if isinstance(selector, TraceSelector):
            nested += [r for r in (selector.related_finding_ref, selector.related_call_ref) if r is not None]
        for selected in nested:
            if getattr(selected, "source_fixture_id", None) is not None:
                require(selected.source_fixture_id in responses, "Assertion references an unselected source.")
                require(any(f.finding_id == selected.template_finding_id for f in responses[selected.source_fixture_id].findings),
                        "Assertion references an unknown template finding.")
            if getattr(selected, "operation_id", None) is not None:
                operations = [op for op in script.operations if op.operation_id == selected.operation_id
                              and op.request_step == selector.request_step]
                require(len(operations) == 1 and selected.attempt <= len(operations[0].attempts),
                        "Assertion operation/attempt binding is unresolved.")
                fixture_id = getattr(selected, "source_fixture_id", None)
                if fixture_id is not None:
                    require(operations[0].attempts[selected.attempt - 1].response_fixture_id == fixture_id,
                            "Assertion finding reference disagrees with operation/attempt.")
