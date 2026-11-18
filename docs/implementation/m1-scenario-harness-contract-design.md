# Hawaii Activity Forecaster — M1.1-E Scenario Harness Contract Design

**Version:** 0.1 — Approved Baseline

**Status:** Approved — Scenario Harness Contract Design

**Approval recorded:** November 18, 2026 — explicit user approval in this chat.

**Scope:** Synthetic policy inputs, tool behavior scripts, evaluator assertions, scenario assembly

**Authorization:** Design approved. Application-code implementation requires a separate request; existing logical requirements remain unchanged.

## 1. Purpose and authority

M1.1-D can preflight catalogs and source responses independently. Complete
TestScenario loading requires the physical formats left open by the approved
fixture design §22. This approved supplement defines those formats; their
implementation remains future work. All new keys and vocabularies below are
**approved harness metadata**, not new
application fields, autonomous roles, trace events, or environmental thresholds.

The sources of truth remain:

| Approved document | Governs |
|---|---|
| [Data schemas](../requirements/03-data-schemas.md) §§2–9 | Records, enums, identifiers and cross-record invariants |
| [Agent/tool contracts](../requirements/04-agent-tool-contracts.md) §§3/4/7/13/14 | Scoped dispatch, correlation, domain permissions and retries |
| [Safety policies](../requirements/05-safety-policies.md) §§4/5/11/14–17 | Mandatory evidence, policy precedence, MIXED and sufficiency |
| [Acceptance](../requirements/06-test-acceptance.md) §§5/16–24 | Scenario fields, conditions, expectations and test outcomes |
| [Observability](../requirements/07-observability.md) | Actual local audit events, provenance and privacy |
| [Fixture design](m1-synthetic-fixture-design.md) §§3–12/16–22 | Independence, physical conventions and unresolved formats |
| [Configuration](m1-configuration-baseline.md) §§6–13 | Budgets, timeouts, tracing and fail-closed execution |
| [Session lifecycle](m1-session-lifecycle.md) §§3/7–10 | Follow-ups, immutable terminal investigations and original provenance |
| [Execution design](m1-langgraph-execution-design.md) §§5/8/9/17 | State ownership, merge semantics, atomic reservations and tracing |

No approved document, source payload, existing fixture package, or runtime code is
changed by this design approval. A later implementation must be separately requested.

## 2. Artifact boundaries and versions — SH-OD-001/002

Use three distinct views of a scenario:

1. **Harness-owned definition:** the complete logical TestScenario, including
   evaluator-owned expected_results, scripts, input references and readiness.
2. **Application inputs:** the user request, fixed clock, catalog, and approved
   synthetic evidence/policy configuration. Specialists receive their existing
   scoped contracts and authorized synthetic adapters, not the scenario definition.
3. **Evaluator inputs:** immutable preauthored assertions plus captured actual
   state, result, trace and harness correlation records after execution.

Expected files, their paths, selectors and values must never be passed to the
Coordinator, specialists, their model context, or synthetic adapters. The harness
can orchestrate loading and evaluation but is a deterministic test component.
No additional agent or externally hosted service is introduced. This separation
is an API/data-flow boundary, not a claim of OS-level file isolation.

Keep M1.1-D format/package `1.0.0` unchanged. Use a separate scenario package
(e.g. `fixtures/scenario-pack-v1/`) with:

| Identifier | Approved value and meaning |
|---|---|
| fixture_format_version | `2.0.0`: adds scenario/index and contract-version metadata |
| fixture_package_version | `1.1.0`: a new synthetic dataset; not an in-place relabeling of v1 |
| schema_version | `0.1`: Data Schemas logical records |
| policy_version | `0.2`: Safety Policies logical baseline |
| harness_contract_version | `1.0.0`: formats in this design |
| policy_configuration_version | `synthetic-policy-1.0.0`: separate synthetic premise/rule configuration |

The v2 manifest retains v1's explicit synthetic marker, clock/window, catalog and
source registry and adds `harness_contract_version` and `scenarios`.
`scenarios` is a list of `{scenario_id, path}` records; IDs/paths must be unique.
Paths refer to `scenarios/<id>/scenario.json`. Each scenario's ID and catalog
reference must agree with its registration. Its reference_time is authoritative
for that scenario; the manifest's clock/window are dataset reference metadata,
not request defaults. Referenced policies/behaviors/assertions all declare
`harness_contract_version: "1.0.0"`; all policies also declare the policy versions.
Reject unsupported version tuples before loading executable inputs. Existing
v1 APIs must continue rejecting v2 until a deliberate implementation adds support.

Keep package-relative paths confined to their designated input subtrees, as in
M1.1-D. Add `source_sets/`, `policies/`, `behaviors/` and evaluator-only
`scenarios/<id>/expected.json`. No relative traversal, URL retrieval, wildcard file
discovery or implicit merging of packages. Resolve symlinks before containment checks.

## 3. Scenario assembly and follow-ups — SH-OD-003

Preserve every approved TestScenario field and its required/conditional status.
`weather_fixture` and `ocean_fixture` each reference a source-set object:
`{harness_contract_version, agent_type, source_fixture_ids}`. IDs resolve to the
manifest's existing typed source registry. Source-set files are harness metadata;
individual response files still contain only EnvironmentalToolResponse fields.
A set cannot import another specialist's provider or evaluator artifacts.

