"""Independent provider-call lifecycle checks; offline transport is not a live run."""

import re
from hashlib import sha256

from hawaii_activity_forecaster.model_runtime.prompts import MODEL, PROFILE, CALL_RESERVE_MICROUSD, canonical, template_text
from hawaii_activity_forecaster.model_runtime.contracts import OUTPUTS
from hawaii_activity_forecaster.model_runtime.errors import ERROR_CODES


PROFILE_METADATA = dict(profile_id=PROFILE, provider="openai", model_identifier=MODEL,
                        execution_mode="OFFLINE_TRANSPORT")
TRACE_MODES = frozenset({"OFFLINE_TRANSPORT", "LIVE_PROVIDER"})
OPERATIONS = {"normalize_request": "COORDINATOR", "coordinator_plan": "COORDINATOR",
              "weather_investigation": "WEATHER", "ocean_investigation": "OCEAN"}


class ModelTraceLedger:
    def __init__(self, require):
        self._require = require
        self.authorized, self.dispatched, self.done = {}, set(), set()

    def observe(self, d, *, metadata, profile, received, normalized, legacy_calls):
        check, call = self._require, d["call_id"]
        check(metadata == MODEL, "TRACE_MODEL_METADATA_INVALID")
        check(all(d[k] == v for k, v in profile.items())
              and d["synthetic_adapter"] is False, "TRACE_MODEL_PROFILE_INVALID")
        operation = d["operation"]
        check(operation in OPERATIONS and d["agent_type"] == OPERATIONS[operation]
              and d["template_version"] == f"{operation}-0.1", "TRACE_MODEL_OPERATION_INVALID")
        check(d["schema_digest"] == sha256(canonical(OUTPUTS[operation].model_json_schema()).encode()).hexdigest(),
              "TRACE_MODEL_SCHEMA_INVALID")
        check(d["template_digest"] == sha256(template_text(operation).encode()).hexdigest(),
              "TRACE_MODEL_TEMPLATE_INVALID")
        check(type(d["reserved_cost_microusd"]) is int and d["reserved_cost_microusd"] == CALL_RESERVE_MICROUSD,
              "TRACE_MODEL_RESERVATION_INVALID")
        check(received and (normalized or operation == "normalize_request"), "TRACE_MODEL_ADMISSION_MISSING")
        phase = d["phase"]
        if phase == "AUTHORIZED":
            check(call not in self.authorized and call not in legacy_calls, "TRACE_MODEL_CALL_DUPLICATED")
            self.authorized[call] = d
            return
        check(call in self.authorized and call not in self.done, "TRACE_MODEL_OUTCOME_UNCORRELATED")
        base = self.authorized[call]
        names = ("operation", "agent_type", "profile_id", "model_identifier", "execution_mode",
                 "template_version", "template_digest", "schema_digest", "reserved_cost_microusd")
        check(all(d[k] == base[k] for k in names), "TRACE_MODEL_CORRELATION_INVALID")
        if phase == "DISPATCHED":
            check(call not in self.dispatched, "TRACE_MODEL_DISPATCH_DUPLICATED")
            self.dispatched.add(call)
            check(len(self.dispatched) + len(legacy_calls) <= 12, "TRACE_MODEL_BUDGET_EXCEEDED")
            return
        check(phase in {"RETURNED", "FAILED", "CANCELLED"}
              and (phase == "CANCELLED") == (call not in self.dispatched), "TRACE_MODEL_PHASE_INVALID")
        check(d["valid"] is (phase == "RETURNED") and type(d["duration_ms"]) is int and d["duration_ms"] >= 0,
              "TRACE_MODEL_OUTCOME_INVALID")
        if phase != "RETURNED":
            check(d["error_code"] in ERROR_CODES, "TRACE_MODEL_ERROR_INVALID")
        check(d["returned_model_identifier"] in {None, MODEL}
              and (phase != "RETURNED" or d["returned_model_identifier"] == MODEL), "TRACE_MODEL_RETURNED_ID_INVALID")
        digest = d["provider_request_digest"]
        check(digest is None or isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-f]{64}", digest)),
              "TRACE_MODEL_REQUEST_ID_INVALID")
        tokens = d["input_token_count"], d["output_token_count"]
        check(type(d["usage_known"]) is bool and
              ((d["usage_known"] and all(type(n) is int and 0 <= n <= cap for n, cap in zip(tokens, (8000, 2048))))
               or (not d["usage_known"] and tokens == (None, None))), "TRACE_MODEL_USAGE_INVALID")
        self.done.add(call)

    def finish(self):
        self._require(set(self.authorized) == self.done, "TRACE_MODEL_OPERATIONS_UNFINISHED")
