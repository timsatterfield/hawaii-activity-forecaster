# Hawaii Activity Forecaster
# M1 LangGraph Execution Design

**Version:** 0.1 — Approved Baseline
**Status:** Approved — M1 LangGraph Execution Design
**Project:** CMU Agentic AI Systems Capstone  
**Milestone:** M1 — Synthetic End-to-End Forecaster  
**Document:** `docs/implementation/m1-langgraph-execution-design.md`  
**Implementation authorization:** Planning only; no application code authorized

## 1. Purpose

This document specifies how LangGraph shall orchestrate the M1 Hawaii Activity Forecaster workflow.

It defines:

- The logical graph and execution nodes.
- Coordinator and specialist responsibilities.
- Investigation State ownership and transitions.
- Parallel Weather and Ocean execution.
- Contract validation and evidence integration.
- Deterministic policy enforcement.
- Bounded ReAct investigation loops.
- Retry, fallback, and failure routing.
- Recommendation and abstention handling.
- Session follow-up behavior.
- Execution tracing and acceptance criteria.

M1 uses synthetic environmental fixtures rather than live providers.

This design does not modify the approved three-agent architecture or authorize application code.

## 2. Specification Authority

The following documents remain authoritative:

| Document | Governs |
|---|---|
| `02-system-architecture.md` | Logical architecture and responsibilities |
| `03-data-schemas.md` | Data contracts, states, identifiers, enums |
| `04-agent-tool-contracts.md` | Delegation and retrieval boundaries |
| `05-safety-policies.md` | Safety, exclusion, eligibility, abstention |
| `06-test-acceptance.md` | Acceptance scenarios and test requirements |
| `07-observability.md` | Audit events and trace behavior |
| `m1-session-lifecycle.md` | Post-terminal conversational follow-ups |
| `m1-technical-plan.md` | Technology and milestone architecture |
| `m1-configuration-baseline.md` | Runtime budgets and safeguards |
| `m1-schema-contract-mapping.md` | Schema-to-implementation mapping |
| `m1-synthetic-fixture-design.md` | Synthetic inputs, behavior, and assertions |

The reconciled Investigation Trace event enumeration in `03-data-schemas.md` takes precedence over earlier proposed event lists.

Where implementation details remain unspecified, this document identifies proposals rather than silently changing approved requirements.

---

# 3. Architectural Boundaries

## 3.1 Three Agent Roles

M1 shall contain exactly three logical agents:

**Coordinator**

Owns overall investigation progress, evidence planning, delegation decisions, candidate comparison, and final result generation.

**Weather Agent**

Investigates authorized weather forecasts, conditions, winds, and applicable weather alerts.

**Ocean Agent**

Investigates authorized surf, swell, marine conditions, relevant visibility reports, and water-quality advisories.

No additional autonomous Validation Agent, Safety Agent, Reviewer Agent, or Logging Agent shall be introduced.

## 3.2 Trusted Components

The architecture also contains deterministic execution components, including:

- Contract Validator.
- Evidence Validator.
- Safety Policy Evaluator.
- Result Validator.
- Budget Manager.
- Trusted State Merger.
- Investigation Trace Writer.
- CLI Session Manager.

These are application components, not additional autonomous agents.

## 3.3 LangGraph Responsibility

LangGraph shall coordinate execution nodes, state updates, conditional routing, and independent specialist branches.

LangGraph does not itself determine whether ocean conditions are safe.

Deterministic application rules remain authoritative for evidence sufficiency and candidate eligibility.

## 3.4 LLM Responsibility

LLM reasoning may assist with:

- Natural-language request interpretation.
- Evidence planning.
- Choosing authorized investigative actions.
- Qualitative comparison of eligible candidates.
- Generating grounded explanations.

LLM output must pass the applicable structured contract and cannot override trusted validation results.

---

# 4. Logical Execution Graph

## 4.1 Initial Execution

The proposed logical flow is:

