# M1.5-D — Request Interpretation and Candidate Selection Design

**Version:** 0.1 — Review draft  
**Status:** Proposed — awaiting human approval  
**Prepared:** November 19, 2026  
**Scope:** Request interpretation, normalized input validation, candidate selection,
and their session/execution boundaries  
**Authorization:** Documentation only. These proposals are not approved requirements
and do not authorize application changes, provider activation, or general CLI requests.

## 1. Purpose and authority

M1.5-C accepts trusted `NormalizedRequest` inputs and explicit field replacements.
The application still lacks a general natural-language interpretation boundary and
catalog selector. This proposal defines a bounded next implementation target while
preserving the Coordinator, Weather and Ocean roles, existing logical records,
deterministic eligibility enforcement, and synthetic-only M1 scope.

Approved sources remain authoritative:

| Source | Relevant requirements |
|---|---|
| [Product requirements](../requirements/01-product-requirements.md) §§3.1–3.4/10 | PR-001..006/011..016; OD-006 omitted-value behavior |
| [Architecture](../requirements/02-system-architecture.md) §§10.1–10.3/13.3 | Interpretation, verified catalog selection, scoped investigation and follow-ups |
| [Data schemas](../requirements/03-data-schemas.md) §§1.3/2/4/5/6 | Canonical records/enums, attribution, constraints, current revision and validated outcomes |
| [Agent/tool contracts](../requirements/04-agent-tool-contracts.md) §§3/4/7 | Scoped specialist requests/responses and tool permissions |
| [Safety policies](../requirements/05-safety-policies.md) §§14–17/22 | Eligibility, evidence applicability, hard constraints versus preferences |
| [Acceptance](../requirements/06-test-acceptance.md) §§11/17/22 | CLI behavior, SC-003 unsupported assessments and SC-012 context preservation |
| [Observability](../requirements/07-observability.md) §§3–5/10 | Actual operations, session/revision correlation and validated presentation |
| [Technical plan](m1-technical-plan.md) §§3–5/13 | Coordinator-assisted normalization and trusted candidate selection |
| [Configuration baseline](m1-configuration-baseline.md) §§5–10 | Provider-neutral work, 12 model/12 tool calls, timeouts and required tracing |
| [Schema mapping](m1-schema-contract-mapping.md) §§5/8/13/14 | One logical schema, identifiers and runtime adapters |
| [Fixture design](m1-synthetic-fixture-design.md) §§3/7/11/16 | Fictional catalogs, fixed clocks, independent expectations and follow-ups |
| [Execution design](m1-langgraph-execution-design.md) §§4/6–9/16 | Trusted nodes, clarification, iteration/budget enforcement and fresh investigations |
| [Session lifecycle](m1-session-lifecycle.md) §§3–11/14 | Post-terminal revisions, terminal integrity and deferred resumption |
| [Harness design](m1-scenario-harness-contract-design.md) §§1/2 | Application/driver/evaluator separation; no oracle-derived interpretation |

No approved specification is edited by this draft. Internal proposals and audit
records below are runtime metadata, not a seventh logical schema or additional
agent. The human approval record must identify which RI-OD decisions are accepted
and resolve RI-C01 before dependent implementation begins.

## 2. Current behavior and unresolved boundaries

