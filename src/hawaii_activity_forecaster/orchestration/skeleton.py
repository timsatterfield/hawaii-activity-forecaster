"""Synthetic LangGraph control-flow probe, without agents or evidence evaluation."""

from collections.abc import Awaitable, Callable
from asyncio import wait_for
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from operator import add
from typing import Annotated, TypedDict
from uuid import uuid4

from pydantic import ValidationError

from langgraph.graph import END, START, StateGraph
from langsmith.run_helpers import tracing_context

from hawaii_activity_forecaster.config.settings import InvestigationLimits
from hawaii_activity_forecaster.models import (
    BeachCatalog, InvestigationState, NormalizedRequest, SpecialistInvestigationRequest,
    TimeRange, TraceEvent,
)
from hawaii_activity_forecaster.models.enums import (
    AgentType, InvestigationStatus, Outcome, TraceActor, TraceEventType,
)
from .budgets import BudgetManager, BudgetSnapshot
from .specialists import SpecialistContractError, SpecialistDelivery, SpecialistExchange
from hawaii_activity_forecaster.harness.contracts import DriverInputs
from hawaii_activity_forecaster.harness.synthetic import DispatchBinding, SyntheticDriver
from hawaii_activity_forecaster.tools.synthetic import SyntheticToolDispatcher, ToolAction


@dataclass(frozen=True)
class BranchInput:
    investigation_id: str
    request_revision: int
    agent_type: AgentType
    candidate_beach_ids: tuple[str, ...]
    target_time_window: TimeRange
    iteration: int


@dataclass(frozen=True)
class BranchSignal:
    """Test control signal, deliberately not a specialist/evidence contract."""

    agent_type: AgentType
    needs_another_cycle: bool = False


@dataclass(frozen=True)
class SkeletonReport:
    state: InvestigationState
    budgets: BudgetSnapshot
    visited_nodes: tuple[str, ...]
    trace_writable: bool
    tool_bindings: tuple[DispatchBinding, ...] = ()
    # state.result_id identifies an operational stop, not a validated public result.


class _GraphState(TypedDict, total=False):
    investigation: InvestigationState
    signals: Annotated[tuple[BranchSignal, ...], add]
    visited: Annotated[tuple[str, ...], add]
    route: str
    reason: str
    requests: tuple[SpecialistInvestigationRequest, ...]
    deliveries: Annotated[tuple[SpecialistDelivery, ...], add]


SyntheticBranch = Callable[[BranchInput], Awaitable[BranchSignal]]
EventRecorder = Callable[[TraceEvent], None]
SpecialistPlanner = Callable[[InvestigationState], tuple[SpecialistInvestigationRequest, ...]]
SyntheticSpecialist = Callable[[SpecialistInvestigationRequest], Awaitable[object]]


class _TraceFailure(RuntimeError):
    pass


def _updated(state: InvestigationState, **changes) -> InvestigationState:
    # Rebuild because model_copy(update=...) skips validation.
    return InvestigationState.model_validate({
        **state.model_dump(), **changes, "updated_at": datetime.now(timezone.utc),
    })


def _initial(request: NormalizedRequest, candidates: tuple[str, ...], session_id: str) -> InvestigationState:
    now = datetime.now(timezone.utc)
    limits = InvestigationLimits()
    return InvestigationState(
        **request.model_dump(), investigation_id=str(uuid4()), session_id=session_id,
        schema_version="0.1", created_at=now, updated_at=now,
        status=InvestigationStatus.INITIALIZING, request_revision=1,
        candidate_beach_ids=list(candidates), assessments=[], investigated_beach_ids=[],
        remaining_candidate_ids=list(candidates), weather_findings=[], ocean_findings=[],
        pending_evidence_requests=[], unresolved_evidence_issues=[], iteration_count=0,
        max_iterations=limits.max_coordinator_iterations, tool_call_count=0,
        max_tool_calls=limits.max_environmental_tool_invocations, retry_count=0,
        max_retries=limits.max_retries_per_failed_invocation,
        remaining_actions=[], active_errors=[], recovery_actions=[],
        fallback_attempted=False,
    )


