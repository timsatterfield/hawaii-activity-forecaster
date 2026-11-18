# M1.1-F — Scenario harness contracts and v2 preflight

This increment implements step 1 of the approved
[M1.1-E design](../implementation/m1-scenario-harness-contract-design.md): typed
harness formats, v2 loading/projections and evaluator-assertion validation. It
implements no scenario execution, operator evaluation, policy evaluation, clocks,
dispatch, binding-index generation, budget manager, graph, or trace writer.

## API and boundaries

```python
from hawaii_activity_forecaster.harness import load_scenario

loaded = load_scenario("path/to/a/v2/package", "SC-004")
application = loaded.application   # user request, fixed clock, catalog, policy inputs
trusted_driver = loaded.driver     # behavior script, selected responses, malformed payloads
independent_evaluator = loaded.evaluator  # assertions and artifact byte digests
readiness = loaded.execution_readiness   # BLOCKED or NOT_RUN; never PASS
```

The path above is illustrative: no complete SC-004/SC-010 package is added by
this increment. The next authoring increment supplies those independently reviewed
inputs/assertions. The current v1 catalog/source examples do not become complete
scenarios merely because the v2 contract exists.

Only ApplicationInputs belongs in the application-facing projection. DriverInputs
is for trusted test tooling, not Coordinator/specialist model context. The logical
TestScenario at `loaded.definition` is harness-owned and resolves expected_results
to the required structured object; it must never be passed to application/model
code. EvaluatorInputs alone receives artifact paths/digests and expected values.
This is an API/data-flow boundary, not OS/process isolation.

The loader reads each resolved artifact's bytes once and records SHA-256 digests
of those same bytes. It returns immutable serialized snapshots; each property
access reconstructs a fresh validated copy, so mutating a nested list/map or
changing a file after preflight does not alter another view or the frozen oracle.
No provider/SDK environment variables or remote services are used.

## Organization

| Module under `src/hawaii_activity_forecaster/harness/` | Responsibility |
|---|---|
| policy.py | Closed categories, activity matrix, explicit boolean premises and narrow MIXED metadata |
| behavior.py | Request sequence, exact dispatch-pattern declarations and seven behavior shapes |
| assertions.py | Closed targets/selectors/operators, readiness reasons and typed JSON Pointers/operands |
| contracts.py | v2 manifest, source sets, physical/logical scenario records and separate projections |
| preflight.py | Cross-artifact source, category, reference, coverage and malformed-fault checks |
| loading.py | Explicit loading, byte snapshots/digests, resolved TestScenario and execution blockers |
| requirements.py | Frozen identifier inventory from the approved requirements/implementation documents |

The identifier inventory contains references, not policy rules or expected outcomes.
Refresh it deliberately if approved specifications add/remove identifiers. Runtime
loading does not scan Markdown or depend on source documentation being installed.

## Compatibility and implemented checks

`load_fixture_inputs()` remains v1-only and unchanged. `load_scenario()` accepts
only the approved v2 tuple: format 2.0.0, package 1.1.0, data schema 0.1, logical
policy 0.2, harness contracts 1.0.0, synthetic policy configuration
synthetic-policy-1.0.0. Unsupported versions fail before executable inputs are
returned. No existing fixture bytes or approved document are modified.

V2 preflight reuses the existing JSON/path validation primitives internally. It
rejects duplicate keys, nonfinite JSON numbers, path traversal and resolved
symlink targets outside each artifact's permitted subtree. It validates registered
scenario IDs/catalog paths, source sets/domains, ordinary tool response schemas,
synthetic error structures, cross-file call/finding identities, candidate refs,
category/provider mappings, declared evidence coverage or explicit scripted gaps,
and references in premises/assertions. Unsupported activity combinations remain
representable; they are not silently promoted or filtered.

Profiles partition the seven categories and retain the approved matrix. Premises
require explicit strict boolean values and scoped support. They cannot contain
final eligibility/policy/suitability/evidence-quality fields. These checks do not
establish that a finding is valid for use or that a hypothetical classification
is true; the independent runtime Evidence Validator and Safety Policy Evaluator
must enforce those meanings before premises can support a result.

Behavior declarations enforce contiguous request/attempt numbering, one retry
slot per original operation, unique exact dispatch patterns, timeout/delivery
threshold consistency, behavior-specific fields, and provider/status/scope
agreement. MALFORMED JSON is loaded only from its own subtree, must actually fail
the tool contract and may have only narrowly declared field faults. Ordinary
source validation remains strict. These declarations do not authorize or perform
any actual retry/fallback, mutate IDs, count calls, merge responses or deliver data.

Assertions reject unknown targets/operators, non-document fields, wildcards,
negative indices, missing/extra operands, invalid readiness/blocker combinations,
unknown requirement/reference IDs and incompatible expected types. Only the
approved structured trace-detail fields may be selected; arbitrary generic JSON
objects cannot be traversed as private state. SAME_AS/DIFFERENT_FROM compare
compatible declared observation types. Explicit expected:null survives snapshots
without being confused with an absent operand. Nonnegative count operands reject
booleans, floats and numeric strings.

## What a successful preflight does not mean

A valid definition is structurally loadable, not runnable acceptance coverage.
An ACTIVE scenario reports BLOCKED because runtime request handling, specialists,
tools, evidence/policy/result validation, budget controls and authoritative trace
execution are missing. BLOCKED definitions remain BLOCKED; DISABLED becomes
NOT_RUN. This increment has no API to turn supplied mock capability flags into a
scenario PASS and makes no claim that SC-001 through SC-012 have executed.

The following approved checks remain runtime/authoring work:

- Actual evidence acceptance, absent/rejected support handling and authoritative
  hazard precedence (SH-T04/05/07), including complete candidate premise sets.
- Independent scenario assertion plans covering all common contract, safety,
  grounding, outcome, bounds, permissions and trace gates, not just the definition's
  explicitly listed requirement IDs. The loader checks declared mandatory coverage;
  it does not synthesize an adequate acceptance plan from requirement names.
- Matching real dispatches, virtual/real timeout execution, atomic budgets,
  deduplication, merging, binding-index creation and actual state transitions
  (SH-T08–13/18/20).
- Evaluation against captured observations: cardinality, non-vacuous ALL_EQUALS,
  missing-capture/pointer failures, strict comparisons, aggregate PASS/FAIL/BLOCKED/
  NOT_RUN reports and evaluator-error diagnostics (runtime portions of SH-T15–17).
- Genuine model-driven reasoning, real-provider activation, production thresholds,
  historical reuse storage and the other explicitly deferred design decisions.

No skipped or stubbed runtime check is counted as passing. Preflight validates
artifact contracts, not the final trace or real-world environmental truth.

## Verification and next increment

```bash
uv sync --locked
uv run --locked pytest tests/test_harness_contracts.py tests/test_harness_loading.py
uv run --locked pytest
```

Tests create temporary contract-only v2 packages from fictional v1 inputs. They
independently exercise invalid schema/versions/references, grammar/type validation,
source permissions, explicit gaps, fault injection, source/clock preservation,
follow-up request definitions, v1 compatibility, snapshot isolation and oracle
separation. They are not authored substitutes for the twelve acceptance scenarios.

Next: author complete SC-004 and SC-010 inputs and independent assertion plans,
keeping execution blocked until the approved runtime components and evaluator
are implemented. Existing CLI behavior, configuration, dependencies, approved
specifications and v1 fixtures remain unchanged.
