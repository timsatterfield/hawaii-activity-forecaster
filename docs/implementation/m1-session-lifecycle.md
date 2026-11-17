# Hawaii Activity Forecaster
# M1 Session Lifecycle Specification

**Version:** 0.1 — Approved Baseline
**Status:** Approved — M1 Session Lifecycle Specification
**Milestone:** M1 — Synthetic End-to-End Forecaster  
**Scope:** CLI session and investigation lifecycle  
**Application code:** Not authorized

## 1. Purpose

This document defines how the M1 CLI handles new requests, conversational follow-ups, investigation identifiers, request revisions, active state, completed investigations, and stale specialist responses.

It supplements the existing Investigation State, Recommendation Result, SpecialistInvestigationRequest, SpecialistInvestigationResponse, and Investigation Trace contracts.

It does not introduce a seventh logical data schema or additional autonomous agent.

## 2. Design Principles

**SL-001 — Session Continuity**

An active CLI session may contain multiple related user requests.

**SL-002 — Terminal Investigation Integrity**

An investigation that reaches COMPLETED, ABSTAINED, or FAILED remains terminal.

**SL-003 — Explicit Request Revisions**

Each new request interpretation within an active session has an identifiable revision.

**SL-004 — Constraint Preservation**

Conversational refinements preserve applicable unchanged constraints.

**SL-005 — Controlled Evidence Reuse**

Existing Environmental Findings may be reused only when their provenance, temporal validity, geographic coverage, and relevance remain acceptable.

**SL-006 — Stale Response Isolation**

Late or outdated specialist responses must not overwrite current assessments.

**SL-007 — Revision Traceability**

Material user changes and resulting reassessments must remain observable.

**SL-008 — No Unnecessary Persistence**

The MVP does not require persistent personal profiles or cross-session memory.

## 3. Session, Investigation, and Request Revision

Three identifiers serve distinct purposes.

| Identifier | Responsibility |
|---|---|
| `session_id` | Groups related CLI interactions |
| `investigation_id` | Identifies one bounded investigation |
| `request_revision` | Identifies the normalized request revision within the session |

### 3.1 New CLI Session

A new CLI session establishes a unique `session_id`.

The first investigation receives:

- A new `investigation_id`.
- `request_revision = 1`.
- An initial Investigation State status of INITIALIZING.

The session maintains the active normalized request context for subsequent conversational follow-ups.

### 3.2 New Investigation

Each independently executed investigation receives a unique `investigation_id`.

An investigation may proceed through the approved Investigation State statuses:

- INITIALIZING.
- INVESTIGATING.
- EVALUATING.
- AWAITING_CLARIFICATION.
- COMPLETED.
- ABSTAINED.
- FAILED.

COMPLETED, ABSTAINED, and FAILED are terminal.

### 3.3 Follow-up After Terminal Outcome

When the user submits a conversational follow-up after an investigation has terminated:

1. The active `session_id` remains unchanged.
2. The session increments `request_revision`.
3. The system creates a new `investigation_id`.
4. The new investigation receives the revised normalized request.
5. Unchanged constraints are preserved.
6. Reusable findings are evaluated for continued validity.
7. The new investigation receives fresh execution budgets.

The completed investigation is not reopened or modified.

### 3.4 Example

Initial request:

"Where should I snorkel tomorrow morning? I'm intermediate, prefer calm water, and near Kihei."

The first investigation has:

- Session: S1.
- Investigation: I1.
- Revision: 1.

After I1 completes, the user asks:

"Actually, let's look near Napili instead."

The follow-up has:

- Session: S1.
- Investigation: I2.
- Revision: 2.

The new request retains snorkeling, intermediate experience, the original requested time period, and the calm-water preference.

Its geographic preference changes to Napili.

The session and investigation identifiers above are illustrative, not required serialization formats.

## 4. Session Context

The active CLI session maintains:

- Current normalized user request.
- Current request revision.
- Most recent investigation identifier.
- Applicable user-provided constraints.
- Relevant reusable evidence references.
- Prior terminal results when retained locally for the active session.

The CLI session shall not treat prior recommendations as permanently valid environmental conclusions.

Persistent user accounts or profiles are not required.

## 5. Request Revision Rules

### 5.1 Modification

A conversational follow-up updates only the constraints explicitly changed by the user.

Examples:

- "Near Napili instead" changes geographic preference.
- "What about swimming?" changes requested activity.
- "Try tomorrow afternoon" changes the target time period.

