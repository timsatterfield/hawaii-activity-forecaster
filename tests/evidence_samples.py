"""Independent evidence examples; no safety outcomes or scenario assertions."""

from hawaii_activity_forecaster.harness.policy import Category, PolicyConfiguration
from hawaii_activity_forecaster.harness.synthetic import DispatchBinding, FindingBinding
from hawaii_activity_forecaster.models import InvestigationState
from specialist_samples import BEACH, WINDOW, catalog, finding, state


def sample():
    snapshot = state()
    fields = dict(
        wind=finding(finding_id="run-wind"),
        marine=finding("OCEAN", finding_id="run-marine", measurements=[{
            "measurement_type": "SURF_HEIGHT", "value": 2, "unit": "ft", "measurement_convention": "FACE",
        }]),
        alerts=finding(finding_id="run-alerts", source_id="NWS_ALERTS", finding_type="ADVISORY", advisories=[]),
        water=finding("OCEAN", finding_id="run-water", source_id="HI_DOH_CWB", finding_type="ADVISORY",
                      coverage_type="BEACH", beach_id=BEACH, advisories=[]),
    )
    snapshot = InvestigationState.model_validate(snapshot.model_dump() | {
        "weather_findings": [fields["wind"], fields["alerts"]], "ocean_findings": [fields["water"], fields["marine"]],
    })
    mapping = {
        Category.WIND_CONDITIONS: "wind", Category.SURF_WAVE_CONDITIONS: "marine",
        Category.CURRENTS_PERSISTENT_HAZARDS: "marine", Category.OFFICIAL_ADVISORIES: "alerts",
        Category.WATER_QUALITY_ADVISORY_CHECK: "water",
    }
    profiles = []
    for activity in ("SWIMMING", "SNORKELING", "SUP"):
        mandatory = set(Category) - {Category.UNDERWATER_VISIBILITY, Category.WIND_CONDITIONS}
        if activity == "SUP":
            mandatory.add(Category.WIND_CONDITIONS)
        profiles.append(dict(activity=activity, mandatory=sorted(mandatory),
                             relevant=[Category.WIND_CONDITIONS] if activity != "SUP" else [], optional=[Category.UNDERWATER_VISIBILITY]))
    rules = [dict(rule_id="rule-" + category, category=category, source_fixture_id=name,
                  finding_id="template-" + name, temporal_rule="COVERS_TARGET_WINDOW", beach_ids=[BEACH])
             for category, name in mapping.items()]
    premises = [dict(
        premise_id="check-" + name, beach_id=BEACH, activity=activity, time_window=WINDOW,
        fact_type=fact, value=True, finding_refs=[dict(source_fixture_id=name, finding_id="template-" + name)],
        catalog_field_refs=[], rationale="Explicit fictional complete-check premise, not a safety verdict",
    ) | {"premise_id": f"check-{name}-{activity}"}
        for activity in ("SWIMMING", "SNORKELING", "SUP")
        for name, fact in (("alerts", "OFFICIAL_ADVISORY_CHECK_COMPLETE"), ("water", "WATER_CONTACT_ADVISORY_CHECK_COMPLETE"))]
    policy = PolicyConfiguration(harness_contract_version="1.0.0", policy_version="0.2",
                                 policy_configuration_version="synthetic-policy-1.0.0", synthetic=True,
                                 evidence_profiles=profiles, evidence_rules=rules, premises=premises, mixed_permissions=[])
    bindings = tuple(DispatchBinding(1, name + "-operation", 1, snapshot.investigation_id,
                                     name + "-call", name, (FindingBinding("template-" + name, fields[name].finding_id),))
                     for name in fields)
    return snapshot, catalog(), policy, bindings


def change_finding(snapshot, finding_id, **changes):
    data = snapshot.model_dump()
    for domain in ("weather_findings", "ocean_findings"):
        data[domain] = [item | changes if item["finding_id"] == finding_id else item for item in data[domain]]
    return InvestigationState.model_validate(data)
