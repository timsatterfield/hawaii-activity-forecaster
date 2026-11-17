# Hawaii Activity Forecaster
# Data Schemas Specification

**Version:** 0.1  
**Status:** Approved — Logical Design  
**Project:** CMU Agentic AI Systems Capstone  
**Document:** `docs/requirements/03-data-schemas.md`

---

## 1. Purpose and Scope

This document defines the logical data schemas used by the Hawaii Activity Forecaster.

The Forecaster recommends suitable Maui locations and times for swimming, snorkeling, and stand-up paddleboarding (SUP) using verified geographic characteristics, environmental evidence, user preferences, and documented safety policies.

The schemas establish how information is represented, validated, and exchanged between the Coordinator, Weather Agent, and Ocean Agent.

They are technology-independent. They do not prescribe SQLite table structures, Python models, a particular agent framework, or external API implementations.

### 1.1 Core Schemas

The system uses six primary schemas:

1. **Beach Catalog** — Persistent, verified geographic reference data.
2. **Environmental Finding** — Weather and ocean evidence retrieved during investigations.
3. **Candidate Assessment** — Evaluation of one beach for a particular activity and time.
4. **Investigation State** — Current working state of an investigation.
5. **Recommendation Result** — Validated structured output presented to users.
6. **Investigation Trace** — Ordered record of significant actions and decisions.

### 1.2 Design Principles

- Maintain a clear separation between stable geographic information and changing environmental conditions.
- Preserve data provenance, geographic coverage, and temporal validity.
- Distinguish retrieved information from validated evidence.
- Represent missing and conflicting evidence explicitly.
- Enforce critical safety and eligibility policies through deterministic validation.
- Keep environmental suitability, evidence quality, and eligibility separate.
- Avoid unsupported numerical suitability and confidence scores.
- Allow bounded investigation and meaningful abstention.
- Keep working state separate from execution history.
- Do not record private model chain-of-thought or unnecessary personal information.

### 1.3 Shared Conventions

All schemas use the following conventions.

**Identifiers**

Identifiers are unique within their defined scope. Referenced identifiers must resolve to existing records unless explicitly marked as external references.

**Enumerations**

Enumerated values use uppercase identifiers. Implementations must not introduce additional values without updating the relevant specification.

**Timestamps**

Timestamps must include an explicit time-zone offset or use UTC with an unambiguous UTC designator.

Maui activity times shall be presented to users in Hawaii Standard Time (`Pacific/Honolulu`).

**Required and Optional Fields**

A required field must be present in a valid record.

Conditional fields are required when the relevant record type, lifecycle state, or outcome applies.

An unknown value must not be replaced with an unsupported assumption.

**Source References**

Material factual claims must remain traceable to source information, verified catalog attributes, or documented assessment rules.

**Schema Versioning**

Structured records shall identify their schema version where specified. Changes affecting field meaning, allowed values, or validation rules require a documented schema revision.

---

# 2. Beach Catalog Schema

## 2.1 Purpose

The Beach Catalog provides verified, relatively stable information about beaches supported by the Forecaster.

The initial catalog will contain approximately 10–15 named beaches in South and West Maui.

The Coordinator uses the catalog to select candidates, interpret geographic preferences, identify supported activities, and evaluate persistent beach characteristics.

The catalog does not store current weather, surf, water visibility, or daily suitability scores.

## 2.2 Beach Record

### Identity and Location

| Field | Type | Required | Description |
|---|---|---|---|
| `beach_id` | String | Yes | Unique, stable beach identifier |
| `name` | String | Yes | Primary beach name |
| `aliases` | String list | No | Common alternative names |
| `region` | Enum | Yes | SOUTH_MAUI / WEST_MAUI |
| `locality` | String | Yes | Kihei, Wailea, Napili, etc. |
| `latitude` | Decimal | Yes | Verified representative coordinate |
| `longitude` | Decimal | Yes | Verified representative coordinate |
| `location_notes` | String | No | Geographic or access limitations |

### Geographic Characteristics

| Field | Type | Required | Description |
|---|---|---|---|
| `shoreline_orientation` | Enum | No | General shoreline-facing direction |
| `coastline_exposure` | Structured list | No | Documented exposure characteristics |
| `shore_type` | Enum/list | No | Sand, rock, mixed, etc. |
| `entry_characteristics` | Structured list | No | Documented shoreline entry characteristics |
| `reef_presence` | Enum | No | PRESENT / ABSENT / UNKNOWN |
| `reef_notes` | String | No | Verified reef characteristics |
| `access_notes` | String | No | Public-access considerations |

These fields represent persistent characteristics, not current environmental suitability.

### Activities and Safety

| Field | Type | Required | Description |
|---|---|---|---|
| `supported_activities` | Enum list | Yes | SWIMMING / SNORKELING / SUP |
| `lifeguard_status` | Enum | Yes | STAFFED / NOT_STAFFED / UNKNOWN |
| `lifeguard_notes` | String | No | Documented service limitations |
| `known_hazards` | Structured list | No | Verified persistent hazards |
| `activity_notes` | Structured list | No | Activity-specific characteristics |

**Activity support is not activity suitability.**

A beach supporting snorkeling means it may be evaluated for snorkeling. It does not establish that snorkeling is appropriate on a particular day.

Actual suitability is determined separately using environmental findings, user constraints, and safety policies.

### Verification and Status

| Field | Type | Required | Description |
|---|---|---|---|
| `sources` | SourceReference list | Yes | Supporting public references |
| `last_verified` | Date | Yes | Most recent catalog review |
| `catalog_status` | Enum | Yes | VERIFIED / NEEDS_REVIEW / DISABLED |
| `verification_notes` | String | No | Outstanding limitations |

Only VERIFIED records may be used as recommendation candidates.

## 2.3 SourceReference

| Field | Type | Required | Description |
|---|---|---|---|
| `source_id` | String | Yes | Source identifier |
| `publisher` | String | Yes | Source publisher |
| `url` | String | Yes | Public reference URL |
| `title` | String | No | Source title |
| `accessed_at` | Date | Yes | Most recent access |
| `supports_fields` | String list | Yes | Attributes supported |
| `notes` | String | No | Relevant qualifications |