`tool_behavior`, when present, is exactly `{script: <behavior JSON path>}`.
Omission means no environmental dispatch is scripted, not implicit success.
`policy_configuration` references a policy object; `expected_results` is a
physical `{path: <expected JSON path>}` reference. Only the harness resolves that
reference into the required logical structured expected_results before validating
the full TestScenario. The application receives a separate projection that omits it.

Illustrative TestScenario (the referenced v2 artifacts are not yet implemented; this is not
an executable replacement for the approved SC-004):

```json
{
  "scenario_id": "SC-004",
  "description": "Applicable synthetic water-contact avoidance advisory",
  "requirement_ids": ["HM-WATER-001", "HM-WATER-002", "EL-004"],
  "user_request": "Where should I snorkel tomorrow morning near Kihei?",
  "reference_time": "2026-11-16T09:00:00-10:00",
  "catalog_fixture": "catalogs/synthetic-maui-v1.json",
  "weather_fixture": "source_sets/sc-004-weather.json",
  "ocean_fixture": "source_sets/sc-004-ocean.json",
  "tool_behavior": {"script": "behaviors/sc-004.json"},
  "policy_configuration": "policies/sc-004.json",
  "expected_results": {"path": "scenarios/sc-004/expected.json"},
  "test_status": "ACTIVE"
}
```

The executable harness must not silently assume the common evidence conditions
from acceptance §16.1: all mandatory checks, non-hazard premises, and relevant
limitations need explicit fixture inputs. Current v1 examples do not meet that
requirement and cannot simply be relabeled as SC-001 or SC-004.

For SC-012, preserve TestScenario.user_request as the initial request and keep
follow-up harness instructions inside the script's `requests` list. Each record
has exactly `{request_step, user_request, reference_time}` with contiguous positive
steps starting at 1. Step 1 must match TestScenario; later steps are submitted only
after a terminal result. The adapter must not replace natural-language requests
with expected normalized values. One session continues; new investigations and
revisions are generated by the application, with fresh budgets. Active-investigation
cancellation, persistence and blind reuse of prior assessments remain excluded.

## 4. Synthetic policy inputs — SH-OD-004

The approved policy object has exactly:

| Field | Type and purpose |
|---|---|
| harness_contract_version | Supported version string |
| policy_version | `0.2`, approved logical policy reference |
| policy_configuration_version | Reviewed synthetic configuration identifier |
| synthetic | Required JSON `true` |
| evidence_profiles | List of activity/category requirements below |
| evidence_rules | List of `{rule_id, category, source_fixture_id, finding_id, temporal_rule, beach_ids}` |
| premises | List of scoped hypothetical facts defined below |
| mixed_permissions | List of `{activity, limitation_code, requirement_ids, disclosure}` |

### 4.1 Explicit evidence categories and profiles

Use these controlled synthetic `category` values, mapped to safety §4.1:

| Category | Swimming | Snorkeling | SUP |
|---|---|---|---|
| OFFICIAL_ADVISORIES | Mandatory | Mandatory | Mandatory |
| SURF_WAVE_CONDITIONS | Mandatory | Mandatory | Mandatory |
| WIND_CONDITIONS | Relevant | Relevant | Mandatory |
| CURRENTS_PERSISTENT_HAZARDS | Mandatory | Mandatory | Mandatory |
| WATER_QUALITY_ADVISORY_CHECK | Mandatory | Mandatory | Mandatory |
| VERIFIED_BEACH_CHARACTERISTICS | Mandatory | Mandatory | Mandatory |
| UNDERWATER_VISIBILITY | Optional | Important, not mandatory | Optional |

An evidence profile is exactly `{activity, mandatory, relevant, optional}`; the
three arrays partition all seven categories without duplicates. For snorkeling,
visibility goes in `optional` with its importance governed by safety §4.5. The
matrix's mandatory categories cannot be removed or weakened. User hard constraints
are evaluated separately and may require additional evidence. A reported wind or
visibility hazard cannot be ignored merely because its category is not mandatory.
These category names would be the synthetic vocabulary carried by the existing
String/Enum evidence_type contract after approval, not new measurement types.

VERIFIED_BEACH_CHARACTERISTICS is checked directly against the catalog's status,
required supported activity and source-backed attributes; evidence_rules are for
environmental findings. Each declared category must either have the necessary
source rules/premises or explicit scripted missing/unavailable coverage. Source
counts alone never establish sufficiency.

Each evidence_rule binds a source/finding template to candidate beach IDs and one
category. temporal_rule is one of:

- `COVERS_TARGET_WINDOW`: explicit forecast/advisory validity covers the requested interval.
- `DECLARED_REPORT_WINDOW`: reported applicability must cover that interval; retrieval
  time cannot replace it or turn a report into a verified future forecast.
- `CONTEXT_ONLY`: e.g. an offshore observation; it cannot by itself satisfy mandatory
  beach surf, current, entry or visibility evidence.

A rule declares a synthetic test mapping, not an ACCEPTED verdict. The Evidence
Validator still checks record structure, source permission, source coverage and
explicit validity, conflicts and intended use. Synthetic region-to-beach mappings
must be stated here; BEACH evidence can bind only its named beach, OFFSHORE remains
contextual, and no rule may change a finding's original coverage/measurement type.
Production provider age limits and numeric hazard thresholds are not introduced.

### 4.2 Hypothetical facts, not final assessments

