# M1.6-F — Synthetic Source Capability Profile Design

**Version:** 0.1 — Proposed  
**Status:** Draft — Human Review Required  
**Date:** 2026-11-19  
**Scope:** Design only; no executable profiles, wire changes or runtime activation

## 1. Authority and purpose

This proposal supplements the approved [technical plan](m1-technical-plan.md),
[configuration baseline](m1-configuration-baseline.md),
[schema mapping](m1-schema-contract-mapping.md),
[fixture design](m1-synthetic-fixture-design.md),
[execution design](m1-langgraph-execution-design.md),
[session lifecycle](m1-session-lifecycle.md),
[request interpretation design](m1-request-interpretation-and-candidate-selection-design.md)
and [harness design](m1-scenario-harness-contract-design.md).
The seven [requirements specifications](../requirements/) remain authoritative.
It develops §4.1 of the [M1.6-D draft](m1-model-provider-and-agent-runtime-design.md)
using the boundaries implemented by [M1.6-E](../development/m1-6e-provider-gateway-and-model-contracts.md).
Neither draft is silently promoted to Approved by this increment.

Agents need to know which synthetic queries they may propose. They must not learn
which queries will succeed, fail or produce an expected recommendation. Introduce
an independently authored interface profile, a trusted offer/resolution layer and
private fixture-coverage validation. These are deterministic application components,
not additional agents. Exactly Coordinator, Weather and Ocean remain autonomous roles.

Current constraints that the design must respect:

- `Operation.match_key()` matches request step, role, source, exact candidate and
  category sets, target interval and geographic-scope JSON. Set ordering is ignored;
  a subset is a different query.
- `SyntheticDriver` allows one original invocation of each matching operation per
  investigation, followed only by its authorized retry. A new delegation cannot
  create another original by selecting the same query again.
- `ToolAction` currently references recovery actions in its own registered plan.
  The dispatcher tracks retrieval gaps; later evidence rejection is a separate stage.
- M1.6-E specialist inputs expose legal option IDs but no explanatory query metadata.
  Its wire proposals cannot reference an observed original in a previous delegation.
- Required local tracing, deterministic validation, authored component mode and
  full-scenario readiness gates already exist and must remain authoritative.

## 2. Artifact and version contract — proposed CP-OD-001

Propose a standalone local JSON configuration artifact, conventionally
`config/source-capabilities/<profile_id>.json`. This is a future path, not a new
file created by M1.6-F. Load only an explicitly supplied path through a dedicated
loader. Do not discover profiles, infer one from a scenario name, add fields to
approved fixture artifacts, or change existing configuration/CLI behavior now.

The future loader receives the already selected catalog and its byte digest. It
returns a detached snapshot and profile digest. Paths are resolved under the
explicit configuration root; reject escapes and unsupported versions before use.
The calling runtime pins one profile/catalog snapshot for the run, including its
registered follow-up steps. No hot reload or source-dependent profile switching.

All fields below are required; all objects are closed. This is an internal physical
configuration format, not a seventh logical data schema.

| Object/field | Proposed v1 meaning |
|---|---|
| `capability_format_version` | Literal `1.0.0`; independent of fixture, harness, policy and model-profile versions. |
| `profile_id` | Private stable ASCII identifier, 1–128 characters. No outcome or scenario hints in names. |
| `profile_version` | Explicit dataset revision; initial `1.0.0`. Changed query material requires a new revision/digest. |
| `catalog_sha256` | Lowercase 64-hex digest of the exact selected catalog bytes. Existing catalogs are root arrays; no invented catalog ID/version fields. |
| `queries` | 1–64 finite `QueryCapability` records, uniquely identified and uniquely matched. |
| Query `query_id` | Private ASCII identifier, unique within the profile; never a script operation ID. |
| Query `agent_type` | Existing `WEATHER` or `OCEAN` domain. |
| Query `source_id` | Existing `SourceId`; must be permitted for this domain and every requested category. |
| Query `candidate_beach_ids` | 1–64 unique existing catalog IDs; exact supported batch, not a wildcard or subset template. |
| Query `requested_evidence` | 1–6 unique existing `Category` values, excluding catalog verification. Exact batch. |
| Query `target_time_window` | Existing aware, ordered `TimeRange`. Exact supported synthetic interval. |
| Query `geographic_scope` | Closed v1 shape `{zone: Identifier}`. Exact synthetic query routing label, not proof of geographic applicability. |

