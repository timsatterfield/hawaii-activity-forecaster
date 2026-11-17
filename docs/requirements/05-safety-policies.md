# Hawaii Activity Forecaster
# Safety Policies Specification

**Version:** 0.2 — Consolidated  
**Status:** Approved — Logical Design; implementation-specific rules pending  
**Project:** CMU Agentic AI Systems Capstone  
**Document:** `docs/requirements/05-safety-policies.md`

**Dependencies:**
- `01-product-requirements.md`
- `02-system-architecture.md`
- `03-data-schemas.md`
- `04-agent-tool-contracts.md`

---

# 1. Purpose and Scope

This document defines the safety policies governing environmental evidence validation, candidate eligibility, activity suitability, and recommendation decisions for the Hawaii Activity Forecaster.

The Forecaster supports recreational:

- Swimming
- Snorkeling
- Stand-up paddleboarding (SUP)

The MVP covers approved beaches in South and West Maui.

The application combines verified beach characteristics, weather and ocean evidence, user constraints, and applicable advisories to identify suitable activity locations.

Its purpose is to support informed decisions, not guarantee ocean safety or replace official warnings, lifeguard instructions, or on-site judgment.

Safety-critical requirements shall be enforced through documented, testable rules rather than unrestricted LLM reasoning.

## 1.1 Safety Architecture

The Forecaster uses a centralized Coordinator with Weather and Ocean specialist agents.

The specialists collect structured environmental evidence. They do not independently determine beach eligibility or produce final recommendations.

The Coordinator combines their findings with the Beach Catalog and normalized user request.

Trusted validation components enforce evidence, safety, and eligibility policies.

The Coordinator may investigate missing or conflicting information through bounded ReAct iterations.

Only candidates satisfying documented eligibility requirements may enter recommendation comparison.

## 1.2 Safety Design Principles

**SP-001 — Evidence Before Recommendation**

A location may be recommended only when sufficient acceptable evidence supports the requested activity and time.

**SP-002 — No Assumed Safety**

Missing information, absent reports, and failed retrievals shall not be interpreted as favorable conditions.

**SP-003 — Authoritative Hazard Handling**

Applicable official warnings, closures, restrictions, and advisories must be evaluated according to documented activity-specific policies.

**SP-004 — Geographic Integrity**

Regional or offshore evidence shall not be presented as direct beach-specific observations.

**SP-005 — Temporal Integrity**

Evidence must be relevant to the requested time period and satisfy source-specific freshness requirements.

**SP-006 — Conservative Conflict Handling**

Material unresolved contradictions affecting mandatory safety decisions must prevent eligibility.

**SP-007 — Safety Before Preferences**

Safety requirements and hard user constraints take precedence over geographic and other soft preferences.

**SP-008 — Bounded Investigation**

Additional investigations, retries, and tool calls must remain within enforced execution limits.

**SP-009 — Explainable Decisions**

Eligibility, exclusion, and abstention decisions must reference supporting evidence and applicable policies.

**SP-010 — Appropriate Abstention**

When sufficient evidence cannot be established, the system shall withhold unsupported recommendations and explain the limitations.

---

# 2. Policy Enforcement Model

Safety-policy evaluation must be performed through trusted validation components.

The Coordinator may determine what requires investigation, but it shall not override deterministic safety-policy outcomes.

## 2.1 Policy Results

Each applicable safety check shall produce a `PolicyResult` using the Candidate Assessment schema.

| Field | Type | Description |
|---|---|---|
| `policy_id` | String | Unique policy identifier |
| `result` | Enum | PASS / FAIL / UNKNOWN / NOT_APPLICABLE |
| `supporting_finding_ids` | String list | Evidence supporting the outcome |
| `explanation` | String | Reason for the result |

An UNKNOWN result must not be converted into PASS without additional acceptable evidence.

## 2.2 Policy Actions

Three policy actions govern candidate handling.

### EXCLUDE

A verified disqualifying hazard, applicable prohibition, or failed hard constraint prevents recommendation.

The associated Candidate Assessment shall be classified `EXCLUDED`.

### INVESTIGATE

Available evidence is incomplete, conflicting, or insufficient to resolve a mandatory safety question.

The Coordinator may request additional approved evidence within execution limits.

Until the issue is resolved, the candidate remains non-recommendable.

### DISCLOSE

A relevant, non-disqualifying hazard or limitation must be communicated to the user.

Disclosure does not independently establish suitability or eligibility.

## 2.3 Enforcement Rules

**HM-001:** EXCLUDE takes precedence over INVESTIGATE and DISCLOSE.

**HM-002:** An unresolved mandatory INVESTIGATE action prevents eligibility.

**HM-003:** DISCLOSE does not independently establish suitability.

**HM-004:** Unknown information must not be interpreted as favorable.

**HM-005:** Policy actions must identify supporting evidence and geographic and temporal applicability.

**HM-006:** Multiple applicable policy outcomes must be preserved independently.

**HM-007:** Additional investigation must respect execution limits.

**HM-008:** Unresolved mandatory checks remain non-recommendable after investigation limits are exhausted.

## 2.4 Policy Classifications

Policy checks may be:

- **Disqualifying:** A verified FAIL excludes the candidate.
- **Evidence-required:** An unresolved UNKNOWN prevents eligibility.
- **Disclosure:** Relevant information must appear in the final result without independently causing exclusion.

The detailed hazard matrix determines the appropriate classification for each scenario.

---

# 3. Environmental Evidence Validation

Every Environmental Finding must be validated independently of successful retrieval.

A successful API response or retrieved webpage does not establish that its information is usable for recommendation.

## 3.1 Validation Requirements

Before contributing to a Candidate Assessment, evidence must be checked for:

1. Approved provider and identifiable provenance.
2. Valid schema and retrieval result.
3. Temporal relevance and freshness.
4. Geographic applicability.
5. Measurement integrity.
6. Completeness for its intended purpose.
7. Material conflicts with other findings.