| ID | Finding | Proposed treatment |
|---|---|---|
| RI-C01 | Architecture §10.2 filters unsupported activities before investigation; SC-003 requires Candidate Assessments showing A/E as UNSUPPORTED. `InvestigationState` requires assessed IDs to belong to its candidate set. Removing A/E entirely cannot satisfy those assertions. | Approve the assessment/dispatch set distinction in §7. No unsupported beach is dispatched or recommended. This clarification needs human review; neither source is silently rewritten. |
| RI-G01 | `SessionManager.start()` currently requires a normalized request; graph initialization creates the investigation and budget afterward. A live model called before that point would lack the investigation's shared budget/trace. | Add raw-request admission within the same investigation lifecycle, as specified in §3. Do not use an uncharged pre-parser model call. |
| RI-G02 | Existing JSON hard constraints all evaluate UNKNOWN; generic preferences have no deterministic meaning. Recognizing a new dictionary shape must not imply that it passed a policy. | Approve a small versioned interpretation vocabulary and independent evaluation in §5. Preserve legacy/unknown behavior. |
| RI-G03 | The graph's `NO_SELECTED_CANDIDATES` stop is not an accepted result-construction stop. A valid empty selection is not yet connected to a grounded abstention path. | Add the contextual validation branch in §8, rather than manufacture an assessment or report an environmental hazard. |
| RI-G04 | PR-002 mentions starting location, but the current normalized schema has no dedicated starting-location field. | Preserve it as attributed interpretation context; do not invent a logical field, hard restriction, distance or travel estimate. |
| RI-G05 | `follow_up()` marks supplied value replacements user-provided. A newly expanded daypart includes assumed precision, even when the user explicitly said “morning.” | Raw-request admission must carry trusted origin declarations, rather than automatically labeling all changed precision explicit. Existing explicit normalized APIs retain their behavior. |

RI-G findings are implementation gaps, not changes to approved requirements.
General input handling, source availability, complete agentic planning and full
scenario acceptance remain incomplete after this design work.

## 3. Execution and trust boundaries — RI-OD-001

Proposed flow for each initial request or post-terminal follow-up:

1. Trusted admission accepts the current user utterance and a detached inherited
   normalized context when applicable. Assign the session/revision, create a new
   investigation/trace and fresh shared budgets before any model dispatch.
2. INITIALIZING state preserves the new `original_request`. Unknown activity/time
   values remain unknown; no guessed activity or time fills a required field.
3. The Coordinator's normalization operation receives only the current utterance,
   inherited normalized values/origins, explicit reference clock, approved request
   rule profile, and a catalog-derived identifier/name/area summary.
4. An injected interpreter produces a structured proposal. Future live execution
   may use the Coordinator's model; deterministic tests use authored proposal
   callbacks. The proposal has no authority to dispatch, alter budgets or decide
   safety. No new parser/reviewer agent is created.
5. Trusted validation checks structure, recognized meanings, current-text origins,
   ambiguity, changes and inherited constraints. It resolves canonical activity,
   time and catalog identifiers and commits a validated normalized snapshot.
6. If material interpretation is unresolved, enter AWAITING_CLARIFICATION and ask
   concrete questions. No specialists, environmental calls or recommendations run.
7. Otherwise select catalog candidates using §7. The Coordinator plans only
   authorized investigation work; existing evidence/safety/result validation follows.

Every actual normalization model dispatch must reserve/dispatch/finish through the
**same** investigation BudgetManager later used by the Coordinator and specialists.
It counts toward 12 shared model invocations and the 30-second timeout, including
failed/malformed/timed-out attempts. It consumes no environmental tool invocation
and no Coordinator investigation iteration. No automatic model retry or model-based
repair loop is authorized. Local rule evaluation and catalog lookup consume neither
model nor environmental invocation budgets. Existing maxima remain unchanged.

The raw-input path must extend existing admission/graph initialization, not call
`SessionManager.start()` after an external normalization model call, create a second
investigation after normalization, or reset counters between phases. Session commit
checks must accept a changed normalized snapshot only through a trusted validation
receipt bound to this utterance, inherited revision, clock, catalog and rule profile.
A model-authored “validated” flag is not such a receipt. A deterministic request
validator can recheck retained inputs without making another model call.

Existing normalized component APIs stay available for explicit synthetic tests.
They do not become general language interfaces merely by accepting a string.

### Proposed internal interpreter interface

The injected interface consumes current text, inherited normalized values/origins,
admission identity, reference clock, pinned request-rule profile and catalog identity
summary. A model-neutral test callback and a future model adapter must implement
the same contract. The Coordinator owns this operation; the callback is not another
autonomous role.

An internal proposal contains these fields only:

- `changed_values`: proposed replacements for existing normalized **value** fields
  (activity, date/window, preferred area, experience, hard constraints and soft
  preferences). Omitted fields are not changes. None/empty lists propose explicit
  clearing where the existing field permits it.
- `source_spans`: proposed current-utterance references for changes, with field,
  optional list-entry index, start and end. These identify text to validate, not
  trusted semantic evidence by themselves.
- `removed_entries`: proposed hard/soft list-entry removals identifying a prior
  index and current-text span. The trusted validator must resolve the user's
  intended target and preserve all other entries; ambiguity rejects the removal.
- `unresolved_spans`: utterance fragments the interpreter cannot normalize. The
  validator independently determines whether they are mandatory/material.

These names describe a proposed internal transport, not a user-facing JSON patch
language or persisted logical record. Exact keys/types are to be validated strictly;
no arbitrary model-generated fields enter Investigation State. Full list replacements
must agree with validated additions/removals and retained entries. The interpreter
cannot set `original_request`, clarification verdicts, origins, clock, identifiers,
rule/profile versions, source permissions, assessment results or budgets.

Trusted validation returns an internal receipt containing the canonical
`NormalizedRequest`, field/entry origins, accepted changed fields, unresolved
limitations/questions, and binding references to admission/current text, inherited
revision, clock, catalog and request-rule version. Clarification fields are set by
this trusted operation. Rechecking a receipt uses those original inputs, not a
model-authored assertion that the request is valid. This is an in-process data-flow
boundary, not a cryptographic credential. Structural contract failure is operational;
supported structure with unresolved user meaning follows the clarification path.

## 4. Supported interpretation and time rules — RI-OD-002/003

All rules in this section are **proposed resolutions**, especially the new morning
hours. They are not inferred from existing fixture expected values.

| Input | Proposed interpretation |
|---|---|
| `swim`, `swimming` | SWIMMING |
| `snorkel`, `snorkeling` | SNORKELING |
| `SUP`, `stand-up paddleboarding`, `stand up paddleboarding`, `paddleboard` | SUP, consistent with SC-003's request |
| Multiple requested activities without a clear single target; generic “paddling”; unsupported surfing/kayaking | Clarification/supported-scope response; do not choose an activity silently |
| Explicit beginner/intermediate/advanced statement | Existing ExperienceLevel value; otherwise None, without assuming competence |
| Omitted date or missing usable time interval | Clarification; do not default to today, tomorrow or all day |
| `today` / `tomorrow` | Resolve once from the injected reference clock in Pacific/Honolulu, not the host clock/UTC calendar date |
| Unambiguous explicit calendar date and local AM/PM or 24-hour interval | Canonical date and aware `[start, end)` interval; validate consistency in Hawaii time |
| `morning` with a known date | **Proposed M1 default: 08:00–11:00 HST.** Mark the exact interval assumed, disclose it, and retain the user's daypart intent |
| `afternoon`, `evening`, ambiguous weekday/AM-PM, or another unconfigured daypart | Ask for an explicit date/time; do not invent another default |

The proposed morning default resolves a bounded portion of product OD-006. It is
chosen for a reviewable M1 scheduling convention, **not** an ocean-safety or provider
freshness rule. A reviewer may reject/change it. Existing fixture windows must never
be read as the normalizer's answer. The default would live in one approved,
versioned request-rule profile and be tested independently of scenario scripts.

Initial language support is a bounded English subset; this is not a claim of
arbitrary-language/date-expression coverage. The validator accepts explicit dates
only when their calendar interpretation is unambiguous. An explicit ISO interval
with an offset is converted consistently to Hawaii time; an ambiguous timezone
abbreviation requests clarification. Naive serialized timestamps are rejected.

Do not silently clip a requested interval, roll an elapsed “today morning” into
tomorrow, or extend it to fit source evidence. Under the proposed planning input
policy, an interval that has already started at the reference clock requests a
current/future interval. No new maximum forecast horizon is introduced. Missing
future source coverage remains an evidence limitation, not permission to change time.