1. Receive CLI request.
2. Initialize or resolve the session context.
3. Create a new Investigation State and Investigation Trace.
4. Normalize the user request.
5. Validate the normalized request.
6. Resolve required clarification, when necessary.
7. Select supported candidate beaches.
8. Establish initial evidence requirements.
9. Plan authorized specialist work.
10. Dispatch Weather and/or Ocean investigations.
11. Validate specialist responses.
12. Merge returned findings through trusted orchestration.
13. Validate environmental evidence.
14. Evaluate deterministic safety policies.
15. Produce Candidate Assessments.
16. Decide whether further investigation is justified.
17. Repeat an authorized investigation step or conclude.
18. Compare eligible candidates.
19. Construct and validate Recommendation Result.
20. Record the terminal outcome.
21. Present the validated outcome through the CLI.

The Investigation Trace records material execution events throughout this lifecycle.

## 4.2 Proposed Node Inventory

| Node | Responsibility | Control type |
|---|---|---|
| `initialize_investigation` | Establish state, identifiers, budgets, trace | Trusted |
| `normalize_request` | Interpret activity, time, constraints, preferences | LLM-assisted |
| `validate_request` | Enforce normalized request contract | Trusted |
| `select_candidates` | Resolve supported catalog candidates | Trusted |
| `plan_evidence` | Select required evidence and next actions | Coordinator |
| `authorize_dispatch` | Validate delegation, reserve budgets | Trusted |
| `weather_investigation` | Execute scoped Weather task | Specialist |
| `ocean_investigation` | Execute scoped Ocean task | Specialist |
| `validate_specialist_responses` | Verify contracts and correlations | Trusted |
| `merge_evidence` | Integrate valid responses without losing provenance | Trusted |
| `validate_evidence` | Assess temporal, geographic, source integrity | Trusted |
| `evaluate_safety` | Apply policy and hard-constraint rules | Trusted |
| `assess_candidates` | Produce validated Candidate Assessments | Trusted |
| `decide_next_action` | Continue, clarify, conclude, or abstain | Coordinator plus guards |
| `compare_candidates` | Compare eligible candidates qualitatively | Coordinator |
| `validate_result` | Enforce structured Recommendation Result | Trusted |
| `finalize_investigation` | Commit terminal state and trace outcome | Trusted |
| `present_result` | Render validated CLI output | Trusted |

Names are logical design labels. They do not mandate exact Python function names.

## 4.3 Specialist Branches

Weather and Ocean may run concurrently when both tasks are valid and independent.

A branch may be omitted when:

- Its required evidence is already acceptably available.
- No authorized evidence requirement exists for that specialist.
- A documented termination condition has been reached.
- Dispatch would exceed an execution limit.

The absence of a branch execution must not be interpreted as proof that its environmental category is favorable.

---

# 5. Investigation State Ownership

## 5.1 Authoritative State

The logical Investigation State defined in `03-data-schemas.md` remains authoritative.

LangGraph may maintain a compatible runtime representation.

State includes:

- Session and investigation identity.
- Request revision.
- Normalized request.
- Candidate IDs.
- Weather and Ocean findings.
- Evidence issues.
- Candidate Assessments.
- Investigation status.
- Execution counters and limits.
- Errors and recovery actions.
- Final outcome references.

## 5.2 Trusted State Writes

Only the Coordinator or trusted orchestration components may modify authoritative Investigation State.

Weather and Ocean specialists return contract-bound responses.

They must not directly alter:

- Candidate eligibility.
- Candidate safety-policy results.
- User hard constraints.
- User preferences.
- Overall investigation status.
- Final Recommendation Result.
- Shared budget counters.

## 5.3 Parallel Branch Output

Parallel branches shall produce isolated outputs that can be correlated to their authorized requests.

The trusted merge step validates those outputs before integrating them into authoritative state.

No concurrent branch may overwrite a complete shared assessment list merely because it completed last.

## 5.4 Evidence Accumulation

Accepted, limited, conflicting, and rejected findings shall remain identifiable.

An updated or conflicting source result must not silently erase a previous material finding.

The current assessment may change following reevaluation, but the historical decision must remain recoverable through the Investigation Trace.

---

# 6. State Transition Design

## 6.1 Approved Statuses

Investigation State uses:

- `INITIALIZING`
- `INVESTIGATING`
- `EVALUATING`
- `AWAITING_CLARIFICATION`
- `COMPLETED`
- `ABSTAINED`
- `FAILED`

The final three statuses are terminal.

## 6.2 Proposed State Transitions

| Current status | Next status | Condition |
|---|---|---|
| INITIALIZING | INVESTIGATING | Valid request established and investigation begins |
| INITIALIZING | AWAITING_CLARIFICATION | Essential request information is unresolved |
| INITIALIZING | FAILED | Unrecoverable initialization failure |
| INVESTIGATING | EVALUATING | Evidence is ready for evaluation |
| INVESTIGATING | AWAITING_CLARIFICATION | Material user ambiguity requires clarification |
| INVESTIGATING | FAILED | Unrecoverable execution failure |
| EVALUATING | INVESTIGATING | More authorized evidence is needed and budget remains |
| EVALUATING | AWAITING_CLARIFICATION | User input is required to proceed |
| EVALUATING | COMPLETED | Valid recommendations produced |
| EVALUATING | ABSTAINED | No defensible recommendation can be produced |
| EVALUATING | FAILED | Unrecoverable technical failure |

The application shall reject unauthorized status transitions.

## 6.3 Clarification Handling

`AWAITING_CLARIFICATION` is nonterminal in the approved logical schema.

However, the approved M1 session lifecycle only specifies post-terminal follow-ups, and active-investigation interruption or resumption is deferred.

**Proposed M1 treatment:**

When a request cannot be normalized sufficiently to investigate, the CLI may request clarification without dispatching environmental tools.

The durable resume behavior for the same active investigation remains deferred.

The implementation must not silently reinterpret `AWAITING_CLARIFICATION` as a terminal status or reopen an already terminal investigation.

A clarification-handling strategy must be finalized before testing multi-turn clarification during an active investigation.

## 6.4 Terminal Invariants

A terminal investigation shall not be reopened.

Proposed result mapping:

| Investigation status | Result outcome |
|---|---|
| COMPLETED | RECOMMENDATIONS |
| ABSTAINED | NO_RECOMMENDATION |
| FAILED | ERROR |

Final state, validated result, and trace status must agree.

---

# 7. Coordinator Investigation Loop

## 7.1 Bounded ReAct

The Coordinator follows the approved ReAct-style investigation approach:

1. Review available evidence and unresolved questions.
2. Select an authorized investigative action.
3. Delegate scoped work.
4. Observe validated responses.
5. Reassess candidates.
6. Continue or conclude.

The Coordinator shall not receive unrestricted permission to call arbitrary tools.

## 7.2 Iteration Definition

**Proposed interpretation:**

One Coordinator investigation iteration is one bounded decision cycle that may authorize and evaluate a set of specialist investigations.

Parallel Weather and Ocean delegation within that cycle counts as one Coordinator iteration, not two.

A subsequent decision to investigate additional evidence starts another iteration.

Initial request normalization, final result rendering, and deterministic validation steps do not independently consume Coordinator investigation iterations.

This interpretation must be enforced consistently and reflected in trace data.

## 7.3 Maximum Iterations

The approved maximum is five iterations per investigation.

The sixth investigation iteration shall not begin.

A framework-specific recursion limit may provide an additional safeguard but shall not replace this application-level limit.

## 7.4 Investigation Continuation

A further iteration may proceed only when:

- A documented evidence gap or unresolved question remains.
- A permitted action exists.
- Required dispatch budgets remain available.
- The action is within approved specialist and geographic scope.
- The investigation is not already terminal.
- Required local trace recording remains functional.

## 7.5 Termination

The Coordinator should stop investigating when:

- Enough eligible candidates are established.
- Remaining candidates are excluded or unsupported.
- Additional evidence cannot materially affect the decision.
- No authorized next action is available.
- Required execution limits are exhausted.
- The investigation must abstain or fail.

The Coordinator may terminate before exhausting available budgets.

---

# 8. Parallel Weather and Ocean Execution

## 8.1 Concurrency Limit

The approved maximum is two concurrent specialist executions.

