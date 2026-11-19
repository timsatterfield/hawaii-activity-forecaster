"""Load local synthetic inputs without executing scenarios or evaluating safety."""

from dataclasses import dataclass
import json
import math
from pathlib import Path, PurePosixPath
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from hawaii_activity_forecaster.models import BeachCatalog, EnvironmentalToolResponse
from hawaii_activity_forecaster.models.enums import AgentType
from hawaii_activity_forecaster.models.permissions import (
    OCEAN_SOURCES as _OCEAN_SOURCES, WEATHER_SOURCES as _WEATHER_SOURCES,
)

from .manifest import FixtureManifest


class FixtureLoadError(ValueError):
    """Invalid fixture input, distinct from an application or environmental failure."""


class UnsupportedFixtureVersionError(FixtureLoadError):
    """The input package declares a version unsupported by this loader."""


@dataclass(frozen=True)
class FixtureInputs:
    manifest: FixtureManifest
    catalog: BeachCatalog
    source_responses: dict[str, EnvironmentalToolResponse]


# Versions describe this initial input format, not a completed scenario harness.
_SUPPORTED_VERSIONS = {
    "fixture_format_version": "1.0.0",
    "fixture_package_version": "1.0.0",
    "schema_version": "0.1",  # 03-data-schemas.md
    "policy_version": "0.2",  # 05-safety-policies.md, reference only
}
_MODEL = TypeVar("_MODEL", bound=BaseModel)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON number")
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("nonstandard JSON constant")


def _read_json(path: Path) -> object:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object,
            parse_float=_finite_float, parse_constant=_reject_constant,
        )
    except OSError:
        raise FixtureLoadError("Cannot read a required fixture file.") from None
    except (ValueError, UnicodeError, RecursionError):
        raise FixtureLoadError("Invalid fixture JSON (including duplicate keys or nonfinite numbers).") from None


def _validated(model: type[_MODEL], data: object, label: str) -> _MODEL:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        fields = ", ".join(".".join(map(str, item["loc"])) or "root"
                           for item in error.errors(include_input=False, include_context=False, include_url=False))
        raise FixtureLoadError(f"Invalid {label} schema at: {fields}.") from None


def _input_path(root: Path, reference: str, area: str) -> Path:
    """Resolve a registered JSON input within its own approved package subtree."""
    relative = PurePosixPath(reference)
    if (relative.is_absolute() or ".." in relative.parts or "\\" in reference
            or "\x00" in reference or relative.suffix != ".json"):
        raise FixtureLoadError("Fixture references must be relative JSON paths inside their input area.")
    expected_area = root / area
    try:
        path = (root / relative).resolve()
    except (OSError, ValueError, RuntimeError):
        raise FixtureLoadError("Cannot resolve fixture reference.") from None
    if not path.is_relative_to(expected_area):
        raise FixtureLoadError("Fixture reference escapes its input area.")
    return path


def load_fixture_inputs(root: str | Path) -> FixtureInputs:
    """Preflight a manifest, catalog, and declared source responses, in that order.

    No implicit discovery, evaluator assertions, policy/behavior loading, network
    operations, runtime ID replacement, evidence acceptance, or safety decisions.
    """
    try:
        package_root = Path(root).resolve()
    except (OSError, ValueError, RuntimeError):
        raise FixtureLoadError("Cannot resolve fixture package root.") from None
    manifest_path = _input_path(package_root, "manifest.json", "")
    manifest = _validated(FixtureManifest, _read_json(manifest_path), "manifest")
    for field, supported in _SUPPORTED_VERSIONS.items():
        if getattr(manifest, field) != supported:
            raise UnsupportedFixtureVersionError(f"Unsupported fixture version: {field}.")

    catalog_path = _input_path(package_root, manifest.catalog_fixture, "catalogs")
    catalog = _validated(BeachCatalog, _read_json(catalog_path), "catalog")
    beach_ids = {beach.beach_id for beach in catalog.root}
    responses: dict[str, EnvironmentalToolResponse] = {}
    finding_ids: set[str] = set()
    call_ids: set[str] = set()
    for entry in manifest.source_fixtures:
        authorized = _WEATHER_SOURCES if entry.agent_type == AgentType.WEATHER else _OCEAN_SOURCES
        if entry.source_id not in authorized:
            raise FixtureLoadError("Source fixture uses an unauthorized specialist/source pairing.")
        area = f"sources/{entry.agent_type.value.lower()}"
        path = _input_path(package_root, entry.path, area)
        response = _validated(EnvironmentalToolResponse, _read_json(path), "source response")
        if response.source_id != entry.source_id:
            raise FixtureLoadError("Source response does not match the manifest source.")
        if response.tool_call_id in call_ids:
            raise FixtureLoadError("Duplicate tool call ID across source fixtures.")
        call_ids.add(response.tool_call_id)
        for finding in response.findings:
            if finding.finding_id in finding_ids:
                raise FixtureLoadError("Duplicate finding ID across source fixtures.")
            finding_ids.add(finding.finding_id)
            if finding.agent_type != entry.agent_type:
                raise FixtureLoadError("Finding specialist domain does not match its source fixture.")
            if finding.beach_id is not None and finding.beach_id not in beach_ids:
                raise FixtureLoadError("Finding references a beach absent from the fixture catalog.")
        responses[entry.fixture_id] = response
    return FixtureInputs(manifest=manifest, catalog=catalog, source_responses=responses)