Relative dates are resolved only for fields explicitly changed by the current
utterance. “Near Napili instead” retains the earlier absolute date/window, even
when the reference clock has advanced. “Tomorrow morning instead” resolves anew
using the new investigation's clock. Explicit time changes without a new date may
retain the inherited date when unambiguous; conflicting date/window changes clarify.

### Origins and semantic validation

Keep the exact current utterance in `original_request`; preserve prior utterances
only through their already retained investigation records. Retain field/entry
origin metadata alongside the normalized snapshot: current-text span, inherited
value, or named profile default. Source spans use zero-based Unicode code-point
offsets with an exclusive end into the current utterance. They are audit references,
not model reasoning or a proof of semantic correctness.

`user_provided_fields` remains a field-level declaration. A derived morning
interval is assumed precision; an explicit “8 a.m. to 11 a.m.” interval is explicit.
Relative “tomorrow” expresses an explicit date intent with a recorded deterministic
clock derivation. Initial empty lists and absent optional values do not become
invented preferences. Hard constraints and soft preferences have no default entries.

Pydantic validity and a quote containing a keyword do **not** prove that a model
understood negation, scope or obligation. Trusted validation must check the supported
clause rules and cross-field consistency. Contradictory targets, unresolved mandatory
clauses or meaning beyond those rules require clarification. Adversarial examples
and human-authored expected interpretations test this boundary; a second model or
an unbounded semantic-validation claim does not replace it.

## 5. Locations, constraints and preferences — RI-OD-003/004

Resolve region/locality labels only against the current validated catalog, with
case folding, trimmed/collapsed whitespace and the documented region underscore/
space spelling equivalence. Beach names and aliases resolve only to actual catalog
records. Do not invent geographic aliases, fuzzily choose among matches, strip
meaningful name distinctions, merge beaches or use model/world knowledge to add IDs.
Ambiguous names require clarification when material. Unknown soft preferences can
remain unfulfilled with a limitation; unknown mandatory targets block investigation.

| Phrase meaning | Proposed treatment |
|---|---|
| `near Kihei`, `prefer Napili`, `ideally West Maui` | Soft area preference in `preferred_area`; never a radius, travel estimate or hard filter |
| Activity-location clause `in South Maui`, `only South Maui`, `must stay in South Maui` | Hard geographic target in a recognized LOCATION_RESTRICTION descriptor |
| `at <unique catalog beach>` as the requested activity destination | Hard named destination, resolved to its canonical beach ID |
| `I'm staying in Kihei` | Starting-location context only; do not promote it to a requested-area restriction or preference |
| `prefer calm water` | Explicit soft CALM_WATER preference; no assumed numeric definition |
| `I won't go in waves`, `must be calm`, or another unreviewed environmental requirement | Preserve as a hard unresolved statement and ask clarification; never reuse a soft preference interpretation as a PASS |

The “in South Maui” rule is a proposed interpretation of SC-003, not a rule that
every occurrence of “in” is a restriction. Clause role matters. A soft cue remains
soft, and starting-location statements do not scope the activity destination.
For an unconfigured “near <beach>” relationship, retain the soft statement as
uninterpreted rather than replacing that beach with its whole locality or inventing
NEARBY_AREA. No coordinate radius, route time or closest-beach ranking is proposed.

Minimal proposed JSON payload vocabulary within the **existing** generic lists:

| List | Shape | Meaning and independent evaluation |
|---|---|---|
| hard_constraints | `{"kind":"LOCATION_RESTRICTION","scope":"REGION","value":"SOUTH_MAUI"}` | REGION uses the existing region value; LOCALITY uses a unique catalog label; BEACH uses a resolved beach ID. Trusted catalog facts establish match/nonmatch, subject to provenance. |
| soft_preferences | `{"kind":"CALM_WATER"}` | Retain the preference. Alignment stays UNKNOWN until a separately approved evidence interpretation can establish it; favorable suitability alone does not prove calm water. |
| Either list | `{"kind":"UNINTERPRETED","text":"exact user fragment"}` | Preserve its original hard/soft character. A material hard statement causes clarification; a soft one may remain UNKNOWN with disclosure. |

