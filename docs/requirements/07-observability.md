# Hawaii Activity Forecaster
# Observability Specification

**Version:** 0.1 — Approved Logical Design  
**Status:** Approved — Logical Design; event vocabulary reconciliation specified
**Project:** CMU Agentic AI Systems Capstone  
**Document:** `docs/requirements/07-observability.md`

**Dependencies:**
- `01-product-requirements.md`
- `02-system-architecture.md`
- `03-data-schemas.md`
- `04-agent-tool-contracts.md`
- `05-safety-policies.md`
- `06-test-acceptance.md`

---

# 1. Purpose and Scope

This document defines the observability requirements for the Hawaii Activity Forecaster.

Observability enables developers and evaluators to inspect the Forecaster's execution, investigate failures, verify policy compliance, and evaluate agentic workflows.

The MVP requires lightweight, local observability appropriate for a command-line application and academic capstone.

The system shall expose sufficient structured information to determine:

1. What request was investigated.
2. Which beach candidates were considered.
3. Which specialist agents and tools were invoked.
4. What environmental evidence was returned.
5. Which findings were accepted, limited, or rejected.
6. Which safety policies were evaluated.
7. How candidate eligibility was determined.
8. Whether fallback, retry, or alternative investigation occurred.
9. Why the system recommended, abstained, or failed.
10. Whether execution remained within authorized limits.

Observability shall not require an additional autonomous agent.

# 2. Design Principles

**OBS-001 — Structured Events**

Material execution activity shall be recorded as structured events rather than relying exclusively on unstructured application logs.

**OBS-002 — Traceability**

Events must support correlation between user requests, specialist requests, tool calls, environmental findings, candidate assessments, and final results.

**OBS-003 — Append-Only Trace**

Investigation Trace entries shall be appended without modifying previously recorded events.

**OBS-004 — Source and Policy Attribution**

Material evidence-validation and safety decisions must retain source, validation-rule, and policy references.

**OBS-005 — Privacy and Sanitization**

Traces must exclude credentials, secrets, unnecessary personal information, and private model chain-of-thought.

**OBS-006 — Lightweight Implementation**

Local structured JSON logging is sufficient for MVP observability.

**OBS-007 — Failure Visibility**

Tool failures, contract violations, rejected findings, investigation exhaustion, and technical errors must be observable.

**OBS-008 — Execution Boundaries**

Relevant retry, iteration, tool-call, and execution-limit information must be recorded.

**OBS-009 — Evaluation Support**

Observability must support the synthetic scenarios and acceptance criteria established in `06-test-acceptance.md`.

**OBS-010 — No Fabricated Trace Events**

The system shall record actual observable execution behavior. It shall not generate a plausible but unsupported trace after an investigation.

**OBS-011 — Minimal Operational Overhead**

Logging shall avoid unnecessary duplication, excessive verbosity, and infrastructure unrelated to the MVP.

**OBS-012 — Distinguish Outcomes**

Successful recommendation, explained abstention, and technical failure must remain distinguishable.

---

# 3. Observability Architecture

The Coordinator owns the investigation lifecycle and the logical Investigation Trace.

Weather and Ocean specialists return structured responses and may provide operation metadata through their approved contracts.

A trusted execution or logging component records observable events.

The architecture consists of:

1. CLI request handling.
2. Coordinator orchestration.
3. Weather and Ocean specialist execution.
4. Approved external tool operations.
5. Contract and evidence validation.
6. Deterministic safety and eligibility evaluation.
7. Recommendation Result validation.
8. Append-only Investigation Trace.
9. Local JSON output and evaluation summaries.

No additional Logging Agent, Monitoring Agent, or Reviewer Agent is required.

## 3.1 Investigation State Versus Investigation Trace

The two structures serve different purposes.

### Investigation State

Represents the Coordinator's current working understanding of the investigation.

It may contain:

- Normalized user request.
- Active request revision.
- Candidate set.
- Accepted and unresolved evidence.
- Candidate Assessments.
- Remaining investigation budget.
- Current workflow status.

Investigation State may change as the investigation progresses.

### Investigation Trace

Represents observable execution history.

It records:

- Operations initiated and completed.
- Tool results and failures.
- Contract and evidence validation.
- Policy evaluations.
- Candidate status transitions.
- Retry and fallback decisions.
- Terminal outcomes.

The Investigation Trace is append-only.

