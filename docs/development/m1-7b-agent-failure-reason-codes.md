# M1.7-B — Sanitized failure categories for specialists and request interpretation

Two of the seven live acceptance attempts failed closed, and their traces could not
say why. SC-004 #1's request interpretation was rejected, and SC-010 #1's Ocean plan
was rejected. Both handlers caught the exception and recorded only
`REQUEST_NORMALIZATION_FAILED` or a bare `AGENT_FAILED`.
[Observability](../requirements/07-observability.md) §7.2 and §10.4 already ask for
a "structured error category" and a "sanitized error category" for technical
failures. This batch fills that gap. No new trace field is introduced:
`error_code` is already in the reviewed privacy allowlist.

## What is recorded

| Event | New detail | Vocabulary |
|---|---|---|
| `AGENT_FAILED` | `error_code` | `AGENT_FAILURE_CODES` |
| `CONTRACT_VALIDATED` with `contract: request_interpretation`, `valid: false` | `error_code`, alongside the existing `reason` | `REQUEST_FAILURE_CODES` |

Both vocabularies live in `observability/failure_codes.py` and are closed:

- **Plan rejections.** Each fixed `ToolPlanError` message maps to a code, for example
  `PLAN_RECOVERY_CONDITION_INVALID`, `PLAN_RECOVERY_ORIGIN_MISMATCH`,
  `PLAN_DUPLICATE_ORIGINAL`, `PLAN_FALLBACK_INVALID` and `PLAN_SCOPE_EXCEEDED`.
  An option the model invented that is absent from the legal lookup becomes
  `PLAN_OPTION_UNKNOWN`.
- **Request rejections.** Each fixed `RequestValidationError` message maps to a
  code, for example `REQUEST_SPAN_FIELD_MISMATCH`, `REQUEST_CHANGE_UNSUPPORTED`,
  `REQUEST_CHANGE_OMITTED` and `REQUEST_AREA_AMBIGUOUS`.
- **Model-layer failures** reuse the gateway's existing closed `ERROR_CODES`, such as
  `MODEL_HTTP_INPUT_INVALID` and `MODEL_TIMEOUT`. Anything else from the model
  layer is `MODEL_CALL_FAILED`.
- **Other errors** use a small set of codes: `DELEGATION_TIMEOUT`,
  `BUDGET_EXHAUSTED`, `SPECIALIST_CONTRACT_INVALID`, `TOOL_OPTIONS_UNAVAILABLE`
  and `SCRIPTED_OPERATION_UNMATCHED`. Anything unrecognized is `UNCLASSIFIED`.

**Privacy.** Classification uses exception types and the validators' fixed
messages. The recorded value is always a constant, never exception text, model
output, option IDs, spans or request wording. A test confirms that an invented
option ID, and errors containing request text, never appear in the trace.

**Validation.** The independent trace validator accepts `error_code` only from the
closed vocabularies, only on `AGENT_FAILED` (not `AGENT_COMPLETED`) and only on
rejected interpretations. Out-of-vocabulary values fail with
`TRACE_SPECIALIST_ERROR_CODE_INVALID` or `TRACE_REQUEST_ERROR_CODE_INVALID`. The
field is optional, so every earlier trace still validates, including the pilot and
all acceptance attempts.

**Follow-up fix (M1.9).** `validate_request` originally collapsed every specific
`RequestValidationError` into its generic catch-all, recorded as
`REQUEST_PROPOSAL_INVALID`. It now preserves the specific message, so the codes
above are recorded for validation rejections too.

## Evidence

`tests/test_failure_codes.py` (17 tests, offline):

- **Coverage.** Every fixed `ToolPlanError` and `RequestValidationError` message in
  the source tree has a code. A new message without one fails this test.
- **Classifier.** Codes are closed and never echo error text.
- **Rejected Ocean plan.** SC-010 with `SURF_ABCD` declared as an original makes the
  planner label it a fallback. The trace records
  `AGENT_FAILED.error_code = PLAN_RECOVERY_CONDITION_INVALID`, and the validator
  accepts it.
- **Rejected follow-up.** SC-012 on profile 0.2 is rejected with
  `MODEL_HTTP_INPUT_INVALID`, recorded on the request-interpretation event.
- **Tampering.** An out-of-vocabulary code in a trace is rejected.

Suite: 1413 passed, 1 xfailed.

## Reading a failure

```bash
grep -h '"AGENT_FAILED"\|"request_interpretation"' traces/acceptance/<id>.jsonl
```

The `error_code` names the rule that rejected the model's output. The earlier
SC-004 #1 and SC-010 #1 traces predate this change and remain uncategorized.
The next live failure will say which rule fired.
