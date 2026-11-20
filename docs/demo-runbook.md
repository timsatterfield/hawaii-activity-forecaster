# M1 synthetic demo runbook

Run commands from the repository root. Use Python 3.12+ and
[uv](https://docs.astral.sh/uv/getting-started/installation/).
This demo uses fictional locations and synthetic environmental data throughout.

The dataset's reference clock is **November 16, 2026, 09:00 HST**. "Tomorrow" means
**November 17**, with morning **08:00–11:00** and afternoon **12:00–16:00 HST**.
These fixed dates make results repeatable; they are not today's Maui conditions.

## Temporary live acceptance selection

The owner temporarily deferred the failing profile 0.7 live checks SC-006 and
SC-008. Preview the current selection with no model calls:

```bash
uv run --locked python scripts/run_live_acceptance.py
```

The default live rerun selects ten scenarios and records the two deferred ones as
NOT_RUN. The full offline pytest suite remains enabled. See the
[deferment record](development/m1-live-acceptance-deferments.md) for the paid opt-in
command, failure evidence and re-enable criteria. This is a selected live gate;
success does not establish twelve passing scenarios on profile 0.7.

## Offline rehearsal

These commands need no API key, model server or paid calls. They demonstrate
authored component plans and independently checked outputs. Real model planning
was separately demonstrated by the [OpenAI pilot](development/m1-openai-pilot.md).

### 1. Check installation and CLI

```bash
uv sync --locked
uv run --locked hafi --version
uv run --locked hafi run --help
```

Expect version `0.1.0` and the opt-in model command's help text. No model executes.

### 2. Show an official advisory exclusion

```bash
uv run --locked hafi demo advisory --fixtures fixtures/scenario-pack-v1 \
  --trace-directory traces/demo-rehearsal/advisory
```

Expect a synthetic warning and only fictional Beach B recommended. Beach A's
applicable official water-contact avoidance advisory excludes it. Sources,
coverage, timestamps and catalog attribution accompany the validated result.
The command exits `0`; its new JSONL file is under the chosen trace directory.
A "Not recommended (excluded)" section names Beach A and its reason (an applicable
official water-contact avoidance advisory). Step 5's trace shows the same exclusion
(`excluded_candidates: 1`; `CANDIDATE_EXCLUDED` for `TEST_BEACH_A`, `HM-WATER-001`).

### 3. Show an explained abstention

```bash
uv run --locked hafi demo outage --fixtures fixtures/scenario-pack-v1 \
  --trace-directory traces/demo-rehearsal/outage
```

Expect no recommendation because mandatory ocean evidence remains insufficient
after bounded recovery. This is an operationally successful abstention, exit `0`.
Its trace shows one retry and two exhausted per-gap fallback attempts, not five
invented Coordinator cycles or a model-provider failure.

### 4. Show a post-terminal revision

```bash
uv run --locked hafi demo session --fixtures fixtures/scenario-pack-v1 \
  --trace-directory traces/demo-rehearsal/session
```

Expect two authored requests, changing the preferred area from Kihei to Wailea.
The session is retained, investigation IDs differ, request revision advances, and
each investigation retrieves its own evidence. This component example is distinct
from the real-model pilot's Kihei-to-Napili follow-up.

### 5. Inspect a trace

Choose one JSONL filename from the directory used above and replace the filename
placeholder here:

```bash
uv run --locked hafi trace traces/demo-rehearsal/advisory/INVESTIGATION_ID.jsonl
```

Expect `complete: true`, outcome `RECOMMENDATIONS`, six tool calls, zero model
calls and one Coordinator cycle for the authored advisory example. The outage
example has eight tool calls. Both include Weather and Ocean component execution;
zero model calls is the expected honest scope of these offline demonstrations.

### 6. Show independent acceptance reporting

```bash
uv run --locked hafi evaluate SC-004 --fixtures fixtures/scenario-pack-v1 \
  --component --trace-directory traces/demo-rehearsal/sc-004
uv run --locked hafi evaluate SC-010 --fixtures fixtures/scenario-pack-v1 \
  --component --trace-directory traces/demo-rehearsal/sc-010
```

These commands deliberately exit **`2`**. Expect `component.outcome=PASS`, with
**84** and **61** passing component assertions, respectively, while
`scenario.outcome=BLOCKED` and `scenario.category=AUTHORED_COMPONENT_SCOPE`.
Authored plans are not model-driven, so they never count as full acceptance.

The same registered scenarios run through the real Coordinator/Weather/Ocean
runtime with `--agent`. This makes paid calls (about five model calls per scenario)
and needs separate authorization:

```bash
uv run --locked --env-file keys/apsi.env hafi evaluate SC-004 --fixtures fixtures/scenario-pack-v1 \
  --agent --config haf.release.example.toml --live --trace-directory traces/acceptance
```

A full PASS (exit `0`, category `ASSERTIONS_EVALUATED`) is reported only when the
verified trace records the live or local model target. The offline test suite runs
the same path over mock HTTP and reports `OFFLINE_MODEL_TRANSPORT` (BLOCKED). See
[M1.7-A](development/m1-7a-agentic-scenario-adapter.md).

### 7. Run the offline workflow checks

```bash
uv run --locked pytest tests/test_agent_release.py tests/test_release_cli.py
uv run --locked pytest
```

The focused checks cover all activities/dayparts, favorable recommendations,
successful fallback recovery, abstention, advisory exclusion, clarification and
follow-ups through the installed SDK with explicit mock HTTP. No additional
offline `demo favorable` or `demo recovery` command is implied.

## Real-model command cards

These are reference commands for a separately authorized future demo. They make
paid OpenAI calls. **The prior ten-investigation pilot allowance is exhausted;
no new paid run is part of this release-readiness batch.** Keep the key local in
the ignored `keys/apsi.env`; do not print the file or add it to GitHub CI secrets.

```bash
uv run --locked --env-file keys/apsi.env hafi run \
  "Where should I snorkel tomorrow morning near Kihei?" \
  --fixtures fixtures/saturday-release --config haf.release.example.toml \
  --live --max-investigations 1 --trace-directory traces/model-demo
```

| Card | Request / options | Expected synthetic behavior | Existing evidence |
|---|---|---|---|
| Favorable | Default case; request above, or "Where should I swim tomorrow morning?" | One to three eligible fictional locations, grounded sources and default-window disclosure | OpenAI pilot; offline SDK checks |
| One supported SUP location | "SUP tomorrow afternoon only South Maui. I am intermediate and prefer calm water." | Only B investigated/recommended; unsupported A/E assessed; 12:00–16:00 window; calm preference preserved without asserting an unverified calm-water condition | OpenAI pilot; offline SDK checks |
| Advisory | Add `--case advisory` to the base request | A excluded despite location preference; eligible alternatives remain | OpenAI pilot; offline SDK checks |
| Recovery | Add `--case recovery`; ask for swimming | Primary timeout, one retry, two alternate-source fallbacks, then supported results | OpenAI pilot; offline SDK checks |
| Outage | Add `--case outage` to the base request | Explained abstention after bounded unsuccessful recovery; exit `0` | OpenAI pilot; offline SDK checks |
| Follow-up | Add `--interactive --max-investigations 2`; after the base request enter "Actually near Napili instead." | Same session, revision 2, new investigation/evidence/budgets, retained prior result | OpenAI pilot; offline SDK checks |
| Clarification | "Where tomorrow morning?" | Questions without environmental retrieval/recommendations; exit `2`; submit a complete clarified request in a new run | Offline SDK/CLI checks; not exercised in the paid pilot |

## Presenter checklist

- Start with the fixed clock and prominent synthetic-data warning.
- Name the three roles and distinguish model planning from deterministic validation.
- Show an eligible recommendation, an exclusion, an abstention and a request revision.
- Inspect the corresponding trace and actual call/recovery counts.
- State whether each example is authored, mock HTTP or a recorded real-model run.
- Keep `BLOCKED` registered-scenario results and undefined real-world criteria explicit.
- If no model access is available, use the offline rehearsal and existing pilot report.
  Local Qwen is deferred and is not the fallback for this demo.

Use the [release checklist](development/m1-release-readiness-and-demo.md) for M1
criterion coverage, GitHub setup and remaining work. Traces are ignored local
artifacts; a fresh checkout generates new offline traces and does not contain the
earlier pilot's private local files.