## 3.2 Single Logical Trace

Each investigation shall have one logical trace.

Under the approved M1 session lifecycle, each post-terminal follow-up retains the session ID, increments the request revision, and creates a new investigation ID. Each investigation has its own logical trace. Terminal investigations and their historical trace events remain immutable.

Events must identify the revision to which they apply.

The exact relationship between investigation IDs, conversation session IDs, and request revision IDs shall follow `03-data-schemas.md`.

Observability shall not introduce conflicting identifier definitions.

---

# 4. Event Model

The implementation shall use the approved Investigation Trace schema.

This document defines required event semantics and a proposed event vocabulary.

Exact serialized field names and event enum values must remain consistent with `03-data-schemas.md`.

## 4.1 Required Event Information

Each event shall record sufficient metadata to identify:

| Information | Description |
|---|---|
| Event identifier | Unique event within the investigation |
| Investigation identifier | Correlates events to one investigation |
| Request revision | Associates an event with the applicable request state |
| Event type | Identifies the observable activity |
| Timestamp | Event occurrence time |
| Originating component | Coordinator, specialist, tool adapter, validator, or CLI |
| Correlation references | Relevant request, response, call, finding, candidate, policy, or result IDs |
| Outcome | Applicable success, failure, or other result |
| Structured details | Small, relevant, sanitized diagnostic information |

Fields not applicable to a particular event may be omitted or left unset according to the schema.

## 4.2 Time Representation

Events shall use an unambiguous timestamp format with timezone information.

UTC timestamps are recommended for trace storage.

User-facing time periods and forecast validity shall retain their relevant Hawaii local-time interpretation.

The system must distinguish event occurrence time from external observation, issuance, and forecast-validity timestamps.

## 4.3 Correlation Rules

**OBS-COR-001:** Specialist responses must correlate with the originating logical request.

**OBS-COR-002:** Retry attempts must be separately identifiable.

**OBS-COR-003:** Tool-call records must distinguish individual executions.

**OBS-COR-004:** Evidence validation events must reference the applicable finding.

**OBS-COR-005:** Policy-evaluation events must reference the applicable candidate and policy.

**OBS-COR-006:** Final result events must identify the validated Recommendation Result.

**OBS-COR-007:** Outdated responses must not silently affect newer request revisions.

**OBS-COR-008:** Concurrent events must preserve enough correlation metadata to reconstruct their relationships without assuming completion order.

---

# 5. Investigation Trace Event Vocabulary

The authoritative event enumeration is defined in Section 7.4 of `03-data-schemas.md`.

The observability implementation shall emit only approved `TraceEvent.event_type` values.

This document specifies how events are captured, correlated, stored, and evaluated. It does not maintain a separate event enumeration.

## 5.1 Required Event Categories

The approved enumeration covers:

1. Request and investigation lifecycle.
2. Specialist and external tool execution.
3. Contract and environmental evidence validation.
4. Candidate assessment and safety-policy evaluation.
5. Retry, fallback, and investigation limits.
6. Final result validation and terminal outcomes.

## 5.2 Validation Events

Contract, evidence, and result validation events shall preserve:

- Relevant operation or record identifiers.
- Applicable validation-rule identifiers.
- Validation outcome.
- Sanitized failure or limitation details.

A validation event shall not imply successful validation merely because the validation operation completed.

Rejected evidence must remain distinguishable from accepted or limited evidence.

## 5.3 Agent and Tool Events

Specialist and tool events shall preserve sufficient correlation information to identify:

- Originating logical request.
- Request revision.
- Execution attempt.
- Tool-call identifier.
- Responsible component.
- Operation outcome.

Concurrent completion order shall not be used as a substitute for explicit correlation.

## 5.4 Safety Events

Policy and candidate assessment events shall preserve:

- Candidate beach identifier.
- Applicable policy identifier.
- Relevant finding identifiers.
- Policy outcome.
- Candidate eligibility outcome.
- Material assessment changes.

Safety decisions must be verifiable without reconstructing private model reasoning.

## 5.5 Terminal Events

Every normally terminated investigation shall have an appropriate terminal event representing:

- Successful recommendation completion.
- Explained abstention.
- Unrecoverable technical failure.

The terminal event must agree with Investigation State and Recommendation Result.

Interrupted executions may have incomplete traces, which must not be repaired by fabricating events.

## 5.6 Event Vocabulary Changes