The graph may execute one Weather and one Ocean specialist concurrently.

Neither specialist may independently start additional top-level agent roles.

## 8.2 Dispatch Validation

Before dispatch, the system shall verify:

- Active investigation identity.
- Current request revision.
- Valid specialist type.
- Authorized candidate IDs.
- Supported evidence requirements.
- Valid target time window.
- Remaining execution budget.
- Required trace availability.

Invalid requests shall not reach synthetic external tools.

## 8.3 Branch Isolation

Each specialist receives a scoped SpecialistInvestigationRequest.

Each branch returns a SpecialistInvestigationResponse.

Specialist responses are validated against the originating request before evidence integration.

## 8.4 Merge Behavior

**Proposed merge policy:**

1. Collect available specialist responses.
2. Match each response to an authorized request and attempt.
3. Reject invalid or outdated response effects.
4. Preserve valid findings and explicit unresolved gaps.
5. Deduplicate repeated deliveries by stable logical identifiers.
6. Preserve material conflicts.
7. Update authoritative Investigation State through trusted logic.
8. Schedule evidence and safety reevaluation.

Merge correctness shall not depend on branch completion order.

## 8.5 Failure Isolation

One specialist failure does not automatically invalidate valid evidence from the other specialist.

The Coordinator may continue with validated evidence, pursue an authorized recovery action, or abstain if mandatory evidence remains unresolved.

---

# 9. Shared Budget Management

## 9.1 Approved Limits

| Budget | Approved limit |
|---|---:|
| Coordinator investigation iterations | 5 |
| External environmental tool invocations | 12 |
| Retries per failed original invocation | 1 |
| Fallback attempts per evidence gap | 1 |
| Concurrent specialist executions | 2 |
| Final recommendations | 3 |
| LLM invocations | 12 |
| LLM request timeout | 30 seconds |
| Synthetic tool timeout | 10 seconds |

## 9.2 Trusted Budget Manager

The Budget Manager shall enforce the limits independently of model-generated instructions.

Limits apply per investigation, except explicitly scoped retry and fallback limits.

## 9.3 Atomic Reservation

**Proposed concurrency policy:**

Before an LLM invocation or external environmental tool dispatch, the trusted execution layer shall reserve one unit from the applicable shared budget.

The reservation must be atomic with respect to concurrent specialist execution.

A failed or timed-out dispatched request still consumes its reserved invocation.

The system shall not dispatch work when a required reservation cannot be obtained.

## 9.4 Retry Accounting

A permitted retry consumes an additional environmental tool invocation.

Each retry must use a new tool-call identifier.

The corresponding specialist attempt and logical delegation identity shall follow the approved contract correlation rules.

The retry allowance does not permit exceeding the investigation's shared tool budget.

## 9.5 Fallback Accounting

A fallback must be associated with one specific unresolved required evidence gap.

No more than one fallback attempt may be authorized per gap.

The fallback consumes the applicable tool-call and model budgets.

## 9.6 Timeout Enforcement

LLM requests are subject to the approved 30-second timeout.

Synthetic tool invocations are subject to the approved 10-second timeout.

A timeout produces a structured failure, not an assumed response.

Late results must not overwrite completed or superseded investigations.

## 9.7 Remaining Open Limits

The following remain open:

- Whole-investigation wall-clock deadline.
- Provider-specific automatic LLM retry policy.
- Token budgets.
- Monetary limits.

The design shall not silently adopt framework defaults that expand approved execution permissions.

---

# 10. Specialist Contract Validation

## 10.1 Required Validation

Before integrating a specialist response:

1. Confirm the originating request exists.
2. Match investigation ID.
3. Match request revision.
4. Match specialist domain.
5. Match attempt number.
6. Validate response schema.
7. Validate finding schemas.
8. Verify authorized evidence scope.
9. Preserve errors and unresolved gaps.
10. Detect duplicate delivery.

## 10.2 Outdated Responses

A response belonging to an outdated request or inactive investigation shall not update current assessments.

Its historical execution may remain represented in the original investigation trace.

## 10.3 Unauthorized Outputs

Specialist-provided eligibility decisions or final recommendations shall not become authoritative.