Material attributes must have identifiable supporting sources. A general list of URLs is insufficient when the source supporting an individual attribute cannot be determined.

## 2.4 Validation Rules

**BC-001:** Every beach shall have a unique, immutable `beach_id`.

**BC-002:** Geographic coordinates must be valid and verified.

**BC-003:** Every record must identify a supported geographic region.

**BC-004:** Supported activities must use the defined activity enumeration.

**BC-005:** Unknown attributes must remain unknown and must not be replaced with favorable assumptions.

**BC-006:** Material geographic and safety attributes must have supporting references.

**BC-007:** Only VERIFIED beaches may enter recommendation eligibility evaluation.

**BC-008:** The catalog shall not store current environmental observations or daily suitability scores.

**BC-009:** Changes to geographic characteristics or safety information must update the verification record.

**BC-010:** Disabled or unverified locations shall not be eligible for recommendation.

**BC-011 — Beach Granularity:** Each named beach shall have one catalog record and a unique `beach_id`. Individual access points or sublocations shall not be modeled as separate records in the MVP. Material differences within a beach may be documented in notes and must not be ignored during suitability evaluation.

**BC-012 — Activity Support vs. Suitability:** `supported_activities` identifies activities that may be evaluated at a beach. It does not establish current suitability or safety. Suitability must be determined separately from validated environmental evidence and applicable policies.

## 2.5 Relationships

- Environmental Findings may reference a beach when source coverage is genuinely beach-specific.
- Candidate Assessments reference catalog beach IDs.
- Investigation State maintains candidate beach identifiers.
- Recommendation Results reference verified catalog records.

## 2.6 Open Decisions

- Final list of supported beaches and boundaries.
- Controlled vocabulary for shoreline orientation and exposure.
- Whether lifeguard schedules require separate structured information.
- Minimum verified attributes required to activate a beach.
- Catalog re-verification frequency.
- Representation of material differences across large beaches.
- Additional geographic subdivisions, if needed.

---

# 3. Environmental Finding Schema

## 3.1 Purpose

Environmental Findings represent weather and ocean evidence retrieved from approved sources during an investigation.

Weather and Ocean agents share a common finding structure, with domain-specific measurement categories.

A finding preserves what a source actually reported, including its geographic scope, temporal validity, and limitations.

It does not independently determine whether a beach is eligible for recommendation.

## 3.2 EnvironmentalFinding

### Identification

| Field | Type | Required | Description |
|---|---|---|---|
| `finding_id` | String | Yes | Unique finding identifier |
| `investigation_id` | String | Yes | Parent investigation |
| `agent_type` | Enum | Yes | WEATHER / OCEAN |
| `source_id` | String | Yes | Approved provider identifier |
| `source_reference` | String | Conditional | URL or identifiable source document |
| `finding_type` | Enum | Yes | OBSERVATION / FORECAST / ADVISORY / REPORT |

A REPORT may contain qualitative information rather than directly measured conditions.

Qualitative reports must not be represented as instrument observations unless supported by the source.

### Geographic Coverage

| Field | Type | Required | Description |
|---|---|---|---|
| `coverage_type` | Enum | Yes | BEACH / LOCAL_AREA / REGIONAL / OFFSHORE |
| `coverage_id` | String | Conditional | Geographic area identifier |
| `coverage_description` | String | Yes | Area represented by the source |
| `beach_id` | String | Conditional | Verified beach-specific reference |
| `coverage_notes` | String | No | Geographic limitations |

A finding may apply to multiple beaches or to a broader area.

A BEACH designation requires source evidence specific to the named beach.

Regional and offshore findings must retain their original coverage rather than being relabeled as beach-specific measurements.

### Temporal Information

| Field | Type | Required | Description |
|---|---|---|---|
| `retrieved_at` | Timestamp | Yes | Retrieval time |
| `issued_at` | Timestamp | Conditional | Publication or issuance time |
| `valid_from` | Timestamp | Conditional | Beginning of applicability |
| `valid_until` | Timestamp | Conditional | End of applicability |
| `observed_at` | Timestamp | Conditional | Observation time |
| `temporal_notes` | String | No | Relevant timing limitations |

Required temporal information depends on the finding type and source contract.

Retrieval time must not be interpreted as observation time.

### Environmental Information

| Field | Type | Required | Description |
|---|---|---|---|
| `measurements` | Measurement list | No | Structured values |
| `advisories` | AdvisoryReference list | No | Relevant advisories |
| `descriptive_findings` | String list | No | Supported qualitative statements |
| `missing_fields` | String list | No | Expected unavailable information |

## 3.3 Measurement

| Field | Type | Required | Description |
|---|---|---|---|
| `measurement_type` | Enum | Yes | Measurement category |
| `value` | Number / Range / Category | Yes | Reported value |
| `unit` | String | Conditional | Original or documented normalized unit |
| `measurement_time` | Timestamp | Conditional | Associated observation or forecast time |
| `measurement_notes` | String | No | Definitions and limitations |
| `measurement_convention` | String | No | Localized measurement method |

### Proposed Weather Measurement Types

- `WIND_SPEED`
- `WIND_DIRECTION`
- `WIND_GUST`
- `PRECIPITATION`
- `AIR_TEMPERATURE`
- `WEATHER_CONDITION`

### Proposed Ocean Measurement Types

- `SWELL_HEIGHT`
- `SWELL_DIRECTION`
- `SWELL_PERIOD`
- `SURF_HEIGHT`
- `WATER_VISIBILITY`
- `WATER_TEMPERATURE`

Final measurement requirements and units depend on approved source capabilities.

Surf height and swell height are distinct measurements and must not be silently substituted.

## 3.4 AdvisoryReference

