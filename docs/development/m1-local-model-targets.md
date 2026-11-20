# Local and OpenAI model targets

Implements the owner's request to make both local Ollama/Qwen and OpenAI explicit
targets. The [addendum](../implementation/m1-local-model-target-addendum.md) records
the narrow change to the prior provider deferment. Existing approved logical
requirements, agent roles, environmental fixtures and execution/safety limits are
preserved. No dependency, lockfile, CI, commit or push change is required.

## Configuration and shared behavior

| Target | Configuration | CLI opt-in | Endpoint |
|---|---|---|---|
| Ollama `qwen3.5:9b` | `haf.ollama.example.toml` | `--local` | Fixed `http://127.0.0.1:11434/v1/chat/completions` |
| OpenAI `gpt-6-luna` | `haf.release.example.toml` | `--live` | Existing `https://api.openai.com/v1/responses` |

Default execution stays disabled. The flag must match the configured provider
before client construction. Every role in an investigation uses the same selected
target; a missing server, timeout or invalid proposal never switches targets.
The local target requires no API key and downloads no models. The existing OpenAI
credential/paid-pilot checks remain intact. Model identity is not inferred from
environment keys or ambient server/base-URL variables.

`model_runtime/targets.py` is a closed list of reviewed tuples and read-only
calibration versions, not a generalized plugin/profile loader. The current local
profile is `m1-ollama-qwen3.5-9b-0.5`; earlier local profiles cannot activate live
execution, but their template versions remain readable to preserve failed-run
audit records. The existing original and release OpenAI prompt bytes remain intact.

Both concrete adapters share the installed LangChain/OpenAI-compatible SDK,
HTTP-dispatch guard, response/error checks and gateway. Ollama uses the supported
Chat Completions JSON-schema format. Its current settings use low reasoning effort,
temperature zero and neutral presence/frequency penalties, rather than inheriting
the installed model's natural-language sampling defaults. On this boolean-thinking
Qwen model, low effort enables thinking; private reasoning is never traced/printed.

The local normalizer additionally receives mechanical Unicode token offsets for
the actual user text. These offsets provide no activity/date/preference interpretation
or expected answer. The model still proposes meaning and selects support; existing
request validation independently checks it. No malformed JSON repair, HTML decoding,
span correction or model-generated safety judgment is accepted.

The CLI, SessionManager, LangGraph, synthetic dispatcher, strict proposals and
evidence/safety/result checks remain shared. Per-investigation limits stay twelve
model calls, twelve tool calls, five Coordinator cycles, two specialist slots,
one retry per original, one fallback per gap and three recommendations. A local
model call has the same thirty-second deadline and 2,048-token output cap. Offline
tests enforce the twelve-call boundary and prevent a thirteenth HTTP dispatch.

JSONL records provider, profile, requested/returned model and actual execution mode:
`LOCAL_PROVIDER`, `LIVE_PROVIDER` or `OFFLINE_TRANSPORT`. The reader checks the
entire tuple, prompt/schema hashes and lifecycle. Local calls reserve zero API
dollars while retaining normal invocation counts. OpenAI retains its existing
conservative reserve. At this increment's completion its $1/ten-investigation pilot
had not run; the later [OpenAI pilot](m1-openai-pilot.md) records its completion.
No local failure can incur a fallback OpenAI charge.

## Actual local checks

Local inventory: Ollama client **0.40.16**, installed `qwen3.5:9b` ID
`d63f830f28d5`, 7.6 GB, `nvfp4`, with completion/tool/thinking capabilities.
No model was installed, downloaded, copied or replaced.

The initial seven manually initiated, bounded investigations used the same non-sensitive
synthetic request, "Where should I snorkel tomorrow morning?". No automatic retry
was introduced. Each run dispatched exactly one local normalization call and zero
environmental calls. All seven retained complete independently validated terminal
ERROR traces in the ignored `traces/ollama-smoke/` directory.

