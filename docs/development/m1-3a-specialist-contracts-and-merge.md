# M1.3-A — Specialist contracts and trusted evidence merge

This implements the contract boundary and parallel merge portion of M1.3 from the
approved [execution design](../implementation/m1-langgraph-execution-design.md),
[technical plan](../implementation/m1-technical-plan.md), and requirements 04
(SRQ, SRS, and ST rules). It does not implement environmental tools, a model-backed
Coordinator, evidence/safety evaluators, or a production investigation executor.

## Components and use

`orchestration.run_specialist_graph()` connects the existing LangGraph runtime to
`SpecialistInvestigationRequest` and `SpecialistInvestigationResponse`. Like
`run_skeleton()`, it is an async component API with injected synthetic callbacks:

```python
report = await run_specialist_graph(
    normalized_request,
    catalog=synthetic_catalog,
    candidate_beach_ids=("TEST_BEACH_A",),
    plan=plan_requests,
    specialist=synthetic_specialist,
    record_event=record_component_event,
)
```

`plan_requests(state_snapshot)` returns a tuple of scoped request models, at most
one per domain. It must use the snapshot's investigation ID, revision, schema
version and target window, catalog-backed candidates, fresh logical request IDs,
and the approved synthetic evidence categories. It receives a detached snapshot;
mutating its lists does not change trusted state. `synthetic_specialist(request)`
is an async callback returning a response model or corresponding dictionary. Its
input and output are detached from the graph and private authorization ledger.
These are test seams, not new autonomous agent roles or provider adapters.

The contract path adds `plan_evidence` and
`validate_and_merge_specialist_responses` to the existing topology. Authorization
happens before dispatch. Weather and Ocean execute in parallel when both are
delegated; an undelegated branch skips its callback, and the join still runs once.
One parallel dispatch counts as one investigation cycle. Continuation requires
explicit unresolved issues/errors and a further authorized plan; an empty plan
stops, and the sixth cycle cannot begin. Actual model/tool invocation counts remain
zero because this increment executes neither kind of external operation.

The earlier `BranchInput` / `BranchSignal` API remains available unchanged.
Initialization now uses logical `schema_version="0.1"`, matching requirements 03
and existing fixture manifests; the previous skeleton incorrectly used `1.0.0`.
Harness format and package versions remain separate and unchanged.

## Trusted authorization and correlation

`SpecialistExchange` is a per-investigation ledger called sequentially by trusted
authorization/join nodes. It is not a concurrent branch writer or a persistent
store. Request validation checks active identity/revision, schema version, domain,
catalog membership and delegated candidates, target window, documented evidence
categories and source-domain permissions, known finding references, issue time,
and deadlines. A proposed batch is registered only after all requests validate.

The synthetic category/source table is reused from the approved harness policy
contracts; it contains no scenario expectations. Catalog characteristics remain a
Coordinator/catalog concern and cannot be delegated as environmental retrieval.
The requirements 04 §13 source-domain allowlist is shared with the existing v1
loader through `models.permissions`, preserving its previous behavior.

A `SpecialistDelivery` pairs the returned payload with dispatcher-owned logical
request/attempt identity. This prevents one branch from impersonating the other
by changing response fields. Merge checks exact request, investigation, revision,
role, schema and attempt correlation, complete nested schemas, source permission,
requested source categories, candidate scope, gap references and response timing.
A response cannot contain extra authoritative state or recommendation fields.

A later registered specialist attempt retains logical delegation identity and
increments the attempt number; it supersedes the previous attempt. Registering
attempts does **not** grant a retry allowance or execute recovery. Actual bounded
retry/fallback scheduling remains deferred. Deadlines supplied on requests are
enforced at callback dispatch and receipt, including cancellation on timeout.
The tool/model timeout policies are not repurposed as specialist timeouts.

## Merge semantics

The join validates all collected deliveries before one logical state update:

- Valid sibling findings survive a malformed response, callback exception, timeout,
  ERROR, or UNAVAILABLE response from the other specialist.