| Field | Type | Required | Description |
|---|---|---|---|
| `advisory_id` | String | Yes | Advisory identifier |
| `issuer` | String | Yes | Issuing authority |
| `advisory_type` | String | Yes | Original advisory category |
| `severity` | String | Conditional | Source-provided severity |
| `affected_area` | String | Yes | Geographic applicability |
| `effective_from` | Timestamp | Conditional | Start of applicability |
| `effective_until` | Timestamp | Conditional | End of applicability |
| `source_reference` | String | Yes | Original advisory source |

Original advisory terminology must be preserved.

The Safety Policy specification determines how each relevant advisory affects candidate eligibility.

## 3.5 Retrieval and Validation Status

| Field | Type | Required | Description |
|---|---|---|---|
| `retrieval_status` | Enum | Yes | SUCCESS / PARTIAL / UNAVAILABLE / ERROR |
| `validation_status` | Enum | Yes | PENDING / ACCEPTED / LIMITED / REJECTED |
| `limitations` | String list | No | Known information limitations |
| `error_code` | String | Conditional | Structured failure identifier |
| `error_message` | String | Conditional | Failure description |

Retrieval and validation are independent.

For example, a successful source request may return stale or geographically unsuitable information.

That result may be SUCCESS for retrieval but REJECTED for evidence validation.

## 3.6 Validation Rules

**EF-001:** Successful and partial findings must identify an approved source.

**EF-002:** Findings must preserve the source's geographic coverage.

**EF-003:** Regional or offshore evidence shall not be represented as confirmed beach-specific observations.

**EF-004:** Findings must preserve their applicable observation or forecast period when available.

**EF-005:** Evidence must meet source-specific freshness policies before being used as current information.

**EF-006:** Values, units, definitions, and measurement types must remain consistent with the source.

**EF-007:** Missing values must be recorded as unavailable rather than invented.

**EF-008:** Material conflicts must be preserved rather than silently averaged or discarded.

**EF-009:** Relevant advisories must retain issuer, geographic coverage, applicability period, and source reference.

**EF-010:** Retrieval failures must not produce fabricated measurements.

**EF-011:** Successful retrieval does not imply successful validation.

**EF-012:** Material environmental claims must remain traceable to their source.

## 3.7 Relationships

- Weather and Ocean agents produce Environmental Findings.
- Investigation State accumulates findings and evidence issues.
- Candidate Assessments reference relevant finding IDs.
- Recommendation Results reference supporting findings.
- Investigation Trace records retrieval and validation events.

## 3.8 Open Decisions

- Approved weather and ocean providers.
- Exact measurement types, values, and units supported by providers.
- Source-specific freshness thresholds.
- Required temporal metadata for each source.
- Geographic applicability rules for regional evidence.
- Minimum evidence by activity.
- Representation of qualitative nearshore reports.
- Treatment of missing and contradictory information.
- Investigation-level caching.
- Provider outage and partial-response contracts.

---

# 4. Candidate Assessment Schema

## 4.1 Purpose

Candidate Assessment evaluates one beach for one activity and requested time period.

It combines:

- Verified Beach Catalog attributes.
- Validated Environmental Findings.
- User constraints and preferences.
- Applicable safety policies.

An assessment determines whether a candidate may enter the recommendation comparison.

An eligible assessment is not a guarantee of safety.

## 4.2 CandidateAssessment

### Identity and Context

| Field | Type | Required | Description |
|---|---|---|---|
| `assessment_id` | String | Yes | Unique assessment identifier |
| `investigation_id` | String | Yes | Parent investigation |
| `beach_id` | String | Yes | Beach Catalog reference |
| `activity` | Enum | Yes | SWIMMING / SNORKELING / SUP |
| `target_time_window` | Time range | Yes | Requested period |
| `evaluated_at` | Timestamp | Yes | Assessment time |

The same beach may have different assessments for different activities or time windows.

### Independent Assessment Dimensions

| Field | Type | Required |
|---|---|---|
| `eligibility` | Enum | Yes |
| `environmental_suitability` | Enum | Yes |
| `evidence_quality` | Enum | Yes |

#### Eligibility

`ELIGIBLE`

Candidate meets documented eligibility requirements and may enter recommendation comparison.

`NEEDS_INVESTIGATION`

Further evidence or clarification may resolve an incomplete assessment.

`EXCLUDED`

Candidate violates an applicable safety policy or hard constraint, or is otherwise disqualified under documented rules.

`UNSUPPORTED`

Beach or requested activity is outside verified catalog support.

#### Environmental Suitability

`FAVORABLE`

Validated conditions support the requested activity under applicable assessment rules.

`MIXED`

Conditions include both supporting evidence and material limitations or concerns.

`UNFAVORABLE`

Validated conditions indicate the activity should not be recommended.

`UNDETERMINED`

Evidence does not establish suitability.

#### Evidence Quality

`SUFFICIENT`

Required evidence satisfies documented freshness, geographic relevance, and completeness requirements.

`LIMITED`

Useful evidence exists, but material limitations remain.

`INSUFFICIENT`

Minimum evidence requirements have not been met.

The three dimensions must be maintained independently.

## 4.3 Environmental Evidence

| Field | Type | Required | Description |
|---|---|---|---|
| `supporting_finding_ids` | String list | Yes | Evidence used in assessment |
| `conflicting_finding_ids` | String list | Yes | Material conflicting evidence |
| `rejected_finding_ids` | String list | Yes | Evidence rejected by validation |
| `evidence_limitations` | String list | Yes | Missing or limited information |
| `assessment_basis` | String | Yes | Concise evidence interpretation |

Referenced findings must exist in the investigation.

Rejected evidence cannot be used as positive supporting evidence.

## 4.4 Constraints and Preferences

| Field | Type | Required | Description |
|---|---|---|---|
| `hard_constraint_results` | ConstraintResult list | Yes | Mandatory checks |
| `preference_results` | PreferenceResult list | Yes | Soft preference comparisons |
| `geographic_preference_match` | Enum | Yes | PREFERRED_AREA / NEARBY_AREA / OUTSIDE_PREFERRED_AREA / NOT_SPECIFIED |

Geographic preferences such as "near Kihei" are soft preferences unless explicitly stated as hard restrictions.

### ConstraintResult