| Calibration profile | Runs | Observed outcome |
|---|---:|---|
| `0.1` | 2 | `MODEL_PROPOSAL_INVALID`: invalid span ordering; other returned values also failed the nested encoding contract. |
| `0.2` | 2 | `MODEL_JSON_INVALID`: invalid JSON embedded in `value_json`. |
| `0.3` | 1 | `MODEL_JSON_INVALID`: encoding remained invalid despite correct source offsets. |
| `0.4` | 1 | `MODEL_JSON_INVALID`: alternate valid JSON escaping instructions did not produce valid logical values. |
| `0.5` | 1 | `MODEL_TIMEOUT`: thinking-enabled inference reached the approved thirty-second deadline. |

The local transport, model identity, usage/call accounting, cancellation and failure
publication are verified against the real server. **A successful real local
request-to-result investigation is not established.** The target is experimental;
these results do not demonstrate reliable Qwen normalization, subsequent genuine
specialist planning or full scenario acceptance. Hardware/model/transport-contract
calibration remains further work and is now deferred at the owner's request.
The subsequent OpenAI pilot provides separate evidence for that target.

The nested JSON-value transport is retained for compatibility. The installed local
model's failures are not a reason to guess values, decode invalid content, relax
schema/safety checks, increase timeouts or alter approved environmental outcomes.
Any simpler transport proposal should be separately reviewed before implementation.

### Warm-model recheck — November 19, 2026

At the owner's request, reran the unchanged `0.5` profile after explicitly checking
model residency. Ollama initially reported no loaded models. An empty-prompt preload
kept the installed model resident for ten minutes, generated zero tokens and returned
`done_reason=load`. The server then reported the model on the GPU with a 4,096-token
context; it remained resident between the two investigations.

Both attempts used the same synthetic snorkeling request, thirty-second model
deadline, thinking-enabled profile and validation rules:

| Attempt | Normalization duration | Outcome | Model/tool calls |
|---|---:|---|---|
| First confirmed-warm run | 30,002 ms | `MODEL_TIMEOUT`, terminal `ERROR` | 1 / 0 |
| Immediate repeat | 30,002 ms | `MODEL_TIMEOUT`, terminal `ERROR` | 1 / 0 |

Both local JSONL records independently validate as complete. They are retained in
the ignored `traces/ollama-warm-check/` directory. No application code, model settings,
execution limits or dependencies changed, and no OpenAI call was made. Warming the
model did not resolve the current profile's deadline failure. This recheck does not
establish which part of inference consumes the time or qualify the target for full
investigations.

## Automated checks

The shared three-role offline integration matrix now covers both targets for all
three activities and both dayparts. New tests cover local configuration/access,
the actual installed SDK payload shape, fixed loopback routing, missing OpenAI
credentials, no provider fallback, scalar/Unicode span projection, rate/error/
timeout/length/malformed/model/usage failures, trace tampering and budget exhaustion.
CLI tests check explicit matching flags and local execution without an env-file.
All routine tests use in-process HTTP doubles, not real model inference.

Focused local/agent checks: **48 passed, 13 upstream LangSmith deprecation warnings**.
Final verification on Python 3.14.8:

- `uv sync --locked`: succeeded with the unchanged 50-package resolution.
- `uv run --locked pytest`: **1,361 passed, 13 warnings in 54.03s**.
  All prior 1,335 tests still pass; the target increment adds 26 cases (20 local
  boundary checks and six additional target/activity/daypart combinations).
- All 24 Python files changed across the integration branch parse with Python
  3.12 syntax; this is not a separate Python 3.12 runtime test.
- Whitespace/document links and all seven retained local terminal traces validate.
- No API charge, model download, dependency/lockfile change, commit or push occurred.

```bash
uv sync --locked
uv run --locked pytest tests/test_ollama_target.py tests/test_agent_release.py
uv run --locked pytest
uv run --locked hafi run "Where should I snorkel tomorrow morning?" \
  --fixtures fixtures/saturday-release --config haf.ollama.example.toml \
  --local --max-investigations 1
```

The last command is a real local experiment and may fail as documented above.
Existing OpenAI instructions remain in the [README](../../README.md#model-driven-synthetic-release).
Full registered scenario acceptance remains BLOCKED; no mock or failed local run
is relabeled as a genuine agentic PASS.
