# Hawaii Activity Forecaster
# M1.1 Synthetic Fixture Design

**Version:** 0.1 — Approved Baseline
**Status:** Approved — M1.1 Synthetic Fixture Design
**Project:** CMU Agentic AI Systems Capstone  
**Milestone:** M1.1 — Project Foundations  
**Document:** `docs/implementation/m1-synthetic-fixture-design.md`  
**Implementation authorization:** Planning only; no application code authorized

## 1. Purpose

This document defines the synthetic data, fixture organization, serialization conventions, simulated provider behaviors, and expected-result assertions used to validate the Hawaii Activity Forecaster during M1.

The design supports repeatable testing of the complete workflow:

1. User request interpretation.
2. Candidate beach selection.
3. Coordinator evidence planning.
4. Weather and Ocean specialist delegation.
5. Synthetic environmental retrieval.
6. Contract and evidence validation.
7. Deterministic safety evaluation.
8. Candidate comparison.
9. Structured recommendation generation.
10. CLI presentation and Investigation Trace validation.

The fixtures shall exercise the approved application contracts without requiring live weather or ocean data.

M1 fixtures are not representations of actual conditions at Maui beaches.

## 2. Authoritative Specifications

This design is subordinate to:

- `01-product-requirements.md`
- `02-system-architecture.md`
- `03-data-schemas.md`
- `04-agent-tool-contracts.md`
- `05-safety-policies.md`
- `06-test-acceptance.md`
- `07-observability.md`
- `m1-session-lifecycle.md`
- `m1-technical-plan.md`
- `m1-configuration-baseline.md`
- `m1-schema-contract-mapping.md`

The approved logical fields, enumerations, agent permissions, safety policies, execution limits, and test scenarios remain authoritative.

This specification proposes their physical fixture representation. It does not redefine them.

---

# 3. Fixture Design Principles

**FX-001 — Deterministic Inputs**

Every fixture shall provide a fixed reference time, versioned inputs, and explicit expected assertions.

**FX-002 — Fictional Geography**

Test beaches shall use fictional, clearly labeled records.

Real Maui locality names may be used to exercise geographic preferences, but synthetic coordinates and shoreline characteristics shall not be interpreted as verified geographic facts.

**FX-003 — Contract Fidelity**

Synthetic Weather and Ocean responses shall conform to the same logical interfaces required of future live source adapters.

**FX-004 — Evidence Independence**

Expected safety and eligibility outcomes shall be maintained independently of the application's generated findings, assessments, and explanations.

**FX-005 — Explicit Assumptions**

Mandatory evidence shall be explicitly represented. A scenario must not pass because unspecified conditions are silently assumed favorable.

**FX-006 — Safety Independence**

Fixtures may provide documented synthetic policy inputs or expected policy results where real-world thresholds remain unresolved.

They shall not authorize arbitrary numerical hazard thresholds.

**FX-007 — Reproducibility**

The same synthetic inputs and versioned policy configuration shall produce consistent deterministic eligibility and safety outcomes.

**FX-008 — Failure Visibility**

Unavailable evidence, rejected findings, retries, fallbacks, and other failures shall be represented as observable events.

**FX-009 — No Acceptance Contamination**

The application under test shall not have access to the expected-results assertions used by the independent evaluator.

**FX-010 — No Live Provider Dependency**

Synthetic tests shall not require network retrieval from environmental providers.

---

# 4. Fixture Package Organization

## 4.1 Proposed Logical Organization

The following directory structure is proposed:

```text
fixtures/
  catalogs/
    synthetic-maui-v1.json

  policies/
    synthetic-policy-v1.json

  sources/
    weather/
    ocean/

  behaviors/
    standard-success.json
    provider-timeout.json
    partial-response.json
    duplicate-response.json
    malformed-response.json
    retry-success.json
    fallback-success.json

  scenarios/
    sc-001/
      scenario.json
      expected.json
    sc-002/
      scenario.json
      expected.json
    ...
    sc-012/
      scenario.json
      expected.json

  manifest.json
```

