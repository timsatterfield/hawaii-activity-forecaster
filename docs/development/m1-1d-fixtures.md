# M1.1-D synthetic input loading and validation

This development note describes implementation choices for review. It does not
change the approved fixture design, logical contracts, safety rules, or scenario
requirements. The increment establishes independently loadable catalog and source
inputs. It does not complete the twelve-scenario evaluation harness.

## Source of truth and scope

The implementation follows:

- `m1-synthetic-fixture-design.md` §§4–8/18 and approved FX-OD-001 through FX-OD-012.
- `06-test-acceptance.md` §16.1 for the five fictional beach identities, regions,
  localities, activity support, common reference time and requested time window.
- `03-data-schemas.md` §§2/3 and `04-agent-tool-contracts.md` §§7/13 for catalog,
  response and finding structures and specialist/source permissions.

Eight source examples exercise success, partial/unavailable retrieval, an advisory,
regional surf versus swell, an offshore observation, and a prior-date report.
They are input examples and do not establish complete safety evidence or expected
recommendations. The independent loader tests check their structural contents.

## Public API and file organization

```python
from hawaii_activity_forecaster.fixtures import (
    FixtureLoadError, UnsupportedFixtureVersionError, load_fixture_inputs,
)

try:
    inputs = load_fixture_inputs("fixtures")
except FixtureLoadError:
    # Report invalid input, not an agent failure or hazardous ocean conditions.
    raise
```

`FixtureInputs` returns a typed manifest, `BeachCatalog`, and mapping from fixture
IDs to `EnvironmentalToolResponse` records. The function reads only explicit
paths, with no default package discovery. The fixture files live at repository
root; they are not bundled into an installed wheel. Callers must supply a local
package root when using the loader outside the checkout.

## Manifest format and version choices

The approved design defines required metadata but does not mandate manifest field
names for input references. This initial physical format uses:

| Field | Meaning |
|---|---|
| `fixture_format_version` | `1.0.0`, this catalog/source input envelope |
| `fixture_package_version` | `1.0.0`, the approved initial fixture package identifier |
| `schema_version` | `0.1`, logical Data Schemas specification version |
| `policy_version` | `0.2`, referenced Safety Policies specification version only |
| `synthetic` | Required JSON boolean `true` |
| `reference_time` | Explicit fixed timestamp with timezone |
| `target_time_window` | Approved `{start, end}` representation |
| `catalog_fixture` | Catalog JSON path relative to the package root |
| `source_fixtures` | Source metadata records with `fixture_id`, `path`, `agent_type`, `source_id` |

Only the listed version tuple is supported. Unknown versions are rejected before
catalog/source reads. The policy version does not imply the presence of a synthetic
policy configuration or executable evaluator. Tool response shape follows Agent
and Tool Contracts v0.2; that document version is distinct from Data Schemas v0.1.
Changes to this input envelope or its supported versions require explicit review.
Future scenario, behavior, assertion and policy envelopes are not silently inferred
from these fields.

The catalog remains a JSON array of `BeachRecord` values as selected in M1.1-B.
Source payloads contain only the existing application contract fields. Synthetic
labels live in names, notes, source references, and declared package metadata;
no synthetic-control fields are inserted into application tool responses.

## Preflight validation

Loading occurs in order: manifest/schema validation, version checks, catalog
validation, then each declared source response and cross-file relationships.
It verifies:

- UTF-8 JSON syntax, rejecting duplicate object keys, nonstandard nonfinite
  constants, and floating-point overflow rather than silently accepting ambiguity.
- Required manifest fields, explicit synthetic marker, timezone-aware reference
  time, valid requested window, and unique source fixture IDs/paths.
- Existing catalog/response contracts, including unique catalog IDs, enums,
  coordinate ranges, required fields, aware timestamps and ordered periods.
- Provider IDs and Weather/Ocean domain permissions from the explicit registry.
- Agreement between source metadata, response provider, and finding domain.
- Finding beach references resolving to the loaded catalog when a beach is named.
- Unique tool call IDs and finding IDs across declared files.

Input references are relative POSIX-style `.json` paths within `catalogs/` or the
matching `sources/weather/` or `sources/ocean/` directory. Absolute paths, parent
traversal, backslashes and null bytes are rejected. Resolved paths, including
symlink targets, must remain in their own input subtree. This also prevents an
ordinary source reference from pointing into an evaluator assertion directory.
This check is input validation, not an OS sandbox against concurrent filesystem
modification by another process.

Only the registered input files are read; extra files are ignored. In particular,
there is no expected-result field, scenario traversal, assertion loader, evaluator
output, generated eligibility, or result object in the returned inputs. Extra
manifest fields such as `expected_results` are rejected. Expected-result handling
must eventually be implemented in the independent evaluator, preserving FX-009.

`FixtureLoadError` identifies fixture read/format/schema/reference failures.
`UnsupportedFixtureVersionError` is a specialized fixture error. These are not
application contract-execution, evidence-validation, policy or orchestration errors.
Validation messages identify the input layer and invalid fields without echoing
raw provider text or fabricating a runtime trace.

## Boundaries and remaining decisions

Preflight preserves `PENDING`, missing information, original timestamps, scope,
and IDs. It does not reject a well-formed old report as a freshness-policy decision,
relabel an offshore finding, rewrite an investigation ID, filter unverified catalog
records, or imply successful source retrieval establishes sufficient evidence.

No TestScenario instances are marked ACTIVE and no SC-001 through SC-012 scenarios
are claimed as passing. No arbitrary numeric safety thresholds, behavioral delay
scheduler, retries, fallback dispatch, controlled model adapter, or actual tool
execution are implemented. Intentional malformed/duplicate delivery fixtures will
need a separate behavior harness; ordinary declared input records must validate.

The approved design §22 still leaves these definitions open:

1. Concrete synthetic-policy facts/configuration schema and independent expected
   assertions for mandatory evidence, including complete activity evidence profiles.
2. Behavior-harness schema, assertion operators/selectors, and evaluator validation.
3. Provider/fixture measurement category mappings and cross-investigation reuse.
4. Controlled model adapter behavior and actual provider/model activation.

Full scenario loading and execution must wait for those definitions rather than
claim arbitrary JSON objects constitute validated policy or evaluator inputs.
The five-beach catalog and typed source inputs can now be validated independently;
the broader M1.1/M1 acceptance gates remain subject to these open decisions and
future runtime work. Resolve the scenario harness definitions before claiming
complete synthetic acceptance readiness, then proceed to M1.2's bounded graph.

## Verification

```bash
uv sync --locked
uv run --locked pytest tests/test_fixtures.py
uv run --locked pytest
```

Tests independently assert the five-beach inventory, source statuses, source
attribution, fixed times, original measurements, missing advisory information,
version rejection, path containment, malformed inputs, duplicate/mismatched IDs,
and exclusion of evaluator-only files from application input loading. They use
local temporary copies for invalid cases and require no environmental or model
provider access. Approved specifications, configuration, dependencies, workflow
files and the information CLI remain unchanged.