Recognized shapes have exact keys/types and allowed scope values under the proposed
request-rule profile `m1-request-rules-0.1`. These are proposed descriptor values,
not additions to approved top-level enums. Unknown keys, `PASS`/`eligibility` claims,
or arbitrary legacy dictionaries never acquire authority from their spelling.
An unknown model-proposal kind or malformed recognized shape is a contract failure;
the interpreter must use UNINTERPRETED for user meaning it cannot express. Existing
opaque normalized component inputs retain their current UNKNOWN behavior.

After approval, the safety evaluator must independently check recognized geographic
constraints against the current candidate and attributed catalog values, producing
existing ConstraintResult PASS/FAIL/UNKNOWN fields. The model cannot supply verdicts.
Unknown or unsupported semantics stay UNKNOWN and prevent eligibility when hard.
Catalog geographic matches never establish environmental suitability.

Starting location is preserved in original text and attributed runtime interpretation
context, without adding a logical state field. Using it for routing/proximity, or
promoting it to a persistent normalized field, requires a separate reviewed design.
No new environmental FactType, hazard threshold, “calm” conversion or policy override
is authorized by this descriptor vocabulary.

## 6. Post-terminal revisions — RI-OD-007

An interpreter proposes changes, not a wholesale replacement of inherited context.
Trusted merge accepts only explicitly supported changes and removals from the
current utterance. It preserves omitted values, including activity, absolute date/
window, experience and all applicable hard/soft entries. Changing activity rechecks
applicability; it does not silently discard an inconvenient constraint.

Removal must identify its intended target unambiguously. “Anywhere is fine” may
clear an existing **soft** area preference; it does not erase “only South Maui.”
“Remove that restriction” with several possible targets clarifies. A hard location
restriction and an outside-area soft preference can coexist; the hard restriction
wins. Mutually incompatible hard restrictions clarify before dispatch.

The trusted merge supplies complete revised lists to the existing normalized API,
with updated origin declarations. No public add/remove constraint language is
introduced. The future raw path must distinguish explicit intent from assumed
precision in changed fields, addressing RI-G05.

The same session ID, next revision, new investigation ID and fresh budgets remain
mandatory. Prior results/findings/assessments are not authority for the new request.
Active revision, cancellation, clarification resumption, persistence and
cross-investigation evidence-reference storage remain deferred. AWAITING_CLARIFICATION
stays nonterminal with no recommendations; a user can begin a fresh session with
a complete request. This proposal does not silently implement SL-OD-006.

## 7. Deterministic catalog selection — RI-OD-005/006

The selector receives a validated normalized request, its trusted interpretation
audit, a detached catalog snapshot and the reference clock. It receives no driver
script, expected assertion, expected beach list or model-authored eligibility verdict.
It verifies the same catalog provenance rules used by evidence/safety validation:
VERIFIED status, required fields, nonfuture verification/access dates, and supporting
references for core/material attributes. Reuse or extract the existing trusted
catalog checks; do not create a weaker parallel definition or new minimum optional
attribute/reverification-age policy.

The current `_catalog_reasons()` helper also reports activity mismatch. Separate
that finding from structural/provenance failures when extracting shared checks:
ACTIVITY_UNSUPPORTED must not erase a verified record from the proposed assessment
set before its unsupported assessment is recorded.

**Proposed resolution of RI-C01: distinguish these runtime sets.**

- Assessment set: verified, attributable records matching explicit hard geographic
  targets, including records whose activity support must be recorded as UNSUPPORTED.
  Store these IDs in `InvestigationState.candidate_beach_ids` so actual assessments
  can reference them. Selection itself assigns no CandidateAssessment eligibility.
- Investigation set: the assessment set restricted to the requested supported
  activity. Only this subset may receive specialist/tool work. Initialize remaining
  investigation work from this set; unsupported records consume no retrieval calls.
