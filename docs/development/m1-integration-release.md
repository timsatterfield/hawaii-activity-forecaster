# M1 integration release

Implements the owner-approved [Saturday release scope](../implementation/m1-saturday-release-scope.md)
after M1.6-F. Approved requirements/architecture documents and the original fixture
packages remain unchanged. M1.6-D/F remain drafts; the approved supplement records
which simplifications and paid-pilot limits the owner accepted.

## Implementation

`agents/runtime.py` uses the existing strict Coordinator, Weather and Ocean proposal
contracts. Coordinator normalization feeds the existing raw-request verifier and
catalog selection. Planning offers scoped legal tasks; specialists choose configured
tool options. After canonical evidence/safety evaluation the Coordinator reviews
the assessments and can conclude only with an allowed reason. A conclusion does not
authorize eligibility: deterministic comparison, construction, result validation and
independent JSONL validation remain mandatory.

`agents/data.py` loads explicit release environments using the existing manifest,
source, behavior and synthetic-policy validators. `tools.json` is a small closed
allowlist, not the deferred generalized capability-profile format. A verified
investigation freezes its supported candidate batch. Each role can be delegated
once, and recovery must reference earlier matching work in that specialist's plan.
This prevents duplicate query labels/delegations from resetting recovery capacity.
Model context never includes scripts, expected assertions or policy premises.

`agents/execution.py` connects these planners to the existing LangGraph. Native
fan-out/join runs Weather/Ocean; no second scheduler, agent framework or retry engine
is added. One existing BudgetManager accounts for normalization, both roles,
Coordinator planning and synthetic tools. The existing dispatcher enforces scope,
observed retryability and unresolved-gap fallback conditions. Optional visibility
cannot substitute for mandatory official checks.

`agents/session.py` reuses SessionManager admissions/revisions and makes fresh
runtime/driver instances for follow-ups. `agents/cli.py` provides `hafi run` with
explicit dataset/configuration, `--live`, bounded process allowance and optional
post-terminal interaction. Clarification stops before environmental work; a complete
clarified request must start a new run. Process persistence, active clarification
resumption and generalized recovery across delegations remain deferred.

The provider adapter now has a real factory guarded by the explicit enabled
`openai` / `gpt-6-luna` / `m1-saturday-runtime-0.1` / `synthetic-release` tuple.
Credentials are read from `OPENAI_API_KEY` only after activation checks. Disabled
defaults and the old offline profile remain available. No key is stored in TOML,
model projections or traces. uv's explicit env-file loading avoids another dotenv
dependency. The local `keys/` directory is ignored.

Calls retain the reviewed 8,000-byte conservative input bound, 2,048-token output
cap, low reasoning effort, foreground Responses API, `store=False`, no hosted tools,
no previous-response state, no parser repair, no model fallback and zero SDK/HTTP
retries. `service_tier="default"` explicitly selects standard processing rather
than inheriting an account-level faster service. LangSmith transmission is disabled.
Provider/account behavior and actual model quality still need live verification.

The release uses a separate prompt profile/version; original prompt bytes and
trace hashes are preserved for old traces. The trace reader checks the selected
profile's template/schema hashes and actual offline/live execution mode. A fake
transport test of the production factory is still offline evidence, regardless of
the deliberately exercised `LIVE_PROVIDER` metadata shape.

## Integration fixes

- Carry the last admitted Coordinator cycle into graph state even when it concludes
  without more specialist work. State, budget and terminal trace counts must agree.
- Exclude unsupported activity/candidate combinations from intended environmental
  uses of shared regional findings. Unsupported candidates still receive their
  required `UNSUPPORTED` assessments. Worst-case validation across supported uses,
  missing attribution, geographic scope and timestamps is preserved.
- Join both specialist outcomes before terminating on model/plan execution failure.
  This records the successful sibling's contract outcome as well as the failure,
  allowing complete technical-error traces without manufacturing a source outage.
- Distinguish model capacity from actual Coordinator iteration exhaustion; do not
  emit a five-cycle exhaustion event when only a model allowance stopped work.

## Acceptance evidence and limits

Focused offline integration checks exercise the installed SDK/strict schemas through
in-process mock HTTP, the real graph/session/dispatch/validation stack and retained
local traces. Assertions are independent pytest expectations, not application input.

