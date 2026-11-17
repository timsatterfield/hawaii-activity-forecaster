# Hawaii Activity Forecaster
# System Architecture Specification

**Version:** 0.1 — Draft  
**Status:** Approved — Logical Design; implementation decisions pending
**Project:** CMU Agentic AI Systems Capstone  
**Document:** `docs/requirements/02-system-architecture.md`  
**Implementation Phase:** Requirements Definition

**Related specifications:**
- `01-product-requirements.md`
- `03-data-schemas.md`
- `04-agent-tool-contracts.md`
- `05-safety-policies.md`
- `06-test-acceptance.md`
- `07-observability.md`

---

# 1. Purpose and Scope

This document defines the logical system architecture of the Hawaii Activity Forecaster.

The Forecaster is an agentic AI application that helps recreational users identify suitable Maui beaches for:

- Swimming.
- Snorkeling.
- Stand-up paddleboarding (SUP).

The MVP supports approximately 10–15 verified named beaches in South and West Maui.

The system interprets natural-language requests, selects supported beach candidates, retrieves environmental evidence, evaluates suitability and safety, and returns up to three evidence-supported recommendations.

When a defensible recommendation cannot be established, the system explains the limitations and abstains.

The architecture is designed for a command-line MVP and an academic capstone.

It is not intended to provide guaranteed ocean safety, replace authoritative warnings or lifeguard guidance, or autonomously undertake external actions.

## 1.1 Architectural Objectives

The architecture shall:

1. Support natural-language activity requests and in-session follow-ups.
2. Separate investigation coordination from specialist environmental retrieval.
3. Preserve structured evidence with identifiable provenance.
4. Maintain geographic and temporal integrity.
5. Enforce critical safety requirements through trusted deterministic components.
6. Support bounded, adaptive ReAct investigations.
7. Distinguish successful retrieval from evidence sufficiency.
8. Handle partial results, failures, and uncertainty without fabricating recommendations.
9. Provide traceable recommendations and abstentions.
10. Remain small enough for a practical capstone implementation.

## 1.2 Core Architectural Principles

**ARCH-001 — Centralized Coordination**

One Coordinator Agent owns the investigation lifecycle and final recommendation process.

**ARCH-002 — Specialized Evidence Gathering**

Weather and Ocean specialists retrieve and report evidence within their authorized domains.

**ARCH-003 — Structured Communication**

Agent interactions use validated request and response contracts.

**ARCH-004 — Trusted Safety Enforcement**

Safety-critical eligibility checks shall be enforced through deterministic policy components, not unrestricted LLM judgment.

**ARCH-005 — Evidence Integrity**

Source provenance, original geographic coverage, time applicability, and measurement definitions must be preserved.

**ARCH-006 — Bounded Autonomy**

Agent investigation, retries, fallback operations, and external tool calls must respect enforced limits.

**ARCH-007 — Explainable Outcomes**

Material recommendation and abstention decisions must be traceable to evidence and documented requirements.

**ARCH-008 — Minimal MVP Complexity**

The architecture shall not introduce components or infrastructure without a demonstrated MVP requirement.

**ARCH-009 — Read-Only Operation**

The Forecaster retrieves information and produces recommendations. It does not perform bookings, purchases, scheduling changes, or other external actions.

**ARCH-010 — Appropriate Abstention**

The system must withhold recommendations that cannot satisfy mandatory evidence and safety requirements.

---

# 2. System Context

## 2.1 Primary User Interaction

The user submits a natural-language request through the CLI.

Example:

"Where should I snorkel tomorrow morning? I'm intermediate, prefer calm water, and near Kihei."

The Forecaster shall interpret:

- Requested activity.
- Target date and time window.
- Experience level, when supplied.
- Environmental preferences.
- Geographic preferences.
- Explicit hard constraints.

The Coordinator determines which supported beaches warrant investigation.

Weather and Ocean specialists retrieve relevant evidence.

Trusted validation components evaluate that evidence and enforce documented safety policies.

The Coordinator then returns eligible recommendations or an explained abstention.

## 2.2 External Dependencies

The system relies on:

- A curated Beach Catalog.
- Approved weather providers.
- Approved ocean and marine providers.
- Authoritative advisory sources.
- An LLM used for supported agentic reasoning and language tasks.
- Local execution and trace storage.

External environmental providers are not trusted to issue instructions to the application.

Their content is evidence to evaluate, not authority to modify system behavior.

## 2.3 System Boundary

The MVP operates as a local command-line application.

The system does not require:

- User registration.
- Persistent personal profiles.
- A graphical interface.
- A remotely hosted application backend.
- External bookings or transactions.
- A distributed agent platform.
- Continuous background monitoring.

---

# 3. Logical Component Architecture

The Forecaster consists of the following logical components.

