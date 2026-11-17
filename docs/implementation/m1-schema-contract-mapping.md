# Hawaii Activity Forecaster
# M1.1 Schema and Contract Implementation Mapping

**Version:** 0.1 — Approved Baseline  
**Status:** Approved — M1.1 Implementation Mapping  
**Project:** CMU Agentic AI Systems Capstone  
**Milestone:** M1.1 — Project Foundations  
**Document:** `docs/implementation/m1-schema-contract-mapping.md`  
**Implementation authorization:** Planning only; no application code authorized

## 1. Purpose

This document maps the approved logical data schemas and agent/tool contracts to the implementation responsibilities required for the Hawaii Activity Forecaster's M1 synthetic end-to-end workflow.

The mapping supports implementation using:

- Python 3.12+.
- LangGraph orchestration.
- Pydantic v2 validation.
- JSON Beach Catalog and synthetic fixtures.
- Deterministic safety-policy enforcement.
- Local JSONL Investigation Trace.
- Optional LangSmith development tracing.

The document does not redefine approved schemas, introduce new agent roles, or authorize application code.

## 2. Source of Authority

| Specification | Authority |
|---|---|
| `01-product-requirements.md` | Product scope and user behavior |
| `02-system-architecture.md` | Logical components and workflow |
| `03-data-schemas.md` | Data definitions, fields, enums, identifiers |
| `04-agent-tool-contracts.md` | Specialist and external-tool interfaces |
| `05-safety-policies.md` | Evidence sufficiency, hazard policy, eligibility |
| `06-test-acceptance.md` | Synthetic scenarios and acceptance assertions |
| `07-observability.md` | Trace semantics, storage, correlation |
| `m1-session-lifecycle.md` | CLI session and investigation lifecycle |
| `m1-technical-plan.md` | M1 technology and development sequence |
| `m1-configuration-baseline.md` | Approved budgets and operational safeguards |

The approved CONSISTENCY-001 corrections apply, including the authoritative TraceEvent enumeration and request-revision association rules.

This implementation mapping is subordinate to those specifications. Any discrepancy must be resolved rather than silently reinterpreted during development.

---

# 3. Mapping Principles

**MAP-001 — One Logical Contract**

Each approved logical schema shall have one authoritative implementation definition.

Equivalent framework representations may exist, but they must not introduce conflicting meanings.

**MAP-002 — Validate at Trust Boundaries**

Untrusted and LLM-produced information shall be validated before entering trusted application state or supporting policy decisions.

**MAP-003 — Preserve Provenance**

Findings shall preserve their source, geographic scope, time applicability, and measurement meaning.

**MAP-004 — Separate Retrieval and Validation**

Successful retrieval does not establish acceptable evidence or candidate eligibility.

**MAP-005 — Deterministic Safety**

Policy checks, eligibility constraints, and final result validation shall not depend exclusively on LLM judgment.

**MAP-006 — Coordinator-Owned State**

Specialists shall not directly modify authoritative Candidate Assessments, safety decisions, or investigation lifecycle status.

**MAP-007 — Explicit Correlation**

Session, investigation, request revision, specialist request, retry attempt, tool call, finding, assessment, and trace identities shall remain distinguishable.

**MAP-008 — Implementation Independence**

Pydantic and LangGraph are implementation mechanisms. Their internal constructs shall not replace the approved application-level schemas.

---

# 4. Primary Schema Implementation Inventory

| Logical schema | Primary implementation responsibility | M1 dependency |
|---|---|---|
| Beach Catalog | Validate persistent beach records and support candidate lookup | Required |
| Environmental Finding | Preserve structured environmental evidence and validation status | Required |
| Candidate Assessment | Represent independent evidence, suitability, and eligibility decisions | Required |
| Investigation State | Maintain Coordinator-owned investigation context and budgets | Required |
| Recommendation Result | Validate and present recommendations, abstentions, and failures | Required |
| Investigation Trace | Record authoritative execution events and decisions | Required |