| Related acceptance behavior | Release checks | Scope |
|---|---|---|
| SC-001 favorable results | All three activities, morning/afternoon, multiple eligible candidates, all roles, budgets and complete traces | Offline request-to-result integration |
| SC-002 geographic/suitability tradeoff | Existing `test_results.py` qualitative comparison guards remain; no invented tradeoff weight | Component coverage; exact scenario preference criteria remain unimplemented |
| SC-003 one supported location | Hard South Maui restriction for SUP; A/E remain unsupported, B investigated/recommended; experience/soft preference preserved | Offline integration |
| SC-004 advisory | Official Beach A advisory excludes A; alternatives retain independent eligibility | Offline integration, plus original registered authored component checks |
| SC-005 dangerous SUP wind | Explicit attributed synthetic dangerous-wind premise excludes preferred B; D remains eligible | Offline integration; real numerical wind thresholds remain blocked |
| SC-006 permitted MIXED | Explicit visibility limitation and reviewed permission preserve eligibility/disclosure; favorable alternative precedes MIXED within the same required geography | Offline integration; no numeric scores |
| SC-007 stale reports | Delivery-boundary expired mandatory marine evidence cannot authorize recommendations | Offline boundary integration; not an exact replay of every local-report variant |
| SC-008 conflict | Explicit synthetic material conflict with actually retrieved support causes abstention | Offline integration; real-world conflict materiality remains blocked |
| SC-009 fallback success | Timeout, one retry and actual alternate surf/current findings produce eligible results | Offline integration |
| SC-010 exhausted recovery | One retry and failed per-gap fallbacks produce abstention and observed limit events | Offline integration, plus original registered authored component checks |
| SC-011 source injection | Instructions inserted at the source-delivery boundary cannot change model context, tool permissions or advisory exclusion | Offline boundary integration; no universal live-model robustness claim |
| SC-012 follow-up | New investigation/revision, same session, inherited request, fresh budgets/findings and unchanged prior trace | Offline integration |
| Technical failures | Normalization, planning and either specialist model failure; malformed out-of-scope source; static diagnostics, no hidden model retries, independently valid terminal trace | Offline failure integration |
| CLI/access | Explicit opt-in, missing credential sends nothing, validated rendering, clarification and interactive follow-up | Offline SDK/CLI tests |

These checks do not relabel full registered scenarios PASS. Existing SC-004/SC-010
`evaluate --component` remains authored, with separate overall BLOCKED results.
General capability-profile/wire v0.2 acceptance is deferred under the approved scope.
Original unit/contract/result/safety suites remain regression gates.

Existing unresolved requirements remain explicit: verified real-beach catalog and
live environmental providers, real numerical hazard thresholds, operational conflict
criteria and comparison tradeoff criteria. No new threshold or scoring rule is
invented. The synthetic release is not full real-world MVP acceptance.

## Validation and pilot

Focused release tests: **29 passed, 13 upstream LangSmith deprecation warnings**.
Initial integration verification on Python 3.14.8, before the subsequent local-target request:

- `uv sync --locked`: succeeded; 50 resolved packages, 48 installed packages checked.
- `uv run --locked hafi --version`: succeeded (`0.1.0`).
- `uv run --locked pytest`: **1,335 passed, 13 warnings in 48.86s**.
  The warnings are existing upstream LangSmith asyncio deprecations. The release
  adds 29 tests to the 1,306-test baseline; existing tests remain passing.
- Ten new agent/release-test Python files parse with Python 3.12 syntax. This is
  not a separate Python 3.12 runtime test.
- All 41 relative links across changed/new documentation resolve; fenced code
  blocks balance and `git diff --check` passes.
- Approved specifications, original fixture files, dependency/lockfile and CI
  configuration are unchanged. No live model call, commit or push occurred at that stage.

The owner authorized a pilot of **at most $1 total and ten investigations across all
commands**. At the initial handoff no paid request had been sent, because the
supplied `keys/apsi.env` path was absent. The owner later supplied the credential,
now stored at `keys/apsi.env`; the [completed OpenAI pilot](m1-openai-pilot.md) records actual results
and the current prompt profile. All ten authorized investigations have now been used.
The process allows one to ten investigations (default three); the shared per-
investigation limits remain 12 model/12 environmental calls, five cycles, two
specialists, one retry per original, one fallback per required gap and three results.
The cumulative pilot count/cost is manual; there is no persistent spend ledger.

On November 19, 2026, [official model pricing](https://developers.openai.com/api/docs/models/gpt-6-luna)
listed $0.10/M input tokens, $0.125/M cache writes and $0.50/M output tokens.
The conservative 2,500-microdollar reserve per dispatched call is retained even for
unknown usage: at most $0.03 per investigation and $0.30 for ten investigations at
the reviewed bounds. These are conservative estimates, not billed measurements.
Recheck pricing before a later pilot. `store=False` is not a zero-retention claim;
the pilot uses synthetic catalog/environment inputs and non-sensitive requests only.

```bash
uv sync --locked
uv run --locked hafi --version
uv run --locked pytest tests/test_agent_release.py tests/test_release_cli.py tests/test_release_profile.py
uv run --locked pytest
```

See the [development guide](../development-guide.md#model-driven-synthetic-release) for paid opt-in
commands. No approved requirements/architecture document, dependency/lockfile,
original fixture package or CI configuration was modified. No commit or push occurs.

The subsequent pilot completed the listed model-driven integration checks and
recorded actual counts/latency/usage plus calibration failures. Next: rehearse the
synthetic demo and review the remaining acceptance limitations with the owner.

## Subsequent local-target request

The owner then requested both local Ollama/Qwen and OpenAI as valid targets. See
the [addendum](../implementation/m1-local-model-target-addendum.md) and
[local-target validation notes](m1-local-model-targets.md) for the implemented
selection, shared adapter behavior and later regression results. Seven actual local
checks failed safely before environmental work; this does not qualify the installed
Qwen model for complete investigations. Local work was subsequently deferred; the
later [OpenAI pilot](m1-openai-pilot.md) completed after credentials were supplied.