Reject unknown keys, coercions, duplicate JSON keys/IDs, nonfinite numbers,
unsupported version tuples, unknown catalog IDs, invalid categories/sources and
naive/reversed intervals. Bound file size at 256 KiB before decoding. These size
bounds are proposed parser safeguards, not increases to investigation budgets.
Identifiers use the existing ASCII shape `^[A-Za-z0-9][A-Za-z0-9_.:-]*$`, at most
128 characters. Profile revisions use three dot-separated nonnegative decimal
integers without leading zeros, at most 32 characters. Only capability format
`1.0.0` is understood initially; a profile revision cannot change format semantics.

Compare candidates/categories as sets; compare interval endpoints as instants;
compare geographic-scope material canonically. Two different IDs with identical
material are invalid aliases. The source/role/category matrix remains the approved
one in harness design §9 and `models/permissions.py`; no profile can extend it.
NDBC surf and HWT narrative wind remain contextual. Supplemental evidence cannot
replace mandatory authoritative advisory checks. Source permission is not proof
that a returned finding satisfies a mandatory evidence requirement.

For reproducible profile hashing, normalize endpoints to UTC ISO strings, sort
candidate/category lists and queries by their private IDs, and serialize with
sorted object keys, ASCII escaping, no nonfinite numbers and compact separators.
Retain the original file-byte SHA-256 separately for artifact bookkeeping. Model
inputs receive neither private IDs nor file paths. The catalog byte digest is
checked before normalization; neither catalog representation nor attribution changes.

### 2.1 Illustrative profile fragment

This JSON describes one interface shape only. The all-zero catalog digest is an
explicit placeholder, and this fragment is not an executable profile, a claim of
current fixture coverage or a real environmental source definition.

```json
{
  "capability_format_version": "1.0.0",
  "profile_id": "synthetic-coastal-example",
  "profile_version": "1.0.0",
  "catalog_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "queries": [
    {
      "query_id": "marine-pair",
      "agent_type": "OCEAN",
      "source_id": "NWS_MARINE",
      "candidate_beach_ids": ["TEST_BEACH_A", "TEST_BEACH_B"],
      "requested_evidence": ["SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS"],
      "target_time_window": {"start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"},
      "geographic_scope": {"zone": "SYNTHETIC_REGION"}
    }
  ]
}
```

The first implementation should use independently authored test profiles. Existing
source-query definitions in authored adapter/demo code and the approved interfaces
may inform authoring. Do not generate profiles by enumerating behavior operations,
available attempts, responses, policy premises or expected results. Human review
must check this provenance; JSON validation alone cannot prove independent authorship.

## 3. Stable gap groups and dispatch history — proposed CP-OD-002

The current fallback key includes investigation, revision, exact candidate group,
category and target interval. Different overlapping candidate groups could otherwise
describe the same unresolved need with fresh fallback allowances.

For v1, impose a deliberate finite-batch restriction: for each category and target
interval, candidate groups across profile queries must be identical or disjoint.
Apply this across sources, roles and zone labels. For example, surf queries for
`{A,B}` and `{A}` cannot coexist in one profile at the same interval; surf `{A,B}`
and `{C,D}` can. Different categories may use different partitions, such as marine
`{A,B}` alongside individual water-quality checks for `{A}` and `{B}`.

This proposed restriction preserves the existing group-based gap semantics. It
avoids silently introducing a per-beach, multi-gap fallback budget. A future profile
supporting overlapping batches needs an explicit budget/correlation design change.
Profiles must not be swapped or refined during an investigation to evade this rule.

Derive the canonical required-gap registry from these fixed groups, owned request
identity/window and the activity evidence profile. Reuse the dispatcher's existing
gap-ID algorithm through a shared trusted helper; do not independently choose new
serialization or include source, role, query ID, delegation ID or zone in that key.
Record typed scope alongside the opaque gap ID. Model-provided gap labels are never
authoritative. A successful retrieval does not close a gap until the applicable
evidence/safety validation establishes sufficient support.

Seed specialist `known_evidence_gaps` and action gaps from that same registry.
A delegation spanning `{A,B,C,D}` with queries for `{A,B}` and `{C,D}` must not
create an additional parent-wide gap for the same category. The current dispatcher
seeds parent-wide retrieval gaps, so split-batch aggregation requires a reviewed
implementation change and regression checks; it is not already solved by hashing.

Maintain an investigation-wide query ledger keyed by canonical query material.
It records reservations and actual original/retry/fallback calls, their trusted
outcomes and gap bindings. It never reads remaining script attempts to decide which
options are legal. Its scope survives later delegations and both specialist branches;
post-terminal follow-ups create a fresh ledger with their new investigation/revision.

