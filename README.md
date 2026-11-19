
# Hawaii Activity Forecaster

Capstone project for Carnegie Mellon University's
Agentic AI Systems program.

## Objective

Recommend suitable Maui locations and times for
swimming, snorkeling, and stand-up paddleboarding
using environmental evidence, verified geographic
information, and user preferences.

## Architecture

- Coordinator Agent: supervision and ReAct workflow
- Weather Agent: weather forecasts and advisories
- Ocean Agent: marine conditions and hazards
- Local JSON: curated beach catalog (approved M1 storage)
- Deterministic safety and evidence validation

## Current Status

M1.3-B — Scoped Synthetic Tool Dispatch. The graph can execute explicitly planned
synthetic environmental calls with shared budget accounting, bounded retries and
fallbacks, and observed template/runtime identity bindings. SC-004/SC-010 remain
execution-blocked. Independent evidence/safety/result evaluation, authoritative
JSONL tracing and environmental recommendations remain for later increments.
The LLM provider/model is undecided.

## Documentation

See [requirements](docs/requirements/) and [implementation plans](docs/implementation/)
for the approved specifications.


## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use Python
3.12 or newer. From the repository root:

```bash
uv sync --locked
uv run --locked hafi
uv run --locked hafi --version
uv run --locked python -m hawaii_activity_forecaster
uv run --locked pytest
```

`uv sync --locked` installs the package, runtime dependencies (Pydantic v2 and
LangGraph), and the pytest development group into `.venv`. If Python is not
available locally, uv can install it with `uv python install 3.12`; select it with
`uv sync --locked --python 3.12`.

The CLI only displays application/version information. No credentials, model
provider, environmental data, or tracing service are needed for startup or tests.
Local JSONL is reserved for future authoritative investigation tracing.
LangSmith is a transitive dependency of the orchestration stack; this bootstrap
does not enable tracing, and its optional pytest plugin is disabled.

Package areas under `src/hawaii_activity_forecaster/` are `config`, `models`,
`fixtures`, `harness`, `agents`, `orchestration`, `validation`, and `tools`. The `models`
package contains the Pydantic contracts, `config` contains settings and loading,
`fixtures` loads local synthetic inputs, and `harness` validates v2 scenario contracts;
`orchestration` contains the synthetic graph, trusted budgets and specialist merge components;
`tools` executes scoped synthetic calls; the agent/validation areas remain placeholders.

See [M1.1-B model notes](docs/development/m1-1b-models.md) for schema coverage,
serialization choices, validation boundaries, and unresolved specification details.
Run the model tests alone with `uv run --locked pytest tests/test_models.py`.

### Configuration

Use the approved defaults or load an explicit local TOML file:

```python
from hawaii_activity_forecaster.config import AppConfig, load_config

defaults = AppConfig()
settings = load_config("haf.example.toml")
```

Precedence is defaults, explicit TOML, then supported `HAF_` environment variables.
The loader does not discover files or read `.env` automatically. It creates no
trace files and contacts no services. Budget and timeout values must match the
approved baseline; real-model execution remains disabled pending provider
activation. Keep credentials out of configuration files.

See [M1.1-C configuration notes](docs/development/m1-1c-configuration.md) for the
settings, environment variables, relative-path rules, and runtime checks deferred
to later increments. Run its tests with `uv run --locked pytest tests/test_config.py`.

### Synthetic input fixtures

```python
from hawaii_activity_forecaster.fixtures import load_fixture_inputs

inputs = load_fixture_inputs("fixtures")
catalog = inputs.catalog
forecast = inputs.source_responses["weather-forecast"]
```

The [fixture package](fixtures/README.md) contains five fictional beaches and
eight synthetic source examples with fixed timestamps. Loading checks declared
versions, paths, record schemas, and cross-file references. It does not execute
scenarios, accept environmental evidence, or generate recommendations.

Run its tests with `uv run --locked pytest tests/test_fixtures.py`. See the
[M1.1-D notes](docs/development/m1-1d-fixtures.md) for the input format and remaining
policy/behavior/assertion design decisions needed before full scenario loading
and M1.2 LangGraph execution.

### Approved scenario harness design — M1.1-E

The [M1.1-E scenario harness contract design](docs/implementation/m1-scenario-harness-contract-design.md)
was **approved on November 18, 2026**, including SH-OD-001 through SH-OD-009 and
acceptance checks SH-T01 through SH-T20. It defines synthetic policy inputs, tool
behaviors, independent assertions, scenario assembly, and the SC-005/SC-008
readiness-status serialization mapping. This design adds no runtime functionality
or changes to the existing fixture format. Its first implementation step is now
available as M1.1-F below; later execution work still requires separate authorization.

