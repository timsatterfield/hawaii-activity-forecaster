# Hawaii Activity Planner — Historical live acceptance deferments

**Status: superseded; both temporary deferments were resolved in M1.13.**
The current executable selection in `scripts/run_live_acceptance.py` contains
**twelve scenarios and zero deferred**, on evaluation profile
`m1-saturday-runtime-0.8` with `gpt-6-luna`. The completed M1 implementation is
frozen for submission. The ten-scenario gate described in the historical record
below is no longer the current selection.

See the [submission summary](../submission-summary.md) and
[profile 0.8 evaluation results](m1-completion-report.md#profile-08-reliability-sample-2026-11-20)
for the final four-round 47/48 scenario result and its limitations. Re-enabling
these scenarios did not resolve intentionally blocked optional assertions or
other deferred capabilities.

## Historical profile 0.7 deferment

**Owner authorization:** 2026-11-20, temporarily defer the failing live checks to
continue development. This temporarily changed the selected live rerun gate, preserving the
registered scenarios, mandatory assertions, safety validators and offline pytest
coverage. Approved requirements and architecture documents are unchanged.

| Scenario | Historical temporary disposition | Follow-up needed at that stage |
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

## Fixes and completed live verification (M1.13)

Both causes were diagnosed and fixed offline. At that stage they remained in
`DEFERRED` until reviewed live passes were available; that verification and
re-enablement are recorded below.

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

## Current selected live rerun

From the repository root, preview the selection without model calls or output files:

```bash
uv run --locked python scripts/run_live_acceptance.py
```

The preview selects SC-001 through SC-012: **twelve selected, zero deferred**.
This replaces the historical ten-selected/two-deferred procedure.
After separate live authorization, run each selected scenario once:

```bash
uv run --locked --env-file keys/apsi.env python scripts/run_live_acceptance.py --live
```

This makes paid calls. A typical run uses 65 model calls across thirteen
investigations because SC-012 has two steps. Existing per-investigation limits
remain enforced; actual call counts can vary. There are no automatic reruns.

The runner creates a new ignored directory under `traces/`, saves reports and
diagnostics, and records the selected outcomes in `batch-status.json`. The
runner would record any future deferred cases as NOT_RUN; currently there are none.
It returns failure for any selected scenario whose exit code or report is not a
PASS. Optional FAIL/BLOCKED assertion counts remain visible in each report.
A successful full selection is **12/12 scenario-level PASS**. That still does
not imply all optional assertions passed, nor does it establish production reliability.

The retained `--include-deferred` switch does not change the current selection
because `DEFERRED` is empty. Any new live run still requires separate authorization.
Direct `hafi evaluate` commands remain available for investigation. Authored and
offline scripted-transport runs can pass component assertions while full scenario
acceptance remains BLOCKED; they must not be labeled genuine-model live passes.

## Historical re-enable procedure — completed

The original procedure required independent offline coverage and reviewed live
evidence before removing each entry from `DEFERRED`. Both entries have been removed
and all twelve scenarios are selected. This historical procedure does not authorize
new feature work or changes to intentionally blocked assertions. The existing
GitHub pytest gate continues to run the full offline suite.

## Intentionally blocked assertions and deferred capabilities

Optional blocked rows still cover production wind-hazard classification (SC-005),
clear-water preference interpretation (SC-006), production freshness cutoffs
(SC-007), automatic conflict-materiality classification (SC-008), and historical
evidence reuse (SC-012). They are distinct from the resolved temporary scenario
exclusions. SC-007 also has optional failures when its redundant source is skipped.

Verified real-beach catalog completion, live environmental providers, production
hazard/freshness/materiality rules and active clarification resumption remain
outside the submitted synthetic M1 scope. The [completion report](m1-completion-report.md)
preserves those boundaries and the original failure provenance.
