# Hawaii Activity Forecaster
## Product Requirements Document (PRD)

**Version:** 0.1 — Draft  
**Status:** Proposed, pending review  
**Project:** CMU Agentic AI Systems Capstone  
**Implementation phase:** Requirements definition

---

## 1. Product Overview

### 1.1 Purpose

The Hawaii Activity Forecaster is an agentic AI application designed to help users identify suitable locations and times for swimming, snorkeling, and stand-up paddleboarding (SUP) on Maui.

The system will combine weather forecasts, ocean and marine conditions, verified geographic characteristics, and user preferences to recommend locations that best match the requested activity.

### 1.2 Problem Statement

Identifying suitable ocean conditions requires gathering information from multiple sources and interpreting how those conditions affect specific locations.

A favorable regional forecast does not necessarily represent conditions at an individual beach. Data may also be incomplete, outdated, contradictory, or geographically irrelevant.

The Forecaster aims to reduce the effort required to research these conditions while providing transparent, evidence-supported recommendations.

The system is intended to support informed decisions, not guarantee ocean safety or replace authoritative warnings and on-site judgment.

### 1.3 Target Users

Recreational ocean users visiting or living on Maui, including individuals with different experience levels and activity preferences.

### 1.4 Primary Use Case

**Example:**

"Where should I snorkel tomorrow morning? I'm intermediate, prefer calm water, and near Kihei."

The Forecaster should interpret the request, identify supported candidate beaches, retrieve relevant environmental information, evaluate constraints, and provide multiple recommendations with explanations.

If insufficient evidence exists, the system must communicate its limitations rather than invent favorable conditions.

---

## 2. MVP Scope

### 2.1 Supported Activities

The initial release will support:

- Swimming
- Snorkeling
- Stand-up paddleboarding (SUP)

Other ocean activities, such as surfing, kayaking, scuba diving, and boating, are outside the initial scope.

### 2.2 Geographic Coverage

The MVP will support approximately **10–15 verified beaches in South and West Maui**.

A curated beach catalog will define supported locations and their relatively stable geographic characteristics.

The system must not represent unsupported beaches as evaluated destinations.

The specific beach list will be finalized in the Beach Catalog specification.

### 2.3 Recommendation Format

The system will return **multiple ranked candidate locations**, where sufficient evidence and eligible candidates exist.

Each recommended location should include:

- Beach name and relevant geographic information
- Recommended activity and time period
- Explanation of why the location was selected
- Supporting weather and ocean evidence
- Relevant environmental hazards or advisories
- Important limitations and uncertainties

Ranking must be based on defined suitability criteria, not unsupported assumptions.

If only one candidate qualifies, the system may recommend that single location. If none qualify, it must explain why.

### 2.4 User Interface

The initial interface will be a **command-line interface (CLI)**.

Users will submit natural-language requests and receive readable recommendations in the terminal.

The CLI should also support conversational follow-up requests within an active session.

A graphical interface is not required for the MVP.

---

## 3. Functional Requirements

### 3.1 User Interaction

**PR-001 — Natural-Language Requests**

The system shall accept conversational requests concerning supported ocean activities, locations, dates, and preferences.

**PR-002 — Request Interpretation**

The system shall extract relevant information, including:

- Requested activity
- Target date and time window
- Starting location, when provided
- Preferred geographic area or proximity to a named location, when provided
- User experience level, when provided
- Environmental preferences and restrictions

The original user request shall be preserved alongside its normalized interpretation.

**PR-003 — Clarification**

The system shall request clarification when missing or ambiguous information materially affects its ability to investigate or recommend a location.

Optional preferences shall not automatically prevent an investigation.

**PR-004 — Conversational Follow-ups**

The system shall maintain active-session context and allow users to modify individual constraints without restating the entire request.

Example: "What if I'm willing to drive 45 minutes?"

The updated investigation shall preserve applicable unchanged constraints.

### 3.2 Geographic Information

**PR-005 — Candidate Beach Retrieval**

The system shall retrieve candidate beaches from the curated catalog using supported geographic and activity attributes.

**PR-006 — Verified Beach Information**

Persistent beach characteristics shall include source references and verification dates.

The system shall distinguish relatively stable beach attributes from changing environmental conditions.

### 3.3 Environmental Investigation

**PR-007 — Weather Information**

The system shall retrieve relevant weather information, potentially including:

- Wind conditions
- Precipitation and forecast weather
- Applicable weather advisories
- Forecast time period and geographic coverage

**PR-008 — Ocean Information**

The system shall retrieve relevant marine information, potentially including:

- Swell direction and size
- Surf or wave conditions
- Available nearshore observations
- Applicable marine advisories
- Reported visibility when a reliable source is available

Measurements not available from approved sources shall be identified as missing rather than inferred as facts.

**PR-009 — Source Attribution**

Environmental findings shall retain source identity, retrieval timestamp, applicable forecast or observation period, and geographic coverage.

**PR-010 — Evidence Validation**

The system shall assess whether environmental findings are sufficiently current, geographically relevant, and complete for the requested activity and time period.

