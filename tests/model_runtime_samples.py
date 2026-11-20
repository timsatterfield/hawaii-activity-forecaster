"""Explicit offline Responses HTTP samples and required JSONL probe sink."""

from datetime import datetime, timezone
import json
from uuid import uuid4

import httpx

from hawaii_activity_forecaster.config import AppConfig, LLMSettings, TraceSettings
from hawaii_activity_forecaster.interpretation import validate_request
from hawaii_activity_forecaster.interpretation.validation import interpreter_input
from hawaii_activity_forecaster.model_runtime.contracts import InvocationIdentity, CoordinatorInput, SpecialistInput
from hawaii_activity_forecaster.model_runtime.gateway import ModelGateway
from hawaii_activity_forecaster.model_runtime.prompts import MODEL, PROFILE
from hawaii_activity_forecaster.model_runtime.provider import OpenAITransportAdapter
from hawaii_activity_forecaster.models import TraceEvent
from hawaii_activity_forecaster.observability import JsonlTraceWriter
from hawaii_activity_forecaster.observability.model_validation import PROFILE_METADATA
from hawaii_activity_forecaster.orchestration.budgets import BudgetManager
from interpretation_samples import morning, window


def normalization():
    ctx, proposal = morning()
    wire = dict(changes=[dict(field=k, value_json=json.dumps(v)) for k, v in proposal['changed_values'].items()],
        source_spans=[dict(s, entry_index=None) for s in proposal['source_spans']], removed_entries=[], unresolved_spans=[])
    identity = InvocationIdentity(session_id=ctx.session_id, investigation_id=ctx.investigation_id, request_revision=1)
    return identity, interpreter_input(ctx), wire


def coordinator():
    ctx, proposal = morning()
    identity, _, _ = normalization()
    task = dict(agent_type="WEATHER", candidate_ids=["beach-a"], evidence_categories=["WIND_CONDITIONS"], gap_ids=["gap-a"])
    inputs = CoordinatorInput.model_validate_json(json.dumps(dict(identity=identity.model_dump(),
        request=validate_request(proposal, ctx).request.model_dump(mode="json"), candidate_ids=["beach-a"],
        assessments=[], observations=[], legal_tasks=[task], evidence_refs=["finding-a"],
        allowed_stop_reasons=["SUFFICIENT_EVIDENCE"], remaining_model_calls=11,
        remaining_tool_calls=12, remaining_iterations=5)))
    wire = dict(action="DELEGATE", tasks=[task], reason_code="INVESTIGATE_GAPS", evidence_refs=[])
    return inputs, wire


def specialist(role="WEATHER"):
    identity, _, _ = normalization()
    request=dict(request_id='specialist-request', investigation_id=identity.investigation_id, request_revision=1,
        schema_version='0.1', agent_type=role, candidate_beach_ids=['beach-a'], target_time_window=window(),
        requested_evidence=[dict(requirement_id='req-a',evidence_type='WIND_CONDITIONS' if role=='WEATHER' else 'SURF_WAVE_CONDITIONS',priority='REQUIRED')],
        known_evidence_gaps=[dict(gap_id='gap-a',gap_type='MISSING',related_finding_ids=[],description='Missing scoped evidence')],
        issued_at='2026-11-16T09:00:00-10:00',attempt_number=1,deadline_at='2026-11-16T09:01:00-10:00')
    inputs = SpecialistInput.model_validate_json(json.dumps(dict(identity=identity.model_dump(), request=request, gap_ids=["gap-a"],
        legal_option_ids=["primary", "retry", "fallback"], observations=[], remaining_tool_calls=12)))
    wire = dict(steps=[dict(option_id="primary", condition="ALWAYS", origin_step=None)],
                unresolved_gap_ids=[], reason_code="PLANNED_WORK")
    return inputs, wire


def response(wire, *, status="completed", model=MODEL, usage=True, refusal=False):
    content = ([dict(type="refusal", refusal="private-refusal")] if refusal else
               [dict(type="output_text", text=wire if isinstance(wire, str) else json.dumps(wire), annotations=[])])
    value = dict(id="resp_test", object="response", created_at=1, status=status, model=model,
        output=[dict(id="msg_test", type="message", status="completed", role="assistant", content=content)])
    if status == "incomplete":
        value["incomplete_details"] = {"reason": "max_output_tokens"}
    if usage:
        value["usage"] = dict(input_tokens=100, output_tokens=40, total_tokens=140)
    return httpx.Response(200, json=value, headers={"x-request-id": "private-provider-request"})


class Probe:
    def __init__(self, tmp_path, handler, *, fail_at=None, current=None, budget=None):
        self.identity, self.inputs, self.wire = normalization()
        self.budget, self.events, self.requests = budget or BudgetManager(), [], []
        self.fail_at = fail_at
        self.trace_id = str(uuid4())
        self.writer = JsonlTraceWriter(TraceSettings(directory=tmp_path), trace_id=self.trace_id,
            investigation_id=self.identity.investigation_id, session_id=self.identity.session_id, request_revision=1)
        config = AppConfig()
        self.emit("INVESTIGATION_STARTED", status="INITIALIZING", component_probe=True, candidate_beach_ids=[],
            trace_metadata=dict(schema_version="0.1", configuration_version="0.1", policy_version="not-applied", model_identifier=MODEL),
            configuration=dict(limits=config.limits.model_dump(), model_profile=PROFILE_METADATA))
        self.emit("REQUEST_RECEIVED")
        async def record(request):
            self.requests.append(request)
            return await handler(request)
        adapter = OpenAITransportAdapter(LLMSettings(provider="openai", model_identifier=MODEL, profile_id=PROFILE),
                                         transport=httpx.MockTransport(record))
        self.gateway = ModelGateway(identity=self.identity, budget=self.budget, adapter=adapter,
                                    emit=self.emit, is_current=current or (lambda _: True))

    def emit(self, kind, **details):
        if details.get("phase") == self.fail_at and self.fail_at is not None:
            raise RuntimeError("private-trace-sink-failure")
        b = self.budget.snapshot()
        event = TraceEvent(event_id=str(uuid4()), trace_id=self.trace_id, sequence_number=len(self.events)+1,
            timestamp=datetime.now(timezone.utc), event_type=kind, actor="VALIDATOR", request_revision=1,
            details=dict(investigation_id=self.identity.investigation_id, session_id=self.identity.session_id,
                model_call_count=b.model_calls, tool_call_count=b.tool_calls, iteration_count=b.iterations,
                retry_count=b.retries, **details))
        self.writer.append(event)
        self.events.append(event)

    def finish(self):
        self.budget.close()
        b = self.budget.snapshot()
        self.emit("INVESTIGATION_FAILED", final_status="FAILED", outcome="ERROR",
            completion_reason="OFFLINE_COMPONENT_PROBE", result_id=None, recommendation_count=0,
            recommended_beach_ids=[], total_tool_calls=b.tool_calls, total_model_calls=b.model_calls,
            total_iterations=0, total_retries=0, total_fallbacks=0)
        return self.writer.path
