# Hawaii Activity Forecaster
# Agent and Tool Contracts

**Version:** 0.2 — Consolidated Draft  
**Status:** Coordinator-to-Specialist Contracts approved; external provider integrations pending final verification  
**Project:** CMU Agentic AI Systems Capstone  
**Document:** `docs/requirements/04-agent-tool-contracts.md`

**Dependencies:**
- `01-product-requirements.md`
- `02-system-architecture.md`
- `03-data-schemas.md`

---

# 1. Purpose and Scope

This specification defines how the Hawaii Activity Forecaster's agents communicate, retrieve environmental information, handle failures, and exchange structured evidence.

It covers:

1. Coordinator, Weather Agent, and Ocean Agent responsibilities.
2. Coordinator-to-Specialist request and response contracts.
3. External environmental data sources and retrieval contracts.
4. Agent permissions and investigation boundaries.
5. Evidence provenance, freshness, and geographic applicability.
6. Tool errors, retries, and fallback behavior.
7. Investigation State and Investigation Trace integration.
8. Contract validation and acceptance tests.

The specification is independent of programming language, LLM provider, and orchestration framework.

It does not authorize application code.

## 1.1 Established Architecture

The Forecaster uses three agent roles:

- **Coordinator:** Owns the investigation, delegates tasks, evaluates candidates, and generates recommendations.
- **Weather Agent:** Retrieves weather forecasts, conditions, and applicable weather advisories.
- **Ocean Agent:** Retrieves marine forecasts, swell, surf, water visibility, nearshore reports, and relevant water-quality advisories.

The architecture uses centralized supervision with bounded ReAct investigation.

Specialist agents provide evidence rather than independently producing eligibility decisions or final recommendations.

The Coordinator uses deterministic validation and safety policies to determine which candidates qualify for comparison.

## 1.2 Core Principles

- Delegate narrowly scoped tasks.
- Share a common specialist request/response structure.
- Preserve source information without inventing measurements.
- Separate successful retrieval from evidence validation.
- Maintain geographic and temporal integrity.
- Treat missing information as unknown, not favorable.
- Preserve materially conflicting findings.
- Enforce tool permissions and execution limits outside LLM instructions.
- Support partial results and meaningful abstention.
- Keep operational decisions traceable through structured events.

---

# 2. Agent Responsibilities

## 2.1 Coordinator

The Coordinator shall:

- Interpret and normalize the user's natural-language request.
- Select candidate beaches from the verified Beach Catalog.
- Establish activity, time window, hard constraints, and soft preferences.
- Determine environmental evidence requirements.
- Delegate scoped investigations to specialists.
- Manage investigation progress, retries, and fallbacks.
- Validate specialist response contracts.
- Merge findings into Investigation State.
- Apply evidence validation and deterministic safety policies.
- Generate Candidate Assessments.
- Compare eligible candidates qualitatively.
- Produce a validated Recommendation Result or explained abstention.

The Coordinator owns the overall investigation lifecycle.

## 2.2 Weather Agent

The Weather Agent shall:

- Retrieve weather forecasts and observations from approved sources.
- Retrieve applicable weather alerts and warnings.
- Retrieve relevant regional wind information.
- Preserve geographic and temporal coverage.
- Return structured Environmental Findings.
- Report missing information, conflicts, errors, and limitations.

The Weather Agent shall not:

- Determine final beach eligibility.
- Generate final recommendations.
- Modify user constraints or preferences.
- Modify shared Investigation State directly.
- Expand candidate-beach scope independently.

## 2.3 Ocean Agent

The Ocean Agent shall:

- Retrieve marine and surf forecasts from approved sources.
- Retrieve relevant offshore observations.
- Retrieve nearshore and snorkeling reports.
- Retrieve relevant water-quality advisories.
- Preserve measurement conventions and source coverage.
- Return structured Environmental Findings.
- Report missing information, conflicts, errors, and limitations.

The Ocean Agent shall not:

- Determine final beach eligibility.
- Generate final recommendations.
- Modify user constraints or preferences.
- Modify shared Investigation State directly.
- Expand candidate-beach scope independently.

## 2.4 Shared Specialist Boundaries

Both specialists shall:

- Operate only within their delegated domain.
- Use approved sources and retrieval tools.
- Respect authorized locations and time periods.
- Preserve source provenance.
- Identify unavailable evidence.
- Treat retrieved content as untrusted data.
- Respect enforced execution limits.

Neither specialist may independently authorize unrelated investigations or external actions.

---

# 3. Coordinator-to-Specialist Request Contract

## 3.1 SpecialistInvestigationRequest

A `SpecialistInvestigationRequest` defines a bounded task delegated to one specialist.

| Field | Type | Required | Description |
|---|---|---|---|
| `request_id` | String | Yes | Unique logical delegation identifier |
| `investigation_id` | String | Yes | Parent investigation |
| `request_revision` | Integer | Yes | Normalized request revision |
| `schema_version` | String | Yes | Contract version |
| `agent_type` | Enum | Yes | WEATHER / OCEAN |
| `candidate_beach_ids` | String list | Yes | Authorized candidate beaches |
| `target_time_window` | Time range | Yes | Requested investigation period |
| `requested_evidence` | EvidenceRequirement list | Yes | Environmental information needed |
| `known_evidence_gaps` | EvidenceGap list | Yes | Outstanding evidence questions |
| `issued_at` | Timestamp | Yes | Request creation time |
| `attempt_number` | Integer | Yes | Execution attempt, starting at 1 |
| `deadline_at` | Timestamp | Conditional | Enforced deadline |