| Component | Primary responsibility |
|---|---|
| CLI | User requests, follow-ups, and presentation |
| Coordinator Agent | Investigation planning, delegation, comparison, final response |
| Weather Agent | Weather forecasts, wind, and weather advisories |
| Ocean Agent | Marine conditions, surf, swell, snorkeling reports, and relevant advisories |
| Beach Catalog | Verified persistent geographic and activity information |
| Tool Adapters | Controlled retrieval from approved environmental sources |
| Contract Validator | Validates agent and tool interfaces |
| Evidence Validator | Validates provenance, freshness, scope, and measurements |
| Safety Policy Evaluator | Enforces documented hazard and eligibility rules |
| Investigation State | Current Coordinator-owned working information |
| Investigation Trace | Append-only observable execution history |
| Recommendation Result Validator | Validates structured outcomes before CLI presentation |

These are logical responsibilities.

They do not necessarily require separate processes, services, classes, or autonomous agents.

## 3.1 Agent Architecture

The system contains exactly three agent roles:

1. Coordinator Agent.
2. Weather Agent.
3. Ocean Agent.

Contract validation, evidence validation, safety evaluation, and logging are trusted application functions or workflow components rather than additional agents.

No separate Writer, Safety, Reviewer, or Monitoring Agent is required.

---

# 4. Coordinator Agent

The Coordinator is the central supervisor.

It owns the overall investigation and determines which actions are necessary to fulfill a user request.

## 4.1 Responsibilities

The Coordinator shall:

- Interpret and normalize natural-language requests.
- Distinguish hard constraints from soft preferences.
- Retrieve supported candidate beaches.
- Determine required evidence categories.
- Delegate scoped tasks to the specialists.
- Track responses, outstanding evidence gaps, and execution budgets.
- Request authorized additional investigations when needed.
- Combine validated evidence into Candidate Assessments.
- Apply trusted safety-policy results.
- Compare eligible candidates qualitatively.
- Produce a structured Recommendation Result.
- Handle clarification, abstention, and technical failure.
- Preserve material investigation history.

## 4.2 Decision Authority

The Coordinator may decide:

- Which supported beaches to investigate.
- Which authorized specialist to invoke.
- Whether additional evidence is needed.
- Whether approved fallback operations should be attempted.
- Which eligible candidates best satisfy user preferences.
- How to explain evidence-supported recommendations.

The Coordinator shall not:

- Override deterministic exclusion rules.
- Treat missing evidence as favorable.
- Invent environmental measurements.
- Reclassify unsupported beaches as verified.
- Expand specialist tool permissions.
- Bypass execution budgets.
- Promote untrusted external instructions into system authority.

## 4.3 Candidate Selection

Candidates shall originate from the verified Beach Catalog.

Candidate selection considers:

- Supported activities.
- Supported geographic regions.
- Hard geographic constraints.
- Soft geographic preferences.
- Verified persistent beach characteristics.

Initial candidate selection does not establish environmental suitability.

Only verified catalog records may enter recommendation eligibility evaluation.

---

# 5. Weather Agent

The Weather Agent retrieves weather-domain information requested by the Coordinator.

## 5.1 Responsibilities

The Weather Agent may investigate:

- General weather forecasts.
- Wind speed and direction.
- Precipitation and relevant forecast conditions.
- Applicable weather warnings and alerts.
- Weather-related environmental limitations.

It shall preserve the source's actual geographic and temporal coverage.

## 5.2 Output

The Weather Agent returns structured Environmental Findings through the approved specialist response contract.

It also reports:

- Missing information.
- Partial results.
- Retrieval failures.
- Source limitations.
- Relevant evidence gaps.

The Weather Agent shall not independently determine final beach eligibility or prepare final recommendations.

## 5.3 Tool Permissions

Only approved Weather-domain sources and authorized evidence categories may be accessed.

The provider registry and tool contracts are defined in `04-agent-tool-contracts.md`.

---

# 6. Ocean Agent

The Ocean Agent retrieves ocean and marine information requested by the Coordinator.

## 6.1 Responsibilities

The Ocean Agent may investigate:

- Marine forecasts.
- Swell height, direction, and period.
- Surf and wave conditions.
- Relevant offshore observations.
- Available nearshore and snorkeling reports.
- Underwater visibility reports.
- Marine warnings and advisories.
- Relevant official water-quality advisories.

## 6.2 Output

The Ocean Agent returns structured Environmental Findings through the approved specialist response contract.

It shall preserve:

- Original geographic coverage.
- Source attribution.
- Observation and forecast periods.
- Measurement units and conventions.
- Known limitations and evidence gaps.

## 6.3 Domain Boundaries

The Ocean Agent shall not:

- Independently expand the authorized candidate set.
- Determine final eligibility.
- Override safety policies.
- Generate final user recommendations.
- Modify Coordinator-owned Investigation State directly.