Any proposed new event type shall be reviewed against the existing enumeration before modifying the schema.

Changes shall be reflected consistently in:

- `03-data-schemas.md`
- `06-test-acceptance.md`
- `07-observability.md`

---

# 6. Request and Investigation Logging

The system shall record the beginning of each investigation.

## 6.1 Required Information

The initial trace should identify:

- Investigation ID.
- Request revision.
- Requested activity.
- Target date or time period.
- Relevant normalized constraints.
- Applicable geographic preference or limitation.
- Start timestamp.
- Active policy configuration version.

Raw user messages need not be duplicated in every event.

## 6.2 Follow-up Requests

When the user modifies an active request:

1. Record a request revision event.
2. Identify the changed constraints.
3. Preserve unchanged constraints according to the session contract.
4. Mark affected prior assessments as requiring reevaluation where applicable.
5. Associate subsequent activity with the new revision.

A response associated with an older revision must not silently overwrite current Investigation State.

## 6.3 Sensitive Information

The MVP does not require permanent user profiles.

Traces must not become a substitute for persistent user-profile storage.

The implementation should minimize the retention of raw user messages and other unnecessary personal information.

---

# 7. Specialist and Tool Observability

Specialist activity must remain visible without exposing internal private reasoning.

## 7.1 Specialist Requests

Each delegated request should be observable through:

- Specialist identity.
- Logical request ID.
- Request revision.
- Attempt number.
- Candidate or geographic scope.
- Requested evidence categories.
- Invocation timestamp.
- Completion status.

## 7.2 Tool Calls

Tool events shall identify:

- Approved provider or tool identifier.
- Tool-call identifier.
- Associated specialist request.
- Attempt number when relevant.
- Execution start and completion times.
- Outcome.
- Structured error category when applicable.

The system should record sufficient details to determine whether the operation was authorized.

## 7.3 Tool Errors

Failures shall preserve meaningful categories, such as:

- Timeout.
- Connection failure.
- Invalid response.
- Parsing failure.
- Unauthorized source.
- Rate limiting.
- Missing data.
- Other provider or adapter error.

Provider-specific error details must be sanitized.

## 7.4 Partial Responses

A partial specialist response shall not be treated as an entirely successful evidence collection.

The trace must preserve:

- Available findings.
- Missing evidence categories.
- Relevant tool failures.
- Contract-validation outcome.
- Whether further investigation was initiated.

## 7.5 Retries and Fallback

Retries and fallbacks must identify:

- Original failed operation.
- Reason for retry or fallback.
- Authorized alternative selected.
- Attempt number.
- Remaining execution budget, where relevant.

Repeated attempts must remain distinguishable without creating duplicate accepted findings.

---

# 8. Evidence Validation Observability

Environmental evidence validation is a primary observability requirement because retrieved information can be stale, irrelevant, incomplete, or misleading.

## 8.1 Validation Events

Each material validation outcome shall identify:

- Finding ID.
- Provider ID.
- Validation result.
- Applicable validation rule.
- Relevant limitation or rejection reason.

Validation results shall distinguish:

- ACCEPTED.
- LIMITED.
- REJECTED.

## 8.2 Source Provenance

The system shall preserve references to:

- Original provider.
- Known underlying source, when different.
- Publication or observation time.
- Forecast validity period.
- Original geographic coverage.
- Measurement definition and units.

These details primarily belong in Environmental Findings.

The Investigation Trace should reference the corresponding findings rather than unnecessarily duplicate their entire contents.

## 8.3 Geographic Validation

When geographic applicability affects a decision, the trace must make it possible to identify:

- Original reported geographic area.
- Candidate beach under assessment.
- Applicable mapping or rule.
- Validation outcome.

Regional and offshore findings must not silently become beach-specific observations.

## 8.4 Temporal Validation

The trace must support investigation of:

- Stale reports.
- Expired forecasts.
- Observation-versus-forecast mismatches.
- Missing timestamps.
- Source pages with independently differing update times.

Retrieval success must not be confused with evidence freshness.

## 8.5 Conflicting Evidence

Material conflicts shall be observable through:

- Relevant finding IDs.
- Conflict classification.
- Applicable validation or policy rule.
- Investigation action taken.
- Whether the conflict was resolved.

The trace must not silently erase conflicting findings when a preferred source is selected.

---

# 9. Safety-Policy Observability

Every material safety-policy decision must be explainable using structured records.

