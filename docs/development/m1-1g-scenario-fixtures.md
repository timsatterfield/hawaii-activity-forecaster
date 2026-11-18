# M1.1-G — SC-004 / SC-010 input and assertion authoring

This increment implements step 2 of the approved
[M1.1-E design](../implementation/m1-scenario-harness-contract-design.md): author
complete scoped synthetic inputs and independent assertion plans for SC-004 and
SC-010 using M1.1-F's existing v2 contracts. It does not implement graph execution,
specialist/tool adapters, evidence/safety/result evaluation, operator execution,
budget guards, tracing, or an LLM provider. Both definitions remain execution-blocked.

## Artifacts and reproducibility

`fixtures/scenario-pack-v1/` is isolated from the original v1 manifest and input
JSON. Its format/package versions are 2.0.0 / 1.1.0; logical schema/policy versions
are 0.1 / 0.2 and harness contract version is 1.0.0. The directory's “v1” means the
first authored scenario pack, not the manifest format. The five-beach catalog is
an exact copy of the original fictional catalog, preserving identities, activity
support, source references, verification dates and explicit synthetic labeling.

| Artifact | Purpose |
|---|---|
| manifest.json | Registers only SC-004/SC-010, their sources and version/clock metadata |
| scenarios/SC-004/scenario.json | Original advisory scenario request and input/oracle references |
| scenarios/SC-010/scenario.json | Original outage scenario request and input/oracle references |
| source_sets/ | Explicit Weather/Ocean response IDs selected by each scenario |
| sources/weather/, sources/ocean/ | 18 typed response templates with synthetic provenance |
| policies/ | Approved evidence profiles, declared applicability and explicit hypothetical premises |
| behaviors/ | Dispatch-matched source deliveries/failures; no Coordinator decision script |
| scenarios/*/expected.json | Independently authored 84 / 61 assertion definitions, evaluator only |

Reference time stays `2026-11-16T09:00:00-10:00`; the target window stays
`2026-11-17T08:00:00-10:00` through `2026-11-17T11:00:00-10:00`, as specified by
acceptance §16.1. These historic test constants do not use the host clock/timezone
or establish product defaults. Every returned finding begins PENDING; source and
advisory URLs use `example.invalid` and describe fictional input definitions.
No fabricated source timestamp, runtime event or result is generated at load time.

## Input completeness by candidate/category

| Category | SC-004 A/B | SC-004 C/D | SC-010 A–D |
|---|---|---|---|
| Official advisories | NWS_ALERTS check + explicit complete/negative-weather premises | Explicit unavailable retrieval | Available NWS_ALERTS check/premises |
| Surf/wave conditions | NWS_MARINE forecast + explicit hypothetical non-disqualifying surf | Explicit unavailable retrieval | Primary ERROR and failed HWT_SURF alternate |
| Currents/persistent hazards | Scoped synthetic marine premise plus attributed catalog | Explicit unavailable retrieval | Primary ERROR and failed SNORKEL_STORE alternate; catalog alone is insufficient |
| Water-contact check | A: applicable advisory; B: complete scoped no-listed-advisory check | Explicit unavailable retrieval | Available complete scoped checks; no applicable listed advisory |
| Verified beach characteristics | Fictional VERIFIED records, supported activity and attributed notes | Fictional catalog available; environmental gaps still unresolved | Fictional VERIFIED records; missing ocean evidence still prevents eligibility |
| Wind (relevant) | Scoped NWS_WEATHER forecast | Explicit unavailable retrieval | Available NWS_WEATHER forecast |
| Visibility (optional) | Explicit UNAVAILABLE | Explicit UNAVAILABLE | Explicit UNAVAILABLE |

Beach E supports SWIMMING only. It is retained as catalog data, not forced into
snorkeling eligibility or assigned favorable conditions. Unsupported activity
handling stays with trusted candidate validation.

SC-004 has separate boolean premises for completed checks, advisory presence,
weather/surf/current/persistent hazard classifications, conflict and positive
activity support. A's true advisory premise coexists with positive weather/surf
support: policy precedence must independently exclude A. B's empty advisory list
is supported by an explicit completed-check premise and descriptive scope/time;
it is not proof of safe water quality. Both candidates' missing visibility remains
a material limitation rather than an invented clear-water report.

SC-010 supplies only facts supported by its available weather/alert/water inputs
and catalog. It does not supply false DISQUALIFYING_SURF_PRESENT or
DANGEROUS_CURRENT_PRESENT, a favorable activity-support premise, or a default
no-conflict premise when marine evidence is missing. The evaluator's eventual
INSUFFICIENT/UNDETERMINED/NEEDS_INVESTIGATION outputs are never embedded in policy
or provider inputs.

No general numeric wind/surf/current/visibility threshold is defined. Marine
numeric values test measurement parsing and preserve SURF_HEIGHT versus
SWELL_HEIGHT; hypothetical current classification does not invent current-speed
measurements or convert regional forecasts into beach observations.

## Behavior and budget-boundary interpretation

SC-004 scripts five successful required source calls for A/B and one optional
unavailable visibility call; five additional C/D gap responses prevent implicit
favorable defaults if other candidates are explored. Scripts describe available
responses to authorized dispatches, not required traversal order.

SC-010 offers regional and four candidate-specific primary marine queries, each
with at most one retry. Their synthetic geographic scopes differ; these are
alternative inquiries, not aliases that may automatically reset a failed original
invocation's retry allowance. Surf/current alternatives use explicit approved
provider/category pairs. Errors use the approved synthetic SpecialistError shape,
retain source/call references, and report SOURCE_UNAVAILABLE rather than an
environmental hazard.

There are 16 potential invocation slots, exceeding the 12-call maximum deliberately
so a real boundary can be tested while remaining inquiries are available. This is
not permission to dispatch more than 12 or to execute every slot. Runtime
components must authorize each action, preserve stable gap/original-call identity,
count failed/retry/fallback calls, enforce concurrency/iteration/model-call limits,
and stop on exhaustion. Fallback-initiation events must correspond to actual
recovery decisions, not operation names.

The plan requires failed surf/current fallback calls and an actual
INVESTIGATION_LIMIT_REACHED event, but does not hardcode a planner trajectory or
an expected iteration count of five. The runtime must identify the exhausted
approved budget and keep its counters/trace consistent. A safe early abstention
without that event does not fully exercise the approved SC-010 boundary case.
The authoring tests do not simulate budget exhaustion or pretend this condition
has already been demonstrated.

## Independent assertion coverage

Expected files were authored from acceptance §§18/20 independently of the input
policies and before any application execution. They contain no output copied from
a policy evaluator or generated recommendation. The authoring helpers used to
write static JSON are not runtime code and are not part of the application. The
committed JSON is the reviewable oracle. Mutating the oracle in a temporary test
changes evaluator snapshots only, leaving application/driver snapshots unchanged.

| Required behavior | Serialized checks | Still required from actual runtime / independent validators |
|---|---|---|
| Request/scope | SNORKELING, fixed requested window, revision 1; Kihei preference in SC-004 | Correct natural-language normalization, soft-vs-hard constraint handling |
| SC-004 exclusion | A EXCLUDED; HM-WATER-001 in disqualifying IDs; A absent from recommendations | Applicable advisory classification, precedence, actual policy evidence references |
| SC-004 positive result | B ELIGIBLE/FAVORABLE/SUFFICIENT, exactly one B result; C/D/E absent | Mandatory evidence and accepted support references really justify eligibility |
| SC-004 grounding | Source IDs, accepted finding statuses, original scope/times, actual assessment ID link, nonempty limitations | Verify material claims, source independence, missing-visibility disclosure and evidence-supported recommended windows |
| SC-010 unresolved evidence | Supported A–D NEEDS_INVESTIGATION / UNDETERMINED / INSUFFICIENT, no disqualifying IDs and nonempty unresolved IDs | Missing mandatory evidence remains UNKNOWN, not fabricated PASS or EXCLUDED |
| SC-010 abstention | NO_RECOMMENDATION, ABSTAINED, zero entries and non-null explanation; no hazard/conflict/constraint-based reason | Grounded prose explaining missing information, no “all beaches unsafe” implication |
| Recovery | TOOL_FAILED with actual fallback operation/attempt correlations and SOURCE_UNAVAILABLE code | Authorize the alternative, preserve the original failure and enforce one fallback per semantic gap |
| Execution bounds | At most 12 TOOL_CALLED events; observed tool/iteration counters agree with state and terminal trace | Atomic actual call/model/concurrency/iteration limits; trace cannot omit unauthorized calls |
| Trace/outcome | Required scenario events, terminal status/result ID/counters linked; no technical-failure terminal event | Event completeness, causal references, validation outcomes and genuine local write-failure handling |
| Trust boundary | Expected files/values only in evaluator views, immutable snapshot checks | Runtime must pass only the appropriate projections to each trusted component/model |

SC-004 requires the actual input findings needed for B's positive recommendation
to be accepted, including A's advisory used for exclusion. For SC-010, available
successful weather/water checks need not be retrieved once missing ocean evidence
precludes any recommendation. Its plan does not demand fabricated evidence-received
or validation-success events when an investigation only encounters failures. At
most six successful finding templates are available; any actual finding must still
be bound to its real source/template by independent provenance checks. A cardinality
bound alone is not sufficient to prove that no ocean evidence was fabricated.

The JSON grammar intentionally cannot prove arbitrary prose grounding, enforce
concurrency timers, or independently establish all source-to-result relationships
from existence assertions. Those remain mandatory runtime/common evaluation gates.
There are no dummy blocked assertions whose operator would later stand in for
those checks, no invented capture targets, and no automatic full-scenario PASS
based only on these 145 definitions. The current harness has no runtime/evaluator
execution and reports both cases BLOCKED. The remaining ten scenarios are not
added or silently reclassified.

## Narrow compatibility fix

Authoring the timestamp comparisons exposed that strict TypeAdapter JSON validation
rejected ISO strings for temporal types with the shared BeforeValidator, including
nullable timestamps. The assertion preflight now uses those types' declared ISO
input validators for string date/date-time operands only, retaining the serialized-
type check. All other operands retain strict JSON validation. Regression tests
cover explicit offsets, UTC, dates, nullable timestamps and rejection of naive,
numeric, malformed and non-ISO operands. This changes no approved contract,
clock/default, provider choice, comparison operator or actual runtime behavior.

## Verification and next work

```bash
uv sync --locked
uv run --locked pytest tests/test_scenario_fixtures.py
uv run --locked pytest
```

The new tests verify authored data, premise support, explicit gaps, structured
failures, independent expected-case facts, trace-plan coverage, versions, fixed
times, oracle separation, and BLOCKED readiness. They are **authoring/preflight
unit tests**, not SC-004/SC-010 execution or genuine model-driven ReAct tests.

Next is the approved bounded graph/runtime work and independent evaluator/common
gates, beginning with M1.2's graph skeleton and trusted budget enforcement. Activate
actual scenario evaluation only when its dependencies exist; do not count blocked
checks as passing. Existing v1 JSON inputs, approved specifications, dependency
manifest/lockfile, configuration and CLI remain unchanged.