Every premise has exactly `{premise_id, beach_id, activity, time_window, fact_type,
value, finding_refs, catalog_field_refs, rationale}`. value is a strict boolean.
finding_refs contains `{source_fixture_id, finding_id}` pairs; catalog_field_refs
contains `{beach_id, field}` pairs naming populated fields of the same candidate.
At least one support reference and a nonempty synthetic rationale are required.
References identify synthetic premise support, not a source's endorsement of the
hypothetical classification. After dispatch, finding references must bind to
actual received evidence and pass applicable independent validation before use.
A declared but never retrieved/rejected finding cannot satisfy a premise.
LIMITED but structurally valid evidence may support detection of uncertainty or
conflict; it cannot positively satisfy a mandatory category without explicit policy
permission. Catalog-only support cannot establish changing environmental facts:
advisory, surf, wind, current, weather and visibility premises require finding
support. Only persistent-characteristic premises may rely on catalog fields alone.

Approved closed fact vocabulary and its interpretation:

| fact_type | Meaning and policy basis |
|---|---|
| OFFICIAL_ADVISORY_CHECK_COMPLETE | Accepted authorized check covers the candidate/time; safety §§4/10 |
| WATER_CONTACT_ADVISORY_CHECK_COMPLETE | Accepted authoritative water-contact check covers the candidate/time; HM-WATER-002/005 |
| WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT | Hypothetical applicable official advisory exists; HM-WATER-001 |
| DISQUALIFYING_SURF_PRESENT | Explicit synthetic hazard classification, never a measurement cutoff; safety §6 |
| DANGEROUS_CURRENT_PRESENT | Explicit synthetic current-hazard classification; safety §9 |
| DISQUALIFYING_WEATHER_PRESENT | Explicit applicable weather hazard/prohibition; safety §10 |
| DANGEROUS_OFFSHORE_WIND_PRESENT | Synthetic wind/exposure classification; SUP policy §8.3 |
| DISQUALIFYING_BEACH_CHARACTERISTIC_PRESENT | Synthetic persistent hazard, independently checked against hard constraints; safety §13 |
| MATERIAL_SAFETY_CONFLICT_PRESENT | Explicit synthetic materiality premise; conflict policy §20.3 |
| ACTIVITY_SUPPORTING_CONDITIONS_PRESENT | Positive hypothetical activity support, still gated by all mandatory evidence/policies |
| NON_DISQUALIFYING_LIMITATION_PRESENT | Supporting finding identifies a reviewed limitation; also requires limitation_code |

Only the last type permits the additional required field `limitation_code`.
Duplicate premises for the same candidate/activity/window/type (and limitation
code when applicable) or contradictory values are invalid input; independent
conflicting findings remain in evidence for the normal conflict policy.

A false value is explicit negative test knowledge only when its required evidence
and applicability are independently established. An omitted premise, false check-
complete premise, empty advisory list, failure or missing support never supplies
implicit PASS, absence of hazards, or favorable suitability. A false hazard premise
cannot contradict an accepted applicable official advisory. Its contradiction must
be investigated or excluded under authoritative precedence, not resolved by fixture
ordering. All relevant policy checks remain independent.

An advisory-status check specifically needs its complete-check premise, accepted
source evidence and evaluated scope/time. Only then may an explicit false
WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT represent “no applicable listed advisory
found,” never “water quality is safe.” A true applicable advisory excludes even if
other evidence is favorable. A missing mandatory check remains UNKNOWN and blocks
eligibility. Mapping these facts through existing policy rules is trusted code;
premises contain no PASS/FAIL, eligibility, suitability or evidence-quality outputs.

Example policy object, deliberately incomplete for SC-004 (it shows one supported
advisory premise; remaining sources/checks must be authored before executable preflight):

```json
{
  "harness_contract_version": "1.0.0",
  "policy_version": "0.2",
  "policy_configuration_version": "synthetic-policy-1.0.0",
  "synthetic": true,
  "evidence_profiles": [{
    "activity": "SNORKELING",
    "mandatory": ["OFFICIAL_ADVISORIES", "SURF_WAVE_CONDITIONS", "CURRENTS_PERSISTENT_HAZARDS", "WATER_QUALITY_ADVISORY_CHECK", "VERIFIED_BEACH_CHARACTERISTICS"],
    "relevant": ["WIND_CONDITIONS"],
    "optional": ["UNDERWATER_VISIBILITY"]
  }],
  "evidence_rules": [{
    "rule_id": "sc004-water-a",
    "category": "WATER_QUALITY_ADVISORY_CHECK",
    "source_fixture_id": "sc004-water-listing",
    "finding_id": "SYNTHETIC_OCEAN_ADVISORY",
    "temporal_rule": "COVERS_TARGET_WINDOW",
    "beach_ids": ["TEST_BEACH_A"]
  }],
  "premises": [{
    "premise_id": "sc004-advisory-a",
    "beach_id": "TEST_BEACH_A",
    "activity": "SNORKELING",
    "time_window": {"start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"},
    "fact_type": "WATER_CONTACT_AVOIDANCE_ADVISORY_PRESENT",
    "value": true,
    "finding_refs": [{"source_fixture_id": "sc004-water-listing", "finding_id": "SYNTHETIC_OCEAN_ADVISORY"}],
    "catalog_field_refs": [],
    "rationale": "Hypothetical applicable water-contact avoidance advisory in this fictional test only."
  }],
  "mixed_permissions": []
}
```

