# Hawaii Activity Forecaster
# M1 Technical Implementation Plan

**Version:** 0.2 — LangGraph and LangSmith  
**Status:** Approved — Technical Implementation Plan  
**Milestone:** M1 — Synthetic End-to-End Forecaster  
**Implementation authorization:** Technical plan approved; application code not yet authorized

## 1. Purpose

This document defines the approved technical approach for Milestone M1 of the Hawaii Activity Forecaster.

M1 demonstrates an end-to-end agentic workflow using synthetic environmental evidence.

The architecture shall:

- Use LangGraph for agent orchestration.
- Preserve the Coordinator, Weather, and Ocean agent roles.
- Use structured and validated agent communication.
- Implement deterministic evidence and safety enforcement.
- Maintain the approved bounded ReAct investigation model.
- Produce locally auditable execution traces.
- Support optional LangSmith tracing and evaluation.
- Pass representative synthetic acceptance scenarios.

This plan does not modify the seven existing requirements specifications.

## 2. Technology Recommendations

| Component | Recommended technology | Status |
|---|---|---|
| Programming language | Python 3.12+ | Approved technical direction |
| Agent orchestration | LangGraph | Approved |
| LLM integration | LangChain-compatible chat model | Approved technical direction |
| LLM provider | To be selected | Open |
| Schema validation | Pydantic v2 | Approved technical direction |
| Beach Catalog | Local JSON | Approved for M1 |
| Synthetic environmental data | Versioned JSON fixtures | Approved for M1 |
| CLI | Python terminal application | Approved for M1 |
| Authoritative observability | Local JSON Lines | Required by specifications |
| Developer tracing | LangSmith | Optional |
| Deterministic testing | pytest | Approved technical direction |
| Environment configuration | Local configuration and environment variables | Approved technical direction |

No cloud deployment, application database server, or vector database is required for M1.

## 3. LangGraph Orchestration

LangGraph shall provide the execution structure for the Coordinator workflow.

The implementation should use its graph-state, node, conditional-routing, and parallel-execution capabilities.

LangGraph is responsible for orchestration mechanics, not for independently determining environmental safety.

### 3.1 Coordinator Graph Responsibilities

The Coordinator graph shall support:

1. Request normalization.
2. Candidate beach selection.
3. Evidence planning.
4. Scoped specialist delegation.
5. Specialist response collection.
6. Contract and evidence validation.
7. Candidate safety evaluation.
8. Conditional follow-up investigation.
9. Recommendation comparison.
10. Result validation.
11. Terminal outcome determination.

The graph may loop through approved investigative steps, subject to enforced limits.

### 3.2 Proposed Logical Graph Nodes

| Node | Responsibility | Execution type |
|---|---|---|
| Request Normalization | Interpret activity, time, and constraints | LLM-assisted with validation |
| Candidate Selection | Select supported beaches | Deterministic |
| Evidence Planning | Identify outstanding evidence needs | Coordinator decision |
| Weather Investigation | Collect scoped weather evidence | Specialist agent |
| Ocean Investigation | Collect scoped ocean evidence | Specialist agent |
| Contract Validation | Validate specialist interfaces | Deterministic |
| Evidence Validation | Assess source, time, geography, and measurements | Deterministic |
| Safety Evaluation | Apply documented policies | Deterministic |
| Investigation Decision | Continue, fallback, or conclude | Coordinator decision with enforced limits |
| Candidate Comparison | Qualitatively compare eligible beaches | Coordinator decision |
| Result Validation | Verify grounding and eligibility | Deterministic |
| Final Presentation | Render validated result | CLI |

Graph nodes are execution components, not additional autonomous agent roles.

### 3.3 Parallel Specialist Execution

Weather and Ocean investigations may execute concurrently.

Maximum specialist concurrency is two.

Responses shall be validated and merged through trusted components.

LangGraph parallel branches must not independently overwrite shared Coordinator-owned assessments.

State updates shall preserve evidence provenance, identifiers, and conflicting findings.

### 3.4 Bounded ReAct

The Coordinator may iteratively:

1. Examine current investigation evidence.
2. Identify unresolved questions.
3. Select an authorized action.
4. Delegate a scoped investigation.
5. Receive and validate results.
6. Reevaluate candidates.
7. Decide whether to continue.

