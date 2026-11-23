# Hawaii Activity Planner — development guide

Development history and reference material moved from the root [README](../README.md) so the README can stay focused on the capstone. The content below is unchanged apart from link paths: release status and model profiles, configuration, fixtures, each M1 increment, the reliability reporting and web interface notes, and specification status.

Run commands from the repository root.

## Current Status

The owner-approved [Saturday M1 release scope](implementation/m1-saturday-release-scope.md)
connects natural-language requests to Coordinator, Weather and Ocean model planning,
the existing LangGraph workflow, synthetic tools, deterministic validation and local
JSONL. All three activities, both default time windows and post-terminal follow-ups
are available through the opt-in `hafi run` command below. Default execution remains
disabled. The current release uses the explicit OpenAI `gpt-6-luna` target for all
three roles. Local Ollama `qwen3.5:9b` remains experimental and is deferred.

Offline integration tests exercise the installed SDK with mock HTTP responses.
The [bounded OpenAI pilot](development/m1-openai-pilot.md) additionally verified
genuine three-role execution for the listed recommendation, recovery, abstention
and follow-up checks. It used all ten authorized investigations, retaining two
early normalization failures; all seven later checks passed on the
`m1-saturday-runtime-0.2` profile. The release configuration now uses `0.8`: `0.3` raised the input bound
([M1.8](development/m1-8-sc-009-sc-012.md)), `0.4` adds request-interpretation
guidance ([M1.9](development/m1-9-sc-001-sc-003.md)), `0.5` adds Ocean
recovery-condition guidance, `0.6` adds no-retry guidance
([M1.9-B](development/m1-9b-profile-0.4-rebaseline.md)), `0.7` adds the
"prefer somewhere near" request guidance ([M1.12](development/m1-12-sc-002-wind-chop.md)),
and `0.8` keeps unapproved preferences as UNINTERPRETED
([deferment record](development/m1-live-acceptance-deferments.md)).
This is a synthetic M1
release with fictional beaches and fixed evidence dates, not a real-world forecaster.
See the [integration notes](development/m1-integration-release.md) for coverage,
remaining acceptance work and approved deferments.

The [M1.6-D runtime proposal](implementation/m1-model-provider-and-agent-runtime-design.md)
and [M1.6-F capability-profile proposal](implementation/m1-synthetic-source-capability-profile-design.md)
remain drafts. The general profile framework is deferred in favor of explicit
configured tool allowlists. Existing SC-004/SC-010 authored component checks remain
available with authored scope. On the release profile 0.8, four full live rounds of
all twelve registered scenarios passed **47/48** scenario runs (51/52 investigations
operationally successful); the one failure, an SC-012 follow-up whose Ocean plan named
an invalid option, failed closed. An earlier 0.7 batch passed 10/12; SC-006 and SC-008
were then fixed and re-enabled. The full offline pytest suite remains enabled. Optional failures and blockers
are retained in the [M1 completion report](development/m1-completion-report.md)
and [deferment record](development/m1-live-acceptance-deferments.md). Increment sections
below retain their original scope; the release section describes current execution.

The final submission snapshot records **1,530 passing pytest tests, one documented
expected failure and zero unexpected failures**. Genuine model-driven evaluations
used `gpt-6-luna`; the current historical evaluation profile is
`m1-saturday-runtime-0.8`. These synthetic development observations do not establish
real-world forecasting accuracy or production reliability. Representative traces,
their saved reports and the four-round aggregate are in the
[portable evaluation evidence](evaluation-evidence/README.md); the complete raw
dataset remains local.

## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use Python
3.12 or newer. From the repository root:

```bash
uv sync --locked
uv run --locked hafi
uv run --locked hafi --version
uv run --locked python -m hawaii_activity_forecaster
uv run --locked hafi demo advisory --fixtures fixtures/scenario-pack-v1
uv run --locked hafi demo outage --fixtures fixtures/scenario-pack-v1
uv run --locked hafi demo session --fixtures fixtures/scenario-pack-v1
uv run --locked pytest
```

`uv sync --locked` installs the package, runtime dependencies (including Pydantic,
LangGraph and the OpenAI adapter), and the pytest development group into `.venv`. If Python is not
available locally, uv can install it with `uv python install 3.12`; select it with
`uv sync --locked --python 3.12`.