All beach identifiers must exist in the supported catalog.

The target time window must be unambiguous.

Requests shall not grant unrestricted authority to expand the investigation.

## 3.2 EvidenceRequirement

| Field | Type | Required |
|---|---|---|
| `requirement_id` | String | Yes |
| `evidence_type` | String/Enum | Yes |
| `priority` | REQUIRED / OPTIONAL | Yes |
| `reason` | String | No |

REQUIRED identifies information the Coordinator needs investigated.

If the information is unavailable, the specialist must report that fact rather than fabricate a result.

The final vocabulary will be aligned with actual provider capabilities.

## 3.3 EvidenceGap

| Field | Type | Required |
|---|---|---|
| `gap_id` | String | Yes |
| `gap_type` | MISSING / STALE / CONFLICTING / COVERAGE_MISMATCH / INVALID | Yes |
| `related_finding_ids` | String list | Yes |
| `description` | String | Yes |

Evidence gaps focus subsequent investigations on unresolved questions.

They do not authorize arbitrary searching.

## 3.4 Request Validation Rules

**SRQ-001:** The request must reference an active investigation.

**SRQ-002:** Exactly one authorized specialist must be identified.

**SRQ-003:** Candidate IDs must exist and be within the authorized investigation scope.

**SRQ-004:** The target time window must be valid and unambiguous.

**SRQ-005:** Requested evidence must fall within the specialist's domain.

**SRQ-006:** Evidence requirements must use documented categories.

**SRQ-007:** Request revision must match the active investigation.

**SRQ-008:** Deadlines must be enforced by trusted orchestration components.

**SRQ-009:** Invalid requests must be rejected before external tool execution.

**SRQ-010:** Requests exceeding investigation limits must not be dispatched.

---

# 4. Coordinator-to-Specialist Response Contract

## 4.1 SpecialistInvestigationResponse

Both specialists use the same response structure.

| Field | Type | Required | Description |
|---|---|---|---|
| `response_id` | String | Yes | Unique response identifier |
| `request_id` | String | Yes | Originating request |
| `investigation_id` | String | Yes | Parent investigation |
| `request_revision` | Integer | Yes | Associated request revision |
| `schema_version` | String | Yes | Contract version |
| `agent_type` | Enum | Yes | WEATHER / OCEAN |
| `attempt_number` | Integer | Yes | Execution attempt |
| `status` | Enum | Yes | SUCCESS / PARTIAL / UNAVAILABLE / ERROR |
| `findings` | EnvironmentalFinding list | Yes | Structured findings |
| `unresolved_gaps` | EvidenceGap list | Yes | Missing information |
| `errors` | SpecialistError list | Yes | Structured errors |
| `started_at` | Timestamp | Yes | Execution start |
| `completed_at` | Timestamp | Yes | Execution completion |

Each response must reference its originating request and exact execution attempt.

## 4.2 Response Status

**SUCCESS:** Requested retrieval operations completed. This does not establish evidence validity or sufficiency.

**PARTIAL:** Some requested retrieval operations completed; unresolved work is identified.

**UNAVAILABLE:** Usable information could not be obtained from approved sources.

**ERROR:** Execution or contract failure prevented successful completion.

## 4.3 SpecialistError

| Field | Type | Required |
|---|---|---|
| `error_id` | String | Yes |
| `error_code` | String/Enum | Yes |
| `message` | String | Yes |
| `source_id` | String | Conditional |
| `tool_call_id` | String | Conditional |
| `retryable` | Boolean | Yes |

Proposed error categories:

- `SOURCE_UNAVAILABLE`
- `SOURCE_TIMEOUT`
- `SOURCE_RESPONSE_INVALID`
- `SOURCE_ACCESS_DENIED`
- `CONTRACT_VALIDATION_FAILED`
- `UNSUPPORTED_EVIDENCE_REQUEST`
- `EXECUTION_LIMIT_REACHED`
- `INTERNAL_ERROR`

A retryable error does not authorize a retry by itself.

## 4.4 Response Validation Rules

**SRS-001:** Every response must reference an originating request.

**SRS-002:** Investigation, specialist, request revision, and attempt must match.

**SRS-003:** Findings must conform to the Environmental Finding schema.

**SRS-004:** Findings must remain within the specialist's authorized domain.

**SRS-005:** Original geographic and temporal scope must be preserved.

**SRS-006:** Specialists must not return eligibility decisions or final recommendations.

**SRS-007:** Missing required evidence must be reported explicitly.

**SRS-008:** ERROR responses must contain a corresponding structured error.

**SRS-009:** PARTIAL responses must identify incomplete work.

**SRS-010:** Response contracts must be validated before state integration.

**SRS-011:** Outdated request revisions must not overwrite current assessments.

**SRS-012:** Duplicate responses must not create duplicate findings or assessments.

**SRS-013:** A valid response structure does not establish that its evidence is sufficient.

---

# 5. Geographic and Temporal Boundaries

## 5.1 Geographic Scope

The MVP supports approved beaches in South and West Maui.