All six schemas are required for the synthetic vertical slice.

The exact Python module and class names are implementation choices, not additional schema requirements.

---

# 5. Beach Catalog Mapping

## 5.1 Logical Responsibility

The Beach Catalog stores persistent, verified geographic and activity characteristics.

It does not store current environmental conditions or daily suitability scores.

Each named beach has one stable `beach_id`.

## 5.2 Required Field Groups

| Group | Fields |
|---|---|
| Identity | `beach_id`, `name`, `region`, `locality`, `latitude`, `longitude` |
| Activities and safety | `supported_activities`, `lifeguard_status` |
| Verification | `sources`, `last_verified`, `catalog_status` |

Optional fields include aliases, geographic characteristics, reef and entry notes, hazards, and activity notes.

Source references use the approved `SourceReference` contract, including source identity, publisher, URL, access date, and supported attributes.

## 5.3 Required Validation

- Valid unique beach IDs.
- Supported region values.
- Valid geographic coordinates.
- Approved activity enums.
- Required verification metadata.
- Valid catalog status.
- Only VERIFIED records entering recommendation eligibility evaluation.
- Traceable material safety and geographic attributes.

## 5.4 M1 Mapping

M1 uses versioned JSON fixtures containing fictional beach records.

Fixtures must satisfy the same logical schema and catalog validation requirements as future real-beach records.

Synthetic verification status does not establish that an actual Maui beach has been researched or verified.

## 5.5 Open Details

- Final real-beach list.
- Catalog activation requirements.
- Controlled shoreline exposure vocabulary.
- Real-world attribute re-verification rules.

These do not block fictional, schema-valid M1 fixtures.

---

# 6. Environmental Finding Mapping

## 6.1 Logical Responsibility

Environmental Findings represent evidence retrieved by authorized Weather and Ocean specialists.

A finding may be an OBSERVATION, FORECAST, ADVISORY, or REPORT.

## 6.2 Required Field Groups

| Group | Fields |
|---|---|
| Identity | `finding_id`, `investigation_id`, `agent_type`, `source_id`, `finding_type` |
| Geographic scope | `coverage_type`, `coverage_description` |
| Temporal scope | `retrieved_at` |
| Retrieval/validation | `retrieval_status`, `validation_status` |

Additional fields are conditionally required according to the approved finding type and source contract.

They include:

- `source_reference`
- `coverage_id`
- `beach_id`
- `issued_at`
- `valid_from`
- `valid_until`
- `observed_at`
- `measurements`
- `advisories`
- `descriptive_findings`
- `missing_fields`
- `limitations`
- `error_code`
- `error_message`

## 6.3 Measurement Mapping

Each Measurement preserves:

- `measurement_type`.
- `value`.
- Applicable `unit`.
- Applicable `measurement_time`.
- Optional measurement notes and convention.

Weather and ocean measurement categories must remain consistent with the logical schema and approved provider contracts.

Surf height and swell height shall not be treated as interchangeable.

Offshore wave heights shall not be silently converted into beach-breaking surf.

## 6.4 Advisory Mapping

An AdvisoryReference preserves:

- Advisory identifier.
- Issuer.
- Original advisory type.
- Geographic applicability.
- Original source reference.
- Conditional severity and effective periods.

A successful advisory retrieval does not independently establish that an activity is safe.

## 6.5 Retrieval and Validation States

Retrieval status:

- SUCCESS.
- PARTIAL.
- UNAVAILABLE.
- ERROR.

Evidence validation status:

- PENDING.
- ACCEPTED.
- LIMITED.
- REJECTED.

These are independent classifications.

A successfully retrieved finding may still be REJECTED for its intended assessment.

## 6.6 M1 Validation Boundaries

M1 shall test:

1. Source identity.
2. Field completeness.
3. Valid enum values.
4. Geographic integrity.
5. Temporal integrity.
6. Measurement integrity.
7. Missing information.
8. Material conflict preservation.
9. Validation outcome.
10. References to the originating investigation.

