# Bounded OpenAI pilot — November 19, 2026

**Status:** Completed within the owner's $1 / ten-investigation authorization  
**Result:** Eight expected outcomes; two earlier normalization calibration failures retained

This verifies a working model-driven synthetic path using OpenAI `gpt-6-luna`:
Coordinator normalization/planning, Weather/Ocean planning, synthetic retrieval,
deterministic validation and authoritative JSONL executed together. No live
environmental data or real-beach recommendation is claimed. Local Qwen is deferred
at the owner's request.

## Access and safeguards

The credential is stored in `keys/apsi.env` and loaded explicitly into child
processes through uv. After the pilot, the file was moved from the repository root
at the owner's request with its contents and permissions unchanged. It was never
displayed or embedded in code/configuration, prompts or traces. `.gitignore`
excludes the `keys/` directory. The owner's example env-file was preserved and
checked not to contain the supplied credential.

The thirty-second model deadline, fixed input/output bounds, twelve model/twelve
tool calls, five Coordinator cycles, two specialists, bounded recovery, three
recommendations, zero SDK/model retries, `store=False`, standard service tier and
disabled remote tracing stayed enforced. The provider/model never switched.

All ten authorized investigations have been used. No additional paid investigation
was run afterward. The approved manually bounded pilot was audited from retained
JSONL; no general persistent spending ledger was introduced.

## Actual checks

Each row has a complete independently validated terminal trace in the ignored
`traces/openai-pilot/` directory. Counts include failed dispatches. Independent
assertions were separate from application/model inputs; expected results, scripts
and policy premises were never model context. The first run exercised the installed
CLI; subsequent checks used the same AgentSession/runtime APIs.

| # | Check | Prompt profile | Observed result | Model / tool calls |
|---|---|---|---|---:|
| 1 | Favorable snorkeling, morning | `0.1` | RECOMMENDATIONS; three fictional eligible locations | 5 / 8 |
| 2 | Detailed SUP, afternoon | `0.1` | ERROR; trusted request validation rejected proposal | 1 / 0 |
| 3 | Detailed SUP diagnostic repeat | `0.1` | ERROR; `MODEL_CHANGE_VALUE_INVALID` | 1 / 0 |
| 4 | Detailed SUP, afternoon, South Maui only | `0.2` | RECOMMENDATIONS; only B; experience/constraints/preference preserved | 5 / 5 |
| 5 | Favorable swimming, morning | `0.2` | RECOMMENDATIONS; three fictional eligible locations | 5 / 9 |
| 6 | Official water-contact avoidance advisory | `0.2` | A EXCLUDED; eligible alternatives recommended | 5 / 8 |
| 7 | Primary timeout, failed retry, successful alternates | `0.2` | RECOMMENDATIONS; one retry and two per-gap fallbacks | 5 / 12 |
| 8 | Primary/retry/alternate outage | `0.2` | NO_RECOMMENDATION; one retry and two per-gap fallbacks | 5 / 11 |
| 9 | Initial snorkeling request near Kihei | `0.2` | RECOMMENDATIONS; valid session/retained trace | 5 / 8 |
| 10 | Post-terminal preference change to Napili | `0.2` | RECOMMENDATIONS; C preferred; new revision/fresh evidence | 5 / 8 |

Follow-up assertions confirmed the same session, a new investigation ID and request
revision 2, inherited activity/absolute time window, fresh finding IDs and budgets,
and byte-for-byte unchanged prior trace. Every successful investigation used two
genuine Coordinator cycles and both specialist model roles. Environmental outage
remained abstention; normalization failures remained technical errors without tool
calls or fabricated recommendations.

Complete metrics and trace filenames are retained locally in
`traces/openai-pilot/pilot-summary.json`. Neither that summary nor JSONL contains raw
prompts/proposals, SDK objects, credentials or private reasoning.

## Normalization calibration

The two failed `0.1` attempts are not passes. The first trace records request-
validation rejection but does not retain the proposal or identify a particular
field; the second identifies invalid logical change-value encoding. Neither was
converted to favorable evidence, environmental unavailability or an automatic retry.

The new explicit `m1-saturday-runtime-0.2` profile adds concise JSON string/array
encoding guidance, hard-versus-soft geographic guidance and mechanical Unicode
token offsets. These offsets provide no interpreted answer; the model still
selects meaning/support, and trusted request validation is unchanged. No invalid
JSON repair, guessed values, span correction or relaxed safety was added.
Earlier prompt bytes/version remain available for independent validation of retained
traces. The release example TOML now explicitly selects `0.2`.

Offline testing caught an input-bound problem in the first candidate prompt for
inherited follow-ups. The instructions were shortened before any `0.2` paid run;
no input was truncated and no limit increased. All seven later live investigations
on `0.2` passed their independent assertions. This small sample does not prove
reliability for every future utterance or model-alias revision.

## Usage and estimated cost

The trace audit reconstructs **10 investigations, 42 model calls and 69 synthetic
tool calls**. Model operations were 10 normalizations, 16 Coordinator plans, eight
Weather plans and eight Ocean plans; all reported `gpt-6-luna`.

Reported usage was **44,659 input tokens and 10,114 output tokens**, known for all
calls. The slowest model operation took **6.704 seconds**; successful complete
investigations took approximately **10.2–15.4 seconds**. Entered dispatches retained
**$0.105 in conservative reservations**, including failures, below the $1 ceiling.

[Official pricing](https://developers.openai.com/api/docs/models/gpt-6-luna),
rechecked before the pilot, listed $0.10/M input, $0.50/M output and $0.125/M cache
writes. Standard rates applied to reported totals give **$0.00952290**, about one
cent before caching effects; pricing every input token at the higher cache-write
rate gives **$0.01063937**. These are usage-based estimates, not an observed invoice
or account balance. Reservations are an audit safeguard, not billed charges.

## Regression and remaining scope

- `uv run --locked pytest`: **1,362 passed, 13 warnings in 55.62s**, Python 3.14.8.
  Warnings remain upstream LangSmith asyncio deprecations.
- Focused model/runtime/CLI/trace checks: **129 passed**, 13 warnings.
- The Unicode-offset assertion now covers current OpenAI and local projections.
  Existing schemas, evidence/safety validation and fixture bytes are preserved.
- All old/new pilot records independently validate under their own prompt versions.
- No dependency/lockfile, approved requirements/architecture, CI, commit or push
  changes were introduced by the pilot. The credential remains ignored.

Live clarification was not exercised within the exhausted ten-investigation
allowance; offline SDK/CLI/graph tests cover it. Stale/conflict/injection variants
and all six activity/daypart combinations retain offline coverage. Full registered
SC-004/SC-010 gates remain BLOCKED; the pilot does not relabel authored component
results or unresolved real-world policy/catalog/threshold requirements as PASS.

The synthetic CLI is demonstrated with genuine model-driven roles for the listed
checks. Next: owner review, synthetic demo rehearsal and remaining acceptance
review. Additional paid checks are outside this exhausted pilot allowance.