---

# 7. Agent Communication

The Coordinator communicates with specialists through validated structured contracts.

## 7.1 Specialist Requests

The common `SpecialistInvestigationRequest` identifies:

- Logical request ID.
- Parent investigation ID.
- Request revision.
- Contract version.
- Specialist type.
- Authorized beach IDs.
- Target time window.
- Requested evidence categories.
- Known evidence gaps.
- Attempt number.
- Conditional deadline.

Requests must remain within the active investigation and specialist's authorized domain.

## 7.2 Specialist Responses

The common `SpecialistInvestigationResponse` identifies:

- Response ID.
- Originating request ID.
- Parent investigation.
- Request revision.
- Contract version.
- Specialist type.
- Attempt number.
- Execution status.
- Environmental Findings.
- Unresolved evidence gaps.
- Structured errors.
- Execution timestamps.

Response status uses the contract-defined values:

- `SUCCESS`
- `PARTIAL`
- `UNAVAILABLE`
- `ERROR`

A successful response does not automatically establish sufficient or valid environmental evidence.

## 7.3 Correlation and Retry

A logical specialist request retains the same `request_id` across retry attempts.

Each attempt uses its own attempt number.

Individual external tool invocations use distinct tool-call identifiers.

Responses must match their originating request, revision, specialist, and attempt.

Duplicate or outdated responses must not corrupt the active investigation.

## 7.4 Validation Boundary

Specialist responses must pass contract validation before their findings can enter trusted evidence assessment.

Malformed, unauthorized, mismatched, or out-of-scope responses must be rejected or handled according to the approved contract rules.

---

# 8. External Tool Architecture

Specialists access environmental providers through controlled tool adapters.

The tool adapters implement the external retrieval contracts in `04-agent-tool-contracts.md`.

## 8.1 Tool Adapter Responsibilities

A tool adapter shall:

1. Validate the approved provider and access method.
2. Validate authorized geographic and temporal parameters.
3. Execute the retrieval.
4. Capture retrieval status and timing.
5. Normalize source information into structured results.
6. Preserve original measurement and source metadata.
7. Report missing fields and structured errors.
8. Return data without independently establishing recommendation eligibility.

## 8.2 Provider Registry

The proposed provider registry includes:

| Provider | Primary purpose | Priority |
|---|---|---|
| NWS Weather | Weather forecasts | P0 |
| NWS Alerts | Applicable weather alerts | P0 |
| NWS Marine and Surf | Marine forecasts and surf advisories | P0 |
| Hawaii DOH Clean Water Branch | Official water-quality advisories | P0 |
| NOAA NDBC | Offshore wave observations | P1 |
| The Snorkel Store | Local qualitative snorkeling reports | P1 |
| HawaiiWeatherToday | Regional visibility, surf, wind, and narrative information | P1 |

P0 and P1 express planned integration priority, not guaranteed availability.

Provider identifiers and individual retrieval contracts are authoritative in `04-agent-tool-contracts.md`.

PacIOOS Maui SWAN is outside the MVP and shall not be included in the initial integration inventory.

## 8.3 Provider Activation

Before a provider is enabled for live investigations, the application must verify:

- Authorized retrieval endpoint or access method.
- Applicable automated-access and reuse permissions.
- Required request parameters.
- Geographic coverage.
- Available publication and observation timestamps.
- Supported evidence categories.
- Freshness and validation behavior.
- Structured error handling.

A documented provider is not automatically an activated provider.

## 8.4 Geographic Mapping

A catalog beach ID does not automatically correspond to an NWS forecast grid, marine zone, reporting region, or buoy station.

Mapping between beach locations and external provider coverage must be verified.

Offshore observations may provide regional context but do not independently establish beach-specific surf, currents, entry conditions, or underwater visibility.

## 8.5 Source Integrity

Each retrieved finding must retain its original source and scope.

The application shall distinguish:

- Forecasts.
- Observations.
- Advisories.
- Qualitative reports.

Derived or republished forecasts must not automatically count as independent corroboration.

---

# 9. Logical Data Architecture

The Forecaster uses the six primary logical schemas defined in `03-data-schemas.md`.

## 9.1 Beach Catalog

Stores persistent, verified beach information, including:

- Beach identity and location.
- Supported activities.
- Shoreline orientation and exposure.
- Persistent hazards and access characteristics.
- Source references and verification dates.

The catalog does not store changing environmental conditions or daily suitability scores.

The MVP uses one stable beach ID per named beach.

Individual beach entry points are not modeled as separate records.

## 9.2 Environmental Finding

Represents weather and ocean information retrieved during an investigation.

Findings retain:

- Source identity.
- Finding type.
- Geographic coverage.
- Relevant timestamps.
- Measurements and their conventions.
- Validation status and limitations.