| Field | Type | Required |
|---|---|---|
| `constraint_id` | String | Yes |
| `constraint_description` | String | Yes |
| `result` | PASS / FAIL / UNKNOWN | Yes |
| `explanation` | String | Yes |

Hard constraints with FAIL disqualify a candidate.

UNKNOWN must not be treated as PASS.

### PreferenceResult

| Field | Type | Required |
|---|---|---|
| `preference_id` | String | Yes |
| `preference_description` | String | Yes |
| `alignment` | MATCH / PARTIAL / NO_MATCH / UNKNOWN | Yes |
| `explanation` | String | Yes |

Preferences influence comparisons between eligible candidates but cannot override safety rules.

## 4.5 Safety Policy Results

| Field | Type | Required |
|---|---|---|
| `policy_results` | PolicyResult list | Yes |
| `disqualifying_policy_ids` | String list | Yes |
| `unresolved_policy_ids` | String list | Yes |
| `safety_limitations` | String list | Yes |

### PolicyResult

| Field | Type | Required |
|---|---|---|
| `policy_id` | String | Yes |
| `result` | PASS / FAIL / UNKNOWN / NOT_APPLICABLE | Yes |
| `supporting_finding_ids` | String list | Yes |
| `explanation` | String | Yes |

Policy checks should be deterministic where structured evidence permits.

Missing evidence must not produce PASS.

## 4.6 Assessment Outcome

| Field | Type | Required |
|---|---|---|
| `decision_reasons` | String list | Yes |
| `recommended_next_actions` | Enum list | Yes |
| `remaining_questions` | String list | Yes |
| `assessment_version` | String | Yes |

Proposed next actions:

- `REQUEST_WEATHER_EVIDENCE`
- `REQUEST_OCEAN_EVIDENCE`
- `CHECK_ADVISORIES`
- `INVESTIGATE_ALTERNATIVE_SOURCE`
- `REQUEST_USER_CLARIFICATION`
- `CONSIDER_ALTERNATIVE_BEACH`
- `READY_FOR_COMPARISON`
- `NO_FURTHER_INVESTIGATION`

These values describe possible Coordinator actions. They do not independently authorize tool execution.

## 4.7 Validation Rules

**CA-001:** Every assessment must reference a supported Beach Catalog record.

**CA-002:** Every assessment must specify its activity and time window.

**CA-003:** Eligibility, suitability, and evidence quality must be represented independently.

**CA-004:** An ELIGIBLE candidate must have SUFFICIENT evidence quality.

**CA-005:** Disqualifying safety-policy failures require EXCLUDED status.

**CA-006:** Failed explicit hard constraints require EXCLUDED status.

**CA-007:** Unknown hard-constraint results shall not be treated as passing.

**CA-008:** Unsupported beach/activity combinations require UNSUPPORTED status.

**CA-009:** Material evidence conflicts must be represented and handled according to policy.

**CA-010:** Rejected findings cannot contribute positive evidence.

**CA-011:** Soft preferences cannot override safety or eligibility rules.

**CA-012:** Assessments must contain explanations supporting eligibility decisions.

**CA-013:** Further investigation must respect Coordinator execution limits.

**CA-014:** NEEDS_INVESTIGATION, EXCLUDED, and UNSUPPORTED candidates cannot enter the recommendation list.

**CA-015:** UNDETERMINED suitability cannot qualify as ELIGIBLE.

**CA-016:** UNFAVORABLE suitability cannot qualify as ELIGIBLE.

## 4.8 Candidate Comparison

Only ELIGIBLE candidates may enter the recommendation comparison.

Candidates are compared qualitatively using:

1. Environmental suitability.
2. Evidence quality and limitations.
3. User preferences.
4. Geographic proximity preference.

The Coordinator shall not invent numerical suitability scores or arbitrary weighted rankings.

Comparable candidates may be presented as similarly suitable.

The default response contains up to three recommendations. Fewer are returned when fewer eligible candidates exist.

MIXED candidates may be recommended only when explicitly permitted by the Safety Policy.

## 4.9 Open Decisions

- Minimum evidence required for eligibility.
- Activity-specific suitability criteria.
- Conditions permitting MIXED recommendations.
- Handling unresolved constraints when investigation limits are reached.
- Rules determining material evidence conflicts.
- Geographic preference matching.
- Reassessment rules after new evidence.
- Final policy and constraint identifiers.
- Ranking tie-breaking behavior.

---

# 5. Investigation State Schema

## 5.1 Purpose

Investigation State is the shared working state maintained during an investigation.

The Coordinator owns the investigation and manages its current request, candidates, evidence, assessments, outstanding questions, and execution limits.

Weather and Ocean agents return structured findings through approved interfaces rather than independently modifying investigation state.

Investigation State represents current information. Investigation Trace represents historical actions and decisions.

## 5.2 InvestigationState

### Identity and Lifecycle

| Field | Type | Required |
|---|---|---|
| `investigation_id` | String | Yes |
| `session_id` | String | Yes |
| `schema_version` | String | Yes |
| `created_at` | Timestamp | Yes |
| `updated_at` | Timestamp | Yes |
| `status` | Enum | Yes |
| `request_revision` | Integer | Yes |

### Investigation Status

- `INITIALIZING`
- `INVESTIGATING`
- `EVALUATING`
- `AWAITING_CLARIFICATION`
- `COMPLETED`
- `ABSTAINED`
- `FAILED`

COMPLETED, ABSTAINED, and FAILED are terminal states.

Only the Coordinator or trusted orchestration components may transition the overall investigation status.

## 5.3 Normalized User Request

| Field | Type | Required | Description |
|---|---|---|---|
| `original_request` | String | Yes | Original user text |
| `activity` | Enum | Conditional | SWIMMING / SNORKELING / SUP |
| `target_date` | Date | Conditional | Requested date |
| `target_time_window` | Time range | Conditional | Requested time |
| `preferred_area` | String | No | Geographic preference |
| `experience_level` | Enum | No | BEGINNER / INTERMEDIATE / ADVANCED / UNKNOWN |
| `hard_constraints` | Constraint list | Yes | Mandatory requirements |
| `soft_preferences` | Preference list | Yes | Nonmandatory preferences |
| `clarification_needed` | Boolean | Yes | Material ambiguity exists |
| `clarification_questions` | String list | Yes | Questions for the user |