- Audit-only records: disabled, unverified/unattributable or outside hard geographic
  scope. Retain their catalog selection reasons; do not invent Candidate Assessments
  for records outside the state candidate set or relabel selection reasons as hazards.

This interprets the architecture's filtering as filtering **dispatch**, while
preserving actual unsupported assessments required by SC-003. It is a proposed
clarification of state membership, not a second candidate schema. Human approval
is required. Before implementation, review all affected selector, merge, assessment
and acceptance assertions against that interpretation.

For “SUP in South Maui,” the assessment set is A/B/E and the investigation set is
B under the common fictional catalog. Trusted catalog-based assessment records
A/E as UNSUPPORTED; environmental and safety checks must still establish whether
B becomes ELIGIBLE. Outside-scope C/D receive selection audit reasons, not fabricated
unsafe-condition claims. Specialist authorization must enforce the investigation
subset as well as the state set; merely checking state membership would be too broad.

For a soft Kihei preference with snorkeling, retain all verified geographic options:
investigable A/B/C/D, with E retained for unsupported assessment. This allows Napili
or another supported area to remain available when a preferred location cannot qualify.
The existing five-beach catalog is an M1 fixture, not a newly fixed real-beach list.

Return all matching IDs without a three-candidate cap. Three is the **final
recommendation** maximum. Proposed repeatable planning order puts exact preferred
region/locality matches first, then other supported records, with beach-ID order
within each group. This is investigation ordering, not recommendation ranking,
evidence quality, safety or a quantitative proximity claim. The Coordinator still
chooses justified work within approved budgets and must disclose unevaluated limits.

Keep a detached selection audit with snapshot/rule references, selected assessment
and investigation sets, exclusion reasons, and catalog source/field references.
No new persisted schema, autonomous role or trace event enum is required. A local
snapshot fingerprint may be computed from application inputs; evaluator-owned
artifact digests are not an application dependency.

## 8. Outcome and trace integration — RI-OD-008/009

| Situation | Proposed outcome |
|---|---|
| Unsupported/ambiguous activity, material missing time, conflicting hard targets, or unresolved mandatory interpretation | AWAITING_CLARIFICATION; no result or environmental dispatch |
| Valid catalog/request, but no supported investigable location meets hard geography/activity constraints | Verified NO_RECOMMENDATION / NO_ELIGIBLE_CANDIDATES; ABSTAINED with catalog reasons, not a hazard claim |
| Supported candidates, unresolved environmental evidence after authorized work | Existing evidence/safety assessment and explained abstention behavior |
| Model timeout/malformed operational response, unreadable/malformed catalog, or broken required tracing | Sanitized operational failure; no invented request context or environmental finding |

Zero-candidate result construction must validate a current selection audit rather
than trust an empty tuple. Recompute selection from the same catalog/request/profile
and check the absence of supported candidates. Retain actual unsupported assessments
when present. When no assessment exists, explain the verified catalog/scope boundary
without saying a nonexistent candidate was assessed. Add an explicit trusted stop
and contextual Result Validator branch using existing outcome/reason enums; do not
force `NO_SELECTED_CANDIDATES` through an unrelated result template.

A failure before activity/window is known may retain FAILED operational diagnostics
with `result=None`, as current code does. Do not fabricate those required result
fields to serialize an ERROR. A structurally valid proposal describing ambiguity is
distinct from an operationally malformed model response.

Required operations use existing REQUEST_RECEIVED, REQUEST_NORMALIZED,
REQUEST_REVISED, CLARIFICATION_REQUESTED and CONTRACT_VALIDATED events. Record the
actual reference clock, request-rule/profile version, field origins, validated
changes, selection sets/reasons, source references and call counters in existing
structured details. Every event remains bound to its investigation/session/revision.
No event should assert successful normalization before trusted validation commits it.
Preserve initial admission and later normalization as separate actual operations;
current component normalization events do not prove that a live model ran.

Authoritative local JSONL is a prerequisite for a general model-backed runtime.
Memory recorders remain isolated component seams. Provider activation also remains
subject to the configuration baseline's review; this document selects no provider
or model and enables no remote tracing. Store no private chain-of-thought, full
unnecessary conversations, credentials or raw sensitive exception payloads.

