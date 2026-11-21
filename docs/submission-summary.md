# Hawaii Activity Planner — M1 submission summary

**Hawaii Activity Planner** is a Carnegie Mellon University Agentic AI Systems
capstone for Hawaii visitors and recreational ocean participants choosing locations
for swimming, snorkeling and stand-up paddleboarding (SUP). Maui is the initial
geographic implementation; other Hawaiian islands are envisioned for future versions.
Repository and package identifiers remain `timsatterfield/hawaii-activity-forecaster`
and `hawaii_activity_forecaster`.

The completed milestone is **M1 — Synthetic End-to-End Forecaster**, with feature
development frozen for submission. It uses fictional beaches and fixed synthetic
environmental evidence. It does not provide validated real-world ocean safety
recommendations or establish real-world forecasting accuracy.

Coordinator, Weather and Ocean roles operate through LangGraph. Models perform
constrained planning; specialists submit conditional plans before retrieval.
Trusted Python independently validates evidence, enforces permissions and safety
policies, and determines eligibility. It activates conditional recovery from
observed outcomes. Unrestricted observation-driven specialist replanning is not
implemented in M1.

## Reviewer setup: no credentials or model calls

Use Python 3.12+ and uv. From the repository root:

```bash
uv sync --locked --python 3.12
uv run --locked hafi --version
uv run --locked hafi demo advisory --fixtures fixtures/scenario-pack-v1
uv run --locked hafi demo outage --fixtures fixtures/scenario-pack-v1
uv run --locked hafi demo session --fixtures fixtures/scenario-pack-v1
uv run --locked pytest
```

Dependency installation may require internet access. The demo commands and tests
use local fixtures or explicit mock HTTP; no API credential or running model server
is needed. The package version is 0.1.0. The fixture clock is November 16, 2026,
09:00 HST; “tomorrow morning” is November 17, 08:00–11:00 HST.

| Command | What to observe | Expected exit |
|---|---|---|
| `demo advisory` | Beach B recommended; Beach A visibly excluded for an official advisory; attribution and limitations retained | 0 |
| `demo outage` | Explained abstention after bounded unsuccessful recovery | 0 |
| `demo session` | Revisions 1 and 2, same session and new investigation/evidence | 0 |
| `hafi trace PATH` | Independent validation and metrics for a generated JSONL file | 0 for a valid trace |
| `evaluate SC-004 --fixtures fixtures/scenario-pack-v1 --component` | 84 component assertions PASS; scenario BLOCKED with AUTHORED_COMPONENT_SCOPE | 2 |

The `demo` commands use authored component plans. They exercise the trusted graph,
tools and validators, but make zero model calls. They are not full model-driven
acceptance runs. See the [demo runbook](demo-runbook.md) for trace paths and commands.

## Model-driven execution and evidence

The separate `hafi run` and `hafi evaluate --agent` commands connect the three
roles to the explicitly enabled model target. The current release configuration
selects `gpt-6-luna`, profile `m1-saturday-runtime-0.8`, with LangSmith disabled.
Defaults are disabled; live execution requires an explicit configuration, local
credential and `--live` opt-in. It makes paid calls and is not needed for the
offline review above. Local Qwen is experimental and deferred.

## Final M1 evaluation snapshot

All genuine model-driven evaluations used **`gpt-6-luna`**. The current historical
evaluation profile is **`m1-saturday-runtime-0.8`**. The
[completion report](development/m1-completion-report.md#profile-08-reliability-sample-2026-11-20)
records four complete rounds against the twelve registered acceptance scenarios:

| Measure | Verified result |
|---|---|
| Existing pytest suite | **1,530 passed; one documented expected failure; zero unexpected failures** |
| Registered acceptance scenarios | **12**, currently selected with zero deferred |
| Historical scenario outcomes | **47/48 PASS** across four profile 0.8 rounds |
| Historical investigations | **52**: 43 recommendations, 8 explained abstentions, 1 technical failure |
| Operational successes | **51/52**, counting recommendations and explained abstentions |

The expected pytest failure concerns the deferred experimental Ollama preferred-area
input bound; it is not a genuine-model evaluation using Qwen. The one profile 0.8
technical failure was an SC-012 follow-up whose Ocean plan named an invalid option;
validation rejected it and the investigation failed closed. Older profile 0.7
failures, subsequent fixes and re-enablement remain in the
[historical deferment record](development/m1-live-acceptance-deferments.md).

These are distinct evidence types:

1. **Authored demonstrations:** fixed component plans through the trusted execution
   and validation stack, with zero model inference calls.
2. **Offline scripted-model component tests:** explicit mock HTTP/scripted responses
   exercise contracts and execution. Full scenario acceptance remains BLOCKED under
   offline transport; component assertion success is not genuine model inference.
3. **Recorded genuine-model investigations:** historical `gpt-6-luna` calls against
   synthetic environmental fixtures, with trace-bound saved evaluation results.

SC-007's six optional Snorkel Store checks failed in each round because the model
skipped that redundant source: 24 optional failures in total. Intentionally blocked
optional assertions remain in SC-005, SC-006, SC-007, SC-008 and SC-012. Scenario-level
PASS therefore does not imply every optional assertion passed.

**Historical evaluation artifacts are not currently included in the tracked
repository and are not publicly available from a fresh clone.** The completion
report records identifiers, digests and outcome summaries. Reviewers can generate
new authored traces with the offline commands above; these are a different evidence
type and cannot recreate or replace the historical genuine-model investigations.

The four-round results describe a small historical development sample of fixed
requests and synthetic conditions. They do not establish real-world ocean forecasting
accuracy or production reliability. The earlier clean-checkout result of 1,499
passing tests is preserved as a dated historical snapshot in the completion report;
it is not the final test count.

## Remaining scope

Verified real-beach catalog completion, live environmental providers, production
freshness/hazard/materiality criteria and active clarification resumption remain
outside this release. The existing CLI supports post-terminal follow-ups; when
clarification is required, a complete clarified request starts a new run.

The approved [technical plan](implementation/m1-technical-plan.md) and
[release scope](implementation/m1-saturday-release-scope.md) define M1. No claim
of complete real-world MVP acceptance is made. GitHub's offline test workflow
runs separately from live acceptance and uses no model credentials.