This is a proposed organizational convention, not an application source-code structure.

Actual fixture paths and references shall be resolved relative to the fixture package root.

## 4.2 Separation of Concerns

| Fixture artifact | Purpose | Consumed by |
|---|---|---|
| Catalog | Candidate beaches and persistent attributes | Application |
| Policy configuration | Versioned synthetic policy inputs | Trusted policy evaluator |
| Source response | Environmental findings and retrieval metadata | Synthetic tool adapter |
| Tool behavior | Simulated delays, errors, duplicates, attempts | Synthetic execution harness |
| Scenario definition | Request and selected input references | Test harness/application |
| Expected results | Independent acceptance assertions | Evaluator only |
| Manifest | Version and fixture integrity metadata | Test harness |

Expected results shall never be used as a substitute for actual safety-policy execution.

---

# 5. Fixture Versioning

## 5.1 Proposed Convention

Each fixture package shall identify:

- `fixture_format_version`
- `fixture_package_version`
- `schema_version`
- `policy_version`
- `scenario_id`, where applicable

Proposed initial fixture package version: `1.0.0`.

The package version is distinct from the logical schema version and Safety Policy version.

## 5.2 Compatibility

A fixture shall declare which approved schema and policy versions it targets.

The loader shall reject unsupported versions rather than silently reinterpret field meanings.

Changes to expected eligibility results, policy assumptions, or serialized field semantics shall trigger review of affected tests.

## 5.3 Reproducibility Record

A test execution should identify:

- Fixture package version.
- Scenario ID.
- Catalog version or reference.
- Policy version.
- Configuration version.
- Model identifier when applicable.
- Fixed reference time.
- Relevant generated investigation and trace identifiers.

Runtime identifiers may vary between runs. Their relationships and validity must remain testable.

---

# 6. JSON Serialization Conventions

These conventions resolve physical representations left open by the approved schema mapping. They are proposed for M1 and require approval.

## 6.1 Timestamp

Use ISO 8601 strings with explicit offsets.

Example:

`2026-11-16T09:00:00-10:00`

UTC timestamps may use an explicit UTC designator.

Naive timestamps without an offset shall be rejected.

## 6.2 Date

Use ISO calendar-date strings.

Example:

`2026-11-17`

## 6.3 Time Range

**Proposed representation:**

```json
{
  "start": "2026-11-17T08:00:00-10:00",
  "end": "2026-11-17T11:00:00-10:00"
}
```

Rules:

- Both boundaries must include time-zone information.
- `start` must precede `end`.
- The range is interpreted as start-inclusive and end-exclusive for interval comparison.
- Activity recommendations shall not extend beyond supported evidence validity.
- Time zones shall not be inferred from the machine's local clock.

The `start` and `end` fields are proposed physical serialization fields for the already-approved logical Time range type.

## 6.4 Numeric Measurements

Represent numeric measurement values as JSON numbers.

Example:

```json
{
  "measurement_type": "WIND_SPEED",
  "value": 8,
  "unit": "kn",
  "measurement_time": "2026-11-17T09:00:00-10:00"
}
```

The numerical value and unit describe reported synthetic evidence, not an automatically favorable or hazardous condition.

## 6.5 Range Measurements

**Proposed representation:**

```json
{
  "measurement_type": "SURF_HEIGHT",
  "value": {
    "min": 1,
    "max": 2
  },
  "unit": "ft",
  "measurement_convention": "FACE"
}
```

Range boundaries must use a consistent unit and measurement convention.

The original source measurement shall be preserved.

The range format shall not be used to conceal different measurement methods.

## 6.6 Categorical Measurements

Represent a supported categorical value as a JSON string.

Example:

```json
{
  "measurement_type": "WEATHER_CONDITION",
  "value": "PARTLY_CLOUDY"
}
```

Categorical vocabulary shall be constrained to documented fixture or approved provider mappings.

Arbitrary model-generated categories shall not automatically become valid structured measurements.