The normalized request must distinguish explicit user-provided values from assumptions or defaults.

Required information may remain unknown while clarification is pending.

A recommendation must not be produced when material unresolved ambiguity prevents a defensible assessment.

Driving-time estimation is outside MVP scope.

## 5.4 Candidate Management

| Field | Type | Required |
|---|---|---|
| `candidate_beach_ids` | String list | Yes |
| `assessments` | CandidateAssessment list | Yes |
| `investigated_beach_ids` | String list | Yes |
| `remaining_candidate_ids` | String list | Yes |

The Coordinator determines candidate selection and investigation order.

When new evidence requires reassessment, prior material decisions must remain recoverable from the Investigation Trace.

## 5.5 Environmental Evidence

| Field | Type | Required |
|---|---|---|
| `weather_findings` | EnvironmentalFinding list | Yes |
| `ocean_findings` | EnvironmentalFinding list | Yes |
| `pending_evidence_requests` | EvidenceRequest list | Yes |
| `unresolved_evidence_issues` | EvidenceIssue list | Yes |

Independent findings must be preserved without silent replacement.

### EvidenceRequest

| Field | Type | Required |
|---|---|---|
| `request_id` | String | Yes |
| `agent_type` | WEATHER / OCEAN | Yes |
| `candidate_beach_ids` | String list | Yes |
| `target_time_window` | Time range | Yes |
| `request_status` | PENDING / COMPLETED / FAILED / CANCELLED | Yes |

### EvidenceIssue

| Field | Type | Required |
|---|---|---|
| `issue_id` | String | Yes |
| `issue_type` | MISSING / STALE / CONFLICTING / COVERAGE_MISMATCH / INVALID | Yes |
| `finding_ids` | String list | Yes |
| `affected_beach_ids` | String list | Yes |
| `description` | String | Yes |
| `resolved` | Boolean | Yes |

## 5.6 Investigation Control

| Field | Type | Required |
|---|---|---|
| `iteration_count` | Integer | Yes |
| `max_iterations` | Integer | Yes |
| `tool_call_count` | Integer | Yes |
| `max_tool_calls` | Integer | Yes |
| `retry_count` | Integer | Yes |
| `max_retries` | Integer | Yes |
| `deadline_at` | Timestamp | Conditional |
| `remaining_actions` | Action list | Yes |

Execution limits must be enforced by orchestration components rather than relying on the LLM to stop voluntarily.

Numerical limits remain open until architecture and baseline evaluation work.

## 5.7 Errors and Recovery

| Field | Type | Required |
|---|---|---|
| `active_errors` | ErrorReference list | Yes |
| `recovery_actions` | Action list | Yes |
| `fallback_attempted` | Boolean | Yes |

Technical errors must be distinguished from environmental conclusions.

Provider failures may lead to fallback, continued investigation using sufficient independent evidence, or explained abstention.

## 5.8 Final Outcome

| Field | Type | Required |
|---|---|---|
| `outcome` | RECOMMENDATIONS / NO_RECOMMENDATION / ERROR | Conditional |
| `result_id` | String | Conditional |
| `completion_reason` | String | Conditional |

An intentional abstention is a valid investigation result.

It is distinct from an unrecoverable technical failure.

## 5.9 State Ownership and Validation Rules

**IS-001:** The Coordinator or trusted orchestration components own investigation state updates.

**IS-002:** Specialist agents return structured findings and cannot independently change overall investigation state.

**IS-003:** Independent evidence must be accumulated without silent replacement.

**IS-004:** Referenced findings, assessments, and candidates must have valid identifiers.

**IS-005:** State updates must preserve schema version and request-revision consistency.

**IS-006:** Execution limits must be enforced independently of model instructions.

**IS-007:** Every investigation must terminate with recommendations, explained abstention, or recorded technical failure.

**IS-008:** Material changes to user constraints must trigger reevaluation of affected assessments.

**IS-009:** Retrieval success does not imply evidence validation success.

**IS-010:** Material state changes must produce corresponding trace events.

## 5.10 Runtime Context Management

The complete logical state need not be supplied to the Coordinator's LLM on every step.

The orchestration layer may maintain full structured records while passing only relevant findings, references, limitations, and unresolved questions to the model.

This reduces context usage without discarding necessary evidence or auditability.

## 5.11 Open Decisions

- Exact state-transition rules.
- Maximum iterations, tool calls, and retries.
- Parallel versus conditional specialist execution.
- Reconciliation of pending tool requests.
- Request revision versus new investigation behavior.
- CLI session persistence and expiration.
- Assessment invalidation and replacement.
- Cancellation and interruption.
- Final action and error enumerations.

---

# 6. Recommendation Result Schema

## 6.1 Purpose

Recommendation Result is the validated structured output of an investigation.

The Coordinator produces the result. The CLI renders its contents into readable recommendations, warnings, limitations, and source references.

Recommendation Result is not simply an unrestricted block of generated text.

The system shall distinguish successful recommendations, intentional abstention, and technical failure.

## 6.2 RecommendationResult

### Identity and Context

| Field | Type | Required |
|---|---|---|
| `result_id` | String | Yes |
| `investigation_id` | String | Yes |
| `request_revision` | Integer | Yes |
| `schema_version` | String | Yes |
| `generated_at` | Timestamp | Yes |
| `activity` | Enum | Yes |
| `target_time_window` | Time range | Yes |
| `outcome` | Enum | Yes |

Allowed outcomes:

- `RECOMMENDATIONS`
- `NO_RECOMMENDATION`
- `ERROR`

### Outcome Summary

| Field | Type | Required |
|---|---|---|
| `summary` | String | Yes |
| `recommendations` | Recommendation list | Yes |
| `general_warnings` | String list | Yes |
| `general_limitations` | String list | Yes |
| `next_step_suggestions` | String list | No |