The [Tests workflow](../.github/workflows/tests.yml) configures a single `pytest` check
on Python 3.12 for pull requests and pushes to `main`. It runs the locked install
and offline test suite without model credentials. After its first GitHub run,
select that check in the protection rule/ruleset for `main` to require passing
tests before merging; repository YAML alone does not enforce the merge gate.
See the [setup instructions](development/m1-release-readiness-and-demo.md#enable-required-status-checking-after-publication).

With no arguments the CLI displays application/version information. The `demo`
command runs a fixed synthetic component example and requires an explicit fixture
directory. Its interpretation and tool plans are authored, with no model call or
full scenario acceptance. All locations, conditions and results are fictional. No credentials,
model provider, live environmental data or tracing service are needed.
Local JSONL provides authoritative investigation tracing. LangSmith is installed
for explicit tracing-context control; provider tests suppress remote tracing, and
its optional pytest plugin is disabled.

Package areas under `src/hawaii_activity_forecaster/` are `config`, `models`,
`fixtures`, `harness`, `agents`, `orchestration`, `interpretation`, `model_runtime`,
`observability`, `validation`, `tools`, `recommendations` and `web`. The `models`
package contains the Pydantic contracts, `config` contains settings and loading,
`fixtures` loads local synthetic inputs, and `harness` validates v2 scenario contracts;
`orchestration` contains the synthetic graph, trusted budgets, session admission and specialist merge components;
`interpretation` checks authored request proposals and selects catalog candidates;
`model_runtime` contains the provider gateway, wire proposals and versioned prompts;
`catalog.py` shares catalog provenance/location checks. `tools` executes scoped synthetic calls, and `validation` evaluates evidence,
synthetic safety policies and Candidate Assessments. `recommendations` compares
eligible candidates and validates controlled synthetic results. `agents` connects
the three model-driven planners, explicit tool options, raw sessions and CLI.
`web` serves the optional loopback-only interface over those same functions.

### Model-driven synthetic release

Choose the target through an explicit TOML file and matching execution switch:

| Target | Configuration | Switch | Access |
|---|---|---|---|
| Local Ollama `qwen3.5:9b` | `haf.ollama.example.toml` | `--local` | Running local Ollama with the installed model; no API key |
| OpenAI `gpt-6-luna` | `haf.release.example.toml` | `--live` | Explicit local `OPENAI_API_KEY`; paid API calls |

**Local model status: experimental.** The installed Qwen accepted requests, but
bounded real checks did not complete request normalization: non-thinking runs
returned invalid nested JSON, and the thinking-enabled profile exceeded the
thirty-second deadline. Its adapter/CLI paths pass offline tests; a successful real
end-to-end local investigation is still unverified. Safety and parsing checks
remain enforced. Local work is deferred; the OpenAI pilot results are recorded above.

For local development, with Ollama running:

```bash
uv run --locked hafi run "Where should I snorkel tomorrow morning?" \
  --fixtures fixtures/saturday-release --config haf.ollama.example.toml \
  --local --max-investigations 1
```

The local target uses `http://127.0.0.1:11434/v1` and the already-installed
`qwen3.5:9b` tag. The application downloads no models and needs no env-file for local
execution. It does not read `OPENAI_API_KEY` for this target. Unavailable Ollama,
invalid output or timeout produces a technical failure without switching to OpenAI.
The same thirty-second model deadline and all validation/budget limits apply.
Local model quality and speed depend on the installed model and hardware; evaluate
your intended demo requests on the chosen target. See the
[local-target validation notes](development/m1-local-model-targets.md).

For OpenAI execution:

Create `keys/apsi.env` containing `OPENAI_API_KEY=...`. The `keys/` directory is
ignored by Git. Keep credentials out of tracked TOML files and shell command
arguments, and pass the env-file path explicitly:

```bash
uv run --locked --env-file keys/apsi.env hafi run \
  "Where should I snorkel tomorrow morning near Kihei?" \
  --fixtures fixtures/saturday-release --config haf.release.example.toml \
  --live --max-investigations 1
```

`--live` makes **paid model calls**. Environmental retrieval stays entirely
synthetic. The bundled clock is November 16, 2026, 09:00 HST, so "tomorrow" means
November 17. Available evidence covers **08:00–11:00** or **12:00–16:00 HST** on
that date. Use "tomorrow afternoon" for the afternoon window. Other dates or
intervals are not covered by this finite dataset and cannot produce recommendations.
The CLI prints the fixture clock/windows and synthetic warnings.

Use `--case advisory`, `--case recovery` or `--case outage` to select a synthetic
environment; the default is `favorable`. These cases change source behavior/data,
not the model's decisions. Add `--interactive --max-investigations 3` to accept
post-terminal follow-ups such as "Actually near Napili instead." Each follow-up
gets a new investigation, fresh evidence/budgets and a correlated trace. Enter
`/quit` to stop. Clarification prints questions without environmental calls; submit
the complete clarified request in a new run. Active clarification resumption is deferred.

Every investigation retains the approved limits: 12 model calls, 12 environmental
calls, five Coordinator cycles, two concurrent specialists, one retry per failed
original, one fallback per required gap and three recommendations. Model retries,
automatic model switching and remote LangSmith tracing are disabled. Both adapters
reuse the installed LangChain/OpenAI-compatible client; no additional SDK is needed.
The process allowance defaults to three investigations and cannot exceed ten.
The authorized pilot was **ten investigations across all commands and $1 total**;
all ten have now been used. Its count was tracked manually, not by a persistent
dollar ledger. That original profile 0.2 pilot reserved up to $0.03 per investigation. The
current profile 0.8 reserves 2,600 microdollars per dispatched call, up to $0.0312
at the twelve-call limit. These are code-level reservations, not invoice amounts
or permission to extend a prior allowance. Local calls reserve zero API dollars and still count toward the model
invocation limit. Traces distinguish `LOCAL_PROVIDER`, `LIVE_PROVIDER` and mock
`OFFLINE_TRANSPORT` execution and retain the selected provider/model identity.

The printed `Local trace:` path can be independently checked with
`uv run --locked hafi trace traces/INVESTIGATION_ID.jsonl`. Tests remain offline:

```bash
uv run --locked pytest tests/test_agent_release.py tests/test_release_cli.py tests/test_release_profile.py
uv run --locked pytest tests/test_ollama_target.py
uv run --locked pytest
```

See the [release fixture documentation](../fixtures/saturday-release/README.md) and
[integration notes](development/m1-integration-release.md). No external service
or account upgrade is needed to run the tests and authored `demo` commands. The
[local-target addendum](implementation/m1-local-model-target-addendum.md)
records the owner's request to add Ollama alongside OpenAI; the broader provider
framework remains deferred.

See [M1.1-B model notes](development/m1-1b-models.md) for schema coverage,
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
approved baseline. Real-model execution requires an explicit enabled release
profile, `activation="synthetic-release"`, target access and matching CLI opt-in; a key alone
does not activate it. `haf.example.toml` preserves disabled defaults, while
`haf.release.example.toml` and `haf.ollama.example.toml` show the explicit target tuples. `HAF_LLM_ACTIVATION`
is supported alongside the existing provider/model/profile settings. Keep
credentials out of configuration files. uv's explicit `--env-file` supplies them
to the process without adding another dotenv loader.

See [M1.1-C configuration notes](development/m1-1c-configuration.md) for the
settings, environment variables, relative-path rules, and runtime checks deferred
to later increments. Run its tests with `uv run --locked pytest tests/test_config.py`.

### Synthetic input fixtures

```python
from hawaii_activity_forecaster.fixtures import load_fixture_inputs

inputs = load_fixture_inputs("fixtures")
catalog = inputs.catalog
forecast = inputs.source_responses["weather-forecast"]
```

The [fixture package](../fixtures/README.md) contains five fictional beaches and
eight synthetic source examples with fixed timestamps. Loading checks declared
versions, paths, record schemas, and cross-file references. It does not execute
scenarios, accept environmental evidence, or generate recommendations.

Run its tests with `uv run --locked pytest tests/test_fixtures.py`. See the
[M1.1-D notes](development/m1-1d-fixtures.md) for the input format and remaining
policy/behavior/assertion design decisions needed before full scenario loading
and M1.2 LangGraph execution.

### Approved scenario harness design — M1.1-E

The [M1.1-E scenario harness contract design](implementation/m1-scenario-harness-contract-design.md)
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

See the [M1.1-F notes](development/m1-1f-harness-contracts.md) for validated
formats, projection boundaries and deferred runtime checks.

### Authored scenario fixtures — M1.1-G

The [isolated v2 scenario pack](../fixtures/scenario-pack-v1/README.md) contains the
SC-004 advisory-exclusion case and SC-010 outage/abstention case, with 18 source
templates and 145 independent assertion definitions. Its name denotes the first
scenario pack; its manifest format is 2.0.0 and dataset version is 1.1.0.

```python
from hawaii_activity_forecaster.harness import load_scenario

scenario = load_scenario("fixtures/scenario-pack-v1", "SC-004")
assert scenario.execution_readiness.outcome == "BLOCKED"
```

Run authoring/preflight tests with `uv run --locked pytest tests/test_scenario_fixtures.py`.
See the [M1.1-G coverage notes](development/m1-1g-scenario-fixtures.md) for
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

See the [M1.2-A notes](development/m1-2a-graph-and-budgets.md) for the graph,
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

See the [M1.3-A notes](development/m1-3a-specialist-contracts-and-merge.md) for
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

See the [M1.3-B notes](development/m1-3b-synthetic-tool-dispatch.md) for API
ownership, virtual timeout semantics, recovery permissions, counters and tracing
boundaries. The SC-010 component test exercises outage/recovery dispatch only;
full scenario acceptance and environmental recommendations remain unavailable.

### Deterministic evidence validation — M1.4-A

Pass `evidence_policy=application.policy_configuration` to
`run_synthetic_tool_graph()` to validate observed findings after each specialist
join. The report includes validation reasons and per-candidate category coverage.
`validation.validate_evidence()` is also available for active component snapshots.

```bash
uv run --locked pytest tests/test_evidence_validation.py tests/test_evidence_graph.py
```

Category coverage does not establish safe conditions, sufficient overall evidence
or eligibility. No recommendations are generated. See the
[M1.4-A notes](development/m1-4a-evidence-validation.md) for scope, provenance,
time/coverage rules, conflict handling, gap resolution and remaining boundaries.

### Safety policy evaluation and assessments — M1.4-B

Add `safety_evaluation=True` alongside `evidence_policy` on the synthetic graph to
evaluate approved supported premises and create trusted Candidate Assessments.
`validation.evaluate_safety()` is also available for active evidence snapshots.
Verified exclusions take precedence; mandatory unknowns prevent eligibility.
Reviewed MIXED visibility requires explicit permission and retained disclosure.

```bash
uv run --locked pytest tests/test_safety_evaluation.py tests/test_safety_graph.py
```

Opaque hard constraints remain UNKNOWN pending an approved input interpretation;
soft preferences cannot override exclusions. See the
[M1.4-B notes](development/m1-4b-safety-and-assessments.md) for policy handling,
independent dimensions, revision/invalidation rules, open input semantics and
tracing boundaries. This assessment-only path produces no Recommendation Result.

### Candidate comparison and Result Validation — M1.5-A

Add `result_generation=True` alongside explicit evidence and safety evaluation on
`run_synthetic_tool_graph()` to construct and validate controlled synthetic results.
`report.result` is assigned only after result validation and terminal-event recording
succeed. The `recommendations` package also exposes standalone comparison,
construction and contextual validation functions for current active snapshots.

```bash
uv run --locked pytest tests/test_results.py tests/test_result_graph.py
```

Comparison uses qualitative suitability/area criteria, preserves unresolved ties,
omits forced numeric ranks and selects at most three eligible locations. Handled
outages may produce explained abstention; application failures remain ERROR outcomes.
See the [M1.5-A notes](development/m1-5a-comparison-and-results.md) for context
guards, disclosures, outcome routing, trace-failure suppression and deferred work.
Outputs are explicitly synthetic; M1.5-B below adds CLI presentation.

### CLI presentation of validated results — M1.5-B

From the repository root:

```bash
uv run --locked hafi demo advisory --fixtures fixtures/scenario-pack-v1
uv run --locked hafi demo outage --fixtures fixtures/scenario-pack-v1
uv run --locked pytest tests/test_presentation.py tests/test_cli_demo.py tests/test_cli_startup.py
```

The advisory example shows only eligible fictional Beach B; the outage example
explains insufficient evidence. The module entry point supports the same commands
(`uv run --locked python -m hawaii_activity_forecaster demo ...`). Outside the
repository, pass an absolute fixture path. Fixture files are not bundled in the wheel.

The renderer checks the committed result and its retained validation context before
writing output. It preserves evidence coverage, units, timestamps, source links,
required disclosures and limitations. Rejected output never appears as partial
recommendations. Exit codes are `0` for recommendations or explained abstention,
`1` for technical failures, and `2` for invalid arguments or fixture preflight errors.
Successful results use stdout; errors use stderr.

Current demos retain their component scope and now record authoritative JSONL.
They refuse BLOCKED or DISABLED definitions; `evaluate --component` separately
runs independent assertions. Full registered scenario acceptance requires
`evaluate --agent` with a genuine model target ([M1.7-A](development/m1-7a-agentic-scenario-adapter.md)). See the
[M1.5-B notes](development/m1-5b-cli-presentation.md) for the original
presentation boundary and remaining request/session work.

### Session lifecycle and post-terminal follow-ups — M1.5-C

```bash
uv run --locked hafi demo session --fixtures fixtures/scenario-pack-v1
uv run --locked pytest tests/test_session_lifecycle.py tests/test_cli_demo.py
```

The session demo executes two authored normalized requests: an initial fictional
snorkeling request near Kihei, then a preference change to Wailea. It preserves the
activity, date/window, experience and calm-water preference. Each investigation
retrieves its own synthetic evidence and produces separately validated output.
This demonstrates the session component; it does not execute SC-012 acceptance or
interpret arbitrary conversational text.

`orchestration.SessionManager` admits a caller-normalized initial request with
declared user-provided fields. Its `follow_up()` accepts explicit replacements of
existing normalized fields; omitted values remain intact. The async runner receives
immutable `SessionRequest` metadata and a detached request, then calls the graph
with `session_request=admission`. Candidate selection remains the runner's responsibility.
Session/revision/prior-investigation correlations flow into graph events and results.

Follow-ups require a terminal investigation. Ambiguous inputs retain context and
request clarification without tool calls or recommendations; resumption of that
nonterminal investigation remains deferred. Prior findings/assessments are not
imported into new execution. Cross-investigation evidence-reference storage,
natural-language normalization and authoritative tracing remain separate work.
See the [M1.5-C notes](development/m1-5c-session-lifecycle.md) for the API,
admission guards, origin declarations, acceptance coverage and open decisions.

### Approved request interpretation and candidate-selection design — M1.5-D

The [M1.5-D design](implementation/m1-request-interpretation-and-candidate-selection-design.md)
was **approved on November 19, 2026**, including RI-OD-001 through RI-OD-010 and the
afternoon-window amendment. It defines interpretation rules, hard/soft
constraint payloads, catalog selection, follow-up origins, shared model-budget
admission and empty-selection abstention. It selects no provider and changes no
application behavior or the existing approved requirement/architecture baselines.

Approved defaults are **08:00–11:00 HST for morning** and **12:00–16:00 HST for
afternoon**. Explicit user times override defaults; assumed windows are disclosed
and require evidence covering the entire interval. The approved distinction between
assessment candidates and supported dispatch candidates resolves RI-C01's tension
between architecture filtering and SC-003's required UNSUPPORTED assessments.
M1.5-E below implements the deterministic validation/selection components with
synthetic interpreter outputs. General conversational CLI execution remains
separately gated.

See the [M1.5-D review notes](development/m1-5d-request-interpretation-design.md)
for the current-code gaps, approval scope and validation performed in this increment.

### Deterministic request validation and catalog selection — M1.5-E

`interpretation.validate_request(proposal, context)` checks the internal authored
proposal transport and returns a detached `ValidatedRequest`. Its `.request` is an
existing `NormalizedRequest`; `.origins`, `.assumed_fields` and
`.assumption_disclosures` preserve explicit/default/inherited precision. Both the
morning (08:00–11:00 HST) and afternoon (12:00–16:00 HST) defaults use the injected
Hawaii clock. Explicit hours take precedence. Unresolved material meaning produces
clarification fields, while invalid proposals raise sanitized `RequestValidationError`.

`select_candidates(receipt, context)` independently rechecks the receipt and
catalog, returning assessment/investigation ID sets, planning order and attribution
audit. `verify_request` and `verify_selection` reject changed or stale snapshots.
For SUP in South Maui, the common fixture's assessment set is A/B/E and its supported
investigation set is B. No eligibility, dispatch or public result follows from
selection alone; the graph does not consume this audit yet.

Recognized LOCATION_RESTRICTION payloads now receive independent catalog-based
PASS/FAIL/UNKNOWN checks in safety evaluation. Unknown/legacy payloads remain
UNKNOWN, and the CALM_WATER preference stays UNKNOWN with disclosure even when
environmental suitability is favorable.

```bash
uv run --locked pytest tests/test_request_validation.py tests/test_request_followups.py tests/test_candidate_selection.py tests/test_location_constraints.py
uv run --locked pytest
uv run --locked hafi demo session --fixtures fixtures/scenario-pack-v1
```

This component API requires explicit context and interpreter proposals; it does not
enable a general natural-language CLI, select an LLM provider, record model usage,
resume clarification or implement zero-candidate result routing. See the
[M1.5-E notes](development/m1-5e-request-validation-and-catalog-selection.md)
for the runnable component example, supported clause limits and deferred RI-T checks.

### Raw request/session graph integration — M1.5-F

`SessionManager.start_raw()` admits text, a detached catalog and an explicit clock
before normalization. `follow_up_raw()` creates a fresh investigation after a
terminal raw request. Each runner calls `run_raw_synthetic_tool_graph()` with an
authored interpreter, trusted planner/tool plan, synthetic driver and policy.
Session commit independently replays the receipt against its owned admission.

The graph retains unsupported records for real assessments while restricting
specialist and tool dispatch to the verified investigation subset. A current
selection audit with no supported candidates yields `NO_RECOMMENDATION` rather
than a technical error or invented hazard. Results disclose default time windows,
unresolved soft preferences and incomplete candidate investigations.

`SyntheticModelAdapter` is an explicitly labeled accounting test double with the
same per-investigation model ledger used by later planner work: 12 calls, a
30-second timeout and no automatic model retry. Environmental calls retain their
separate 12-call limit. It enables no provider and does not use model BehaviorScript
operations. Authored interpretation callbacks use neither invocation budget.

```bash
uv sync --locked
uv run --locked pytest tests/test_raw_request_graph.py tests/test_raw_session_lifecycle.py tests/test_raw_selection_scope.py tests/test_raw_model_accounting.py
uv run --locked pytest
uv run --locked hafi --version
uv run --locked hafi demo session --fixtures fixtures/scenario-pack-v1
```

See the [M1.5-F integration notes](development/m1-5f-raw-request-session-graph-integration.md)
for API wiring, trust checks, verification results and remaining runtime gates.
These are component APIs; the existing CLI accepts fixed synthetic demos only.

### Authoritative local JSONL tracing — M1.6-A

Synthetic demos now create `traces/<investigation-id>.jsonl` by default. Each line
is an approved `TraceEvent`; the initial event carries trace/configuration/policy
metadata. Writes are synced before execution continues. Required storage or trace
validation failures stop further dispatch and suppress result publication.

```bash
uv sync --locked
uv run --locked hafi demo advisory --fixtures fixtures/scenario-pack-v1
uv run --locked hafi demo session --fixtures fixtures/scenario-pack-v1 --trace-directory traces
uv run --locked hafi trace traces/<investigation-id>.jsonl
uv run --locked pytest
```

Replace `<investigation-id>` with a generated filename. `hafi trace PATH` prints
structured completeness and metrics; it exits 1 for partial or invalid traces.
It does not authorize recommendations or establish full scenario acceptance.
Trace location precedence is `--trace-directory`, `HAF_TRACE_DIRECTORY`, an explicit
`--config PATH` TOML `[trace]` directory, then `traces/`. Relative TOML paths are
anchored to the configuration file's directory.

Raw messages, opaque constraints, source/model payloads and private reasoning are
omitted from local traces. Events retain controlled summaries, identifiers,
timestamps, source/rule/policy references and actual outcomes. Explicit in-memory
recorders remain component-test seams. Remote tracing is disabled; model-driven
release execution requires explicit provider opt-in. Existing `.gitignore` rules
exclude the default trace directory.

Keep files only as long as needed for local development/evaluation; manually remove
unneeded files after their investigations have stopped. No automatic retention
period, repair, overwrite or investigation resumption is implemented. See the
[M1.6-A notes](development/m1-6a-authoritative-local-jsonl-tracing.md) for format,
privacy, integrity, test coverage and remaining acceptance gates.

### Independent assertion evaluation and reporting — M1.6-B

```bash
uv run --locked hafi evaluate SC-004 --fixtures fixtures/scenario-pack-v1
uv run --locked hafi evaluate SC-010 --fixtures fixtures/scenario-pack-v1
uv run --locked pytest tests/test_harness_evaluation.py
```

The evaluation CLI preflights inputs and reports readiness without dispatching
work. Both scenarios currently report BLOCKED (exit 2). Invalid fixtures report
FAIL (exit 1). The evaluator-only Python API can compare verified component
captures with the approved expected files; component assertion success cannot
be presented as a full scenario PASS.

M1.6-B identified two demo gaps in request preference and limit reporting. M1.6-C
below resolves them without changing expected fixtures or inventing events.
See the [M1.6-B notes](development/m1-6b-scenario-evaluation-and-reporting.md)
for APIs, comparison semantics, diagnostic categories and remaining gates.

### Scenario execution adapter and demo alignment — M1.6-C

```bash
uv run --locked hafi evaluate SC-004 --fixtures fixtures/scenario-pack-v1 --component --trace-directory traces
uv run --locked hafi evaluate SC-010 --fixtures fixtures/scenario-pack-v1 --component --trace-directory traces
uv run --locked pytest tests/test_scenario_execution.py
```

`--component` explicitly executes the existing authored synthetic plan. JSON output
separates `component` assertion results from the overall `scenario` result. SC-004
passes 84 component assertions and SC-010 passes 61; overall readiness remains
BLOCKED (exit 2), with `AUTHORED_COMPONENT_SCOPE`. Without a runner flag,
`evaluate` remains preflight/readiness-only (`AGENT_EXECUTION_NOT_RUN`) and
dispatches no work.

### Registered scenarios through the agent runtime — M1.7-A

```bash
uv run --locked --env-file keys/apsi.env hafi evaluate SC-004 --fixtures fixtures/scenario-pack-v1 \
  --agent --config haf.release.example.toml --live --trace-directory traces/acceptance
uv run --locked pytest tests/test_agent_scenarios.py
```

`--agent` runs the registered scenario through the model-driven Coordinator,
Weather and Ocean roles. It uses the explicit, preflighted tool allowlist in
`fixtures/scenario-pack-v1/agent_tools/`. `--live` makes paid OpenAI calls;
`--local` uses the configured Ollama target. Scenario PASS is reported only when
each verified trace records a live or local model target. The offline tests run
the same path over mock HTTP, pass all 84/61 assertions, and report
`OFFLINE_MODEL_TRANSPORT` (BLOCKED). See the
[M1.7-A notes](development/m1-7a-agentic-scenario-adapter.md) for the reporting
categories, allowlist rules and remaining gaps.

[M1.8](development/m1-8-sc-009-sc-012.md) registers SC-009 (fallback recovery,
ACTIVE, 73 assertions) and SC-012 (preference revision, ACTIVE, 84 assertions), with
dataset `1.2.0`. It also adds model profile `m1-saturday-runtime-0.3`, which raises the
input bound to 12,000 bytes so revised follow-ups fit.

[M1.9](development/m1-9-sc-001-sc-003.md) registers SC-001 (86 assertions) and
SC-003 (55 assertions) with dataset `1.3.0`. [M1.10](development/m1-10-sc-006-sc-007-sc-011.md) adds
SC-006 (permitted MIXED), SC-007 (stale reports) and SC-011 (prompt injection) with
dataset `1.4.0`. [M1.11](development/m1-11-sc-005-sc-008.md) adds the partially
blocked SC-005 (SUP offshore wind) and SC-008 (material conflict) with dataset `1.5.0`.
[M1.12](development/m1-12-sc-002-wind-chop.md) completes the set with SC-002, adding the
owner-approved swimming wind-chop MIXED permission, dataset `1.6.0` and profile `0.7`.

Default demos now use raw admission and independently validated interpretation
proposals. SC-004 retains the requested Kihei preference. SC-010 records actual
exhaustion of the one-fallback-per-evidence-gap allowance, with eight tool calls
and one investigation cycle; it does not manufacture iteration exhaustion.
The normalized session demo remains available.

See the [M1.6-C notes](development/m1-6c-scenario-execution-and-demo-alignment.md)
for runtime boundaries, snapshots, lifecycle checks and remaining gates.

### Model provider and agent runtime design — M1.6-D

Review the [draft design](implementation/m1-model-provider-and-agent-runtime-design.md)
and [development notes](development/m1-6d-model-provider-and-agent-runtime-design.md).
The proposal preserves the three roles, deterministic safety, local JSONL and
approved invocation limits. New provider, token/spending and runtime-profile
choices are explicitly proposed, not approved defaults. Existing setup, demo,
evaluation and test commands remain unchanged; no API credentials are needed.

### Provider gateway and model contracts — M1.6-E

```bash
uv sync --locked
uv run --locked pytest tests/test_model_runtime_contracts.py tests/test_model_gateway.py tests/test_model_trace_validation.py
uv run --locked pytest
```

All tests use synthetic inputs and in-process mock HTTP responses. They verify the
installed SDK path, strict schemas, no retries, shared call limits, stale-response
rejection and local trace accounting without credentials or paid calls. The graph,
authored demos and scenario acceptance gates retain their existing behavior.

The optional `HAF_LLM_PROFILE_ID=m1-agent-runtime-0.1` setting requires explicit
`HAF_LLM_PROVIDER=openai` and `HAF_LLM_MODEL_IDENTIFIER=gpt-6-luna`; it records
offline profile metadata only. This tuple alone cannot activate live execution.
A provider API key or installed SDK cannot enable calls. Do not add credentials to TOML.

See the [M1.6-E notes](development/m1-6e-provider-gateway-and-model-contracts.md)
for API boundaries, trace-detail fields, verification and remaining activation work.

### Synthetic source capability profile design — M1.6-F

Review the [draft profile design](implementation/m1-synthetic-source-capability-profile-design.md)
and [M1.6-F notes](development/m1-6f-synthetic-source-capability-profile-design.md).
The proposal keeps source interface capabilities separate from scripted outcomes
and expected assertions. It records current exact-query, candidate-batch and
cross-delegation recovery limitations, with explicit proposed compatibility changes.
The general profile implementation is deferred under the approved Saturday scope.
The release uses explicit tool allowlists; full registered scenario acceptance
is evaluated separately from its focused integration tests. Completed live runs
and the subsequent two-scenario deferment are recorded in the completion report.

### Read-only reliability reporting

```bash
uv run --locked hafi reliability traces/acceptance
uv run --locked hafi reliability traces/acceptance --reports traces/acceptance --format json
```

These commands summarize existing local evidence without model calls. Profiles
and recorded execution modes stay separate. Recommendations and abstentions are
operational successes; saved scenario PASS/FAIL is reported separately. Invalid
inputs are surfaced, duplicate copies are deduplicated, and clarification is not
counted as a terminal failure. Most historical traces are absent from a fresh clone;
representative profile 0.8 traces in the
[portable evaluation evidence](evaluation-evidence/README.md) can be summarized
the same way, and the [reporting notes](development/m1-reliability-baseline.md) include an offline
demo example and explain denominators, privacy and exit status. SC-006 and SC-008
were fixed in M1.13; the selected live gate again covers all twelve scenarios.

### Local web interface (optional) — M2 WEB-A

```bash
uv run --locked hafi web --fixtures fixtures/scenario-pack-v1
```

Open the printed `http://127.0.0.1:…/#token=…` URL. Without `--live` or `--local`
the page offers the authored demonstrations and the recorded `gpt-6-luna` traces
from the evidence package, with no credentials and no model calls. Adding
`--release-fixtures fixtures/saturday-release --config haf.release.example.toml --live`
(with the env-file) allows paid model runs and follow-ups under the same limits as
`hafi run`. The CLI remains the required interface. See the
[design](implementation/m2-local-web-ui-design.md) and
[implementation notes](development/m2-web-a-local-web-interface.md).

## Specification notes

All seven core requirements and eight approved M1 implementation/design
documents are present. The additional M1.6-D model/runtime and M1.6-F capability
profile designs are drafts.
The older technical plan still marks dependency management and several safeguards
as open; the approved configuration baseline resolves uv and its lockfile,
invocation limits/timeouts, and trace write-failure handling. Provider/model defaults
remain unset; the owner's subsequent release approval authorizes the explicit
opt-in tuple described above without rewriting the baselines. The planning-only
notices in AGENTS.md and specifications precede the separate implementation
authorizations recorded in development notes and the release scope supplement.

Existing path irregularity: `docs/decisions/README.md` is a directory rather than
a Markdown file. It is preserved. Existing data and approved specifications
remain unchanged; the empty bootstrap placeholders were removed for submission.
