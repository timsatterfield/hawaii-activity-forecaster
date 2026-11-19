# M1.6-A — Authoritative local JSONL tracing

Implements the local tracing increment authorized after
[M1.5-F](m1-5f-raw-request-session-graph-integration.md), using the approved
[observability requirements](../requirements/07-observability.md),
[trace schema](../requirements/03-data-schemas.md),
[configuration baseline §11](../implementation/m1-configuration-baseline.md),
[execution design §17](../implementation/m1-langgraph-execution-design.md), and
[trace acceptance cases](../requirements/06-test-acceptance.md).

Approved specifications, event enums, logical schemas, fixture artifacts,
dependencies and provider configuration are unchanged. No general conversational
CLI, new autonomous role, optional remote telemetry integration or scenario
acceptance runner is introduced.

## Files and interfaces

Created `src/hawaii_activity_forecaster/observability/` with:

- `storage.py`: exclusive per-investigation files and synchronous durable appends.
- `privacy.py`: a small structured projection excluding raw/private payloads.
- `validation.py`: strict reading, correlation/completeness checks and metrics.
- `__init__.py`: public writer, reader, inspection and validation APIs.

Updated graph emission, model/tool accounting events, session commits, result
validation metadata, presentation, synthetic demos and CLI. Added
`tests/trace_samples.py`, `test_trace_storage.py`, `test_trace_validation.py`,
`test_trace_graph.py` and `test_cli_traces.py`. One existing result test now checks
both the actual failed validation event and the subsequent validated ERROR result.
README describes setup, trace generation and inspection.

`run_synthetic_tool_graph()` and `run_raw_synthetic_tool_graph()` now require local
JSONL by default. Supply `trace_settings=TraceSettings(directory=...)` explicitly
or use the configured default. An explicitly supplied `record_event` callback
selects the existing component-test seam and produces no authoritative file.
Combining that callback with explicit local settings is rejected rather than
silently selecting one authority.

`SkeletonReport.trace_path` identifies the local artifact;
`trace_validation` retains its byte digest, event count, completeness and metrics.
The preterminal ResultValidationSnapshot records whether authoritative tracing
was required, preventing omission of the path/receipt from silently downgrading
presentation to the memory seam. These are runtime metadata, not new logical schemas.

## Physical format and lifecycle

Each file is `<configured-directory>/<investigation-id>.jsonl`. Every line is one
UTF-8 JSON TraceEvent followed by a newline. No extra header/footer record or event
type is added. The initial INVESTIGATION_STARTED event's `trace_metadata` details
carry schema/configuration/policy versions and the conditional model identifier.
The reader reconstructs InvestigationTrace using those details, the initial event
timestamp, and actual terminal events. Completion is never invented from EOF.

The current schema/configuration versions are `0.1`; applied synthetic safety
policy is `0.2`. A low-level probe without policy application records `not-applied`
instead of claiming policy execution. Effective approved limits/timeouts and the
synthetic policy configuration version are retained. No model is selected;
`model_identifier` remains None, including accounting-double tests.

Creation uses exclusive append mode and private file permissions. Existing files,
including symlink collisions, are never overwritten or resumed. The writer checks
identity, unique event IDs, contiguous append sequence and destination identity/size.
Short writes are completed; successful events are fsynced before returning. A
terminal append closes the writer. Follow-ups use new investigation/trace IDs and
files while preserving the session/revision/prior-investigation relationship.

Events are emitted at their actual operations, with responsible actors, explicit
specialist request/attempt identities, tool call IDs, finding/source/rule references,
assessment/policy references, validation outcomes and terminal counters. No expected
scenario assertions or retrospective event replay enter the application.
Source timestamps and virtual synthetic delivery timestamps remain distinct from
UTC occurrence times. Tool `duration_ms` measures local execution; the separate
`simulated_duration_ms`/`elapsed_ms` describe authored virtual source behavior.

## Failure, closure and publication

The destination is opened and checked before admission events or model/tool work.
Startup, append, fsync, deleted/replaced destination and close failures stop new
dispatch through the shared budget/exchange closure path. Public results and their
validation receipts are suppressed. Errors expose static operational categories,
never raw exception messages or sensitive filesystem paths.

After recording a terminal event, the graph independently rereads and validates
the file against state, result, budgets, bindings and validation decisions before
publishing. A validation failure is reported as TRACE_VALIDATION_FAILED, distinct
from TRACE_WRITE_FAILED. Session commit and presentation repeat the checks and
compare the exact retained byte digest. A missing, changed or invalid artifact
cannot authorize display.