A specialist cannot expand the candidate set beyond the delegated scope.

## 10.4 Validation Failures

Malformed responses shall be rejected or quarantined according to the approved contracts.

A contract failure may produce a documented recovery action if permitted.

It shall not silently become successful evidence.

---

# 11. Environmental Evidence Validation

## 11.1 Validation Independence

Evidence validation is separate from successful retrieval and structural contract validation.

A successful source response may contain stale, geographically unsuitable, conflicting, or incomplete evidence.

## 11.2 Required Checks

The trusted Evidence Validator shall assess:

- Approved source identity.
- Finding structure.
- Geographic coverage.
- Temporal validity.
- Measurement consistency.
- Advisory applicability.
- Missing evidence.
- Material conflicts.
- Required evidence completeness.

## 11.3 Validation Outcomes

Environmental Findings use:

- PENDING.
- ACCEPTED.
- LIMITED.
- REJECTED.

LIMITED evidence may provide context but shall not independently satisfy mandatory requirements unless the approved policy explicitly permits it.

REJECTED evidence cannot provide positive support for suitability.

## 11.4 Geographic Integrity

Regional and offshore evidence must retain the original source coverage.

The system shall not convert offshore wave observations into direct beach surf measurements without a verified method.

## 11.5 Temporal Integrity

Retrieval time, issuance time, observation time, and forecast-validity periods shall remain distinct.

Fixture-specific temporal checks shall use the approved fixed reference time.

Real-world provider freshness thresholds remain outside M1.

---

# 12. Deterministic Safety Evaluation

## 12.1 Authority

The Safety Policy Evaluator determines policy outcomes using approved policies and validated evidence.

The Coordinator cannot override the evaluator.

## 12.2 Policy Outcomes

Individual policy results use:

- PASS.
- FAIL.
- UNKNOWN.
- NOT_APPLICABLE.

Policy handling actions include:

- EXCLUDE.
- INVESTIGATE.
- DISCLOSE.

## 12.3 Precedence

The trusted policy evaluator shall enforce:

1. A verified disqualifying FAIL requires exclusion.
2. An unresolved mandatory UNKNOWN prevents eligibility.
3. DISCLOSE does not independently establish suitability.
4. Soft preferences never override safety policy.
5. Missing evidence never becomes favorable by assumption.

## 12.4 Candidate Assessments

Each assessment independently represents:

- Eligibility.
- Environmental suitability.
- Evidence quality.

Only ELIGIBLE candidates with SUFFICIENT evidence and FAVORABLE or explicitly policy-permitted MIXED suitability may enter recommendation comparison.

## 12.5 Synthetic Policy Inputs

The synthetic fixture system may establish hypothetical policy facts where real-world numeric thresholds remain unresolved.

The evaluator must apply the documented policy logic rather than merely copy fixture expected outcomes.

## 12.6 Unresolved Evidence

A candidate with an unresolved mandatory safety issue remains non-recommendable.

The Coordinator may investigate further within limits.

If the issue remains unresolved at termination, the candidate shall not be recommended.

---

# 13. Coordinator Decision Routing

## 13.1 Proposed Decision Categories

The Coordinator may propose one of the following logical actions:

- INVESTIGATE_MORE.
- COMPARE_ELIGIBLE.
- REQUEST_CLARIFICATION.
- ABSTAIN.
- FAIL.

These are proposed graph-routing labels, not additions to the approved Investigation State or Candidate Assessment enums.

They must be mapped to approved state transitions and result outcomes.

## 13.2 Trusted Routing Guards

Before executing a proposed Coordinator action, the graph shall verify:

- The action is authorized.
- The active investigation permits the action.
- Required budgets remain available.
- Required contract data exists.
- The action does not override a safety policy.
- Required trace operations can be recorded.

An invalid model-proposed action shall not execute.

## 13.3 Compare Eligible

Only validated ELIGIBLE candidates may enter qualitative comparison.

Comparison may consider:

- Environmental suitability.
- Evidence quality and limitations.
- User preferences.
- Geographic preference.

The Coordinator shall not invent numerical suitability scores or driving-time estimates.