Specialists may retrieve regional or offshore evidence relevant to those beaches without expanding the candidate list.

For example, the Ocean Agent may retrieve an offshore buoy observation to investigate conditions affecting South Maui.

That observation must remain identified as offshore evidence.

**SC-001:** Broader-area evidence may be retrieved for authorized candidates.

**SC-002:** Specialists may not independently add candidate beaches.

**SC-003:** Original source geographic coverage must be preserved.

**SC-004:** Interpretations must be distinguishable from source observations.

**SC-005:** Beach-level applicability is determined through documented validation rules.

## 5.2 Temporal Scope

Findings must distinguish:

- Observation time.
- Forecast issuance time.
- Forecast validity period.
- Retrieval time.
- Requested activity time.

**TM-001:** Source-provided temporal information must be preserved.

**TM-002:** Retrieval time must not replace observation time.

**TM-003:** Evidence outside the target period may be retained as context if clearly identified.

**TM-004:** Expired information must not be described as current.

**TM-005:** Evidence validation determines whether temporal coverage is acceptable.

---

# 6. External Environmental Providers

## 6.1 Provider Classification

External providers are classified as:

**Authoritative:** Government agencies publishing official warnings, advisories, or forecasts.

**Scientific:** Observational and research services providing environmental measurements or models.

**Supplemental:** Independent reporting services providing localized observations, summaries, or interpretations.

Classification helps determine the role of the evidence but does not automatically determine its validity.

Every finding remains subject to source-specific freshness, geographic, and completeness checks.

## 6.2 Provider Registry

| Source ID | Provider | Domain | Classification | Priority |
|---|---|---|---|---|
| `NWS_WEATHER` | National Weather Service | Weather forecasts | Authoritative | P0 |
| `NWS_ALERTS` | National Weather Service | Weather alerts | Authoritative | P0 |
| `NWS_MARINE` | NWS Honolulu | Marine and surf forecasts | Authoritative | P0 |
| `HI_DOH_CWB` | Hawaii DOH Clean Water Branch | Water-quality advisories | Authoritative | P0 |
| `SNORKEL_STORE` | The Snorkel Store | Daily local snorkel reports | Supplemental | P1 |
| `HWT_VISIBILITY` | HawaiiWeatherToday | Regional water visibility | Supplemental | P1 |
| `HWT_SURF` | HawaiiWeatherToday | Regional surf forecasts | Supplemental | P1 |
| `HWT_WIND` | HawaiiWeatherToday | Regional wind information | Supplemental | P1 |
| `HWT_NARRATIVE` | HawaiiWeatherToday | Daily weather narrative | Supplemental | P1 |
| `NDBC` | NOAA National Data Buoy Center | Offshore observations | Scientific / Government | P1 |

**Removed:** PacIOOS Maui SWAN wave model.

PacIOOS is outside MVP scope and shall not be included in the initial tool inventory.

Provider priorities indicate integration importance, not approval for unrestricted automated use.

## 6.3 Provider Activation Requirements

Before a provider is enabled for live investigations, the project must verify:

- Authorized retrieval endpoint or access method.
- Applicable usage and automated access permissions.
- Required request parameters.
- Geographic coverage.
- Publication and observation timestamps.
- Supported evidence types.
- Freshness and validation behavior.
- Structured failure handling.

Providers with unresolved access requirements may remain documented but inactive.

---

# 7. Common External Tool Contracts

## 7.1 EnvironmentalToolRequest

| Field | Type | Required | Description |
|---|---|---|---|
| `tool_call_id` | String | Yes | Unique tool invocation |
| `investigation_id` | String | Yes | Parent investigation |
| `source_id` | String | Yes | Approved provider |
| `agent_type` | WEATHER / OCEAN | Yes | Invoking specialist |
| `requested_evidence` | String list | Yes | Authorized evidence categories |
| `target_time_window` | Time range | Yes | Requested period |
| `geographic_scope` | Structured object | Yes | Coordinates, zones, or stations |
| `issued_at` | Timestamp | Yes | Invocation time |

Source-specific geographic identifiers must be validated.

A beach ID does not automatically represent a forecast grid, marine zone, or buoy station.

## 7.2 EnvironmentalToolResponse

| Field | Type | Required | Description |
|---|---|---|---|
| `tool_call_id` | String | Yes | Originating tool call |
| `source_id` | String | Yes | Provider identifier |
| `retrieval_status` | Enum | Yes | SUCCESS / PARTIAL / UNAVAILABLE / ERROR |
| `retrieved_at` | Timestamp | Yes | Retrieval completion |
| `source_reference` | String | Conditional | Source URL or document |
| `findings` | EnvironmentalFinding list | Yes | Structured findings |
| `missing_evidence` | String list | Yes | Unavailable information |
| `errors` | Structured error list | Yes | Retrieval failures |
| `duration_ms` | Integer | Yes | Execution duration |

Tool retrieval status and environmental evidence validation status remain independent.

---

# 8. Weather Agent — External Tools

## 8.1 WT-001 — NWS Weather Forecast

**Provider:** National Weather Service  
**Source ID:** `NWS_WEATHER`  
**Priority:** P0

**Purpose:** Retrieve forecasts relevant to supported Maui locations and requested times.

**Proposed API access:**

- `https://api.weather.gov/points/{lat},{lon}`
- NWS forecast resources returned from the point lookup.
- Hourly forecast resources when available.