### Scenario contracts and preflight — M1.1-F

`hawaii_activity_forecaster.harness.load_scenario(root, scenario_id)` validates an
explicitly registered v2 scenario and returns separate application, trusted-driver,
and evaluator snapshots. The existing `load_fixture_inputs()` API remains v1-only.
Expected values and artifact digests stay out of application/driver inputs.

M1.1-F tests construct temporary contract-only packages. M1.1-G adds the authored
SC-004/SC-010 package below; structurally valid ACTIVE definitions remain **BLOCKED**
for execution until the runtime components are implemented.

Run the new tests with:

```bash
uv run --locked pytest tests/test_harness_contracts.py tests/test_harness_loading.py
```

See the [M1.1-F notes](docs/development/m1-1f-harness-contracts.md) for validated
formats, projection boundaries and deferred runtime checks.

### Authored scenario fixtures — M1.1-G

The [isolated v2 scenario pack](fixtures/scenario-pack-v1/README.md) contains the
SC-004 advisory-exclusion case and SC-010 outage/abstention case, with 18 source
templates and 145 independent assertion definitions. Its name denotes the first
scenario pack; its manifest format is 2.0.0 and dataset version is 1.1.0.

```python
from hawaii_activity_forecaster.harness import load_scenario

scenario = load_scenario("fixtures/scenario-pack-v1", "SC-004")
assert scenario.execution_readiness.outcome == "BLOCKED"
```

Run authoring/preflight tests with `uv run --locked pytest tests/test_scenario_fixtures.py`.
See the [M1.1-G coverage notes](docs/development/m1-1g-scenario-fixtures.md) for
explicit evidence/gap inputs, independent expectations, budget-boundary semantics,
and the temporal assertion-validation fix. M1.2-A below begins the bounded
graph/runtime work with the graph skeleton and trusted budget enforcement.

### Graph skeleton and trusted budgets — M1.2-A

`orchestration.run_skeleton()` is an async component-test API with injected
synthetic control signals and an event recorder. It exercises parallel Weather
and Ocean branch entry/exit, conditional looping and bounded termination. It
produces no evidence or public recommendation results. `BudgetManager` provides
atomic per-investigation tool/model reservations and scoped recovery allowances.

```bash
uv run --locked pytest tests/test_orchestration_budgets.py tests/test_orchestration_skeleton.py
```

See the [M1.2-A notes](docs/development/m1-2a-graph-and-budgets.md) for the graph,
failure semantics, tracing boundary and deferred runtime integration. The CLI
continues to display application information only.

### Specialist contracts and trusted merge — M1.3-A

`orchestration.run_specialist_graph()` accepts a trusted synthetic planner,
specialist callback and event recorder. Requests use the approved specialist
contracts; the trusted join validates correlation and scope, deduplicates stable
IDs, preserves independent findings and explicit gaps/errors, and isolates failed
branches. New findings remain PENDING for independent evidence validation.

```bash
uv run --locked pytest tests/test_specialist_exchange.py tests/test_specialist_graph.py
```

See the [M1.3-A notes](docs/development/m1-3a-specialist-contracts-and-merge.md) for
the API, merge rules, deadline behavior and remaining execution boundaries.
No environmental tool calls, model calls or recommendations execute in this chunk.

### Scoped synthetic tool dispatch — M1.3-B

`orchestration.run_synthetic_tool_graph()` combines trusted specialist and tool
plans with the approved driver projection. `tools.ToolAction` explicitly scopes
each source call and any retry/fallback. The script supplies declared behavior
without selecting actions. Actual dispatches consume the shared tool budget;
duplicate delivery does not consume another call. Runtime bindings preserve
source provenance and evidence timestamps, and findings remain PENDING.

```bash
uv run --locked pytest tests/test_synthetic_tools.py tests/test_synthetic_tool_graph.py
```

See the [M1.3-B notes](docs/development/m1-3b-synthetic-tool-dispatch.md) for API
ownership, virtual timeout semantics, recovery permissions, counters and tracing
boundaries. The SC-010 component test exercises outage/recovery dispatch only;
full scenario acceptance and environmental recommendations remain unavailable.

## Specification notes

All seven core requirements and seven approved M1 implementation/design
documents are present.
The older technical plan still marks dependency management and several safeguards
as open; the approved configuration baseline resolves uv and its lockfile,
invocation limits/timeouts, and trace write-failure handling. Its provider/model
decision remains open. The planning-only notices in AGENTS.md and specifications
precede the separate authorization for this bootstrap increment.

Existing path irregularity: `docs/decisions/README.md` is a directory rather than
a Markdown file. It is preserved. Existing `src/tmp.txt`, `tests/tmp.txt`, data,
and approved specifications are also preserved.