RECOMMENDATIONS requires one to three eligible recommendations.

NO_RECOMMENDATION and ERROR contain no recommendations.

## 6.3 Recommendation

### Identity

| Field | Type | Required |
|---|---|---|
| `recommendation_id` | String | Yes |
| `beach_id` | String | Yes |
| `assessment_id` | String | Yes |
| `rank` | Integer | Conditional |
| `display_name` | String | Yes |

The rank is a presentation order only when a defensible distinction exists.

Comparable recommendations may be presented as similarly suitable.

### Environmental Assessment

| Field | Type | Required |
|---|---|---|
| `environmental_suitability` | FAVORABLE / MIXED | Yes |
| `evidence_quality` | SUFFICIENT | Yes |
| `recommended_time_window` | Time range | Yes |
| `supporting_finding_ids` | String list | Yes |
| `advisory_references` | String list | Yes |

MIXED is permitted only under explicitly documented Safety Policy criteria.

The recommended time window must be supported by the underlying evidence.

### Explanation

| Field | Type | Required |
|---|---|---|
| `recommendation_reason` | String | Yes |
| `environmental_summary` | String | Yes |
| `preference_alignment` | String list | Yes |
| `warnings` | String list | Yes |
| `limitations` | String list | Yes |
| `source_references` | Source identifier list | Yes |

Material claims must be grounded in accepted findings or verified catalog attributes.

The response must distinguish observations, forecasts, and environmental interpretations.

## 6.4 No-Recommendation Details

| Field | Type | Required |
|---|---|---|
| `no_recommendation_reason` | Enum | Conditional |
| `explanation` | String | Conditional |
| `affected_beach_ids` | String list | No |
| `unresolved_issues` | String list | No |
| `suggested_alternatives` | String list | No |

Proposed reasons:

- `NO_ELIGIBLE_CANDIDATES`
- `INSUFFICIENT_EVIDENCE`
- `CONFLICTING_EVIDENCE`
- `APPLICABLE_HAZARDS`
- `UNRESOLVED_CONSTRAINTS`
- `INVESTIGATION_LIMIT_REACHED`

Suggested alternatives must not be presented as already verified unless they have been evaluated.

## 6.5 Technical Error Details

| Field | Type | Required |
|---|---|---|
| `error_code` | String | Conditional |
| `error_summary` | String | Conditional |
| `recoverable` | Boolean | Conditional |

Internal secrets or sensitive debugging details must not be shown in CLI responses.

## 6.6 Source Presentation

The CLI should display enough source information to support meaningful verification, including:

- Publisher or provider.
- Recognizable source name.
- Relevant observation or forecast period.
- Geographic coverage when material.
- Link or document reference when available.

Source metadata must derive from Environmental Findings or the Beach Catalog.

## 6.7 Validation Rules

**RR-001:** Each result must reference a valid investigation and request revision.

**RR-002:** Each result must declare a supported outcome.

**RR-003:** RECOMMENDATIONS must contain one to three recommendations.

**RR-004:** NO_RECOMMENDATION and ERROR must contain no recommendations.

**RR-005:** Every recommendation must reference an ELIGIBLE assessment.

**RR-006:** Every recommendation must have SUFFICIENT evidence quality.

**RR-007:** Recommended candidates must have FAVORABLE or explicitly policy-permitted MIXED suitability.

**RR-008:** Recommendations must satisfy applicable hard user constraints.

**RR-009:** Recommendations must not violate disqualifying safety policies.

**RR-010:** Material environmental claims must be grounded in accepted evidence or verified catalog information.

**RR-011:** Recommended time periods must be supported by evidence validity windows.

**RR-012:** Regional and offshore findings must not be misrepresented as direct beach observations.

**RR-013:** Applicable relevant advisories must be disclosed and handled according to policy.

**RR-014:** Unsuitable candidates shall not be added to meet the maximum recommendation count.

**RR-015:** NO_RECOMMENDATION must include a meaningful explanation.

**RR-016:** Technical failures must not be presented as environmental suitability conclusions.

**RR-017:** Recommendations outside the user's preferred geographic area should explain the reason for that choice.

**RR-018:** Ranking must reflect documented comparison criteria; defensible ties are permitted.

**RR-019:** Recommendation Result must pass validation before presentation as recommendations.

## 6.8 CLI Presentation

A successful CLI response should include:

1. Activity and requested time period.
2. Up to three supported recommendations.
3. Reasons for selecting each beach.
4. Relevant environmental evidence.
5. Warnings, advisories, and limitations.
6. Source references.

Technical schema identifiers and internal policy details need not appear in the default response.

NO_RECOMMENDATION and ERROR must produce appropriate explanations rather than an empty recommendation list.

## 6.9 Open Decisions

- Policy for MIXED candidate recommendations.
- Detailed ranking and tie presentation.
- Required environmental detail in CLI output.
- Minimum visible source attribution.
- Optional expanded evidence display.
- Final abstention and error categories.
- Explicit advice to recheck conditions before entering the water.

---

# 7. Investigation Trace Schema

## 7.1 Purpose

Investigation Trace preserves the ordered history of significant events during an investigation.

It supports debugging, evaluation, and verification of agent behavior, evidence validation, safety-policy enforcement, and workflow limits.

The MVP uses lightweight structured JSON event logging.

The trace records observable actions and decisions, not private model reasoning.

## 7.2 InvestigationTrace

### Trace Metadata

| Field | Type | Required |
|---|---|---|
| `trace_id` | String | Yes |
| `investigation_id` | String | Yes |
| `schema_version` | String | Yes |
| `started_at` | Timestamp | Yes |
| `completed_at` | Timestamp | Conditional |
| `final_status` | COMPLETED / ABSTAINED / FAILED | Conditional |
| `configuration_version` | String | Yes |
| `policy_version` | String | Yes |
| `model_identifier` | String | Conditional |
| `events` | TraceEvent list | Yes |

Partial traces may remain after interrupted execution.

Missing events must not be fabricated.

## 7.3 TraceEvent