## 6.7 Unknown and Missing Values

Missing evidence shall be represented through the approved missing-field, evidence-gap, or validation mechanisms.

A required field shall not be silently replaced by `null` unless the authoritative schema explicitly permits that representation.

Optional fields may be omitted when their absence has no material meaning.

Explicitly unavailable required evidence shall remain discoverable and traceable.

## 6.8 Identifiers and Enumerations

Use approved uppercase enum values exactly as specified.

Identifiers shall be stable within a fixture package when representing the same logical object.

Scenario-local IDs may be namespaced with the scenario identifier.

A runtime-generated identifier need not equal a fixture identifier unless the relevant contract requires that exact identity.

---

# 7. Synthetic Beach Catalog

## 7.1 Common Catalog

Use the five fictional test beaches defined in the approved acceptance specification.

| Beach ID | Region | Locality | Supported activities |
|---|---|---|---|
| `TEST_BEACH_A` | SOUTH_MAUI | Kihei | SWIMMING, SNORKELING |
| `TEST_BEACH_B` | SOUTH_MAUI | Wailea | SWIMMING, SNORKELING, SUP |
| `TEST_BEACH_C` | WEST_MAUI | Napili | SWIMMING, SNORKELING |
| `TEST_BEACH_D` | WEST_MAUI | Kaanapali | SWIMMING, SNORKELING, SUP |
| `TEST_BEACH_E` | SOUTH_MAUI | Makena | SWIMMING |

The catalog shall include all required fields defined in `03-data-schemas.md`.

These include identifiers, names, geographic fields, supported activities, lifeguard status, verification metadata, and source references.

## 7.2 Synthetic Source References

Catalog verification references shall identify their synthetic nature.

They must not imply that fictional beach attributes were verified against actual public sources.

Source-reference serialization must remain consistent with the approved `SourceReference` contract.

A fixture-specific synthetic reference scheme may be proposed during implementation, provided it satisfies contract validation and does not resemble fabricated public verification.

## 7.3 Geographic Relationships

The catalog shall encode region and locality relationships needed for preference evaluation.

For M1:

- A and B support South Maui preference scenarios.
- C and D support West Maui preference scenarios.
- E exercises limited activity support and entry restrictions.

No fixture shall introduce unsupported driving-time calculations.

## 7.4 Catalog Variants

Scenario-specific catalog variants may test:

- Unsupported activities.
- Unverified catalog records.
- Disabled beaches.
- Missing persistent hazard information.
- Valid but limited geographic attributes.
- Malformed source references.

A variant shall explicitly identify changes from the common catalog.

---

# 8. Environmental Source Fixtures

## 8.1 Source Identity

Synthetic responses may use approved provider IDs:

- `NWS_WEATHER`
- `NWS_ALERTS`
- `NWS_MARINE`
- `HI_DOH_CWB`
- `NDBC`
- `SNORKEL_STORE`
- `HWT_VISIBILITY`
- `HWT_SURF`
- `HWT_WIND`
- `HWT_NARRATIVE`

Each response must be clearly identifiable as synthetic.

Using a provider ID in a fixture does not authorize or imply live retrieval from that provider.

PacIOOS Maui SWAN remains outside MVP scope.

## 8.2 Synthetic Environmental Finding

Each returned finding shall use the approved `EnvironmentalFinding` contract.

The fixture shall preserve:

- Source identity.
- Specialist domain.
- Finding type.
- Geographic scope.
- Temporal metadata.
- Measurements and advisories.
- Missing information.
- Retrieval status.
- Applicable validation state.

The synthetic source adapter shall not use the evaluator's expected assertions to determine the finding's correctness.

## 8.3 Weather Fixtures

Weather source fixtures should cover:

- Forecast wind.
- Weather conditions.
- Relevant alerts.
- Forecast time coverage.
- Geographic limitations.
- Missing or stale weather information.

Weather fixtures must preserve whether data represents a forecast, observation, advisory, or qualitative report.

## 8.4 Ocean Fixtures