A finding does not independently establish eligibility.

## 9.3 Candidate Assessment

Represents evaluation of one candidate beach for a requested activity and time.

It maintains three independent dimensions:

**Eligibility**
- `ELIGIBLE`
- `NEEDS_INVESTIGATION`
- `EXCLUDED`
- `UNSUPPORTED`

**Environmental suitability**
- `FAVORABLE`
- `MIXED`
- `UNFAVORABLE`
- `UNDETERMINED`

**Evidence quality**
- `SUFFICIENT`
- `LIMITED`
- `INSUFFICIENT`

These dimensions shall not be collapsed into a numerical score.

## 9.4 Investigation State

Stores the Coordinator's current working information.

It includes the normalized request, active revision, candidate assessments, evidence, unresolved questions, and operational progress according to the approved schema.

Investigation State is mutable during execution.

## 9.5 Recommendation Result

Represents the structured outcome of an investigation.

The result contains supported recommendations, material limitations, evidence references, or an explained no-recommendation or failure outcome.

The CLI renders this validated structure.

## 9.6 Investigation Trace

Records observable operations and decisions throughout the investigation.

The trace is append-only and distinct from Investigation State.

It captures execution facts and policy outcomes, not private model chain-of-thought.

---

# 10. Investigation Lifecycle

The Coordinator manages a bounded investigation lifecycle.

The following are logical workflow phases, not a new serialized state enumeration.

## 10.1 Phase 1 — Request Interpretation

1. Receive the user request.
2. Identify the requested activity.
3. Resolve the requested time period.
4. Identify supplied experience information.
5. Separate hard constraints from soft preferences.
6. Request clarification when materially necessary.
7. Establish the active normalized request.

Requests involving relative dates must use the investigation's current time and Hawaii time-zone interpretation.

## 10.2 Phase 2 — Candidate Selection

1. Query the verified Beach Catalog.
2. Filter unsupported activities and hard geographic restrictions.
3. Select supported beaches for further investigation.
4. Record candidate IDs in Investigation State.
5. Identify persistent hazards and relevant geographic characteristics.

A beach's inclusion in the candidate set does not establish safety.

## 10.3 Phase 3 — Evidence Planning

The Coordinator identifies the environmental categories required for the requested activity.

Evidence requirements follow `05-safety-policies.md`.

The Coordinator prepares scoped requests for the appropriate specialists.

The investigation plan must remain within configured execution limits.

## 10.4 Phase 4 — Specialist Investigation

Weather and Ocean specialists retrieve evidence from approved providers.

Independent investigations may execute concurrently.

Specialists return structured responses, findings, errors, and outstanding gaps.

The Coordinator shall not assume response arrival order.

## 10.5 Phase 5 — Contract and Evidence Validation

The system validates specialist responses before accepting their findings.

The Evidence Validator evaluates:

- Source authorization and provenance.
- Schema correctness.
- Temporal relevance.
- Geographic applicability.
- Measurement integrity.
- Completeness.
- Material conflicts.

Findings may be accepted, limited, or rejected according to the approved schema and validation policy.

Retrieval success is independent of evidence validation.

## 10.6 Phase 6 — Safety and Candidate Assessment

Trusted deterministic components evaluate mandatory evidence and applicable safety policies.

The Coordinator updates Candidate Assessments based on validated outcomes.

Only candidates satisfying the eligibility requirements may proceed to recommendation comparison.

## 10.7 Phase 7 — Bounded ReAct Investigation

If important questions remain unresolved, the Coordinator may:

- Inspect evidence gaps.
- Select an authorized next investigation.
- Delegate a new specialist request.
- Use an approved fallback.
- Consider other supported candidate beaches.
- Reevaluate affected assessments.

Each additional investigation must have a documented purpose and remain within permitted limits.

The Coordinator shall not repeatedly retrieve the same information without a reason or exceed authorized budgets.

## 10.8 Phase 8 — Recommendation Comparison

Eligible candidates are compared qualitatively using:

- Environmental suitability.
- Validated evidence and its limitations.
- Explicit user preferences.
- Verified beach characteristics.
- Geographic preferences.

FAVORABLE candidates generally rank above otherwise comparable MIXED candidates.

Ties or comparable alternatives are permitted.

No arbitrary numerical suitability weights are required.

## 10.9 Phase 9 — Result Validation

The Coordinator produces a structured Recommendation Result.

Trusted validation checks that:

- Referenced beaches are supported.
- Recommended candidates are eligible.
- Required evidence and safety policies are satisfied.
- Claims have appropriate supporting references.
- Material limitations are disclosed.
- The result conforms to the approved schema.

Invalid results must not be displayed as valid recommendations.

## 10.10 Phase 10 — Terminal Outcome

The investigation ends with one of three logical outcomes:

- **Recommendation:** One or more eligible candidates are returned.
- **Abstention:** No supported recommendation can be established.
- **Technical failure:** An unrecoverable system error prevents correct completion.

Exact serialized outcome values and state fields are defined by `03-data-schemas.md`.

The architecture shall not introduce competing terminal-state definitions.

---

# 11. Bounded ReAct Design

ReAct provides the Coordinator's adaptive investigation pattern.

The system does not require a full Tree-of-Thought search or unrestricted autonomous exploration.

## 11.1 Investigation Cycle

The Coordinator may repeat the following bounded cycle:

1. Review current Investigation State.
2. Identify a specific unresolved evidence question.
3. Select an approved investigation action.
4. Invoke the appropriate specialist.
5. Validate returned information.
6. Update Candidate Assessments.
7. Determine whether further investigation is justified.

The cycle ends when:

- Sufficient evidence supports the permitted recommendations.
- No eligible candidates remain and further investigation is not justified.
- Required evidence cannot be established.
- An execution limit is reached.
- An unrecoverable error occurs.

## 11.2 Investigation Budgets

Trusted components shall enforce configured limits on:

- Coordinator iterations.
- Specialist requests.
- External tool calls.
- Retry attempts.
- Other approved execution constraints.

Exact numerical limits remain open.

The LLM shall not grant itself additional execution capacity.

## 11.3 Investigation Trace

Material operations and decisions must produce observable trace events.

The trace shall identify actual tool calls, results, validation outcomes, retries, fallbacks, and terminal decisions.

Private model chain-of-thought shall not be logged.

---

# 12. Safety and Eligibility Architecture

Safety enforcement is a trusted workflow responsibility.

It is not delegated to an autonomous Safety Agent.

## 12.1 Evidence Sufficiency

Evidence requirements are specific to swimming, snorkeling, and SUP.

The mandatory evidence categories include:

- Applicable official advisories.
- Surf and wave conditions.
- Currents and persistent hazards.
- Water-quality advisory checks.
- Verified beach characteristics.
- Wind conditions where mandatory.

Underwater visibility is important for snorkeling but is not universally mandatory.

Missing visibility alone does not automatically exclude an otherwise eligible snorkeling candidate.

## 12.2 Policy Evaluation

Policy checks produce documented results using:

- `PASS`
- `FAIL`
- `UNKNOWN`
- `NOT_APPLICABLE`

The associated policy actions are:

- `EXCLUDE`
- `INVESTIGATE`
- `DISCLOSE`

These are distinct from the candidate eligibility states.

## 12.3 Eligibility Enforcement

A candidate may be ELIGIBLE only when:

1. Its activity and beach are supported.
2. Evidence quality is SUFFICIENT.
3. Mandatory hazard checks are resolved.
4. No disqualifying safety policy has failed.
5. Explicit hard user constraints are satisfied.
6. Environmental suitability is FAVORABLE or an explicitly permitted MIXED condition.

UNFAVORABLE and UNDETERMINED candidates cannot be eligible.

NEEDS_INVESTIGATION and UNSUPPORTED candidates cannot be recommended.

## 12.4 MIXED Suitability

MIXED recommendations are permitted only when:

- Evidence is SUFFICIENT.
- No disqualifying policy has failed.
- Mandatory hazards are resolved.
- Remaining limitations are non-disqualifying.
- Required disclosures are included.

MIXED does not automatically establish eligibility.

## 12.5 Safety Precedence

Safety and mandatory evidence rules take precedence over user preferences.

Applicable official restrictions cannot be overridden by favorable supplemental reports.

When a mandatory decision remains unresolved, the candidate stays non-recommendable.

## 12.6 Policy Authority

`05-safety-policies.md` is authoritative for hazard rules, evidence requirements, candidate eligibility, MIXED suitability, conflict handling, and abstention.

This architecture document shall not independently define new environmental thresholds or safety exemptions.

---

# 13. Investigation State Management

The Coordinator owns Investigation State.

Specialists shall not directly modify it.

## 13.1 State Update Rules

**ARCH-ST-001:** State changes must follow validated inputs and approved workflow rules.

**ARCH-ST-002:** Specialist responses must be contract-validated before trusted merging.

**ARCH-ST-003:** Independent findings must not be silently overwritten.

**ARCH-ST-004:** Each accepted finding must retain its source and identifier.

**ARCH-ST-005:** Outdated request revisions must not replace active assessments.

**ARCH-ST-006:** Relevant state changes must generate trace events.

**ARCH-ST-007:** Retry results must remain correlated with the correct logical request and attempt.

## 13.2 Concurrent Specialist Execution

Weather and Ocean investigations may execute concurrently when independent.

Each response is validated before merging.

Merge behavior must preserve:

- Request correlation.
- Source provenance.
- Findings from independent specialists.
- Conflicts.
- Outstanding gaps.
- Current revision authority.

