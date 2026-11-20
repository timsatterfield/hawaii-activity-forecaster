# Temporary live acceptance deferments

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