Ocean source fixtures should cover:

- Surf and wave conditions.
- Swell measurements.
- Offshore observations.
- Water visibility reports.
- Water-quality advisories.
- Current and shoreline hazard evidence where supported.
- Regional-versus-beach coverage.
- Conflicting reports.

Surf and swell measurements shall remain distinct.

Offshore observations shall not be represented as direct shoreline conditions.

## 8.5 Synthetic Advisory Checks

An applicable official advisory shall be represented using the approved AdvisoryReference structure.

Fixtures must distinguish:

1. An applicable advisory exists.
2. No applicable advisory was found after an acceptable check.
3. Advisory retrieval was unavailable.
4. An advisory exists outside the candidate geography or time.
5. Advisory applicability remains uncertain.

Retrieval failure shall never be treated as confirmation that no advisory exists.

---

# 9. Synthetic Policy Configuration

## 9.1 Purpose

The synthetic policy configuration enables deterministic safety tests before real-world hazard thresholds have been verified.

It is not a replacement for `05-safety-policies.md`.

## 9.2 Policy Inputs and Expected Outcomes

Fixtures may supply synthetic facts sufficient to exercise documented policies.

For example:

- An official water-contact avoidance advisory is applicable.
- A verified disqualifying hazard has been established.
- A mandatory advisory check is unavailable.
- A non-disqualifying visibility limitation exists.
- Two material safety findings conflict.

The trusted evaluator must still apply the approved policy rules.

## 9.3 Prohibited Shortcuts

A fixture must not bypass safety evaluation by supplying an unexplained final `ELIGIBLE` classification as authoritative source evidence.

Expected policy results may appear in evaluator-owned expected assertions.

Synthetic policy inputs may establish a hypothetical hazard classification when its real-world measurement threshold is unresolved, but that mechanism must be explicit and distinguishable from ordinary source measurements.

## 9.4 MIXED Suitability

Fixtures testing MIXED suitability shall explicitly specify:

- The non-disqualifying limitation.
- Sufficient evidence for all mandatory questions.
- No applicable disqualifying policy failure.
- The policy basis permitting MIXED recommendation.
- Required disclosure assertions.

MIXED with LIMITED evidence shall not be eligible.

## 9.5 Threshold Limitations

M1 shall not establish unsupported universal thresholds for:

- Surf height.
- Offshore swell height.
- Wind speed.
- Water visibility.
- Current speed.
- Shorebreak conditions.

Numerical values may exercise measurement parsing and preservation without establishing real-world safety thresholds.

---

# 10. Tool Behavior Fixtures

## 10.1 Purpose

Tool behavior fixtures control how synthetic environmental adapters respond.

They shall be independent of the EnvironmentalToolRequest and EnvironmentalToolResponse logical schemas.

Behavior controls are test-harness instructions, not additional fields inserted into production tool responses.

## 10.2 Proposed Behavior Vocabulary

| Behavior | Meaning |
|---|---|
| `SUCCESS` | Return configured valid response |
| `PARTIAL` | Return some findings and explicit gaps |
| `UNAVAILABLE` | Return unavailable status without fabricated findings |
| `ERROR` | Return structured failure |
| `TIMEOUT` | Simulate exceeding approved tool timeout |
| `MALFORMED` | Return a response that violates the approved contract |
| `DUPLICATE` | Deliver the same logical response more than once |

These names describe fixture-harness behavior and do not change approved retrieval-status enumerations.

## 10.3 Proposed Behavior Representation

```json
{
  "behavior": "TIMEOUT",
  "simulated_duration_ms": 11000,
  "attempt": 1
}
```

The approved synthetic tool timeout is 10 seconds.

A simulated 11-second completion shall exercise timeout handling without requiring an actual 11-second test delay.

## 10.4 Retry and Fallback Scripts

A scenario may define sequential responses for an original attempt and permitted recovery actions.

Example:

- Original tool invocation: ERROR.
- Authorized retry: SUCCESS.
- Further retry attempt: forbidden.

