# Portable evaluation evidence

This folder lets a reviewer inspect genuine model-driven investigations of the
**Hawaii Activity Planner** without API credentials, paid inference or the original
development machine. It supports the M1 evaluation claims in the
[submission summary](../submission-summary.md) and the
[completion report](../development/m1-completion-report.md#profile-08-reliability-sample-2026-11-20).

**Start with the [evaluation summary](evaluation-summary.md)**, which gives the
results, denominators and limitations.

## Contents

| Path | What it is |
|---|---|
| [evaluation-summary.md](evaluation-summary.md) | Objectives, results across four rounds, failures and limitations |
| [evidence-manifest.json](evidence-manifest.json) | Provenance and SHA-256 checksum for every published artifact |
| `representative-traces/` | Six original JSONL investigation traces, copied byte for byte |
| `representative-reports/` | Five original saved scenario reports, copied byte for byte |
| [aggregate/four-round-reliability.md](aggregate/four-round-reliability.md) | `hafi reliability` summary of all 52 investigations and 48 reports |
| `aggregate/four-round-reliability.json` | The same summary as JSON, including per-investigation metrics |
| `aggregate/scenario-round-matrix.json` | Derived matrix of all 48 scenario evaluations, with mandatory and optional assertion counts |

The whole folder is about 1.4 MB.

## How the evaluation was run

Each of the twelve registered acceptance scenarios was run once per round with
`scripts/run_live_acceptance.py --live`, over four rounds on 2026-11-20. Every run
used the full agent runtime with `gpt-6-luna` and profile
`m1-saturday-runtime-0.8`, against synthetic environmental fixtures. The runner
saved one JSONL trace per investigation and one scenario report per scenario. Each
report binds to its traces by SHA-256 digest. The original batch directories stay
local and are not tracked; the manifest names each one.

## Why these examples

One example per behavior a reviewer is likely to ask about. The rest of the
dataset is summarized in `aggregate/`, not published in full.

| Example | Trace | Behavior shown | Where to look |
|---|---|---|---|
| A. Recommendation | `sc-001-round0-recommendation.jsonl` | Request normalization, Weather and Ocean planning, eight tool calls, evidence validation, three eligible beaches recommended | `REQUEST_NORMALIZED`, `AGENT_COMPLETED`, `CANDIDATE_ELIGIBLE`, final `INVESTIGATION_COMPLETED` |
| B. Advisory exclusion | `sc-004-round0-advisory-exclusion.jsonl` | Beach A excluded under the official water-contact advisory policy `HM-WATER-001` despite otherwise favorable claims; Beach B eligible and the only recommendation | `CANDIDATE_EXCLUDED` (A) with `decision_reasons`, `CANDIDATE_ELIGIBLE` (B) |
| C. Conditional recovery | `sc-009-round0-conditional-recovery.jsonl` | Primary marine source times out (`SOURCE_TIMEOUT`); two authorized fallbacks recover the evidence; all five beaches eligible, three recommended | `TOOL_FAILED`, `FALLBACK_INITIATED` ×2, `INVESTIGATION_COMPLETED` |
| D. Explained abstention | `sc-010-round0-explained-abstention.jsonl` | Required ocean sources unavailable; one retry and two fallbacks, all within allowance; no recommendation given | `TOOL_FAILED`, `RETRY_INITIATED`, `FALLBACK_INITIATED`, `INVESTIGATION_LIMIT_REACHED`, `INVESTIGATION_ABSTAINED` |
| E. Failed closed (context) | `sc-012-round3-step1-session-start.jsonl` | First step of the session: Kihei request, recommendations for A and C | `INVESTIGATION_COMPLETED` |
| E. Failed closed | `sc-012-round3-step2-failed-closed.jsonl` | Follow-up revision: the Ocean plan names an option not on its allowlist; trusted validation rejects it with `MODEL_PLAN_OPTION_NOT_ALLOWED`; zero tool calls; investigation FAILED | `CONTRACT_VALIDATED` with `valid: false` (events 20, 22), `INVESTIGATION_FAILED` |

The matching saved reports are `sc-001-round0.json`, `sc-004-round0.json`,
`sc-009-round0.json`, `sc-010-round0.json` and `sc-012-round3.json`. The SC-012
report is the round's FAIL result and binds to both SC-012 traces.

Round 0 provides examples A–D because it was the first complete profile 0.8
round. The same behaviors recur in every round, as the matrix shows. The only
SC-012 failure is in round 3.

## Genuine model runs versus authored demonstrations

The traces here record real model calls: 4–5 per investigation, each with the
returned model identifier `gpt-6-luna`. The `hafi demo` commands produce traces of
the same shape from fixed, authored plans with **zero** model calls. Those
demonstrations are a different kind of evidence and are not included here.

The application records model identity and execution mode in the trace. They are
not independent proof that network inference took place.

## Which artifacts support which claims

| Claim | Supporting artifact |
|---|---|
| 47/48 scenario evaluations passed | `aggregate/scenario-round-matrix.json`; saved-report table in `aggregate/four-round-reliability.md` |
| 52 investigations: 43 recommendations, 8 abstentions, 1 failure; 51/52 operational | Trace-group `statuses` and `operational_success` in `aggregate/four-round-reliability.json` |
| 259 model calls, 414 tool calls, median 9,477 ms | `model_calls`, `tool_calls`, `terminal_duration_ms` in the same file |
| SC-012 failed closed on an invalid option | `representative-traces/sc-012-round3-step2-failed-closed.jsonl` and `representative-reports/sc-012-round3.json` |
| SC-007 optional failures (24) and blocked optional assertions (20) | `optional_failed_assertion_ids` and `optional_blocked_assertion_ids` in the matrix |
| All runs used `gpt-6-luna`, profile 0.8, `LIVE_PROVIDER` | `profile_id` and `execution_mode` in the reliability JSON; `INVESTIGATION_STARTED` configuration in each trace |
| 1,530 passing tests | Reproduce with `uv run --locked pytest`; not stored here |

## Checking the evidence yourself

These commands need no credentials and make no model calls. Run them from the
repository root after `uv sync --locked`.

Validate one trace. Each prints its event count, digest, completeness and
metrics, and exits 0 when valid:

```bash
uv run --locked hafi trace docs/evaluation-evidence/representative-traces/sc-012-round3-step2-failed-closed.jsonl
```

Validate all six traces and check that every report binds to its traces. The
command exits 1 if any trace is invalid or any report fails to bind:

```bash
uv run --locked hafi reliability docs/evaluation-evidence/representative-traces --reports docs/evaluation-evidence/representative-reports
```

Expected result: 6 validated investigations, 0 input issues, 5/6 operational
successes (the SC-012 failure is the sixth), and the failure codes
`MODEL_PLAN_OPTION_NOT_ALLOWED` and `MODEL_INVESTIGATION_INACTIVE`. These numbers
describe the six examples, not the full evaluation.

Verify every published checksum against the manifest:

```bash
uv run --locked python -c "import hashlib,json,pathlib; r=pathlib.Path('docs/evaluation-evidence'); m=json.load(open(r/'evidence-manifest.json')); bad=[a['portable_path'] for a in m['artifacts'] if hashlib.sha256((r/a['portable_path']).read_bytes()).hexdigest()!=a['published_sha256']]; print('mismatches:', bad or 'none')"
```

Confirm that the rejected plan ran no tools:

```bash
grep -c '"event_type":"TOOL_CALLED"' docs/evaluation-evidence/representative-traces/sc-012-round3-step2-failed-closed.jsonl
```

This prints `0`. Applied to `sc-001-round0-recommendation.jsonl`, it prints `8`.

## What this package cannot establish

- **The full aggregate cannot be re-derived from this folder.** It holds six of
  the 52 traces and five of the 48 reports. The aggregate files were produced from
  the complete local dataset, which is not published.
- **Network inference is not proven.** Model identity and mode are application
  records.
- **The evaluated source revision is unknown.** It was not recorded; see the
  summary.
- **Assertions are not re-evaluated.** `hafi reliability` reads the saved outcomes.
  Re-running the assertions requires the live runner.
- **Synthetic data only.** Nothing here measures real-world forecasting accuracy.

## Privacy review

Every published file was checked for credentials, authorization headers, API
keys, tokens, personal names, email addresses, absolute or user paths, and
non-synthetic URLs, including nested JSON fields.

The traces contain no raw request text, prompts or model replies
(`raw_payloads_retained: false`). Their identifiers are application-generated
UUIDs and digests, and the only URLs are synthetic `example.invalid` addresses.
No redaction was needed, so traces and reports are published unchanged and
their checksums match the originals. Each artifact's status is in the manifest.