The evaluator owns the independently authored expected EXCLUDED assertion; it is
not derived from this object or passed into the policy evaluator. No premise may
bypass actual evidence retrieval, sufficiency, catalog support, hard constraints,
policy precedence or result validation. ACTIVITY_SUPPORTING_CONDITIONS_PRESENT
alone cannot produce FAVORABLE/ELIGIBLE, and its absence cannot imply favorability.

For the initial MIXED scenario, permit only `SYNTHETIC_POOR_VISIBILITY` as a reviewed
limitation code, scoped to SNORKELING and HM-VIS-003 plus safety §15. It requires
accepted supporting visibility information, sufficient mandatory evidence, no
failed disqualifying policy, resolved mandatory hazards and explicit disclosure.
The policy mapping independently derives MIXED; the rule cannot grant eligibility
or suppress another hazard. SC-002's generic limitation must be concretely authored
and separately reviewed before adding another code. Numerical wind/chop thresholds
remain unapproved.

## 5. Tool behavior scripts — SH-OD-005

A script has exactly `{harness_contract_version, requests, operations}`. requests
is the request-step sequence in §3. operations is a list of independent environmental
operation definitions, each with `{operation_id, request_step, agent_type, source_id,
candidate_beach_ids, requested_evidence, target_time_window, geographic_scope,
attempts}`. Scope/evidence fields use the existing contract meanings; candidate IDs
come from the validated parent specialist dispatch context. Each attempt contains
`{attempt, behavior, simulated_duration_ms}` plus only the behavior-specific fields
below. attempt is a positive integer, contiguous within its operation, starting at 1.
Durations are finite, nonnegative integer milliseconds; booleans are not integers.

Operations match actual authorized dispatches, not Coordinator plans. Match all
listed scope/time/evidence fields exactly (candidate/evidence sets ignore ordering).
Reject overlapping ambiguous operation definitions, undeclared source/category
mappings, or runtime unmatched/excess attempts. The script must not autonomously
select a beach, cause a retry/fallback, declare policy outcomes or stop a Coordinator
iteration. An unused alternative is allowed; an assertion can require that an
intended action actually occurred. Independent operations have no required total
order, so Weather/Ocean completion order can vary without consuming script steps
belonging to another operation.

| behavior | Additional fields | Delivery and validation |
|---|---|---|
| SUCCESS | response_fixture_id | Registered, contract-valid response with SUCCESS status |
| PARTIAL | response_fixture_id | Contract-valid PARTIAL response with explicit missing evidence/errors |
| UNAVAILABLE | response_fixture_id | Contract-valid UNAVAILABLE response preserving the gap |
| ERROR | response_fixture_id | Contract-valid ERROR response with nonempty structured errors |
| TIMEOUT | none | No response payload; simulated duration exceeds the configured timeout |
| MALFORMED | raw_response_path, invalid_fields | Deliberately invalid contract JSON from `malformed/`; see below |
| DUPLICATE | response_fixture_id, delivery_count | Deliver the same logical successful/partial response 2+ times |

For non-TIMEOUT delivery, simulated duration must be at most the configured timeout;
otherwise the fixture contradicts its declared behavior and is invalid. This
design chooses completion at exactly the virtual deadline as timely, and a
strictly greater declared duration as TIMEOUT. This deterministic test convention
does not replace real timer testing. For TIMEOUT, advance the test clock to the
10,000 ms cutoff, record the actual simulated failure there, and never merge a
hypothetical late response. Do not wait 11 wall-clock seconds or claim a real
provider timed out. Model invocations retain their separate 30-second timeout;
this script format authorizes no model retries or model-call mocking.

For synthetic EnvironmentalToolResponse.errors, reuse the already defined
SpecialistError field structure: required error_id, error_code, message, retryable;
conditional source_id and tool_call_id. No new top-level tool response fields are
added. Use the existing proposed error-code inventory from contracts §4.3; IDs and
call/source references are bound to the actual failure. A failed virtual invocation
produces SOURCE_TIMEOUT at the trusted execution boundary. retryable is diagnostic,
not permission to retry. This inner error shape is approved under SH-OD-005.

MALFORMED payloads must be valid UTF-8 JSON but fail the application contract.
invalid_fields is a nonempty list of explicit JSON Pointer field locations
identifying intentional contract faults; empty/root/wildcard locations are forbidden.
Every observed contract error must fall in a declared location/subtree and the
payload must actually be invalid. Path/syntax/permission
faults in fixtures themselves still fail preflight. Do not register such payloads
as normal typed source responses or weaken v1 validation to admit them. Only the
raw payload is delivered across the application's contract boundary; fault
annotations remain in the harness and independent assertions test rejection.

DUPLICATE keeps one tool_call_id and identical finding IDs across deliveries. It
consumes one dispatched invocation, not multiple calls. Separate invocations must
have different tool IDs. Reusing a template for a new retrieval creates new runtime
bindings, whereas redelivery of an existing response does not.

Example operation fragment (only this requests/operations entry is shown; a
complete SC-009 also needs its alternate-source operation and all other mandatory
inputs):

```json
{
  "harness_contract_version": "1.0.0",
  "requests": [{
    "request_step": 1,
    "user_request": "Where should I swim tomorrow morning?",
    "reference_time": "2026-11-16T09:00:00-10:00"
  }],
  "operations": [{
    "operation_id": "primary-surf-check",
    "request_step": 1,
    "agent_type": "OCEAN",
    "source_id": "NWS_MARINE",
    "candidate_beach_ids": ["TEST_BEACH_B"],
    "requested_evidence": ["SURF_WAVE_CONDITIONS"],
    "target_time_window": {"start": "2026-11-17T08:00:00-10:00", "end": "2026-11-17T11:00:00-10:00"},
    "geographic_scope": {"zone": "SYNTHETIC_REGION"},
    "attempts": [{"attempt": 1, "behavior": "TIMEOUT", "simulated_duration_ms": 11000}]
  }]
}
```