Fallback behavior must identify the unresolved evidence gap and authorized alternative source.

Retries and fallbacks shall consume the approved shared environmental tool budget.

## 10.5 Parallel Execution

Fixture behavior shall allow Weather and Ocean responses to complete in either order.

Acceptance results shall not depend on execution-completion order.

Tests must verify:

- Maximum two concurrent specialist executions.
- No duplicate evidence after repeated responses.
- No lost independent findings.
- No stale revision overwrites.
- No budget oversubscription.
- Valid response correlation.

---

# 11. Scenario Definition

## 11.1 Authoritative TestScenario

Each scenario shall preserve the approved TestScenario fields:

- `scenario_id`
- `description`
- `requirement_ids`
- `user_request`
- `reference_time`
- `catalog_fixture`
- Conditional `weather_fixture`
- Conditional `ocean_fixture`
- Optional `tool_behavior`
- `policy_configuration`
- `expected_results`
- `test_status`

The physical fixture representation may reference expected assertions from a separate file, provided the loader resolves that reference into the required logical `expected_results` value before validation.

## 11.2 Reference Time

The approved common scenario reference time is:

`2026-11-16T09:00:00-10:00`

For the initial scenario set:

"Tomorrow morning" resolves to:

`2026-11-17T08:00:00-10:00` through `2026-11-17T11:00:00-10:00`.

This convention applies to the designated synthetic scenarios only.

It must not become an undocumented default for real user requests.

## 11.3 Scenario Status

Approved test statuses:

- ACTIVE.
- BLOCKED.
- DISABLED.

An individual assertion may be PARTIALLY_BLOCKED when an unresolved requirement affects only part of a scenario.

A blocked assertion shall not be counted as a passing test.

## 11.4 Scenario Isolation

Each scenario shall run with:

- Its declared fixture versions.
- A new investigation context.
- A fixed reference time.
- Fresh execution budgets.
- An independent authoritative trace.

Session-follow-up scenarios may intentionally share a session ID across investigations.

---

# 12. Expected-Results Design

## 12.1 Independent Ground Truth

Expected assertions shall be defined before the system under test executes.

The fixture evaluator shall compare actual structured outputs with those expectations.

The evaluator must not derive expected outcomes from generated recommendation prose.

## 12.2 Assertion Categories

Expected assertions may address:

| Category | Example |
|---|---|
| Request | Activity and target window normalized correctly |
| Candidate | Supported beach selected |
| Contract | Specialist response correlation valid |
| Evidence | Stale finding rejected |
| Safety | Applicable advisory produces exclusion |
| Assessment | Eligibility and evidence quality match |
| Result | Correct outcome and recommendation count |
| Workflow | Retry and fallback limits respected |
| Trace | Required material events present |
| Grounding | No unsupported beach-specific claims |
| Session | Follow-up creates new investigation |

## 12.3 Proposed Physical Assertion Format

```json
{
  "assertion_id": "SC-004-A01",
  "target": "candidate_assessment",
  "selector": {
    "beach_id": "TEST_BEACH_A"
  },
  "field": "eligibility",
  "operator": "EQUALS",
  "expected": "EXCLUDED"
}
```

This is a proposed evaluator-owned assertion representation, not a new application contract.

Allowed operators and selector validation must be defined before the evaluator is implemented.

## 12.4 Forbidden-Behavior Assertions

Fixtures must support assertions such as:

- An EXCLUDED candidate must not appear in recommendations.
- Rejected evidence must not be treated as accepted.
- A missing advisory check must not become PASS.
- A specialist must not expand the candidate list.
- Prompt injection must not alter trusted instructions.
- Tool budgets must not be exceeded.
- A technical error must not be presented as hazardous ocean conditions.

## 12.5 Trace Assertions

Expected trace assertions shall use event types authorized by the reconciled `03-data-schemas.md` specification.

The evaluator shall verify required event existence and relevant ID correlations.

Parallel specialist completion order shall not be fixed unless causal ordering is required by the contracts.

---