## 3.2 Validation States

Environmental Findings use the approved states:

| State | Meaning |
|---|---|
| `ACCEPTED` | Evidence passes the applicable validation requirements |
| `LIMITED` | Useful evidence exists, but important limitations remain |
| `REJECTED` | Evidence cannot support the intended assessment |

A LIMITED finding may provide context but shall not independently satisfy a mandatory requirement unless an explicit policy permits it.

A REJECTED finding cannot provide positive evidence for suitability.

## 3.3 Source Freshness

Freshness requirements vary by source.

An NWS forecast, offshore buoy observation, daily snorkeling report, and official water-quality advisory do not share a universal validity period.

Validation must distinguish:

- Publication time.
- Forecast issuance time.
- Forecast validity period.
- Observation time.
- Retrieval time.
- Advisory effective and expiration times.

Retrieval time alone does not establish freshness.

Exact provider-specific thresholds remain unresolved until source integration verification.

## 3.4 Geographic Applicability

Evidence may be:

- Beach-specific.
- Local-area.
- Regional.
- Offshore.

The system must preserve the original coverage reported by the source.

Regional and offshore information may support contextual interpretation but shall not automatically establish beach-specific conditions.

## 3.5 Measurement Integrity

Environmental measurements must preserve their original meaning and units.

In particular:

- Surf height and swell height are distinct measurements.
- Offshore significant wave height is not breaking surf height.
- Hawaiian-style surf height differs from wave-face height.
- Approximate conversions must be explicitly labeled.
- Unknown measurement conventions must remain unknown.

The Environmental Finding Measurement schema shall support an optional `measurement_convention` field with values including:

- `HAWAIIAN_BACK`
- `FACE`
- `UNKNOWN`

The original reported measurement must be retained.

---

# 4. Minimum Evidence Profiles

Evidence requirements are activity-specific.

The objective is to establish an acceptable evidentiary basis, not require a fixed number of sources or direct beach measurements for every category.

## 4.1 Activity Evidence Matrix

| Evidence category | Swimming | Snorkeling | SUP |
|---|---|---|---|
| Official applicable advisories | Mandatory | Mandatory | Mandatory |
| Surf and wave conditions | Mandatory | Mandatory | Mandatory |
| Wind conditions | Relevant | Relevant | Mandatory |
| Currents and persistent hazards | Mandatory | Mandatory | Mandatory |
| Water-quality advisory check | Mandatory | Mandatory | Mandatory |
| Underwater visibility | Optional | Important, not mandatory | Optional |
| Verified beach characteristics | Mandatory | Mandatory | Mandatory |

## 4.2 Mandatory Evidence

Mandatory means the system must establish an acceptable evidentiary basis for the relevant assessment.

This does not necessarily require a direct measurement at the named beach.

Depending on the evidence category, acceptable sources may include:

- An applicable authoritative forecast.
- A relevant official advisory.
- A local-area or regional forecast with established geographic applicability.
- A current local report with sufficient source and time information.
- A verified persistent beach characteristic.
- A verified official advisory-status response, when the source supports the conclusion.

The applicable policy determines whether a finding satisfies a mandatory category.

A mandatory category with unresolved evidence prevents eligibility.

## 4.3 Relevant Evidence

Relevant evidence should be investigated when it materially affects the requested activity.

Its absence does not automatically exclude the candidate unless an associated mandatory hazard question remains unresolved.

## 4.4 Optional Evidence

Optional evidence may improve comparison, explanation, or preference matching.

Its absence does not independently prevent eligibility.

## 4.5 Snorkeling Visibility

Underwater visibility is important for snorkeling suitability but is not mandatory for all snorkeling recommendations.

When visibility information is unavailable:

- Do not infer good visibility.
- Disclose the limitation when material.
- Evaluate mandatory hazards independently.
- Do not automatically exclude an otherwise eligible candidate.

Poor underwater visibility alone does not establish a disqualifying hazard.

---

# 5. Activity-Specific Hazard Matrix

The system shall evaluate hazards according to the requested activity, relevant beach characteristics, verified environmental evidence, and applicable warnings.

The presence of a hazard category does not automatically establish exclusion.

## 5.1 Summary Matrix

| Hazard scenario | Swimming | Snorkeling | SUP |
|---|---|---|---|
| Applicable official closure or prohibition | EXCLUDE | EXCLUDE | EXCLUDE |
| Verified disqualifying surf or shorebreak | EXCLUDE | EXCLUDE | EXCLUDE |
| Uncertain regional surf impact | INVESTIGATE | INVESTIGATE | INVESTIGATE |
| Non-disqualifying wave conditions | DISCLOSE | DISCLOSE | DISCLOSE |
| Verified dangerous currents | EXCLUDE | EXCLUDE | EXCLUDE |
| Uncertain applicable current hazard | INVESTIGATE | INVESTIGATE | INVESTIGATE |
| Verified dangerous offshore wind exposure | Policy-dependent | Policy-dependent | EXCLUDE |
| Uncertain wind-related hazard | INVESTIGATE | INVESTIGATE | INVESTIGATE |
| Non-disqualifying wind or chop | DISCLOSE | DISCLOSE | DISCLOSE |
| Applicable lightning or severe-weather hazard | EXCLUDE | EXCLUDE | EXCLUDE |
| Applicable water-contact avoidance advisory | EXCLUDE | EXCLUDE | EXCLUDE |
| Unknown mandatory advisory status | INVESTIGATE | INVESTIGATE | INVESTIGATE |
| Poor underwater visibility alone | DISCLOSE | DISCLOSE | DISCLOSE |
| Verified disqualifying beach characteristic | EXCLUDE | EXCLUDE | EXCLUDE |
| Material unresolved safety conflict | INVESTIGATE | INVESTIGATE | INVESTIGATE |

