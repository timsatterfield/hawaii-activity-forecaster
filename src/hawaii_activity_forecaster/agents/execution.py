"""Admitted, model-driven execution using the existing LangGraph and safeguards."""

from hawaii_activity_forecaster.orchestration.session import RawSessionRequest
from hawaii_activity_forecaster.orchestration.skeleton import _run_graph


async def run_agent_investigation(admission, *, runtime, driver_inputs, policy, trace_settings=None, request_step=1):
    if not isinstance(admission, RawSessionRequest):
        raise ValueError("Agent execution requires an owned raw admission")
    return await _run_graph(admission.request, candidate_beach_ids=(), catalog=admission.context.catalog,
        session_id=admission.session_id, raw_admission=admission, provider_adapter=runtime.adapter,
        agent_runtime=True, plan=runtime.plan, tool_plan=runtime.tools, driver_inputs=driver_inputs,
        evidence_policy=policy, request_step=request_step, safety_evaluation=True, result_generation=True,
        trace_settings=trace_settings, record_event=None)