**Relevant evidence:**

- Wind speed and direction.
- Forecast precipitation.
- General weather conditions.
- Forecast issue and validity times.
- Forecast geographic coverage.

**Requirements:**

- Preserve point/grid and zone coverage.
- Retain forecast validity periods.
- Distinguish point forecasts from broader-area forecasts.
- Report unavailable fields explicitly.
- Avoid presenting inland or higher-elevation forecasts as precise beach conditions.

## 8.2 WT-002 — NWS Weather Alerts

**Provider:** National Weather Service  
**Source ID:** `NWS_ALERTS`  
**Priority:** P0

**Purpose:** Retrieve applicable official weather warnings, watches, and advisories.

**Proposed API access:**

- `https://api.weather.gov/alerts/active`

**Relevant evidence:**

- Alert identifier and type.
- Issuing authority.
- Severity, when provided.
- Affected geography.
- Effective and expiration times.
- Original source reference.

The Weather Agent returns the advisory information.

The Coordinator and safety validation layer determine the advisory's effect on beach eligibility.

## 8.3 WT-003 — HawaiiWeatherToday Regional Winds

**Provider:** HawaiiWeatherToday  
**Source ID:** `HWT_WIND`  
**Priority:** P1

**Source:**

https://www.hawaiiweathertoday.com/windsurfing/

**Purpose:** Retrieve supplemental regional wind information for Maui.

**Relevant evidence:**

- Regional wind descriptions.
- Forecast wind strength and direction, when stated.
- Relevant marine or trade-wind context.
- Geographic applicability.
- Publication and forecast dates.

**Requirements:**

- Preserve original geographic descriptions.
- Identify whether information is forecast or observation.
- Preserve publication and validity dates.
- Detect missing or stale page updates.
- Avoid representing regional wind forecasts as beach-level measurements.

The page must be validated independently from other HawaiiWeatherToday pages.

## 8.4 WT-004 — Glenn's Daily Weather Narrative

**Provider:** HawaiiWeatherToday  
**Source ID:** `HWT_NARRATIVE`  
**Priority:** P1

**Source:**

https://www.hawaiiweathertoday.com/glenns-daily-weather-narrative/

**Purpose:** Retrieve supplemental narrative interpretation of Maui weather conditions and developing weather systems.

**Relevant evidence:**

- Weather-system descriptions.
- Wind and precipitation trends.
- Forecast changes.
- Broad geographic impacts.
- Relevant marine developments.

**Requirements:**

- Preserve the original publication timestamp.
- Distinguish narrative interpretation from measured observations.
- Retain relevant geographic and time references.
- Identify material uncertainty.
- Avoid converting narrative statements into precise measurements without source support.
- Avoid duplicate counting of underlying NWS forecasts as independent corroboration.

Where the narrative contains ocean-specific commentary, the Weather Agent may retain the relevant context, but structured ocean evidence remains the Ocean Agent's responsibility.

---

# 9. Ocean Agent — External Tools

## 9.1 OT-001 — NWS Marine and Surf Forecasts

**Provider:** NWS Honolulu  
**Source ID:** `NWS_MARINE`  
**Priority:** P0

**Purpose:** Retrieve official marine forecasts, surf conditions, and marine advisories.

**Relevant evidence:**

- Marine wind and sea forecasts.
- Surf forecasts.
- Swell and wave descriptions.
- Marine warnings and advisories.
- Forecast validity and geographic coverage.

**Relevant marine zones may include:**

- `PHZ118` — Maui County Leeward Waters.
- `PHZ119` — Māʻalaea Bay.
- `PHZ117` — Maui County Windward Waters.
- `PHZ120` — Pailolo Channel.

Exact zone applicability must be established through verified geographic mappings.

**Requirements:**

- Preserve marine zone identifiers.
- Distinguish forecast-zone data from beach-specific observations.
- Retain issuance and applicability periods.
- Preserve advisory terminology.
- Identify geographic limitations.

Exact product retrieval endpoints require final verification.

## 9.2 OT-002 — NOAA NDBC Observations

**Provider:** NOAA National Data Buoy Center  
**Source ID:** `NDBC`  
**Priority:** P1

**Purpose:** Retrieve observed offshore wave and meteorological conditions.

**Source:**

https://www.ndbc.noaa.gov/

**Relevant evidence:**

- Station identifier and geographic coordinates.
- Wave height.
- Wave period.
- Wave direction.
- Wind observations when available.
- Observation timestamp.

**Requirements:**

- Use an approved station registry.
- Verify station health and recent reporting.
- Preserve observed timestamps.
- Identify measurements as offshore observations.
- Never represent offshore measurements as confirmed beach conditions.
- Report unavailable measurements explicitly.

A station's published existence does not establish that it currently reports usable data.

## 9.3 OT-003 — Hawaii Water-Quality Advisories

**Provider:** Hawaii Department of Health, Clean Water Branch  
**Source ID:** `HI_DOH_CWB`  
**Priority:** P0

**Source:**

https://eha-cloud.doh.hawaii.gov/cwb/

**Purpose:** Retrieve official water-quality advisories relevant to supported beaches.

**Relevant evidence:**

- Advisory category.
- Issuing authority.
- Affected location.
- Issuance and effective dates.
- Advisory status.
- Original source reference.