A terminal row can remain physically visible after a final fsync/close failure.
Its presence alone does not authorize publication: the application has no successful
receipt and reports failure. Inspection with the actual failed runtime state rejects
the mismatch. Standalone inspection checks file contents, not the historical success
of a filesystem acknowledgment or the full scenario's acceptance.

Interrupted files are preserved without repair, truncation or fabricated terminal
events. Valid nonterminal prefixes inspect as `complete=False`; malformed JSON,
missing final newlines, duplicate keys, nonfinite JSON, bad references and sequence
gaps are invalid. Clarification closes the local execution with no terminal/result,
remaining AWAITING_CLARIFICATION. Cancellation still propagates and blocks session
reuse; no new cancellation/resumption semantics are introduced.

## Privacy and retention

Only reviewed structured fields are retained. Raw utterances, full conversations,
opaque hard/soft payloads, prompts, private reasoning, SDK exception messages,
headers and full provider/model responses are omitted. Normalization records
canonical activity/date/window/experience, preference presence, constraint counts
and recognized location scopes/entry indexes rather than free-form destination or
constraint values. Selection audit IDs/reasons and source references preserve the
catalog boundary. Origins retain indexes and assumption metadata without quotations.

Attribution URLs keep host/path while removing credentials, queries and fragments.
Known token/email patterns are redacted in permitted diagnostic strings. This is
not a general PII detector: producers must use controlled IDs and trusted validator
summaries rather than arbitrary untrusted prose. Runtime validation remains bound
to the complete owned inputs; the minimized file is not a replacement for input
fixtures or a replay database.

Files stay local. Default `traces/` is already gitignored; users choosing another
directory should keep generated traces out of source control. No automatic deletion
or fixed retention duration is selected while the approved retention decision is
open. Manually remove files no longer needed after investigations stop; retain
necessary synthetic evidence for capstone review. The application never cleans up
historical or partially written files itself.

## Verification and use

```bash
uv sync --locked
uv run --locked pytest
uv run --locked hafi demo advisory --fixtures fixtures/scenario-pack-v1 --trace-directory traces
uv run --locked hafi trace traces/<investigation-id>.jsonl
```

Substitute a generated filename. `hafi trace PATH` emits JSON with completeness and
duration, iterations, specialist/tool/model counts, recovery counts, distinct
finding outcomes, candidate counts and final outcome. Counts on partial files
describe observed records; they cannot prove dispatch completion beyond the prefix.
Evidence totals count distinct finding IDs using their worst recorded category
status; current candidate totals use the latest recorded assessment per beach.

Exit status is 0 for a structurally complete valid file, 1 for a valid partial file
or invalid/unreadable trace. Invalid files print only a static diagnostic code.
Runtime state/result/binding comparisons are additionally available through
`inspect_trace(path, state=..., result=..., budgets=..., bindings=..., evidence=...)`.
A standalone complete file is not an authorization to recommend or a scenario PASS.

CLI directory precedence is explicit `--trace-directory` over HAF_TRACE_DIRECTORY
over an explicit `--config PATH` TOML `[trace]` setting over defaults. TOML-relative
paths are anchored to the file's directory. Invalid configuration prevents work.

Tests cover TL-001..012 at the synthetic component boundary: successful and partial
tools, timeouts/retries/fallbacks, evidence/source correlations, policy exclusions,
terminal/result agreement, privacy, concurrent specialist completion order,
shared synthetic model accounting, partial writes, fsync/close faults, interruption,
tampering, session isolation, startup failure and CLI inspection/configuration.
Remote tracing remains suppressed even with ambient SDK tracing variables; optional
LangSmith availability is not required for local tracing.

Final verification: **1,174 tests passed in 25.39s** on Python 3.14.8, including
**89 new tests** over the 1,085-test baseline. The same 13 upstream LangSmith
deprecation warnings remain. `uv sync --locked`, package import, installed CLI
version, module startup, installed session-demo execution and inspection of both
generated traces passed. Python 3.12 syntax checks passed for all 18 changed/new
Python files (not a separate 3.12 runtime test). All 29 relative documentation links,
fenced code blocks and `git diff --check` passed. Approved specifications, fixture
artifacts, pyproject.toml and uv.lock remain unchanged.

## Remaining gates

No new specification conflict was found. Older observability text leaving budgets
and fail-open/fail-closed behavior unresolved is superseded by the approved
configuration baseline. Exact retention duration remains an open design decision.
General conversational execution, provider/model activation, real Coordinator
planning and full independent scenario acceptance remain deferred. Existing scenario
readiness is unchanged; local trace completeness alone does not establish M1 PASS.

Recommended next increment: **M1.6-B — independent scenario assertion evaluation and
reporting**, retaining explicit BLOCKED/NOT_RUN outcomes until execution prerequisites
are met. No evaluator or provider integration is implemented in this increment.