Completion order shall not determine which evidence is considered authoritative.

## 13.3 Follow-up Requests

The CLI supports in-session follow-ups.

A follow-up may modify only a subset of the active request.

Example:

"Actually, let's look near Napili instead."

The Coordinator shall preserve unchanged constraints, update the geographic preference, and reevaluate affected candidates.

Existing evidence may be reused only when it remains valid and applicable.

A revised request must not silently inherit incompatible assessments.

---

# 14. Failure and Recovery Architecture

The system must handle expected environmental retrieval failures without fabricating results.

## 14.1 Failure Categories

Possible failures include:

- Provider unavailable.
- Provider timeout.
- Access denied.
- Invalid source response.
- Contract-validation failure.
- Stale evidence.
- Geographic mismatch.
- Incomplete findings.
- Material source conflict.
- Execution budget exhaustion.
- Internal application failure.

## 14.2 Partial Success

A specialist may return PARTIAL results.

The Coordinator may retain valid findings while recording unresolved evidence gaps.

Partial retrieval success does not establish candidate eligibility.

## 14.3 Retry

A retry is permitted only when:

- The operation is authorized.
- The relevant failure is retryable.
- The Coordinator or trusted orchestration component approves further investigation.
- Sufficient execution budget remains.

A retryable error alone does not authorize an unlimited retry loop.

## 14.4 Fallback

When a provider cannot supply necessary evidence, the Coordinator may select another approved source.

Fallback must preserve:

- The original failure.
- The alternative provider identity.
- Source permissions.
- Geographic and temporal applicability.
- Remaining execution limits.

A fallback result must pass normal evidence validation.

## 14.5 Abstention

If mandatory evidence remains unresolved after permitted investigation, the affected candidate cannot be recommended.

If no eligible candidate remains, the system returns an explained NO_RECOMMENDATION outcome.

An unresolved candidate must not automatically be classified EXCLUDED merely because the investigation budget was exhausted.

## 14.6 Technical Failure

An unrecoverable orchestration or application failure shall be represented as a technical failure using the approved result and investigation state definitions.

A correctly handled provider outage leading to insufficient evidence is an abstention, not necessarily a technical failure.

---

# 15. Recommendation Architecture

Only eligible candidates enter final recommendation comparison.

## 15.1 Qualitative Comparison

The Coordinator compares candidates based on supported environmental suitability, user preferences, and verified geographic characteristics.

The architecture shall not introduce arbitrary numeric ranking weights.

Comparable candidates may be presented as ties.

## 15.2 Recommendation Count

The CLI returns up to three recommendations by default.

If only one or two beaches qualify, it returns only those eligible candidates.

The system shall not add unsupported locations to fill the requested count.

## 15.3 Result Grounding

Material factual claims must be traceable to:

- Accepted Environmental Findings.
- Verified Beach Catalog attributes.
- Documented policy or assessment outcomes.

Regional evidence must retain its proper attribution.

## 15.4 User Communication

Final responses shall communicate:

- Recommended beaches.
- Activity and supported time period.
- Reasons for recommendation.
- Relevant environmental findings.
- Important advisories and limitations.
- Material uncertainty.
- Recognizable source references.

The application shall not guarantee safety.

Users should be encouraged to verify official warnings, posted notices, lifeguard guidance, and current on-site conditions before entering the water.

---

# 16. Observability Architecture

The Forecaster uses the existing Investigation Trace schema as the logical execution record.

No additional Monitoring or Logging Agent is required.

## 16.1 Event Recording

A trusted logging component records material:

- Request events.
- Specialist operations.
- Tool calls and failures.
- Contract validation.
- Evidence validation.
- Policy evaluations.
- Candidate reassessments.
- Retry and fallback operations.
- Execution budget exhaustion.
- Terminal outcomes.

## 16.2 State Versus History

Investigation State represents the current working assessment.

Investigation Trace represents the observable history of material actions and decisions.

The trace is append-only.

It shall not be reconstructed after execution using fabricated events.

## 16.3 Local Storage

Local JSON Lines (`.jsonl`) is the preferred event-storage format.

No external telemetry service, distributed tracing infrastructure, or separate observability database is required.

## 16.4 Privacy

Trace events shall exclude:

- Credentials and authentication secrets.
- Unnecessary personal information.
- Private model chain-of-thought.
- Untrusted source instructions presented as authorized actions.

## 16.5 Event Vocabulary

`03-data-schemas.md` defines the authoritative Investigation Trace schema.

The event names proposed by `07-observability.md` and required by `06-test-acceptance.md` must be reconciled into one consistent vocabulary before implementation.

This architecture document does not introduce a separate event enumeration.

---

# 17. Security and Trust Boundaries

The architecture separates trusted application components from untrusted external content.

## 17.1 Trusted Components