**Requirements:**

- Preserve original advisory terminology.
- Identify the affected geographic area.
- Preserve advisory issue, update, and cancellation information when available.
- Distinguish advisories from general public-health guidance.
- Never treat failure to retrieve advisories as confirmation of safe water quality.

The exact machine-readable access method remains unresolved.

## 9.4 OT-004 — The Snorkel Store Daily Report

**Provider:** The Snorkel Store  
**Source ID:** `SNORKEL_STORE`  
**Priority:** P1

**Source:**

https://thesnorkelstore.com/maui-snorkeling-conditions-reports/

**Purpose:** Retrieve supplemental, locally informed snorkeling conditions.

**Publication schedule:** Typically around 8:00 a.m. Hawaii Standard Time each day. The website has also described a reporting time near 7:30 a.m. HST; actual publication timestamps must determine freshness.

**Relevant evidence:**

- Report publication date.
- Regional snorkeling assessments.
- Named beach observations when provided.
- Reported wave and wind conditions.
- Local hazards and warnings.
- Qualitative snorkeling suitability.
- Time-of-day observations or recommendations.

**Requirements:**

- Preserve report date and source attribution.
- Maintain the distinction between regional and individual-beach observations.
- Treat publisher scores as qualitative third-party assessments.
- Do not directly map publisher ratings into Forecaster suitability classifications.
- Preserve relevant cautions and environmental limitations.
- Verify whether the current day's report is available.
- Do not silently substitute a previous day's report as current.

**Temporal applicability:**

A report describing today's conditions may provide valuable same-day information.

It must not automatically be treated as a verified forecast for tomorrow morning.

Reports retrieved before the expected publication time require explicit handling of the possibility that the day's report has not yet been issued.

Automated retrieval and reuse permissions remain subject to verification.

## 9.5 OT-005 — HawaiiWeatherToday Water Visibility

**Provider:** HawaiiWeatherToday  
**Source ID:** `HWT_VISIBILITY`  
**Priority:** P1

**Source:**

https://www.hawaiiweathertoday.com/dive-and-snorkel/

**Purpose:** Retrieve supplemental visibility information relevant to snorkeling and swimming.

**Relevant evidence:**

- Regional underwater visibility descriptions.
- Qualitative conditions such as poor, marginal, or good visibility.
- Relevant wave descriptions.
- North, south, east, and west shore geographic references.
- Forecast or report time period.

**Requirements:**

- Preserve qualitative visibility categories as reported.
- Do not invent visibility distances in feet or meters.
- Retain original geographic coverage.
- Preserve publication and forecast dates.
- Distinguish visibility observations from forecasts.
- Identify uncertainty or limitations.

Visibility information covering an entire shore shall not automatically be treated as a direct observation at an individual beach.

## 9.6 OT-006 — HawaiiWeatherToday Surf Forecast

**Provider:** HawaiiWeatherToday  
**Source ID:** `HWT_SURF`  
**Priority:** P1

**Source:**

https://www.hawaiiweathertoday.com/surfing/

**Purpose:** Retrieve localized regional surf forecasts for Maui.

**Relevant evidence:**

- Surf-height ranges.
- Forecast period.
- Shore or regional location.
- Surf trends.
- Wave-height reporting convention.

The site uses **Hawaiian-style surf measurements**, commonly describing the back of a wave rather than the wave face.

This differs from many other reporting conventions.

**Required measurement metadata:**

| Field | Type | Example |
|---|---|---|
| `measurement_type` | Enum | SURF_HEIGHT |
| `value` | Number / Range | 2–3 |
| `unit` | String | ft |
| `measurement_convention` | Enum | HAWAIIAN_BACK |
| `coverage_description` | String | Kihei/Wailea |

Proposed measurement-convention values:

- `HAWAIIAN_BACK`
- `FACE`
- `UNKNOWN`

**Requirements:**

- Preserve the original reported height and measurement convention.
- Do not silently convert Hawaiian-style heights to wave-face measurements.
- Label any converted estimate explicitly as approximate.
- Document the conversion method when one is used.
- Retain source-provided geographic and temporal coverage.
- Do not present regional surf forecasts as direct beach measurements.

The approximate 2× face-height relationship described by the publisher is not a universally precise physical conversion.

For MVP, retaining original values and conventions is preferable to automatically normalizing all surf heights.

## 9.7 OT-007 — PacIOOS

**Status:** REMOVED FROM MVP

The PacIOOS Maui SWAN model will not be integrated in the initial Forecaster.

No PacIOOS retrieval tool, dataset dependency, or model-specific fallback is required.

The general Environmental Finding schema remains capable of supporting modeled ocean forecasts if the project's scope changes in the future.

---

# 10. Source Freshness and Publication Timing

Freshness must be evaluated at the level of an individual finding or source page.

Different sources may publish on different schedules.

Even pages belonging to the same website may have different publication times.

## 10.1 Requirements

**FR-001:** Every source retrieval must record `retrieved_at`.

**FR-002:** Source publication, issuance, observation, or forecast validity timestamps must be preserved when available.

**FR-003:** Retrieval time shall not substitute for the underlying information timestamp.

**FR-004:** Each HawaiiWeatherToday page must be validated independently.

**FR-005:** The freshness of Glenn's Daily Weather Narrative must not establish freshness for the Surf, Visibility, or Wind pages.