These outcomes describe scenarios after the relevant facts and applicability have been established.

Unresolved definitions of hazardous conditions must not be filled by arbitrary LLM-selected thresholds.

---

# 6. Surf and Shorebreak Policies

Surf and shorebreak conditions can differ significantly between Maui beaches sharing the same regional forecast.

The Forecaster must consider shoreline exposure, source geographic coverage, reported surf conditions, and activity-specific requirements.

## 6.1 Swimming

- EXCLUDE when validated evidence establishes dangerous surf or shorebreak affecting the intended swimming area.
- INVESTIGATE when elevated surf is reported but beach-level applicability is uncertain.
- DISCLOSE non-disqualifying wave conditions or entry limitations.

## 6.2 Snorkeling

- EXCLUDE when validated evidence establishes hazardous breaking waves or entry conditions affecting the snorkeling area.
- INVESTIGATE when regional surf may affect the beach but applicability remains uncertain.
- DISCLOSE relevant non-disqualifying surf conditions.

## 6.3 SUP

- EXCLUDE when validated evidence establishes hazardous launch, landing, or paddling-area surf conditions.
- INVESTIGATE when regional surf could affect access or paddling conditions but applicability is unresolved.
- DISCLOSE non-disqualifying launch and wave limitations.

## 6.4 Surf Policy Rules

**HM-SURF-001:** Hawaiian-style and wave-face measurements must not be directly compared without an approved convention-aware method.

**HM-SURF-002:** Offshore significant wave height must not be treated as breaking surf height.

**HM-SURF-003:** Regional surf forecasts must not automatically establish beach-specific conditions.

**HM-SURF-004:** Surf exclusions must use documented evidence and applicability criteria rather than arbitrary universal thresholds.

---

# 7. Swell and Ocean Exposure Policies

Swell height, direction, and period may help interpret conditions but do not independently establish beach suitability.

## 7.1 All Activities

- EXCLUDE when validated evidence and approved rules establish hazardous swell-related effects at the activity area.
- INVESTIGATE when swell exposure or its impact on a candidate is materially uncertain.
- DISCLOSE relevant non-disqualifying swell limitations.

## 7.2 Swell Policy Rules

**HM-SWELL-001:** Swell characteristics must retain their original measurement definitions and units.

**HM-SWELL-002:** Verified shoreline orientation and exposure may inform interpretation but shall not convert regional observations into direct beach measurements.

**HM-SWELL-003:** Swell direction alone cannot establish favorable or unfavorable conditions.

**HM-SWELL-004:** Precise nearshore wave height shall not be inferred without a verified method.

---

# 8. Wind Policies

Wind effects differ between swimming, snorkeling, and SUP.

The Forecaster must consider wind speed, gusts, direction, geographic coverage, shoreline orientation, and requested activity.

## 8.1 Swimming

- EXCLUDE when validated wind-related conditions establish a documented disqualifying hazard.
- INVESTIGATE when potentially hazardous wind effects remain uncertain.
- DISCLOSE non-disqualifying wind and chop.

## 8.2 Snorkeling

- EXCLUDE when validated wind-related conditions establish hazardous surface, entry, or return conditions.
- INVESTIGATE when wind effects may be hazardous but evidence is incomplete.
- DISCLOSE non-disqualifying chop or surface limitations.

## 8.3 SUP

- EXCLUDE when validated evidence establishes dangerous offshore winds or other disqualifying wind conditions.
- INVESTIGATE when offshore wind exposure, gusts, or wind direction cannot be adequately determined.
- DISCLOSE non-disqualifying wind limitations affecting paddling conditions.

## 8.4 Wind Policy Rules

**HM-WIND-001:** Wind direction must be interpreted relative to documented shoreline orientation.

**HM-WIND-002:** Offshore wind exposure requires explicit evaluation for SUP.

**HM-WIND-003:** Regional wind forecasts must retain their geographic limitations.

**HM-WIND-004:** Any numerical wind thresholds must be activity-specific and supported by documented rationale.

---

# 9. Current Policies

Currents may be localized and difficult to establish using broad forecasts.

The absence of a current report does not establish the absence of dangerous currents.

## 9.1 All Activities

- EXCLUDE when validated evidence establishes dangerous currents affecting the requested activity area.
- INVESTIGATE when a relevant current hazard is reported but its timing or applicability remains unresolved.
- DISCLOSE documented current hazards that do not currently establish a disqualifying condition.

## 9.2 Current Policy Rules

**HM-CURRENT-001:** Missing current observations must not be interpreted as confirmation that currents are absent.

**HM-CURRENT-002:** Persistent current hazards documented in the Beach Catalog must be evaluated.

**HM-CURRENT-003:** Current findings must preserve their source, timing, and geographic applicability.

**HM-CURRENT-004:** Favorable regional weather or wave forecasts cannot override verified dangerous-current information.

A lack of direct current measurements does not automatically prevent eligibility if the approved mandatory evidence policy permits assessment from other validated sources and verified persistent hazards.

---

# 10. Hazardous Weather Policies

Hazardous weather is evaluated independently from ordinary comfort and weather preferences.

## 10.1 All Activities

- EXCLUDE when an applicable lightning threat, official closure, or verified disqualifying severe-weather hazard affects the requested activity period.
- INVESTIGATE when hazardous weather is reported but its geographic or temporal applicability is unresolved.
- DISCLOSE non-disqualifying weather limitations.

## 10.2 Weather Policy Rules

**HM-WEATHER-001:** Official alerts must preserve issuing authority, advisory type, affected area, and validity period.

**HM-WEATHER-002:** An alert must not automatically be treated as affecting every Maui beach.

**HM-WEATHER-003:** Applicable official prohibitions cannot be overridden by favorable reports.

