# M1.3-B — Scoped synthetic tool dispatch

This increment implements synthetic tool retrieval, actual invocation accounting,
and explicitly authorized recovery from M1.3 in the approved technical and
LangGraph execution plans. Behavior matching and template binding follow
[SH-OD-005/006](../implementation/m1-scenario-harness-contract-design.md).
Approved requirements, fixture contents, architecture documents and dependency
versions are unchanged. No real provider or LLM is selected or called.

## API and ownership

`orchestration.run_synthetic_tool_graph()` extends the existing component graph:

```python
report = await run_synthetic_tool_graph(
    normalized_request,
    catalog=application.catalog,
    candidate_beach_ids=candidate_ids,
    plan=plan_specialist_requests,
    tool_plan=plan_tool_actions,
    driver_inputs=scenario.driver,
    record_event=record_component_event,
)
```

`plan` receives only detached logical state, as in M1.3-A. `tool_plan` receives
only a detached authorized specialist request and returns a tuple of `ToolAction`
models. The script and evaluator assertions are never passed to either planner.
`DriverInputs` contains script/source templates and deliberate malformed payloads,
not independent expected outcomes. `request_step` defaults to 1 and selects the
script's fixed reference time; it does not implement conversational follow-ups.

`tools.ToolAction` identifies an explicit action ID, source, candidate IDs,
requested evidence categories and source-specific geographic scope. Optional
`retry_of` or `fallback_of` refers to an earlier action in that same plan. It is a
trusted application plan, not a new autonomous agent or a persisted logical
contract. Action IDs are unique within the investigation. Caller-owned models and
nested lists are detached when plans are registered.

The existing `run_skeleton()` and `run_specialist_graph()` APIs remain available.
The new path uses the same investigation budget manager and Weather/Ocean slots.
Trusted adapters return the approved specialist response contracts, and the
existing join performs independent contract validation and state merging. Model
calls remain zero; graph state now reflects actual tool calls, retries and whether
fallback occurred. `SkeletonReport.tool_bindings` contains observed driver metadata.

## Dispatch and script semantics

`harness.synthetic.SyntheticDriver` snapshots the driver projection and matches
actual tool requests by request step, role, source, candidates, evidence,
target window and geographic scope. Candidate/evidence order is ignored. Unknown,
ambiguous or excess operations are rejected; script availability grants no scope
permission, retry, fallback, candidate selection or stopping decision. Such script
mismatches are operational/configuration errors, not fabricated provider outages.

Before dispatch, `SyntheticToolDispatcher` verifies parent identity/revision,
specialist/source permissions, candidate containment, evidence containment and
source/category mappings. Geographic identifiers must match the explicitly
scripted synthetic scope; a beach ID is not converted to a forecast zone or buoy.
This validates fixture identifiers only, not real-world geographic mappings.

The dispatcher serializes virtual source dispatch under a lock. It reserves the
shared environmental allowance before dispatch, records the dispatch boundary,
then consumes exactly one script attempt. A denied reservation consumes neither
a script attempt nor a binding. All dispatched outcomes, including failed,
malformed and timed-out calls, remain counted. Exhaustion preserves earlier valid
findings and returns a structured EXECUTION_LIMIT_REACHED error plus explicit gaps.

Behaviors follow the approved definitions:

- SUCCESS and PARTIAL preserve delivered findings and source limitations. Incomplete
  responses retain explicit gaps/errors. A successful retrieval never accepts its
  evidence or establishes category sufficiency/safety.
- ERROR and UNAVAILABLE retain structured diagnostics and missing information.
- TIMEOUT advances that specialist execution's virtual clock by exactly 10,000 ms,
  generates SOURCE_TIMEOUT at the trusted boundary, and delivers no late payload.
  Exactly 10,000 ms is timely; a greater scripted duration is a timeout. There are
  no wall-clock source sleeps. Virtual tests are not proof of real provider timers.
- MALFORMED delivers only the declared raw JSON to contract validation. Fault
  annotations remain in the driver; invalid material becomes SOURCE_RESPONSE_INVALID
  and cannot become an Environmental Finding.
- DUPLICATE repeats one materialized response with identical call/finding IDs. It
  counts as one invocation and contributes no duplicate findings.