Propose one primary retrieval claim per required gap. A multi-category primary
claims all required gaps it addresses atomically. Another source addressing the
same unresolved required gap after that primary is recovery and must consume its
fallback allowance; labeling it ALWAYS cannot turn it into a fresh primary. Contextual
or optional retrievals do not establish required coverage or acquire a fallback
allowance. Purpose and priority come from trusted requirements/source rules, not a
model label that could demote a required gap to optional. No query signature can be
dispatched as a second original. An authorized
retry repeats exact material and references its actual failed original, at most once.

This is a proposed trusted admission policy for the new runtime, not behavior that
M1.6-E already implements. Preserve authored component semantics while adding and
testing it. It permits evidence-driven recovery without unbounded corroboration.

## 4. Runtime offers and model views — proposed CP-OD-003

Generate offers only from the pinned profile/catalog, independently verified request
receipt, deterministic candidate selection, canonical requirements/assessments,
observed evidence/tool history, scoped delegation and current budgets. Profile
coverage cannot remove otherwise supported candidates or turn a soft preference
into a hard restriction. Preserve UNSUPPORTED assessments under the existing rules.

A query is admissible only when its complete candidate group is within authorized
investigation/delegation scope, its entire category batch is permitted, its exact
window equals the validated target, and its source/domain and recovery history are
allowed. Never shrink a batch, add an out-of-scope candidate, substitute a different
window or rewrite a zone merely to find a matching script. Returned geography and
time applicability remain independently validated.

The trusted offer registry binds each option to exact query material and permitted
purpose/origins. Its receipt records identity, request/delegation attempt, profile,
catalog and request-context digests, relevant observations and the input snapshot.
Derive opaque `option_id` values with a versioned SHA-256 binding; never reuse private
query IDs or driver operation IDs as public choices. Offers expire with the owning
investigation, revision, delegation or incompatible profile/request context.

Models receive only the following projected descriptors:

| Field | Model-visible meaning |
|---|---|
| `option_id` | Opaque lookup token; not an executable function or URL. |
| `source_id` | Permitted source identity, without fixture/operation aliases. |
| `candidate_beach_ids` | Exact authorized batch; names/regions may be resolved from the existing catalog summary. |
| `requested_evidence` | Exact category batch. |
| `target_time_window` | Owned exact interval. |
| `allowed_conditions` | Permitted ALWAYS / conditional retry / conditional fallback shapes, without predicting their activation. |
| `observed_origin_call_ids` | Only already observed, scope-compatible origins available for recovery; never hypothetical future calls. |

Raw `geographic_scope.zone`, private query/profile IDs, scenario IDs, paths, script
operation IDs, source fixture/template IDs, fault labels, attempt inventories,
simulated durations, expected assertions and private policy premises stay out of
model inputs. Existing zone strings sometimes contain scenario identifiers; they
must remain private even when needed verbatim by the dispatcher. The descriptor
describes request scope, not verified source coverage or favorable conditions.

Retain `legal_option_ids` as the exact index of descriptor IDs in the specialist
projection; reject mismatched lists, duplicate IDs or invented descriptors. A trusted
resolver, never the model, supplies request IDs, tool IDs, geographic routing material,
deadlines and final `ToolAction`/`EnvironmentalToolRequest` fields.

Before offering Coordinator `legal_tasks`, derive the role's outstanding category
requirements and close any indivisible query batches. Candidate subsets come only
from distinct declared query groups plus the complete selected pool, not arbitrary
model-selected powersets. Offer only scopes whose requested categories have an
authorized query combination within that scope; mandatory closure must not rely on
contextual-only sources. The model selects exact tasks under the existing contract;
specialists then choose sources and guarded steps. No task fixes future tool outcomes,
forces all alternatives to execute, or dictates an expected recommendation.

Keep offers finite and deterministically ordered by public query material, not
predicted success or source-response contents. Recheck the actual rendered input
against M1.6-E's bounds. If the complete admissible view cannot fit, fail the size/
capability check; do not silently truncate options, evidence or constraints, change
the input limit or auto-select an expensive model.

## 5. Recovery and wire compatibility — proposed CP-OD-004

Within one plan, retain conditional steps referencing earlier `origin_step` entries.
Before any environmental call, validate the entire plan's membership, scope,
acyclicity, duplicate primary claims and worst-case tool capacity. At actual dispatch,
activate recovery only from trusted observations:

