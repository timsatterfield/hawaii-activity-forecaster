"""Approved synthetic premises and evidence profiles; no policy evaluation."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, StrictBool, model_validator

from hawaii_activity_forecaster.models.common import ContractModel, Text, TimeRange, unique
from hawaii_activity_forecaster.models.enums import Activity, SourceId

Version = Literal["1.0.0"]


class Category(StrEnum):
    OFFICIAL_ADVISORIES = "OFFICIAL_ADVISORIES"
    SURF_WAVE_CONDITIONS = "SURF_WAVE_CONDITIONS"
    WIND_CONDITIONS = "WIND_CONDITIONS"
    CURRENTS_PERSISTENT_HAZARDS = "CURRENTS_PERSISTENT_HAZARDS"
    WATER_QUALITY_ADVISORY_CHECK = "WATER_QUALITY_ADVISORY_CHECK"
    VERIFIED_BEACH_CHARACTERISTICS = "VERIFIED_BEACH_CHARACTERISTICS"
    UNDERWATER_VISIBILITY = "UNDERWATER_VISIBILITY"


class FactType(StrEnum):
    OFFICIAL_ADVISORY_CHECK_COMPLETE = "OFFICIAL_ADVISORY_CHECK_COMPLETE"
    WATER_CONTACT_ADVISORY_CHECK_COMPLETE = "WATER_CONTACT_ADVISORY_CHECK_COMPLETE"
    WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT = "WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT"
    DISQUALIFYING_SURF_PRESENT = "DISQUALIFYING_SURF_PRESENT"
    DANGEROUS_CURRENT_PRESENT = "DANGEROUS_CURRENT_PRESENT"
    DISQUALIFYING_WEATHER_PRESENT = "DISQUALIFYING_WEATHER_PRESENT"
    DANGEROUS_OFFSHORE_WIND_PRESENT = "DANGEROUS_OFFSHORE_WIND_PRESENT"
    DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT = "DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT"
    MATERIAL_SAFETY_CONFLICT_PRESENT = "MATERIAL_SAFETY_CONFLICT_PRESENT"
    ACTIVITY_SUPPORTING_CONDITIONS_PRESENT = "ACTIVITY_SUPPORTING_CONDITIONS_PRESENT"
    NON_DISQUALIFYING_LIMITATION_PRESENT = "NON_DISQUALIFYING_LIMITATION_PRESENT"


class EvidenceProfile(ContractModel):
    activity: Activity
    mandatory: list[Category]
    relevant: list[Category]
    optional: list[Category]

    @model_validator(mode="after")
    def matrix(self) -> Self:
        categories = self.mandatory + self.relevant + self.optional
        unique(categories, "profile categories")
        if set(categories) != set(Category):
            raise ValueError("profile must partition all seven evidence categories")
        required = set(Category) - {Category.WIND_CONDITIONS, Category.UNDERWATER_VISIBILITY}
        if self.activity == Activity.SUP:
            required.add(Category.WIND_CONDITIONS)
        if not required <= set(self.mandatory):
            raise ValueError("profile cannot weaken mandatory activity evidence")
        if Category.UNDERWATER_VISIBILITY not in self.optional:
            raise ValueError("visibility belongs in optional under the approved evidence matrix")
        if self.activity != Activity.SUP and Category.WIND_CONDITIONS not in self.relevant:
            raise ValueError("wind belongs in relevant for swimming/snorkeling; hard constraints are separate")
        return self


class FindingRef(ContractModel):
    source_fixture_id: Text
    finding_id: Text


class CatalogFieldRef(ContractModel):
    beach_id: Text
    field: Text


class EvidenceRule(ContractModel):
    rule_id: Text
    category: Category
    source_fixture_id: Text
    finding_id: Text
    temporal_rule: Literal["COVERS_TARGET_WINDOW", "DECLARED_REPORT_WINDOW", "CONTEXT_ONLY"]
    beach_ids: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def structure(self) -> Self:
        unique(self.beach_ids, "rule beach IDs")
        if self.category == Category.VERIFIED_BEACH_CHARACTERISTICS:
            raise ValueError("catalog verification cannot be supplied by environmental findings")
        return self


class Premise(ContractModel):
    premise_id: Text
    beach_id: Text
    activity: Activity
    time_window: TimeRange
    fact_type: FactType
    value: StrictBool
    finding_refs: list[FindingRef]
    catalog_field_refs: list[CatalogFieldRef]
    rationale: Text
    limitation_code: Literal["SYNTHETIC_POOR_VISIBILITY"] | None = None

    @model_validator(mode="after")
    def structure(self) -> Self:
        if not self.finding_refs and not self.catalog_field_refs:
            raise ValueError("premise requires explicit support")
        if not self.finding_refs and self.fact_type != FactType.DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT:
            raise ValueError("changing environmental premises require finding support")
        limitation = self.fact_type == FactType.NON_DISQUALIFYING_LIMITATION_PRESENT
        if limitation != (self.limitation_code is not None):
            raise ValueError("only limitation premises require/permit limitation_code")
        if limitation and self.activity != Activity.SNORKELING:
            raise ValueError("the initial reviewed limitation code is scoped to snorkeling")
        if any(ref.beach_id != self.beach_id for ref in self.catalog_field_refs):
            raise ValueError("catalog support must name the same candidate")
        unique([(ref.source_fixture_id, ref.finding_id) for ref in self.finding_refs], "premise finding refs")
        return self


class MixedPermission(ContractModel):
    activity: Literal[Activity.SNORKELING]
    limitation_code: Literal["SYNTHETIC_POOR_VISIBILITY"]
    requirement_ids: list[Text] = Field(min_length=1)
    disclosure: Text

    @model_validator(mode="after")
    def basis(self) -> Self:
        if "HM-VIS-003" not in self.requirement_ids:
            raise ValueError("visibility permission must reference HM-VIS-003")
        return self


class PolicyConfiguration(ContractModel):
    harness_contract_version: Version
    policy_version: Literal["0.2"]
    policy_configuration_version: Literal["synthetic-policy-1.0.0"]
    synthetic: StrictBool
    evidence_profiles: list[EvidenceProfile] = Field(min_length=1)
    evidence_rules: list[EvidenceRule]
    premises: list[Premise]
    mixed_permissions: list[MixedPermission]

    @model_validator(mode="after")
    def structure(self) -> Self:
        if not self.synthetic:
            raise ValueError("policy inputs must be explicitly synthetic")
        unique([profile.activity for profile in self.evidence_profiles], "activity profiles")
        unique([rule.rule_id for rule in self.evidence_rules], "evidence rule IDs")
        unique([premise.premise_id for premise in self.premises], "premise IDs")
        unique([(p.beach_id, p.activity, p.time_window.start, p.time_window.end, p.fact_type, p.limitation_code)
                for p in self.premises], "premise scope/type")
        unique([(p.activity, p.limitation_code) for p in self.mixed_permissions], "MIXED permissions")
        return self


CATEGORY_SOURCES = {
    Category.OFFICIAL_ADVISORIES: {SourceId.NWS_ALERTS, SourceId.NWS_MARINE},
    Category.SURF_WAVE_CONDITIONS: {SourceId.NWS_MARINE, SourceId.HWT_SURF, SourceId.NDBC},
    Category.WIND_CONDITIONS: {SourceId.NWS_WEATHER, SourceId.HWT_WIND, SourceId.NWS_MARINE, SourceId.HWT_NARRATIVE},
    Category.CURRENTS_PERSISTENT_HAZARDS: {SourceId.NWS_MARINE, SourceId.SNORKEL_STORE},
    Category.WATER_QUALITY_ADVISORY_CHECK: {SourceId.HI_DOH_CWB},
    Category.UNDERWATER_VISIBILITY: {SourceId.SNORKEL_STORE, SourceId.HWT_VISIBILITY},
}
