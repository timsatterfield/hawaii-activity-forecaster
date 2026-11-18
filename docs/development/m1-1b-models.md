# M1.1-B Pydantic models

This implementation note describes code for review. It does not revise the
approved requirements or architecture. The separate M1.1-B implementation request
authorizes this increment despite the older planning-only notices.

## Coverage

| Module under `src/hawaii_activity_forecaster/models/` | Specification |
|---|---|
| `common.py` | 03 §1.3; approved FX-OD-001 through FX-OD-006 |
| `catalog.py` | 03 §2: BeachRecord, SourceReference, BeachCatalog |
| `evidence.py` | 03 §3: EnvironmentalFinding, Measurement, AdvisoryReference |
| `assessment.py` | 03 §4: CandidateAssessment and constraint/preference/policy results |
| `investigation.py` | 03 §5: InvestigationState, NormalizedRequest, EvidenceRequest, EvidenceIssue |
| `result.py` | 03 §6: RecommendationResult and Recommendation |
| `trace.py` | 03 §7: InvestigationTrace and TraceEvent |
| `contracts.py` | 04 §§3/4/7: specialist/tool requests and responses, requirements, gaps, errors |
| `enums.py` | Enumerations in 03/04, including the authoritative 03 §7.4 event list |

Required fields have no default. Optional/conditional fields can be omitted and
use `None` internally; use `model_dump_json(exclude_none=True)` to omit them from
serialized records. All declared models reject extra fields. Primitive strings,
booleans, and counters reject misleading type coercions. Timestamp inputs require
an aware datetime or an ISO date/time string with explicit timezone information;
numeric Unix timestamps are rejected. Dates use `YYYY-MM-DD`.

Time ranges use `{start, end}` with positive duration and start-inclusive,
end-exclusive semantics. Measurement ranges use `{min, max}`. Numeric and
categorical values retain their reported type, unit, and convention. No surf/swell
conversion or condition classification occurs. Decimal coordinates are bounded
by valid latitude/longitude ranges; Pydantic serializes these as decimal strings.

## Validation boundaries

Construction checks structure and locally decidable consistency, including:

- Unique catalog IDs, valid enums, coordinates, timestamps, and ordered periods.
- Source identity for successful/partial findings, required beach ID for BEACH
  coverage, and no environmental payload from unavailable/failed retrievals.
- Independent retrieval and evidence validation statuses.
- Contradictory assessment fields: rejected positive evidence, insufficient evidence
  on ELIGIBLE assessments, unresolved hard constraints, and exclusion requirements.
- Terminal investigation status/outcome agreement and specialist finding domains.
- One to three recommendations for RECOMMENDATIONS; empty recommendations for
  abstention/error; required outcome-specific explanations.
- Unique trace event IDs, increasing sequence numbers, parent trace IDs, and
  agreement with any supplied terminal trace status.
- Specialist response chronology, nested finding identities, explicit gaps/errors
  for partial/error responses, and nonnegative tool durations.

Model construction is not a certificate of eligibility or evidence validity.
References to records outside a model, originating request/response correlations,
source permissions, schema-version compatibility, geographic applicability,
source-specific freshness/units, hazard thresholds, actual policy evaluation,
MIXED permission, grounding, and evidence-supported recommendation windows require
later trusted validators. Trace event details are JSON objects; event-specific
detail requirements, privacy sanitization, causal references, and trace completeness
also require the future trace validator. No workflow, safety evaluator, trace writer,
fixture loader, model provider, or provider adapter is implemented here.

Models represent snapshots and disable attribute reassignment. Nested lists/maps
are not deeply immutable. Runtime mutation/merge enforcement, append-only storage,
terminal-state transitions, and session revision handling remain future work;
call `model_validate` on serialized data when validating a revised snapshot.
Pydantic's `model_construct`/`model_copy(update=...)` bypass validation and must not
be used for untrusted updates.

`retry_count` remains an investigation aggregate, while `max_retries` applies per
failed original invocation. These values are deliberately not compared as a
single aggregate retry budget. Dispatch counting and concurrency guards remain
outside the models.

## Open details and implementation choices for review

The approved fixture design resolves the older mapping's open time/range formats.
Other underspecified types are preserved without inventing field vocabularies:

- `Constraint`, `Preference`, `Action`, and `ErrorReference` have no field inventory.
  Their collections accept JSON objects pending approved definitions.
- Shoreline orientation/type vocabularies and structured beach attributes remain
  open. Strings/JSON objects preserve supplied data without claiming vocabulary
  verification or geographic verification.
- Evidence categories and error codes described as String/Enum remain nonempty
  strings. Categorical measurement vocabulary still needs fixture/provider rules.
- Tool geographic scopes, tool error objects, and trace details remain JSON objects.
  Their semantic validation is deferred rather than inferred from framework defaults.
- `BeachCatalog` is a root JSON array of `BeachRecord` values, avoiding invented
  wrapper/version fields. Investigation field groups are flattened, with the
  normalized request fields reused through inheritance. These are physical Python
  organization choices, not new logical contracts.
- No fixed supported schema-version list or request-revision-to-assessment storage
  is invented. Cross-investigation reuse reference storage remains open; original
  finding investigation IDs are preserved and never rewritten.

These open details limit semantic validation and should be resolved before the
corresponding runtime features are implemented. No approved specification was edited.

## Verification

`tests/test_models.py` contains small fictional in-memory payloads for structural
checks, not the twelve-scenario fixture package. Tests cover JSON round trips,
missing/null required fields, unknown fields/enums, invalid values, record
contradictions, and the separation of retrieval success from evidence acceptance.

```bash
uv sync --locked
uv run --locked pytest
```
