# M1.7-A — Registered-scenario agent execution adapter

Connects the registered SC-004/SC-010 scenarios to the model-driven
Coordinator/Weather/Ocean runtime. Before this batch, `evaluate` could run only
authored component plans, so full acceptance stayed BLOCKED with
`SCENARIO_ADAPTER_UNAVAILABLE`. It implements the approved
[harness design](../implementation/m1-scenario-harness-contract-design.md) §§2, 8–10
under the [Saturday release scope](../implementation/m1-saturday-release-scope.md).
That scope's "small explicit configurable tool allowlists" deferral covers the new
fixture files. Requirements, schemas, safety policies, expected assertion files,
behavior scripts, model profiles and execution limits are unchanged.

**Owner review requested** for the decisions marked ▲ below.

## What runs

```bash
uv run --locked --env-file keys/apsi.env hafi evaluate SC-004 \
  --fixtures fixtures/scenario-pack-v1 --agent --config haf.release.example.toml \
  --live --trace-directory traces/acceptance
```

`--agent` needs `--config` plus `--live` (OpenAI, paid) or `--local` (Ollama). The
opt-in checks are the ones `hafi run` already uses, now shared in
`agents.cli.configured_target`. The run then goes through the following steps:

1. Full v2 scenario preflight, exactly as before.
2. Allowlist preflight, before any model call (see below).
3. The existing `execute_scenario` session loop with a fresh `AgentRuntime` per
   request step, the scenario's `DriverInputs` and policy. No new graph path is added.
4. The existing verified capture, then evaluation of the snapshotted assertions.

The model sees only the existing runtime contracts: request text, verified
projections, canonical assessments, legal task descriptions and option IDs. It
never sees scripts, response fixtures, behaviors, operation IDs, expected files or
assertion IDs. `test_model_context_contains_no_scripts_outcomes_or_oracle_values`
checks this.

## ▲ Decision 1 — explicit per-scenario tool allowlists

`fixtures/scenario-pack-v1/agent_tools/SC-004.json` and `SC-010.json` use the
release `tools.json` option shape plus `harness_contract_version` and
`scenario_id`. They are explicit application inputs, outside the manifest, the
same way the release `tools.json` is. Their SHA-256 is reported as
`tool_allowlist_digest`. The v2 manifest, harness contract `1.0.0` and existing
artifact digests are unchanged.

Preflight (`load_scenario_tools`) rejects the allowlist before dispatch with
`FIXTURE_INVALID` if any of the following hold:

- An option falls outside the catalog or approved category/source mapping.
- An option ID is duplicated or a key is unknown.
- The allowlist names another scenario.
- An option is not answerable by exactly one scripted operation.
- A retry has no scripted second attempt.
- A recovery option is malformed: a recovery of a recovery, a retry that changes
  its query, or a fallback that doesn't address one original category through
  another source.

Options are never derived from scripts at runtime. Preflight only proves that
every declared option is answerable, so the model cannot reach an unscripted query.
At runtime, options are filtered to the delegated candidate scope: subsets are
allowed, widening never is. This lets SC-004 offer its scripted A/B and C/D batches.

**Limitation.** The two scripts were authored for the authored plans. SC-010
scripts a marine retry and two fallbacks, while SC-004 scripts no recovery. Its
answerable allowlist therefore offers no recovery options, and SC-010's does.
Recovery availability differs between the two, but neither allowlist reveals
success or failure. Making them uniform would mean adding operations to the
registered scripts, which is a fixture change and is deliberately not made here.

## ▲ Decision 2 — scenario PASS requires a verified genuine model target

Harness design §10 forbids reporting "scripted adapters, or a controlled decision
stub" as genuine model-driven behavior. The capture boundary therefore reads the
execution mode from the authoritative trace's `INVESTIGATION_STARTED`
configuration. It never takes the mode from the caller. The capture also requires
`component_probe` to agree with that mode and at least one model call for any model
profile. The scenario report then uses these diagnostic categories:

| Captures | Scenario outcome | Category |
|---|---|---|
| None (preflight only) | BLOCKED | `AGENT_EXECUTION_NOT_RUN` |
| `--component` authored plans | BLOCKED | `AUTHORED_COMPONENT_SCOPE` |
| Agent runtime over offline mock HTTP | BLOCKED | `OFFLINE_MODEL_TRANSPORT` |
| Agent runtime, `LIVE_PROVIDER` or `LOCAL_PROVIDER` | Assertion aggregate: PASS, FAIL or BLOCKED | `ASSERTIONS_EVALUATED` |
| Mixed modes, or a declared mode the traces contradict | FAIL | `CAPTURE_CONTEXT_MISMATCH` |

`SCENARIO_ADAPTER_UNAVAILABLE` is retired because the adapter now exists. A failed
active mandatory assertion still makes the scenario FAIL in every mode. Outcome
enums, assertion semantics and precedence are unchanged.

## Evidence in this batch (offline, no paid calls)

`tests/test_agent_scenarios.py` uses the existing offline SDK mock HTTP:

- **Offline agent runs.** SC-004 passes 84/84 component assertions and SC-010
  passes 61/61, each with five real gateway model calls and the scenario still
  `OFFLINE_MODEL_TRANSPORT` BLOCKED.
  - SC-004 trace: one candidate excluded, outcome `RECOMMENDATIONS`.
  - SC-010 trace: one retry, two fallbacks, outcome `NO_RECOMMENDATION`.