**FR-006:** The Snorkel Store report date must be verified independently of retrieval time.

**FR-007:** Previous-day reports must not be presented as current-day observations.

**FR-008:** Current-day reports must not automatically be treated as next-day forecasts.

**FR-009:** Published update schedules do not prove that data have actually been updated.

**FR-010:** Source-specific freshness thresholds shall be documented in the Safety Policy or source configuration before a finding may establish recommendation eligibility.

## 10.2 Publication Schedule Registry

| Source | Expected publication behavior | Validation |
|---|---|---|
| NWS forecasts | Provider-specific issuance/update schedule | Check actual issuance and validity |
| NWS alerts | Event-driven updates | Check active status and applicability |
| NDBC | Station-dependent observations | Check observation timestamp |
| Hawaii DOH | Event-driven advisories | Check issue and current status |
| Snorkel Store | Daily, around 8 a.m. HST | Verify actual report date/time |
| HWT Visibility | Page-specific | Verify page's date and applicability |
| HWT Surf | Page-specific | Verify page's date and applicability |
| HWT Wind | Page-specific | Verify page's date and applicability |
| HWT Narrative | Daily or page-specific | Verify actual publication timestamp |

The schedule describes expected behavior, not guaranteed availability.

---

# 11. Measurement Integrity and Qualitative Evidence

## 11.1 Measurement Conventions

Environmental measurements must retain their original meaning.

Wave and surf measurements can use different conventions.

For example:

- Offshore significant wave height.
- Breaking surf height.
- Hawaiian-style surf height.
- Wave-face height.

These are not interchangeable.

**MC-001:** Preserve source measurement definitions.

**MC-002:** Preserve reported units.

**MC-003:** Record surf-height convention when known.

**MC-004:** Unknown conventions must remain UNKNOWN.

**MC-005:** Conversions must use documented methods and retain original measurements.

**MC-006:** Approximate conversions must be labeled as estimates.

**MC-007:** Surf height and swell height must not be silently substituted for one another.

The Environmental Finding Measurement schema should be extended to support an optional `measurement_convention` field before implementation.

## 11.2 Qualitative Findings

Qualitative statements may include:

- Calm water.
- Marginal visibility.
- Choppy conditions.
- Strong currents.
- Increasing winds.
- Favorable morning conditions.

These statements may be useful evidence when accompanied by source, date, geographic scope, and limitations.

**QF-001:** Qualitative information must retain original source attribution.

**QF-002:** Qualitative categories must not be converted into unsupported numerical values.

**QF-003:** Publisher assessments must not automatically become Forecaster eligibility decisions.

**QF-004:** Narrative observations must be distinguishable from predictions and interpretations.

**QF-005:** Material source limitations must remain visible to the Coordinator.

---

# 12. Evidence Conflicts and Source Authority

Sources may disagree because of:

- Different observation periods.
- Different geographic coverage.
- Measurement conventions.
- Forecast versus observation differences.
- Qualitative interpretation.
- Update delays.

The Coordinator must preserve material discrepancies.

## 12.1 Source Priority

Applicable authoritative warnings and advisories take precedence for safety-policy enforcement.

However, provider classification does not automatically resolve every environmental measurement disagreement.

A local report may provide useful context alongside a broader forecast.

The system must not silently discard inconvenient evidence.

## 12.2 Independent Corroboration

Some supplemental reports may summarize or republish NWS information.

The Forecaster must not count the same underlying forecast as independent corroboration merely because it appears on multiple websites.

**CF-001:** Preserve original underlying source attribution where identifiable.

**CF-002:** Identify derivative or republished information when known.

**CF-003:** Do not count duplicate underlying forecasts as independent confirmation.

**CF-004:** Preserve material differences between sources.

**CF-005:** Investigate conflicts when authorized and within execution limits.

**CF-006:** Disclose or abstain when unresolved conflicts prevent adequate evidence.

---

# 13. Agent Tool Permissions

The MVP uses explicit source and tool allowlists.

| Tool | Weather Agent | Ocean Agent | Coordinator |
|---|---|---|---|
| NWS weather forecast | Allowed | No | Delegate |
| NWS weather alerts | Allowed | No | Delegate |
| HWT regional winds | Allowed | No | Delegate |
| HWT daily narrative | Allowed | No | Delegate |
| NWS marine and surf | No | Allowed | Delegate |
| NDBC buoy observations | No | Allowed | Delegate |
| Hawaii DOH advisories | No | Allowed | Delegate |
| Snorkel Store report | No | Allowed | Delegate |
| HWT visibility | No | Allowed | Delegate |
| HWT surf | No | Allowed | Delegate |
| Beach Catalog candidate selection | No | No | Allowed |
| Final eligibility evaluation | No | No | Allowed via validation |
| Final Recommendation Result | No | No | Allowed |

Specialists may receive scoped beach context needed for retrieval but cannot change the catalog or candidate list.

All tools are read-only.

No agent may book activities, purchase services, update calendars, or perform external real-world actions.

---

# 14. Retries, Fallbacks, and Partial Results

## 14.1 Request Identity

A logical specialist request has a stable `request_id`.

Retries of the same request retain that identifier and increment `attempt_number`.

Materially changed requests receive new identifiers.

