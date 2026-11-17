# Hawaii Activity Forecaster
# M1.1 Configuration Baseline

**Version:** 0.1 — Approved Baseline  
**Status:** Approved — Operational Configuration; provider selection and implementation details pending  
**Project:** CMU Agentic AI Systems Capstone  
**Milestone:** M1.1 — Project Foundations  
**Document:** `docs/implementation/m1-configuration-baseline.md`  
**Implementation authorization:** Configuration approved; no application code authorized

## 1. Purpose

This document establishes the approved development environment, execution safeguards, configuration boundaries, and error-handling requirements for M1.1.

It supplements the approved M1 Technical Implementation Plan v0.2 and M1 Session Lifecycle Specification v0.1.

It does not change the seven approved logical requirements specifications.

The initial M1 implementation will use synthetic environmental evidence to demonstrate an end-to-end agentic workflow.

Live environmental integrations remain outside M1.

## 2. Configuration Principles

**CFG-001 — Configuration-Driven Execution**

Model selection, execution limits, tool timeouts, and optional integrations shall be configurable without changing agent responsibilities.

**CFG-002 — Trusted Enforcement**

Operational limits shall be enforced by trusted application components rather than relying exclusively on LLM instructions.

**CFG-003 — Provider Independence**

The initial LLM provider and model remain undecided.

The application shall use an abstraction compatible with the approved LangGraph architecture.

**CFG-004 — Deterministic Safety**

Configuration shall not permit LLM decisions to override deterministic evidence validation, safety policies, or recommendation eligibility.

**CFG-005 — Local Auditability**

The authoritative Investigation Trace shall remain available locally without requiring LangSmith or another cloud observability service.

**CFG-006 — Controlled Failure**

Unrecoverable errors and exhaustion of execution limits must produce documented outcomes rather than fabricated recommendations.

**CFG-007 — Minimal Development Complexity**

M1 shall avoid infrastructure unnecessary for synthetic end-to-end evaluation.

---

## 3. Approved Technology Baseline

| Component | Technology | Status |
|---|---|---|
| Language | Python 3.12+ | Approved technical direction |
| Orchestration | LangGraph | Approved |
| Agent roles | Coordinator, Weather, Ocean | Approved |
| Model interface | LangChain-compatible adapter | Approved technical direction |
| Schema validation | Pydantic v2 | Approved technical direction |
| Synthetic data | Versioned JSON fixtures | Approved for M1 |
| Beach Catalog | Local JSON | Approved for M1 |
| CLI | Python terminal application | Approved for M1 |
| Testing | pytest | Approved technical direction |
| Authoritative trace | Local JSONL | Required |
| Developer observability | LangSmith | Optional |
| Dependency management | `uv` with committed lockfile | Approved for M1.1 |

No application database server, production API gateway, or cloud deployment is required for M1.

---

## 4. Python Environment and Dependency Management

### 4.1 Approved Tooling

Use `uv` for Python environment and dependency management.

The project shall maintain:

- A project dependency manifest.
- A committed dependency lockfile.
- A documented Python version requirement.
- Separated development and runtime dependencies.
- Reproducible installation instructions.

### 4.2 Version Management

Runtime dependencies should use compatible pinned versions resolved through the lockfile.

Major framework upgrades must not be adopted automatically without validation.

Material LangGraph, LangChain, or Pydantic updates should trigger regression testing of affected contracts and workflows.

### 4.3 Local Environment

The development environment shall support:

- macOS development.
- Local command-line execution.
- Isolated Python dependencies.
- Environment-specific configuration.
- Synthetic test execution without live environmental providers.

Platform-specific dependency assumptions shall be documented.

---

## 5. LLM Provider Configuration

### 5.1 Provider Status

The initial LLM provider is intentionally undecided.

Potential providers include OpenAI, Anthropic, and Google, but no provider is authorized as the M1 default by this specification.

The application shall not silently select a provider based on installed packages or available credentials.

### 5.2 Provider Abstraction

The model integration should support:

