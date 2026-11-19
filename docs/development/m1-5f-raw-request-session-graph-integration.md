# M1.5-F — Raw request/session graph integration

Implements the integration authorized by
[M1.5-D §11](../implementation/m1-request-interpretation-and-candidate-selection-design.md)
after the [M1.5-E components](m1-5e-request-validation-and-catalog-selection.md).
Approved requirements, logical schemas, architecture, fixture artifacts and
dependency versions are unchanged. This increment resolves integration gaps
RI-G01 (admission/accounting), RI-G03 (empty selection) and RI-G05 (assumed precision).

Files created: `orchestration/model_calls.py`, `tests/raw_graph_samples.py`, four
`tests/test_raw_*.py` modules and these integration notes. Files updated: request
context/input construction in `interpretation/contracts.py` and `validation.py`;
raw lifecycle/exports in `orchestration/session.py`, `skeleton.py` and `__init__.py`;
dispatch guards in `orchestration/specialists.py` and `tools/synthetic.py`; canonical
grounding/disclosures in `recommendations/results.py` and `presentation.py`; README.
Application paths above are relative to `src/hawaii_activity_forecaster/`.

## Admission and graph

`SessionManager.start_raw(text, catalog=..., reference_time=..., run=...)` assigns
the session/revision and investigation ID before invoking the runner. The frozen
`RawSessionRequest` retains serialized catalog data and detached inherited request
values/origins. Its initial normalized snapshot preserves the raw text with unknown
activity/time. No prior findings, assessments, results or driver scripts enter
interpreter input.

The raw runner calls `run_raw_synthetic_tool_graph()`. Within one graph invocation,
it initializes a fresh trace identity and BudgetManager, records admission, obtains
an interpretation proposal, independently validates it, records normalization,
selects catalog candidates and proceeds through existing scoped evidence/safety/
result validation. Normalization does not consume a Coordinator iteration.

Wiring example (the callbacks, policy and synthetic inputs are supplied explicitly):

```python
from hawaii_activity_forecaster.orchestration import (
    SessionManager, run_raw_synthetic_tool_graph,
)

async def execute(admission):
    return await run_raw_synthetic_tool_graph(
        admission,
        interpreter=authored_interpreter,
        plan=trusted_planner,
        tool_plan=trusted_tool_plan,
        driver_inputs=synthetic_driver_inputs,
        evidence_policy=synthetic_policy,
        record_event=component_events.append,
    )

session = SessionManager()
report = await session.start_raw(
    text, catalog=catalog, reference_time=reference_time, run=execute,
)
revised = await session.follow_up_raw(
    follow_up_text, catalog=catalog, reference_time=later_reference_time, run=execute,
)
```

The planner receives `RawPlanningInput`: a detached state, supported investigation
IDs, repeatable preferred-area-first order, and a synthetic model-accounting seam.
It may be synchronous or asynchronous. It receives no source script or evaluator
assertions. The raw API is not a general language CLI; interpretation still needs
explicit authored proposals or the accounting adapter described below. Executable
authored wiring is in `tests/raw_graph_samples.py` and the integration tests.

`SkeletonReport` retains the request context, validation receipt and selection
audit. Before committing history, SessionManager replays the proposal against its
own admitted text, clock, catalog, profile, inherited receipt and actual IDs. It
does not accept the runner's context as independent authority. Returned reports and
requests cannot mutate history.

Raw follow-ups require COMPLETED, ABSTAINED or FAILED. They retain the same session,
advance revision, create a new investigation/ledger and preserve omitted values
and origins. A geographic-only change retains the absolute window despite an
advanced clock. Replacing a daypart retains assumed hour precision; explicit hours
use the existing explicit-precision rules. Use `follow_up_raw()` for raw sessions;
the caller-normalized replacement API cannot erase those origin checks.

A FAILED run that never committed normalization can accept a complete new raw
utterance at the next revision. Its prior investigation is correlated explicitly,
but no activity/time is invented or inherited. AWAITING_CLARIFICATION remains
nonterminal and produces no result or retrieval. Active revision, clarification
resumption, cancellation semantics, persistence and evidence reuse remain deferred.

## Scope and outcomes

Selection keeps all verified records allowed by hard geography in
`candidate_beach_ids`, including unsupported activity records. Only the supported
subset initializes remaining work and is authorized by SpecialistExchange and the
tool dispatcher. The selector applies no early three-candidate cap; three remains
the final recommendation limit.

For SUP in South Maui, A/B/E receive actual assessments while only B may receive
specialist/tool work. The component test retrieves wind for B, records A/E as
UNSUPPORTED, and leaves B NEEDS_INVESTIGATION because the remaining evidence and
safety requirements are not established. Unsupported/outside-scope dispatch
attempts fail before specialist/tool invocation.