A second attempt is available only if trusted execution authorizes a retry after
a failed original invocation and an atomic shared-budget reservation succeeds.
`attempt` is a harness tool-operation attempt, **not** SpecialistInvestigationRequest.
attempt_number. Multiple tool calls can occur within one specialist execution;
retrying that specialist request separately follows its existing request ID/attempt
contract. Retrying a retry cannot create a new original-invocation retry allowance.

Fallback targets are separate operations, selected only by trusted application
logic for an identified evidence gap. The harness observes the actual gap/retry
correlations but never grants permission merely because an operation is scripted.
Gap identity must remain stable for the same semantic gap; renaming it cannot
refresh its one-fallback allowance. A fallback is a new environmental invocation;
any retry of that invocation still requires its own legitimate original-call
correlation and shared capacity. Concurrency/iteration limits and 12 environmental
and 12 model calls remain separate trusted controls. All dispatched failures and
recovery calls consume their respective budgets.

For deterministic concurrency tests, barriers in the test runner can delay
completion to force overlap/reversed order, without invoking a third specialist
or resetting counters. A virtual-time pass cannot be reported as proof of real
wall-clock timeout or concurrency scheduling behavior.

## 6. Identity binding and evidence provenance — SH-OD-006

Source files are immutable templates. A trusted synthetic adapter copies the
selected response at actual dispatch and binds its tool_call_id to that request.
For newly retrieved findings it allocates unique runtime finding IDs and uses the
current investigation ID. Stable source IDs, measurement values, timestamps,
original geographic scope, advisory IDs and content are retained exactly. This
binding is initial retrieval materialization, not relabeling previously collected
evidence. Existing v1 loader outputs remain unchanged.

The harness records a separate binding index, based on observed execution. Every
dispatch has `{request_step, operation_id, attempt, runtime_investigation_id,
runtime_tool_call_id}`. A delivered template adds source_fixture_id; each
materialized finding additionally binds template_finding_id and runtime_finding_id.
Timeouts have call-level records only; redelivery reuses the existing bindings. This index is
harness metadata, not a substitute for the authoritative local trace. It contains
no expected values and is never created by reading the evaluator assertions.

Selectors resolve logical template references through this index. Duplicate
redelivery reuses its binding; a fresh retrieval gets a fresh binding. Ambiguous
multiple invocations require an operation_id/attempt selector rather than choosing
whichever match completed last. Keep runtime specialist request/attempt correlations
separate and validate them through existing contracts.

SC-012 initially re-retrieves required evidence in each investigation. This avoids
silently deciding the open cross-investigation storage representation. Session and
constraint preservation, new investigation IDs, request revisions, fresh budgets
and prior-terminal immutability are still testable. Reuse-specific assertions remain
BLOCKED until a reference representation is approved. Any later reuse must preserve
the actual original finding and its parent investigation, revalidate applicability,
and never rebind it as a new retrieval.

## 7. Independent evaluator assertions — SH-OD-007

An expected file has exactly `{harness_contract_version, scenario_id, assertions}`.
Assertions are authored before execution, independently from generated results and
policy outputs. TestScenario.requirement_ids, catalog/source references and approved
requirements determine the required coverage, not the application's prose.

Each assertion requires `{assertion_id, requirement_ids, mandatory, test_status,
target, selector, operator}`. mandatory is a strict boolean. Optional fields are
`field`, `expected`, `expected_ref`, and `blocking_reason` subject to the table below.
Reject duplicate IDs, unknown fields, unknown targets/operators, malformed selectors,
unsupported paths/types, and reference cycles. Never execute expressions, imports,
code, regex rules or arbitrary model-written selectors.

### 7.1 Targets and selection

Every selector requires positive integer `request_step`. Allowed targets and
additional selector keys are:

| target | Keys and actual records |
|---|---|
| investigation_state | None: one captured state for this request step |
| candidate_assessment | beach_id, activity: current assessments, not superseded versions |
| environmental_finding | source_fixture_id, template_finding_id; operation_id/attempt when needed |
| recommendation_result | None: one captured validated result |
| recommendation | beach_id: entries from that result |
| trace_event | event_type, actor, related_finding_ref, related_call_ref: actual correlated trace events |
| harness_execution | None: observed execution summary for this request step |

related_finding_ref is `{source_fixture_id, template_finding_id}` with optional
operation_id/attempt, resolved to actual related_ids through §6. No sequence-number
assumption fixes Weather/Ocean completion order. Unsupported/unbound references
cannot match an arbitrary record. An expected nonappearance uses ABSENT against a
known candidate/event selector, not a made-up fixture finding that was never bound.
related_call_ref is `{operation_id, attempt}`, resolved within request_step to the
actual tool_call_id. It can select failed/timeout events that have no finding.
When both related-reference selectors are present, both must match the event.

harness_execution exposes only `{session_id, investigation_id, request_revision,
tool_invocation_count, model_invocation_count, iteration_count,
max_concurrent_specialists}` recorded from actual dispatch/session instrumentation.
Never copy configuration maxima into these observed fields. Counts are per
investigation, include dispatched failures/recovery, and must agree with local
trace/state where those records represent the same count.