Trusted components include:

- Approved configuration.
- Agent and tool permission enforcement.
- Contract validators.
- Evidence validators.
- Safety-policy evaluators.
- Result validators.
- Trace-event generation.

## 17.2 Untrusted Inputs

Untrusted inputs include:

- Retrieved webpages and reports.
- External API response content.
- Other third-party environmental information.
- User-supplied requests, which must be interpreted within application permissions.

## 17.3 External Content Isolation

External content may supply evidence but must not:

- Change agent instructions.
- Modify safety policies.
- Expand source permissions.
- Authorize external transactions.
- Forge structured trace events.
- Override hard constraints.

## 17.4 Read-Only Tool Boundary

Environmental tools shall be limited to approved retrieval operations.

No external mutation, booking, scheduling, messaging, or purchasing tools are authorized for the MVP.

## 17.5 Fail-Safe Validation

Invalid contracts, unsupported evidence, or unresolved mandatory safety checks must not result in an eligible recommendation.

Safety rules shall not be bypassed because a provider or logging operation fails.

---

# 18. Testing Architecture

Testing shall follow `06-test-acceptance.md`.

The primary acceptance strategy uses controlled synthetic environmental scenarios.

## 18.1 Synthetic Execution

A synthetic test may supply:

- Fixed reference time.
- Fictional verified beach records.
- Weather and Ocean findings.
- Provider errors and response delays.
- Versioned policy configuration.
- Expected eligibility outcomes.
- Expected Recommendation Result.
- Required Investigation Trace assertions.

The synthetic fixtures are authoritative for expected test inputs and outcomes, but they do not establish real Maui conditions.

## 18.2 Testing Boundaries

Tests shall distinguish:

1. Contract and schema correctness.
2. Evidence validation.
3. Deterministic policy enforcement.
4. Coordinator workflow behavior.
5. End-to-end output correctness.
6. Qualitative explanation quality.

A synthetic EXCLUDE outcome can verify enforcement without proving that an actual wind or wave measurement should trigger that exclusion.

## 18.3 Mandatory Gates

Mandatory deterministic safety and contract tests must pass.

A persuasive final explanation does not compensate for a failed safety check.

Tests depending on unresolved provider rules or environmental thresholds must remain BLOCKED rather than using invented criteria.

## 18.4 Initial Scenario Set

The approved acceptance baseline includes twelve synthetic scenarios covering:

- Multiple favorable recommendations.
- Soft geographic preferences.
- A single eligible candidate.
- Official water-contact advisories.
- Hazardous SUP offshore wind.
- Permitted MIXED snorkeling conditions.
- Stale source reports.
- Material evidence conflicts.
- Successful fallback.
- Provider outage and abstention.
- Prompt-injection resistance.
- Conversational request revision.

---

# 19. MVP Deployment and Operational Constraints

The MVP is designed for local CLI execution.

## 19.1 Persistence

Persistent application data is limited to what the requirements justify, including:

- The curated Beach Catalog.
- Approved configuration.
- Local investigation traces.
- Synthetic test fixtures and results.

Investigation State and in-session user context need not be stored as permanent user profiles.

## 19.2 Technology Independence

This specification does not mandate:

- A programming language.
- An LLM provider.
- An agent orchestration library.
- A database engine.
- A cloud platform.

Those choices may be made during implementation planning without changing approved logical responsibilities.

## 19.3 Explicit MVP Exclusions

The architecture shall not include:

- Additional autonomous agent roles.
- Full Tree-of-Thought search.
- Vector-database or semantic RAG infrastructure.
- Automated bookings or external transactions.
- Drive-time calculation or route planning.
- Personal account management.
- Permanent personalized profiles.
- Continuous autonomous monitoring.
- Distributed deployment requirements.
- Enterprise observability infrastructure.

Retrieval of current environmental conditions through approved tools does not require a semantic RAG system.

---

# 20. Cross-Specification Authority

To avoid conflicting definitions, the following documents are authoritative for their respective areas.

| Specification | Authoritative responsibility |
|---|---|
| `01-product-requirements.md` | Product behavior, scope, user requirements |
| `02-system-architecture.md` | Component relationships and overall workflow |
| `03-data-schemas.md` | Logical records, fields, enumerations, state definitions |
| `04-agent-tool-contracts.md` | Agent communication, tool permissions, source contracts |
| `05-safety-policies.md` | Hazard rules, evidence sufficiency, eligibility enforcement |
| `06-test-acceptance.md` | Test scenarios and acceptance gates |
| `07-observability.md` | Event semantics, trace requirements, logging behavior |

When an apparent contradiction exists, it must be resolved through a documented specification update.

No implementation component may independently override one specification based on an informal interpretation of another.

---

# 21. Architecture Acceptance Criteria

The logical architecture is acceptable when:

