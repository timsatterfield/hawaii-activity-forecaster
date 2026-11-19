"""Shared trusted catalog attribution and approved location-constraint rules."""

from datetime import timedelta, timezone

from hawaii_activity_forecaster.models import BeachCatalog

HST = timezone(timedelta(hours=-10))
CORE_FIELDS = frozenset({"beach_id", "name", "region", "locality", "latitude", "longitude", "supported_activities", "lifeguard_status"})
MATERIAL_FIELDS = frozenset({"shoreline_orientation", "coastline_exposure", "shore_type", "entry_characteristics",
                            "reef_presence", "known_hazards", "activity_notes", "access_notes", "location_notes",
                            "reef_notes", "lifeguard_notes", "aliases"})


def location_key(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def catalog_provenance_reasons(beach, reference_time) -> tuple[str, ...]:
    """Existing BC checks, without treating activity mismatch as bad provenance."""
    if beach is None:
        return ("CATALOG_RECORD_MISSING",)
    reasons = []
    local_date = reference_time.astimezone(HST).date()
    if beach.catalog_status != "VERIFIED":
        reasons.append("CATALOG_NOT_VERIFIED")
    if beach.last_verified > local_date:
        reasons.append("CATALOG_VERIFICATION_IN_FUTURE")
    required = CORE_FIELDS | {name for name in MATERIAL_FIELDS if getattr(beach, name) not in (None, [], "")}
    supported = {name for source in beach.sources if source.accessed_at <= local_date and source.url.strip()
                 for name in source.supports_fields}
    if not required <= supported:
        reasons.append("CATALOG_ATTRIBUTE_PROVENANCE_MISSING")
    return tuple(sorted(reasons))


def resolve_location(catalog: BeachCatalog, text: str, scopes=("REGION", "LOCALITY", "BEACH")) -> tuple[tuple[str, str], ...]:
    """Exact catalog spelling equivalence only; ambiguous matches remain distinct."""
    key = location_key(text)
    matches = set()
    for beach in catalog.root:
        if "REGION" in scopes and location_key(text.replace("_", " ")) == location_key(beach.region.value.replace("_", " ")):
            matches.add(("REGION", beach.region.value))
        if "LOCALITY" in scopes and key == location_key(beach.locality):
            matches.add(("LOCALITY", beach.locality))
        if "BEACH" in scopes and any(key == location_key(name) for name in (beach.name, *(beach.aliases or ()))):
            matches.add(("BEACH", beach.beach_id))
    return tuple(sorted(matches))


def location_descriptor(value) -> bool:
    return (isinstance(value, dict) and set(value) == {"kind", "scope", "value"}
            and value["kind"] == "LOCATION_RESTRICTION" and isinstance(value["scope"], str)
            and value["scope"] in {"REGION", "LOCALITY", "BEACH"}
            and isinstance(value["value"], str) and bool(value["value"].strip()))


def location_match(descriptor, beach) -> bool:
    return descriptor["value"] == {"REGION": beach.region.value, "LOCALITY": beach.locality, "BEACH": beach.beach_id}[descriptor["scope"]]


def known_location(descriptor, catalog: BeachCatalog) -> bool:
    return location_descriptor(descriptor) and any(location_match(descriptor, beach) for beach in catalog.root)


def check_location_constraint(descriptor, beach, catalog: BeachCatalog, reference_time) -> str:
    """Independent PASS/FAIL/UNKNOWN; unrecognized legacy payloads stay UNKNOWN."""
    if not known_location(descriptor, catalog) or catalog_provenance_reasons(beach, reference_time):
        return "UNKNOWN"
    return "PASS" if location_match(descriptor, beach) else "FAIL"