## 9.1 Policy Evaluation

A policy-evaluation event shall reference:

- Candidate beach ID.
- Requested activity.
- Policy identifier.
- Policy result: PASS, FAIL, UNKNOWN, or NOT_APPLICABLE.
- Supporting finding IDs.
- Required action when applicable: EXCLUDE, INVESTIGATE, or DISCLOSE.
- Concise decision explanation.

These fields shall reference the approved Candidate Assessment and PolicyResult representations.

## 9.2 Exclusions

When a candidate is excluded, the trace must identify the applicable verified disqualifying rule.

It must not attribute exclusion to a nonexistent or unverified hazard.

## 9.3 Unresolved Evidence

When a mandatory evidence requirement remains unresolved, the trace must preserve the reason.

Investigation exhaustion must not silently convert uncertainty into a verified exclusion.

## 9.4 MIXED Suitability

When a MIXED candidate is eligible, observability must establish that:

1. Evidence quality was SUFFICIENT.
2. No disqualifying safety policy failed.
3. All mandatory hazard checks were resolved.
4. Remaining limitations were non-disqualifying.
5. Required disclosures appeared in the final result.

## 9.5 Eligibility Transitions

Material changes to Candidate Assessment shall be observable.

Examples include:

- NEEDS_INVESTIGATION to ELIGIBLE.
- NEEDS_INVESTIGATION to EXCLUDED.
- ELIGIBLE to EXCLUDED after newly validated evidence.
- Changed assessment following a request revision.

The system must not overwrite earlier decisions without leaving an observable history of relevant changes.

---

# 10. Recommendation Result Observability

The Forecaster shall validate the structured Recommendation Result before displaying the CLI response.

## 10.1 Final Result Information

The terminal event must identify:

- Investigation ID.
- Active request revision.
- Final Recommendation Result ID when produced.
- Result outcome.
- Number of recommendations.
- Relevant candidate IDs.
- Completion timestamp.
- Material abstention or error reason when applicable.

## 10.2 Recommendation Outcome

A successful recommendation outcome must be distinguishable from an investigation that completed correctly but returned no recommendation.

A valid `NO_RECOMMENDATION` outcome is an expected form of abstention.

## 10.3 Abstention Outcome

For abstentions, the trace should identify the principal cause or causes:

- No eligible candidates.
- Verified disqualifying hazards.
- Insufficient mandatory evidence.
- Material unresolved conflicts.
- Unsatisfied hard constraints.
- Investigation budget exhaustion.

Multiple causes may apply.

## 10.4 Technical Failure

An unrecoverable application or orchestration failure must be distinguishable from a policy-based abstention.

The trace should include a sanitized error category and relevant operation references.

A source outage that is handled correctly through an explained abstention is not automatically a technical failure.

---

# 11. Execution Budget Observability

The MVP shall use bounded ReAct investigations.

Observability must verify compliance with configured execution limits.

## 11.1 Required Counters

The application shall make available the relevant counts for:

- Coordinator investigation iterations.
- Specialist requests.
- External tool calls.
- Retry attempts.
- Fallback attempts.
- Candidate assessments, when useful.

Counters shall correspond to the budget definitions approved in the architecture and agent-tool specifications.

## 11.2 Budget Exhaustion

When a limit is reached:

1. Record the applicable limit event.
2. Identify the exhausted budget category.
3. Stop unauthorized additional operations.
4. Preserve current accepted evidence and assessments.
5. Complete or abstain according to the applicable workflow rules.

## 11.3 Pending Limits

Exact numerical budgets remain unresolved.

Observability shall not invent limits independently.

The final configuration shall be versioned so acceptance tests can determine whether an execution exceeded the authorized budget.

---

# 12. Performance and Usage Metrics

The MVP requires lightweight performance and usage measurements.

## 12.1 Core Metrics

| Metric | Description |
|---|---|
| Investigation duration | Elapsed time from investigation start to terminal outcome |
| Specialist duration | Elapsed execution time per specialist attempt |
| Tool-call duration | Elapsed time per external operation |
| Total tool calls | Number of executed external tool operations |
| Retry count | Number of retry attempts |
| Fallback count | Number of alternative retrieval attempts |
| Evidence accepted | Number of accepted findings |
| Evidence limited | Number of limited findings |
| Evidence rejected | Number of rejected findings |
| Candidate count | Number of candidates investigated |
| Eligible count | Number of candidates qualifying for recommendation |
| Excluded count | Number of verified exclusions |
| Unresolved count | Number of candidates remaining non-recommendable due to uncertainty |
| Final outcome | Recommendations, abstention, or technical failure |