- Retry: an actual retryable failed original, identical material, unused per-original
  retry allowance and shared capacity. A success, partial-but-not-failed retrieval,
  unobserved call or retry-of-retry does not qualify.
- Fallback: one unresolved REQUIRED gap, same canonical group/category/window,
  another permitted noncontextual source, an unused target signature and unused
  per-gap fallback allowance. The fallback query has one category. It cannot widen
  scope, be chained into another fallback for the same gap or create a renamed gap.
- A fallback is itself an original invocation at its target query; its own actual
  retryable failure may have one retry under the existing approved harness rule.
- Skip inactive conditional steps without charging or emitting dispatch/recovery
  events. Every dispatched retry/fallback consumes the shared twelve-tool budget.

Later Coordinator cycles must also be able to select recovery after observing
responses. Propose an explicit **internal wire revision**, not a reinterpretation
of the existing ALWAYS/null combination:

| Proposed specialist PlanStep v0.2 field | Rule |
|---|---|
| `option_id`, `condition`, `origin_step` | Retained, all required; existing meanings preserved. |
| `origin_call_id` | New required nullable identifier. Original: both origins null. Recovery: exactly one earlier step index or one offered observed tool-call ID. |

An observed origin must belong to the active investigation/revision and match a
trusted eligible record. Neither a model string nor script availability establishes
that relationship. Snapshot it in `observed_origin_call_ids`; resolve it against the
current ledger again at dispatch. IDs are references, not permission to retry.

Add the descriptors and this nullable field under a separately reviewed
`m1-agent-runtime-0.2` wire/prompt profile. Keep v0.1 tests, hashes and archived-trace
interpretation intact. Do not accept the new field through v0.1's closed schema or
mark old traces as v0.2. No logical specialist/tool schema or top-level event/status
enum changes. M1.6-F changes no current model profile or adapter configuration.

Required implementation work before genuine integration includes resolving observed
origins across delegations and reconciling trusted evidence-validation gaps with the
dispatcher's retrieval-gap view. In particular, SUCCESS followed by stale/rejected
evidence cannot be treated as sufficient support or retried as a transport failure;
a permitted alternate is a guarded fallback for the still-unresolved required gap.
Do not use a new ALWAYS call to bypass the missing recovery bridge.
The current independent trace reader also requires a failing/partial original for
fallback events. Extend that check only with independently reconstructable required-
gap proof from actual validation/coverage records for a successful-but-insufficient
retrieval. Preserve rejection of fabricated gaps and retries of successful calls;
do not simply remove the origin-outcome check.

## 6. Atomic dispatch and concurrency — proposed CP-OD-005

The new trusted resolver and existing BudgetManager must jointly authorize work.
Use one short critical section, with no await, to recheck current identity, scope,
query consumption, canonical gap claims, recovery eligibility and remaining capacity;
reserve all relevant claims or none. Required durable authorization precedes dispatch.
Undispatched reservations can be released. Once dispatched, failed/unknown outcomes
retain their counts; no relabeling or new delegation refunds them.

Two specialists may hold offers from the same snapshot. Another branch consuming
global budget does not alone invalidate an otherwise compatible offer: budgets
shown to the model are advisory snapshots and are rechecked atomically. Structural
identity/profile/scope changes invalidate it; newly satisfied gaps or consumed query/
recovery claims require deterministic reauthorization or skipping. Stale options
must not race into extra original calls, retries or fallbacks.

Preserve five Coordinator cycles, twelve model calls, twelve environmental calls,
two specialist executions, three recommendations, 30-second model and 10-second
synthetic tool timeouts. Profiles contain no overrides. Model invocations for offer
planning still use the shared gateway. No hidden judge, repair, autonomous source
selector or model retry is introduced. Deterministic stop/validation/rendering
continues using already sufficient accepted state when limits are reached.

## 7. Private coverage preflight — proposed CP-OD-006

Retain the approved harness loading and independent-evaluator snapshot order. After
ordinary fixture preflight, add a private capability compatibility pass before
request admission/model/tool dispatch. It receives the profile, catalog, registered
request steps and driver input snapshot, never expected results as an input to
capability construction. Existing evaluator assertions remain separately snapshotted.
Use a narrow preflight input object rather than passing LoadedScenario or evaluator
objects; coverage diagnostics and driver bindings remain private harness data.

