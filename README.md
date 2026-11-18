
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

M1.1-B — Pydantic Schema Implementation. The Python package, information CLI,
and structural data contracts are available. Agent execution, environmental
recommendations, scenario fixtures, and safety evaluation remain for later
increments. The LLM provider/model is undecided.

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
`agents`, `orchestration`, `validation`, and `tools`. The `models` package contains
the Pydantic contracts; the other areas remain placeholders for later work.

See [M1.1-B model notes](docs/development/m1-1b-models.md) for schema coverage,
serialization choices, validation boundaries, and unresolved specification details.
Run the model tests alone with `uv run --locked pytest tests/test_models.py`.

## Specification notes

All seven core requirements and six M1 implementation documents are present.
The older technical plan still marks dependency management and several safeguards
as open; the approved configuration baseline resolves uv and its lockfile,
invocation limits/timeouts, and trace write-failure handling. Its provider/model
decision remains open. The planning-only notices in AGENTS.md and specifications
precede the separate authorization for this bootstrap increment.

Existing path irregularity: `docs/decisions/README.md` is a directory rather than
a Markdown file. It is preserved. Existing `src/tmp.txt`, `tests/tmp.txt`, data,
and approved specifications are also preserved.