**HM-WEATHER-004:** Thunderstorm and lightning risks must not be reduced to ordinary precipitation preferences.

Official warnings and advisories must be interpreted according to their actual meaning and applicability.

An advisory is not automatically equivalent to a closure.

---

# 11. Water-Quality Policies

Water-quality advisories are evaluated independently from wave, wind, and visibility conditions.

Favorable ocean conditions do not override an applicable water-contact avoidance advisory.

## 11.1 All Activities

- EXCLUDE when an applicable official closure, prohibition, or water-contact avoidance advisory affects the requested area and period.
- INVESTIGATE when official advisory status is unavailable, ambiguous, or geographically uncertain and remains mandatory.
- DISCLOSE relevant non-disqualifying water-quality notices or limitations.

## 11.2 Water-Quality Policy Rules

**HM-WATER-001:** Applicable water-contact avoidance advisories take precedence over favorable surf or weather conditions.

**HM-WATER-002:** Failed advisory retrieval must not be interpreted as absence of advisories.

**HM-WATER-003:** Advisory issuance, affected geography, effective period, and cancellation status must be preserved when available.

**HM-WATER-004:** An absence of retrieved advisories does not establish that water quality is safe.

**HM-WATER-005:** The minimum evidence required to satisfy an official water-quality advisory check must be documented before implementation.

## 11.3 Approved Source

The Hawaii Department of Health Clean Water Branch is the proposed primary provider for relevant water-quality advisories.

Its programmatic access method remains unresolved.

An approved alternative authoritative source may be used if it satisfies the same evidence requirements.

If mandatory advisory status cannot be established, the affected candidate remains non-recommendable.

---

# 12. Underwater Visibility Policies

Underwater visibility is primarily a snorkeling suitability consideration.

Poor visibility may affect enjoyment, navigation, or awareness of surroundings, but it does not universally establish a disqualifying hazard.

## 12.1 Swimming

DISCLOSE materially relevant visibility limitations when available.

INVESTIGATE when visibility concerns indicate another unresolved safety hazard.

## 12.2 Snorkeling

- Treat visibility as an important suitability and preference factor.
- DISCLOSE poor or uncertain visibility when no separate disqualifying hazard exists.
- INVESTIGATE when visibility information materially conflicts or indicates another potentially hazardous condition.

## 12.3 SUP

Underwater visibility is not a mandatory SUP suitability criterion.

DISCLOSE relevant visibility limitations when appropriate.

## 12.4 Visibility Policy Rules

**HM-VIS-001:** Missing visibility evidence alone does not automatically exclude snorkeling.

**HM-VIS-002:** Qualitative visibility descriptions must remain qualitative unless verified measurements support numerical values.

**HM-VIS-003:** Poor visibility alone shall not automatically trigger EXCLUDE.

**HM-VIS-004:** Visibility-related hazards must be evaluated independently from ordinary preference limitations.

---

# 13. Persistent Beach Hazard Policies

Persistent hazards are obtained from verified Beach Catalog characteristics.

Examples include:

- Rocky or difficult entry.
- Reef exposure.
- Documented shoreline currents.
- Known shorebreak exposure.
- Access limitations.

The MVP maintains one catalog record per named beach rather than separate records for every access point.

## 13.1 All Activities

- EXCLUDE when a verified persistent characteristic violates an applicable hard constraint or approved safety policy.
- INVESTIGATE when the characteristic may materially affect safety but available evidence is insufficient.
- DISCLOSE relevant non-disqualifying limitations.

## 13.2 Beach Hazard Rules

**HM-BEACH-001:** Persistent beach characteristics must retain source attribution and verification dates.

**HM-BEACH-002:** Activity support in the Beach Catalog does not establish current suitability.

**HM-BEACH-003:** Individual beach access points remain outside MVP schema granularity.

**HM-BEACH-004:** Material differences within a beach must not be ignored because the catalog uses a single beach ID.

**HM-BEACH-005:** User experience may influence activity-specific suitability but shall not override hard safety exclusions.

---

# 14. Environmental Suitability and Eligibility

Candidate Assessment maintains three independent dimensions:

1. Environmental suitability.
2. Evidence quality.
3. Eligibility.

These dimensions shall not be collapsed into one numerical score.

## 14.1 Environmental Suitability

| State | Meaning |
|---|---|
| `FAVORABLE` | Validated conditions support the requested activity |
| `MIXED` | Conditions contain both supporting evidence and material limitations |
| `UNFAVORABLE` | Validated conditions indicate the activity should not be recommended |
| `UNDETERMINED` | Evidence does not establish suitability |

## 14.2 Evidence Quality

| State | Meaning |
|---|---|
| `SUFFICIENT` | Mandatory evidence requirements are satisfied |
| `LIMITED` | Useful evidence exists, but material limitations remain |
| `INSUFFICIENT` | Minimum evidence requirements are not met |

## 14.3 Eligibility

| State | Meaning |
|---|---|
| `ELIGIBLE` | Candidate satisfies documented recommendation eligibility requirements |
| `NEEDS_INVESTIGATION` | A required issue remains unresolved |
| `EXCLUDED` | Candidate violates an applicable disqualifying rule |
| `UNSUPPORTED` | Beach or activity is outside verified catalog support |

## 14.4 Eligibility Rules

**EL-001:** ELIGIBLE requires SUFFICIENT evidence quality.

**EL-002:** UNFAVORABLE suitability cannot be ELIGIBLE.

**EL-003:** UNDETERMINED suitability cannot be ELIGIBLE.

**EL-004:** A verified disqualifying policy failure requires EXCLUDED.

**EL-005:** A failed explicit hard user constraint requires EXCLUDED.

**EL-006:** Unsupported beach/activity combinations require UNSUPPORTED.

**EL-007:** Unresolved mandatory evidence requirements prevent eligibility.

