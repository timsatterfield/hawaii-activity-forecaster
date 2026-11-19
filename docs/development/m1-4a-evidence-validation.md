# M1.4-A — Deterministic evidence validation

This increment implements independent synthetic evidence validation and activity-
specific category accounting from M1.4. It follows requirements 03/04/05, the
[execution design §11](../implementation/m1-langgraph-execution-design.md), and
[approved harness rules §4](../implementation/m1-scenario-harness-contract-design.md).
Approved specifications, logical schemas, fixtures and dependency versions are
unchanged. Safety-policy outcomes, Candidate Assessments, eligibility, suitability,
Recommendation Results and environmental abstention remain separate increments.

## API and integration

The synthetic graph now accepts an optional approved policy projection:

```python
report = await run_synthetic_tool_graph(
    normalized_request,
    catalog=application.catalog,
    candidate_beach_ids=candidate_ids,
    plan=plan_specialist_requests,
    tool_plan=plan_tool_actions,
    driver_inputs=scenario.driver,
    evidence_policy=application.policy_configuration,
    record_event=record_component_event,
)
coverage = report.evidence_report.candidates
```

With `evidence_policy`, the graph checks the supplied activity profile and rule
context before environmental dispatch, then runs `validate_evidence` after each
specialist join. Its fixed reference time is the selected script request step's
reference time, not the machine clock or virtual tool completion time. Catalog and
policy inputs are detached snapshots. Source templates and evaluator assertions
are not passed to the validator or planners. Existing graph APIs and the default
`evidence_policy=None` path preserve M1.3 behavior, leaving findings PENDING.

`validation.validate_evidence()` also accepts an active logical state, catalog,
policy, observed `DispatchBinding` records, explicit aware `reference_time`, optional
request step, and trusted `RetrievalGap` correlations. It returns a detached
`EvidenceValidationReport`. These report dataclasses are internal component
results, not new authoritative logical schemas. The standalone validator does not
advance execution timestamps or write files; the graph records actual validation
events before committing the returned snapshot. Terminal states cannot be reopened
or revalidated through this API.

`report.evidence_report` describes the latest committed validation-node snapshot;
`report.state` is the final operational graph state. The graph still stops FAILED /
ERROR at the missing safety/result-validator boundary. No public recommendation
result is generated. A prior M1.3 terminal report cannot be retroactively validated;
enable the option during a new run instead.

## Independent finding checks

Every received finding is structurally revalidated and matched to observed runtime
bindings. A declaration or template never substitutes for retrieval. Binding
identity includes investigation, request step, source fixture, template finding and
runtime call/finding identity. Identical binding replay is idempotent; ambiguous
runtime call or finding identities fail closed. All matching actual retrievals
remain available; no completion order chooses a latest winning source.

Validation checks:

- Approved source/domain and identifiable provenance, separate retrieval status,
  and the category/source mappings approved for synthetic evidence.
- Actual candidate scope. BEACH evidence can support only its named beach.
  LOCAL_AREA/REGIONAL evidence needs its original coverage identifier, an explicit
  rule mapping and attributable verified catalog context. Nothing is retagged as
  a direct beach observation.
- Original source timestamps against the fixed reference time. Future retrieval,
  issuance or observation timestamps, and publication after retrieval, are invalid.
  Forecast measurement times may still describe the requested future period.
- COVERS_TARGET_WINDOW permits forecast/advisory validity covering the entire
  target interval. DECLARED_REPORT_WINDOW requires a report with explicit covering
  applicability. Retrieval/publication dates do not replace validity. Missing
  temporal metadata remains LIMITED; an uncovered/expired target is REJECTED for
  that intended use. No live-provider TTL or universal age limit is invented.
- OFFSHORE, NDBC, HWT_NARRATIVE and explicit CONTEXT_ONLY uses remain contextual.
  They cannot satisfy mandatory beach categories. Observations preserve their
  observation time and never become forecasts.
- Existing schema integrity, numeric units/range structure, explicit missing
  fields, partial retrieval and content completeness. Surf-height FACE and
  HAWAIIAN_BACK conventions stay distinct; missing/unknown/unreviewed conventions
  remain LIMITED. Values, units and measurement types are never converted.
  Provider-specific numeric interpretation and hazard thresholds remain open.
- Embedded advisory intervals use half-open temporal overlap. Missing intervals
  remain unknown and limit the finding. An expired individual advisory does not
  erase a valid listing/status check. The report records temporal overlap only;
  individual advisory geographic/hazard applicability belongs to later policy
  evaluation. No empty advisory list implies a completed check or safe water.

Original source references, limitations, timestamps, advisory IDs, measurements
and coverage are retained. Only validation_status changes. Arbitrary limitation
prose is not parsed into policy: the authored synthetic disclaimer remains present
without making every fictional source unusable. Explicit partial/missing metadata
still prevents acceptance.

Decisions name finding, rule, beach, category, validation status and reason codes.
Because one logical finding has one validation_status, its worst intended-use
verdict is conservatively propagated across its applicable rules. This prevents a
LIMITED/REJECTED finding from positively filling another category through a more
permissive mapping; all individual reasons remain visible.