## 12.2 Optional Metrics

The implementation may capture:

- Model token usage, if available.
- Estimated model invocation cost, if available and reliable.
- Per-provider retrieval success and failure counts.
- Source-specific evidence rejection categories.

Optional usage information must not become a dependency for correct policy enforcement.

## 12.3 Performance Targets

Exact latency and usage thresholds remain pending.

Initial evaluation should establish baseline behavior before selecting quantitative targets.

Performance optimization must not bypass mandatory safety or evidence checks.

---

# 13. Local Logging and Storage

Local structured JSON logging is sufficient for the MVP.

## 13.1 Storage Format

A JSON Lines format is recommended for event storage.

Each line represents one structured Investigation Trace event.

This allows:

- Incremental append operations.
- Human-readable inspection.
- Programmatic filtering.
- Synthetic test verification.
- Simple local metrics aggregation.

The implementation may use a separate validated structured result file when needed.

## 13.2 Proposed File Organization

The following is illustrative rather than a mandated directory structure:

```text
logs/
  investigations/
    <investigation-id>.jsonl
```

Directory names and file-retention rules may be finalized during implementation planning.

## 13.3 Append-Only Semantics

New events are appended in occurrence order as observed by the logging component.

Existing events shall not be silently rewritten.

Concurrent operations may complete in a different order from their initiation.

Correlation identifiers must preserve correct causal relationships.

## 13.4 Storage Failures

The system should detect and report logging failures.

A failure to persist mandatory trace information must be visible to the application and test harness.

For acceptance testing, inability to capture required events is a trace-compliance failure.

The final fail-open versus fail-closed behavior for local logging failures remains an implementation decision.

Logging failures must not cause safety checks to be bypassed.

## 13.5 Retention

The MVP does not require indefinite trace retention.

Retention should support local development and capstone evaluation without unnecessary accumulation of user data.

Exact retention and cleanup rules remain open.

---

# 14. Privacy and Security

Observability shall support debugging without collecting unnecessary sensitive information.

## 14.1 Prohibited Trace Content

Traces shall not include:

- API keys.
- Authentication tokens.
- Passwords.
- Session secrets.
- Unnecessary personal identifiers.
- Full private model chain-of-thought.
- Unauthorized source content unrelated to the investigation.

## 14.2 Permitted Diagnostic Content

Traces may contain sanitized:

- Normalized request parameters.
- Approved source identifiers.
- Tool names and status.
- Environmental finding references.
- Validation outcomes.
- Policy evaluations.
- Candidate transitions.
- Concise operational explanations.
- Error classifications.

## 14.3 Raw Source Content

The Forecaster should avoid duplicating full raw provider responses in event logs.

Where debugging requires additional source detail, retention should be limited to relevant sanitized excerpts or references.

Raw content from external providers must be treated as untrusted data.

Instructions embedded in source content must never change logging, safety, or agent permissions.

## 14.4 Log Injection

Untrusted text must not be allowed to forge structured trace events or modify event metadata.

The logging component shall generate authoritative event identifiers, timestamps, and correlation references.

External content may appear only as appropriately sanitized data.

## 14.5 Local Data Access

Trace files should remain local to the user's development or evaluation environment unless explicitly exported.

No remote telemetry service is required.

---

# 15. Synthetic Evaluation Support

Observability must support the acceptance tests defined in `06-test-acceptance.md`.

## 15.1 Required Test Assertions

The evaluation harness shall be able to inspect:

- Specialist requests and outcomes.
- Tool calls and failures.
- Retry and fallback behavior.
- Finding validation results.
- Safety-policy evaluations.
- Candidate eligibility changes.
- Investigation-limit events.
- Final Recommendation Result.
- Terminal investigation outcome.

## 15.2 Trace Completeness

A synthetic test shall fail when a required event or correlation reference is missing.

The evaluator must not infer missing operations from natural-language explanations.

## 15.3 Evidence Grounding

Tests shall verify that material recommendation claims are backed by identifiable accepted findings.

Trace and result references must permit checking that:

- The finding exists.
- The source is approved.
- The finding is accepted for the relevant use.
- The geographic and temporal scope is appropriate.
- The cited evidence supports the claim.