Unchanged applicable constraints remain in force.

### 5.2 Explicit Versus Inferred Values

The system must distinguish user-provided constraints from assumptions or defaults.

A follow-up must not silently convert a preference into a hard constraint.

### 5.3 Material Ambiguity

If a follow-up creates a material ambiguity, the system may request clarification according to existing product requirements.

Clarification handling must preserve current session context.

No recommendation may be produced while material ambiguity remains unresolved.

## 6. Nonterminal Request Changes

If a user revises a request while an investigation remains active, the system must prevent obsolete work from corrupting the revised request.

For M1, the proposed rule is:

1. Treat the change as superseding the active request.
2. Stop dispatching further tool calls for the superseded investigation.
3. Mark pending requests for cancellation when the runtime supports it.
4. Create a new investigation under the same session.
5. Increment the session request revision.
6. Validate or re-retrieve necessary evidence.
7. Ignore late responses for state mutation of the new investigation.

The superseded investigation must reach an appropriate documented terminal state.

The exact cancellation and interruption representation remains open because the approved Investigation State schema does not define a CANCELLED terminal status.

Until that representation is resolved, M1 may restrict conversational follow-ups to after completed investigations.

## 7. Specialist Request Correlation

Specialist requests and responses already include:

- `investigation_id`
- `request_id`
- `request_revision`
- `agent_type`
- `attempt_number`

The trusted orchestration component shall validate all applicable identifiers before merging findings.

A mismatched investigation or revision cannot update the current Investigation State.

Retries retain the original logical `request_id` while incrementing the attempt number.

## 8. Candidate Assessment Validity

Candidate Assessments must be valid for the current investigation and normalized request.

A previous assessment must not automatically remain eligible after user constraints change.

### 8.1 Reassessment

Material changes may require reevaluation of:

- Candidate membership.
- Activity support.
- Hard constraints.
- Environmental evidence applicability.
- Safety policies.
- Environmental suitability.
- Evidence quality.
- Recommendation preference alignment.

### 8.2 Assessment Versioning

The existing `assessment_id` and `assessment_version` values remain authoritative.

The Coordinator shall retain a traceable relationship between the assessment evaluation, governing request revision, and supporting evidence.

No new required Candidate Assessment field is introduced.

### 8.3 Reusable Findings

An earlier Environmental Finding may be referenced by a later investigation when:

- The original evidence remains valid for the new time period.
- Its geographic coverage applies to the new candidate or requested area.
- Its measurement interpretation is unchanged.
- The source remains authorized.
- The finding satisfies current evidence-validation requirements.

Reuse of a finding does not imply reuse of its previous Candidate Assessment or eligibility decision.

Because Environmental Findings include a parent `investigation_id`, cross-investigation reuse must preserve their original parent identity and source metadata.

The new investigation shall record its references to reused findings without relabeling them as newly retrieved findings.

The exact storage mechanism for these cross-investigation references remains open.

## 9. Investigation Budgets

Each new investigation receives the approved M1 limits:

- Maximum five Coordinator iterations.
- Maximum twelve external tool calls.
- Maximum one retry per failed original invocation.
- Maximum one fallback attempt per required evidence gap.
- Maximum two concurrent specialists.
- Maximum three recommendations.

A follow-up that creates a new investigation receives a new budget.

Unused budget from an earlier investigation is not transferred.

Budget counters are associated with the `investigation_id`.

Retry and fallback limits remain scoped as defined in the M1 Implementation Readiness Baseline.

## 10. Terminal State Rules

An investigation ends with one of three terminal statuses:

| Investigation State | Recommendation Result outcome |
|---|---|
| COMPLETED | RECOMMENDATIONS |
| ABSTAINED | NO_RECOMMENDATION |
| FAILED | ERROR |

A valid abstention is not a technical application error.

An application failure must not be presented as a confirmed environmental hazard.

Terminal investigations shall not transition back into INITIALIZING, INVESTIGATING, or EVALUATING.

## 11. Investigation Trace

Each investigation has its own logical Investigation Trace.

Events shall use the authoritative event enumeration defined in `03-data-schemas.md`.

A follow-up creates a new trace associated with its new investigation ID and existing session ID.

Where relevant, the trace shall record:

- Original request and normalization.
- Request revision.
- Specialist requests.
- Tool operations.
- Evidence validation.
- Policy evaluations.
- Candidate assessments.
- Retry and fallback actions.
- Final result validation.
- Terminal outcome.

