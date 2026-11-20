# M1 synthetic demo runbook

Run commands from the repository root. Use Python 3.12+ and
[uv](https://docs.astral.sh/uv/getting-started/installation/).
This demo uses fictional locations and synthetic environmental data throughout.

The dataset's reference clock is **November 16, 2026, 09:00 HST**. "Tomorrow" means
**November 17**, with morning **08:00–11:00** and afternoon **12:00–16:00 HST**.
These fixed dates make results repeatable; they are not today's Maui conditions.

## Offline rehearsal

These commands need no API key, model server or paid calls. They demonstrate
authored component plans and independently checked outputs. Real model planning
was demonstrated by the original pilot and subsequent registered-scenario runs.
The [M1 completion report](development/m1-completion-report.md) indexes all twelve
live scenario passes and their remaining optional assertions.

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

## Current acceptance baseline

The release configuration selects **`m1-saturday-runtime-0.7`** with `gpt-6-luna`.
The registered pack is dataset **`1.6.0`**, format `2.0.0`. All twelve scenarios have
recorded live scenario-level PASS results: eleven on profile 0.6 and SC-002 on 0.7.
This is historical evidence across versions. The subsequent authorized all-twelve
0.7 rerun passed **10/12**; SC-006 and SC-008 failed. See the
[completion report](development/m1-completion-report.md#profile-07-rerun-and-sc-006-investigation-2026-11-20)
for the current regression result and SC-006 diagnosis.
Profile 0.7 changes only request-normalization guidance; older profiles remain
available for validating their traces.

Scenario PASS means the mandatory executable assertions pass. Optional blocked
assertions remain for real wind-hazard classification (SC-005), clear-water
preference interpretation (SC-006), production freshness cutoffs (SC-007), material
conflict classification (SC-008) and historical evidence reuse (SC-012). SC-007's
recorded passing run also has six optional FAIL assertions for a skipped redundant
Snorkel Store report. See the completion report for exact evidence and decisions.

### Optional all-twelve live confirmation

**Paid reference commands; not part of the offline rehearsal.** Run only after
new authorization. A normal pass uses about **65 model calls across thirteen
investigations** (SC-012 has two). Actual plans may differ; the existing bound is
12 model calls per investigation, up to 156 for this batch. No batch-wide dollar
ledger is provided. Each command below runs once, with no automatic rerun.

Run in Bash or zsh from the repository root. The timestamped directory keeps this
batch separate from earlier reports and traces. Reports are saved even on failure;
the final summary returns a failure if any scenario did not pass.

```bash
acceptance_run="traces/acceptance-0.7-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$acceptance_run"
for scenario in SC-001 SC-002 SC-003 SC-004 SC-005 SC-006 SC-007 SC-008 SC-009 SC-010 SC-011 SC-012; do
  if uv run --locked --env-file keys/apsi.env hafi evaluate "$scenario" \
    --fixtures fixtures/scenario-pack-v1 --agent --config haf.release.example.toml \
    --live --trace-directory "$acceptance_run" > "$acceptance_run/$scenario.json"; then
    echo "$scenario: PASS"
  else
    echo "$scenario: non-PASS; inspect its report and trace"
  fi
done
python3 - "$acceptance_run" <<'SUMMARY'
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
passed = 0
for number in range(1, 13):
    scenario = f"SC-{number:03d}"
    try:
        report = json.loads((root / f"{scenario}.json").read_text())["scenario"]
        print(scenario, report["outcome"], report["counts"])
        passed += report["outcome"] == "PASS"
    except (OSError, ValueError, KeyError, TypeError):
        print(scenario, "missing or invalid report")
print(f"{passed}/12 scenario-level passes; inspect optional FAIL/BLOCKED rows too.")
sys.exit(0 if passed == 12 else 1)
SUMMARY
```

### Optional live clarification check

This separate reference command should print clarification questions and exit
**`2`**, with **one normalization model call, zero specialist requests and zero
environmental tool calls**. Inspect the new trace using `hafi trace`. It does not
resume clarification in the same investigation; a complete request starts a new run.
The owner-authorized close-out check passed live on profile 0.7 with these counts
and exit code. Its validated trace ends at `CLARIFICATION_REQUESTED`, so
`complete: false` is expected while awaiting input. See the
[completion report](development/m1-completion-report.md#authorized-live-clarification-check-2026-11-20)
for the trace digest. A new invocation still requires its own authorization.

```bash
uv run --locked --env-file keys/apsi.env hafi run "Where tomorrow morning?" \
  --fixtures fixtures/saturday-release --config haf.release.example.toml \
  --live --max-investigations 1 --trace-directory traces/clarification-0.7
```

## Real-model command cards

These are reference commands for a separately authorized future demo. They make
paid OpenAI calls. The original ten-investigation pilot is historical; subsequent
owner-run acceptance evidence is indexed in the completion report. New live commands
require a separately agreed spending/call allowance. Keep the key local in
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
| Clarification | "Where tomorrow morning?" | Questions without environmental retrieval/recommendations; exit `2`; submit a complete clarified request in a new run | Offline SDK/CLI checks and live profile 0.7 close-out check |

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
