# M1.5-E — Deterministic request validation and catalog selection

This increment implements the component scope of the approved
[M1.5-D design](../implementation/m1-request-interpretation-and-candidate-selection-design.md)
§11: the pinned rule profile, authored proposal interface/validation, normalized
follow-up merge, selection/audit and independent geographic-constraint checks.
The existing logical schemas, approved specifications, fixtures, dependencies,
runtime limits and provider settings are unchanged.

## Components and example

`interpretation` exports `RequestContext`, `InterpretationProposal`, `SourceSpan`,
`RemovedEntry`, `TextSpan`, `ValidatedRequest`, `RequestRuleProfile`,
`validate_request`, `verify_request`, `interpret_request`, `select_candidates` and
`verify_selection`. These are internal transport/audit components, not a seventh
logical schema, standalone agent or new CLI input format.

The following runs locally from the repository root after `uv sync --locked`:

```python
from datetime import datetime
from hawaii_activity_forecaster.fixtures import load_fixture_inputs
from hawaii_activity_forecaster.interpretation import (
    RequestContext, select_candidates, validate_request,
)

text = "Swim tomorrow afternoon."
context = RequestContext(
    original_request=text,
    reference_time=datetime.fromisoformat("2026-11-16T09:00:00-10:00"),
    catalog=load_fixture_inputs("fixtures").catalog,
    session_id="component-session", investigation_id="component-investigation",
)
proposal = {
    "changed_values": {
        "activity": "SWIMMING", "target_date": "2026-11-17",
        "target_time_window": {
            "start": "2026-11-17T12:00:00-10:00",
            "end": "2026-11-17T16:00:00-10:00",
        },
    },
    "source_spans": [
        {"field": "activity", "start": 0, "end": 4},
        {"field": "target_date", "start": 5, "end": 13},
        {"field": "target_time_window", "start": 14, "end": 23},
    ],
}
receipt = validate_request(proposal, context)
assert not receipt.request.clarification_needed
assert receipt.assumed_fields == {"target_time_window"}
assert receipt.assumption_disclosures
selection = select_candidates(receipt, context)
assert len(selection.investigation_candidate_ids) == 5
```

This example's IDs are supplied trusted component metadata, not proof that a graph
investigation or trace was created. No model/tool work, events or recommendations
are produced. Runtime admission remains a future integration responsibility.

`interpret_request(context, interpreter)` provides the same boundary with an
authored **synchronous** proposal callback. The callback receives a frozen
`InterpreterInput`: current text/clock/identity/profile, immutable catalog identity
summary, inherited origin declarations and a detached inherited request. It receives
no driver script, source responses, expected assertions, policy verdicts or previous
recommendation. Callback errors and invalid input/proposal errors are sanitized.
No SDK, retry, model accounting or remote tracing is installed by this seam.

## Validation rules and supported language

The strict proposal shape permits only `changed_values`, `source_spans`,
`removed_entries` and `unresolved_spans`. Change keys are limited to existing
normalized value fields. Runtime identifiers, budgets, original text, clarification
verdicts and eligibility cannot be supplied by a proposal. Bounds and types use
Unicode code-point offsets; source spans must support the relevant field/entry.

Independent clause checks recompute supported meanings instead of trusting an
enum, quoted keyword or model-supplied PASS. New descriptors have exact approved
shapes; malformed/unknown proposal kinds fail. Known current-text changes must be
represented consistently. Unresolved mandatory fragments remain hard, preserve
their text and request clarification; unresolved optional preferences may remain
UNKNOWN with limitations. Unsupported material language never silently authorizes
selection. The original utterance is retained exactly.

Supported clauses include the approved activity aliases; today/tomorrow, explicit
ISO dates and full English month/day/year dates; named morning/afternoon periods;
unambiguous local AM/PM or HH:MM intervals; and offset-aware ISO intervals. The
Hawaii clock is injected. Dayparts remain assumed precision; explicit hours override
them. Omitted dates/hours, unconfigured evening periods, ambiguous intervals,
conflicting dates or intervals already started at the reference clock clarify.
Requested intervals are not clipped, extended or rolled to another day.