## 13.4 Abstention

ABSTAIN is appropriate when no defensible candidate can be recommended because of documented environmental limitations, exclusions, or unresolved mandatory evidence.

A handled provider outage may lead to abstention.

An unrecoverable application failure is not an environmental abstention.

---

# 14. Recommendation Result Construction

## 14.1 Successful Result

RECOMMENDATIONS contains between one and three eligible recommendations.

Every recommendation must reference:

- A supported beach.
- An ELIGIBLE Candidate Assessment.
- Sufficient accepted evidence.
- An evidence-supported time window.
- Material limitations and advisories.
- Appropriate source references.

## 14.2 No Recommendation

NO_RECOMMENDATION contains no recommendations.

It must explain the actual constraint, exclusion, evidence, or investigation limitation preventing a supported recommendation.

## 14.3 Technical Error

ERROR contains no recommendations.

It must distinguish a technical application failure from unfavorable environmental conditions.

## 14.4 Result Validation

The Result Validator shall verify structured completeness, valid references, grounding, eligibility, and outcome consistency.

Invalid results cannot be presented as valid recommendations.

---

# 15. Error and Recovery Routing

## 15.1 Error Classes

The execution design shall distinguish:

- Invalid request or contract.
- Source unavailable.
- Source timeout.
- Partial evidence.
- Stale or invalid evidence.
- Conflicting evidence.
- Exhausted investigation budget.
- Unrecoverable graph or application error.
- Mandatory trace write failure.

## 15.2 Recovery Options

Permitted actions include:

- Use already sufficient accepted evidence.
- Retry one failed original environmental tool invocation.
- Attempt one approved fallback for an evidence gap.
- Investigate another supported candidate.
- Request user clarification when supported.
- Produce explained abstention.
- Produce technical failure.

A retryable error flag is not sufficient authorization for a retry.

## 15.3 Recovery Decision

The Coordinator may select among permitted actions.

Trusted components enforce actual authorization, budget availability, and scope.

## 15.4 Source Outages

An external source failure does not independently establish unsafe conditions.

If a mandatory evidence requirement cannot be satisfied, the affected candidate remains non-recommendable.

## 15.5 Trace Failure

A failure to maintain mandatory local JSONL tracing shall:

1. Block further model and environmental tool dispatch.
2. Prevent publication of recommendations.
3. Preserve valid state where possible.
4. Report an operational failure.

The system must not fabricate missing trace events.

---

# 16. Session Follow-Up Execution

## 16.1 Approved Lifecycle

M1 supports post-terminal conversational follow-ups.

The CLI preserves the session ID across related requests.

A post-terminal follow-up shall:

- Increment the session request revision.
- Create a new investigation ID.
- Preserve unchanged applicable constraints.
- Reevaluate affected candidates.
- Receive fresh execution budgets.
- Preserve immutable previous terminal investigations.

## 16.2 Evidence Reuse

Previously collected findings may be considered for reuse when allowed.

The application must:

- Preserve original finding provenance.
- Verify temporal relevance.
- Verify geographic applicability.
- Recheck required evidence sufficiency.
- Avoid treating previous eligibility decisions as automatically valid.

## 16.3 Assessment Reuse

Candidate Assessments shall not be reused blindly across changed requests.

Material request changes require new or updated evaluations associated with the new investigation.

## 16.4 Deferred Behaviors

M1 does not require:

- Active-investigation cancellation.
- Resuming interrupted graph execution after process restart.
- Persistent LangGraph checkpoint recovery.
- Arbitrary active-investigation request replacement.

---

# 17. Investigation Trace and LangSmith

## 17.1 Authoritative Trace

Local JSONL is the authoritative Investigation Trace.

Each investigation shall have one logical trace.

Events shall use the approved, reconciled vocabulary in `03-data-schemas.md`.

## 17.2 Required Observability

The trace shall support reconstruction of:

- Request normalization.
- Specialist delegation.
- Tool dispatch and completion.
- Retries and fallbacks.
- Contract validation outcomes.
- Evidence validation outcomes.
- Policy evaluations.
- Candidate Assessments.
- Budget exhaustion.
- Terminal results.