For v1, every declared query must have exactly one matching operation at **each**
registered request step, with the same exact role/source/candidate/category/window/
geographic material. This intentionally finite run-wide contract avoids silently
selecting subsets of advertised capabilities from scripts. A profile with multiple
windows requires declared coverage for them at every step; a narrower profile or
new dataset must be authored explicitly if that is inappropriate. Extra unadvertised
script operations are allowed but cannot become runtime choices.

Check original/retry coverage privately. If a first scripted response could activate
an admitted retry under the real trusted failure predicate, the corresponding second
attempt must exist and be valid. TIMEOUT and invalid-response handling must agree
with runtime rules; a source's retryable flag alone never grants execution. A
one-attempt successful query does not require a fake retry delivery, since its
retry condition cannot activate. Fallback targets are ordinary declared queries;
they require their own coverage, including a possible retry of the fallback.

The compatibility report may inspect behavior/error annotations to detect missing
coverage but may not feed them into offers. Changing future source outcomes while
keeping interface material fixed must leave the advertised query set unchanged.
If that mutation requires an absent retry delivery, reject the fixture binding;
do not suppress the retry option to make the mutated dataset pass. Preflight never
consumes attempts, dispatches fake calls or manufactures exhaustion/trace events.

| Condition | Classification |
|---|---|
| Runtime/profile capability not implemented or not supplied during readiness checks | BLOCKED, no execution; cannot report PASS. |
| Explicit invalid/unreadable profile, wrong catalog, ambiguous/missing declared script match or reachable retry coverage | FAIL: invalid configuration/fixture binding before dispatch, not blocked-but-correct behavior. |
| Before-admission proof that the requested execution exceeds supported capability | BLOCKED with a concrete capability diagnostic. Never alter request meaning to fit the profile. |
| Unsupported query/scope discovered after admission, stale/forged option or unexpected missing/excess match at runtime | FAIL; retain actual spent calls and trace. Do not retroactively label attempted execution BLOCKED or simulate source outage. |
| Actually dispatched source outage, stale evidence or invalid response | Existing trusted recovery, evidence validation and terminal rules; possible explained abstention. |

Coverage is not an acceptance oracle. It proves that every advertised permitted
query has deterministic fixture handling, not that an LLM chooses correctly or that
mandatory evidence will be favorable, sufficient or available after dispatch.

### 7.1 Existing dataset implications

SC-004 uses regional candidate batches plus individual water checks. SC-010 contains
both a broad marine query and individual marine variants at the same interval.
The latter cannot all appear in one proposed v1 profile under §3; choose a reviewed
nonoverlapping interface family before execution. Unadvertised variants remain
unused scripts, not secret model choices. Profiles for narrower hard scopes may
require additional independently authored operations, without widening user scope.

Some current zone strings contain scenario labels and otherwise similar strings
differ in punctuation. Preserve their exact private routing material when needed;
do not normalize hyphens, infer geographic coverage from labels, or expose labels
as model hints. No automatic profile is claimed for either existing scenario.
Approved fixtures and their expected files remain unchanged in M1.6-F.

## 8. Trace and lifecycle integration — proposed CP-OD-007

Pin profile/catalog versions and digests in the trusted run receipt and capture.
Retain local authoritative JSONL, fail-closed writes and independent trace validation.
Use existing CONTRACT_VALIDATED events; proposed additional controlled details are:

| Contract/detail | Meaning |
|---|---|
| `source_capability_profile` with format/revision, `capability_profile_digest`, `capability_catalog_digest` | Exact approved interface/catalog snapshot; no file path, private ID or source payload. |
| `source_capability_offer` with `capability_offer_digest`, public option IDs, delegation identity and permitted scope | Offered immutable view and its owning request/attempt. |
| `source_capability_action` with `selected_option_id`, offer digest, original-call/gap references and controlled purpose | Membership/authorization decision tied to actual dispatch or rejection. |

Review concrete key names/privacy projections and implement them with independent
reader checks in the later code increment. Expected digests, raw zones, scripts,
prompts, private reasoning and opaque user constraints stay out of these records.
Existing tool events still preserve actual source attribution, evidence timestamps,
runtime finding IDs and evaluator-only bindings under current rules.

A model-selected ID alone is not evidence of execution. Correlate an authorized
offer/action to actual TOOL_CALLED and completion/failure, retries/fallbacks and
the same shared budget totals. A complete trace cannot claim capability fulfillment
from an unused option, a CANCELLED reservation or an unvalidated finding.

Post-terminal follow-ups retain session, advance revision and create a new
investigation, fresh query/gap/call ledgers and independently retrieved evidence.
Previous results/traces remain immutable. Old offer IDs and origin calls cannot be
used in the new investigation. Active clarification resumption and persistence
remain deferred. Paid-model activation and cumulative spending controls remain
outside this profile design; the M1.6-E live-execution gate stays closed.