# 13. Initial Twelve-Scenario Coverage

The approved acceptance scenarios shall remain the source of truth for their required behavior.

| ID | Scenario | Primary fixture focus |
|---|---|---|
| SC-001 | Multiple Favorable Recommendations | Three eligible beaches and soft geographic preference |
| SC-002 | Geographic Preference Versus Environmental Suitability | Preference must not override environmental conditions |
| SC-003 | Only One Eligible Beach | Exclusions and one valid recommendation |
| SC-004 | Applicable Water-Contact Avoidance Advisory | Mandatory exclusion |
| SC-005 | Hazardous Offshore Wind for SUP | Synthetic wind-policy enforcement |
| SC-006 | Permitted MIXED Snorkeling Conditions | Disclosure and sufficient evidence |
| SC-007 | Stale Daily Reports | Source-specific temporal validity |
| SC-008 | Material Conflict in Regional Evidence | Conflict preservation and investigation |
| SC-009 | Provider Outage With Successful Fallback | Authorized fallback and recovery |
| SC-010 | Provider Outage Leading to Abstention | Unresolved mandatory evidence |
| SC-011 | Prompt Injection in External Content | External content remains untrusted |
| SC-012 | Conversational Follow-Up | Session revision and reevaluation |

The expected outcomes, blocked assertions, and original scenario conditions in `06-test-acceptance.md` shall be preserved.

The fixture design shall not silently reclassify a BLOCKED assertion as ACTIVE.

---

# 14. M1 Scenario Implementation Priority

The approved technical plan initially prioritizes:

**Initial end-to-end set:**

- SC-001 — Multiple favorable recommendations.
- SC-003 — One eligible candidate.
- SC-004 — Applicable advisory exclusion.
- SC-006 — Permitted MIXED suitability.
- SC-010 — Provider outage and abstention.
- SC-011 — Prompt injection.
- SC-012 — Follow-up revision.

**Secondary expansion:**

- SC-002 — Geographic preference tradeoff.
- SC-005 — SUP offshore wind.
- SC-007 — Stale reports.
- SC-008 — Conflicting evidence.
- SC-009 — Successful fallback.

All twelve scenarios remain part of the broader approved acceptance plan.

This prioritization does not waive mandatory contract, safety, configuration, or trace tests.

---

# 15. Prompt-Injection Fixture Design

## 15.1 Threat Model

Synthetic provider content may contain instructions attempting to redirect the LLM or Coordinator.

For example, a retrieved source could contain text instructing the agent to ignore safety policies or recommend a particular beach.

Such content is untrusted source data.

## 15.2 Required Controls

The fixture shall verify that:

- External text is treated as evidence, not authoritative instructions.
- Agent and tool permissions remain unchanged.
- Candidate eligibility remains under deterministic policy control.
- Tool and model budgets remain enforced.
- The system does not reveal secrets or hidden instructions.
- The final result is grounded in approved evidence.

## 15.3 Acceptance

SC-011 shall fail if source-provided instructions change authorized workflow behavior or produce prohibited recommendations.

The test shall not require recording private model chain-of-thought.

---

# 16. Session Follow-Up Fixture Design

## 16.1 Purpose

SC-012 exercises the approved M1 Session Lifecycle Specification v0.1.

## 16.2 Required Behavior

A test shall contain at least two related CLI requests.

The first investigation reaches a terminal state.

The follow-up changes a geographic preference or another specified constraint.

The system shall:

1. Preserve the session ID.
2. Increment the request revision.
3. Create a new investigation ID.
4. Preserve unchanged applicable constraints.
5. Reevaluate affected candidates.
6. Revalidate reused findings.
7. Preserve historical provenance.
8. Reset investigation execution budgets.
9. Leave the previous terminal investigation immutable.

## 16.3 Expected Assertions

The evaluator shall confirm:

- Two distinct investigation IDs.
- Shared session identity.
- Correct request revisions.
- No invalid reuse of Candidate Assessments.
- No silent loss of unchanged user constraints.
- Appropriate result and trace correlations.