### 7.2 Operators and missing data

field, when used, is a JSON Pointer into the target's documented JSON projection
(e.g. `/eligibility` or `/activity`), with no wildcards or negative indices.
Preflight must validate it against target types; trace details can use only the
approved structured fields documented in 03 §§7.5–7.8, not arbitrary source text.
There is no private model-state, credential, or chain-of-thought target.

| operator | Required operands | Semantics |
|---|---|---|
| EQUALS, NOT_EQUALS | field and expected | Exactly one selected record; strict typed JSON comparison |
| ALL_EQUALS | field and expected | Every selected record matches; zero records is FAIL |
| INCLUDES, EXCLUDES | field and expected | One record; field is an array, expected is one strictly typed element |
| COUNT_EQUALS, COUNT_AT_MOST | expected only | Count selected records; expected is a nonnegative integer |
| EXISTS, ABSENT | none | At least one / zero matching records |
| SAME_AS, DIFFERENT_FROM | field and expected_ref | One record compared with exactly one other actual record's field |

expected_ref is `{target, selector, field}` with the same validation and type rules;
it compares captured observations across request steps, never supplies application
inputs. It cannot recursively reference another assertion. Missing pointers or
missing required captures are FAIL when execution was attempted, not null, empty
arrays, UNKNOWN policy results, or an automatic pass. ABSENT requires a captured
collection; a missing result/trace is not evidence that a forbidden recommendation
or event was absent. Boolean true does not equal numeric 1. No string/numeric
coercion, substring equality, or nondeterministic explanation grading is allowed.

Illustrative SC-004 assertions (a subset, not the complete common acceptance gates):

```json
{
  "harness_contract_version": "1.0.0",
  "scenario_id": "SC-004",
  "assertions": [
    {
      "assertion_id": "SC-004-A01",
      "requirement_ids": ["HM-WATER-001", "EL-004"],
      "mandatory": true,
      "test_status": "ACTIVE",
      "target": "candidate_assessment",
      "selector": {"request_step": 1, "beach_id": "TEST_BEACH_A", "activity": "SNORKELING"},
      "field": "/eligibility",
      "operator": "EQUALS",
      "expected": "EXCLUDED"
    },
    {
      "assertion_id": "SC-004-A02",
      "requirement_ids": ["RR-005"],
      "mandatory": true,
      "test_status": "ACTIVE",
      "target": "recommendation",
      "selector": {"request_step": 1, "beach_id": "TEST_BEACH_A"},
      "operator": "ABSENT"
    },
    {
      "assertion_id": "SC-004-A03",
      "requirement_ids": ["RR-003"],
      "mandatory": true,
      "test_status": "ACTIVE",
      "target": "recommendation",
      "selector": {"request_step": 1},
      "operator": "COUNT_EQUALS",
      "expected": 1
    },
    {
      "assertion_id": "SC-004-A04",
      "requirement_ids": ["RR-005"],
      "mandatory": true,
      "test_status": "ACTIVE",
      "target": "recommendation",
      "selector": {"request_step": 1, "beach_id": "TEST_BEACH_B"},
      "operator": "EXISTS"
    }
  ]
}
```

An empty recommendation list must fail SC-004's positive/count assertions even
though A is absent. All active scenarios also need independent mandatory checks
for schema/correlation integrity, grounded eligible recommendations, sufficient
accepted evidence, correct outcome mapping, execution bounds, source permissions,
required trace events and agreement with terminal state. Those checks inspect
actual evidence and references; they cannot merely trust an ELIGIBLE string or
RESULT_VALIDATED event name. Missing components are blockers, not passing stubs.

## 8. Readiness, reporting and the status conflict — SH-OD-008

Preserve the approved TestScenario.test_status enum: ACTIVE, BLOCKED, DISABLED.
Preserve test outcomes PASS, FAIL, BLOCKED, NOT_RUN from acceptance §24.1.

There is a source inconsistency: acceptance narrative labels SC-005 and SC-008
PARTIALLY_BLOCKED, while §5.1's TestScenario enum has no such value. Approved
resolution under SH-OD-008: use ACTIVE containers for their runnable synthetic
assertions, with explicit BLOCKED atomic assertions for unresolved production
classification. Preserve the original PARTIALLY_BLOCKED narrative label in the
review coverage table below. This explicitly approved serialization mapping preserves the baseline narrative
and does not add an application enum.

Assertion test_status permits ACTIVE, BLOCKED, DISABLED and the approved individual
PARTIALLY_BLOCKED readiness label. Any blocked/partially-blocked assertion requires
a nonempty blocking_reason naming its missing rule/dependency. Prefer splitting
partially blocked checks into ACTIVE and BLOCKED atomic assertions; unsplit
PARTIALLY_BLOCKED assertions yield BLOCKED, never PASS. ACTIVE assertions cannot
contain a blocker; disabled assertions require an explanatory reason too.

Scenario-level reporting:

- BLOCKED scenarios do not execute and report BLOCKED; DISABLED reports NOT_RUN.
- ACTIVE scenarios preflight first. Invalid input reports FAIL with diagnostic
  category `FIXTURE_INVALID`, distinct from an application failure; no execution.
- Missing declared runtime capability reports BLOCKED with its dependency. An
  unexpected evaluator exception reports FAIL/category `EVALUATOR_ERROR`.
- After execution, any failed active mandatory assertion makes the scenario FAIL,
  even when other assertions are blocked or pass. A missing required output after
  dispatch is FAIL; it is not recast as a missing implementation dependency.