Every external tool invocation receives its own `tool_call_id`.

This allows responses, retries, and trace events to be correlated.

## 14.2 Partial Results

Specialists may return PARTIAL results when only some requested information is available.

Available findings must be preserved.

Missing evidence must be identified explicitly.

Partial retrieval does not automatically establish sufficient evidence.

## 14.3 Fallback Rules

The Coordinator may authorize fallback to another approved source when:

- Required evidence is missing.
- A provider is unavailable.
- A source returns stale information.
- Material conflicts require further investigation.

Fallback must remain within the authorized investigation scope and execution limits.

No fallback may bypass provider permissions or safety validation.

## 14.4 Failure Behavior

A failed tool invocation does not necessarily make the entire investigation fail.

The Coordinator may:

- Use sufficient independent evidence already collected.
- Authorize another approved source.
- Investigate another supported candidate.
- Return an explained abstention.

The system must never fabricate data to compensate for a provider failure.

---

# 15. State Integration

The Coordinator is responsible for merging specialist responses into Investigation State.

## 15.1 Integration Sequence

1. Receive SpecialistInvestigationResponse.
2. Validate request and response correlation.
3. Validate schema structure.
4. Check authorized specialist domain.
5. Reject unauthorized or malformed material.
6. Preserve valid findings and source metadata.
7. Perform independent environmental evidence validation.
8. Update unresolved evidence issues.
9. Reevaluate affected candidates.
10. Determine next action or final outcome.

Response-contract validation and evidence validation are separate operations.

## 15.2 State Rules

**ST-001:** Specialists may not directly modify shared Investigation State.

**ST-002:** Trusted orchestration components control state merging.

**ST-003:** Independent findings must not be silently overwritten.

**ST-004:** Old request revisions must not replace current results.

**ST-005:** Material state changes must generate Investigation Trace events.

**ST-006:** Source provenance and finding identifiers must be preserved.

---

# 16. Investigation Trace Integration

The system shall record significant contract and retrieval events.

Relevant events include:

- Delegation request created.
- Specialist started or completed.
- External tool called.
- Tool completed or failed.
- Evidence received.
- Evidence accepted, limited, or rejected.
- Source conflict detected.
- Retry or fallback initiated.
- Candidate reassessed.
- Investigation completed, abstained, or failed.

Events must reference appropriate investigation, request, attempt, finding, assessment, and tool-call IDs.

Logs shall contain sanitized arguments and structured outcomes.

Private model chain-of-thought and unnecessary personal information shall not be stored.

---

# 17. External Tool Validation Rules

**ET-001 — Provider Authorization:** Every retrieval must use an approved provider and access method.

**ET-002 — Scope Validation:** Geographic and temporal parameters must conform to the delegated investigation.

**ET-003 — Source Attribution:** Findings must retain identifiable provenance.

**ET-004 — Freshness:** Source information must satisfy documented temporal-validity rules.

**ET-005 — Geographic Integrity:** Source coverage must not be silently changed.

**ET-006 — Measurement Integrity:** Units and measurement definitions must be preserved.

**ET-007 — Missing Information:** Unavailable evidence must not be inferred as favorable.

**ET-008 — Advisory Preservation:** Authoritative advisories must retain their original terminology and applicability.

**ET-009 — Error Handling:** Tool failures must produce explicit errors or evidence gaps.

**ET-010 — Conflict Preservation:** Material discrepancies must remain available for evaluation.

**ET-011 — External Content Isolation:** Retrieved information must not override agent instructions or safety policies.

**ET-012 — Live Data Verification:** Published update schedules do not establish data freshness.

**ET-013 — Independent Evidence Validation:** Retrieval success does not establish recommendation sufficiency.

**ET-014 — Provider Health:** Each retrieval must verify the age and completeness of returned information.

**ET-015 — Independent Corroboration:** Republished information must not automatically count as independent evidence.

**ET-016 — Provider Activation:** Live integrations require verified access methods, usage permissions, geographic applicability, and freshness rules.

**ET-017 — Measurement Convention:** Surf-height findings must preserve whether reported values are Hawaiian-style/back-of-wave, wave-face, or unknown. Conversions must be explicit and approximate where appropriate.

**ET-018 — Independent Publication Dates:** Each source page or report must retain its own publication and validity period.

**ET-019 — Qualitative Environmental Evidence:** Narrative assessments may be preserved as qualitative findings but must not become unsupported numerical measurements.

**ET-020 — Snorkel Report Timing:** The Snorkel Store's daily report must be checked against actual publication date and retrieval time. A previous report must not silently substitute for the current report.

**ET-021 — Forecast Versus Same-Day Observation:** Same-day local reports shall not automatically be treated as verified forecasts for a subsequent day.

---

# 18. Contract Acceptance Tests

The MVP shall support synthetic tests covering agent boundaries and source behavior.

