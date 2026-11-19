# M1.5-C — Session lifecycle and post-terminal follow-ups

This increment implements the approved session-lifecycle specification's
post-terminal scope (SL-001..008; SL-T01..04/06..09), execution-design §§6/16,
configuration-baseline §6.2, product PR-004, architecture §13.3, and trace request
revision semantics. Approved requirements, architecture/implementation specifications,
logical schemas, fixtures, dependencies and execution limits remain unchanged.

## Runtime API

`orchestration.SessionManager` is an in-memory trusted controller. It supplies:

- `start(request, user_provided_fields=..., run=...)`: admit one initial
  `NormalizedRequest`; session revision starts at one.
- `follow_up(original_request, changes=..., run=...)`: admit a new interpretation
  only after COMPLETED, ABSTAINED or FAILED. Increment the revision and preserve
  omitted normalized fields.
- `session_id`, `request_revision`, `current`, `investigations`: read-only runtime
  metadata and detached snapshots of request context and returned investigations.
- `close()`: end admission after the runner returns. Closing never changes an
  investigation's status or cancels executing work.

Each async runner receives a frozen `SessionRequest` admission. Its `.request`
property returns a fresh validated `NormalizedRequest`. The runner selects scoped
candidates and uses the existing graph with `session_request=admission`:

```python
from hawaii_activity_forecaster.demo import run_demo
from hawaii_activity_forecaster.orchestration import SessionManager

session = SessionManager()

async def execute(admission):
    # Explicit synthetic example only; real normalization/selection is deferred.
    output = await run_demo(
        "advisory", "fixtures/scenario-pack-v1", session_request=admission,
    )
    return output.report

# Inside an async function, with a caller-validated normalized request:
# first = await session.start(request, user_provided_fields={...}, run=execute)
# second = await session.follow_up(
#     "Prefer Wailea instead", changes={"preferred_area": "Wailea"}, run=execute,
# )
```

`SessionRequest` is runtime admission metadata, not a seventh logical schema,
persisted session record, graph checkpoint or credential. Its normalized payload
is retained as private immutable bytes; callers cannot mutate it through nested
lists. Existing graph APIs remain compatible without session admission and default
to revision one. Passing mismatched request/session metadata is rejected before
events or dispatch. Graph invocations always create new UUID investigation IDs;
no graph API accepts a prior Investigation State for resumption.

The manager checks returned report identity, revision, normalized scope, terminal
or clarification status, closed budgets/counters and result correlation before
retaining history. It returns deep copies, so caller-owned reports cannot alter
previous terminal investigations. The Result Validator and presentation layer
remain responsible for independent grounding checks; session admission does not
replace them or establish authoritative persisted events.

## Request changes and origin declarations

The input boundary deliberately uses existing normalized request fields. It does
not parse natural language, infer proximity/travel times, add a constraint DSL,
choose a model, or turn opaque JSON constraints into passing safety checks.

The caller identifies initially user-provided value fields with
`user_provided_fields`. Populated undeclared fields are tracked as assumptions.
Declarations are at normalized-field granularity, attested by the trusted
normalizer/caller, and recorded separately from the logical request. Nested mixed
origins or semantic normalization of constraint payloads are not inferred here.
An explicit follow-up replacement marks that field user-provided; unchanged origin
declarations remain intact. Preferences never move into hard constraints.

`changes` names only existing normalized fields, excluding `original_request`
(supplied separately), runtime identity, findings and assessments. Values are
validated before admission. Unknown or invalid keys/values do not increment the
revision, dispatch work or replace context. `None` explicitly clears nullable
values, while `[]` explicitly replaces a list with an empty list. Nonempty lists
are whole-field replacements. Removing individual constraints requires the trusted
caller to supply the intended complete list; no add/remove patch language is added.

All omitted values are preserved, including activity, date/window, experience,
geographic preference, hard constraints and soft preferences. The caller must
provide coordinated updates when changing both date and window: conflicting
calendar date versus the window's Hawaii start date is rejected before admission.
This is an admission consistency guard, not a natural-language interpretation rule.

Missing activity/window or declared clarification produces AWAITING_CLARIFICATION
with retained context and questions. It produces no result, assessment, iteration,
model call or environmental call. Unresolved questions also preserve this guard.
Active clarification resumption remains deferred under SL-OD-006 and execution
design §6.3. A subsequent follow-up cannot bypass this nonterminal status; the user
may end that session and start a fresh one with a complete normalized request.

## Fresh execution and evidence provenance

Each new investigation starts INITIALIZING with empty evidence/assessment/work
collections, zero investigation counters, and a new `BudgetManager`. It retains the
session ID, uses the next revision and receives the same approved maxima. Prior
unused or spent budget is never transferred. Tests exercise eight calls followed
by six calls under one session, including reset of retry/fallback use.

The manager passes no prior findings, assessments, eligibility or report to the
runner. This increment always re-retrieves evidence. Prior returned findings keep
their original parents, IDs, source metadata and timestamps. New dispatches acquire
new runtime IDs/bindings; fixed fixture timestamps remain fixed. A report containing
foreign-parent findings is rejected. No provenance is rewritten to claim a prior
retrieval occurred in the new investigation.