Regional observations shall not be presented as confirmed beach-specific measurements.

### 3.4 Recommendations

**PR-011 — Constraint Evaluation**

The system shall evaluate candidate beaches against the user's stated constraints and applicable safety policies. the Coordinator distinguishes between hard constraints and soft preferences.

**PR-012 — Candidate Comparison**

The system shall compare supported candidates using the available environmental evidence, verified beach characteristics, and user preferences.

**PR-013 — Candidate Ranking and Recommendations**

The Forecaster shall evaluate candidate beaches in two stages.

First, candidates must satisfy applicable safety policies, supported activity requirements, evidence sufficiency, and explicit hard user constraints.

Second, eligible candidates will be compared based on environmental suitability, evidence quality, user preferences, and geographic proximity.

The system shall return up to three recommended locations by default, with explanations describing the relevant differences. Rankings shall not depend on arbitrary numerical suitability scores.

Geographic proximity will be treated as a preference rather than a hard constraint unless explicitly specified by the user.

When multiple candidates have comparable supporting evidence and suitability, the system may present them as similarly suitable rather than inventing distinctions.

The system shall not recommend unsuitable or insufficiently supported beaches simply to meet the default recommendation count.

**PR-014 — Investigation and Fallback**

When relevant evidence is missing or conflicting, the system may investigate approved alternative sources, time periods, or candidate beaches.

Investigation steps and retries shall be bounded.

**PR-015 — Uncertainty and Abstention**

The system shall communicate material uncertainty and decline to recommend a location when the available evidence is insufficient or applicable safety rules prohibit a recommendation.

**PR-016 — Response Grounding**

Material factual claims about environmental conditions and beach suitability shall be traceable to validated evidence or verified catalog attributes.

---

## 4. Multi-Agent Architecture Requirements

The Forecaster will use three agents with distinct responsibilities.

### Coordinator Agent

Responsible for interpreting requests, selecting candidates, delegating investigations, evaluating results, managing bounded ReAct iterations, and producing final recommendations.

### Weather Agent

Responsible for retrieving and reporting relevant weather conditions and advisories, including source information, geographic applicability, and data limitations.

### Ocean Agent

Responsible for retrieving and reporting relevant ocean conditions and marine hazards, including source information, geographic applicability, and data limitations.

### Coordination

The system will use centralized supervision with iterative, bounded ReAct reasoning.

Weather and Ocean investigations may execute in parallel when independent.

Specialist findings will be combined through a structured shared investigation state.

Critical safety and evidence validation shall be enforced by deterministic workflow components rather than relying exclusively on LLM judgment.

Detailed state transitions, agent interfaces, and tool permissions will be specified separately.

---

## 5. Safety and Reliability Requirements

**SAF-001 — Geographic Validation**

The system shall reject unsupported or unverified beach-specific claims.

**SAF-002 — Environmental Freshness**

The system shall enforce source-specific freshness requirements before treating evidence as current.

**SAF-003 — Geographic Applicability**

Environmental information shall retain its actual geographic coverage.

**SAF-004 — Hazard Evaluation**

Applicable authoritative warnings and advisories shall be evaluated before recommending an activity.

**SAF-005 — Missing Data**

Missing environmental information shall never be interpreted as favorable conditions.

**SAF-006 — Conflicting Evidence**

Material discrepancies between sources shall be preserved and either investigated or disclosed.

**SAF-007 — Bounded Autonomy**

The Coordinator shall operate within defined limits for investigation iterations, tool calls, and retries.

**SAF-008 — Safe Abstention**

When sufficient evidence cannot be established, the system shall return an explanation rather than an unsupported recommendation.

**SAF-009 — Tool Restrictions**

Agents shall access only approved tools and data sources, with permissions appropriate to their responsibilities.

**SAF-010 — External Content Isolation**

Retrieved external content shall be treated as untrusted data and shall not override agent instructions or safety policies.

**SAF-011 — Output Validation**

Recommendations shall pass documented evidence and safety validation checks before being returned.

**SAF-012 — Human Oversight**

The system may request clarification from users when necessary. During development, failed evaluations and unexpected behavior shall be available for human review.

The MVP does not require a live human approval queue.

---

## 6. Nonfunctional Requirements

**NFR-001 — Observability**

Each investigation shall produce a structured execution trace containing relevant agent actions, tool results, evidence references, validation decisions, and final outcome.

**NFR-002 — Reproducibility**

The system shall support testing with synthetic, repeatable environmental scenarios.

**NFR-003 — Maintainability**

Agent responsibilities, data-source integrations, safety policies, and persistent geographic information shall be sufficiently modular to support independent changes.

**NFR-004 — Performance**

The system shall track total response latency, investigation iterations, and tool usage.

Performance targets shall be established after baseline measurements.

**NFR-005 — Data Privacy**

The MVP shall not require user registration or persistent personal profiles.

Synthetic user data shall be used for capstone demonstrations requiring stored preferences or history.

Execution logs shall avoid retaining unnecessary personal information or secrets.

**NFR-006 — Failure Handling**