- New findings enter state as PENDING regardless of a callback's validation claim.
  Existing independently validated statuses survive repeat delivery. Contract
  acceptance is not evidence acceptance or proof of requested-category completeness.
- Findings retain source attribution, measurements, regional/offshore coverage,
  and original retrieval/issuance/observation/validity timestamps. No regional or
  offshore finding is converted to direct beach evidence.
- Repeated response IDs are idempotent after normalization of the non-authoritative
  validation-status field. Repeated finding IDs with identical content do not
  create duplicate findings, even across different response IDs.
- Changed content under a response, finding, gap or error ID quarantines affected
  responses. If conflicting variants arrive in the same collected batch, all
  affected variants are rejected, so completion order cannot select a winner.
  Across later batches, previously committed content is immutable. A rejected
  replay cannot erase previously completed work.
- Independent findings with different IDs remain present even when their reports
  conflict. This component neither resolves nor classifies material environmental
  conflicts; those decisions belong to the later evidence/safety evaluators.
- Explicit gaps become unresolved `EvidenceIssue` records, conservatively associated
  with that request's candidate set. Structured specialist errors retain their
  fields plus request/attempt attribution. A valid reply never silently resolves
  an earlier issue; independent evaluation remains deferred.
- Unknown/outdated execution envelopes, stale response identity/revision/attempt,
  and inactive/terminal investigations cannot change current logical state.
  Observations may still appear in rejection reports/events. Malformed current
  deliveries produce structured operational errors, without changing assessments,
  hard constraints, preferences, eligibility, status, or budgets in the merge step.

Response and finding/issue lists use stable ID ordering; error records use
deterministic content ordering. Duplicate/stale-only batches do not change
`updated_at`. The caller supplies receipt time to standalone ledger methods,
allowing tests to use a fixed synthetic clock.

## Outcome and tracing boundary

The graph still stops before evidence/safety/result validators. It returns an
operational FAILED / ERROR state identifying the missing-validator boundary,
iteration exhaustion, invalid delegation, or trace failure. It constructs no public
`RecommendationResult`, environmental abstention, or real recommendation.
SC-004 and SC-010 remain execution-blocked.

Existing trace contracts record actual request/response validation outcomes,
request/response/attempt correlations, branch completion/failure, and receipt of
PENDING material. No evidence-validation, policy-evaluation or result-validation
success is fabricated. Recorder failures block further dispatch and prevent the
merge from being committed to returned graph state. Remote LangSmith tracing
remains explicitly disabled even with ambient tracing variables set.

Memory recorders in tests are not authoritative local JSONL traces. The JSONL
writer, full trace metadata, acceptance driver, scenario readiness transition,
active-session resumption and conversational follow-ups remain future work.

## Validation

```bash
uv sync --locked
uv run --locked pytest tests/test_specialist_exchange.py tests/test_specialist_graph.py
uv run --locked pytest
uv run --locked hafi --version
```

Tests use fictional catalog entries and synthetic contract payloads. Coverage
includes authorization, correlation, branch impersonation, deadlines, mutation
isolation, opposite completion orders, source/candidate scope, exact replays,
identifier/content collisions, preserved conflicts/gaps/errors, late attempts,
terminal integrity, failure isolation, the five-cycle guard, and trace failure.
These are contract/control-flow checks, not full scenario or safety acceptance.

Validation on the implementation branch: **639 tests passed**, including 67 new
specialist tests. Locked dependency sync, public API imports, CLI startup and
`git diff --check` also passed. Python 3.14 reports 13 existing upstream LangSmith
deprecation warnings for `asyncio.iscoroutinefunction`; no warnings are suppressed.

All relevant approved specifications are present; no specification changes are
needed. The next proposed increment is M1.3-B — scoped synthetic tool dispatch,
using the approved behavior scripts with actual environmental-call accounting and
bounded recovery. Safety/result evaluation and production tracing remain separate.
