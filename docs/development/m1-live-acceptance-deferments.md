# Temporary live acceptance deferments (resolved in M1.13)

**Owner authorization:** 2026-11-20, temporarily defer the failing live checks to
continue development. This changes the selected live rerun gate, preserving the
registered scenarios, mandatory assertions, safety validators and offline pytest
coverage. Approved requirements and architecture documents are unchanged.

| Scenario | Temporary disposition | Follow-up needed |
|---|---|---|
| SC-006 | NOT_RUN in the default live rerun | Add reviewed, versioned normalization guidance for retaining unsupported soft preferences; verify with offline cases and an authorized live check |
| SC-008 | NOT_RUN in the default live rerun | Diagnose the profile 0.7 assertion failures, correct the cause and verify with an authorized live check |

The earlier profile 0.7 batch at local
`traces/acceptance-0.7-closeout-1795206283375/batch-status.json` recorded **10/12
scenario-level PASS**, with SC-006 and SC-008 FAIL. Historical reports and traces
are retained. In the owner's separate `traces/acceptance/m111b-SC-006.json`, the
failure was `APPLICATION_FAILURE`: request normalization rejected a missing
`soft_preferences` change (`REQUEST_CHANGE_OMITTED`) before environmental work.
The phrase "prefer clear water" must be retained as UNINTERPRETED or covered by
an unresolved phrase span. This is independent of MIXED safety evaluation.

## Fixes applied, pending live verification (M1.13)

Both causes are now diagnosed and fixed offline. The scenarios stay in `DEFERRED`
until each has a reviewed live pass.

| Scenario | Diagnosed cause (profile 0.7 batch) | Fix |
|---|---|---|
| SC-006 | Request interpretation rejected with `REQUEST_CHANGE_OMITTED`, field `soft_preferences`. The model dropped the unapproved "prefer clear water" preference | **Profile `m1-saturday-runtime-0.8`**, template `normalize_request-release-0.5`. Adds guidance to never drop a preference clause: any unapproved `prefer …` clause is returned as `UNINTERPRETED` with its exact phrase. Other prompts and limits are identical to 0.7 |
| SC-008 | The model called **neither** `REGIONAL_SURF_ABCD` nor `LOCAL_CURRENTS_A`, so surf and currents went uncovered: A was INSUFFICIENT and no conflict formed. Both names contain `SURF_`/`CURRENTS_`, which the 0.5+ Ocean prompt reserves for fallbacks ("never run … as ALWAYS"). The M1.11 rename introduced this | Renamed to **`REGIONAL_WAVES_ABCD`** and **`LOCAL_CURRENT_REPORT_A`**. A new guard test checks every allowlist, including the release `tools.json`: a name containing a reserved token (`RETRY_`, `SURF_`, `CURRENTS_`, `MARINE_`) must actually have that role. The test fails on the old SC-008 names |

**Live verification (profile 0.8) and re-enablement.**

| Scenario | Result | Trace |
|---|---|---|
| SC-006 | **PASS** 62/62 mandatory, 1 optional BLOCKED. `normalize_request-release-0.5`; A MIXED with disclosure, B FAVORABLE. 5 model calls, 8 tool calls | `5bd29260…` (`0e6facea…`) |
| SC-008 | **PASS** 45/45 mandatory, 1 optional BLOCKED. Called NWS_MARINE and SNORKEL_STORE; `EVIDENCE_CONFLICT_DETECTED`; both findings LIMITED; abstained. 5 model calls, 9 tool calls | `32a1052a…` (`8b748ad0…`) |

Both are removed from `DEFERRED`, so the selected live gate is again all twelve
scenarios. Offline suite: 1530 passed, 1 xfailed. A full twelve-scenario live run
on 0.8 then passed **12/12**, with 13/13 operational successes, 65 model calls and no
technical failures (`traces/acceptance-subset-1bf7ac46-…`).

## Selected live rerun

From the repository root, preview the selection without model calls or output files:

```bash
uv run --locked python scripts/run_live_acceptance.py
```

The preview selects SC-001–005, SC-007 and SC-009–012: **ten selected, two deferred**.
After separate live authorization, run each selected scenario once:

```bash
uv run --locked --env-file keys/apsi.env python scripts/run_live_acceptance.py --live
```

This makes paid calls. A typical run uses 55 model calls across eleven
investigations because SC-012 has two steps. Existing per-investigation limits
remain enforced; actual call counts can vary. There are no automatic reruns.

The runner creates a new ignored directory under `traces/`, saves reports and
diagnostics, and records the deferred scenarios as NOT_RUN in `batch-status.json`.
It returns failure for any selected scenario whose exit code or report is not a
PASS. Optional FAIL/BLOCKED assertion counts remain visible in each report.
A successful selected gate is **10/10 selected**, never 12/12 acceptance.

To preview all twelve for future verification, append `--include-deferred`.
Combining that switch with `--live` explicitly includes both deferred scenarios;
it requires authorization for the expanded live batch. Direct `hafi evaluate`
commands also remain available for investigation.

## Re-enable

After each fix has independent offline coverage and reviewed live evidence,
remove its entry from `DEFERRED` in the runner and update this record. Until then,
report the unresolved regressions alongside the selected gate. The existing
GitHub pytest gate continues to run the full offline suite.