The system shall handle unavailable sources, malformed responses, tool failures, and timeouts without uncontrolled execution or fabricated results.

**NFR-007 — Configuration**

Source definitions, safety policies, and operational limits shall be configurable without requiring changes to agent responsibilities.

---

## 7. Evaluation and Acceptance Criteria

The MVP shall be evaluated using predefined synthetic scenarios, including normal operating conditions, conflicting evidence, hazardous conditions, and tool failures.

The primary evaluation dimensions will include:

| Metric | Acceptance objective |
|---|---|
| Safety compliance | All predefined deterministic safety-policy tests pass |
| Groundedness | Material factual claims are supported by identifiable evidence |
| Constraint compliance | Explicit hard user constraints are respected |
| Fallback behavior | Source failures produce permitted recovery or clear limitations |
| Appropriate abstention | The system withholds recommendations in predefined insufficient-evidence cases |
| Workflow correctness | Agent and tool interactions follow documented contracts |
| Performance | Tool usage, iterations, and latency are recorded and reviewed |

### Minimum Acceptance Scenarios

**AT-001:** Recommend multiple eligible beaches when sufficient evidence is available.

**AT-002:** Respect stated activity, experience, and travel constraints.

**AT-003:** Correctly interpret a follow-up that modifies one constraint.

**AT-004:** Request clarification when a necessary constraint is materially ambiguous.

**AT-005:** Reject stale environmental evidence as current information.

**AT-006:** Detect when a tool result references the wrong beach or geographic area.

**AT-007:** Apply documented exclusions when an authoritative hazard is applicable.

**AT-008:** Preserve and appropriately handle materially conflicting sources.

**AT-009:** Handle unavailable environmental services using documented fallback rules.

**AT-010:** Abstain when no supported recommendation can be produced.

**AT-011:** Reject instructions embedded in external source content that attempt to alter the workflow.

**AT-012:** Produce a structured execution trace sufficient to reconstruct material workflow decisions.

Successful completion of these tests demonstrates compliance with the defined MVP behavior. It does not guarantee real-world ocean safety.

---

## 8. Out of Scope

The following capabilities are explicitly excluded from the initial release:

- Geographic coverage beyond the approved South and West Maui beach catalog
- Activities beyond swimming, snorkeling, and SUP
- Booking, purchasing, or scheduling activities
- Autonomous real-world actions on behalf of users
- Mobile applications or production web interfaces
- User accounts and persistent real-user profiles
- Fine-tuning or locally hosting foundation models
- Full Tree of Thoughts search
- Semantic RAG or vector databases
- Additional autonomous reviewer or safety agents
- Enterprise security gateways or production monitoring infrastructure
- Automated ingestion of arbitrary web sources
- Guarantees of safety or real-time on-site ocean conditions

These exclusions may be reconsidered only through an explicit scope or architecture revision.

---

## 9. Dependencies

The MVP depends on:

1. A curated, verified catalog of supported Maui beaches.
2. Approved environmental information providers with usable access methods.
3. Defined agent and tool input/output contracts.
4. A documented safety-policy matrix.
5. A repeatable synthetic evaluation dataset.
6. An LLM capable of supporting the Coordinator's required reasoning and tool-driven workflow.

These dependencies must be evaluated before the corresponding implementation work begins.

---

## 10. Open Product Decisions

The following requirements remain unresolved and must be addressed in subsequent design specifications.

| ID | Open decision | Priority |
|---|---|---|
| OD-001 | Final list of supported beaches | High |
| OD-002 | Approved weather, marine, and nearshore information sources | High |
| OD-003 | Exact environmental freshness and geographic coverage requirements | High |
| OD-004 | Hazard-policy matrix by activity and advisory type | High |
| OD-005 | Required evidence for declaring a candidate eligible | High |
| OD-006 | Default behavior for omitted dates, times, experience levels, and starting locations | High |
| OD-007 | Candidate ranking criteria and treatment of uncertainty | High |
| OD-008 | Maximum investigation iterations, tool calls, retries, and timeouts | Medium |
| OD-009 | Definition and retention of active-session context | Medium |
| OD-010 | CLI response structure and presentation details | Medium |
| OD-011 | Measurable latency targets and evaluation thresholds beyond deterministic safety checks | Medium |

The implementation framework and specific LLM model remain technical decisions to be addressed in the system architecture specification.

---

## 11. MVP Completion Criteria

The MVP will be considered complete when:

1. All three planned agent roles are operational within the documented coordination workflow.
2. The CLI supports natural-language requests and session-based follow-ups.
3. The system can investigate supported beaches using approved environmental sources.
4. Recommendations are grounded in verified geographic and environmental evidence.
5. Documented safety and evidence guardrails are enforced.
6. The system handles missing, conflicting, and unavailable information appropriately.
7. Multiple candidate recommendations can be generated when supported.
8. Every investigation produces an auditable execution trace.
9. All required acceptance scenarios pass.
10. The final implementation remains within the approved capstone scope.

---

**Document status:** Draft v0.1. Product requirements are proposed for review; unresolved decisions are not authorization for coding agents to invent implementation behavior.