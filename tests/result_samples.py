"""Fictional multi-candidate result contexts without independent scenario oracles."""

from datetime import timedelta
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.harness.synthetic import DispatchBinding, FindingBinding
from hawaii_activity_forecaster.models import BeachCatalog, InvestigationState
from hawaii_activity_forecaster.recommendations import ResultContext
from hawaii_activity_forecaster.validation import evaluate_safety, validate_evidence
from safety_samples import context, mixed_context
from specialist_samples import NOW

GENERATED = NOW + timedelta(seconds=2)


def result_context(beaches=("TEST_BEACH_A",), *, mixed=(), preferred_area=None):
    seed, seed_catalog, seed_policy, _ = context("SNORKELING")
    catalog_data, weather, ocean, rules, premises, bindings, permissions = [], [], [], [], [], [], []
    for beach_id in beaches:
        state, catalog, policy, observed = mixed_context() if beach_id in mixed else context("SNORKELING")
        beach = next(b for b in catalog.root if b.beach_id == "TEST_BEACH_A").model_dump()
        location = next(b for b in seed_catalog.root if b.beach_id == beach_id)
        beach.update(beach_id=beach_id, name=f"Fictional {beach_id} (SYNTHETIC)", region=location.region, locality=location.locality)
        for source in beach["sources"]:
            source["source_id"] = "catalog-" + beach_id
            source["url"] = "https://example.invalid/catalog/" + beach_id
        catalog_data.append(beach)
        for domain, dest in ((state.weather_findings, weather), (state.ocean_findings, ocean)):
            for finding in domain:
                dest.append(finding.model_dump() | {"finding_id": finding.finding_id + "-" + beach_id,
                                                    "beach_id": beach_id if finding.beach_id else None})
        for binding in observed:
            bindings.append(DispatchBinding(
                binding.request_step, binding.operation_id, binding.attempt,
                binding.runtime_investigation_id, binding.runtime_tool_call_id,
                binding.source_fixture_id,
                tuple(FindingBinding(f.template_finding_id + "-" + beach_id, f.runtime_finding_id + "-" + beach_id) for f in binding.findings),
            ))
        for rule in policy.evidence_rules:
            rules.append(rule.model_dump() | {"rule_id": rule.rule_id + "-" + beach_id,
                                               "source_fixture_id": rule.source_fixture_id,
                                               "finding_id": rule.finding_id + "-" + beach_id, "beach_ids": [beach_id]})
        for premise in policy.premises:
            data = premise.model_dump()
            data.update(premise_id=premise.premise_id + "-" + beach_id, beach_id=beach_id,
                        finding_refs=[dict(source_fixture_id=r.source_fixture_id,
                                           finding_id=r.finding_id + "-" + beach_id) for r in premise.finding_refs],
                        catalog_field_refs=[dict(beach_id=beach_id, field=r.field) for r in premise.catalog_field_refs])
            premises.append(data)
        if policy.mixed_permissions:
            permissions = [p.model_dump() for p in policy.mixed_permissions]
    policy = PolicyConfiguration.model_validate(seed_policy.model_dump() | {
        "evidence_rules": rules, "premises": premises, "mixed_permissions": permissions,
    })
    # A shared source response can contain separate findings for several beaches.
    # Keep the multi-candidate example within the approved actual call cap.
    grouped = {}
    for binding in bindings:
        key = (binding.operation_id, binding.attempt, binding.runtime_tool_call_id, binding.source_fixture_id)
        grouped.setdefault(key, []).extend(binding.findings)
    bindings = [DispatchBinding(1, op, attempt, seed.investigation_id, call, fixture, tuple(material))
                for (op, attempt, call, fixture), material in grouped.items()]
    catalog = BeachCatalog.model_validate(catalog_data)
    state = InvestigationState.model_validate(seed.model_dump() | {
        "candidate_beach_ids": list(beaches), "remaining_candidate_ids": list(beaches),
        "preferred_area": preferred_area, "weather_findings": weather, "ocean_findings": ocean,
        "tool_call_count": len(bindings),
    })
    evidence = validate_evidence(state, catalog=catalog, policy=policy, bindings=bindings, reference_time=NOW)
    safety = evaluate_safety(evidence, catalog=catalog, policy=policy, bindings=bindings)
    current = InvestigationState.model_validate(safety.state.model_dump() | {"status": "EVALUATING", "updated_at": NOW + timedelta(seconds=1)})
    return ResultContext(current, evidence, safety, catalog, policy, tuple(bindings))