- Configurable provider selection.
- Configurable model identifier.
- Structured response handling.
- Tool-calling support where required.
- Model invocation limits.
- Request timeouts.
- Error classification.
- Optional usage and latency reporting.

The final provider must support the agent behaviors and structured contracts needed by M1.

### 5.3 Provider Activation

Before invoking a real model provider, the project must establish:

1. Provider and model identifier.
2. API credentials or another authorized access method.
3. Billing and usage expectations.
4. Required structured-output capabilities.
5. Tool-calling compatibility.
6. Error and timeout behavior.
7. Relevant data-handling expectations.

API credentials shall not be embedded in source code, fixtures, or committed configuration files.

### 5.4 Provider-Neutral Development

Deterministic schema, policy, configuration, and fixture tests should not require access to a live model provider.

Provider-dependent integration tests may remain blocked until the initial provider is selected.

This must not be reported as successful validation of the complete agentic workflow.

---

## 6. Approved Investigation Limits

The following M1 limits have already been approved and remain unchanged.

| Setting | Limit | Scope |
|---|---:|---|
| Coordinator investigation iterations | 5 | Per investigation |
| External environmental tool invocations | 12 | Per investigation |
| Retries | 1 | Per failed original tool invocation |
| Fallback attempts | 1 | Per required evidence gap |
| Concurrent specialist executions | 2 | Per investigation |
| Recommendations | 3 | Per final result |

### 6.1 Enforcement

Limits shall be checked through trusted orchestration components.

External tool-call budgets include retry and fallback invocations.

Budget accounting shall remain correct under parallel specialist execution.

A retry or fallback cannot bypass the overall investigation budget.

### 6.2 Investigation Scope

Each new investigation receives fresh counters.

Post-terminal follow-ups use the existing session ID, increment the request revision, and create a new investigation ID.

Previous terminal investigations remain immutable.

Active-investigation interruption and cancellation remain deferred.

---

## 7. Approved LLM Execution Safeguards

The following safeguards are approved for M1.1.

### 7.1 LLM Invocation Limit

**Approved value:** 12 model invocations per investigation.

A model invocation is a request dispatched to the configured LLM provider.

The count includes:

- Coordinator model calls.
- Weather Agent model calls.
- Ocean Agent model calls.
- Model-level retries, if separately authorized.

The limit is shared across all three agents within the investigation.

A request consumes budget when dispatched, regardless of its outcome.

This budget is independent of the approved twelve-call external environmental tool limit.

### 7.2 Model Request Timeout

**Approved value:** 30 seconds per LLM invocation.

Requests exceeding the timeout shall be treated as failed invocations.

A timeout must not produce an assumed model response.

Automatic model-call retry behavior is not independently authorized by this configuration.

Model retry policy remains an open decision.

### 7.3 Budget Exhaustion

When the model invocation budget is exhausted:

1. No additional model calls may be dispatched.
2. The limitation must be recorded.
3. Existing validated evidence and assessments must be preserved.
4. The application must determine whether it can produce a valid result without further model execution.
5. If it cannot complete safely and correctly, it must return the appropriate documented abstention or technical failure.

Exhaustion does not establish an environmental hazard.

### 7.4 Token and Financial Limits

Exact token limits, monetary budgets, and model cost ceilings remain open pending provider selection.

The implementation shall not invent provider-specific values.

These settings may be added without changing the three-agent architecture.

---

## 8. Approved Synthetic Tool Execution Safeguards

### 8.1 Tool Timeout

**Approved value:** 10 seconds per synthetic external-tool invocation.

A timed-out invocation shall produce a structured failure.

The Coordinator may investigate an approved fallback or retry within the existing budgets.

### 8.2 Tool Failure

A failed tool invocation shall not automatically fail the entire investigation.

Possible outcomes include:

- Use other sufficient accepted evidence.
- Retry an authorized operation.
- Attempt one approved fallback for the relevant evidence gap.
- Investigate another supported candidate.
- Return an explained abstention.

No missing environmental information may be fabricated.