`NO_SUPPORTED_CANDIDATES` is a trusted internal stop, not a new schema enum. It
requires independent receipt/selection replay, zero supported investigation
candidates, no environmental work and no fabricated assessments. Existing safety
evaluation records actual unsupported assessments when those records exist; a
truly empty assessment pool stays empty. Result validation then produces existing
NO_RECOMMENDATION / NO_ELIGIBLE_CANDIDATES and ABSTAINED, with catalog reasons and
catalog/scope next steps. It makes no hazardous-condition claim.

Both recommendation and abstention validation recheck the raw scope and audit
against the current catalog/evidence. The read-only presenter repeats those checks.
Default window disclosures and unresolved interpretation limitations are part of
the canonical result, including known-context operational errors. Partial
investigations name candidates whose evidence/requirements remain unresolved.
Timeouts, malformed proposals and broken required tracing are operational failures.
If activity/window is unknown, FAILED diagnostics retain `result=None`.

## Synthetic model accounting and events

An authored synchronous interpreter is ordinary component code: zero model calls,
zero environmental calls and no provider-call events. Alternatively, explicitly
inject `SyntheticModelAdapter(async_respond)` instead of an interpreter. It is an
accounting test double, independent of BehaviorScript and disabled live-model
configuration. Its normalization input is the same isolated InterpreterInput.
Only trusted planners receive `inputs.models.invoke(operation, payload)` for later
accounting probes. No live SDK/provider is implemented or configured.

`ComponentModelCalls` reserves, records authorization, dispatches, waits at the
approved 30-second timeout and finishes through the graph's existing BudgetManager.
The 12-model-call cap is shared across normalization and later work. Failed,
malformed and timed-out dispatched attempts remain charged. Required recording
failure before dispatch cancels capacity without charging or invoking the adapter.
There is no automatic model retry/repair. Environmental calls have their separate
12-call cap, and the existing five Coordinator iterations are unchanged.

Existing event enums carry admission, revision, normalization and contract details:
actual reference clock/profile, current/inherited origins, accepted changes,
selection reasons/source attribution and observed counters. Synthetic adapter
authorization/return/failure details explicitly set `synthetic_adapter=True` and
never masquerade as environmental TOOL_CALLED events or real model usage. Tool
events include actual candidate/category/window scope. Required result/terminal
recording must succeed before publishing a result. Memory recorders are component
seams, not authoritative local JSONL; remote tracing remains suppressed.

## Verification and remaining work

```bash
uv sync --locked
uv run --locked pytest tests/test_raw_request_graph.py tests/test_raw_session_lifecycle.py tests/test_raw_selection_scope.py tests/test_raw_model_accounting.py
uv run --locked pytest
uv run --locked hafi --version
uv run --locked python -m hawaii_activity_forecaster
uv run --locked hafi demo session --fixtures fixtures/scenario-pack-v1
```

The 47 added checks cover raw initial/follow-up integration, immutable history,
owned-context tamper rejection, failures before a receipt, unknown/elapsed requests,
shared accounting and the 12-call cap, timeout/no-retry behavior, required recording
failures, scope guards, unsupported assessments, empty-selection grounding,
preferred ordering/incomplete-work disclosures and retained presentation checks.
They exercise the integration portions of RI-T09/10/13..18/20..22.

Afternoon tests author in-memory source/premise variants with 12:00–16:00 coverage
or only 12:00–14:00 coverage. The latter cannot support the entire default window;
it abstains without extending evidence. The former supports the controlled fictional
result and geographic follow-up with inherited afternoon precision. These variants
do not change the approved fixture package or establish new scenario acceptance.

Final verification: `uv sync --locked` succeeded. **1,085 tests passed in 18.10s**
on Python 3.14.8, including **47 new checks**. The same 13 upstream LangSmith
deprecation warnings remain. Package import, installed CLI version, module startup
and the synthetic session demo passed. Python 3.12 syntax checks passed for all 15
changed/new Python files (not a separate Python 3.12 runtime test). All 24 relative
documentation links and fenced blocks passed, along with `git diff --check`.

No new specification conflict was found. Existing normalized APIs and CLI demos
remain covered. Full SC-003/SC-012 acceptance, SC-004/SC-010 agentic execution,
general natural-language CLI use and overall M1 completion are not claimed.

Recommended next increment: **M1.6-A — authoritative local JSONL tracing**, including
trace completeness and failure/closure checks. General model-backed execution still
requires that trace foundation plus separately reviewed provider/model integration,
real Coordinator planning and independent scenario execution.
