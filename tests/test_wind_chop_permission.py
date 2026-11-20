"""Owner-reviewed swimming wind-chop MIXED permission and the SC-002 request phrasing."""

import pytest
from pydantic import ValidationError

from hawaii_activity_forecaster.harness.policy import MixedPermission, Premise
from hawaii_activity_forecaster.interpretation.clauses import analyze
from interpretation_samples import context

W = {"start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"}


def permission(**change):
    return dict(activity="SWIMMING", limitation_code="SYNTHETIC_WIND_CHOP", requirement_ids=["HM-T05"],
                disclosure="SYNTHETIC chop disclosure") | change


def test_chop_permission_requires_swimming_and_its_basis():
    assert MixedPermission.model_validate(permission())
    for change in (dict(activity="SNORKELING"), dict(requirement_ids=["HM-VIS-003"]), dict(activity="SUP")):
        with pytest.raises(ValidationError):
            MixedPermission.model_validate(permission(**change))
    assert MixedPermission.model_validate(permission(activity="SNORKELING", limitation_code="SYNTHETIC_POOR_VISIBILITY",
                                                     requirement_ids=["HM-VIS-003"]))
    with pytest.raises(ValidationError):  # Visibility stays snorkeling-only.
        MixedPermission.model_validate(permission(limitation_code="SYNTHETIC_POOR_VISIBILITY", requirement_ids=["HM-VIS-003"]))


@pytest.mark.parametrize("activity,code,valid", [
    ("SWIMMING", "SYNTHETIC_WIND_CHOP", True), ("SNORKELING", "SYNTHETIC_POOR_VISIBILITY", True),
    ("SNORKELING", "SYNTHETIC_WIND_CHOP", False), ("SUP", "SYNTHETIC_WIND_CHOP", False),
    ("SWIMMING", "SYNTHETIC_POOR_VISIBILITY", False),
])
def test_limitation_premises_only_for_reviewed_activity_code_pairs(activity, code, valid):
    data = dict(premise_id="p", beach_id="TEST_BEACH_A", activity=activity, time_window=W,
                fact_type="NON_DISQUALIFYING_LIMITATION_PRESENT", value=True, limitation_code=code,
                finding_refs=[dict(source_fixture_id="s", finding_id="f")], catalog_field_refs=[], rationale="SYNTHETIC")
    if valid:
        assert Premise.model_validate(data)
    else:
        with pytest.raises(ValidationError):
            Premise.model_validate(data)


@pytest.mark.parametrize("text,area,questions", [
    ("Where should I swim tomorrow morning? I'd prefer somewhere near Kihei.", "Kihei", 0),
    ("Where should I swim tomorrow morning? I prefer somewhere near Kihei.", "Kihei", 0),
    ("Where should I swim tomorrow morning? I'd prefer near Kihei.", "Kihei", 0),
    ("Where should I swim tomorrow morning? I'd prefer somewhere near Atlantis.", None, 0),
])
def test_prefer_somewhere_near_is_a_soft_area_preference(text, area, questions):
    meaning = analyze(context(text), None)
    assert meaning.changes.get("preferred_area") == area and len(meaning.questions) == questions
    if area is None:  # An unknown area stays uninterpreted; no nearby relationship is inferred.
        assert meaning.changes["soft_preferences"][0]["kind"] == "UNINTERPRETED"
    else:
        start, end = next(o.span for k, o in meaning.origins.items() if k[0] == "preferred_area")
        assert text[start:end].endswith(f"near {area}")
