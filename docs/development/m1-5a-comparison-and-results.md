# M1.5-A — Candidate comparison and Result Validation

This increment implements qualitative eligible-candidate comparison, controlled
synthetic Recommendation Results, independent contextual Result Validation and
matching terminal outcomes. It follows requirements 01 PR-012/013, requirements 03
RR-001..019, safety §15 and execution design §§13–15. Approved specifications,
logical schema fields, fixtures, configuration and dependencies are unchanged.

## Graph API and ownership

```python
report = await run_synthetic_tool_graph(
    normalized_request,
    catalog=application.catalog,
    candidate_beach_ids=candidate_ids,
    plan=plan_specialist_requests,
    tool_plan=plan_tool_actions,
    driver_inputs=scenario.driver,
    evidence_policy=application.policy_configuration,
    safety_evaluation=True,
    result_generation=True,
    record_event=record_component_event,
)
result = report.result
```

`result_generation` defaults to False and requires explicit safety evaluation.
Existing component modes retain their prior behavior and missing-capability stops.
The new mode adds `compare_candidates -> construct_result -> validate_result`
before finalization, after bounded investigation/safety assessment. It constructs
fictional synthetic outputs only; the CLI remains information/version-only.

`report.comparison` exposes comparison groups and selected/omitted assessment IDs.
`report.result` is available only after contextual validation **and** required
result/terminal event recording succeed. No source templates, driver scripts or
independent expected assertions enter comparison or Result Validation. The graph
still consumes only trusted explicit plans, not model-generated recommendations.

The `recommendations` package also provides standalone component functions:

- `ResultContext`: current active EVALUATING state, evidence/safety reports, catalog,
  policy, observed bindings and optional request step.
- `compare_candidates(context)`: verified qualitative groups and bounded selection.
- `build_result(context, generated_at=..., stop_reason=...)`: controlled proposal.
- `validate_result(proposal, context, now=..., stop_reason=...)`: independent
  validation returning a detached RecommendationResult.
- `build_error_result` / `validate_error_result`: sanitized operational errors,
  requiring known request context and an explicit trusted failure code.

Standalone callers supply the current active snapshot and explicit aware clock.
These functions do not manage session admission, historical storage or publication.
Terminal input snapshots cannot be reopened. The fixed evidence reference clock
remains separate from actual result generation time; source timestamps and target
windows are preserved rather than updated to make old fixture evidence current.

## Comparison choices

Only freshly verified ELIGIBLE / SUFFICIENT / FAVORABLE-or-permitted-MIXED assessments
enter comparison. Evidence validation and safety evaluation are recomputed against
the current catalog, policy and bindings. Assessment content, revision, original
request, constraints, source payloads, candidates and counters must match the
active state. A controller may advance status to EVALUATING and update its timestamp;
other unassessed changes fail closed. Approved execution maxima/counters are checked.

Comparison uses qualitative dominance on two documented criteria:

1. FAVORABLE versus reviewed MIXED suitability.
2. Established canonical PREFERRED_AREA versus OUTSIDE_PREFERRED_AREA matches.

One candidate precedes another only when it is no worse on all comparable criteria
and better on at least one. FAVORABLE/outside versus MIXED/preferred is an unresolved
tradeoff. Unknown comparisons do not become favorable preferences. No arbitrary
scores, weights, source-count bonuses, limitation counts, or travel estimates are
introduced. Opaque preference interpretation remains open and cannot override safety.

Non-dominated groups are retained. Within a group, catalog beach-ID order provides
repeatable presentation and truncation, **not** a merit distinction. Numeric `rank`
is omitted because detailed total-ranking/tie policy remains open. Up to three
eligible candidates are selected; no excluded, unsupported, insufficient or unresolved
candidate fills unused slots. Omitted eligible options and unresolved ordering are
explained without claiming that a stable identifier makes an option better.

This is a conservative implementation of the approved qualitative criteria. More
specific preference normalization or total-ranking rules remain reviewable future
design work.

## Construction and contextual validation

Every recommendation references its actual current assessment, verified catalog
name, requested supported interval and scoped ACCEPTED finding IDs. Source IDs
come from accepted findings and attributable catalog references. Original evidence
coverage and type remain intact; regional/area support receives an explicit
limitation and is never described as direct beach observation. Applicable reported
advisory IDs and source disclosures are retained without spreading another named
beach's advisory to the recommended candidate.

MIXED permission is recomputed and its required disclosure is retained verbatim in
recommendation warnings. Evidence limitations, including material optional missing
visibility, remain visible. Outside-area recommendations explain their inclusion
on evidence and safety grounds. No unchecked alternative location is presented as
already verified. All outputs carry explicit synthetic-only labeling.