External source content, prior recommendations, scripts and expected results are
not normalization instructions. An interpreter cannot set candidate pools, invent
identifiers, change provider permissions, supply outcome verdicts/budget overrides
or write fields outside its proposal contract. A proposed named-destination ID must
resolve through the trusted catalog. Generic source-injection text cannot mutate
user context.

## 9. Acceptance design

These are proposed tests, not executed scenarios or a claim of acceptance PASS.
Test inputs and expected interpretations must be authored independently. Model
stand-ins emit proposals without accessing expected assertions. Stateful tests
observe actual graph operations/counters; selector audits alone cannot stand in
for required Candidate Assessments.

Proposal-returning callbacks make no provider requests and must not fabricate
provider-call events or real-model usage. Separate adapter/budget component tests
may exercise clearly identified test doubles for dispatch/timeout accounting;
they do not establish provider activation or complete agentic acceptance. Do not
extend the existing BehaviorScript format to authorize model-call mocking/retries
or configure a fake provider to bypass the disabled live-model setting.

| ID | Case | Required observation |
|---|---|---|
| RI-T01 | Supported activity aliases, absent experience | Canonical activity, original text preserved, no guessed skill |
| RI-T02 | Unsupported/multiple activities or ambiguous “paddling” | Clarification; zero environmental calls |
| RI-T03 | Reference `2026-11-17T00:30:00Z`, “tomorrow morning” | Hawaii reference date Nov 16; target Nov 17 08:00–11:00 HST; interval explicitly tagged assumed |
| RI-T04 | Missing date/time, unconfigured afternoon, invalid/elapsed/conflicting interval | Concrete clarification; no invented/rolled/clipped interval |
| RI-T05 | Explicit 08:00–11:00 interval | Explicit precision; no daypart-default claim |
| RI-T06 | “near Kihei” versus “only South Maui” and activity-location “in South Maui” | Soft versus hard rules, including clause-role validation |
| RI-T07 | “I'm staying in Kihei” alone | Preserved starting context; no invented destination preference/restriction |
| RI-T08 | Unknown/ambiguous aliases or unsupported named-beach nearness | No model-invented ID/radius; mandatory ambiguity clarifies, optional meaning remains disclosed UNKNOWN |
| RI-T09 | SUP in South Maui under common catalog | Assessment set A/B/E; dispatch only B; actual A/E UNSUPPORTED assessments; no assumed B eligibility. Blocked on RI-C01 resolution. |
| RI-T10 | Soft Kihei preference with available West Maui support | Other supported areas retained; no padding or early three-record truncation |
| RI-T11 | NEEDS_REVIEW/DISABLED/future-dated/unattributable catalog entry | Audit-only; no authorized retrieval or recommendation using unverified support |
| RI-T12 | Dictionary claiming PASS/ELIGIBLE, unknown model-proposal kind, or malformed recognized shape | Contract rejection, never a trusted verdict; valid UNINTERPRETED stays unresolved and old opaque normalized dictionaries remain UNKNOWN |
| RI-T13 | Calm-water preference with favorable assessment but no calm-water interpretation | UNKNOWN preference alignment and disclosure; no invented calm-water measurement or threshold |
| RI-T14 | Post-terminal “near Napili instead” after the clock advances | Same session, next revision, new investigation/budgets; original absolute date/window, experience and constraints retained |
| RI-T15 | Explicit time/daypart change or removal with several possible targets | Supported replacement with correct assumed precision, or clarification; no silent hard-constraint loss |
| RI-T16 | Fresh empty selection and a tampered/stale selection audit | Grounded catalog abstention for the former; invalid audit rejected; no fake hazard/assessment |
| RI-T17 | Shared-ledger adapter accounting component test followed by later work | One investigation/ledger, 12-model-call cap and no phase reset; test doubles identified; no extra Coordinator iteration solely for normalization |
| RI-T18 | Timeout, malformed proposal or required trace failure during normalization | Only dispatched attempts charged; no automatic repair/retry; no dispatch when required recording fails beforehand; further dispatch/publication blocked appropriately |
| RI-T19 | Negation, unrepresented mandatory clauses, source instructions or injected IDs/budget settings | Trusted scope/origin guards; no silently discarded hard meaning or source-control authority |
| RI-T20 | Existing normalized APIs, session demo and old opaque dictionaries | Backward-compatible component behavior and UNKNOWN semantics; no fake model invocation |