Catalog region/locality comparisons allow case folding and whitespace normalization.
Only region labels receive underscore/space equivalence. Beach names/aliases retain
meaningful distinctions; no fuzzy matching, diacritic stripping, merged identities,
new geographic mappings, radii or travel times are inferred. Unknown/ambiguous hard
locations clarify. An unknown soft statement can be retained as UNINTERPRETED
without replacing a different, unmentioned preference.

The clause checker is a conservative bounded-English verifier, not a general NLP
parser. Polite/connective words and the documented supported clauses are accepted;
uncovered words/clauses ask for restatement. Complex negation, alternative targets,
unconfigured time expressions or unsupported environmental requirements may clarify
rather than be guessed. This does not establish unrestricted semantic validation
or a working model-driven Coordinator. Future changes to those meanings must stay
within the approved profile or receive design review.

The rule profile is pinned to `m1-request-rules-0.1`; hours are fixed at 08:00–11:00
and 12:00–16:00 HST. It adds no AppConfig/environment options or financial/model
limits. Validator exceptions contain controlled messages, not raw proposal values,
credentials or callback stack text.

## Follow-ups and receipt ownership

For a refinement, `RequestContext.inherited` is the owning controller's prior
receipt, with the same session, new investigation ID, next revision and an attested
`prior_status` of COMPLETED, ABSTAINED or FAILED. Omitted normalized fields and
applicable hard/soft entries are retained. Geographic-only updates keep absolute
times even when the clock advances. New dayparts resolve against the new clock;
date-only changes retain inherited hour precision. Elapsed inherited windows still
clarify rather than move silently.

Only unique, explicitly identified removals are accepted, with exact prior indices
and current-text references. Retained list origins are reindexed. “Anywhere is fine”
clears the soft area, while hard restrictions remain. An activity change cannot
erase constraints. Starting-location context carries its original investigation
reference, never becoming a destination restriction or inferred preference.

Receipts retain immutable serialized normalized/proposal snapshots, frozen origin
metadata, limitations and starting context. Accessing `.request` returns a fresh
Pydantic snapshot. `verify_request(receipt, context)` reconstructs the interpretation
and compares the receipt against the actual supplied text/identity/revision/clock,
catalog, inherited context and rule profile. Mutated proposals, outputs or current
contexts are rejected; profile/identity/clock rebinding is not accepted.

These are in-process data-flow checks, not credentials or a cryptographic assertion
that a prior investigation completed. The caller must supply genuine controller-owned
history/status. Pending clarification cannot be resumed through this API. An actual
FAILED terminal investigation can receive a new interpretation using retained
context; callers must not relabel AWAITING_CLARIFICATION as FAILED to bypass the
terminal-only lifecycle. No SessionManager/graph admission behavior is changed here.

## Selection and safety evaluation

`catalog.py` extracts the existing catalog status/date/attribute-attribution checks
for shared use. Evidence validation preserves its former activity-support checks;
selection separates that mismatch from invalid provenance. No new required optional
attribute, minimum verification age, numeric proximity rule or catalog version
envelope is invented.

`CandidateSelection` retains two ID sets and a separate planning order:

- `assessment_candidate_ids`: verified, attributable records satisfying recognized
  hard geographic restrictions, including activity-unsupported records.
- `investigation_candidate_ids`: the supported-activity subset; no three-record cap.
- `planning_order`: exact preferred-area matches first, then other supported IDs,
  using stable beach-ID order within each group. This is not recommendation rank.

