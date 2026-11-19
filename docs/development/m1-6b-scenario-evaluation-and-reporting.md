# M1.6-B — Independent scenario assertion evaluation and reporting

Implements the evaluator/reporting portion of the approved
[harness design §§7–10](../implementation/m1-scenario-harness-contract-design.md)
and [acceptance specification](../requirements/06-test-acceptance.md), following
[M1.6-A](m1-6a-authoritative-local-jsonl-tracing.md).
No approved specification, fixture, dependency, provider selection or autonomous
role changes. Full agentic execution and scenario acceptance remain unavailable.

## Implementation

Created `src/hawaii_activity_forecaster/harness/evaluation.py` and
`tests/test_harness_evaluation.py`. Updated CLI and README with readiness reporting,
and corrected the loader's stale missing-capability description. The synthetic
tool adapter now emits the approved singular `error_code` alongside its existing
error-code list; independent SC-010 assertions exposed that missing trace field.

`capture_report(request_step, report, catalog=..., policy=..., driver_inputs=...)`
is trusted harness instrumentation. It independently validates the authoritative
trace, closure/counters/bindings and canonical result through existing validators.
It accepts no expected file. Captures detach JSON observations into immutable bytes
and retain actual dispatch bindings, trace digest, application/policy/driver input
fingerprints and original-request fingerprint. Concurrency is measured from actual
specialist start/end events, never copied from the configured concurrency maximum.
No-result failures leave result/recommendation collections unavailable rather than
inventing empty validated output. Invalid or missing trace/result proof raises the
static `CaptureError("CAPTURE_INVALID")`.

`evaluate_assertions(expected_results, captures)` consumes only evaluator-owned
assertions and detached observations. It reports scope COMPONENT. Supported targets
are current state/assessments/findings, validated result/recommendations, actual trace
events and the approved observed ExecutionSummary. Superseded assessments do not
enter the current-assessment target.

The implementation supports all approved operators. EQUALS/NOT_EQUALS, membership
and cross-actual comparisons require exactly one record. ALL_EQUALS requires at
least one. COUNT operators count verified selected collections. Missing steps,
collections, pointers and required references fail attempted assertions. Explicit
JSON null differs from a missing pointer. Booleans differ from numbers; strings
are not coerced and membership is element equality rather than substring search.
SAME_AS/DIFFERENT_FROM compare actual observations, including across request steps.
No eval, executable selectors, regex expressions, imports or model grading is used.

Source/template selectors resolve only actual DispatchBinding/FindingBinding
records. Multiple invocations require operation/attempt disambiguation. Unbound
references fail even for ABSENT; nonexistent findings cannot prove nonappearance.
Trace finding selectors use actual related IDs, and call selectors use actual call
IDs, without assuming Weather/Ocean completion order. Both references must match
when supplied together. Duplicate request-step captures fail instead of selecting
the last capture.

## Outcomes and boundaries

Each assertion records ID, requirement IDs, mandatory flag, outcome and a concise
reason. Reports retain every assertion, all four outcome counts, trace digests,
supported artifact versions and (for scenario reports) preflight artifact digests.
No raw provider/model payload or private exception text is included.

Mandatory active failures dominate blocked/pass outcomes. Otherwise blocked
mandatory checks yield BLOCKED; PASS requires all mandatory checks to run and pass.
Empty/all-disabled mandatory sets yield NOT_RUN. Optional failures remain visible
without overriding passing mandatory assertions. BLOCKED/PARTIALLY_BLOCKED atomic
checks never count as passing; DISABLED checks report NOT_RUN.

`evaluate_scenario(root, scenario_id, captures=None)` preflights the existing
registered package. Invalid input reports FAIL/FIXTURE_INVALID. Unexpected evaluator
exceptions report FAIL/EVALUATOR_ERROR with no private exception text. Definition
BLOCKED/DISABLED statuses prevent evaluation and report BLOCKED/NOT_RUN respectively.
An ACTIVE definition without captures reports unavailable execution, never PASS.

