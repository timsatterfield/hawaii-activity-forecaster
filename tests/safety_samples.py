"""Explicit hypothetical safety facts, independent of evaluator assertions."""

from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.models import BeachCatalog, InvestigationState
from hawaii_activity_forecaster.validation import validate_evidence
from evidence_samples import sample
from specialist_samples import BEACH, NOW, WINDOW


def context(activity="SWIMMING"):
    snapshot, catalog, policy, bindings = sample()
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {
        "activity": activity, "hard_constraints": [], "soft_preferences": [],
    })
    catalog_data = catalog.model_dump()
    next(beach for beach in catalog_data if beach["beach_id"] == BEACH)["supported_activities"] = ["SWIMMING", "SNORKELING", "SUP"]
    catalog = BeachCatalog.model_validate(catalog_data)
    data = policy.model_dump()
    facts = [
        ("WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT", False, ["water"]),
        ("DISQUALIFYING_SURF_PRESENT", False, ["marine"]),
        ("DANGEROUS_CURRENT_PRESENT", False, ["marine"]),
        ("DISQUALIFYING_WEATHER_PRESENT", False, ["alerts", "wind"]),
        ("DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT", False, []),
        ("MATERIAL_SAFETY_CONFLICT_PRESENT", False, ["marine", "water", "alerts"]),
        ("ACTIVITY_SUPPORTING_CONDITIONS_PRESENT", True, ["marine", "wind"]),
    ]
    if activity == "SUP":
        facts.append(("DANGEROUS_OFFSHORE_WIND_PRESENT", False, ["wind"]))
    for fact, value, sources in facts:
        data["premises"].append(dict(
            premise_id="fact-" + fact, beach_id=BEACH, activity=activity, time_window=WINDOW,
            fact_type=fact, value=value,
            finding_refs=[dict(source_fixture_id=source, finding_id="template-" + source) for source in sources],
            catalog_field_refs=[dict(beach_id=BEACH, field="access_notes")] if not sources else [],
            rationale="Explicit scoped synthetic classification, not a numerical threshold or final outcome",
        ))
    return snapshot, catalog, PolicyConfiguration.model_validate(data), bindings


def fact(policy, name, *, remove=False, **changes):
    data = policy.model_dump()
    data["premises"] = [p | changes if p["fact_type"] == name else p for p in data["premises"]
                        if not (remove and p["fact_type"] == name)]
    return PolicyConfiguration.model_validate(data)


def evidence(snapshot, catalog, policy, bindings):
    return validate_evidence(snapshot, catalog=catalog, policy=policy, bindings=bindings, reference_time=NOW)


def mixed_context(permission=True):
    from hawaii_activity_forecaster.harness.synthetic import DispatchBinding, FindingBinding
    from specialist_samples import finding
    snapshot, catalog, policy, bindings = context("SNORKELING")
    visibility = finding("OCEAN", finding_id="run-visibility", source_id="HWT_VISIBILITY", finding_type="REPORT")
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {"ocean_findings": snapshot.ocean_findings + [visibility]})
    data = policy.model_dump()
    data["evidence_rules"].append(dict(rule_id="visibility", category="UNDERWATER_VISIBILITY", source_fixture_id="visibility",
                                       finding_id="template-visibility", temporal_rule="DECLARED_REPORT_WINDOW", beach_ids=[BEACH]))
    data["premises"].append(dict(premise_id="poor-visibility", beach_id=BEACH, activity="SNORKELING", time_window=WINDOW,
                                 fact_type="NON_DISQUALIFYING_LIMITATION_PRESENT", value=True, limitation_code="SYNTHETIC_POOR_VISIBILITY",
                                 finding_refs=[dict(source_fixture_id="visibility", finding_id="template-visibility")],
                                 catalog_field_refs=[], rationale="Reviewed fictional non-disqualifying visibility limitation"))
    if permission:
        data["mixed_permissions"].append(dict(activity="SNORKELING", limitation_code="SYNTHETIC_POOR_VISIBILITY",
                                              requirement_ids=["HM-VIS-003"], disclosure="Synthetic poor visibility must be disclosed"))
    bindings += (DispatchBinding(1, "visibility", 1, snapshot.investigation_id, "visibility-call", "visibility",
                                 (FindingBinding("template-visibility", "run-visibility"),)),)
    return snapshot, catalog, PolicyConfiguration.model_validate(data), bindings