- Otherwise any blocked mandatory assertion makes the aggregate BLOCKED. PASS
  requires all mandatory assertions to run and pass. An empty/all-disabled mandatory
  set cannot pass and must report NOT_RUN; omitting required coverage is invalid input.
- Record optional assertion failures separately; report every assertion outcome and
  pass/fail/blocked/not-run counts. Do not present a full-scenario pass when required
  classification is blocked. No aggregate percentage overrides a mandatory failure.

Diagnostic categories are harness report metadata; they do not add result, state,
policy, trace-event or test-outcome enum values. Assertion outcomes and their
reasons must be retained independently from application logs.

### Scenario coverage preserved for review

| Scenario | Baseline readiness | Required coverage / limits of the design |
|---|---|---|
| SC-001 | ACTIVE | Multiple eligible candidates; explicit complete mandatory evidence; soft geography |
| SC-002 | ACTIVE | Favorable farther beach over permitted MIXED preferred beach; limitation code still needs concrete authoring/review |
| SC-003 | ACTIVE | Only B supports SUP in the hard South Maui area; no padding |
| SC-004 | ACTIVE | Applicable advisory excludes A; B alone recommended with complete checks |
| SC-005 | PARTIALLY_BLOCKED | Test explicit synthetic wind hazard enforcement; real measurement/orientation classification stays BLOCKED |
| SC-006 | ACTIVE | Reviewed poor-visibility MIXED permission, sufficient evidence and disclosure; otherwise comparable B favored |
| SC-007 | ACTIVE timestamp checks; eligibility policy-dependent | Explicit source validity, independent page checks; production freshness cutoffs remain BLOCKED |
| SC-008 | PARTIALLY_BLOCKED | Preserve both findings and enforce unresolved synthetic conflict; automatic materiality classification stays BLOCKED |
| SC-009 | ACTIVE | Timeout then authorized alternate operation; original failure and budgets retained |
| SC-010 | ACTIVE | Failed recovery and exhausted investigation yield abstention, not unsafe-ocean claims or technical failure |
| SC-011 | ACTIVE | Source instruction text remains untrusted; applicable hazard excludes A; no permission/constraint changes |
| SC-012 | ACTIVE | Post-terminal request sequence preserves constraints/session, new IDs/revisions/budgets; reuse representation-specific checks stay BLOCKED |

ACTIVE in this table describes the baseline's defined behavior, not implemented
coverage. This design approval activates no scenario and claims no acceptance passes.

## 9. Preflight and capability gates — SH-OD-009

The approved loading order is: manifest and versions; scenario definition and registered
source sets; catalog; policy configuration; ordinary typed responses; behavior
script and deliberately malformed payload descriptors; evaluator-only expected
file; cross-artifact validation; readiness/capability check; application projection.
No model/tool dispatch occurs before all required enabled inputs and assertions
have passed preflight. BLOCKED/DISABLED definitions are still version/shape checked
when inventoried; invalid definitions are reported distinctly from their declared
readiness. Invalid input is never counted as a blocked-but-correct application.

Snapshot validated inputs and evaluator assertions before dispatch; do not reload
or derive expected values during execution. Record artifact versions and byte
digests in the harness run report for reproducibility. Expected-file names/digests
belong only to evaluator bookkeeping, not application or model inputs.

Preflight must reject:

- Unsupported versions, unknown keys/categories/facts/operators, missing fields,
  naive/reversed times, nonfinite values, duplicate JSON keys/IDs and path escapes.
- Mismatched scenario IDs, invalid source domains/categories, missing references,
  incomplete profiles, or an undeclared missing mandatory evidence category for a
  scoped candidate/activity. Unsupported catalog activities remain representable
  as intended UNSUPPORTED cases; they are not falsely required to have hazard data.
- Conflicting premises, final verdicts in policy inputs, references to expected
  files from application/source data, and a profile that weakens the safety matrix.
- Ordinary source responses that violate application contracts; malformed data
  without a narrowly declared fault; response statuses inconsistent with behavior;
  ambiguous operation matches; gaps/attempts that would invent new permissions.
- Assertions with invalid type/cardinality/operand shapes, unknown targets/fields,
  missing mandatory coverage, unresolved IDs, or readiness inconsistent with blockers.

The approved category/source mapping is fixture-only and subordinate to §13's domain
permissions: OFFICIAL_ADVISORIES uses NWS_ALERTS/NWS_MARINE; SURF_WAVE_CONDITIONS
uses NWS_MARINE/HWT_SURF with NDBC contextual only; WIND_CONDITIONS uses
NWS_WEATHER/HWT_WIND/NWS_MARINE, with HWT_NARRATIVE contextual; water-contact checks
use HI_DOH_CWB; visibility uses SNORKEL_STORE/HWT_VISIBILITY. Current/persistent
hazard assessment uses attributed catalog characteristics plus explicitly scoped
synthetic premises supported by applicable NWS_MARINE or SNORKEL_STORE findings;
it does not assert that those providers supply direct current-speed measurements.
Catalog verification is never supplied by an environmental provider. Supplemental
reports cannot substitute for mandatory authoritative advisory checks. This
mapping permits no live access and makes no claim about verified real-provider
coverage or freshness. Additional mappings require explicit review.