| Field | Type | Required |
|---|---|---|
| `event_id` | String | Yes |
| `trace_id` | String | Yes |
| `sequence_number` | Integer | Yes |
| `timestamp` | Timestamp | Yes |
| `event_type` | Enum | Yes |
| `actor` | Enum | Yes |
| `request_revision` | Integer | Yes |
| `related_ids` | String list | No |
| `details` | Structured object | Yes |

Allowed actors:

- `COORDINATOR`
- `WEATHER`
- `OCEAN`
- `ORCHESTRATOR`
- `VALIDATOR`
- `CLI`

Sequence numbers provide ordering within a trace without assuming that parallel operations began or completed sequentially.

## 7.4 Event Types

### Request Events

- `REQUEST_RECEIVED`
- `REQUEST_NORMALIZED`
- `REQUEST_REVISED`
- `CLARIFICATION_REQUESTED`

### Agent and Tool Events

- `AGENT_STARTED`
- `AGENT_COMPLETED`
- `TOOL_CALLED`
- `TOOL_COMPLETED`
- `TOOL_FAILED`

### Evidence Events

- `EVIDENCE_RECEIVED`
- `EVIDENCE_VALIDATED`
- `EVIDENCE_REJECTED`
- `EVIDENCE_CONFLICT_DETECTED`

### Candidate and Safety Events

- `CANDIDATE_ASSESSED`
- `POLICY_EVALUATED`
- `CANDIDATE_EXCLUDED`
- `CANDIDATE_ELIGIBLE`

### Workflow Events

- `RETRY_INITIATED`
- `FALLBACK_INITIATED`
- `INVESTIGATION_LIMIT_REACHED`
- `INVESTIGATION_COMPLETED`
- `INVESTIGATION_ABSTAINED`
- `INVESTIGATION_FAILED`

The final event vocabulary may be refined in the Agent and Tool Contracts specification.

## 7.5 Tool Execution Details

| Field | Type | Required |
|---|---|---|
| `tool_call_id` | String | Yes |
| `tool_name` | String | Yes |
| `agent_type` | Enum | Yes |
| `arguments_summary` | Structured object | Conditional |
| `execution_status` | SUCCESS / PARTIAL / ERROR / TIMEOUT | Conditional |
| `duration_ms` | Integer | Conditional |
| `result_reference_ids` | String list | No |
| `error_code` | String | Conditional |

Tool calls and outcomes must be correlated using `tool_call_id`.

Retries must have distinct call identifiers.

The trace should reference stored findings instead of duplicating full external responses.

## 7.6 Evidence Validation Events

| Field | Type | Required |
|---|---|---|
| `finding_id` | String | Yes |
| `validation_status` | ACCEPTED / LIMITED / REJECTED | Yes |
| `validation_rule_ids` | String list | Yes |
| `validation_reasons` | String list | Yes |
| `source_id` | String | Yes |

Validation events must preserve the reasons evidence was accepted, limited, or rejected.

Examples include:

- Stale information.
- Geographic mismatch.
- Missing required measurements.
- Invalid units.
- Material source conflicts.
- Unverified provenance.

## 7.7 Candidate and Policy Events

| Field | Type | Required |
|---|---|---|
| `assessment_id` | String | Yes |
| `beach_id` | String | Yes |
| `activity` | Enum | Yes |
| `eligibility` | Enum | Yes |
| `environmental_suitability` | Enum | Yes |
| `evidence_quality` | Enum | Yes |
| `applied_policy_ids` | String list | Yes |
| `decision_reasons` | String list | Yes |

Material reassessments must produce new trace events.

Previously recorded events must not be silently overwritten.

## 7.8 Investigation Completion

| Field | Type | Required |
|---|---|---|
| `final_status` | COMPLETED / ABSTAINED / FAILED | Yes |
| `result_id` | String | Conditional |
| `recommended_beach_ids` | String list | Yes |
| `completion_reason` | String | Yes |
| `total_iterations` | Integer | Yes |
| `total_tool_calls` | Integer | Yes |
| `total_retries` | Integer | Yes |
| `total_duration_ms` | Integer | Yes |

The final trace status must agree with Investigation State and Recommendation Result.

A completed investigation without recommendations is ABSTAINED, not FAILED, when the workflow completed its intended evaluation successfully.

## 7.9 Privacy and Data Handling

The MVP shall:

- Exclude credentials, API keys, access tokens, and secrets.
- Avoid capturing private chain-of-thought.
- Record sanitized tool parameters.
- Avoid retaining full conversations when normalized information is sufficient.
- Use identifiers to correlate records.
- Prefer synthetic user profiles for evaluation.
- Apply documented local trace-retention rules.
- Avoid unnecessary personal data collection.
- Keep logging local unless an approved requirement introduces external storage.

Enterprise monitoring infrastructure is outside MVP scope.

## 7.10 Evaluation Support

Traces must support evaluation of:

- Safety-policy compliance.
- Source freshness and geographic validation.
- Missing and conflicting evidence handling.
- Tool errors, retries, and fallback behavior.
- Investigation limit compliance.
- Recommendation and abstention correctness.
- Tool usage and execution latency.

Synthetic tests must define expected outcomes.

A plausible natural-language answer does not count as a passing test if documented requirements were violated.

A trace alone is not a complete reproducible fixture. Reproduction also requires the relevant environmental input data and configuration.

## 7.11 Validation Rules

**IT-001:** Every trace must reference a valid investigation.

**IT-002:** Event identifiers must be unique and sequence numbers monotonically increasing.

**IT-003:** Timestamps must be unambiguous and consistent with event occurrence.

**IT-004:** Tool outcomes must reference initiating tool calls.

**IT-005:** Evidence validation events must reference valid findings.

**IT-006:** Candidate events must reference valid beach and assessment identifiers.

**IT-007:** Material policy decisions must identify the rules involved.

**IT-008:** Tool-call, retry, and iteration counts must be observable.

**IT-009:** Final trace status must agree with state and result records.

**IT-010:** Trace events must exclude secrets and unnecessary personal data.

