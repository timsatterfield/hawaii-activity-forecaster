# Synthetic input fixtures — M1.1-D

Every record here is fictional. Coordinates, locality relationships, source
responses, and advisory text do not represent real Maui locations or conditions.
`VERIFIED` means a record belongs to this synthetic catalog; it is not a claim of
public-source geographic verification. `example.invalid` references identify
fixture definitions and are never retrieved.

This is an initial input package, not a runnable acceptance-scenario package.
It contains:

- `manifest.json`: versions, fixed reference time/window, and declared input paths.
- `catalogs/synthetic-maui-v1.json`: the five fictional beaches from acceptance §16.1.
- `sources/weather/`: forecast, partial forecast, and unavailable response examples.
- `sources/ocean/`: surf/swell forecast, an advisory, unavailable advisory retrieval,
  offshore observation, and an old qualitative report.

The source files use the existing `EnvironmentalToolResponse` contract, including
required empty lists where appropriate. Finding timestamps, original coverage,
measurement meanings, units, conventions, source IDs, and synthetic investigation
IDs are preserved. Sources with environmental evidence begin `PENDING`; loading
never promotes them to accepted evidence. Missing advisory retrieval remains
missing information, not an assertion that no advisory exists.

The weather and ocean numerical values exercise parsing only; they establish no
favorable or hazardous threshold. The old report deliberately predates the requested
window, and the offshore observation deliberately has no beach-specific coverage.
The advisory exists in this fictional input but no policy evaluation is performed.
No source set is claimed to establish the complete mandatory evidence profile for
any activity.

For this package only, the fixed reference is `2026-11-16T09:00:00-10:00` and the
requested window is November 17, 2026, 08:00–11:00 HST. These are test constants,
not application defaults or current conditions.

```python
from hawaii_activity_forecaster.fixtures import load_fixture_inputs

inputs = load_fixture_inputs("fixtures")
catalog = inputs.catalog
forecast = inputs.source_responses["weather-forecast"]
```

Paths resolve relative to the explicitly supplied package root. Only declared
catalog/source files are read. The loader does not discover scenario assertions,
load policies/behavior scripts, access the network, write traces, or execute tools.
Tests in `tests/test_fixtures.py` independently assert structural expectations.

See [implementation notes](../docs/development/m1-1d-fixtures.md) for version
identifiers, manifest fields, validation boundaries, and remaining design decisions.

## Separate v2 scenario package

[scenario-pack-v1/](scenario-pack-v1/README.md) adds authored SC-004 and SC-010
inputs and independent assertions using the approved v2 harness format. It has
its own manifest and is loaded explicitly with `load_scenario()`; the parent v1
loader does not discover or merge it. Both cases remain blocked for execution.
The original v1 manifest/catalog/source JSON inputs are unchanged.