The harness then checks which actual components a run requires: request handling,
specialist/tool adapters, independent evidence/policy/result validators, budget
controls, trace writing, and optional model interface. A missing component blocks
the applicable execution/assertions; a schema-valid fixture alone is not an
end-to-end acceptance pass. Runtime failures and trace-write suppression must
remain actual observable behavior under existing events, not replayed expected
traces. An optional LangSmith outage must not disable authoritative local tracing.

## 10. Approved acceptance criteria for the implementation

These are approved targets for future code, not tests run by this design change.

| ID | Required check and expected behavior |
|---|---|
| SH-T01 | v1 fixtures still load unchanged; unsupported/v2 inputs are rejected by the existing v1-only API |
| SH-T02 | New scenario preflight rejects bad versions, paths, JSON, references and unknown keys before dispatch |
| SH-T03 | Complete evidence profiles cannot drop a mandatory category; intentionally missing categories remain explicit gaps |
| SH-T04 | Unretrieved/rejected support and absent/check-incomplete premises never become sufficient evidence or PASS |
| SH-T05 | True applicable advisory beats favorable premises; A is excluded and never recommended in SC-004 |
| SH-T06 | SC-004 also requires B's eligibility/recommendation and count 1, so an empty result cannot pass |
| SH-T07 | Poor visibility permits MIXED only with all five §15 conditions; an unknown mandatory hazard still blocks eligibility |
| SH-T08 | Timeout/partial/unavailable/error scripts preserve observable failures and consume actual shared dispatch budgets |
| SH-T09 | Retry/fallback script availability cannot bypass one-per-origin/gap limits, source permissions, or total call caps |
| SH-T10 | Duplicate delivery consumes one invocation and reuses identities; no duplicate state/evidence effect |
| SH-T11 | Malformed payload is allowed only as declared fault injection, then must be rejected at the actual contract boundary |
| SH-T12 | Reverse specialist completion order preserves independent evidence/conflicts and keeps actual concurrency within two |
| SH-T13 | Runtime IDs bind to real dispatches; reused historical findings retain their original identity/provenance |
| SH-T14 | Application/model/adapter projections contain no expected values, selectors, expected paths or evaluator objects |
| SH-T15 | Missing captures/pointers fail active assertions; ALL_EQUALS is non-vacuous and booleans are not numeric values |
| SH-T16 | Blocked/disabled/partially blocked assertions are not counted as passing; active mandatory failure dominates aggregate results |
| SH-T17 | Fixture-invalid, evaluator-error, dependency-blocked, application failure and environmental abstention are distinguishable |
| SH-T18 | SC-012 has shared session, new investigation/revision, unchanged constraints, fresh budgets and immutable prior terminal state |
| SH-T19 | Injected source instructions cannot alter policies, script permissions, constraints, or the evaluator oracle |
| SH-T20 | Local trace-write failure stops dispatch/suppresses recommendations; no missing events are fabricated |

A reviewer must also compare authored scenario assertions with the original twelve
conditions/expected outcomes in acceptance §§17–22. These twenty checks supplement,
not replace, TC/TE/TS/TW/TR, CFG-T01–16, LG-T01–10 or the mandatory MVP gates.
Do not report virtual timing, scripted adapters, or a controlled decision stub as
successful genuine model-driven ReAct behavior.

## 11. Approved decisions and implementation sequence

All nine decisions below and acceptance checks SH-T01 through SH-T20 are
**APPROVED** by explicit user approval on November 18, 2026. This settles the
physical harness contracts. It does not approve a model/provider, live access,
real-world hazard criteria or application-code implementation.

| Decision | Approved disposition |
|---|---|
| SH-OD-001 | Separate harness definition, application projection and evaluator oracle as in §2 |
| SH-OD-002 | Add isolated v2 scenario package and explicit per-artifact versions; retain v1 compatibility |
| SH-OD-003 | Preserve TestScenario fields via typed source sets/reference resolution; post-terminal request sequence in script |
| SH-OD-004 | Adopt explicit evidence profiles, scoped boolean premises, validity rules and narrow MIXED permission; no final verdict inputs |
| SH-OD-005 | Adopt seven behaviors, dispatch-matched operations, virtual-time convention and narrow malformed-payload exception |
| SH-OD-006 | Bind templates only at actual retrieval; separate observed binding index; defer historical reuse representation |
| SH-OD-007 | Adopt closed target/operator/selector grammar, strict missing/cardinality semantics and independent expected files |
| SH-OD-008 | Resolve SC-005/008 status mismatch by split assertions; preserve existing logical statuses/outcomes |
| SH-OD-009 | Adopt preflight/capability gates and SH-T01–20; never treat unimplemented execution as a pass |

Following this design approval, a separate implementation request may proceed in this order:

1. Implement harness-format models, v2 loading/projections and evaluator validation
   with unit tests for invalid inputs and oracle separation. Keep existing v1 APIs.
2. Author complete scenario inputs/assertions, beginning with SC-004 and SC-010;
   keep missing execution capabilities and real-world classification BLOCKED.
3. Implement M1.2's bounded graph and trusted shared-budget controls, then the
   specialists/tools, evidence/safety evaluation, CLI lifecycle and local tracing
   according to the approved M1 sequence. Promote scenario runs only as actual
   dependencies become available and required assertions execute successfully.

Still deferred: production freshness/measurement normalization and hazard cutoffs,
model/provider activation and model retry/cost/token decisions, persistent sessions,
active-investigation interruption, and cross-investigation reuse storage. The
approved contracts make these limitations explicit rather than supplying framework
defaults or fixture-derived final answers.
