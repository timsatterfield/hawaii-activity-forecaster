# M1 submission summary

This repository implements a synthetic Hawaii Activity Forecaster for a Carnegie
Mellon University Agentic AI Systems capstone. It supports swimming, snorkeling
and stand-up paddleboarding through a CLI, with Coordinator, Weather and Ocean
roles, LangGraph coordination, deterministic validation and local JSONL traces.

The demonstration uses fictional beaches and fixed environmental evidence.
It does not retrieve current Maui conditions or establish real-world ocean safety.

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

The [completion report](development/m1-completion-report.md) maps the fifteen
approved M1 criteria to tests and recorded live evidence. All twelve scenarios
have historical live passes across profiles 0.6/0.7. The latest all-twelve profile
0.7 batch passed **10/12**. SC-006 and SC-008 were then diagnosed and fixed (profile
0.8 normalize guidance, and SC-008 option names that avoid reserved prompt tokens).
Both passed live on profile 0.8 and are re-enabled. A subsequent all-twelve live
batch on 0.8 passed **12/12**. Across four full rounds on 0.8 (that batch plus three
more), **47/48** scenario runs passed, with 51/52 operational successes. The one failure, an SC-012 follow-up
where the Ocean plan named an invalid option, failed closed. See the
[completion report](development/m1-completion-report.md). Their earlier failures remain documented. No offline tests or
safety assertions were disabled.

SC-007's passing live report also contains six optional failures for a skipped
redundant source. Optional blocked checks cover unresolved production rules and
other explicit limitations. A scenario-level PASS is not a claim that every
optional assertion passed. See the [deferment record](development/m1-live-acceptance-deferments.md).

Historical traces and raw reports are ignored local artifacts, absent from a
fresh clone. The completion report contains their identifiers, digests and outcome
summaries. Reviewers can regenerate fresh authored traces with the offline commands;
those new traces must not be relabeled as recorded genuine model execution.

## Verification snapshot (2026-11-20)

A fresh public-source copy installed from `uv.lock` on Python 3.12.14 and passed
**1499 tests, with 1 expected failure**, in 81.81 seconds. The expected failure
covers the deferred experimental Ollama preferred-area input bound. Startup,
all three authored demos, trace validation, SC-004 component evaluation and the
selected-live preview also passed without model credentials or paid calls.
See the completion report for the exact verification scope and earlier CI evidence.

## Remaining scope

Verified real-beach catalog completion, live environmental providers, production
freshness/hazard/materiality criteria and active clarification resumption remain
outside this release. The existing CLI supports post-terminal follow-ups; when
clarification is required, a complete clarified request starts a new run.

The approved [technical plan](implementation/m1-technical-plan.md) and
[release scope](implementation/m1-saturday-release-scope.md) define M1. No claim
of complete real-world MVP acceptance is made. GitHub's offline test workflow
runs separately from live acceptance and uses no model credentials.