async def run_skeleton(
    request: NormalizedRequest, *, candidate_beach_ids: tuple[str, ...],
    branch: SyntheticBranch, record_event: EventRecorder, session_id: str | None = None,
) -> SkeletonReport:
    """Traverse the graph with trusted synthetic callbacks only.

    Inputs are already normalized and candidates already selected. No agents,
    tools, evidence, safety decisions or public results are implemented here.
    Memory recorders are unit-test seams, not authoritative investigation traces.
    Recorder failures stop branch dispatch. Every run has fresh IDs and budgets;
    this API does not resume an investigation or accept previous graph state.
    """
    return await _run_graph(request, candidate_beach_ids=candidate_beach_ids, branch=branch,
                            record_event=record_event, session_id=session_id)


async def run_specialist_graph(
    request: NormalizedRequest, *, catalog: BeachCatalog, candidate_beach_ids: tuple[str, ...],
    plan: SpecialistPlanner, specialist: SyntheticSpecialist, record_event: EventRecorder,
    session_id: str | None = None,
) -> SkeletonReport:
    """Probe approved specialist contracts with trusted synthetic callbacks.

    Planning receives a detached state snapshot. Specialists receive only their
    authorized request. The trusted join validates/merges deliveries, preserving
    valid sibling work. No tools, automatic retries or safety decisions execute.
    """
    return await _run_graph(
        request, candidate_beach_ids=candidate_beach_ids, record_event=record_event,
        session_id=session_id, catalog=catalog, plan=plan, specialist_callback=specialist,
    )


