# M1 reliability baseline reporting

Implements the owner-approved read-only reporting batch on `m1-reliability-baseline`.
It follows [observability §§12 and 15.5](../requirements/07-observability.md) and
[technical plan §10](../implementation/m1-technical-plan.md#10-observability-architecture).
No agent, graph, prompt, policy, source integration or dependency changes are made.

## Commands

```bash
uv run --locked hafi reliability traces/acceptance --format markdown
uv run --locked hafi reliability traces/acceptance --reports traces/acceptance --format json
```

Pass one or more JSONL files or directories; directories are searched recursively.
Give `--reports` **once**, followed by every report path; repeating the flag keeps
only the last value, which silently drops earlier batches' reports.
`--reports` optionally takes saved scenario JSON files or directories. It reads
existing evidence only: no fixture evaluation, provider client, model server,
credential or network access is needed. Input files are never repaired or modified.

Output goes to stdout, so it can be redirected into an ignored local directory:

```bash
mkdir -p traces/reliability
uv run --locked hafi reliability traces/acceptance --reports traces/acceptance \
  --format markdown > traces/reliability/acceptance.md
```

A fresh clone has no historical traces. Generate authored demo evidence first:

```bash
uv run --locked hafi demo advisory --fixtures fixtures/scenario-pack-v1 \
  --trace-directory traces/reliability-demo
uv run --locked hafi reliability traces/reliability-demo
```

This sample reports AUTHORED_COMPONENT and zero model calls. It is not a live
reliability sample. Use narrow input directories to avoid mixing unrelated test
artifacts into a development baseline. Keep generated reports local unless reviewed
for sharing; JSON includes supplied input paths and investigation/session identities.

## Counting rules

- **Profiles and modes:** separate groups for each `(profile_id, execution_mode)`.
  Authored, OFFLINE_TRANSPORT, LIVE_PROVIDER and LOCAL_PROVIDER inputs are not pooled.
  Older controlled accounting doubles without a model profile are labeled
  SYNTHETIC_ADAPTER and remain separate from authored and SDK mock execution.
  Modes are taken from independently validated metadata. Reporting cannot prove
  network provenance: an offline test can deliberately relabel a trace. Live
  execution claims still depend on reviewed run provenance.
- **Operational outcomes:** COMPLETED/recommendations and ABSTAINED/no recommendation
  count as operational successes. FAILED/ERROR counts as failure. The rate shows
  its numerator and terminal-investigation denominator explicitly.
- **Nonterminal evidence:** clarification is AWAITING_CLARIFICATION, not technical
  failure. Other valid prefixes are INCOMPLETE. Both are excluded from terminal
  success rates and terminal latency statistics; observed call counts remain visible.
- **Latency and usage:** count, total, minimum, median and maximum; duration is in
  milliseconds. Terminal duration excludes nonterminal prefixes. Model/tool call
  statistics include all valid observed investigations. No price estimate or billed
  cost is inferred, and no quantitative performance threshold is invented.
- **Failures:** closed codes from failed model operations, rejected normalization
  and failed specialist execution are grouped by stage/code. Event counts can
  include multiple layers of one cause; each row also reports distinct affected
  investigations. Unknown technical causes use UNCLASSIFIED. Handled source outages
  remain recovery/abstention behavior, not automatic technical failures.
- **Duplicates:** byte-identical copies count once. Different valid contents for
  one investigation ID are conflicting evidence; all versions are excluded and the
  conflict is reported. Distinct failed attempts remain distinct observations.
- **Invalid inputs:** unreadable, invalid or changed-during-read traces are excluded
  from metrics and reported as issues. Raw payloads and exception text are not echoed.
  Empty trace input is an issue, not a successful zero-run baseline.

## Saved scenario reports

Saved outcomes are imported using the existing `ExecutionEvaluation` type. Every
trace digest must bind to a validated supplied trace, with matching execution mode,
session and request-step revision. Counts must agree with the saved assertion rows.
Reports lacking their traces, conflicting reports and ambiguous trace bindings are
reported as issues and excluded from scenario totals. Equivalent duplicate reports
count once. `batch-status.json` is selection metadata and is not imported as an
execution report; deferred cases without traces never become observed runs.

Scenario results are grouped separately by scenario, profile and mode. A two-step
SC-012 attempt is one scenario report and two investigations. Optional FAIL/BLOCKED
assertions remain visible. Importing a saved report does not re-evaluate assertions,
certify its oracle or change its recorded outcome. It does not make authored/mock
success a full live acceptance PASS. No expected fixture files are consulted.

Consequently an operationally valid abstention can coexist with a saved scenario
FAIL when the required acceptance behavior was not exercised. This distinction
matters for the profile 0.7 SC-008 regression.

## Exit status and diagnostics

The reporting command exits **0** when its supplied evidence can be summarized,
even if it contains valid technical failures or recorded scenario FAIL outcomes.
It exits **1** if input validation/binding issues exist, while still printing the
valid subset and issue codes. It is a reporting command, not an acceptance gate.
The existing live runner and GitHub pytest gate retain their exit semantics.

Markdown contains compact aggregate tables and issue counts. JSON additionally
contains per-investigation safe metadata, observed metrics, digests and input issue
locations. Neither output copies request text, model replies, source text, arbitrary
assertion reasons, credentials or provider exception messages.

## Baseline evidence and limitations

The prior owner-authorized profile 0.7 batch can be summarized locally with:

```bash
uv run --locked hafi reliability traces/acceptance-0.7-closeout-1795206283375 \
  --reports traces/acceptance-0.7-closeout-1795206283375
```

It contains thirteen terminal investigations across twelve scenarios. Operational
results are ten COMPLETED, two ABSTAINED and one FAILED: **12/13 operational
successes**, distinct from **10/12 saved scenario passes**. Usage totals are
61 model calls and 96 tool calls; median terminal duration is 9,767 ms.
SC-006 records REQUEST_CHANGE_OMITTED at request validation; SC-008 has a saved
scenario FAIL despite operational abstention. SC-007 retains six optional failures.
These are selected historical development observations, not a representative
reliability estimate or a newly executed model benchmark.

A broader local snapshot combined `traces/acceptance/`, that profile 0.7 batch,
and the earlier clarification-check directory. It validated **70 investigations**
with no input issues. Its trace-declared LIVE_PROVIDER groups were:

| Profile | Investigations | Completed | Abstained | Failed | Awaiting clarification |
|---|---|---|---|---|---|
| 0.2 | 5 | 2 | 1 | 2 | 0 |
| 0.3 | 7 | 4 | 0 | 3 | 0 |
| 0.4 | 7 | 5 | 1 | 1 | 0 |
| 0.5 | 3 | 0 | 1 | 2 | 0 |
| 0.6 | 17 | 12 | 3 | 2 | 0 |
| 0.7 | 31 | 23 | 4 | 3 | 1 |

These groups cover different development attempts, fixture versions and requests;
they are not controlled comparisons of model/profile quality. Additional local
traces outside the supplied directories are not included. Generated Markdown and
JSON are local ignored artifacts under `traces/reliability-baseline/`, including
`profile-0.7-batch.md` and `all-recorded-inputs.md`.

The [two live deferments](m1-live-acceptance-deferments.md) remain unchanged. Reporting
does not hide their earlier failures, re-enable them, or count NOT_RUN as PASS.
Raw request wording is not retained for reporting. Controlled variation of wording
and new repeated live trials remain separate evaluation work, requiring appropriate
authorization. No paid calls are part of this batch.

## Verification

`tests/test_reliability.py` uses synthetic authored traces and explicit SDK mock
HTTP. It covers outcome denominators, profiles/modes, valid clarification and
partial traces, duplicate/conflicting copies, privacy on invalid inputs, digest-bound
reports, operational success alongside acceptance failure, optional assertions,
multi-step counting, and CLI behavior with provider construction forbidden.

Validation (2026-11-20):

- `uv sync --locked` in a fresh isolated source checkout on **Python 3.12.14**:
  succeeded, 50 resolved packages / 48 installed, unchanged lockfile. Local credentials,
  prior traces, presenter notes and the existing developer virtualenv were excluded.
- Final full regression: **1516 passed, 1 xfailed in 84.24s**. The existing expected
  failure is the deferred experimental Ollama preferred-area input bound.
- New focused reporting suite on the developer Python 3.14 environment:
  **17 passed**, 13 upstream LangSmith deprecation warnings, 7.22s.
- Installed `hafi reliability` generated the current batch's Markdown without
  inference. Historical trace/report aggregation validated 70 investigations with
  no input issues. Invalid-input behavior was verified separately with synthetic data.
- Documentation links, command syntax and `git diff --check` pass. Existing
  specifications, live gate selection, prompts, safety policies, fixtures,
  dependencies and CI are unchanged. No paid call, commit or push was made.