The application enforces a maximum of five Coordinator investigation iterations.

A framework-level recursion or execution safeguard may provide additional protection but shall not replace the approved application-level budget.

## 4. Agent Implementation Boundaries

### 4.1 Coordinator

The Coordinator may use LLM reasoning for:

- Natural-language interpretation.
- Evidence-planning decisions.
- Choosing authorized next investigative steps.
- Qualitative candidate comparison.
- Explanation generation.

The Coordinator may not override deterministic policy results or create evidence.

### 4.2 Weather Agent

The Weather Agent receives scoped tasks and accesses authorized weather tools.

For M1, those tools return controlled synthetic findings.

The specialist must use the approved SpecialistInvestigationRequest and SpecialistInvestigationResponse contracts.

### 4.3 Ocean Agent

The Ocean Agent receives scoped marine and ocean tasks.

For M1, its tools return synthetic surf, swell, visibility, advisory, and related evidence.

The specialist must preserve source metadata and report missing information.

### 4.4 Agentic Behavior

M1 shall demonstrate actual agentic decision-making and controlled tool delegation, rather than merely hardcoding a complete predetermined recommendation.

Synthetic fixtures control the environmental evidence and expected policy outcomes.

They do not dictate every Coordinator reasoning step or final explanation.

However, deterministic acceptance tests must remain reproducible and must not depend on nondeterministic wording.

## 5. Investigation State and LangGraph State

The logical Investigation State schema defined in `03-data-schemas.md` remains authoritative.

LangGraph state is the runtime representation used to execute the workflow.

The implementation may adapt logical records into graph-state structures, provided no approved fields or meanings are silently changed.

### 5.1 State Ownership

The Coordinator or trusted orchestration components control state mutation.

Specialists return structured responses rather than directly updating eligibility.

### 5.2 Concurrency

Concurrent branches require explicit merge semantics.

Independent findings shall be preserved.

Conflicting findings shall remain available for validation rather than being overwritten according to completion order.

### 5.3 Session Lifecycle

Use the approved M1 Session Lifecycle Specification v0.1:

- One continuing session ID for related CLI interactions.
- One new investigation ID for each post-terminal follow-up.
- Incrementing session request revisions.
- Immutable terminal investigations.
- Validated reuse of previous environmental findings.
- Fresh execution budgets per investigation.

LangGraph execution identifiers and any framework checkpoint/thread identifiers must remain distinct from application identifiers unless an explicit documented mapping is established.

### 5.4 Persistence

Persistent LangGraph checkpointing is not required for M1 if the CLI can preserve active-session context and complete each investigation synchronously.

Checkpointing may be added later if needed for recovery, interruption, or more advanced session behavior.

No checkpoint or persistence feature shall silently reopen an already terminal investigation.

## 6. Approved M1 Operational Limits

| Limit | Approved value |
|---|---:|
| Coordinator investigation iterations | 5 |
| External environmental tool invocations | 12 |
| Retries per failed original invocation | 1 |
| Fallback attempts per required evidence gap | 1 |
| Concurrent specialist executions | 2 |
| Recommendations in final result | 3 |

The limits shall be enforced by trusted application components.

Tool-call counts include retry and fallback invocations.

Concurrent dispatch shall not bypass the shared investigation budget.

Exact runtime deadlines and LLM token budgets remain open.

## 7. Pydantic and Contract Validation

Pydantic v2 is the approved technical direction for runtime validation of the existing logical schemas.

The implementation should provide validated representations of:

- Beach Catalog records.
- Environmental Findings.
- Candidate Assessments.
- Investigation State.
- Recommendation Results.
- Investigation Trace events.
- Specialist request and response contracts.
- External tool request and response contracts.

Models must implement approved fields and enums rather than redefining them.

Pydantic validation does not independently determine environmental truth or safety.

Evidence validity and safety policy evaluation remain separate operations.

## 8. Synthetic Evidence Infrastructure

M1 uses local synthetic fixtures instead of live environmental providers.

Each synthetic source adapter should behave like its future live counterpart at the contract boundary.

Fixtures should support:

- Successful retrieval.
- Partial retrieval.
- Missing evidence.
- Stale evidence.
- Geographic mismatches.
- Contradictory findings.
- Official advisory scenarios.
- Tool failures and timeouts.
- Unauthorized source content.
- Retry and fallback behavior.