### 8.3 Synthetic Versus Live Tools

M1 shall use fixture-backed tool adapters.

The same logical tool contracts should support future live adapters, but this does not establish approval for live retrieval.

Actual provider timeouts, rate limits, and usage restrictions remain future integration decisions.

---

## 9. LangGraph Runtime Safeguards

### 9.1 Graph Execution

LangGraph shall orchestrate the Coordinator workflow through explicit nodes, edges, and conditional routing.

The approved five-iteration investigation budget remains the authoritative application-level iteration limit.

Framework execution limits may provide additional protection but shall not replace it.

### 9.2 Shared State

The logical Investigation State schema remains authoritative.

LangGraph runtime state may represent that schema using framework-compatible structures.

Specialists shall not directly overwrite authoritative Candidate Assessments or policy decisions.

### 9.3 Concurrent Execution

The trusted orchestration layer shall enforce a maximum of two concurrent specialist executions.

Parallel state merges must preserve:

- Source identifiers.
- Finding identifiers.
- Request and response correlations.
- Conflicting findings.
- Outstanding evidence gaps.

### 9.4 Runtime Exceptions

Unexpected graph exceptions shall be captured and classified.

The system shall not convert a framework exception into an apparently successful environmental recommendation.

### 9.5 Checkpointing

Persistent LangGraph checkpointing is not required for M1.

Any future checkpointing mechanism must preserve application-level session and investigation identifiers.

Framework thread and checkpoint identifiers shall not silently replace those identifiers.

---

## 10. Observability Configuration

### 10.1 Authoritative Local Trace

The application shall maintain an append-only Investigation Trace using local JSON Lines.

Trace events must conform to the authoritative event enumeration defined in `03-data-schemas.md`.

Events shall preserve relevant request, specialist, tool, finding, candidate, and policy correlation references.

### 10.2 LangSmith

LangSmith remains optional.

The default configuration shall not transmit execution traces to LangSmith.

When intentionally enabled for development:

- Synthetic or appropriately sanitized inputs should be used.
- Secrets and credentials must not be transmitted.
- Unnecessary personal information must be excluded.
- Private model chain-of-thought must not be recorded.
- Trace costs and service configuration should be reviewed.

LangSmith availability shall not be required for correct safety-policy enforcement.

### 10.3 Trace Integrity

Local trace events shall represent actual observable behavior.

The system shall not invent missing events after execution.

A trace-validation failure must remain distinguishable from a successful investigation.

---

## 11. Approved Local Trace Write-Failure Policy

### 11.1 Failure Policy

**Approved behavior:** Fail closed when the required authoritative trace cannot be maintained.

If the application cannot reliably append mandatory trace events:

1. Stop dispatching new model and environmental tool operations.
2. Do not publish an unverified recommendation.
3. Preserve any already valid local state.
4. Report an operational failure through a safe error-handling path.
5. Avoid inventing missing trace events.

### 11.2 Startup Validation

Before beginning an investigation, the application shall verify that the configured trace destination is usable.

A startup check does not guarantee that future writes will succeed.

Runtime write errors must still be handled.

### 11.3 During Investigation

A mandatory trace-write failure shall prevent further recommendation-producing execution until the logging issue is resolved.

The application may display a concise technical error message.

The error message must not claim that the ocean conditions were unsafe.

### 11.4 LangSmith Independence

A LangSmith outage does not constitute a failure of the required local Investigation Trace.

Optional LangSmith failures shall not independently block valid local execution.

---

## 12. Configuration Security

### 12.1 Secrets

Credentials and authentication tokens shall be obtained from approved local environment or secret-management mechanisms.

Secrets shall not be committed to the repository.

### 12.2 Configuration Validation

Before executing affected operations, the application shall validate:

- Required configuration fields.
- Authorized provider selection.
- Model identifier presence when real-model execution is enabled.
- Approved investigation limits.
- Valid positive timeout values.
- Trace-storage configuration.
- Synthetic fixture availability.

Invalid configuration shall prevent affected operations from executing.