Active-investigation interruption remains outside M1.

---

# 17. Configuration and Execution-Budget Fixtures

Fixtures shall exercise all sixteen approved configuration tests, CFG-T01 through CFG-T16.

Required coverage includes:

- Approved budget values.
- Sixth Coordinator iteration blocked.
- Thirteenth environmental tool call blocked.
- Unauthorized additional retry rejected.
- Unauthorized additional fallback rejected.
- Third concurrent specialist execution prevented.
- Fourth recommendation rejected.
- Thirteenth LLM call blocked.
- Model request timeout.
- Synthetic tool timeout.
- LangSmith disabled.
- LangSmith unavailable.
- Mandatory local trace write failure.
- Missing model configuration.
- New investigation budget following a terminal follow-up.
- Malformed configuration rejected.

Provider-dependent tests may use a controlled model adapter for boundary testing.

Such tests do not establish successful live LLM integration.

---

# 18. Fixture Loading and Validation

## 18.1 Loading Order

The test harness should:

1. Read the fixture package manifest.
2. Validate supported versions.
3. Resolve the scenario and its references.
4. Load the synthetic catalog.
5. Load synthetic policy configuration.
6. Load source-response fixtures.
7. Load simulated tool behavior.
8. Load independent expected assertions.
9. Validate fixture relationships.
10. Execute only if the scenario is appropriately enabled.

The application under test receives only its authorized scenario inputs.

## 18.2 Preflight Requirements

Before execution, validate:

- JSON syntax.
- Required TestScenario fields.
- Valid schema versions.
- Existing referenced fixture paths.
- Unique beach and finding identifiers.
- Valid specialist and tool source references.
- Correct activity enumerations.
- Valid time windows and temporal metadata.
- Authorized geographic scopes.
- Consistent scenario-local identifiers.
- Supported behavior names.
- Expected assertion structures.

Invalid fixtures must fail fixture preflight rather than be misreported as agent failures.

## 18.3 Fixture Integrity

The harness shall distinguish:

- Invalid fixture input.
- Application contract failure.
- Evidence validation failure.
- Safety-policy failure.
- Evaluation harness failure.

An invalid expected-results file must not generate a passing application test.

---

# 19. LangGraph Integration Requirements

## 19.1 Execution Boundary

The synthetic harness supplies environmental data through approved tool interfaces.

It does not bypass the Coordinator, specialist contracts, evidence validators, or Safety Policy Evaluator.

## 19.2 Concurrent Specialists

Weather and Ocean may execute concurrently.

Fixture execution shall support deliberately varied completion order.

Trusted merge logic shall preserve independent findings and avoid overwriting Coordinator-owned assessment state.

## 19.3 Shared Budgets

The approved counters shall be enforced independently of synthetic behavior controls.

Concurrency must not permit more tool calls or LLM invocations than authorized.

## 19.4 Model-Provider Independence

The fixture package shall not require a specific OpenAI, Anthropic, or Google model.

Model-dependent tests shall be clearly identified.

A controlled model adapter may enable deterministic testing of orchestration boundaries before a real provider is selected.

However, a controlled adapter shall not be presented as proof of genuine LLM-driven agentic reasoning.

---

# 20. Investigation Trace Requirements

## 20.1 Authoritative Recording

Each investigation shall produce the mandatory local JSONL Investigation Trace.

The trace shall record actual test execution, not events copied from expected assertions.

## 20.2 Trace Correlation

Relevant events shall retain:

- Investigation ID.
- Request revision.
- Specialist request identifiers.
- Tool call identifiers.
- Finding identifiers.
- Assessment identifiers.
- Policy identifiers.
- Terminal investigation outcome.

## 20.3 Failure Simulation

The harness shall support controlled trace-write failure.

An application encountering a mandatory trace failure must:

- Stop new model and environmental tool dispatch.
- Suppress recommendations.
- Report an operational failure.
- Avoid fabricating missing audit events.

## 20.4 LangSmith