**IT-011:** Private model chain-of-thought shall not be logged.

**IT-012:** Partial traces should be retained after unexpected termination when technically feasible.

**IT-013:** Historical events shall not be silently overwritten.

**IT-014:** Trace events must conform to their documented structures.

## 7.12 Open Decisions

- Exact JSON serialization.
- Local storage organization.
- Trace retention period.
- Whether logging is configurable.
- Handling corrupted or incomplete trace files.
- Final event and error-code vocabularies.
- Optional token usage and cost metrics.
- Required deterministic replay capabilities.
- Representation of parallel execution.
- Request-text and tool-argument sanitization rules.

---

# 8. Cross-Schema Relationships

## 8.1 Primary Relationships

| Source | Target | Relationship |
|---|---|---|
| Investigation State | Beach Catalog | References candidate beach IDs |
| Investigation State | Environmental Finding | Accumulates investigation evidence |
| Investigation State | Candidate Assessment | Maintains current candidate evaluations |
| Environmental Finding | Beach Catalog | Optional verified beach-specific relationship |
| Candidate Assessment | Environmental Finding | References supporting, conflicting, and rejected findings |
| Candidate Assessment | Beach Catalog | References one named beach |
| Recommendation Result | Candidate Assessment | References eligible assessments |
| Recommendation Result | Environmental Finding | References supporting environmental evidence |
| Investigation Trace | Investigation State | Records material state changes |
| Investigation Trace | Other schemas | References findings, assessments, policies, and results |

## 8.2 Information Lifecycle

**Request**

A natural-language request is normalized into activity, time, constraints, and preferences.

**Candidate Selection**

The Coordinator identifies supported beaches using the Beach Catalog.

**Environmental Investigation**

Weather and Ocean agents return Environmental Findings.

**Evidence Validation**

Retrieved findings are evaluated for freshness, geographic relevance, completeness, and consistency.

**Candidate Assessment**

Validated evidence is combined with catalog information, user constraints, and applicable safety policies.

**Recommendation Comparison**

Eligible candidates are compared qualitatively.

**Recommendation Result**

The Coordinator produces a structured, validated result containing up to three recommendations or an explained abstention.

**Investigation Trace**

Material events and decisions throughout the lifecycle are recorded.

---

# 9. Cross-Schema Invariants

The following rules apply across the complete data model.

**DS-001 — Valid References**

Relationships between investigations, beaches, findings, assessments, and results must use valid identifiers.

**DS-002 — Geographic Integrity**

No component may silently change the geographic meaning of external evidence.

**DS-003 — Temporal Integrity**

Observed, issued, retrieved, forecast, and recommended times must retain their distinct meanings.

**DS-004 — Evidence Preservation**

Missing, conflicting, and rejected evidence must remain identifiable.

**DS-005 — Safety Independence**

Model-generated explanations must not override deterministic eligibility and safety policies.

**DS-006 — Eligibility Requirement**

Only ELIGIBLE assessments with SUFFICIENT evidence and permitted environmental suitability may appear in recommendations.

**DS-007 — No Invented Precision**

The system shall not fabricate measurements, geographic specificity, confidence scores, or unsupported rankings.

**DS-008 — Bounded Operation**

All additional investigations, retries, and tool calls must operate within enforced limits.

**DS-009 — Outcome Consistency**

Investigation State, Recommendation Result, and Investigation Trace must represent compatible final outcomes.

**DS-010 — Explainability**

Every recommendation must retain sufficient supporting references and decision reasons to explain why it was selected.

**DS-011 — Scope Control**

Only approved Maui catalog locations and the three supported activities are eligible in the MVP.

**DS-012 — No Safety Guarantee**

Eligibility and suitability classifications represent evidence-supported recommendations, not guarantees of actual ocean safety.

---

# 10. Outstanding Design Dependencies

The six logical schemas are approved, but several implementation-critical requirements remain intentionally unresolved.

These will be addressed in subsequent specifications.

## 10.1 Data Sources and Coverage

- Approved weather and marine providers.
- Source access methods and applicable usage constraints.
- Required environmental fields and units.
- Freshness thresholds.
- Geographic applicability rules.
- Evidence requirements for individual activities.

## 10.2 Safety Policies

- Activity-specific hazard criteria.
- Mandatory advisory exclusions.
- Minimum acceptable evidence.
- Rules permitting or excluding MIXED suitability.
- Handling of conflicting and incomplete findings.
- Final abstention requirements.

## 10.3 Agent and Tool Contracts

- Approved tool inventory.
- Agent-specific tool permissions.
- Inputs, outputs, errors, and timeouts.
- Parallel investigation behavior.
- Retry and fallback rules.
- State update mechanisms.

## 10.4 Coordinator Workflow

- Allowed investigation state transitions.
- Numerical execution limits.
- Request revision behavior.
- Candidate reevaluation rules.
- Session persistence and expiration.
- Clarification behavior.

## 10.5 Presentation and Observability

- CLI output details.
- Source display requirements.
- Ranking ties and qualitative comparison.
- JSON serialization conventions.
- Trace retention and sanitization.
- Optional usage and cost metrics.

---

# 11. Specification Status

| Schema | Status |
|---|---|
| Beach Catalog | Approved — Logical Design |
| Environmental Finding | Approved — Logical Design |
| Candidate Assessment | Approved — Logical Design |
| Investigation State | Approved — Logical Design |
| Recommendation Result | Approved — Logical Design |
| Investigation Trace | Approved — Logical Design |

The schemas are approved as logical requirements.

Open decisions remain explicitly unresolved and must not be filled through unsupported assumptions during implementation.

**No application code is authorized by approval of this document.**

## 12. Next Specifications

The logical data schemas provide the foundation for the remaining engineering documents:

- `04-agent-tool-contracts.md`
- `05-safety-policies.md`
- `06-test-acceptance.md`
- `07-observability.md`

The next recommended task is to define Coordinator-to-specialist interfaces and approved tool boundaries in `04-agent-tool-contracts.md`.

---

**End of Data Schemas Specification v0.1**