The current Result Validator supports the deterministic constructor's templates
and selection protocol. It does not pretend to semantically validate unrestricted
model prose merely because IDs resolve. Changed claims, ranks, selection, context,
time windows, source IDs or required warnings/limitations are rejected. Future
model-assisted wording requires its own grounded-construction boundary. The Pydantic
contracts continue to handle local structure; the contextual validator establishes
current eligibility, real references, grounding, disclosures and permitted selection.

Generated timestamps must be aware, follow the current investigation snapshot and
not exceed the explicitly supplied validation time. Content-derived IDs bind the
result and recommendation to their current context. Mutable caller-owned lists
cannot change the original context or a newly constructed result.

## Outcome classification

| Validated outcome | Terminal state | Meaning |
|---|---|---|
| RECOMMENDATIONS | COMPLETED | One to three currently eligible synthetic recommendations |
| NO_RECOMMENDATION | ABSTAINED | Explained environmental/evidence/constraint limitation |
| ERROR | FAILED | Sanitized operational failure, no recommendations |

All three keep state/result identity and outcome consistent. Handled provider
ERROR/UNAVAILABLE/TIMEOUT/MALFORMED responses can lead to explained abstention;
failed retrieval is not itself a finding that a beach is unsuitable.

No-recommendation reasons describe actual assessments. All verified exclusions
prefer APPLICABLE_HAZARDS; excluded/unsupported-only sets use NO_ELIGIBLE_CANDIDATES.
Otherwise actual material conflicts, unresolved hard constraints, an actual iteration
limit, insufficient evidence, or other unmet eligibility questions determine the
reason and explanation. Source/policy questions and affected candidates are retained.
An iteration limit never upgrades evidence or eligibility. Already eligible evidence
may still support recommendations at the limit without dispatching more work.

Unrecovered specialist contract/execution failures with no eligible alternative
are operational ERROR outcomes. Unexpected graph/application exceptions and invalid
proposed results also produce sanitized ERROR results while event recording works.
Failure codes are restricted to trusted component diagnoses; arbitrary exception
text, credentials and stack traces are not exposed. Source outages cannot be
relabeled ERROR merely by using a source diagnostic as the failure code.

Initial clarification remains nonterminal with no result. The required result
schema cannot express an unknown activity/window: early technical failures with
incomplete request context retain operational diagnostics rather than inventing
those values to construct an ERROR object.

## Commit boundary and remaining scope

The Result Validator records actual RESULT_VALIDATED only after validation. The
matching terminal event is then recorded before assigning `report.result` and the
terminal logical state. Recorder failure at either boundary closes execution,
suppresses the proposed result and current assessments, and reports operational
FAILED / ERROR diagnostics with `result=None`. Missing events are not fabricated.
There is no new model/tool work in comparison, construction or validation, and
closed/terminal investigations cannot dispatch more work or resume.

Memory event recorders remain test seams. Authoritative append-only JSONL,
production runtime admission, request normalization/catalog selection, CLI result
rendering, conversational follow-ups and independent scenario assertion execution
remain separate work. SC-004 and SC-010 execution readiness stays BLOCKED. Remote
LangSmith tracing remains disabled by the graph.

Hard-constraint/soft-preference input semantics, provider activation and real-world
freshness/numeric hazard thresholds remain open as previously documented. Opaque
hard constraints remain UNKNOWN and prevent recommendations; no input DSL or new
autonomous role was added.

## Verification

```bash
uv sync --locked
uv run --locked pytest tests/test_results.py tests/test_result_graph.py
uv run --locked pytest
uv run --locked hafi --version
```

**800 tests passed**, including 40 new comparison/result/graph checks. Coverage
includes the three-location cap, ties/tradeoffs, excluded candidates, MIXED permission
and disclosure, stale references/revisions/constraints, broadened time windows,
false prose/source claims, budget bounds, abstention/error separation, sanitized
exceptions, and result/terminal trace-write failure. The 13 existing upstream
LangSmith deprecation warnings remain on Python 3.14.

The result-enabled SC-004 component returns only fictional Beach B and ends
COMPLETED. SC-010 ends ABSTAINED with INSUFFICIENT_EVIDENCE after the eight planned
calls. These are pipeline component checks, not full independent scenario acceptance
runs. The existing MIXED test helper was shared without changing earlier tests'
behavior; multi-candidate unit data groups findings into shared source calls to
stay within approved invocation limits.

Next proposed work: M1.5-B — CLI presentation of validated synthetic outcomes,
with explicit boundaries for incomplete request interpretation and session handling.
Authoritative tracing and full acceptance remain independently reviewable milestones.