Cross-investigation reference storage remains open (SL-OD-003 / MAP-OD-004); no
reuse mechanism is invented. SL-T05's actual evidence-reference reuse is deferred.
The conservative re-retrieval path satisfies the rule that reuse is optional and
only permitted when validated. Candidate selection is an injected runner concern,
and evidence/safety evaluation and assessments are performed afresh.

Specialist correlation uses the existing investigation/revision/request/attempt
guards. Late old-investigation or old-revision responses cannot enter the follow-up
or alter its request, findings or assessments; their response identity remains in
the appropriate rejection event. `DeliveryRejection` retains a detached tuple of
schema-valid reported investigation/revision/request/agent/attempt identifiers,
which the graph records as `response_correlation` alongside the response ID. These
are observed identities, not authority to merge. Malformed payloads contribute no
raw diagnostic or source content to this metadata. Previously these rejections
dropped the reported response identity, preventing complete stale-work correlation.

## Events and failure behavior

All graph component events now carry session/investigation correlation in existing
structured details. Each session-managed graph has a new trace ID and event
sequence. Initialization records zero counters and INITIALIZING, then emits actual
REQUEST_RECEIVED / REQUEST_NORMALIZED admission events. A follow-up also emits
REQUEST_REVISED with changed fields, prior revision and the prior investigation ID
through existing `related_ids` and details. Field-origin declarations accompany
normalization. Result/terminal events retain the new investigation and revision.
No new event enumeration is added, and old trace events remain unchanged.

Memory recorders remain component seams; these events are not authoritative JSONL
traces or full acceptance evidence. A recorder failure at admission stops work
before source dispatch; a later failure suppresses result publication as before.
A new post-terminal investigation may use its own functioning recorder without
altering prior failure diagnostics.

Concurrent admission is rejected; active graph execution cannot be interrupted,
cancelled, resumed or superseded through the session API (SL-T09's explicitly
permitted terminal-only restriction). `AWAITING_CLARIFICATION` is never relabeled
terminal. An unhandled runner exception, cancellation or invalid/mismatched report
makes the session unavailable for more work. No undocumented terminal outcome is
fabricated. The caller must start a new session; already returned history is intact.
Runner exceptions are sanitized at the session/CLI boundaries.

## CLI demonstration and validation

```bash
uv sync --locked
uv run --locked hafi demo session --fixtures fixtures/scenario-pack-v1
uv run --locked python -m hawaii_activity_forecaster demo session --fixtures fixtures/scenario-pack-v1
uv run --locked pytest tests/test_session_lifecycle.py tests/test_cli_demo.py
uv run --locked pytest
```

The new fixed `session` demo performs two normalized SC-004 component invocations,
first preferring Kihei, then Wailea. It retains intermediate experience and the
opaque calm-water preference and renders each result through the existing contextual
validation boundary. Both investigations make six synthetic tool calls and zero
model calls. The entire two-result display is buffered before stdout is written;
a rejected second result cannot leak a partial first response. Existing exit-code,
stderr and BLOCKED/DISABLED preflight behavior is retained.

This is not the SC-012 acceptance scenario: its independent fixtures/assertions are
not authored or executed. The initial demonstration uses the same fictional
candidate pool on both revisions and reevaluates area preference. Arbitrary
conversational text is not accepted by the CLI. Existing SC-004/SC-010 full execution
readiness remains BLOCKED.

The authored source behavior permits its original fixed time-window signature.
Changing the normalized time is supported by session admission, but executing that
new request with the old demo script returns a controlled technical failure rather
than inheriting old eligibility or silently changing the time. Other windows need
appropriate authored tool behavior. This is a component-fixture limitation, not a
finding of unsuitable environmental conditions.

Verification covers stable session identity, increasing revisions, new investigation
and trace IDs, terminal immutability, constraint/origin preservation, explicit clears,
invalid admission, time changes, fresh budgets, abstention/error follow-ups, stale
responses, clarification, concurrency, recorder failure, cancelled/failed runners,
installed CLI entry points and buffered/sanitized failure output.

Final validation: `uv sync --locked` succeeded; **912 tests passed in 12.37s**
on Python 3.14, including 63 added lifecycle/CLI checks. The 13 existing upstream
LangSmith deprecation warnings remain. The session CLI demonstration and installed
console/module entry points succeeded; `git diff --check` passed. The dependency
and lock files, approved specifications and fixture artifacts are unchanged.

## Remaining work

No new specification conflict was found. Existing open decisions remain: active
clarification resumption; evidence-reference storage/reuse; interruption/cancellation;
expiration and persistence. Sessions are process-local with random UUID identities,
no expiry timer, database, disk profile or restart restoration. These choices follow
the conservative approved scope and do not resolve those deferred decisions.

Natural-language request interpretation, general candidate selection, agentic
planning/model activation, authoritative JSONL and independent scenario execution
remain outside this increment. M1.5's complete natural-language/follow-up exit
criterion and M1 acceptance are not yet satisfied.

Next proposed increment: M1.5-D — request interpretation and candidate-selection
boundary review, before enabling general conversational CLI requests.