## 15.4 Deterministic Replay

A test execution should be reproducible using:

- Fixed user request.
- Fixed reference time.
- Versioned synthetic Beach Catalog.
- Versioned environmental fixtures.
- Versioned policy configuration.
- Defined tool behavior and execution limits.

The evaluation system should preserve enough metadata to identify the fixture and configuration versions used.

Exact LLM wording need not be identical across executions.

Deterministic policy outcomes must remain consistent.

## 15.5 Evaluation Reports

A lightweight local evaluation report should summarize:

- Scenario identifier.
- PASS / FAIL / BLOCKED / NOT_RUN.
- Assertions evaluated.
- Failed assertion identifiers.
- Relevant trace and result references.
- Execution duration.
- Tool and retry counts.

No external dashboard is required.

---

# 16. Observability Acceptance Tests

## 16.1 Trace Lifecycle

| ID | Scenario | Expected result |
|---|---|---|
| OB-T01 | New investigation begins | Investigation ID and start event recorded |
| OB-T02 | Request normalized | Normalized request event recorded |
| OB-T03 | User modifies active request | Revision recorded and correlated |
| OB-T04 | Investigation completes | Terminal result recorded |
| OB-T05 | Investigation abstains | Abstention reason recorded |
| OB-T06 | Unrecoverable failure occurs | Technical failure distinctly recorded |

## 16.2 Agent and Tool Operations

| ID | Scenario | Expected result |
|---|---|---|
| OB-T07 | Specialist invoked | Scoped request recorded |
| OB-T08 | Specialist completes | Response correlated |
| OB-T09 | Tool invocation succeeds | Tool completion recorded |
| OB-T10 | Tool times out | Structured failure recorded |
| OB-T11 | Retry occurs | Attempt number and original operation identifiable |
| OB-T12 | Fallback occurs | Alternate source and reason recorded |
| OB-T13 | Concurrent results complete out of order | Correlation remains valid |
| OB-T14 | Duplicate response received | No duplicate accepted finding |

## 16.3 Evidence and Safety

| ID | Scenario | Expected result |
|---|---|---|
| OB-T15 | Stale evidence rejected | Validation reason and finding ID recorded |
| OB-T16 | Regional evidence evaluated | Geographic applicability visible |
| OB-T17 | Material conflict detected | Conflicting finding references retained |
| OB-T18 | Safety policy evaluated | Policy result and evidence references recorded |
| OB-T19 | Candidate excluded | Disqualifying reason identifiable |
| OB-T20 | Candidate transitions to eligible | Transition observable |
| OB-T21 | MIXED candidate recommended | Required policy checks and disclosures traceable |
| OB-T22 | Mandatory evidence remains unresolved | Uncertainty preserved |

## 16.4 Limits and Outcomes

| ID | Scenario | Expected result |
|---|---|---|
| OB-T23 | Tool-call budget exhausted | Limit event recorded |
| OB-T24 | Retry budget exhausted | No additional unauthorized attempts |
| OB-T25 | Source outage causes abstention | Not mislabeled as application failure |
| OB-T26 | Final result contains recommendation | Result ID and eligible candidate references preserved |
| OB-T27 | Result validation fails | Validation failure observable |

## 16.5 Privacy and Storage

| ID | Scenario | Expected result |
|---|---|---|
| OB-T28 | Source includes API credential | Credential absent from logs |
| OB-T29 | Source includes prompt injection | Source text cannot forge trace event |
| OB-T30 | Model emits private reasoning | Private chain-of-thought not stored |
| OB-T31 | Concurrent events written | Append-only integrity maintained |
| OB-T32 | Logging operation fails | Failure observable; safety not bypassed |
| OB-T33 | Synthetic evaluation completed | Structured summary available |

Acceptance tests shall use the approved Investigation Trace contract and must not require unapproved event types solely because they appear in this draft.

---

# 17. MVP Acceptance Criteria

Observability is acceptable for the MVP when:

1. Each investigation has a unique trace identifier.
2. Material agent and tool operations are recorded.
3. Specialist requests, responses, and attempts can be correlated.
4. Evidence validation outcomes are observable.
5. Material safety decisions reference policies and evidence.
6. Candidate eligibility changes are traceable.
7. Retry, fallback, and execution-limit behavior is visible.
8. Final recommendations, abstentions, and failures are distinguishable.
9. Required synthetic trace assertions pass.
10. Sensitive information and private model reasoning are not logged.
11. Local JSON traces can be inspected without external infrastructure.
12. Lightweight performance and usage summaries are available.

