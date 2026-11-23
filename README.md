
# Hawaii Activity Planner

Capstone project for Carnegie Mellon University's Agentic AI Systems program.

## Problem and intended users

Hawaii visitors and recreational ocean participants must combine weather,
marine reports, advisories and local beach characteristics when choosing where
and when to swim, snorkel or stand-up paddleboard (SUP). Hawaii Activity Planner
investigates that evidence and explains supported options and uncertainties.

Maui is the initial geographic implementation. Other Hawaiian islands are
envisioned for future versions; they are outside the submitted M1 implementation.
The repository remains `timsatterfield/hawaii-activity-forecaster`, and the Python
package remains `hawaii_activity_forecaster`. CLI banners and archived
specifications retain the original Hawaii Activity Forecaster label.

**Completed milestone:** M1 — Synthetic End-to-End Forecaster, the evaluated
capstone baseline; its behavior is frozen. M1 uses fictional beaches and synthetic
environmental evidence; it does not provide validated real-world ocean safety
recommendations or retrieve current Maui conditions. An optional local web
interface (M2 WEB-A) was added after the M1 evaluation. It displays the same
validated results and traces, and changes no agent, tool or safety behavior.

## Quick review (no credentials, no model calls)

With [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.12+,
from the repository root:

```bash
uv sync --locked
uv run --locked pytest
uv run --locked hafi demo advisory --fixtures fixtures/scenario-pack-v1
uv run --locked hafi trace docs/evaluation-evidence/representative-traces/sc-012-round3-step2-failed-closed.jsonl
uv run --locked hafi web --fixtures fixtures/scenario-pack-v1
```

| Command | What it shows |
|---|---|
| `pytest` | The offline test suite; no credentials or network calls |
| `hafi demo advisory` | An authored run through the real validators: one beach excluded by an official advisory, another recommended |
| `hafi trace …` | Validation of a recorded genuine `gpt-6-luna` investigation that failed closed on an invalid model plan |
| `hafi web` | The local web interface: authored demos and the six recorded `gpt-6-luna` runs. Open the printed URL |

The [submission summary](docs/submission-summary.md) explains the evidence types
and limitations, and the [evaluation evidence](docs/evaluation-evidence/README.md)
package holds the recorded traces, reports, aggregates and checksums.

## Architecture and reasoning boundary

- **Coordinator:** interprets requests, delegates investigations and reviews results.
- **Weather Agent:** plans authorized weather-related retrieval operations.
- **Ocean Agent:** plans authorized marine-related retrieval operations.
- **Trusted Python components:** independently validate evidence, enforce tool
  permissions and safety policies, and determine recommendation eligibility.
- **LangGraph:** orchestrates the three model-driven roles; a local JSON catalog
  supplies curated geographic inputs and local JSONL records investigations.

M1 performs constrained model-driven planning. Specialists generate conditional
plans before environmental retrieval. Trusted execution activates their retries
and fallbacks from observed outcomes, within the approved budgets. Unrestricted
observation-driven specialist replanning is not implemented in M1. Authored
`demo` plans and offline scripted-model tests are separate from genuine model
inference; the evidence types are distinguished below.

## Evaluation results

All genuine model-driven runs used OpenAI `gpt-6-luna` (profile `m1-saturday-runtime-0.8`)
against synthetic environmental data. Twelve acceptance scenarios were each run four times.

| Measure | Result |
|---|---|
| Scenario evaluations | **47/48 passed**; the one failure (SC-012, round 3) failed closed |
| Investigations | 52: 43 recommendations, 8 explained abstentions, 1 technical failure |
| Operationally successful | 51/52 |
| Median run time | 9.48 s (259 model calls and 414 tool calls in total) |
| Automated tests (M1 snapshot) | 1,530 passed, 1 documented expected failure |

These results show the system behaves as designed on a small, fixed set of synthetic requests.
They do not measure real-world forecasting accuracy. Representative traces, reports, the
full four-round aggregate and checksums are in the
[evaluation evidence package](docs/evaluation-evidence/README.md); the
[submission summary](docs/submission-summary.md) explains the evidence types.

## Running it with a live model

Live runs make **paid** OpenAI calls. Put `OPENAI_API_KEY=...` in `keys/apsi.env` (ignored by
Git), then:

```bash
uv run --locked --env-file keys/apsi.env hafi run \
  "Where should I snorkel tomorrow morning near Kihei?" \
  --fixtures fixtures/saturday-release --config haf.release.example.toml \
  --live --max-investigations 1
```

The same live runs are available in the local web interface:

```bash
uv run --locked --env-file keys/apsi.env hafi web --fixtures fixtures/scenario-pack-v1 \
  --release-fixtures fixtures/saturday-release --config haf.release.example.toml --live
```

Environmental data stays synthetic. The fixture clock is November 16, 2026, 09:00 HST, so
"tomorrow" is November 17, with evidence for **08:00–11:00** or **12:00–16:00 HST**. Follow-ups,
other synthetic cases, the local Ollama target and configuration details are in the
[development guide](docs/development-guide.md#model-driven-synthetic-release).

## Documentation

See [requirements](docs/requirements/) and [implementation plans](docs/implementation/)
for the approved specifications.

- [Development guide](docs/development-guide.md): release status and model profiles, configuration, fixtures, each M1 increment and specification status.
- [Submission summary](docs/submission-summary.md): offline reviewer setup, evidence scope and current limitations.
- [Portable evaluation evidence](docs/evaluation-evidence/README.md): representative genuine-model traces, saved reports, the four-round aggregate and a checksum manifest.
- [M1 completion report](docs/development/m1-completion-report.md): criterion coverage, live evidence and close-out limitations.
- [Reliability baseline](docs/development/m1-reliability-baseline.md): read-only trace metrics, failure categories and separate saved scenario outcomes.
- [Demo runbook](docs/demo-runbook.md): offline rehearsal, expected results, trace inspection and reference live commands.
- [Release checklist and GitHub test gate](docs/development/m1-release-readiness-and-demo.md): M1 evidence, required-check setup and remaining acceptance gaps.
