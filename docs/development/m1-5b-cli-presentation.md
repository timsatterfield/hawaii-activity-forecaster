# M1.5-B — CLI presentation of validated results

This increment implements plain-text presentation against requirements 03
§§6.5–6.8 / RR-010..019, requirements 06 §11, requirements 07 §10, and the
trusted `present_result` responsibility in the execution design. It preserves
the three-agent architecture and approved logical schemas. Approved requirements,
implementation specifications, fixture data, configuration and dependencies are
unchanged.

## Commands and outcomes

```bash
uv sync --locked
uv run --locked hafi
uv run --locked hafi --version
uv run --locked hafi demo advisory --fixtures fixtures/scenario-pack-v1
uv run --locked hafi demo outage --fixtures fixtures/scenario-pack-v1
uv run --locked python -m hawaii_activity_forecaster demo advisory --fixtures fixtures/scenario-pack-v1
uv run --locked pytest
```

No arguments still display application information. Help/version remain supported.
`demo` requires a named fixed example and an explicit directory; installed wheels
do not include repository fixtures. An absolute path also works outside the repo.
Natural-language requests, arbitrary result-file input and session follow-ups are
not exposed by this command.

| Command result | Exit code | Output |
|---|---|---|
| Validated recommendations | 0 | stdout |
| Validated NO_RECOMMENDATION | 0 | stdout with explanation and unresolved questions |
| Validated ERROR or unavailable/invalid committed result | 1 | sanitized stderr |
| Invalid arguments, fixture preflight failure, BLOCKED/DISABLED definition | 2 | stderr; no graph execution |

Every displayed result retains the mandatory fictional-output warning and a
component-demo label. `advisory` uses explicit SC-004 component plans and displays
only fictional Beach B after six calls. `outage` uses explicit SC-010 recovery
plans, consumes eight calls (one retry, two fallbacks), and explains insufficient
evidence. Neither makes a real-world environmental recommendation.

The dedicated `demo` module is an outer component harness. It loads validated
artifacts, checks definition status, and passes only application and trusted-driver
projections to the graph. Candidate selection, normalization and call plans are
fixed authored examples. They are not inferred from scripts, source payloads or
expected assertions. No independent evaluator projection enters execution or
rendering. Definition status and full scenario execution readiness remain distinct:
ACTIVE definitions permit these component demos, while full acceptance stays
BLOCKED. Definitions explicitly marked BLOCKED or DISABLED never execute.

## Read-only presentation boundary

`presentation.render_report(report, catalog=..., policy=...)` returns a complete
string. It performs no input/output, source/model dispatch, budget changes, event
recording or session mutation. It never repairs an invalid result or invents a
fallback recommendation. The CLI buffers the whole string before writing it, so
validation/rendering failures cannot leak partial recommendations.

`SkeletonReport.result_validation` now retains a detached active-state snapshot,
trusted stopping/error context and request step. It is optional internal runtime
metadata, not a persisted logical schema or a new resumable investigation. It is
published alongside `report.result` only after result validation and terminal-event
recording succeed. Existing component modes retain `None` for both fields.
Failure handling synchronizes actual tool/retry/fallback counters before constructing
its error result and retaining the corresponding validation basis.

Before display, the renderer copies and validates the result/state, verifies
matching terminal identity/outcome and closed budgets with no outstanding work,
and compares terminal fields with the retained preterminal basis. It reruns the
existing contextual Result Validator, including evidence/safety recomputation for
recommendations or abstention, against the retained active basis. This does not
reopen the terminal investigation. ERROR results use the existing sanitized trusted
error validator and require no environmental claims. Missing context, stale fields,
mutated nested lists or failed recording suppress output. A report supplied by
arbitrary untrusted code is not a cryptographic proof of persisted trace events;
this remains an in-process trusted component API.

## Display choices

- Activity, requested and recommended windows use Hawaii Standard Time with an
  explicit UTC-10:00 offset; fixed fixture times are never refreshed to today.
- Recommendations show verified names, qualitative suitability/evidence quality,
  controlled reasons and summaries, required MIXED disclosures, preferences and
  limitations. Bullets preserve the constructor's order without inventing ranks.
- Environmental details come from referenced ACCEPTED findings. Provider names,
  reported coverage/type, validity, issue/observation/retrieval/measurement times,
  values, units, measurement conventions/notes and original links are preserved.
  Surf and swell remain separate; no numeric conversion or safety threshold is added.
- Referenced advisories retain issuer/type, area, effective interval, reported
  severity when supplied, and link. Catalog references retain publisher/title,
  access date, verification date and URL. No live lookup is performed.
- Friendly labels explain known evidence categories/reasons. Abstention lists
  affected location names, unresolved questions, limitations and existing next steps.
  A handled provider outage remains distinct from an application failure.
- Internal result/assessment/policy IDs are not added as display fields. Original
  coverage descriptions or fixture URLs may themselves contain fixture identifiers.
  Source prose is flattened and terminal control characters are suppressed.
- Arbitrary exceptions, raw diagnostics, credentials and stack traces do not enter
  technical-error output. No advice or environmental claims are generated by the CLI.

Detailed source-display formatting and total ranking remain open in the approved
specifications; these are conservative local presentation choices recorded here.

## Verification and remaining scope

The tests exercise installed console/module entry points outside the repository,
recommendations/abstention/technical-error separation, source attribution and original
measurement semantics, ties/cap/MIXED disclosures, read-only rendering, rejected or
mutated results, retained-context/terminal mismatches, trace-write failure suppression,
preflight gates and invalid usage. Existing component tests remain unchanged apart
from the startup test expecting argparse's subcommand-aware rejection wording.

Final validation: `uv sync --locked` succeeded; **849 tests passed in 7.52s**
on Python 3.14, including 49 new presentation/demo checks. The 13 existing upstream
LangSmith deprecation warnings remain. Console/module startup and both demo commands
succeeded; `git diff --check` passed. No dependency or lockfile changes were needed.

Memory event recording remains a test seam. Authoritative local JSONL, independent
scenario assertion execution, natural-language normalization/catalog selection,
session admission and post-terminal follow-ups remain separate work. This increment
does not satisfy the complete M1.5 milestone or unblock SC-004/SC-010 acceptance.
Provider/model activation, opaque constraint/preference interpretation, real-beach
verification, real-world freshness and numeric hazard thresholds remain open.

Next proposed increment: M1.5-C — session lifecycle and post-terminal follow-up
handling, with request interpretation boundaries reviewed before implementation.
