# M1.6-C — Scenario execution adapter and demo alignment

This records the original increment. The subsequent
[release-readiness batch](m1-release-readiness-and-demo.md) replaces the old
`AGENTIC_RUNTIME_UNAVAILABLE` diagnostic with `SCENARIO_ADAPTER_UNAVAILABLE`:
the model-driven runtime now works, while registered-scenario agent execution and
capture remain unconnected. Authored component scope and the BLOCKED gate persist.

Connects the [M1.6-B evaluator](m1-6b-scenario-evaluation-and-reporting.md) to actual
authored component execution under the approved
[harness design](../implementation/m1-scenario-harness-contract-design.md),
[request/session integration design](../implementation/m1-request-interpretation-and-candidate-selection-design.md),
[configuration baseline](../implementation/m1-configuration-baseline.md) and
[LangGraph execution design](../implementation/m1-langgraph-execution-design.md).
Approved specifications, fixture bytes, event enums and dependencies are unchanged.
No provider, model, remote tracing, general conversational CLI or new agent role is
introduced. Full agentic acceptance is still unavailable.

## Changes

Created `harness/execution.py` and `tests/test_scenario_execution.py`. Updated
`harness/evaluation.py` to evaluate the already loaded snapshot without rereading
expected artifacts. Updated demos and CLI for explicit authored execution. Added
an observed fallback-capacity query, unresolved-gap tracking, scoped limit emission
and independent trace checks in the existing budget/tool/graph/trace components.
Adjusted regression expectations for the two resolved gaps and for actual raw
normalization event order. README documents the command and reporting boundary.
Application paths are relative to `src/hawaii_activity_forecaster/`.

## Execution boundary

`execute_scenario(root, scenario_id, runtime=..., trace_settings=...)` preflights
the entire registered scenario once. Definitions, assertions, source templates,
behavior declarations and artifact digests remain snapshotted before dispatch.
Invalid fixtures fail before the runtime is called. BLOCKED/DISABLED definitions
produce BLOCKED/NOT_RUN and never execute. Missing runtime produces BLOCKED without
creating investigation files.

The trusted runtime receives `ComponentExecutionInput`, containing only one raw
session admission, its request step, local trace settings, and detached policy/
driver projections. It receives no LoadedScenario, definition, evaluator object,
expected values, expected paths or evaluator artifact digests. Driver behavior is
trusted dispatcher configuration, never interpreter/planner context. The existing
authored plans remain explicit code; they are not inferred by enumerating scripts,
source payloads or assertions. This is the existing in-process data-flow boundary,
not a sandbox against arbitrary code deliberately reading repository files.

The adapter owns SessionManager and admits each request before invoking the runtime.
Only current text/clock, catalog and inherited normalized values/origins enter raw
admission. Each post-terminal follow-up retains its session, advances revision,
creates a new investigation and fresh budgets, and retrieves evidence independently.
No previous findings, reports or assessments are passed to the runtime. Active
clarification resumption, persistence, cancellation semantics and evidence reuse
remain deferred. Normalized component/session APIs remain available.

After each returned report, session correlation and authoritative trace validation
run before `capture_report`. Capture then independently verifies canonical results,
evidence/safety grounding, dispatch bindings and observed counts. Exceptions,
missing reports, invalid receipts and broken required tracing after admission are
FAIL, not missing-capability blockers. Interruptions propagate with the existing
partial-trace behavior. Expected files are never reloaded after runtime dispatch.
Evaluation consumes the original LoadedScenario snapshot.

## Request and exhaustion alignment

The standalone advisory/outage demos now admit raw requests before normalization.
An explicit authored morning/snorkeling proposal is independently validated in the
graph against the actual request, clock, catalog, identity and rule profile. The
advisory's `near Kihei` clause is represented as a soft preference and remains in
state; it is not read from the evaluator's expected value. Other supported areas
and unsupported assessments remain available according to approved selection rules.

The callback is deliberately narrow and uses authored synthetic morning values;
it is not a general parser or live model. Changed dates/meaning require a supported
authored proposal, and the independent validator rejects unsupported or stale
proposals before environmental dispatch. Explicitly injected component interpreters
can exercise additional approved input/follow-up cases. No real-model usage is
recorded for Python callbacks.