## 9. Proposed acceptance tests — CP-OD-008

All code tests remain synthetic, offline and credential free. These supplement
SH-T01–20, approved contract/configuration tests and the MR-T acceptance plan.

| ID | Required check |
|---|---|
| CP-T01 | Strict/versioned loading rejects unknown keys, duplicate JSON, coercions, oversize input, invalid paths/times/IDs/digests; no dispatch or profile auto-discovery. |
| CP-T02 | Role/category/source and contextual-authority constraints cannot be expanded by a profile. Catalog verification remains local. |
| CP-T03 | Equivalent set order/time offsets hash/match consistently; duplicate aliases and overlapping nonidentical category groups are rejected. |
| CP-T04 | A valid profile/catalog pair produces detached deterministic offers using only allowed inputs; changing caller lists cannot mutate the registry. Split-batch retrieval does not invent an additional parent-wide gap. |
| CP-T05 | Hard-scope A cannot issue an A+B query; missing capability does not alter candidate selection, user meaning or UNSUPPORTED assessments. |
| CP-T06 | Changing only future success/failure/payloads leaves offered descriptors unchanged; missing newly reachable retry coverage fails binding rather than changing options. |
| CP-T07 | Model views contain no zones/scenario hints, scripts, private IDs, attempt inventories, evaluator data or private policy premises. Unknown injected instructions stay data. |
| CP-T08 | Every advertised query matches exactly once per request step; missing/ambiguous patterns fail before admission. Unadvertised script alternatives never become choices. |
| CP-T09 | Repeating a signature through a new option, delegation, source alias or cycle cannot create a second original; a real retry preserves exact material and its original allowance. |
| CP-T10 | Fallback keys survive source/role/delegation/zone changes; candidate refinement cannot reset the same required gap. Duplicate multi-category primary claims are rejected atomically. |
| CP-T11 | Same-plan recovery and observed-origin recovery bind actual calls, never hypothetical IDs; cross-investigation/revision or retry-of-retry references fail. |
| CP-T12 | SUCCESS with stale/rejected evidence preserves required uncertainty; an allowed alternate consumes fallback capacity and has independently validated trace gap proof, while fabricated gaps and transport retry of success are rejected. |
| CP-T13 | Conditional branches activate only from qualifying observations, fallback retries follow the approved rule, and skipped branches cost zero. |
| CP-T14 | Opposite Weather/Ocean completion order cannot oversubscribe calls or duplicate query/gap claims; unrelated budget changes do not invalidate compatible offers. |
| CP-T15 | Failure before dispatch releases reservations; dispatched failures/trace uncertainty stay charged and required tracing failures prevent publication. |
| CP-T16 | Old offers/observed origins cannot survive a new investigation; unchanged normalized context may carry forward but prior evidence and allowances do not. |
| CP-T17 | Expanded specialist inputs and `origin_call_id` require the new wire/prompt version; v0.1 rejects extra fields and its trace hashes remain interpretable. |
| CP-T18 | Actual rendered offer input obeys size bounds without silent omission, limit increases, provider switches or hidden model calls. |
| CP-T19 | Missing preflight capability is BLOCKED, invalid binding is FAIL, and post-admission faults remain FAIL with observed counts; real outage is a distinct actual execution path. |
| CP-T20 | Current authored CLI/component regressions remain valid; schema/profile/coverage success cannot promote full scenario or M1 PASS. |

## 10. Review decisions and next increment

All CP-OD-001–008 are **PROPOSED**. Particular review points are the exact finite
profile format, nonoverlapping gap groups/primary-claim rule, descriptor projection,
observed-origin wire v0.2 extension, atomic query ledger, run-wide coverage proof,
trace details and tests. These resolve implementation choices without changing the
three roles, logical contracts, mandatory safety requirements or approved limits.

After review, recommend **M1.6-G — Capability Profile Loading and Validation**:
implement the strict local loader, catalog binding/canonicalization, group checks,
detached query registry and private coverage preflight with independently authored
component fixtures. Keep authored scenarios and disabled live-model configuration
unchanged. Stage offer/proposal v0.2, cross-delegation recovery and agent integration
after those foundations, with explicit acceptance checks; do not claim them from
loader tests. Full scenario PASS still requires genuine model-driven decisions,
canonical evidence/safety/results, complete tracing and every mandatory assertion.
