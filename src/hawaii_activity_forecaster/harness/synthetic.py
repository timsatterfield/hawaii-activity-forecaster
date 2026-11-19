"""Scripted retrieval materialization, independent of application decisions/oracles."""

from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
from uuid import uuid4

from hawaii_activity_forecaster.fixtures.loading import FixtureLoadError
from hawaii_activity_forecaster.models import EnvironmentalToolRequest, SpecialistError
from .behavior import Operation
from .contracts import DriverInputs
from .preflight import check_malformed


class ScriptDispatchError(ValueError):
    """No matching available scripted invocation; not a source outage."""


@dataclass(frozen=True)
class FindingBinding:
    template_finding_id: str
    runtime_finding_id: str


@dataclass(frozen=True)
class DispatchBinding:
    request_step: int
    operation_id: str
    attempt: int
    runtime_investigation_id: str
    runtime_tool_call_id: str
    source_fixture_id: str | None
    findings: tuple[FindingBinding, ...]


@dataclass(frozen=True)
class ScriptDelivery:
    payloads: tuple[object, ...]
    elapsed_ms: int
    timed_out: bool


class SyntheticDriver:
    """One run's snapshotted driver inputs and observed bindings.

    No methods expose scripts, fault annotations or expected assertions to the
    application. peek/deliver must be serialized by the trusted dispatcher.
    """

    def __init__(self, inputs: DriverInputs):
        # exclude_unset preserves behavior-specific exact field declarations.
        self._inputs = DriverInputs.model_validate_json(inputs.model_dump_json(exclude_unset=True))
        self._used: dict[tuple[str, str], int] = {}
        self._bindings: list[DispatchBinding] = []
        self._lock = RLock()
        for op in self._inputs.script.operations:
            for attempt in op.attempts:
                if attempt.behavior == "MALFORMED":
                    if attempt.raw_response_path not in self._inputs.malformed_responses:
                        raise FixtureLoadError("Missing preflighted malformed payload.")
                    check_malformed(attempt, self._inputs.malformed_responses[attempt.raw_response_path])
                elif attempt.response_fixture_id is not None:
                    template = self._inputs.source_responses.get(attempt.response_fixture_id)
                    if (template is None or template.source_id != op.source_id
                            or (attempt.behavior != "DUPLICATE" and template.retrieval_status != attempt.behavior)
                            or (attempt.behavior == "DUPLICATE" and template.retrieval_status not in {"SUCCESS", "PARTIAL"})):
                        raise FixtureLoadError("Script/template mismatch.")
                    for error in template.errors:
                        parsed = SpecialistError.model_validate(error)
                        if parsed.source_id is not None and parsed.source_id != op.source_id:
                            raise FixtureLoadError("Error refers to another source.")

    @property
    def bindings(self) -> tuple[DispatchBinding, ...]:
        with self._lock:
            return tuple(self._bindings)

    def reference_time(self, request_step: int):
        return self._inputs.script.requests[request_step - 1].reference_time

    def peek(self, request: EnvironmentalToolRequest, candidates: tuple[str, ...], request_step: int,
             *, retry: bool) -> tuple[str, int]:
        probe = Operation(
            operation_id="dispatch-probe", request_step=request_step, agent_type=request.agent_type,
            source_id=request.source_id, candidate_beach_ids=list(candidates),
            requested_evidence=request.requested_evidence, target_time_window=request.target_time_window,
            geographic_scope=request.geographic_scope,
            attempts=[{"attempt": 1, "behavior": "TIMEOUT", "simulated_duration_ms": 10001}],
        )
        with self._lock:
            matches = [op for op in self._inputs.script.operations if op.match_key() == probe.match_key()]
            if len(matches) != 1:
                raise ScriptDispatchError("Unmatched or ambiguous scripted operation.")
            op = matches[0]
            used = self._used.get((request.investigation_id, op.operation_id), 0)
            if (used != 0) != retry or used >= len(op.attempts):
                raise ScriptDispatchError("Unmatched or excess operation attempt.")
            return op.operation_id, used + 1

    def deliver(self, request: EnvironmentalToolRequest, operation_id: str, attempt: int) -> ScriptDelivery:
        with self._lock:
            op = next(op for op in self._inputs.script.operations if op.operation_id == operation_id)
            key = (request.investigation_id, operation_id)
            if self._used.get(key, 0) + 1 != attempt:
                raise ScriptDispatchError("Operation attempt was already consumed.")
            scripted = op.attempts[attempt - 1]
            self._used[key] = attempt
            fixture_id = scripted.response_fixture_id
            bindings = []
            if scripted.behavior == "TIMEOUT":
                payloads = ()
            elif scripted.behavior == "MALFORMED":
                payloads = (deepcopy(self._inputs.malformed_responses[scripted.raw_response_path]),)
            else:
                template = self._inputs.source_responses[fixture_id]
                payload = template.model_dump(mode="json")
                payload["tool_call_id"] = request.tool_call_id
                payload["duration_ms"] = scripted.simulated_duration_ms
                for finding in payload["findings"]:
                    runtime_id = str(uuid4())
                    bindings.append(FindingBinding(finding["finding_id"], runtime_id))
                    finding.update(finding_id=runtime_id, investigation_id=request.investigation_id)
                for error in payload["errors"]:
                    error.update(error_id=str(uuid4()), source_id=request.source_id.value,
                                 tool_call_id=request.tool_call_id)
                count = scripted.delivery_count if scripted.behavior == "DUPLICATE" else 1
                payloads = tuple(deepcopy(payload) for _ in range(count))
            self._bindings.append(DispatchBinding(
                op.request_step, operation_id, attempt, request.investigation_id,
                request.tool_call_id, fixture_id, tuple(bindings),
            ))
            return ScriptDelivery(payloads, min(scripted.simulated_duration_ms, 10000),
                                  scripted.behavior == "TIMEOUT")
