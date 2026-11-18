# M1.1-C configuration and budget validation

This increment implements the configuration layer of the approved
`docs/implementation/m1-configuration-baseline.md` v0.1. It does not revise that
baseline, implement a Budget Manager, or satisfy every runtime configuration gate.

## API and organization

- `config/settings.py`: Pydantic configuration models and structural validation.
- `config/loading.py`: explicit TOML/environment loading and `ConfigurationError`.
- `haf.example.toml`: reviewable example containing the approved defaults.
- `tests/test_config.py`: deterministic configuration tests using synthetic values.

```python
from hawaii_activity_forecaster.config import AppConfig, load_config

settings = AppConfig()  # defaults only; no environment or file access
settings = load_config("haf.example.toml")  # defaults < TOML < HAF_ variables
settings = load_config(environ={})  # defaults; ignore the process environment
```

The information CLI continues to work without configuration. This increment does
not add an investigation command or implicitly connect configuration to execution.

## Approved settings

| Setting | Approved value | Scope |
|---|---:|---|
| `limits.max_coordinator_iterations` | 5 | Per investigation |
| `limits.max_environmental_tool_invocations` | 12 | Per investigation, including retries/fallbacks |
| `limits.max_retries_per_failed_invocation` | 1 | Per failed original environmental invocation |
| `limits.max_fallback_attempts_per_evidence_gap` | 1 | Per required evidence gap |
| `limits.max_concurrent_specialists` | 2 | Per investigation |
| `limits.max_recommendations` | 3 | Per final result |
| `limits.max_llm_invocations` | 12 | Shared across the three agents, per investigation |
| `timeouts.llm_request_seconds` | 30 | Per model invocation |
| `timeouts.synthetic_tool_seconds` | 10 | Per synthetic environmental invocation |

These nine fields validate the exact baseline values as strict integers. Both
increases and reductions are rejected rather than silently changing the approved
baseline. Boolean, string, floating-point, null, and nonfinite values are rejected.
Changing this configuration validation policy requires an approved baseline
revision; these classes do not count calls or enforce elapsed time.

Other defaults:

- `environment.mode = "synthetic"`; live environmental retrieval is not supported.
- `llm.enabled = false`; provider and model identifier remain `None`.
- `trace.directory = "traces"`, `trace.format = "jsonl"`, and
  `trace.write_failure_policy = "fail_closed"`.
- `langsmith.enabled = false`.

`llm.provider` and `llm.model_identifier` can hold explicit, nonempty future
configuration metadata while disabled. `llm.enabled = true` is rejected: missing
provider/model fields produce a configuration error, and populated fields still
cannot bypass the unresolved provider-activation review and integration work.
No provider allowlist, credentials, retry policy, token budget, monetary budget,
whole-investigation deadline, or safety-policy override is invented.

A LangSmith flag can be explicitly set to true as configuration data. No tracing
integration, client, environment mutation, or transmission occurs. It does not
stand in for the required data-handling, credentials, costs, and sanitization
review before future integration is used.

## Loading and precedence

`AppConfig()` validates defaults only. `load_config()` reads the process environment
by default but does not search for files. A TOML file is read only when explicitly
passed; a missing or malformed requested file is an error. Standard-library
`tomllib` is used; no new dependency or automatic `.env` reader is added.

The six supported environment variables are:

| Variable | Configuration field |
|---|---|
| `HAF_ENVIRONMENT_MODE` | `environment.mode` |
| `HAF_LLM_ENABLED` | `llm.enabled` |
| `HAF_LLM_PROVIDER` | `llm.provider` |
| `HAF_LLM_MODEL_IDENTIFIER` | `llm.model_identifier` |
| `HAF_TRACE_DIRECTORY` | `trace.directory` |
| `HAF_LANGSMITH_ENABLED` | `langsmith.enabled` |

Boolean variables accept only case-insensitive `true` or `false`, with no implicit
numeric or whitespace conversion. Unknown `HAF_` variables are rejected to catch
misspellings. SDK variables such as `LANGSMITH_TRACING`, `LANGCHAIN_TRACING_V2`,
or provider credential variables are not read or changed by this loader. Their
presence never selects a provider or changes application defaults.

A supplied environment mapping replaces the process environment for this lookup.
Precedence is defaults, then explicit TOML, then supported environment variables.
Unknown configuration fields are rejected at every typed level.

Relative trace paths are anchored to the containing directory of the supplied
TOML file, or the working directory if no file was supplied. This includes paths
provided through an environment override. Absolute paths are preserved. The
loader does not expand `~`, substitute shell variables, check writability, or
create a destination. Blank, null-byte, nonpath, and URI-form destinations are
rejected. A directory need not exist yet; startup preflight remains future work.

Models prevent attribute reassignment and revalidate nested instances. Do not use
Pydantic `model_construct` or `model_copy(update=...)` as validation for untrusted
input. `load_config()` wraps parsing/validation failures in `ConfigurationError`
without echoing input values or TOML snippets. Credentials have no settings fields
and must not be placed in tracked configuration.

## Acceptance mapping and remaining work

| Approved test | M1.1-C coverage |
|---|---|
| CFG-T01 | Approved budget and timeout defaults loaded and tested |
| CFG-T02–T06 | Settings validated; iteration/call/retry/fallback/concurrency dispatch guards deferred |
| CFG-T07 | Three-recommendation setting validated; structural result-count checks already exist in M1.1-B |
| CFG-T08–T10 | Model-call cap/timeouts validated; dispatch accounting, timers and structured timeout failures deferred |
| CFG-T11 | Default disabled flag and side-effect-free configuration loading tested; full execution tracing test deferred |
| CFG-T12–T13 | Local JSONL/fail-closed settings validated; outage handling, destination preflight and runtime write-failure suppression deferred |
| CFG-T14 | Enabling unconfigured real-model execution rejected; all real-model activation remains unavailable |
| CFG-T15 | Per-investigation scope retained in settings; session lifecycle/counter reset tests deferred |
| CFG-T16 | Invalid file/environment/nested settings rejected before configuration is returned |

No blocked runtime test is represented by a dummy passing test or included in the
configuration pass count. Future orchestration must enforce atomic shared budgets,
count failed/timed-out dispatches, scope retries and fallbacks properly, and give
each new investigation fresh counters. A future trace component must check the
destination before investigation startup and fail closed on mandatory write errors.

The remaining configuration baseline decisions (provider/model, model retry
policy, costs/tokens, overall deadline, retention, and session persistence) remain
open or deferred. Fixture availability is not validated here because the versioned
fixture package and loader have not yet been implemented.

## Verification

```bash
uv sync --locked
uv run --locked pytest tests/test_config.py
uv run --locked pytest
```

The next foundation increment is synthetic fixture loading and validation, before
M1.2 LangGraph execution. Approved requirements/implementation specifications,
dependencies, workflows, and the existing CLI are unchanged by M1.1-C.