## 17.3 Concurrent Event Ordering

Concurrent operations may complete in different orders.

Trace sequence numbers shall provide append order.

Correlation identifiers shall establish causality.

The evaluator must not assume that Weather always finishes before Ocean.

## 17.4 Privacy

Trace contents shall exclude secrets, unnecessary personal data, and private model chain-of-thought.

The trace shall record observable decisions and structured reasoning summaries only where authorized.

## 17.5 Optional LangSmith

LangSmith may supplement the local trace for:

- Graph visualization.
- Model-call inspection.
- Tool-call inspection.
- Latency analysis.
- Development evaluation.

LangSmith remains disabled by default.

A LangSmith outage shall not change deterministic safety decisions.

---

# 18. M1 Execution Acceptance Tests

The following tests are particularly relevant to this execution design.

| Test | Expected behavior |
|---|---|
| TW-001 | Correct scoped Weather and Ocean delegation |
| TW-002 | Parallel responses correctly correlated |
| TW-003 | PARTIAL findings preserved and gaps recorded |
| TW-004 | Approved fallback may proceed |
| TW-005 | Unauthorized retry rejected |
| TW-006 | Tool budget cannot be exceeded |
| TW-007 | Outdated response cannot overwrite state |
| TW-008 | Geographic follow-up triggers reevaluation |
| TW-009 | Specialist cannot introduce candidate beach |
| TW-010 | Prompt injection cannot override instructions |
| TW-011 | No eligible candidates produces abstention |
| TW-012 | Unrecoverable failure produces FAILED / ERROR |
| TW-013 | Handled provider outage with insufficient evidence produces ABSTAINED / NO_RECOMMENDATION |

The implementation shall also satisfy the approved configuration tests CFG-T01 through CFG-T16.

## 18.1 Priority End-to-End Scenarios

Initial M1 acceptance prioritizes:

- SC-001 — Multiple favorable recommendations.
- SC-003 — Only one eligible beach.
- SC-004 — Water-contact advisory exclusion.
- SC-006 — Permitted MIXED snorkeling.
- SC-010 — Provider outage and abstention.
- SC-011 — Prompt injection.
- SC-012 — Post-terminal follow-up.

## 18.2 Additional Execution Tests

Proposed additional checks:

**LG-T01:** Both specialists return in opposite completion orders; final safety outcomes remain invariant.

**LG-T02:** Parallel tool dispatch cannot oversubscribe the shared budget.

**LG-T03:** Parallel LLM calls cannot oversubscribe the shared model budget.

**LG-T04:** Invalid specialist response cannot mutate authoritative Candidate Assessments.

**LG-T05:** Coordinator attempts an unauthorized action; trusted dispatch rejects it.

**LG-T06:** Five investigation iterations completed; a sixth is blocked.

**LG-T07:** An expired or outdated response cannot modify terminal investigation state.

**LG-T08:** Required trace writing fails; no recommendation is published.

**LG-T09:** Coordinator attempts to recommend EXCLUDED candidate; Result Validator rejects the result.

**LG-T10:** A post-terminal follow-up creates a new investigation with fresh budgets and preserved constraints.

These tests are proposed additions to the execution-level test plan and require approval with this document.

---

# 19. Proposed Development Sequence

## M1.2 — Graph Skeleton

Define:

- LangGraph state representation.
- Logical graph nodes.
- Conditional transitions.
- Specialist branch entry and exit.
- Terminal routing.
- Basic budget enforcement.

**Exit criterion:** A synthetic investigation traverses the graph and terminates within approved limits.

## M1.3 — Specialist and Synthetic Tool Integration

Define:

- Validated specialist request and response handling.
- Synthetic Weather and Ocean adapters.
- Scoped dispatch.
- Retry and fallback logic.
- Parallel merge behavior.

**Exit criterion:** Specialist contracts and concurrent execution pass synthetic tests.

## M1.4 — Trusted Safety and Evidence Evaluation

Define:

- Evidence validation.
- Policy evaluation.
- Candidate Assessment creation.
- Eligibility enforcement.
- Abstention behavior.