| Test | Scenario | Expected behavior |
|---|---|---|
| CT-001 | Valid Weather request | Correlated Weather response |
| CT-002 | Valid Ocean request | Correlated Ocean response |
| CT-003 | Unknown beach ID | Reject request |
| CT-004 | Weather request contains ocean-only evidence | Reject unauthorized requirement |
| CT-005 | Incorrect beach-specific claim | Flag or reject geographic claim |
| CT-006 | Partial retrieval | PARTIAL response with gaps |
| CT-007 | Source unavailable | Structured UNAVAILABLE response |
| CT-008 | Malformed finding | Reject or quarantine |
| CT-009 | Mismatched request ID | Do not merge |
| CT-010 | Outdated request revision | Do not overwrite current assessments |
| CT-011 | Duplicate response | No duplicate state updates |
| CT-012 | Retry limit reached | No additional unauthorized execution |
| CT-013 | Regional source used for beach investigation | Preserve regional coverage |
| CT-014 | Specialist returns final recommendation | Reject unauthorized output |
| CT-015 | Successful retrieval of stale information | Reject as current evidence |
| CT-016 | Approved alternate source exists | Bounded fallback permitted |
| CT-017 | Prompt injection in retrieved content | Ignore unauthorized instructions |
| CT-018 | Hawaiian-style surf measurement | Preserve original convention and units |
| CT-019 | Surf report omits measurement convention | Mark convention UNKNOWN |
| CT-020 | Visibility report uses qualitative descriptions | Preserve qualitative categories |
| CT-021 | Snorkel Store report not yet published | Do not represent yesterday's report as current |
| CT-022 | Today's snorkel report used for tomorrow | Do not treat as confirmed next-day forecast |
| CT-023 | HWT narrative current but wind page stale | Validate each page independently |
| CT-024 | Same NWS forecast repeated by another site | Avoid false independent corroboration |
| CT-025 | Official advisory conflicts with favorable local report | Preserve advisory and apply safety policy |
| CT-026 | Water-quality portal unavailable | Do not claim water quality is safe |
| CT-027 | NDBC station has no recent observations | Report unavailable or stale observations |
| CT-028 | Provider not approved for automated access | Do not activate retrieval tool |

These tests verify contract compliance rather than the scientific accuracy of forecasts.

---

# 19. Open Decisions and Dependencies

The following requirements remain unresolved and must be addressed before implementing their corresponding integrations.

## 19.1 Provider Access

- Final NWS coordinate-specific API verification.
- Final marine and surf product endpoints.
- Approved NDBC station list.
- Hawaii DOH programmatic access method.
- Automated access and reuse permissions for The Snorkel Store.
- Automated access and reuse permissions for HawaiiWeatherToday.

## 19.2 Source Validation

- Source-specific freshness thresholds.
- Geographic applicability mappings.
- Minimum environmental evidence by activity.
- Classification of material source conflicts.
- Accepted surf-height conversion methods, if needed.
- Handling of unavailable publication timestamps.
- Duplicate-source detection criteria.

## 19.3 Execution Controls

- Maximum specialist execution time.
- Maximum tool calls and retries.
- Parallel execution behavior.
- Fallback source ordering.
- Cancellation and timeout behavior.

## 19.4 Contract Implementation

- Exact serialization formats.
- Final evidence-type enumeration.
- Error-code mapping.
- Tool adapter interfaces.
- Contract versioning and compatibility behavior.
- Validation implementation mechanisms.

The unresolved items must not be filled through unsupported assumptions during implementation.

---

# 20. Specification Status

## 20.1 Approved Design Decisions

- Three-agent centralized architecture.
- Coordinator ownership of investigation state.
- Common specialist request and response contracts.
- Scoped delegation.
- Structured specialist findings rather than recommendations.
- Request and retry identity separation.
- Two-stage response and evidence validation.
- Preservation of geographic and temporal coverage.
- Independent per-source freshness validation.
- Explicit handling of surf-height measurement conventions.
- Preservation of qualitative source reporting.
- No numerical suitability scores.
- Bounded investigation and fallback.
- Structured execution tracing.
- PacIOOS removed from MVP.

## 20.2 Provider Integration Status

| Provider | Status |
|---|---|
| NWS Weather | Primary candidate; endpoint integration pending |
| NWS Alerts | Primary candidate; endpoint integration pending |
| NWS Marine / Surf | Primary candidate; product access verification pending |
| Hawaii DOH | Primary candidate; programmatic access unresolved |
| NDBC | Scientific observation candidate; station registry pending |
| The Snorkel Store | Supplemental candidate; automated access permission pending |
| HawaiiWeatherToday | Supplemental candidate; automated access permission pending |
| PacIOOS | Removed from MVP |

## 20.3 Related Schema Change

The Environmental Finding Measurement schema in `03-data-schemas.md` should be amended to include:

`measurement_convention`: Optional Enum — `HAWAIIAN_BACK`, `FACE`, or `UNKNOWN`.

This field is particularly relevant to surf-height measurements. It does not replace the existing measurement type or units.

The field should be documented as a cross-specification update before implementation.

---

# 21. Next Specification

The next design document is:

`docs/requirements/05-safety-policies.md`

It shall define:

- Required evidence by supported activity.
- Applicable authoritative hazard rules.
- Geographic and temporal evidence sufficiency.
- Environmental suitability classifications.
- Permitted treatment of MIXED conditions.
- Conflicting evidence handling.
- Candidate exclusion rules.
- Clarification, fallback, and abstention requirements.

Safety policies shall use the evidence and interfaces defined here without depending on unverified provider behavior.

---

**End of Agent and Tool Contracts v0.2**

**Document approval status:** Architecture and specialist interfaces approved; external source candidates accepted for design, with operational integrations pending verification.

**No application code is authorized by this specification.**