Fixture timestamps shall use a fixed reference time during deterministic testing.

Fictional beaches must not be presented as actual Maui environmental assessments.

## 9. Deterministic Safety Enforcement

Safety enforcement remains independent of LLM reasoning.

Trusted policy functions shall:

- Validate mandatory evidence.
- Evaluate applicable policy outcomes.
- Enforce exclusions.
- Preserve unresolved mandatory questions.
- Determine candidate eligibility.
- Validate permitted MIXED suitability.
- Enforce explicit hard constraints.

LangGraph may route execution based on the resulting assessment state.

It must not independently override that state.

Undefined real-world hazard thresholds shall not be invented for M1.

## 10. Observability Architecture

M1 uses two complementary layers.

### 10.1 Local Investigation Trace

Local JSON Lines is the authoritative application trace.

It shall record the events and correlations required by `03-data-schemas.md` and `07-observability.md`.

The trace shall include:

- Investigation identity and request revision.
- Specialist execution.
- Tool invocations and failures.
- Contract validation.
- Evidence validation.
- Policy outcomes.
- Candidate assessment changes.
- Retry and fallback actions.
- Execution limits.
- Final outcome.

The application trace must remain available when LangSmith is disabled or unavailable.

### 10.2 Optional LangSmith Integration

LangSmith may be enabled during development to visualize:

- LangGraph node execution.
- Agent delegation.
- Model calls.
- Tool operations.
- Latency and token usage.
- Execution failures.
- Comparative evaluations.

LangSmith is supplementary and shall not replace mandatory local audit events.

### 10.3 Tracing Privacy and Controls

LangSmith tracing shall be disabled by default for M1 until its data-handling configuration is reviewed.

When tracing is enabled:

- Only synthetic or appropriately sanitized information should be transmitted.
- Credentials and secrets shall not be recorded.
- Unnecessary user details shall be excluded.
- Private model chain-of-thought shall not be logged.
- Trace metadata should include safe investigation and scenario identifiers.
- Tracing configuration and any service costs shall be reviewed.

LangSmith failures must not disable mandatory local evidence and safety enforcement.

## 11. Evaluation Strategy

The primary acceptance mechanism remains pytest with synthetic fixtures.

The approved twelve synthetic scenarios provide the broader evaluation baseline.

M1 initially prioritizes:

- SC-001 — Multiple favorable recommendations.
- SC-003 — One eligible candidate.
- SC-004 — Water-contact advisory exclusion.
- SC-006 — Permitted MIXED snorkeling.
- SC-010 — Provider outage and abstention.
- SC-011 — External prompt injection.
- SC-012 — Conversational follow-up.

Each scenario shall verify:

- Relevant structured records.
- Approved contract usage.
- Evidence-validation outcomes.
- Safety-policy results.
- Recommendation eligibility.
- Execution-budget compliance.
- Required Investigation Trace events.

### 11.1 LangSmith Evaluation

LangSmith evaluation may supplement pytest by supporting:

- Trace inspection.
- Comparison of agent approaches.
- Evaluation datasets.
- Regression analysis.
- Explanation-quality review.

LangSmith-based evaluation is optional for M1.

It shall not replace deterministic acceptance tests or establish real-world safety validity.

## 12. Proposed Project Organization

The following is a logical module outline, not a mandate for exact filenames.

| Area | Proposed content |
|---|---|
| `cli/` | CLI interaction and session handling |
| `agents/` | Coordinator, Weather, Ocean agent responsibilities |
| `graph/` | LangGraph workflow and routing |
| `schemas/` | Pydantic representations of approved contracts |
| `catalog/` | Beach Catalog access and validation |
| `tools/` | Synthetic and future live source adapters |
| `validation/` | Contracts and environmental evidence validation |
| `policies/` | Deterministic safety and eligibility evaluation |
| `recommendations/` | Candidate comparison and result validation |
| `observability/` | JSONL trace generation and optional LangSmith integration |
| `fixtures/` | Synthetic beach and environmental inputs |
| `tests/` | Unit, contract, and end-to-end acceptance tests |
| `config/` | Provider definitions, budgets, and runtime configuration |