A trace need not reproduce the model's complete reasoning process.

It must provide sufficient observable facts to evaluate the system's documented decisions and actions.

---

# 18. Open Decisions

| ID | Decision | Priority |
|---|---|---|
| OBS-OD-001 | Final event vocabulary reconciliation with Investigation Trace schema | High |
| OBS-OD-002 | Exact trace field serialization | High |
| OBS-OD-003 | Final correlation ID relationships | High |
| OBS-OD-004 | Logging behavior when persistent writes fail | Medium |
| OBS-OD-005 | Trace file organization | Low |
| OBS-OD-006 | Local retention and cleanup period | Medium |
| OBS-OD-007 | Optional token-usage and cost tracking | Low |
| OBS-OD-008 | Final timing and performance targets | Medium |
| OBS-OD-009 | Evaluation summary output format | Medium |
| OBS-OD-010 | Sanitized raw-source diagnostic retention | Medium |
| OBS-OD-011 | Final execution-budget counters and limits | High |
| OBS-OD-012 | Exact trace-to-result validation rules | High |

These details must be reconciled with the existing schemas, contracts, and acceptance criteria.

They shall not be independently invented by an implementation agent.

---

# 19. MVP Constraints

The observability design shall not introduce:

- Additional autonomous monitoring agents.
- External telemetry services as mandatory dependencies.
- Distributed tracing infrastructure.
- Enterprise log aggregation.
- Persistent personal profiles.
- Full model chain-of-thought capture.
- Unbounded log retention.
- Continuous background monitoring.
- A separate observability database.
- Complex reporting dashboards.

The preferred implementation remains local structured logging with simple inspection and evaluation utilities.

---

# 20. Cross-Specification Dependencies

## Product Requirements

Defines supported activities, user interactions, geographic scope, and user-visible outcomes.

## System Architecture

Defines Coordinator and specialist responsibilities, workflow boundaries, and investigation limits.

## Data Schemas

Defines Investigation Trace, Investigation State, Environmental Finding, Candidate Assessment, and Recommendation Result structures.

## Agent and Tool Contracts

Defines specialist request correlation, attempt identifiers, approved providers, structured responses, and error handling.

## Safety Policies

Defines evidence validation, policy results, eligibility, MIXED suitability, and abstention.

## Test and Acceptance

Defines synthetic scenarios, required trace assertions, mandatory safety gates, and evaluation metrics.

Observability must support these specifications without introducing a separate competing source of truth.

---

# 21. Specification Status

## Proposed Logical Design

- Coordinator-owned logical Investigation Trace.
- Append-only structured event records.
- Local JSON logging.
- Event and response correlation.
- Evidence and policy traceability.
- Execution-budget observability.
- Separate recommendation, abstention, and failure outcomes.
- Privacy-preserving diagnostics.
- Synthetic test and evaluation support.
- Lightweight metrics and reporting.

## Pending Implementation Details

- Final serialized event vocabulary.
- Exact trace field structure.
- Storage and retention configuration.
- Error handling for failed log writes.
- Optional model usage metrics.
- Quantitative performance targets.
- Final execution-budget limits.

Approval establishes logical observability behavior, not a requirement for additional infrastructure.

No application code is authorized by this specification.

---

# 22. Next Phase

After approval, the project will have seven logical requirements specifications:

1. Product Requirements.
2. System Architecture.
3. Data Schemas.
4. Agent and Tool Contracts.
5. Safety Policies.
6. Test and Acceptance.
7. Observability.

The next phase should be a cross-document requirements consistency and implementation-readiness review.

That review shall identify:

- Conflicting definitions or duplicate requirements.
- Missing contract and schema details.
- Unresolved safety-critical dependencies.
- Provider integration assumptions.
- Requirements necessary for a first working CLI prototype.
- Requirements that may safely be deferred.
- Acceptance tests that can be executed before live integrations.

Implementation planning should begin only after these issues have been identified and prioritized.

---

**End of Observability Specification v0.1**

**Status:** Approved logical observability design. Trace-event vocabulary is governed by `03-data-schemas.md`; implementation-specific storage, retention, and operational settings remain open.

**No application code is authorized by this document.**