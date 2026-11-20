# M1.6-E — Provider gateway and structured model contracts

Implements the offline foundation described by the
[M1.6-D proposal](../implementation/m1-model-provider-and-agent-runtime-design.md),
under the approved [configuration baseline](../implementation/m1-configuration-baseline.md),
[execution design](../implementation/m1-langgraph-execution-design.md),
[schema mapping](../implementation/m1-schema-contract-mapping.md) and
[request interpretation design](../implementation/m1-request-interpretation-and-candidate-selection-design.md).
The owner authorized this code increment after reviewing the provider options and
retained the OpenAI recommendation. This is not billing authorization, approval of
every draft decision or activation of paid execution. The M1.6-D draft and all
approved specifications remain unchanged.

## Changes and boundaries

New application files under `src/hawaii_activity_forecaster/`:

- `model_runtime/contracts.py`: internal closed output models and narrow input
  projections; strict JSON decoding and proposal-membership checks.
- `model_runtime/prompts.py`: four versioned operation templates, detached input
  snapshots, schema/template hashes and fixed offline profile bounds.
- `model_runtime/provider.py`: LangChain-compatible OpenAI Responses adapter,
  exercised only through an explicitly supplied `httpx.MockTransport`.
- `model_runtime/gateway.py`: one investigation's shared model reservation,
  dispatch, deadline, failure and trace boundaries.
- `model_runtime/errors.py` and package initializer: closed diagnostics and an
  import boundary that does not construct a client.
- `observability/model_validation.py`: independent provider-profile/call-lifecycle
  checks used by the existing JSONL reader.

Configuration adds an optional `profile_id` and `HAF_LLM_PROFILE_ID`. A named
profile requires its explicit provider/model tuple. Defaults still leave all three
unset and execution disabled; even a complete `enabled=True` configuration remains
rejected. No provider key is read. The adapter's offline credential is a fixed
noncredential, with an explicit `.invalid` base URL and disabled environment proxy
handling. Mock callbacks are trusted test code, not a sandbox against arbitrary
Python deliberately making its own network calls.

`pyproject.toml` and `uv.lock` add direct dependencies used by the adapter:
`langchain-openai`, `openai`, `httpx` and `langsmith`. LangSmith's explicit disabled
tracing context prevents SDK calls from inheriting remote tracing environment
settings. The lock resolves compatible LangChain core/protocol updates; no framework
major upgrade or CI change is introduced. README documents the new checks and
corrects its obsolete future-JSONL statement.

New tests are `test_model_runtime_contracts.py`, `test_model_gateway.py` and
`test_model_trace_validation.py`, with authored samples in `model_runtime_samples.py`.
Existing tests, fixtures, logical schemas, graph, safety evaluator, session manager
and scenario harness are unchanged.

## Structured proposal boundary

The four operations remain `normalize_request`, `coordinator_plan`,
`weather_investigation`, `ocean_investigation`. The first two are Coordinator work;
this does not add an agent role.

Wire schemas close every object, require every field, bound arrays and represent
nullable fields explicitly. Normalization uses the proposed JSON-value string
bridge, rejects duplicate/nonfinite JSON and unauthorized/duplicate change fields,
and converts to the existing `InterpretationProposal`. A smoke integration replays
that proposal through `validate_request` and `verify_request`; a schema-conforming
false interpretation still fails those independent checks.

Coordinator proposals can select only exact supplied legal delegations, permitted
evidence references and supplied stop reasons. Proposed work must fit the projected
remaining cycle/model/tool capacity, counting the current planning call. Specialist
inputs retain the existing scoped specialist request, including time window,
requirements, identity, attempt and deadline; revision and gap membership are
rechecked. Specialist proposals can select only supplied option IDs and gap IDs; recovery references must
be backward, and a retry cannot retry a retry or duplicate the original's allowance.
The shared dispatch ledger remains the authority for actual concurrent capacity.

These are membership/transport checks, not a replacement for semantic authorization.
The future trusted runtime must build projections from verified request receipts
and canonical state, independently check stop sufficiency, bind gap identities,
construct specialist requests/tool actions, enforce source/time/geographic scope,
and guard conditional recovery against actual observations. No option registry or
synthetic capability-profile artifact is invented in this increment. No findings,
measurements, eligibility, safety decisions or final recommendations are model output.
User/source strings stay in JSON data, never in the versioned system template.

## Gateway and HTTP behavior

`ModelGateway` requires an owned `InvocationIdentity`, the existing `BudgetManager`,
an explicit offline adapter, a trusted event emitter and a current-revision predicate.
The production owner must supply the required durable trace emitter. Explicit
component emitters remain test seams, as with the existing graph APIs. The gateway
is not connected to the graph, session manager, CLI or scenario executor yet.

