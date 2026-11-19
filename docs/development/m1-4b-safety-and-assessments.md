# M1.4-B — Safety policy evaluation and Candidate Assessments

This increment implements deterministic synthetic safety evaluation and trusted
Candidate Assessment creation under requirements 03/05, execution design §12, and
the approved harness premise/MIXED contracts. Approved requirements, implementation
specifications, schemas, fixtures and dependencies remain unchanged. There are no
LLM/provider calls, recommendation comparison, public Recommendation Results,
production trace writer, or full scenario acceptance execution.

## API and trusted inputs

Enable the additional graph node explicitly:

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
    record_event=record_component_event,
)
assessments = report.state.assessments
```

The default remains `safety_evaluation=False` for compatibility. Enabling it
requires the explicit evidence policy. The graph runs `evaluate_safety` after
`validate_evidence`, then routes using assessment eligibility rather than treating
source-call counts or optional missing visibility as a safety verdict.

The standalone `validation.evaluate_safety(evidence_report, catalog=..., policy=...,
bindings=...)` accepts an active `EvidenceValidationReport` and observed bindings.
It independently recomputes evidence validation and rejects stale or inconsistent
reports before creating assessments. Terminal snapshots cannot be reassessed.
Only actual received findings with matching candidate/activity/time and allowed
category support may establish synthetic premises. A template, false/omitted
premise, or caller-supplied eligibility value cannot substitute for evidence.

The evaluator consumes only approved application policy and actual runtime
bindings. Independent expected assertions remain in the evaluator projection.
Catalog/policy inputs and returned state are detached snapshots; prior assessment
objects are never edited in place.

## Deterministic policy handling

PolicyResult records use existing requirement IDs and PASS / FAIL / UNKNOWN /
NOT_APPLICABLE values. The implemented groups are:

| Input or check | Policy basis | Handling |
|---|---|---|
| Verified catalog/activity support | BC-007 | Missing support remains non-recommendable |
| Mandatory category coverage | ES-V002 | Missing accepted basis remains UNKNOWN |
| Official advisory check | ES-005 | Requires actual supported complete-check premise |
| Water-contact check | HM-WATER-005 | Failure/absence never implies clear water |
| Water-contact avoidance advisory | HM-WATER-001 | Supported true hazard requires exclusion |
| Disqualifying surf | HM-SURF-004 | Uses scoped synthetic classification, no numeric cutoff |
| Dangerous currents | HM-CURRENT-004 | Cannot be overridden by favorable forecasts |
| Disqualifying weather/prohibition | HM-WEATHER-003 | Evaluated independently of comfort/preferences |
| Offshore wind exposure | HM-WIND-002 | Explicitly required for SUP; other activities need their own hazard interpretation |
| Persistent beach characteristic | HM-BEACH-004 | Requires attributable populated catalog-field support |
| Material safety conflict | ES-009 | Unresolved conflict prevents eligibility |
| Positive activity support | ES-007 | Absent/false support never becomes favorable |
| Reviewed visibility limitation | HM-VIS-003 | DISCLOSE; MIXED permission is separately gated |

A supported true disqualifying hazard produces FAIL; a supported explicit false
hazard can produce PASS only when required evidence and applicability hold. Missing,
stale, rejected, wrong-category or unreceived support stays UNKNOWN. Ordinary LIMITED
or contextual information cannot clear a mandatory hazard or establish a verified
exclusion. Supported material conflicts retain the actual findings. A finding
limited solely by a supported conflict may still establish a negative hazard;
it cannot establish favorable conditions or fill mandatory accepted coverage.
Explicit UNKNOWN catalog attributes cannot resolve a persistent-hazard fact.

Structured official notices are checked independently of premise ordering. The
known authored synthetic water-contact avoidance type, authoritative source,
named beach and temporal overlap require exclusion even against a false hazard
premise or conflicting favorable reports. Unknown notice meaning/geography/timing
remains unresolved; an advisory is not automatically a closure. Expired notices or
notices explicitly naming another catalog beach do not automatically exclude this
candidate. This is a narrow synthetic interpretation, not a real-provider advisory
parser or a general natural-language classifier.

For swimming/snorkeling, an absent SUP-specific offshore-wind premise is
NOT_APPLICABLE. An explicitly reported dangerous offshore-wind question for those
activities remains UNKNOWN until a documented activity-specific classification
resolves it; it is not an automatic SUP-style exclusion. No wind/surf thresholds,
unit conversions, confidence scores or experience-based cutoffs are introduced.

## Independent assessment dimensions

A verified disqualifying FAIL always yields EXCLUDED / UNFAVORABLE, even if other
checks remain unknown. Unsupported/unverified catalog/activity combinations without
a verified failure yield UNSUPPORTED. All other candidates remain NEEDS_INVESTIGATION
unless every eligibility prerequisite holds.

Evidence quality is evaluated independently:

- INSUFFICIENT: a mandatory category has no usable basis, or catalog support fails.
- LIMITED: useful evidence exists but mandatory classifications or material
  conflicts remain unresolved.
- SUFFICIENT: mandatory categories have accepted applicable support and mandatory
  safety questions are resolved. Known adverse evidence can still be SUFFICIENT.

Positive accepted activity support is required for FAVORABLE. Missing/false positive
support stays UNDETERMINED and cannot be ELIGIBLE, even when the evidence quality is
SUFFICIENT. Verified adverse conditions remain UNFAVORABLE. Soft preferences never
change a safety result or promote a non-eligible candidate.

For reviewed `SYNTHETIC_POOR_VISIBILITY`, MIXED eligibility requires accepted scoped
limitation support, sufficient mandatory evidence, resolved hazards, no exclusion,
passing hard constraints, positive activity support and the approved snorkeling
MIXED permission. Its exact disclosure is retained in `safety_limitations` for the
future Result Validator. Missing permission keeps the candidate non-recommendable;
poor visibility alone does not cause exclusion. Optional unavailable visibility
is disclosed in evidence limitations without implying good visibility or
independently blocking an otherwise eligible candidate.

## Open input semantics retained conservatively

Approved normalized-request fields still represent hard constraints and soft
preferences as opaque JSON objects; their concrete interpretation remains open.
This increment does not invent an input DSL or trust embedded `result: PASS/FAIL`
keys. Every uninterpreted hard constraint produces a stable ConstraintResult with
UNKNOWN, blocks eligibility and requests clarification. Soft preferences produce
UNKNOWN alignment without overriding policy. Their original request data remains
unchanged. Deterministic interpretation of specific hard constraints, including
how verified PASS/FAIL results are derived, still needs an approved normalization
contract; the existing CandidateAssessment schema already enforces exclusion for
any actual failed ConstraintResult.

Exact known catalog locality/region labels can produce PREFERRED_AREA or
OUTSIDE_PREFERRED_AREA. Unrecognized area text has no established canonical match,
is reported with a limitation and NOT_SPECIFIED comparison, and produces no nearby,
distance or driving-time claim. No general geography parser is introduced.

## Identity, reevaluation and tracing

Each assessment records its activity/window, actual accepted/conflicting/rejected
finding IDs, policy results, unresolved/disqualifying IDs, limitations, decisions
and proposed next actions. No schema field was added. Content-derived assessment
IDs/versions incorporate investigation/request revision, fixed evaluation clock,
policy, catalog and source payloads; identical evaluation is idempotent. Revision
changes cannot reuse prior assessment identities. State/trace correlations retain
the governing revision as required by the approved schema mapping.

A new authorized investigation cycle clears prior active assessments before
source work, with invalidated assessment IDs recorded in the request-validation
event. The trusted evaluator replaces the active assessment list only after all
policy/assessment events record successfully. Policy, assessment or trace failure
suppresses current assessments and closes execution. Earlier observations remain
in the trace; no stale ELIGIBLE assessment can silently survive as current output.

Actual POLICY_EVALUATED, CANDIDATE_ASSESSED, CANDIDATE_EXCLUDED and CANDIDATE_ELIGIBLE
events use existing TraceEvent types. They reference assessment identity/version,
candidate, policy outcomes and actual finding IDs. No result-validation event or
successful terminal investigation is fabricated. Remote LangSmith tracing remains
disabled, and memory recorders are component seams, not authoritative JSONL.

Only NEEDS_INVESTIGATION assessments request further bounded investigation;
EXCLUDED/UNSUPPORTED/ELIGIBLE states do not independently trigger more tool work.
Next actions are suggestions, not dispatch permissions. A trusted plan and budgets
still control execution. The five-cycle limit remains authoritative; its recursion
guard now accommodates the policy node. Evaluation consumes no model/tool calls.

The graph still ends operationally FAILED / ERROR at
RESULT_VALIDATION_NOT_IMPLEMENTED (or the applicable limit/trace-failure reason).
Candidate eligibility does not imply that a recommendation has been published.
Full scenario readiness remains BLOCKED.

## Verification and next work

```bash
uv sync --locked
uv run --locked pytest tests/test_safety_evaluation.py tests/test_safety_graph.py
uv run --locked pytest
uv run --locked hafi --version
```

**760 tests passed**, including 42 new safety/unit/graph checks. They cover supported
failures, mandatory unknowns, independent dimensions, authoritative advisory
contradictions, context/partial support, activity-specific wind, reviewed/unpermitted
MIXED, unknown constraints, soft preferences, revision identity, stale evidence,
terminal integrity, new-cycle invalidation, trace failures and five-cycle bounds.
The 13 existing upstream LangSmith warnings on Python 3.14 remain.

Authored component runs derive SC-004 Beach A as EXCLUDED / UNFAVORABLE / SUFFICIENT
and Beach B as ELIGIBLE / FAVORABLE / SUFFICIENT. SC-010's candidates remain
NEEDS_INVESTIGATION / UNDETERMINED / INSUFFICIENT after the eight planned calls.
The shared authored dispatch helper was extracted from the earlier evidence test
without changing its plan. These are component checks, not independent full
scenario acceptance reports.

No approved document was modified. Open constraint/preference normalization,
real-source thresholds and provider activation remain unresolved as designed.
Next proposed implementation work is M1.5-A — eligible candidate comparison and
Recommendation Result validation, including explained no-recommendation outcomes.
CLI interpretation/presentation, authoritative tracing and full acceptance execution
remain separately reviewable work.