Audit decisions retain selection reasons and declared catalog source metadata,
including access/verification dates and supported fields. Source declarations are
not all accepted evidence: selection independently recomputes usable attribution at
the reference clock. Disabled, unverified, future-dated or unattributable records
stay audit-only. Hard geography is never replaced by soft preference.
`verify_selection` recomputes all sets, ordering, reasons, attribution and digest;
an empty audit is valid data, not a fabricated environmental finding or result.

The common SUP/South Maui example yields assessment A/B/E and investigation B.
A component test separately invokes real evidence/safety evaluation: A/E become
UNSUPPORTED, while B remains NEEDS_INVESTIGATION without environmental evidence.
The selector itself creates no Candidate Assessments or eligibility verdicts.

Safety evaluation now independently checks exact LOCATION_RESTRICTION descriptors
against current attributed catalog facts. Match/nonmatch gives PASS/FAIL; unknown
semantics or unverified facts give UNKNOWN. Model-supplied verdict keys never pass.
Verified hazards still exclude even when geography passes, and missing environmental
evidence still prevents eligibility. Passed geography does not request unnecessary
user clarification when more environmental investigation is needed.

CALM_WATER alignment remains UNKNOWN. Its explanation/disclosure survives assessment
and existing controlled result construction; favorable suitability is not interpreted
as calm water. Other legacy opaque hard/soft payloads retain their former UNKNOWN
behavior. No new hazard FactType, environmental threshold or safety exemption is added.

## Verification and remaining integration

```bash
uv sync --locked
uv run --locked pytest tests/test_request_validation.py tests/test_request_followups.py tests/test_candidate_selection.py tests/test_location_constraints.py
uv run --locked pytest
uv run --locked hafi --version
uv run --locked hafi demo session --fixtures fixtures/scenario-pack-v1
```

Interpretation, merge and selection checks exercise the component portions of
RI-T01..16 and RI-T19..22:
aliases, injected clocks/defaults, explicit overrides, source/meaning tampering,
unknown clauses, locations/origins, exact removals, immutable history, separate
candidate pools, catalog attribution, independent constraints and partial-window
evidence. Candidate audit checks do not replace required assessments. No authored
expected value is read by the callback, clause checker or selector. RI-T14's real
raw-session/budget lifecycle and RI-T16/22's complete public outcome workflows are
not established by these unit/component tests.

Raw session/graph admission, shared model adapter/accounting (RI-T17/18), trusted
receipt publication in the graph, enforcement of both selection sets at dispatch,
the zero-candidate Result Validator path (full RI-T16), and full result/CLI afternoon
workflows remain separate integration work. The existing graph does not consume
selection audits; returning an ID set is not permission to dispatch that set.
Memory/component data is not authoritative JSONL. No general natural-language CLI,
provider activation, source integration or full scenario acceptance is enabled.
SC-004/SC-010 execution readiness remains BLOCKED; SC-003/SC-012 acceptance is not
claimed by the component checks.

Final validation: `uv sync --locked` succeeded; **1,038 tests passed in 13.04s**
on Python 3.14, including **126 new component checks**. The 13 existing upstream
LangSmith deprecation warnings remain. The documented Python example executed,
the installed console version and module startup succeeded, and the full suite
retained existing synthetic CLI demo coverage. Python 3.12 syntax parsing passed
for all seven new modules (this is not a separate Python 3.12 runtime test).
All 22 relative documentation links/code fences and `git diff --check` passed.
Approved specifications, fixture artifacts, pyproject.toml and uv.lock are unchanged.

No new specification conflict was found. The approved RI-C01 assessment/dispatch
distinction is implemented at the component boundary, while RI-G01/03/05 remain
integration obligations. Active clarification resumption, persistent profiles,
evidence-reference reuse and detailed recommendation ranking remain deferred.

Recommended next increment: **M1.5-F — raw request/session graph integration**,
with shared-budget/trace admission, receipt validation, selection-scope enforcement
and grounded empty-selection outcomes. Live model/general CLI activation still
requires the separately reviewed provider and authoritative tracing gates.