Synthetic freshness and geographic applicability rules must be explicit within the fixture or versioned test policy.

Undefined real-world freshness thresholds must not be invented.

---

# 7. Candidate Assessment Mapping

## 7.1 Logical Responsibility

Candidate Assessment evaluates one beach, activity, and requested time period.

It separates:

- Eligibility.
- Environmental suitability.
- Evidence quality.

These dimensions must remain independently represented.

## 7.2 Required Field Groups

| Group | Fields |
|---|---|
| Identity | `assessment_id`, `investigation_id`, `beach_id`, `activity`, `target_time_window`, `evaluated_at` |
| Assessment | `eligibility`, `environmental_suitability`, `evidence_quality` |
| Findings | `supporting_finding_ids`, `conflicting_finding_ids`, `rejected_finding_ids`, `evidence_limitations`, `assessment_basis` |
| Constraints/preferences | `hard_constraint_results`, `preference_results`, `geographic_preference_match` |
| Safety | `policy_results`, `disqualifying_policy_ids`, `unresolved_policy_ids`, `safety_limitations` |
| Decision | `decision_reasons`, `recommended_next_actions`, `remaining_questions`, `assessment_version` |

## 7.3 Approved Enumerations

**Eligibility:**

- ELIGIBLE.
- NEEDS_INVESTIGATION.
- EXCLUDED.
- UNSUPPORTED.

**Environmental suitability:**

- FAVORABLE.
- MIXED.
- UNFAVORABLE.
- UNDETERMINED.

**Evidence quality:**

- SUFFICIENT.
- LIMITED.
- INSUFFICIENT.

Constraint results, preference results, and policy results shall use their respective approved enumerations and field definitions.

## 7.4 Deterministic Validation

An ELIGIBLE assessment requires:

- Supported beach and activity.
- SUFFICIENT evidence.
- No disqualifying policy failure.
- Satisfied hard constraints.
- Resolved mandatory hazard questions.
- FAVORABLE or explicitly policy-permitted MIXED suitability.

Unknown mandatory checks must not be treated as passing.

Rejected findings cannot contribute positive supporting evidence.

## 7.5 Assessment Revision Mapping

The approved request-revision correction requires an unambiguous relationship between:

- Assessment identity and version.
- Governing request revision.
- Supporting findings.
- Investigation identity.

This relationship may be maintained through Investigation State and correlated trace references.

No new required Candidate Assessment field is authorized.

The implementation must prevent superseded assessments from supporting newer recommendations without appropriate reevaluation.

## 7.6 State Ownership

Candidate Assessments shall be created or updated by trusted assessment components under Coordinator supervision.

Weather and Ocean agents may provide evidence but may not directly authorize eligibility.

---

# 8. Investigation State Mapping

## 8.1 Logical Responsibility

Investigation State is the current mutable working state of an investigation.

It is distinct from the append-only Investigation Trace.

## 8.2 Identity and Lifecycle

Required identity fields:

- `investigation_id`
- `session_id`
- `schema_version`
- `created_at`
- `updated_at`
- `status`
- `request_revision`

Approved investigation statuses:

- INITIALIZING.
- INVESTIGATING.
- EVALUATING.
- AWAITING_CLARIFICATION.
- COMPLETED.
- ABSTAINED.
- FAILED.

COMPLETED, ABSTAINED, and FAILED are terminal.

## 8.3 Normalized Request

The normalized request contains:

- `original_request`.
- Conditional activity, date, and time window.
- Preferred area.
- Experience level.
- Hard constraints.
- Soft preferences.
- Clarification status and questions.

The original request shall remain distinguishable from normalized interpretations and assumptions.

## 8.4 Candidate and Evidence State

Investigation State maintains:

- Candidate beach identifiers.
- Candidate Assessments.
- Investigated and remaining candidate IDs.
- Weather findings.
- Ocean findings.
- Pending evidence requests.
- Unresolved evidence issues.

State updates must not silently overwrite independent findings.

## 8.5 Investigation Controls

Approved logical control fields include:

- `iteration_count`.
- `max_iterations`.
- `tool_call_count`.
- `max_tool_calls`.
- `retry_count`.
- `max_retries`.
- Conditional deadline.
- Remaining actions.

The existing schema remains authoritative.

Additional operational budgets such as LLM invocation limits and fallback-per-gap limits shall be enforced through trusted configuration and execution controls without redefining these existing fields.

## 8.6 M1 Approved Budgets

- 5 Coordinator investigation iterations.
- 12 external environmental tool invocations.
- 1 retry per failed original invocation.
- 1 fallback per required evidence gap.
- 2 concurrent specialists.
- 3 maximum recommendations.
- 12 LLM invocations per investigation.
- 30-second model request timeout.
- 10-second synthetic tool timeout.

Budget accounting must remain correct under concurrent execution.

## 8.7 LangGraph Mapping

LangGraph runtime state shall provide an execution-compatible representation of Investigation State.

Specialist branches shall return structured results.

Trusted orchestration shall validate and merge those results.

Parallel branches shall not directly overwrite Coordinator-owned Candidate Assessments, policy results, or lifecycle status.

Graph-internal execution identifiers must not replace application-level session, investigation, and request-revision identities.

---

# 9. Recommendation Result Mapping

## 9.1 Logical Responsibility

Recommendation Result represents the validated structured outcome presented by the CLI.

## 9.2 Required Top-Level Identity

- `result_id`.
- `investigation_id`.
- `request_revision`.
- `schema_version`.
- `generated_at`.
- `activity`.
- `target_time_window`.
- `outcome`.

Allowed outcomes:

- RECOMMENDATIONS.
- NO_RECOMMENDATION.
- ERROR.

## 9.3 Result Content

The result includes:

- `summary`.
- `recommendations`.
- `general_warnings`.
- `general_limitations`.
- Optional `next_step_suggestions`.

RECOMMENDATIONS must contain one to three eligible recommendations.

NO_RECOMMENDATION and ERROR must contain no recommendations.

## 9.4 Recommendation References

Each recommendation references:

- Recommendation ID.
- Beach ID.
- Candidate Assessment ID.
- Optional rank.
- Display name.
- Environmental suitability.
- Evidence quality.
- Recommended time window.
- Supporting finding IDs.
- Advisory references.
- Explanations and limitations.
- Source references.

## 9.5 Deterministic Validation

The Result Validator must verify:

1. Correct outcome structure.
2. No more than three recommendations.
3. Every recommendation references an ELIGIBLE assessment.
4. Every recommendation has SUFFICIENT evidence.
5. FAVORABLE or expressly permitted MIXED suitability.
6. Applicable hard constraints satisfied.
7. No disqualifying safety-policy failures.
8. Supporting findings exist and are acceptable.
9. Recommended time periods are evidence-supported.
10. Required material warnings and limitations are present.

The CLI may render only validated recommendations.

## 9.6 Terminal Mapping

| Investigation State | Result outcome |
|---|---|
| COMPLETED | RECOMMENDATIONS |
| ABSTAINED | NO_RECOMMENDATION |
| FAILED | ERROR |

These outcomes remain distinct.

---

# 10. Investigation Trace Mapping

## 10.1 Logical Responsibility

Investigation Trace records material operations and decisions.

Local JSONL is the authoritative M1 trace format.

LangSmith remains supplementary and optional.

## 10.2 Trace Metadata

The logical trace includes:

- `trace_id`.
- `investigation_id`.
- `schema_version`.
- `started_at`.
- Conditional completion metadata.
- Configuration and policy versions.
- Conditional model identifier.
- `events`.

## 10.3 TraceEvent Contract

Required fields:

- `event_id`.
- `trace_id`.
- `sequence_number`.
- `timestamp`.
- `event_type`.
- `actor`.
- `request_revision`.
- `details`.

Optional:

- `related_ids`.

The authoritative event enumeration is the approved, reconciled Section 7.4 of `03-data-schemas.md`.

No independent implementation event vocabulary is authorized.

## 10.4 Event Validation

The trace implementation shall verify:

- Approved event types.
- Approved actor values.
- Unique event IDs.
- Monotonically increasing sequence numbers.
- Valid correlation references.
- Correct investigation and request revision.
- Actual observable execution.
- No private chain-of-thought or secrets.
- Agreement between terminal state, result, and trace.

## 10.5 Trace Write-Failure Behavior

If mandatory local trace writing cannot be maintained:

- Further model and external-tool dispatch must stop.
- Recommendations must not be published.
- The failure must be reported as an operational error.
- Missing events must not be fabricated.

LangSmith availability does not override this requirement.

---

# 11. Specialist Contracts

The approved contracts in `04-agent-tool-contracts.md` define how the Coordinator delegates Weather and Ocean investigations.

## 11.1 SpecialistInvestigationRequest

Required fields:

- `request_id`.
- `investigation_id`.
- `request_revision`.
- `schema_version`.
- `agent_type`.
- `candidate_beach_ids`.
- `target_time_window`.
- `requested_evidence`.
- `known_evidence_gaps`.
- `issued_at`.
- `attempt_number`.

Conditional:

- `deadline_at`.

Nested contract types:

- EvidenceRequirement.
- EvidenceGap.

## 11.2 SpecialistInvestigationResponse

Required fields:

- `response_id`.
- `request_id`.
- `investigation_id`.
- `request_revision`.
- `schema_version`.
- `agent_type`.
- `attempt_number`.
- `status`.
- `findings`.
- `unresolved_gaps`.
- `errors`.
- `started_at`.
- `completed_at`.

Response statuses:

- SUCCESS.
- PARTIAL.
- UNAVAILABLE.
- ERROR.

Nested types:

- EnvironmentalFinding.
- EvidenceGap.
- SpecialistError.

## 11.3 Contract Validation Sequence

Before merging a specialist response:

1. Confirm the originating request exists.
2. Validate the investigation identifier.
3. Validate the active request revision.
4. Validate the specialist domain.
5. Validate the execution attempt.
6. Validate the response schema.
7. Validate authorized candidate scope.
8. Validate Environmental Finding structures.
9. Preserve error and gap details.
10. Reject duplicate or outdated response effects.

A structurally valid response is not necessarily sufficient environmental evidence.

## 11.4 Retry Identity

A retry maintains the same logical specialist request identifier where applicable.

The attempt number identifies the individual specialist execution.

External tool calls use separate unique tool-call IDs.

A retry cannot automatically create another retry allowance.

---

# 12. External Tool Contracts

## 12.1 EnvironmentalToolRequest

Required fields:

- `tool_call_id`.
- `investigation_id`.
- `source_id`.
- `agent_type`.
- `requested_evidence`.
- `target_time_window`.
- `geographic_scope`.
- `issued_at`.

## 12.2 EnvironmentalToolResponse

Required fields:

- `tool_call_id`.
- `source_id`.
- `retrieval_status`.
- `retrieved_at`.
- `findings`.
- `missing_evidence`.
- `errors`.
- `duration_ms`.

Conditional:

- `source_reference`.

## 12.3 Tool Trust Boundary

External tool execution must verify:

- Approved provider.
- Authorized specialist.
- Authorized evidence category.
- Valid geographic scope.
- Valid requested time window.
- Remaining execution budget.
- Configured timeout.

Returned tool data must pass contract validation and independent evidence validation.

## 12.4 M1 Synthetic Adapters

M1 uses synthetic tool adapters conforming to the same logical request and response structures.

These adapters may simulate:

- Success.
- Partial response.
- Missing evidence.
- Stale findings.
- Geographic mismatch.
- Source conflict.
- Timeout.
- Access denial.
- Malformed response.
- Retry.
- Fallback.

Simulation of an approved provider identifier does not establish that real provider access has been verified.

---

# 13. Identifier and Reference Mapping

| Identifier | Scope | Purpose |
|---|---|---|
| `session_id` | CLI session | Groups conversational requests |
| `investigation_id` | Investigation | Groups one bounded investigation |
| `request_revision` | Session request context | Tracks conversational refinements |
| `request_id` | Specialist delegation | Correlates specialist request and response |
| `attempt_number` | Specialist execution | Distinguishes execution attempts |
| `tool_call_id` | Tool invocation | Correlates each external call and outcome |
| `finding_id` | Environmental Finding | Identifies evidence |
| `assessment_id` | Candidate Assessment | Identifies candidate evaluation |
| `assessment_version` | Assessment | Distinguishes assessment versions |
| `result_id` | Recommendation Result | Identifies final structured result |
| `trace_id` | Investigation Trace | Identifies execution history |
| `event_id` | TraceEvent | Identifies individual observable event |
| `beach_id` | Beach Catalog | Stable supported beach identity |

Referenced identifiers must resolve under the relevant contract.

Cross-investigation evidence reuse must preserve the original finding's identity and investigation provenance.

The physical representation of cross-investigation references remains open.

---

# 14. LangGraph Execution and Merge Boundaries

## 14.1 Proposed Logical Flow

1. CLI accepts request.
2. Coordinator normalizes request.
3. Catalog selects supported candidates.
4. Coordinator identifies evidence requirements.
5. Weather and Ocean investigations execute when required.
6. Specialist response contracts are validated.
7. Findings are independently validated.
8. Trusted orchestration merges accepted and limited evidence.
9. Safety Policy Evaluator produces Candidate Assessments.
10. Coordinator decides whether to continue or conclude.
11. Eligible candidates enter qualitative comparison.
12. Recommendation Result is validated.
13. CLI presents the result.
14. Investigation Trace records material actions throughout.

## 14.2 Parallelism

Weather and Ocean branches may execute concurrently.

Shared budget counters and mutable assessment state must remain under trusted orchestration control.

The implementation must not rely on whichever parallel branch finishes last to determine authoritative evidence or safety state.

## 14.3 Graph State Versus Logical State

LangGraph may use framework-specific runtime structures.

However:

- Approved schema fields retain their defined meaning.
- Specialist outputs remain subject to contract validation.
- Authoritative state updates occur through trusted merge logic.
- Unrecognized framework metadata does not become application authority.
- Checkpoint/thread identifiers remain distinct from application identifiers.

## 14.4 Error Boundaries

Malformed specialist responses, stale request revisions, or invalid findings must not corrupt Investigation State.

A properly handled source outage may lead to explained abstention.

An unrecoverable application or orchestration failure must be represented as a technical failure.

---

# 15. M1 Validation Responsibility Matrix

| Validation responsibility | Trusted owner | Can involve LLM? |
|---|---|---|
| Request interpretation | Coordinator | Yes |
| Normalized request schema | Validator | No |
| Beach Catalog integrity | Catalog validator | No |
| Specialist request authorization | Contract validator | No |
| Specialist response structure | Contract validator | No |
| Source evidence extraction | Specialist/tool adapter | Yes, when appropriate |
| Finding schema integrity | Evidence validator | No |
| Geographic applicability | Approved evidence rules | Not authoritative |
| Freshness evaluation | Approved evidence rules | Not authoritative |
| Policy enforcement | Safety evaluator | No |
| Candidate eligibility | Safety evaluator | No |
| Qualitative comparison | Coordinator | Yes, after eligibility |
| Recommendation Result validation | Result validator | No |
| Trace-event validation | Trace validator | No |

LLM interpretation may contribute candidate explanations but cannot override trusted validation outcomes.