async def _run_graph(
    request, *, candidate_beach_ids, record_event, session_id=None, branch=None,
    catalog=None, plan=None, specialist_callback=None, driver_inputs=None, tool_plan=None, request_step=1,
) -> SkeletonReport:
    request = NormalizedRequest.model_validate(request.model_dump())
    candidates = tuple(candidate_beach_ids)
    initial = _initial(request, candidates, session_id or str(uuid4()))
    budget = BudgetManager()
    current = initial
    visited: list[str] = []
    sequence = 0
    trace_id = str(uuid4())
    trace_failed = False
    exchange = SpecialistExchange(initial, catalog) if catalog is not None else None
    dispatcher = None

    def emit(event_type: TraceEventType, **details):
        nonlocal sequence, trace_failed
        if trace_failed:
            raise _TraceFailure("mandatory event recording failed")
        sequence += 1
        event = TraceEvent(
            event_id=str(uuid4()), trace_id=trace_id, sequence_number=sequence,
            timestamp=datetime.now(timezone.utc), event_type=event_type,
            actor=TraceActor.ORCHESTRATOR, request_revision=initial.request_revision,
            details={"investigation_id": initial.investigation_id, **details},
        )
        try:
            record_event(event)
        except Exception:
            trace_failed = True
            budget.close()
            if exchange is not None:
                exchange.close()
            raise _TraceFailure("mandatory event recording failed") from None

    def visit(name: str):
        visited.append(name)
        return {"visited": (name,)}

    if driver_inputs is not None:
        driver = SyntheticDriver(driver_inputs)
        reference = driver.reference_time(request_step)
        dispatcher = SyntheticToolDispatcher(
            driver, budget, investigation_id=initial.investigation_id, request_revision=initial.request_revision,
            reference_time=reference, emit=emit, request_step=request_step,
        )
        specialist_callback = dispatcher.run

    def initialize(state: _GraphState):
        emit(TraceEventType.INVESTIGATION_STARTED, component_probe=True)
        return visit("initialize_investigation")

    def validate(state: _GraphState):
        nonlocal current
        current = state["investigation"]
        update = visit("validate_request")
        if request.clarification_needed or request.activity is None or request.target_time_window is None:
            current = _updated(current, status=InvestigationStatus.AWAITING_CLARIFICATION,
                               clarification_needed=True)
            emit(TraceEventType.CLARIFICATION_REQUESTED)
            return {**update, "investigation": current, "route": "end"}
        if not candidates:
            return {**update, "route": "stop", "reason": "NO_SELECTED_CANDIDATES"}
        current = _updated(current, status=InvestigationStatus.INVESTIGATING)
        return {**update, "investigation": current, "route": "dispatch"}

    def authorize(state: _GraphState):
        nonlocal current
        iteration = budget.begin_iteration()
        current = _updated(state["investigation"], status=InvestigationStatus.INVESTIGATING,
                           iteration_count=iteration)
        return {**visit("authorize_dispatch"), "investigation": current}

    def plan_evidence(state: _GraphState):
        nonlocal current
        snapshot = InvestigationState.model_validate(state["investigation"].model_dump())
        try:
            requests = tuple(SpecialistInvestigationRequest.model_validate(
                r.model_dump() if isinstance(r, SpecialistInvestigationRequest) else deepcopy(r),
            ) for r in plan(snapshot))
        except (ValidationError, ValueError, TypeError):
            emit(TraceEventType.CONTRACT_VALIDATED, contract="specialist_request", valid=False,
                 reason="REQUEST_SCHEMA_INVALID")
            raise SpecialistContractError("REQUEST_SCHEMA_INVALID") from None
        if not requests:
            return {**visit("plan_evidence"), "route": "stop", "reason": "VALIDATORS_NOT_IMPLEMENTED"}
        try:
            proposed = exchange.authorize(state["investigation"], requests, now=datetime.now(timezone.utc))
            if dispatcher is not None:
                for scoped in requests:
                    detached = SpecialistInvestigationRequest.model_validate(scoped.model_dump())
                    dispatcher.register(scoped, tuple(tool_plan(detached)))
        except SpecialistContractError as error:
            emit(TraceEventType.CONTRACT_VALIDATED, contract="specialist_request", valid=False,
                 reason=str(error), request_ids=[r.request_id for r in requests])
            raise
        emit(TraceEventType.CONTRACT_VALIDATED, contract="specialist_request", valid=True,
             request_ids=[r.request_id for r in requests])
        current = proposed
        # Planner-owned nested lists never become shared graph authority.
        return {**visit("plan_evidence"), "investigation": current, "route": "authorize",
                "requests": tuple(SpecialistInvestigationRequest.model_validate(r.model_dump()) for r in requests)}

    async def specialist(state: _GraphState, role: AgentType):
        snapshot = state["investigation"]
        scoped_request = None
        if exchange is not None:
            scoped_request = next((r for r in state["requests"] if r.agent_type == role), None)
            if scoped_request is None:
                return visit(f"{role.value.lower()}_skipped")
        with budget.specialist_slot(role):
            emit(TraceEventType.AGENT_STARTED, agent_type=role.value, iteration=snapshot.iteration_count)
            if exchange is not None:
                detached = SpecialistInvestigationRequest.model_validate(scoped_request.model_dump())
                try:
                    if scoped_request.deadline_at is None:
                        response = await specialist_callback(detached)
                    else:
                        seconds = (scoped_request.deadline_at - datetime.now(timezone.utc)).total_seconds()
                        if seconds <= 0:
                            raise TimeoutError("delegation expired before dispatch")
                        response = await wait_for(specialist_callback(detached), timeout=seconds)
                    # Capture now; callbacks may retain and later mutate their own payload.
                    response = deepcopy(response)
                except Exception:
                    emit(TraceEventType.AGENT_FAILED, request_id=scoped_request.request_id,
                         attempt_number=scoped_request.attempt_number)
                    delivery = SpecialistDelivery(scoped_request.request_id, scoped_request.attempt_number,
                                                  execution_failed=True)
                else:
                    emit(TraceEventType.AGENT_COMPLETED, request_id=scoped_request.request_id,
                         attempt_number=scoped_request.attempt_number)
                    delivery = SpecialistDelivery(scoped_request.request_id, scoped_request.attempt_number, response)
                return {**visit(f"{role.value.lower()}_investigation"), "deliveries": (delivery,)}
            # No mutable logical state or budget manager is exposed to callbacks.
            signal = await branch(BranchInput(
                snapshot.investigation_id, snapshot.request_revision, role, candidates,
                TimeRange.model_validate(snapshot.target_time_window.model_dump()), snapshot.iteration_count,
            ))
            if (not isinstance(signal, BranchSignal) or not isinstance(signal.agent_type, AgentType)
                    or signal.agent_type != role or type(signal.needs_another_cycle) is not bool):
                raise ValueError("invalid synthetic branch signal")
            emit(TraceEventType.AGENT_COMPLETED, agent_type=role.value, iteration=snapshot.iteration_count)
            return {**visit(f"{role.value.lower()}_investigation"), "signals": (signal,)}

    async def weather(state: _GraphState):
        return await specialist(state, AgentType.WEATHER)

    async def ocean(state: _GraphState):
        return await specialist(state, AgentType.OCEAN)

    def merge_responses(state: _GraphState):
        nonlocal current
        # Only this cycle's isolated outputs participate in its trusted join.
        deliveries = state["deliveries"][-len(state["requests"]):]
        report = exchange.merge(state["investigation"], deliveries,
                                now=datetime.now(timezone.utc))
        for response_id in report.accepted_response_ids:
            origin = next(d for d in deliveries if (
                d.response.get("response_id") if isinstance(d.response, dict)
                else getattr(d.response, "response_id", None)
            ) == response_id)
            emit(TraceEventType.CONTRACT_VALIDATED, contract="specialist_response", valid=True,
                 response_id=response_id, request_id=origin.request_id, attempt_number=origin.attempt_number)
        for rejection in report.rejections:
            emit(TraceEventType.CONTRACT_VALIDATED, contract="specialist_response", valid=False,
                 request_id=rejection.request_id, attempt_number=rejection.attempt_number,
                 response_id=rejection.response_id, reason=rejection.reason)
        if report.accepted_response_ids:
            emit(TraceEventType.EVIDENCE_RECEIVED, response_ids=list(report.accepted_response_ids),
                 validation_status="PENDING")
        stats = budget.snapshot()
        current = _updated(report.state, tool_call_count=stats.tool_calls, retry_count=stats.retries,
                           fallback_attempted=bool(stats.fallbacks))
        return {**visit("validate_and_merge_specialist_responses"), "investigation": current}

    def decide(state: _GraphState):
        nonlocal current
        current = _updated(state["investigation"], status=InvestigationStatus.EVALUATING)
        more = (bool(current.unresolved_evidence_issues or current.active_errors) if exchange is not None
                else any(signal.needs_another_cycle for signal in state["signals"][-2:]))
        repeat = more and current.iteration_count < current.max_iterations
        reason = "ITERATION_LIMIT_REACHED" if more else "VALIDATORS_NOT_IMPLEMENTED"
        if more and not repeat:
            emit(TraceEventType.INVESTIGATION_LIMIT_REACHED, iteration=current.iteration_count)
        return {**visit("decide_next_action"), "investigation": current,
                "route": "dispatch" if repeat else "stop", "reason": reason}

    def finalize(state: _GraphState):
        nonlocal current
        budget.close()
        if dispatcher is not None:
            dispatcher.close()
        if exchange is not None:
            exchange.close()
        current = _updated(state["investigation"], status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                           result_id=str(uuid4()), completion_reason=state["reason"])
        emit(TraceEventType.INVESTIGATION_FAILED, reason=state["reason"])
        return {**visit("finalize_investigation"), "investigation": current}

    graph = StateGraph(_GraphState)
    for name, node in (
        ("initialize_investigation", initialize), ("validate_request", validate),
        ("authorize_dispatch", authorize), ("weather_investigation", weather),
        ("ocean_investigation", ocean), ("decide_next_action", decide),
        ("finalize_investigation", finalize),
    ):
        graph.add_node(name, node)
    graph.add_edge(START, "initialize_investigation")
    graph.add_edge("initialize_investigation", "validate_request")
    routes = {"dispatch": "authorize_dispatch", "stop": "finalize_investigation", "end": END}
    if exchange is not None:
        graph.add_node("plan_evidence", plan_evidence)
        graph.add_node("validate_and_merge_specialist_responses", merge_responses)
        routes["dispatch"] = "plan_evidence"
        graph.add_conditional_edges("plan_evidence", lambda state: state["route"],
                                    {"authorize": "authorize_dispatch", "stop": "finalize_investigation"})
    graph.add_conditional_edges("validate_request", lambda state: state["route"], routes)
    graph.add_edge("authorize_dispatch", "weather_investigation")
    graph.add_edge("authorize_dispatch", "ocean_investigation")
    join = "validate_and_merge_specialist_responses" if exchange is not None else "decide_next_action"
    graph.add_edge(["weather_investigation", "ocean_investigation"], join)
    if exchange is not None:
        graph.add_edge(join, "decide_next_action")
    graph.add_conditional_edges("decide_next_action", lambda state: state["route"], routes)
    graph.add_edge("finalize_investigation", END)
    trace_writable = True
    try:
        # Suppress remote tracing even if ambient SDK variables enable it.
        with tracing_context(enabled=False):
            await graph.compile().ainvoke(
                {"investigation": initial, "signals": (), "visited": (), "deliveries": ()},
                config={"recursion_limit": 32},
            )
    except Exception as error:
        reason = ("TRACE_WRITE_FAILED" if trace_failed else
                  "SPECIALIST_CONTRACT_FAILED" if isinstance(error, SpecialistContractError) else
                  "SKELETON_EXECUTION_FAILED")
        trace_writable = not trace_failed
        budget.close()
        current = _updated(current, status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                           result_id=str(uuid4()), completion_reason=reason)
        if trace_writable:
            try:
                emit(TraceEventType.INVESTIGATION_FAILED, reason=reason)
            except _TraceFailure:
                trace_writable = False
                current = _updated(current, completion_reason="TRACE_WRITE_FAILED")
    finally:
        budget.close()
        if dispatcher is not None:
            dispatcher.close()
        if exchange is not None:
            exchange.close()
    stats = budget.snapshot()
    current = _updated(current, tool_call_count=stats.tool_calls, retry_count=stats.retries,
                       fallback_attempted=bool(stats.fallbacks))
    return SkeletonReport(current, stats, tuple(visited), trace_writable,
                          dispatcher.driver.bindings if dispatcher is not None else ())


async def run_synthetic_tool_graph(
    request: NormalizedRequest, *, catalog: BeachCatalog, candidate_beach_ids: tuple[str, ...],
    plan: SpecialistPlanner, tool_plan: Callable[[SpecialistInvestigationRequest], tuple[ToolAction, ...]],
    driver_inputs: DriverInputs, record_event: EventRecorder, session_id: str | None = None,
    request_step: int = 1,
) -> SkeletonReport:
    """Execute explicitly planned synthetic retrievals; never an acceptance run.

    Driver inputs stay in the trusted layer; planners receive no script/oracle.
    Evidence, safety, result evaluation and authoritative JSONL remain deferred.
    """
    if type(request_step) is not int or not 1 <= request_step <= len(driver_inputs.script.requests):
        raise ValueError("Invalid synthetic request step")
    return await _run_graph(
        request, candidate_beach_ids=candidate_beach_ids, catalog=catalog, plan=plan,
        tool_plan=tool_plan, driver_inputs=driver_inputs, request_step=request_step,
        record_event=record_event, session_id=session_id,
    )
