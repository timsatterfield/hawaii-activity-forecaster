# M1.2-A — LangGraph skeleton and trusted budgets

This increment implements the first part of M1.2 in the approved
[execution design](../implementation/m1-langgraph-execution-design.md), using the
limits from the [configuration baseline](../implementation/m1-configuration-baseline.md).
It does not execute SC-004/SC-010 or change their readiness status.

## Implemented components

`orchestration.run_skeleton()` is an async **component-test API**, not the
application investigation entry point. It accepts an already normalized request,
preselected synthetic candidate IDs, a trusted async callback, and a synchronous
event recorder. It creates fresh investigation/trace/result identifiers and
per-run budgets, without checkpoints or resumption. An optional session identifier
can correlate runs; conversational follow-up interpretation is not implemented.

The LangGraph topology is:

```text
initialize_investigation -> validate_request
  clarification -> END (AWAITING_CLARIFICATION, no final outcome)
  no selected candidates -> finalize_investigation
  otherwise -> authorize_dispatch
    -> weather_investigation + ocean_investigation (parallel)
    -> decide_next_action (join)
      more synthetic work, below five cycles -> authorize_dispatch
      otherwise -> finalize_investigation -> END
```

Only trusted nodes update the logical `InvestigationState`. Callbacks receive a
frozen `BranchInput`, containing correlation, scope and iteration fields, and
return only a `BranchSignal`. This signal is a test seam, **not** a replacement
for the approved specialist request/response contracts. It carries no evidence,
assessments, preferences, counter updates or terminal authority. Invalid signals
and callback exceptions stop the probe as an operational failure. Both parallel
branches count as one cycle; the sixth cycle cannot dispatch. A separate graph
recursion limit is a framework safeguard, not the investigation counter.

The probe always stops before evidence/safety/result evaluation. Its ordinary
terminal state is FAILED / ERROR with `VALIDATORS_NOT_IMPLEMENTED`, or
`ITERATION_LIMIT_REACHED` when synthetic continuation reaches five cycles.
An empty candidate input stops with `NO_SELECTED_CANDIDATES`; it is not a
finding that no safe beach exists. The state's `result_id` identifies the
operational stop only. No validated `RecommendationResult` is constructed or
published, and neither environmental abstention nor recommendations are inferred.
Initial clarification remains nonterminal and is not resumable through this API.

`BudgetManager` is a thread-safe component for the later trusted dispatch layer:

- Atomic reservations share the 12 environmental-call or independent 12 model-call
  capacity. Reservations count against capacity immediately; invocation counters
  advance at dispatch. Cancellation before dispatch releases capacity; dispatched
  failures/timeouts count permanently.
- A retry requires a failed, retryable original environmental invocation; it has
  one allowance per original, and cannot retry a retry. One fallback is allowed
  per stable required-evidence-gap identifier. A failed fallback may itself have
  one retry. Recovery still consumes the shared environmental-call limit.
- A cancelled reservation has not used its retry/fallback allowance. IDs cannot
  be reused, including cancelled IDs. Simultaneous recovery reservations cannot
  claim the same allowance twice.
- There are at most two concurrent specialist executions, one Weather and one
  Ocean. Slots release on exceptions. Closing execution denies new cycles,
  reservations, dispatches and specialist entries, cancels pending reservations,
  and permits bookkeeping of already dispatched completions.

The caller owns semantic recovery authorization: stable gap identity, required
status, source permissions, timeouts and actual adapter execution are not inferred
by this counter. Synthetic graph signals make no model or tool calls; their
invocation counters correctly remain zero. The three-recommendation publication
limit belongs to the later Result Validator, not to these invocation counters.

## Tracing boundary

The probe requires an injected event recorder and emits existing `TraceEvent`
contracts for actual component actions only. A recorder failure closes execution
and produces `TRACE_WRITE_FAILED` with `trace_writable=False`; it cannot claim a
successfully recorded terminal event. The report is operational diagnostics and
never a public recommendation. Memory recorders used in tests are **not**
authoritative investigation traces. A local JSONL writer, trace verification,
configuration/policy metadata assembly and production dispatch integration remain
future work. There is no usable production investigation executor in this chunk.

The graph runs inside `tracing_context(enabled=False)` so ambient LangSmith
variables cannot enable remote graph tracing. No tracing credentials or LLM
provider/model are configured.

## Verification and deferred work

```bash
uv sync --locked
uv run --locked pytest tests/test_orchestration_budgets.py tests/test_orchestration_skeleton.py
uv run --locked pytest
```

Component tests exercise parallel tool/model reservation races, cancellation,
recovery scoping, independent limits, slot cleanup, both branch completion orders,
conditional traversal, five-cycle termination, initial clarification, recorder
failure, invalid callbacks, and independent per-run state. They do not prove
safety invariance, evidence acceptance, or full scenario acceptance criteria.

No approved specification changes are needed for this component increment.
Request normalization, catalog selection, real specialist contract correlation,
evidence merging, source-scoped synthetic tools, timeout enforcement, deterministic
validators, result presentation and the authoritative JSONL writer remain deferred.
The next proposed chunk is M1.2-B: connect the specialist contract boundaries to
the graph, with synthetic delegation and trusted state merging, before enabling
full scenario execution. Confirm that scope against the approved M1.3 specialist
integration sequence when planning that increment.