## Category accounting and conflicts

The report has one `CategoryCoverage` per candidate/category and an activity-specific
MANDATORY/RELEVANT/OPTIONAL priority. Accepted applicable findings may cover a
category; LIMITED/contextual/rejected findings are retained separately and never
fill mandatory support by themselves. Source counts and confidence scores are not
used. Wind is mandatory for SUP and relevant for swimming/snorkeling. Visibility
remains optional under the approved profiles; user hard constraints remain for
independent constraint evaluation.

Official and water-contact checks additionally require an explicit true complete-
check premise, with actual accepted support scoped to the candidate/activity/time.
False, omitted or unreceived support never implies a completed check or absence of
hazards. No other environmental hazard premise is converted to PASS/FAIL here.

VERIFIED_BEACH_CHARACTERISTICS checks catalog verification status, supported
activity, nonfuture verification/access dates, and source attribution of existing
required identity/geographic/activity fields plus populated material characteristics.
Missing optional attributes are not invented. UNKNOWN remains UNKNOWN. Calendar
checks use Hawaii time (UTC-10). This does not settle the open minimum optional
attributes or re-verification interval for activating real catalog beaches.

Supported true MATERIAL_SAFETY_CONFLICT_PRESENT premises identify unresolved
synthetic material conflicts. Their actual findings remain present and become
LIMITED, with conflict reasons/issues. Missing or rejected support does not fabricate
an observed conflict. General numeric/prose conflict inference and hazard-specific
materiality remain deferred; independent opposing findings are never averaged or
discarded. Absence of a supported materiality premise is not a policy PASS.

`CandidateEvidenceCoverage.mandatory_categories_covered` means only that the
profile's declared categories have accepted support and completed check evidence.
It is **not** EvidenceQuality.SUFFICIENT, resolved safety policies, satisfied hard
constraints, safe conditions, eligibility or a recommendation. SC-004 illustrates
why: mandatory category coverage can exist alongside an actual advisory requiring
later deterministic exclusion.

## Issues, recovery and trace writes

Uncovered categories produce stable evidence issues with finding/candidate
references and MISSING, STALE, COVERAGE_MISMATCH, INVALID or CONFLICTING type as
appropriate. Revalidation preserves records and deterministically updates their
resolved flags. Issue identity includes investigation/revision, candidate/category
and UTC-normalized target-window instants.

The synthetic dispatcher now exposes frozen `RetrievalGap` scope metadata for the
operational gap IDs it creates. Only those trusted correlations can connect an
older retrieval issue to current category coverage; all candidates in that gap
must be covered to resolve it. Opaque unrelated issues, contract errors and failure
history are preserved. The validator never guesses a category by parsing prose
or recomputing arbitrary caller labels. Existing fallback budget IDs/allowances
are unchanged and cannot be reset by resolving an issue.

When validation is enabled, graph continuation considers unresolved mandatory
coverage or observed material conflicts. Optional missing visibility and historical
recovery diagnostics alone do not force another cycle. A trusted permitted plan
is still required, and the sixth cycle cannot start. The framework recursion guard
allows the additional validation node while preserving the five-cycle application
limit. The validator itself consumes no tool/model calls.

Only actual EVIDENCE_VALIDATED, EVIDENCE_REJECTED and supported
EVIDENCE_CONFLICT_DETECTED events are recorded, with findings, rules and reasons.
Recorder failure closes execution and prevents the validation snapshot from being
committed. No policy/result success is fabricated. Local authoritative JSONL,
production investigation execution and full scenario acceptance remain deferred;
memory recorders are test seams. Remote LangSmith tracing stays disabled.

## Verification and next increment

```bash
uv sync --locked
uv run --locked pytest tests/test_evidence_validation.py tests/test_evidence_graph.py
uv run --locked pytest
uv run --locked hafi --version
```

**718 tests passed**, including 49 new evidence/unit/graph checks. Coverage includes
provenance, received-vs-declared bindings, timezone equivalence, stale/missing time
metadata, source permissions, context-only data, measurement conventions, advisory
overlap, source-backed catalog fields, complete-check premises, activity profiles,
conflicts, stable revalidation, terminal integrity, trace failure and five cycles.

Authored component checks execute SC-004's six planned source calls and SC-010's
eight planned calls (one retry/two fallbacks). SC-004 has category coverage but no
eligibility verdict; SC-010 retains missing mandatory support despite its call
count. Both full scenarios remain execution-BLOCKED. No evaluator assertion or
expected safety outcome drives planning/validation. Thirteen existing upstream
LangSmith deprecation warnings remain on Python 3.14.

No approved specification conflict was found. The next proposed increment is
M1.4-B — deterministic synthetic safety-policy evaluation and Candidate Assessments,
using actual validated findings, explicit supported premises and independent
eligibility/suitability/evidence-quality fields. Result generation, model/provider
activation, full tracing and acceptance readiness remain separate work.