These supplement PR-001..006/011..016, BC/CA/IS/RR contracts, SC-003 and SC-012.
They do not replace complete independent scenario assertions, request-specific
source behavior, full agentic planning, or authoritative trace acceptance.

## 10. Decisions for human review

All decisions remain **PROPOSED**. Existing approved limits/roles/guards are not
reopened by the recommendations.

| ID | Recommended decision |
|---|---|
| RI-OD-001 | Admit raw work and initialize one investigation/budget/trace before model normalization; keep provider-neutral stand-ins for component work. |
| RI-OD-002 | Use the injected Hawaii clock, explicit missing-value clarification, and the disclosed **08:00–11:00 HST morning default**; other dayparts require explicit times initially. |
| RI-OD-003 | Approve bounded aliases and clause-based geographic meaning; distinguish destination restrictions, soft areas and starting context without distance inference. |
| RI-OD-004 | Approve only LOCATION_RESTRICTION, CALM_WATER and UNINTERPRETED descriptor shapes under a versioned request profile; evaluate recognized hard geography independently; preserve other UNKNOWN semantics. |
| RI-OD-005 | Resolve RI-C01 with separate assessment/state and supported dispatch sets, preserving actual unsupported assessments while filtering external work. |
| RI-OD-006 | Keep the full matching pool, exact-area planning preference and stable ID tie order; no three-candidate selection cap or new recommendation-ranking policy. |
| RI-OD-007 | Validate current-utterance deltas/removals and origin declarations; preserve inherited absolute values; defer active clarification/resumption and evidence reuse as before. |
| RI-OD-008 | Add independently grounded empty-selection abstention and preserve technical-error/clarification separation. |
| RI-OD-009 | Treat structured proposals and quote spans as untrusted evidence of interpretation, enforce bounded semantic checks, and use existing events for auditable trusted commits. |
| RI-OD-010 | Approve the staged implementation boundaries below, with general runtime activation still gated on provider/tracing review. |

## 11. Implementation sequence after approval

Recommended next increment: **M1.5-E — deterministic request validation and catalog
selection components**. Implement the approved rule profile, proposal-validation
interface, explicit normalized follow-up merge and selector/audit using authored
synthetic interpreter outputs. Integrate recognized geographic constraints only
with an independent catalog-based check; leave other payloads UNKNOWN. Keep code
compatible with the approved logical shapes and existing normalized component APIs.
Implement the applicable RI-T component checks without exposing a new general CLI.

A later, separately authorized integration increment should adapt raw session/graph
admission, shared model accounting, trusted normalization receipts, selection scope
authorization and the zero-candidate Result Validator path. It must address RI-G01,
RI-G03 and RI-G05 explicitly; a thin pre-parser around today's demo is insufficient.

General natural-language CLI execution requires authoritative JSONL, a separately
reviewed provider/model integration, real Coordinator planning within synthetic M1
sources, appropriately authored tool behaviors and independent scenario execution.
Do not infer those capabilities or an M1.5/M1 acceptance PASS from component tests.

This proposal changes no logical schema fields or top-level enums. Future changes
to approved policy, harness or schema versions must be reviewed rather than silently
relabelled. The request profile's own version identifies its proposed meanings and
defaults. Final beach activation policy, real provider mappings/freshness thresholds,
environmental “calm” criteria, detailed recommendation ranking, session persistence
and evidence-reference storage remain outside this design's decision scope.

**Approval record:** None. Record explicit human approval and any amendments here
before treating accepted decisions as an approved implementation source of truth.