All four operations share the same supplied model ledger. Authorization is recorded
before dispatch. The HTTP boundary checks the exact endpoint/profile, admits the
dispatch once, then invokes the mock transport. SDK/adapter retries are zero;
there is no parser repair, model failover or hidden writer/judge call. `store=False`,
foreground nonstreaming Responses, low effort and the 2,048-output-token cap are
explicit. Hosted tools and provider conversation state are absent. The installed
adapter's actual HTTP shape is tested, rather than inferred from callback counts.
[LangChain adapter documentation](https://docs.langchain.com/oss/python/integrations/chat/openai),
[official SDK retry/timeout documentation](https://github.com/openai/openai-python).

The approved thirty-second timeout applies around the awaited operation and in the
SDK. An elapsed-deadline check rejects a late return even if cancellation were
suppressed. Revision changes, closed investigations and dispatched cancellations
cannot return an accepted proposal. Dispatched failures remain charged and close
further execution; budget exhaustion itself preserves the existing caller-owned
finalization path. No retry or source-outage abstention is fabricated from a model
fault.

An authorization write failure sends nothing and releases/cancels the reservation.
Once the dispatch boundary is entered, a dispatch-event write failure retains a
conservative charge even if the mock HTTP handler was not reached; the sink is
unusable, execution closes, and the partial trace cannot authorize publication.
Authorization is never counted as proof that an HTTP request reached a provider.

Input admission uses a conservative serialized-byte bound, including schema,
instructions, context and framing, and rechecks the actual HTTP body. It downloads
no tokenizer and makes no hidden token-count request. Oversize input fails without
truncation. This is an offline safeguard, not a measured guarantee of the model's
tokenizer. Accurate live token/usage behavior and pricing still require verification
before activation. Each dispatched call retains a proposed 2,500-microdollar reserve;
twelve such reserves equal $0.03. These are estimates, not billed amounts. The
proposed $5 cumulative pilot ledger is not implemented or authorized; no live
factory exists that could bypass that unfinished gate.

## Trace detail migration

Logical event enums and schemas remain unchanged. Existing synthetic callback
records retain `contract=synthetic_model_dispatch` and their original semantics.
Provider records use `contract=model_dispatch`, `synthetic_adapter=False` and an
explicit `execution_mode=OFFLINE_TRANSPORT`. The reader also understands the future
`LIVE_PROVIDER` metadata shape; reading that shape does not establish provider
access or genuine agentic execution.

The first event's existing configuration envelope gains a `model_profile` object
only for provider-component traces: provider, profile_id, model_identifier and
execution_mode. The conditional trace model identifier must agree. Current authored
graph traces continue using a null model identifier.

The privacy whitelist adds only these controlled fields:

| Fields | Meaning |
|---|---|
| `provider`, `profile_id`, `execution_mode`, `model_profile` | Explicit profile and offline/live distinction. |
| `template_version`, `template_digest`, `schema_digest` | Reviewed operation version and exact template/schema SHA-256; no prompt content. |
| `returned_model_identifier` | Validated returned identifier, distinct from configured metadata. |
| `provider_request_digest` | SHA-256 of the provider request header when available; no raw header or request ID. |
| `input_token_count`, `output_token_count`, `usage_known` | Bounded reported usage, or explicit unknown values. |
| `reserved_cost_microusd` | Conservative reservation, not an invoice measurement. |

Existing operation/call/role/correlation/phase/duration/error fields are reused.
AUTHORIZED, DISPATCHED and RETURNED/FAILED/CANCELLED records must correlate; only
entered dispatches count. A cancelled pre-dispatch reservation costs zero model
invocations. Complete traces cannot have unfinished calls. Schema/template hashes,
role bindings, usage types/caps, counts and terminal totals are independently checked.
Returned failures with unknown usage retain their full conservative reserve.

Raw prompts, user text, model output, SDK objects/headers, private reasoning and
arbitrary exceptions are not traced. Digesting request IDs avoids logging unexpected
provider-controlled strings. A malformed proposal cannot print its raw response in
the public error. Independent JSONL validation is still required before publication.

## Validation and remaining work

Final verification on Python 3.14.8:

- `uv sync --locked`: succeeded with the updated lockfile (50 resolved packages).
- `uv run --locked pytest`: **1,306 passed, 13 warnings in 44.52s**; 73 new tests
  over the 1,233-test baseline. Warnings are the existing upstream LangSmith asyncio
  deprecations. The focused new suite also passed all 73 tests.
- Package import and installed `hafi --version`: succeeded (`0.1.0`).
- Installed SC-004 / SC-010 component CLI runs: 84/84 and 61/61 assertions PASS,
  overall scenario BLOCKED, exit 2, preserving authored scope.
- All 15 changed/new Python files parse with Python 3.12 syntax; this is not a
  separate Python 3.12 runtime test. All 35 relative documentation links resolve,
  fences balance, and whitespace checks pass.
- Approved specifications, fixture bytes, logical schemas, graph/session/safety/
  harness code and CI configuration are unchanged. No live provider call, paid
  pilot, commit or push occurred.

Tests cover the
applicable offline portions of MR-T01–06/08/13/14/16/17. Prompt separation and
unauthorized-output checks support MR-T07; they do not prove a live model resists
every injection. Genuine observation-driven planning (MR-T10), graph cycle admission
and tool recovery integration (MR-T11/12), session-to-gateway wiring (MR-T15), actual
provider quality and full financial controls remain future work.

```bash
uv sync --locked
uv run --locked hafi --version
uv run --locked pytest tests/test_model_runtime_contracts.py tests/test_model_gateway.py tests/test_model_trace_validation.py
uv run --locked pytest
```

SDK-level failures/refusals currently retain unknown usage conservatively; a returned
reply rejected by local proposal validation retains its reported usage. Live error
metadata, tokenizer behavior and financial settlement still require pilot review.

SC-004 and SC-010 retain their independent authored component scope; overall scenario
acceptance remains BLOCKED. This increment does not implement Coordinator/Weather/
Ocean execution, select environmental providers, add a general conversational CLI,
or satisfy full M1 acceptance. No new approved-specification conflict was found.

Next: **M1.6-F — Synthetic Source Capability Profile Design**, defining the concrete
versioned legal-action metadata and query coverage for review before genuine agent
integration. Do not infer those capabilities from fixture scripts or expected
answers. Real activation still requires configuration baseline §5.3, account/data
review, actual token/latency/schema verification and explicit billing authorization.