SC-010 makes eight actual tool invocations: ordinary requests, a marine retry and
two failed fallbacks. The existing planner then has no additional authored work.
Previously no event exposed the already consumed per-gap fallback allowances.

The trusted dispatcher now tracks unresolved retrieval gaps. BudgetManager reports
exhaustion only from dispatched fallback reservations, using stable gap identity;
unused script entries, reserved-but-undispatched calls and arbitrary labels do not
consume capacity. When no work is planned, the graph intersects those unresolved
exhausted gaps with missing mandatory evidence and NEEDS_INVESTIGATION candidates.
It records existing INVESTIGATION_LIMIT_REACHED events with:

- `budget_kind = fallback_per_evidence_gap`
- the actual gap/category/candidate scope
- `configured_limit = 1`
- an explicit unresolved-evidence/fallback-allowance reason

No new Coordinator cycle or source invocation is fabricated. This does not claim
that all tool capacity, all recovery options or all Coordinator iterations were
exhausted. The actual stop stays NO_FURTHER_ACTION and the validated outcome stays
NO_RECOMMENDATION / INSUFFICIENT_EVIDENCE. Independent trace validation checks the
gap against actual fallback initiation, failed outcome, cap, category and scope.
Unsupported exhaustion claims fail trace validation and cannot authorize display.

## Commands and report scope

```bash
uv sync --locked
uv run --locked hafi evaluate SC-004 --fixtures fixtures/scenario-pack-v1
uv run --locked hafi evaluate SC-004 --fixtures fixtures/scenario-pack-v1 --component --trace-directory traces
uv run --locked hafi evaluate SC-010 --fixtures fixtures/scenario-pack-v1 --component --trace-directory traces
uv run --locked pytest
```

Without `--component`, evaluation is readiness-only and dispatches nothing. The
flag opts into one of the two existing authored runtimes; it does not activate a
model/provider or a general request interface. Runtime capability is explicit;
an unavailable authored runtime remains blocked.

The execution report has `mode=AUTHORED_COMPONENT`, attempted request steps, a
component report, and a scenario report. Component results may PASS while overall
scenario status remains BLOCKED with AGENTIC_RUNTIME_UNAVAILABLE. Active mandatory
failure still dominates that blocker. CLI exit 2 means BLOCKED/NOT_RUN, exit 1 FAIL;
full PASS remains unavailable in this increment.

Both unchanged fixture assertion sets now pass against verified component captures:
SC-004 84/84; SC-010 61/61. These checks do not establish genuine model-driven ReAct,
SC-003/SC-012 acceptance, complete coverage of all twelve scenarios or M1 PASS.

## Validation and remaining gates

New tests cover connected execution/evaluation, preflight/readiness non-dispatch,
missing runtime, oracle isolation, expected-file mutation after preflight, runtime/
trace/receipt failures, actual fallback capacity, rejected fake exhaustion records,
CLI opt-in and separate component/scenario scopes. A temporary two-step contract
fixture verifies inherited values, stable session, new investigation/revision,
fresh six-call budgets, repeat retrievals and unchanged prior trace bytes. It does
not modify or claim acceptance of the deferred SC-012 fixture.

Final validation: **1,233 tests passed in 41.98s** on Python 3.14.8, including
**18 new tests** over the 1,215-test baseline. The same 13 upstream LangSmith
deprecation warnings remain. `uv sync --locked` succeeded. Installed CLI runs
passed all 84 SC-004 and 61 SC-010 component assertions, reported overall BLOCKED
with exit 2, and produced traces that passed installed CLI inspection. Version
startup passed. Python 3.12 syntax parsing passed for all 11 changed/new Python
files (not a separate 3.12 runtime test). All 30 relative documentation links,
fenced blocks and `git diff --check` passed. Approved specifications, fixtures,
pyproject.toml and uv.lock remain unchanged.

No new specification conflict was found. The two demo gaps reported by M1.6-B are
resolved. Provider/model activation and real Coordinator planning still require
their separate review and implementation. Before any full acceptance claim, finish
the genuine execution runtime and independently author/run remaining scenarios
with all mandatory gates. Retention and production classification decisions remain
outside this increment.