No separate service or deployment infrastructure is required for each directory.

## 13. Proposed Development Sequence

### M1.1 — Project Foundations

- Establish Python development environment.
- Select the LLM provider.
- Establish dependency management.
- Implement approved logical schema validation.
- Establish synthetic fixture loading.
- Define configuration and budget validation.

**Exit criterion:** Schemas, configuration, and fixtures can be validated independently.

### M1.2 — LangGraph Investigation Skeleton

- Establish Coordinator workflow.
- Define graph state.
- Support Weather and Ocean delegation.
- Support parallel specialist execution.
- Define conditional routing and loop termination.
- Enforce initial execution budgets.

**Exit criterion:** A synthetic investigation traverses the intended graph and terminates within approved limits.

### M1.3 — Synthetic Specialists and Tools

- Implement scoped specialist contracts.
- Provide controlled synthetic tool results.
- Support partial results, errors, and fallback.
- Preserve request and attempt correlation.

**Exit criterion:** Synthetic specialist investigations satisfy contract tests.

### M1.4 — Evidence and Safety Enforcement

- Implement evidence validation.
- Implement documented synthetic policy outcomes.
- Produce Candidate Assessments.
- Enforce eligibility and abstention.

**Exit criterion:** Mandatory safety tests pass independently of generated prose.

### M1.5 — Recommendation and CLI

- Compare eligible candidates.
- Produce validated Recommendation Results.
- Render CLI responses.
- Support post-terminal follow-up revisions.

**Exit criterion:** The CLI supports the approved request and follow-up workflows.

### M1.6 — Observability and Acceptance

- Produce authoritative local JSONL traces.
- Validate trace completeness.
- Add optional LangSmith tracing.
- Run representative synthetic scenarios.
- Summarize failures and blocked assertions.

**Exit criterion:** M1 acceptance criteria pass and execution is auditable.

## 14. Explicit M1 Exclusions

M1 does not require:

- Live weather or ocean providers.
- Real-time ocean recommendations.
- Verified real-beach catalog completion.
- Real-world numeric hazard thresholds.
- Remote deployment.
- Persistent user accounts.
- Vector RAG.
- Tree-of-Thought exploration.
- Additional autonomous agents.
- Active-investigation interruption.
- Production LangGraph checkpoint persistence.
- Mandatory LangSmith availability.

## 15. Open Technical Decisions

| ID | Decision | Status |
|---|---|---|
| TECH-001 | Python as implementation language | Approved technical direction |
| TECH-002 | LangGraph as orchestration framework | Approved |
| TECH-003 | Pydantic v2 for schema validation | Approved technical direction |
| TECH-004 | Model provider and specific model | Open |
| TECH-005 | Local JSON fixture organization | Approved for M1 |
| TECH-006 | Beach Catalog physical storage as JSON | Approved for M1 |
| TECH-007 | Dependency and environment management | Open |
| TECH-008 | LLM invocation and token budgets | Open |
| TECH-009 | Runtime timeout limits | Open |
| TECH-010 | LangSmith tracing configuration and data handling | Optional; configuration pending |
| TECH-011 | LangGraph checkpointing strategy | Deferred for M1 |
| TECH-012 | Trace storage-failure handling | Open |

## 16. M1 Completion Criteria

M1 is complete when:

1. The CLI accepts supported activity requests.
2. LangGraph executes the Coordinator workflow.
3. Weather and Ocean specialists operate through approved contracts.
4. Specialist concurrency remains within the approved limit.
5. Tool invocations, retries, and fallbacks remain bounded.
6. Synthetic findings preserve required metadata.
7. Evidence-validation rules are enforced.
8. Deterministic policies govern candidate eligibility.
9. Only supported eligible candidates are recommended.
10. Unresolved mandatory evidence results in appropriate abstention.
11. Conversational follow-ups use the approved session lifecycle.
12. Recommendation Results pass schema and grounding validation.
13. Local Investigation Traces satisfy required event assertions.
14. LangSmith is optional and does not affect correctness when disabled.
15. The selected M1 synthetic acceptance scenarios pass their executable scope.

---

**End of M1 Technical Implementation Plan v0.2**

**Status:** Approved — Technical Implementation Plan

**No application code has been authorized by this document.**