- **Non-vacuous evaluation.** Removing Beach A's water-check option makes SC-004
  FAIL (A029/A030/A082), even offline.
- **Preflight.** Nine invalid allowlist variants, plus a missing file and
  identifier escapes, are rejected with zero model calls and no trace.
- **Mode checks.** An authored capture declared as agent runtime is a mismatch,
  and so is the reverse.
- **CLI.** It refuses to construct a client without explicit opt-in, and offline
  JSON output exits `2`.
- **Reporting seam.** Relabeling an offline adapter as `LIVE_PROVIDER` or
  `LOCAL_PROVIDER` shows the evaluator can report PASS. This exercises reporting
  logic only. It is not acceptance evidence.

## Owner-run live evidence (2026-11-19, `gpt-6-luna`, profile `m1-saturday-runtime-0.2`)

| Attempt | Result | Trace |
|---|---|---|
| SC-004 #1 | Technical failure after 1 model call. The model's `normalize_request` reply passed the wire schema, but independent request validation rejected it (`REQUEST_NORMALIZATION_FAILED`). No tool ran. The run failed closed | `62c5ff71…`, outcome `ERROR` |
| SC-004 #2 | **Full scenario PASS**, 84/84, `execution_modes: [LIVE_PROVIDER]`. 5 model calls, 9 tool calls, 2 Coordinator cycles. A excluded (HM-WATER-001), B eligible and the only recommendation, C/D unresolved. The model skipped optional visibility, unlike the authored plan | `a2bf7e93…`, digest `999967c2…` |

| SC-004 #3 | **Full scenario PASS**, 84/84, `LIVE_PROVIDER`. 5 model calls, 11 tool calls (this time including optional visibility), 2 cycles. A excluded, B the only recommendation. Run after the owner raised the account's RPM limit | `b156c265…`, digest `b3d519a7…` |
| SC-010 #1 | **FAIL**, 22/61. Weather ran both tools. The Ocean model's plan passed the wire schema, but runtime plan validation rejected it (`AGENT_FAILED`, `SPECIALIST_CONTRACT_FAILED`). No ocean tool, retry or fallback ran, so the investigation ended `ERROR` instead of abstaining. All 39 failures follow from this. The harness correctly reported an application failure, not a pass or an abstention | `718d0c07…`, digest `8b4a94b8…` |
| SC-010 #2 | **Full scenario PASS**, 61/61, `execution_modes: [LIVE_PROVIDER]`. 5 model calls, 8 tool calls, 2 cycles. Marine primary failed, then one retry failed, then the HWT_SURF and SNORKEL_STORE fallbacks failed; visibility was unavailable. Limit reached, then `ABSTAINED` with `NO_RECOMMENDATION` for A–D | `a42a5ea6…`, digest `9021971f…` |

Both registered scenarios have now passed in full against a genuine live model.
These are observations, not a reliability rate: SC-004 passed 2 of 3 live
attempts and SC-010 passed 1 of 2. Neither failed trace shows a rate-limit or
provider error: in both, the model returned a schema-valid reply that deterministic
validation then rejected. Both failed attempts failed closed. Deterministic validation
rejected an unusable model interpretation (SC-004 #1) or Ocean plan (SC-010 #1)
instead of proceeding, and neither produced a recommendation.

## Remaining gaps

- **Live planning is intermittent.** SC-010 #1 failed at Ocean recovery planning
  and #2 passed with the same inputs, so this is model variance, not a fixed
  fixture fault. The rejected rule in #1 is unknown:
  `AGENT_FAILED` records no reason code, and payloads are deliberately not traced.
  Since [M1.7-B](m1-7b-agent-failure-reason-codes.md), `AGENT_FAILED` and rejected
  interpretations record a closed, sanitized `error_code`. One suspect is the allowlist name
  `WATER_ABCD`: the Ocean prompt describes `WATER_` options as "the named beach",
  while release fixtures use per-beach water options. SC-004's batch `WATER_CD`
  worked live, though.
- **Live request normalization is not reliable yet.** One of two SC-004 attempts
  failed at request interpretation. The cause is not recorded, because traces
  deliberately omit model payloads. Deciding whether to add a bounded diagnostic
  or adjust the prompt is a separate model-profile decision.
- **Ollama known limit (pre-existing).** On the experimental local profile, a
  preferred-area request such as "near Kihei" exceeds the 8000-byte
  `normalize_request` input bound before dispatch (`MODEL_HTTP_INPUT_INVALID`).
  This also affects `hafi run --local`. SC-004 `--local` therefore fails; SC-010
  `--local` works offline. A strict `xfail` records it. Changing the bound is a
  model-profile decision and is not part of this batch.
- **Multi-step scenarios.** The session loop already submits later steps (as
  SC-012 will need), but no registered multi-step scenario exists yet to exercise
  agent follow-ups through the harness.
- **Live model variance.** A real model may legitimately choose different
  delegations or skip optional work. Assertions check outcomes and invariants,
  not the authored call sequence. Variance therefore yields FAIL only when a
  required behavior is missing, and the report shows which assertion failed.