Supplying captures means execution was attempted. Missing outputs then fail rather
than becoming dependency blockers. Context checks bind captures to the snapshotted
scenario's catalog/policy, driver configuration, request text/step, session/revision
and fresh investigation identities. Application failures are distinct from normal
environmental abstention. Capture objects are an in-process data-flow boundary,
not signed credentials or a sandbox against a caller fabricating private objects.

This increment has no agentic scenario execution adapter, real Coordinator planning
or reviewed model/provider integration. Scenario reports therefore remain BLOCKED
when assertions otherwise succeed; active mandatory failures still report FAIL.
No capability flag allows a controlled demo to claim full scenario PASS. Existing
application/model/driver projections contain no expected assertions or report data.
Use `capture_report` with actual trusted runtime inputs; do not reconstruct captures
from expected values, create synthetic events after execution, or pass the evaluator
oracle into application callbacks.

## Commands and observed gaps

```bash
uv sync --locked
uv run --locked pytest
uv run --locked hafi evaluate SC-004 --fixtures fixtures/scenario-pack-v1
uv run --locked hafi evaluate SC-010 --fixtures fixtures/scenario-pack-v1
```

The CLI is readiness-only and never dispatches. It emits structured report JSON;
exit status is 2 for BLOCKED/NOT_RUN, 1 for FAIL, and 0 reserved for PASS. Both current
ACTIVE scenario definitions report BLOCKED with zero passing assertions when no
captures are supplied. No evaluation output files are written automatically.

The Python component API evaluated the unchanged authored assertions against the
existing durable demo reports and found genuine application gaps:

- SC-004-A028 expects preferred_area Kihei; the fixed demo omits that normalized
  value. Its remaining authored assertions pass after capture validation.
- SC-010-A054 expects INVESTIGATION_LIMIT_REACHED; its fixed planner stops with
  NO_FURTHER_ACTION before reaching an investigation limit. The evaluator preserves
  the missing-event failure rather than fabricating exhaustion. Its remaining
  assertions pass after adding the missing approved tool error-code field.

These are reported demo/execution gaps, not specification conflicts and not pytest
failures: tests assert that the independent evaluator finds them. No expected value,
fixture or stop reason was changed to manufacture a pass. Address request-aware
execution and justified investigation termination in a subsequent execution increment.

## Validation and remaining work

Tests cover operators, null/missing/cardinality behavior, non-vacuous comparisons,
strict JSON equality, bound/ambiguous/unbound selectors, observed counters,
cross-step references, immutable captures, invalid artifacts, readiness aggregation,
optional failures, context mismatch, fixture/evaluator diagnostic separation and
CLI non-dispatch behavior. Existing safety and trace validators remain the common
grounding gate rather than trusting ELIGIBLE or RESULT_VALIDATED labels alone.

Final validation: **1,215 tests passed in 30.18s** on Python 3.14.8, including
**41 new tests** over the 1,174-test baseline. The same 13 upstream LangSmith
deprecation warnings remain. Locked environment installation and installed CLI
readiness reports passed: SC-004 reports 84 BLOCKED assertions; SC-010 reports
61 BLOCKED assertions when no execution is supplied. Both exit 2 with zero passes.
Captured demo evaluation separately reports 83 PASS / 1 FAIL for SC-004 and
60 PASS / 1 FAIL for SC-010, exposing the gaps above. Python 3.12 syntax parsing
passed for all five changed/new Python files (not a separate 3.12 runtime test).
All 27 relative documentation links, code fences and `git diff --check` passed.
Approved specifications, fixture artifacts, pyproject.toml and uv.lock are unchanged.

No new specification conflict was found. Detailed production classifications,
provider/model activation, persistent sessions, evidence reuse, and full scenario
execution remain deferred. Recommended next work: the scenario execution adapter
and request/termination gaps identified above, with provider activation reviewed
separately before claiming model-driven ReAct or full M1 acceptance.