A relationship to a prior investigation may be recorded through existing structured correlation references.

No additional event type is required solely to link session investigations.

## 12. Session Termination

A CLI session may end when the user exits the application.

The session may also expire according to a future approved runtime policy.

M1 does not require:

- Reopening a session after application restart.
- Cross-device session synchronization.
- Persistent personal profiles.
- User registration.

A new process may establish a new session ID.

Exact session expiration and persistence behavior remains an open implementation decision.

## 13. M1 Acceptance Scenarios

### SL-T01 — Initial Request

Given a new CLI session and a supported request:

- A session ID exists.
- A new investigation ID exists.
- Request revision is 1.
- Investigation starts in INITIALIZING.

### SL-T02 — Follow-up After Recommendation

Given a completed snorkeling investigation followed by a geographic preference revision:

- The session ID remains unchanged.
- The request revision increments.
- A new investigation ID is created.
- Unchanged constraints are preserved.
- Affected assessments are reevaluated.

### SL-T03 — Follow-up After Abstention

Given an ABSTAINED investigation followed by a revised request:

- The earlier abstention remains terminal.
- The follow-up creates a new investigation.
- A new investigation budget is available.
- Prior evidence is reused only when valid.

### SL-T04 — Stale Specialist Response

Given a late response from a prior investigation:

- It cannot update the new investigation's Candidate Assessments.
- It cannot overwrite the active normalized request.
- Its correlation identifiers remain preserved in the appropriate trace.

### SL-T05 — Evidence Reuse

Given a finding from a prior investigation:

- The source and original investigation are preserved.
- Evidence applicability is reevaluated.
- Prior eligibility is not inherited automatically.
- Cross-investigation references remain traceable.

### SL-T06 — Terminal State Integrity

Given an investigation in COMPLETED, ABSTAINED, or FAILED:

- It cannot transition back into an active investigation state.
- New user work receives a new investigation ID.

### SL-T07 — Budget Reset

Given a valid follow-up that creates a new investigation:

- All investigation-scoped budget counters begin at zero.
- Configured M1 maxima remain unchanged.
- Prior budget usage remains associated with the previous investigation.

### SL-T08 — Material Ambiguity

Given a follow-up that creates unresolved material ambiguity:

- The system requests clarification.
- Unchanged session context remains available.
- No recommendation is issued until required clarification is resolved.

### SL-T09 — Active Investigation Revision

A request revision received while an investigation is still active must not permit stale state mutation.

This test remains BLOCKED until cancellation and interruption behavior is approved, or the M1 CLI explicitly restricts follow-ups to terminal investigations.

## 14. Open Decisions

| ID | Decision | Priority |
|---|---|---|
| SL-OD-001 | Whether M1 supports revisions during active investigations | Medium |
| SL-OD-002 | Cancellation and interruption terminal representation | Medium |
| SL-OD-003 | Cross-investigation evidence-reference storage | Medium |
| SL-OD-004 | Session expiration policy | Low |
| SL-OD-005 | Session persistence across process restarts | Low |
| SL-OD-006 | Clarification response handling within active investigations | Medium |
| SL-OD-007 | Exact identifier-generation and storage mechanism | Low |

For M1, the recommended conservative scope is:

- Support new requests.
- Support follow-ups after terminal outcomes.
- Preserve session context.
- Use a new investigation for each follow-up.
- Keep terminal investigations immutable.
- Defer interruption and cancellation of active investigations.

## 15. Approval Criteria

This specification may be approved when:

1. Session and investigation identifiers have distinct responsibilities.
2. Terminal investigations remain terminal.
3. Follow-ups preserve applicable unchanged constraints.
4. Request revisions remain traceable.
5. Specialist responses are correlated with the correct investigation.
6. Reused findings retain their original provenance.
7. Prior eligibility decisions are not blindly reused.
8. Each investigation receives its approved execution budget.
9. No new top-level logical schema or autonomous agent is introduced.
10. Unresolved cancellation and persistence behavior remains explicitly documented.

**Status:** Approved — M1 Session Lifecycle Specification.

**Approved M1 scope:** New requests and post-terminal follow-ups, with immutable terminal investigations and fresh execution budgets.

**Deferred:** Active-investigation interruption, cancellation, and resumption, as documented in Section 14.
**No application code is authorized by this document.**

---

**End of M1 Session Lifecycle Specification v0.1**