Virtual clocks are independent per specialist execution and begin at the selected
request-step reference time. Sequential calls in one execution advance its clock;
parallel completion order cannot shift the other execution's clock. Trace event
wall-clock timestamps and virtual timing details remain distinct. Optional parent
specialist deadlines retain the existing real callback timeout enforcement.

## Recovery permissions and gap identity

A retry runs only when explicitly planned and its referenced original invocation
failed with a retryable diagnostic. It uses the same material source/scope/evidence,
a new tool-call ID and one additional shared invocation. A successful or permanent
failure skips the planned retry. Retrying a retry, changing its scope, or inventing
an original reference is rejected. A script's second operation attempt is separate
from the specialist `attempt_number`; multiple tools can run within attempt 1.

A fallback runs only when explicitly planned against an earlier retrieval action
with an unresolved REQUIRED evidence category. It addresses exactly one such
category over the same candidate scope, through another permitted source. Optional
missing evidence cannot authorize fallback. The fallback does not run merely
because an alternate is present in the script, or after successful recovery clears
that retrieval gap. A failed fallback can have its own one permitted retry.

Gap identifiers derive from investigation, revision, category, sorted candidate
scope and UTC-normalized target-window instants. Source names, action/request
labels and geographic-provider identifiers do not refresh the same gap's allowance.
Different candidate/time/category questions remain distinct. The budget manager
enforces one fallback per such gap and one retry per failed original, within the
shared 12-call cap. No model retry policy is introduced.

Operational retrieval gaps are deliberately conservative: PARTIAL, missing/error
fields and unattempted REQUIRED categories remain explicit. Subset retrievals do
not automatically establish completeness of a broader delegation. Independent
M1.4 evaluation must determine actual evidence sufficiency and resolve issues;
these operational records never decide eligibility, safety or environmental
abstention. Historical failure diagnostics remain visible after successful recovery.

## Runtime identity and provenance

The driver materializes templates only for actual dispatch:

- Each invocation has a fresh tool-call ID; each fresh retrieval allocates fresh
  finding IDs and binds the current investigation.
- Source identity, measurements, coverage, advisory IDs, and source evidence
  timestamps are preserved. Offshore/regional material is never relabeled as direct
  beach evidence. New findings remain PENDING for independent validation.
- Error IDs and call/source references bind to the observed invocation. The tool
  response duration reflects its scripted execution duration. Templates remain
  unchanged and are not historical investigation evidence being rebound.
- Frozen binding records contain request step, operation/attempt, investigation,
  tool-call ID, source fixture and template/runtime finding IDs. Timeouts have
  call-only bindings; duplicate delivery reuses the same binding.

The binding index is observed harness metadata. It contains no expected values
and does not replace the authoritative local trace.

## Tracing, validation and remaining boundaries

Actual tool, retry, fallback, failure and limit events use the existing TraceEvent
vocabulary and carry request/tool/operation correlations. Recorder failure closes
execution, cancels undispatched reservations and prevents new dispatch or evidence
publication. Dispatched calls remain counted even when terminal recording fails.
No evidence/policy/result-validation success is fabricated, and remote LangSmith
tracing remains disabled by the graph regardless of ambient SDK variables.

```bash
uv sync --locked
uv run --locked pytest tests/test_synthetic_tools.py tests/test_synthetic_tool_graph.py
uv run --locked pytest
uv run --locked hafi --version
```

Validation: **669 tests passed**, including 30 new tool/graph component tests.
The authored SC-010 dispatch test executes eight explicitly planned calls: one
retry and two fallbacks, with preserved partial findings and unresolved gaps.
Planning/dispatch use only the application/driver projections; the normal loader
retains independent assertions in its separate evaluator projection. This is not
an SC-010 acceptance result.
The existing 13 upstream LangSmith deprecation warnings on Python 3.14 remain.

SC-004 and SC-010 readiness remains BLOCKED. There is no production investigation
entry point, authoritative JSONL writer, request interpretation/catalog selection,
independent evidence/safety/result evaluation, or recommendation presentation yet.
The CLI still prints application/version information only. Memory event recorders
are component-test seams, not authoritative investigation traces.

The next proposed increment is M1.4-A — deterministic evidence validation and
required-evidence accounting, using approved synthetic category/rule inputs.
Policy evaluation, eligibility, result generation and full scenario acceptance
should remain separately reviewable increments. No new specification conflict
was found; the provider/model and real-source thresholds remain open as designed.