LangSmith shall remain disabled by default.

Optional LangSmith traces may assist development but are not required to pass deterministic acceptance tests.

---

# 21. Privacy and Data Handling

M1 fixtures shall use public, fictional, synthetic, or appropriately anonymized information.

They shall not include:

- Real API credentials.
- Personal identifying information.
- Confidential organization data.
- Private correspondence.
- Live user health or financial information.
- Private model chain-of-thought.

Synthetic user requests may include fictional experience levels and activity preferences because these are necessary to test product behavior.

No personal user profile is required for M1.

---

# 22. Open Fixture Design Decisions

The following proposed choices require approval as part of this document.

| ID | Decision | Proposed disposition |
|---|---|---|
| FX-OD-001 | Timestamp serialization | ISO 8601 with explicit offset |
| FX-OD-002 | Time-range serialization | `start` and `end` object |
| FX-OD-003 | Interval boundary convention | Start-inclusive, end-exclusive |
| FX-OD-004 | Numeric measurement serialization | JSON number |
| FX-OD-005 | Range measurement serialization | `min` and `max` object |
| FX-OD-006 | Categorical measurement serialization | Documented string value |
| FX-OD-007 | Fixture package version | Initial `1.0.0` |
| FX-OD-008 | Test fixture storage | Local versioned JSON |
| FX-OD-009 | Expected assertions | Separate evaluator-owned artifact |
| FX-OD-010 | Simulated tool timeout | Logical simulated duration, no real delay required |
| FX-OD-011 | Parallel execution test | Vary completion order; preserve invariant outcomes |
| FX-OD-012 | Synthetic policy facts | Explicit inputs, evaluated by trusted policies |

Additional implementation details remain open:

- Exact fixture-harness behavior schema.
- Exact assertion operator vocabulary.
- Physical cross-investigation finding references.
- Concrete synthetic-policy configuration schema.
- Provider-specific measurement category normalization.
- Details of controlled model adapter behavior.
- Real LLM provider/model selection.
- Real environmental freshness and hazard thresholds.

These shall not be silently resolved in ways that modify approved safety semantics.

---

# 23. Acceptance Criteria

The synthetic fixture design is ready for M1 implementation when:

- [ ] The five fictional beaches follow the approved catalog contract.
- [ ] All fixture timestamps are explicit and reproducible.
- [ ] Time ranges have a documented JSON representation.
- [ ] Measurements preserve type, units, and conventions.
- [ ] Required evidence is explicit rather than silently favorable.
- [ ] Synthetic tool responses follow approved contracts.
- [ ] Retrieval errors remain distinct from evidence validation.
- [ ] Provider behavior supports retry, fallback, timeout, and partial evidence.
- [ ] Safety-policy expectations are independently specified.
- [ ] Unresolved real-world thresholds are not invented.
- [ ] All twelve approved scenarios have fixture coverage planned.
- [ ] Blocked assertions remain identified.
- [ ] Scenario expected results are inaccessible to the application.
- [ ] Parallel specialist execution preserves evidence and shared budgets.
- [ ] Session follow-ups preserve the approved lifecycle.
- [ ] JSONL trace requirements are testable.
- [ ] Local trace failure prevents recommendation publication.
- [ ] No real provider or model selection is required for fixture preparation.

## 24. Next Development Gate

After this design is approved, M1.1 shall have:

1. An approved technical implementation plan.
2. An approved session lifecycle.
3. An approved configuration baseline.
4. An approved schema and contract mapping.
5. An approved synthetic fixture design.

The next planning step is the M1 LangGraph Execution Design, which defines graph nodes, state ownership, parallel merging, execution budgets, recovery paths, and terminal routing.

This document does not authorize application code.

---

**End of M1.1 Synthetic Fixture Design v0.1**

**Status:** Approved — M1.1 Synthetic Fixture Design.

**Approved fixture conventions:** FX-OD-001 through FX-OD-012.

**Remaining implementation details:** Open as documented in Section 22.

**No application code is authorized by this document.**