---

# 16. Implementation-Level Test Mapping

| Test area | Primary specification | M1 readiness |
|---|---|---|
| Beach Catalog schema | BC rules in `03` | READY for synthetic tests |
| Environmental Finding structure | EF rules in `03` | READY for structural tests |
| Candidate Assessment invariants | CA rules in `03` and Safety Policy | READY for defined synthetic outcomes |
| Investigation State identity/lifecycle | IS rules and approved session lifecycle | READY |
| Recommendation Result validity | RR rules in `03` | READY |
| Investigation Trace structure | IT rules and reconciled event enum | READY for synthetic validation |
| Specialist request contract | SRQ rules in `04` | READY |
| Specialist response contract | SRS rules in `04` | READY |
| External tool contract | ET rules in `04` | READY for synthetic adapters |
| M1 configuration limits | CFG-T01 through CFG-T16 | READY for provider-independent tests |
| Real provider access | Provider activation requirements | BLOCKED pending verification |
| Real hazard classification | `05-safety-policies.md` open criteria | BLOCKED |
| LLM-dependent end-to-end agent behavior | Approved M1 plan | BLOCKED pending provider selection |

READY means sufficiently specified for implementation planning, not that a test has been executed or passed.

---

# 17. Implementation Mapping Decisions Still Open

The following details require explicit selection or verification before their respective implementation tasks can be finalized.

| ID | Open detail | Priority |
|---|---|---|
| MAP-OD-001 | Concrete JSON representation for Time range, Number/Range/Category measurement values, and structured generic fields | High |
| MAP-OD-002 | Controlled vocabulary and serialization for evidence categories still described as String/Enum | High |
| MAP-OD-003 | Runtime representation of request-revision-to-assessment associations | High |
| MAP-OD-004 | Cross-investigation evidence reuse references | Medium |
| MAP-OD-005 | Atomic concurrent budget reservations and state-merging approach | High |
| MAP-OD-006 | Exact physical organization of Pydantic models and LangGraph state adapters | Medium |
| MAP-OD-007 | Schema and fixture versioning conventions | Medium |
| MAP-OD-008 | Synthetic tool failure and delay fixture representation | Medium |
| MAP-OD-009 | Initial LLM provider/model | Open by explicit decision |
| MAP-OD-010 | Provider-dependent structured-output implementation | Depends on provider |

These decisions shall not be silently resolved by choosing arbitrary framework defaults where doing so changes approved data or safety semantics.

---

# 18. M1.1 Mapping Acceptance Criteria

This mapping is acceptable when:

- [ ] All six logical schemas have implementation responsibilities.
- [ ] Specialist requests and responses map to the approved contract fields.
- [ ] External tool requests and responses map to approved interfaces.
- [ ] Schema validation and evidence validation remain separate.
- [ ] Safety eligibility remains deterministic.
- [ ] Agent state ownership is preserved under LangGraph.
- [ ] Parallel merge requirements are explicit.
- [ ] Approved operational limits remain unchanged.
- [ ] Session and investigation identifiers are not conflated.
- [ ] Request-revision and assessment validity are traceable.
- [ ] Trace events use the reconciled authoritative vocabulary.
- [ ] No additional autonomous agents are introduced.
- [ ] LLM provider selection remains open.
- [ ] Unresolved real-world environmental rules remain explicitly blocked.

## 19. Next Planning Deliverable

After approval of this mapping, prepare:

`docs/implementation/m1-synthetic-fixture-design.md`

The fixture design shall define the concrete JSON representation, versioning conventions, synthetic source responses, tool behaviors, and independent expected assertions required for the M1 acceptance scenarios.

The fixture design must preserve the approved schemas and must not introduce real-world environmental thresholds.

---

**End of M1.1 Schema and Contract Implementation Mapping v0.1**

**Status:** Approved — M1.1 Implementation Mapping.

**No application code is authorized by this document.**