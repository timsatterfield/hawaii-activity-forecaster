"""Synthetic LangGraph control-flow probe, without agents or evidence evaluation."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from operator import add
from typing import Annotated, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langsmith.run_helpers import tracing_context

from hawaii_activity_forecaster.config.settings import InvestigationLimits
from hawaii_activity_forecaster.models import InvestigationState, NormalizedRequest, TimeRange, TraceEvent
from hawaii_activity_forecaster.models.enums import (
    AgentType, InvestigationStatus, Outcome, TraceActor, TraceEventType,
)
from .budgets import BudgetManager, BudgetSnapshot


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
    # state.result_id identifies an operational stop, not a validated public result.


class _GraphState(TypedDict, total=False):
    investigation: InvestigationState
    signals: Annotated[tuple[BranchSignal, ...], add]
    visited: Annotated[tuple[str, ...], add]
    route: str
    reason: str


SyntheticBranch = Callable[[BranchInput], Awaitable[BranchSignal]]
EventRecorder = Callable[[TraceEvent], None]


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
        schema_version="1.0.0", created_at=now, updated_at=now,
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
    request = NormalizedRequest.model_validate(request.model_dump())
    candidates = tuple(candidate_beach_ids)
    initial = _initial(request, candidates, session_id or str(uuid4()))
    budget = BudgetManager()
    current = initial
    visited: list[str] = []
    sequence = 0
    trace_id = str(uuid4())
    trace_failed = False

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
            raise _TraceFailure("mandatory event recording failed") from None

    def visit(name: str):
        visited.append(name)
        return {"visited": (name,)}

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

    async def specialist(state: _GraphState, role: AgentType):
        snapshot = state["investigation"]
        with budget.specialist_slot(role):
            emit(TraceEventType.AGENT_STARTED, agent_type=role.value, iteration=snapshot.iteration_count)
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

    def decide(state: _GraphState):
        nonlocal current
        current = _updated(state["investigation"], status=InvestigationStatus.EVALUATING)
        more = any(signal.needs_another_cycle for signal in state["signals"][-2:])
        repeat = more and current.iteration_count < current.max_iterations
        reason = "ITERATION_LIMIT_REACHED" if more else "VALIDATORS_NOT_IMPLEMENTED"
        if more and not repeat:
            emit(TraceEventType.INVESTIGATION_LIMIT_REACHED, iteration=current.iteration_count)
        return {**visit("decide_next_action"), "investigation": current,
                "route": "dispatch" if repeat else "stop", "reason": reason}

    def finalize(state: _GraphState):
        nonlocal current
        budget.close()
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
    graph.add_conditional_edges("validate_request", lambda state: state["route"], routes)
    graph.add_edge("authorize_dispatch", "weather_investigation")
    graph.add_edge("authorize_dispatch", "ocean_investigation")
    graph.add_edge(["weather_investigation", "ocean_investigation"], "decide_next_action")
    graph.add_conditional_edges("decide_next_action", lambda state: state["route"], routes)
    graph.add_edge("finalize_investigation", END)
    trace_writable = True
    try:
        # Suppress remote tracing even if ambient SDK variables enable it.
        with tracing_context(enabled=False):
            await graph.compile().ainvoke(
                {"investigation": initial, "signals": (), "visited": ()},
                config={"recursion_limit": 32},
            )
    except Exception:
        reason = "TRACE_WRITE_FAILED" if trace_failed else "SKELETON_EXECUTION_FAILED"
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
    return SkeletonReport(current, budget.snapshot(), tuple(visited), trace_writable)