**ARCH-A001:** The system contains exactly the three approved agent roles.

**ARCH-A002:** The Coordinator owns investigation planning and final recommendation generation.

**ARCH-A003:** Specialists return evidence rather than final eligibility decisions.

**ARCH-A004:** Agent interactions use validated structured contracts.

**ARCH-A005:** Tool execution remains within explicitly approved sources and scopes.

**ARCH-A006:** Evidence validation is separate from retrieval success.

**ARCH-A007:** Deterministic components enforce critical safety and eligibility policies.

**ARCH-A008:** Bounded ReAct investigation is supported without unrestricted exploration.

**ARCH-A009:** Investigation State is Coordinator-owned and distinct from append-only Investigation Trace.

**ARCH-A010:** Invalid or outdated responses cannot corrupt active assessments.

**ARCH-A011:** Only eligible candidates can enter final recommendations.

**ARCH-A012:** Missing or conflicting mandatory evidence leads to further authorized investigation or abstention.

**ARCH-A013:** Successful recommendation, abstention, and technical failure remain distinct.

**ARCH-A014:** CLI follow-ups preserve applicable unchanged constraints.

**ARCH-A015:** No unsupported numerical rankings, source coverage, or environmental measurements are introduced.

**ARCH-A016:** The system supports synthetic end-to-end tests and material trace assertions.

**ARCH-A017:** The architecture remains read-only and within MVP scope.

---

# 22. Open Architecture Decisions

The logical component responsibilities and investigation workflow are established.

The following implementation-specific decisions remain open.

| ID | Decision | Priority |
|---|---|---|
| ARCH-OD-001 | Final implementation language and project structure | Medium |
| ARCH-OD-002 | LLM provider and model configuration | Medium |
| ARCH-OD-003 | Whether to use an orchestration framework or lightweight custom workflow | Medium |
| ARCH-OD-004 | Physical storage format for the Beach Catalog | Medium |
| ARCH-OD-005 | Exact investigation iteration, retry, and tool-call limits | High |
| ARCH-OD-006 | Final serialization and field definitions for normalized user requests | High |
| ARCH-OD-007 | Final geographic mapping between catalog beaches and provider coverage | High |
| ARCH-OD-008 | Provider activation and fallback configuration | High |
| ARCH-OD-009 | Final trace-event vocabulary reconciliation | High |
| ARCH-OD-010 | Final policy-dependent hazard criteria and evidence sufficiency rules | High |
| ARCH-OD-011 | Handling local trace-storage failure | Medium |
| ARCH-OD-012 | Exact session and request-revision lifecycle rules | Medium |
| ARCH-OD-013 | CLI runtime configuration and local secret management | Medium |
| ARCH-OD-014 | Detailed synthetic fixture and test-harness implementation | Medium |

These decisions shall be addressed during the requirements-readiness review and implementation planning.

Undefined safety policies, source capabilities, or environmental thresholds must not be invented by implementation agents.

---

# 23. Architecture Status

## Established Logical Design

- Three-agent Coordinator/Weather/Ocean architecture.
- Centralized supervision.
- Bounded ReAct investigation.
- Scoped and validated specialist communication.
- Controlled environmental tool access.
- Curated verified Beach Catalog.
- Six logical data schemas.
- Separate evidence and safety validation.
- Deterministic candidate eligibility enforcement.
- Qualitative recommendation comparison.
- Explicit abstention and technical failure.
- Coordinator-owned Investigation State.
- Append-only Investigation Trace.
- Local CLI MVP.
- Synthetic acceptance testing.

## Pending Implementation Details

- Selected technology stack.
- Final provider access methods and permissions.
- Beach catalog population and source mappings.
- Provider freshness rules.
- Activity-specific hazard criteria.
- Exact execution budgets.
- Final normalized-request and trace-event contracts.
- Physical storage and runtime configuration.

Approval of the logical architecture does not establish that these implementation dependencies are resolved.

---

# 24. Next Phase

After approval, the seven requirements documents shall be reviewed together for:

1. Schema and contract consistency.
2. Shared enumeration and identifier alignment.
3. Safety-policy readiness.
4. Provider integration readiness.
5. Execution limits and recovery behavior.
6. Observability event vocabulary consistency.
7. Synthetic test coverage.
8. First implementation milestone scope.

The review shall classify outstanding requirements as:

- **READY:** Defined sufficiently for implementation.
- **BLOCKED:** Requires a decision or verification before implementation.
- **DEFER:** May be postponed without compromising mandatory MVP behavior.

The recommended initial development milestone is a synthetic-data vertical slice demonstrating the complete approved workflow.

No live provider shall be treated as verified solely because it appears in the approved provider registry.

---

**End of System Architecture Specification v0.1**

**Status:** Approved — Logical Design; implementation decisions pending

**No application code is authorized by this document.**