**Exit criterion:** Mandatory synthetic safety assertions pass.

## M1.5 — Recommendation and CLI

Define:

- Eligible candidate comparison.
- Recommendation Result validation.
- CLI rendering.
- Post-terminal follow-up handling.

**Exit criterion:** Required synthetic CLI workflows produce validated outcomes.

## M1.6 — Observability and Acceptance

Define:

- JSONL trace validation.
- Required event coverage.
- Optional LangSmith instrumentation.
- Synthetic acceptance runs.
- Failure classification.

**Exit criterion:** M1 acceptance requirements are satisfied and auditable.

---

# 20. Open Execution-Design Decisions

| ID | Decision | Proposed disposition |
|---|---|---|
| LG-OD-001 | Node inventory and trusted/LLM division | Approve Section 4 |
| LG-OD-002 | State transition table | Approve Section 6, subject to clarification lifecycle restriction |
| LG-OD-003 | Coordinator iteration counting | One decision-and-investigation cycle; parallel specialist work counts as one iteration |
| LG-OD-004 | Parallel branch merging | Trusted validation and merge, completion-order independent |
| LG-OD-005 | Budget concurrency | Atomic reservations before dispatch |
| LG-OD-006 | Specialist response deduplication | Correlation and stable logical IDs |
| LG-OD-007 | Continuation routing | Coordinator proposal plus deterministic authorization |
| LG-OD-008 | Terminal outcome handling | Approved three terminal state/outcome pairs |
| LG-OD-009 | LangSmith dependency | Optional, disabled by default |
| LG-OD-010 | Additional execution acceptance tests | LG-T01 through LG-T10 |

The following remain unresolved or deferred:

- Active-investigation clarification resume behavior.
- Whole-investigation wall-clock deadline.
- Model-specific retry behavior.
- Token and monetary budgets.
- Exact LangGraph runtime types and reducer definitions.
- Detailed handling of cancellation in already-dispatched parallel operations.
- Persistent checkpointing and restart recovery.
- LLM provider and model selection.

None of these shall be silently treated as approved by framework defaults.

---

# 21. Design Acceptance Criteria

The LangGraph execution design is ready for implementation when:

- [ ] Exactly three agent roles are preserved.
- [ ] LangGraph is responsible for orchestration rather than safety judgment.
- [ ] All major workflow stages have logical nodes.
- [ ] Investigation State remains Coordinator-owned.
- [ ] Specialist responses pass contract validation before state integration.
- [ ] Concurrent Weather and Ocean findings are merged safely.
- [ ] Shared budgets are enforced atomically.
- [ ] The approved five-iteration Coordinator limit is preserved.
- [ ] Retry and fallback limits are preserved.
- [ ] Model and synthetic tool timeouts are enforced.
- [ ] Evidence validation remains separate from successful retrieval.
- [ ] Deterministic safety results cannot be overridden by the Coordinator.
- [ ] Only eligible candidates enter recommendation comparison.
- [ ] Terminal state, result, and trace status remain consistent.
- [ ] Post-terminal follow-ups follow the approved lifecycle.
- [ ] Trace-write failures suppress recommendations.
- [ ] LangSmith remains optional.
- [ ] No live-provider access or real-world hazard thresholds are introduced.
- [ ] Unresolved clarification and persistence behavior remains identified.
- [ ] Proposed LG-T01 through LG-T10 tests are accepted or explicitly deferred.

## 22. Approval and Implementation Boundary

Approval of this document establishes the LangGraph workflow design for M1.

It does not authorize implementation or select the initial LLM provider/model.

The approved requirements, session lifecycle, configuration baseline, schema mapping, and synthetic fixture conventions remain in force.

Implementation shall begin only when separately authorized.

---

**End of M1 LangGraph Execution Design v0.1**

**Status:** Approved — M1 LangGraph Execution Design.

**Approved design decisions:** LG-OD-001 through LG-OD-010.
**Approved additional tests:** LG-T01 through LG-T10.
**Remaining implementation decisions:** Open or deferred as documented in Section 20.
**No application code is authorized by this document.**