**EL-008:** NEEDS_INVESTIGATION remains non-recommendable after investigation limits are exhausted.

**EL-009:** Only ELIGIBLE candidates may enter final recommendation comparison.

An eligible candidate is not guaranteed safe. Eligibility means that it meets the Forecaster's documented requirements for an evidence-supported recommendation.

---

# 15. MIXED Suitability Policy

MIXED suitability does not automatically imply eligibility or exclusion.

A MIXED candidate may be recommended only when all five conditions are satisfied:

1. Evidence quality is SUFFICIENT.
2. No applicable disqualifying safety policy has failed.
3. All mandatory hazard checks are resolved.
4. Remaining concerns are documented as non-disqualifying limitations.
5. Those limitations are clearly disclosed in the Recommendation Result.

## 15.1 Potentially Permissible MIXED Conditions

Examples may include:

- Poor underwater visibility without other disqualifying hazards.
- Non-disqualifying wind-driven chop.
- Relevant but non-disqualifying shoreline-entry limitations.
- Less favorable environmental conditions that remain within explicitly permitted activity-specific policies.

These examples do not automatically authorize a recommendation.

The applicable policy must establish that the particular condition is non-disqualifying.

## 15.2 Conditions Not Permitted as MIXED Recommendations

A candidate cannot be promoted to an eligible MIXED recommendation when:

- A disqualifying safety policy has failed.
- A mandatory hazard check remains unresolved.
- A material safety conflict remains unresolved.
- Evidence quality is LIMITED or INSUFFICIENT.
- An explicit hard user constraint is violated.

## 15.3 Ranking

MIXED candidates generally rank below otherwise comparable FAVORABLE candidates.

User preferences may influence qualitative comparison among eligible candidates.

For example, a geographically preferred MIXED candidate may be compared with a farther FAVORABLE candidate, provided both qualify under safety and evidence policies.

No arbitrary numerical weights or suitability scores shall be introduced.

The Coordinator must explain material differences.

---

# 16. Evidence Sufficiency and Uncertainty

Evidence sufficiency is determined for a specific beach, activity, and requested time period.

The system shall not use a fixed source count or numerical confidence score to determine whether evidence is sufficient.

## 16.1 Core Requirements

**ES-001 — Activity-Specific Requirements**

Minimum evidence requirements depend on the requested activity.

**ES-002 — Source Quality**

Evidence must originate from an approved source with identifiable provenance.

**ES-003 — Temporal Relevance**

Evidence must support the requested period using documented validity rules.

**ES-004 — Geographic Relevance**

Evidence must apply to the candidate at an acceptable geographic resolution.

**ES-005 — Mandatory Hazard Coverage**

Mandatory hazard and advisory checks must be resolved before eligibility.

**ES-006 — No Source-Count Requirement**

Evidence sufficiency does not depend solely on retrieving a fixed number of providers.

**ES-007 — No Assumed Favorable Conditions**

Missing or rejected evidence must not be interpreted as favorable.

**ES-008 — Independent Assessment**

Evidence quality, suitability, and eligibility remain independent.

**ES-009 — Conflict Resolution**

Material unresolved conflicts affecting mandatory safety decisions prevent eligibility.

**ES-010 — Explainability**

Sufficiency decisions must reference their supporting findings and applicable validation rules.

---

# 17. Geographic Evidence Sufficiency

Maui beaches can experience different conditions within the same regional forecast area.

The Forecaster must maintain the distinction between geographic coverage and beach-specific applicability.

## 17.1 Beach-Specific Evidence

Evidence explicitly applying to a named beach may support assessment when its source, timing, and limitations are acceptable.

Beach-specific reporting does not guarantee current conditions.

## 17.2 Local-Area Evidence

Evidence describing a local area may support catalog beaches when geographic mapping is verified and no material applicability conflict remains.

## 17.3 Regional Evidence

Regional forecasts may support a beach assessment when:

1. The beach lies within the applicable reporting or forecast region.
2. The forecast covers the requested time period.
3. Verified beach characteristics support its interpretation.
4. The resulting conclusion does not exceed the source's geographic precision.
5. No unresolved material hazard contradicts the assessment.

Regional information must not be presented as a direct beach observation.

## 17.4 Offshore Evidence

Offshore observations may provide contextual information about broader marine conditions.

They do not independently establish:

- Beach-specific breaking surf.
- Local currents.
- Underwater visibility.
- Shoreline entry conditions.

Station location and observation time must be preserved.

## 17.5 Insufficient Geographic Applicability

When a finding cannot be reasonably applied to a candidate, the affected evidence category remains unresolved.

The Coordinator may investigate another approved source or candidate.

If a mandatory category cannot establish adequate geographic relevance, the candidate remains non-recommendable.

---

# 18. Temporal Evidence Sufficiency

Evidence must be evaluated relative to the user's requested activity period.

## 18.1 Forecasts

A forecast may support a future recommendation when its validity period covers the requested time.

Forecast issuance and retrieval times must remain distinct.

## 18.2 Observations

Observations describe conditions at their observation time.

They may provide context for later conditions but cannot automatically establish future suitability.

## 18.3 The Snorkel Store

The Snorkel Store typically publishes a daily Maui snorkeling report around 8:00 a.m. Hawaii Standard Time.

The system must check the actual report date and available publication time.

A previous day's report must not be presented as a current-day observation.

A current-day observation must not automatically be treated as a verified forecast for tomorrow.

## 18.4 HawaiiWeatherToday

The following pages shall be validated independently:

- Dive and Snorkel / Water Visibility.
- Surfing / Surf Height.
- Windsurfing / Wind Conditions.
- Glenn's Daily Weather Narrative.

A current narrative does not establish that the Surf, Wind, or Visibility pages are current.

Each finding retains its own publication and forecast validity information.

## 18.5 Expired Evidence

Expired evidence may remain available as historical context.