### 12.3 Safe Defaults

M1 shall default to:

- Synthetic environmental evidence.
- No live environmental retrieval.
- LangSmith disabled.
- Approved investigation budgets.
- Local authoritative trace storage.
- No external mutation or transaction tools.

---

## 13. Test Requirements

The M1.1 configuration layer shall support deterministic tests for:

| ID | Test | Expected outcome |
|---|---|---|
| CFG-T01 | Approved investigation budgets loaded | Correct values |
| CFG-T02 | Coordinator attempts sixth investigation iteration | Dispatch blocked |
| CFG-T03 | Thirteenth external environmental tool invocation | Dispatch blocked |
| CFG-T04 | Second retry of the same failed original invocation | Rejected |
| CFG-T05 | Second fallback for the same evidence gap | Rejected |
| CFG-T06 | Third concurrent specialist execution | Not permitted concurrently |
| CFG-T07 | More than three final recommendations | Result validation fails |
| CFG-T08 | Thirteenth LLM invocation | Rejected |
| CFG-T09 | LLM request exceeds configured timeout | Structured failure |
| CFG-T10 | Synthetic tool exceeds configured timeout | Structured failure |
| CFG-T11 | LangSmith disabled | No LangSmith transmission |
| CFG-T12 | LangSmith unavailable | Local audit remains functional |
| CFG-T13 | Local trace cannot be written | Recommendation suppressed |
| CFG-T14 | Missing model configuration | Provider-dependent execution blocked |
| CFG-T15 | User submits post-terminal follow-up | New investigation and fresh budget |
| CFG-T16 | Malformed configuration | Validation failure before affected operation |

All sixteen configuration tests are approved as requirements.

Tests requiring a real LLM provider shall remain BLOCKED until that provider is selected.

---

## 14. Remaining Open Decisions

| ID | Decision | Status |
|---|---|---|
| CFG-OD-001 | Initial LLM provider | Open |
| CFG-OD-002 | Model identifier | Open |
| CFG-OD-003 | Provider-specific model retries | Open |
| CFG-OD-004 | Token and monetary budgets | Open |
| CFG-OD-005 | Whole-investigation wall-clock deadline | Open |
| CFG-OD-006 | CLI session expiration | Deferred |
| CFG-OD-007 | Session persistence across restarts | Deferred |
| CFG-OD-008 | Active-investigation cancellation | Deferred |
| CFG-OD-009 | Cross-investigation evidence storage | Open |
| CFG-OD-010 | Detailed trace retention and cleanup | Open |

These decisions shall not be silently filled using framework defaults when doing so would change approved behavior or safety requirements.

---

## 15. M1.1 Readiness Gate

The following configuration requirements are approved:

1. The six investigation limits remain unchanged.
2. Dependency management uses `uv` with a committed lockfile.
3. The shared model invocation budget is twelve per investigation.
4. Model requests have a thirty-second timeout.
5. Synthetic environmental tool invocations have a ten-second timeout.
6. Local trace write failures prevent publishing recommendations.
7. Configuration validation occurs before affected operations.
8. The initial LLM provider and model remain explicitly undecided.
9. Synthetic-only execution remains separate from live environmental integrations.
10. The approved session lifecycle remains unchanged.
11. No additional autonomous agents or unsupported MVP capabilities are introduced.

These requirements are approved for M1.1 implementation planning.

Provider-dependent execution remains blocked until the required provider and model decisions are resolved.

## 16. Specification Status

The following are established:

- Seven approved logical requirements specifications.
- Approved M1 Technical Implementation Plan v0.2.
- Approved M1 Session Lifecycle Specification v0.1.
- Six approved M1 investigation limits.
- Six approved M1.1 operational safeguards.

The M1.1 operational configuration baseline is approved.

Remaining open decisions are documented in Section 14.

This approval does not authorize application code.

---

**End of M1.1 Configuration Baseline v0.1**

**Status:** Approved — Operational Configuration; provider selection and implementation details pending.

**No application code is authorized by this document.**