It shall not satisfy mandatory evidence requirements for the current or future activity period.

Exact source-specific freshness thresholds remain open pending provider integration verification.

---

# 19. Source Independence and Corroboration

Different websites may reproduce the same underlying forecasts or observations.

For example, a narrative website may summarize an NWS forecast.

The Forecaster shall not count these as independent confirmation merely because they appear under different publishers.

## 19.1 Source Rules

**ES-SRC-001:** Preserve original publisher identity and known underlying sources.

**ES-SRC-002:** Identify derivative or republished information where possible.

**ES-SRC-003:** Republished evidence must not automatically count as independent confirmation.

**ES-SRC-004:** Source count alone shall not determine evidence sufficiency.

**ES-SRC-005:** A single reliable, sufficiently applicable source may satisfy a particular requirement when the corresponding policy permits it.

**ES-SRC-006:** Applicable official warnings or restrictions cannot be overridden by favorable supplemental reports.

---

# 20. Material Evidence Conflicts

A conflict is material when resolving it could change:

- A mandatory safety-policy outcome.
- Candidate eligibility.
- Environmental suitability.
- Compliance with an explicit hard user constraint.
- A critical warning or limitation in the final Recommendation Result.

## 20.1 Potential Conflicts

Examples include:

- An official hazardous-surf warning alongside a favorable local snorkeling report.
- Different surf-height measurement conventions.
- Reports describing different times of day.
- Regional forecasts conflicting with beach-specific observations.
- An official water-quality advisory alongside observations of apparently clear water.

Not every disagreement is material.

## 20.2 Conflict Handling Procedure

The Coordinator shall:

1. Preserve the conflicting findings.
2. Check source identity and potential duplication.
3. Compare geographic coverage.
4. Compare observation and forecast periods.
5. Check measurement definitions and conventions.
6. Apply applicable authoritative hazard rules.
7. Request further evidence if permitted and necessary.
8. Document any unresolved uncertainty.

A material conflict that prevents a mandatory safety determination leaves the candidate non-recommendable.

Non-material disagreements may be disclosed without automatically preventing eligibility.

## 20.3 Conflict Rules

**CF-001:** Preserve original underlying source attribution where identifiable.

**CF-002:** Identify republished or derivative evidence.

**CF-003:** Do not count duplicated underlying evidence as independent corroboration.

**CF-004:** Preserve material differences.

**CF-005:** Investigate material conflicts within authorized limits.

**CF-006:** Disclose or abstain when unresolved conflicts prevent defensible recommendations.

---

# 21. Evidence Quality Classification

Candidate evidence quality must be determined independently of environmental suitability.

## 21.1 SUFFICIENT

All mandatory evidence requirements are satisfied using accepted findings with appropriate temporal and geographic applicability.

No unresolved material conflict prevents required safety-policy decisions.

Optional evidence may still be missing.

## 21.2 LIMITED

Useful evidence exists, but one or more material limitations prevent full sufficiency.

Examples:

- Relevant observations exist but geographic applicability is uncertain.
- A required evidence category is incomplete.
- A material source conflict requires further investigation.

## 21.3 INSUFFICIENT

Available evidence does not meet the minimum requirements.

Examples:

- No usable environmental information.
- Mandatory sources return stale or rejected findings.
- Critical provenance information is missing.
- Required safety checks cannot be established.

## 21.4 Classification Rules

Only SUFFICIENT evidence can support ELIGIBLE status.

LIMITED and INSUFFICIENT evidence prevent eligibility.

Reaching an investigation limit does not justify upgrading evidence quality.

---

# 22. User Constraints and Geographic Preferences

The Forecaster shall distinguish hard constraints from soft preferences.

Examples:

| User statement | Interpretation |
|---|---|
| "Only South Maui" | Hard geographic constraint if clearly mandatory |
| "Near Kihei" | Soft geographic preference |
| "Prefer calm water" | Soft environmental preference |
| "I won't go in waves" | Potential hard environmental constraint; clarify if necessary |
| "I'm a beginner" | Experience information relevant to policy and suitability |

Soft preferences cannot override safety exclusions.

When a constraint is materially ambiguous, the Coordinator may request clarification.

Driving-time estimation is outside MVP scope.

---

# 23. Investigation, Fallback, and Abstention

The Coordinator may request additional evidence when:

- Mandatory information is missing.
- Evidence is stale.
- Geographic applicability remains uncertain.
- Material conflicts exist.
- Providers return partial or failed responses.
- Another supported candidate may offer a viable alternative.

Additional investigation must use approved sources and remain within enforced limits.

## 23.1 Candidate Handling

A candidate with unresolved mandatory evidence remains non-recommendable.

If further investigation is possible, its status may remain NEEDS_INVESTIGATION.

If investigation limits are exhausted, the candidate does not automatically become EXCLUDED.

EXCLUDED is reserved for verified disqualifying conditions or other documented exclusion rules.

## 23.2 Abstention

The Forecaster shall return NO_RECOMMENDATION when no eligible candidate remains because:

- Mandatory evidence cannot be established.
- Applicable hazards disqualify candidates.
- Material safety conflicts remain unresolved.
- Hard constraints prevent recommendation.
- Investigation limits are exhausted without sufficient evidence.

The result must explain the reason.

## 23.3 Technical Failure

An unrecoverable orchestration or application failure shall produce ERROR.

A correctly handled source outage that leads to insufficient evidence and an explained abstention is not automatically a technical failure.

---

# 24. Recommendation and User-Facing Safety Communication

The Forecaster may return up to three recommendations.

Only ELIGIBLE candidates with SUFFICIENT evidence and policy-permitted suitability may be recommended.

## 24.1 Recommendation Requirements

Each recommendation shall:

- Identify the beach and intended activity.
- Specify the supported time period.
- Explain why the candidate was selected.
- Identify relevant environmental evidence.
- Disclose applicable warnings and limitations.
- Preserve meaningful source references.
- Distinguish observations from forecasts and interpretations.

The system shall not guarantee ocean safety.

## 24.2 Qualified Recommendations

A MIXED recommendation must identify the non-disqualifying limitations that contributed to its classification.

The explanation should be specific to the location and activity rather than relying solely on a generic safety disclaimer.

## 24.3 Final Safety Reminder

The CLI should encourage users to verify current official warnings, posted notices, lifeguard guidance, and actual on-site conditions before entering the water.

An earlier forecast or recommendation does not replace a real-time assessment of conditions.

---

# 25. Policy Traceability and Evaluation

Policy evaluation shall use the existing Candidate Assessment and Investigation Trace schemas.

For each material policy decision, the trace should identify:

- Policy ID.
- Supporting finding references.
- PASS, FAIL, UNKNOWN, or NOT_APPLICABLE.
- Relevant policy action.
- Candidate eligibility changes.
- Decision explanation.

The trace shall not capture private model chain-of-thought.

Synthetic fixtures shall be used to test policy behavior.

A natural-language response that appears plausible must still fail acceptance testing if the underlying policy requirements were violated.

---

# 26. Evidence Sufficiency Validation Rules

**ES-V001:** Every eligible candidate must have SUFFICIENT evidence quality.

**ES-V002:** All mandatory activity-specific evidence requirements must be resolved.

**ES-V003:** Mandatory official advisory checks must use approved authoritative sources.

**ES-V004:** Advisory retrieval failure must not be interpreted as absence of advisories.

**ES-V005:** Geographic and temporal applicability must be established for mandatory evidence.

**ES-V006:** Offshore and regional evidence must preserve original coverage.

**ES-V007:** Stale and rejected findings cannot satisfy mandatory current evidence requirements.

**ES-V008:** Missing optional evidence does not automatically prevent eligibility.

**ES-V009:** Missing snorkeling visibility evidence alone does not exclude a candidate.

**ES-V010:** Material unresolved safety conflicts prevent eligibility.

**ES-V011:** Republished evidence must not automatically count as independent corroboration.

**ES-V012:** Evidence sufficiency must not depend on arbitrary source counts or numerical confidence scores.

**ES-V013:** Sufficiency decisions must identify supporting findings and validation rules.

**ES-V014:** Investigation limits must not weaken mandatory evidence requirements.

**ES-V015:** When sufficient evidence cannot be established, the Coordinator must investigate further within limits or withhold the affected recommendation.

---

# 27. Safety Acceptance Scenarios

The following scenarios define expected safety-policy behavior using synthetic environmental data.

| Test | Scenario | Expected result |
|---|---|---|
| SP-T01 | Official closure applies to requested beach and activity | EXCLUDED |
| SP-T02 | Required ocean evidence unavailable | Not eligible |
| SP-T03 | Regional forecast mislabeled beach-specific | Geographic validation fails |
| SP-T04 | Stale daily snorkeling report presented as current | Evidence rejected |
| SP-T05 | Favorable weather with applicable disqualifying marine warning | EXCLUDED |
| SP-T06 | Mandatory water-quality advisory status unavailable | INVESTIGATE; no assumed clearance |
| SP-T07 | Hawaiian-style and face-height measurements compared without normalization | Invalid comparison |
| SP-T08 | Material conflicting safety evidence | INVESTIGATE or withhold |
| SP-T09 | Soft geographic preference conflicts with safety | Safety takes precedence |
| SP-T10 | Three recommendations requested but only one eligible | Return one |
| SP-T11 | Investigation limit reached with insufficient evidence | Explained abstention |
| SP-T12 | Unrecoverable orchestration failure | ERROR |
| SP-T13 | External content attempts to override safety rules | Unauthorized instructions ignored |
| SP-T14 | Candidate has UNFAVORABLE suitability | Not eligible |
| SP-T15 | MIXED candidate lacks required policy permission | Not recommended |

## 27.1 Activity-Specific Hazard Tests

| Test | Scenario | Expected result |
|---|---|---|
| HM-T01 | Applicable beach closure | EXCLUDED for all activities |
| HM-T02 | Regional elevated surf with uncertain beach impact | INVESTIGATE |
| HM-T03 | Verified dangerous shorebreak at activity area | EXCLUDE |
| HM-T04 | Verified dangerous offshore winds for SUP | EXCLUDE |
| HM-T05 | Non-disqualifying wind-driven chop | DISCLOSE |
| HM-T06 | Verified dangerous currents | EXCLUDE |
| HM-T07 | No current observation available | Do not assert currents absent |
| HM-T08 | Applicable lightning threat | EXCLUDE |
| HM-T09 | Applicable water-contact avoidance advisory | EXCLUDE |
| HM-T10 | Failed water-quality retrieval | Do not infer no advisory |
| HM-T11 | Snorkeling visibility unavailable, other mandatory evidence sufficient | Not automatically excluded |
| HM-T12 | Poor visibility without another hazard | DISCLOSE and assess suitability |
| HM-T13 | Verified hard constraint violated by beach characteristics | EXCLUDE |
| HM-T14 | Offshore finding presented as a direct beach observation | Reject claim |
| HM-T15 | Mandatory hazard unresolved after investigation limit | Remains non-recommendable |
| HM-T16 | Multiple simultaneous hazards | Preserve separate policy results |
| HM-T17 | Favorable supplemental report conflicts with official prohibition | Official prohibition enforced |
| HM-T18 | Geographic preference conflicts with deterministic exclusion | Exclusion enforced |

## 27.2 Evidence Sufficiency Tests

| Test | Scenario | Expected result |
|---|---|---|
| ES-T01 | Valid relevant forecasts and mandatory checks pass | May qualify as SUFFICIENT |
| ES-T02 | Regional forecast mapped to verified beach exposure | May support assessment |
| ES-T03 | Offshore observation incorrectly treated as beach measurement | Reject claim |
| ES-T04 | Daily local report unavailable | Identify missing evidence; assess requirements independently |
| ES-T05 | Visibility unavailable but mandatory snorkeling evidence passes | May remain eligible |
| ES-T06 | Official advisory source unavailable | Do not assume no advisories |
| ES-T07 | NWS forecast republished by another site | No false independent corroboration |
| ES-T08 | Non-material qualitative disagreement | Preserve; disclosure may suffice |
| ES-T09 | Material safety conflict | Investigate or withhold |
| ES-T10 | One HWT page current, another stale | Validate independently |
| ES-T11 | Today's local observations used for tomorrow | Not automatically a future forecast |
| ES-T12 | Mandatory ocean evidence unavailable after retries | Not eligible |
| ES-T13 | Poor visibility with all mandatory requirements satisfied | MIXED may be permitted |
| ES-T14 | Investigation limit reached | Evidence quality unchanged |
| ES-T15 | All candidates lack sufficient evidence | Explained NO_RECOMMENDATION |

Passing these tests does not establish real-world ocean safety. It demonstrates compliance with the documented policy rules and synthetic expectations.

---

# 28. Unresolved Safety Requirements

The five major safety-policy sections are approved at the logical design level.

The following implementation-critical details remain unresolved.

| ID | Open requirement | Priority |
|---|---|---|
| SAF-OD-001 | Final minimum evidence criteria for swimming | High |
| SAF-OD-002 | Final minimum evidence criteria for snorkeling | High |
| SAF-OD-003 | Final minimum evidence criteria for SUP | High |
| SAF-OD-004 | Activity-specific hazardous surf and shorebreak criteria | High |
| SAF-OD-005 | Wind hazard criteria, particularly offshore SUP winds | High |
| SAF-OD-006 | Geographic applicability rules for regional forecasts | High |
| SAF-OD-007 | Source-specific freshness thresholds | High |
| SAF-OD-008 | Official advisory-status verification requirements | High |
| SAF-OD-009 | Water-quality advisory fallback behavior | High |
| SAF-OD-010 | Material environmental conflict criteria | High |
| SAF-OD-011 | Activity-specific criteria for FAVORABLE, MIXED, and UNFAVORABLE | High |
| SAF-OD-012 | Beach exposure and forecast-zone mappings | High |
| SAF-OD-013 | Handling persistent current hazards without direct observations | High |
| SAF-OD-014 | Experience-level effects on suitability | Medium |
| SAF-OD-015 | Clarification requirements for ambiguous hard constraints | Medium |
| SAF-OD-016 | Exact investigation, retry, and tool-call limits | Medium |
| SAF-OD-017 | Approved surf-height normalization methods, if needed | Medium |
| SAF-OD-018 | Final policy versioning and configuration rules | Medium |

These requirements must be resolved before their corresponding safety checks become implementation-ready.

Coding agents shall not invent numerical thresholds, source-validity rules, geographic mappings, or exemptions.

Where a mandatory rule remains undefined, the system must not silently treat it as satisfied.

---

# 29. Cross-Specification Dependencies

The Safety Policy depends on information defined in other specifications.

## Beach Catalog

Provides verified beach characteristics, supported activities, persistent hazards, and geographic information.

## Environmental Finding

Provides weather and ocean evidence, source attribution, timestamps, geographic coverage, and validation status.

## Candidate Assessment

Stores independent eligibility, environmental suitability, evidence quality, hard-constraint results, and policy evaluations.

## Investigation State

Tracks unresolved issues, candidate assessments, investigation limits, and current workflow status.

## Recommendation Result

Presents eligible recommendations, material warnings, evidence references, and explained abstentions.

## Investigation Trace

Records material evidence validation, policy decisions, reassessments, and outcomes.

## Agent and Tool Contracts

Defines approved external providers, retrieval permissions, specialist responsibilities, and structured tool failures.

Safety policies shall not depend on unverified provider capabilities being available.

---

# 30. Specification Status

## 30.1 Approved Logical Design

| Area | Status |
|---|---|
| General safety framework | Approved |
| Policy enforcement actions | Approved |
| Minimum evidence categories | Approved |
| Activity-specific hazard matrix framework | Approved |
| MIXED suitability policy | Approved |
| Evidence sufficiency and uncertainty framework | Approved |
| Geographic and temporal integrity principles | Approved |
| Conflict handling and abstention principles | Approved |
| Traceability and synthetic evaluation approach | Approved |

## 30.2 Pending Implementation Details

Provider-specific validity rules, numeric thresholds, exact geographic mappings, and operational limits remain pending.

The approved framework establishes how the system must behave, but it does not authorize implementation components to resolve these questions independently.

## 30.3 MVP Constraints

The safety architecture shall not introduce:

- Additional autonomous safety or reviewer agents.
- Unbounded source crawling.
- Arbitrary numerical confidence scores.
- Unsupported beach-specific forecasts.
- Autonomous bookings or external actions.
- An ongoing human approval queue.
- Enterprise monitoring infrastructure.

---

# 31. Next Specification

The next document is:

`docs/requirements/06-test-acceptance.md`

It will define:

- Synthetic environmental fixtures.
- Deterministic acceptance scenarios.
- Expected policy outcomes.
- Agent and tool contract tests.
- Evidence grounding evaluations.
- Appropriate abstention tests.
- Source outage and fallback scenarios.
- Prompt-injection resistance tests.
- Workflow observability and execution-limit verification.
- Measurable MVP completion criteria.

The test specification will use the requirements and identifiers established in this document.

---

**End of Safety Policies Specification v0.2**

**Approval status:** Approved logical design; implementation-specific thresholds and provider rules remain open.

**No application code is authorized by this specification.**