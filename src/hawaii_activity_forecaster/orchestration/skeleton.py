"""Synthetic component graph for scoped investigation and trusted evaluation."""

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
    TimeRange, TraceEvent, RecommendationResult,
)
from hawaii_activity_forecaster.models.enums import (
    AgentType, InvestigationStatus, Outcome, TraceActor, TraceEventType,
)
from .budgets import BudgetManager, BudgetSnapshot
from .specialists import SpecialistContractError, SpecialistDelivery, SpecialistExchange
from .session import SessionRequest
from hawaii_activity_forecaster.harness.contracts import DriverInputs
from hawaii_activity_forecaster.harness.synthetic import DispatchBinding, SyntheticDriver
from hawaii_activity_forecaster.tools.synthetic import SyntheticToolDispatcher, ToolAction
from hawaii_activity_forecaster.harness.policy import PolicyConfiguration
from hawaii_activity_forecaster.validation import EvidenceValidationReport, validate_evidence
from hawaii_activity_forecaster.validation import SafetyEvaluationReport, evaluate_safety as evaluate_safety_policies
from hawaii_activity_forecaster.recommendations import (
    CandidateComparison, ResultContext, ResultValidationError, ResultValidationSnapshot, build_error_result, build_result,
    compare_candidates, validate_error_result, validate_result,
)


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
    evidence_report: EvidenceValidationReport | None = None
    safety_report: SafetyEvaluationReport | None = None
    comparison: CandidateComparison | None = None
    result: RecommendationResult | None = None
    result_validation: ResultValidationSnapshot | None = None
    # Without result_generation, state.result_id identifies only an operational stop.


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


def _initial(request: NormalizedRequest, candidates: tuple[str, ...], session_id: str,
             request_revision: int = 1) -> InvestigationState:
    now = datetime.now(timezone.utc)
    limits = InvestigationLimits()
    return InvestigationState(
        **request.model_dump(), investigation_id=str(uuid4()), session_id=session_id,
        schema_version="0.1", created_at=now, updated_at=now,
        status=InvestigationStatus.INITIALIZING, request_revision=request_revision,
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
    session_request: SessionRequest | None = None,
) -> SkeletonReport:
    """Traverse the graph with trusted synthetic callbacks only.

    Inputs are already normalized and candidates already selected. No agents,
    tools, evidence, safety decisions or public results are implemented here.
    Memory recorders are unit-test seams, not authoritative investigation traces.
    Recorder failures stop branch dispatch. Every run has fresh IDs and budgets;
    this API does not resume an investigation or accept previous graph state.
    """
    return await _run_graph(request, candidate_beach_ids=candidate_beach_ids, branch=branch,
                            record_event=record_event, session_id=session_id, session_request=session_request)


async def run_specialist_graph(
    request: NormalizedRequest, *, catalog: BeachCatalog, candidate_beach_ids: tuple[str, ...],
    plan: SpecialistPlanner, specialist: SyntheticSpecialist, record_event: EventRecorder,
    session_id: str | None = None,
    session_request: SessionRequest | None = None,
) -> SkeletonReport:
    """Probe approved specialist contracts with trusted synthetic callbacks.

    Planning receives a detached state snapshot. Specialists receive only their
    authorized request. The trusted join validates/merges deliveries, preserving
    valid sibling work. No tools, automatic retries or safety decisions execute.
    """
    return await _run_graph(
        request, candidate_beach_ids=candidate_beach_ids, record_event=record_event,
        session_id=session_id, session_request=session_request, catalog=catalog, plan=plan, specialist_callback=specialist,
    )


async def _run_graph(
    request, *, candidate_beach_ids, record_event, session_id=None, branch=None,
    catalog=None, plan=None, specialist_callback=None, driver_inputs=None, tool_plan=None, request_step=1,
    evidence_policy=None, safety_evaluation=False, result_generation=False,
    session_request=None,
) -> SkeletonReport:
    request = NormalizedRequest.model_validate(request.model_dump())
    if session_request is not None:
        session_request.check(request)
        if session_id is not None and session_id != session_request.session_id:
            raise ValueError("Conflicting session identities")
        session_id = session_request.session_id
    if catalog is not None:
        catalog = BeachCatalog.model_validate(catalog.model_dump())
    candidates = tuple(candidate_beach_ids)
    initial = _initial(request, candidates, session_id or str(uuid4()),
                       session_request.request_revision if session_request is not None else 1)
    budget = BudgetManager()
    current = initial
    visited: list[str] = []
    sequence = 0
    trace_id = str(uuid4())
    trace_failed = False
    exchange = SpecialistExchange(initial, catalog) if catalog is not None else None
    dispatcher = None
    evidence_report = None
    safety_report = None
    comparison = None
    result_context = None
    proposed_result = None
    validated_result = None
    published_result = None
    result_validation = None
    published_validation = None
    latest_contract_failure = False
    trusted_error_code = None
    if evidence_policy is not None:
        evidence_policy = PolicyConfiguration.model_validate(evidence_policy.model_dump())

    def emit(event_type: TraceEventType, *, related_ids=None, **details):
        nonlocal sequence, trace_failed
        if trace_failed:
            raise _TraceFailure("mandatory event recording failed")
        sequence += 1
        event = TraceEvent(
            event_id=str(uuid4()), trace_id=trace_id, sequence_number=sequence,
            timestamp=datetime.now(timezone.utc), event_type=event_type,
            actor=TraceActor.ORCHESTRATOR, request_revision=initial.request_revision,
            related_ids=related_ids,
            details={"investigation_id": initial.investigation_id, "session_id": initial.session_id, **details},
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
        emit(TraceEventType.INVESTIGATION_STARTED, component_probe=True, status=initial.status,
             iteration_count=initial.iteration_count, tool_call_count=initial.tool_call_count,
             retry_count=initial.retry_count, model_call_count=0, fallback_attempted=False)
        if session_request is not None:
            emit(TraceEventType.REQUEST_RECEIVED, original_request=request.original_request)
            if session_request.previous_investigation_id is not None:
                emit(TraceEventType.REQUEST_REVISED,
                     related_ids=[session_request.previous_investigation_id],
                     previous_investigation_id=session_request.previous_investigation_id,
                     previous_request_revision=initial.request_revision - 1,
                     changed_fields=list(session_request.changed_fields))
            emit(TraceEventType.REQUEST_NORMALIZED, normalized_request=request.model_dump(mode="json"),
                 user_provided_fields=sorted(session_request.user_provided_fields),
                 assumed_fields=sorted(session_request.assumed_fields))
        return visit("initialize_investigation")

    def validate(state: _GraphState):
        nonlocal current
        current = state["investigation"]
        update = visit("validate_request")
        if request.clarification_needed or request.activity is None or request.target_time_window is None:
            current = _updated(current, status=InvestigationStatus.AWAITING_CLARIFICATION,
                               clarification_needed=True)
            emit(TraceEventType.CLARIFICATION_REQUESTED, questions=current.clarification_questions)
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
        nonlocal current, safety_report
        snapshot = InvestigationState.model_validate(state["investigation"].model_dump())
        if evidence_policy is not None and snapshot.iteration_count == 0:
            # Validate the supplied configuration before any environmental call.
            # No findings exist yet, so this produces no observed-evidence events
            # or committed category/issue decisions.
            validate_evidence(snapshot, catalog=catalog, policy=evidence_policy, bindings=(),
                              reference_time=dispatcher.driver.reference_time(request_step), request_step=request_step)
        try:
            requests = tuple(SpecialistInvestigationRequest.model_validate(
                r.model_dump() if isinstance(r, SpecialistInvestigationRequest) else deepcopy(r),
            ) for r in plan(snapshot))
        except (ValidationError, ValueError, TypeError):
            emit(TraceEventType.CONTRACT_VALIDATED, contract="specialist_request", valid=False,
                 reason="REQUEST_SCHEMA_INVALID")
            raise SpecialistContractError("REQUEST_SCHEMA_INVALID") from None
        if not requests:
            reason = ("NO_FURTHER_ACTION" if result_generation else
                      "RESULT_VALIDATION_NOT_IMPLEMENTED" if safety_evaluation else "VALIDATORS_NOT_IMPLEMENTED")
            return {**visit("plan_evidence"), "route": "stop", "reason": reason}
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
        invalidated = []
        if safety_evaluation:
            invalidated = [a.assessment_id for a in proposed.assessments]
            proposed = _updated(proposed, assessments=[])
            safety_report = None
        emit(TraceEventType.CONTRACT_VALIDATED, contract="specialist_request", valid=True,
             request_ids=[r.request_id for r in requests], invalidated_assessment_ids=invalidated)
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
        nonlocal current, latest_contract_failure
        # Only this cycle's isolated outputs participate in its trusted join.
        deliveries = state["deliveries"][-len(state["requests"]):]
        report = exchange.merge(state["investigation"], deliveries,
                                now=datetime.now(timezone.utc))
        latest_contract_failure = bool(report.rejections)
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
                 response_id=rejection.response_id, reason=rejection.reason,
                 response_correlation=dict(rejection.response_correlation))
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
        if evidence_report is not None:
            more = (any(not candidate.mandatory_categories_covered for candidate in evidence_report.candidates)
                    or bool(evidence_report.conflicted_finding_ids))
        if safety_report is not None:
            more = any(a.eligibility == "NEEDS_INVESTIGATION" for a in safety_report.assessments)
        repeat = more and current.iteration_count < current.max_iterations
        boundary = ("ASSESSMENT_COMPLETE" if result_generation else
                    "RESULT_VALIDATION_NOT_IMPLEMENTED" if safety_evaluation else "VALIDATORS_NOT_IMPLEMENTED")
        reason = "ITERATION_LIMIT_REACHED" if more else boundary
        if more and not repeat:
            emit(TraceEventType.INVESTIGATION_LIMIT_REACHED, iteration=current.iteration_count)
        return {**visit("decide_next_action"), "investigation": current,
                "route": "dispatch" if repeat else "stop", "reason": reason}

    def evaluate_evidence(state: _GraphState):
        nonlocal current, evidence_report
        proposed = validate_evidence(
            _updated(state["investigation"], status=InvestigationStatus.EVALUATING),
            catalog=catalog, policy=evidence_policy, bindings=dispatcher.driver.bindings,
            reference_time=dispatcher.driver.reference_time(request_step), request_step=request_step,
            retrieval_gaps=dispatcher.gap_scopes,
        )
        for decision in proposed.decisions:
            event_type = (TraceEventType.EVIDENCE_REJECTED if decision.status == "REJECTED"
                          else TraceEventType.EVIDENCE_VALIDATED)
            emit(event_type, finding_id=decision.finding_id, rule_id=decision.rule_id,
                 beach_id=decision.beach_id, category=decision.category,
                 validation_status=decision.status, reasons=list(decision.reasons))
        if proposed.conflicted_finding_ids:
            emit(TraceEventType.EVIDENCE_CONFLICT_DETECTED, finding_ids=list(proposed.conflicted_finding_ids))
        current = proposed.state
        evidence_report = proposed
        return {**visit("validate_evidence"), "investigation": current}

    def assess_candidates(state: _GraphState):
        nonlocal current, safety_report
        if evidence_report is None or evidence_report.state != state["investigation"]:
            raise ValueError("Safety evaluation requires the current evidence snapshot")
        proposed = evaluate_safety_policies(
            evidence_report, catalog=catalog, policy=evidence_policy,
            bindings=dispatcher.driver.bindings, request_step=request_step,
        )
        for assessment in proposed.assessments:
            for result in assessment.policy_results:
                emit(TraceEventType.POLICY_EVALUATED, assessment_id=assessment.assessment_id,
                     beach_id=assessment.beach_id, policy_id=result.policy_id, result=result.result,
                     supporting_finding_ids=result.supporting_finding_ids)
            emit(TraceEventType.CANDIDATE_ASSESSED, assessment_id=assessment.assessment_id,
                 assessment_version=assessment.assessment_version, beach_id=assessment.beach_id,
                 eligibility=assessment.eligibility, evidence_quality=assessment.evidence_quality,
                 environmental_suitability=assessment.environmental_suitability)
            if assessment.eligibility in {"EXCLUDED", "ELIGIBLE"}:
                event = TraceEventType.CANDIDATE_EXCLUDED if assessment.eligibility == "EXCLUDED" else TraceEventType.CANDIDATE_ELIGIBLE
                emit(event, beach_id=assessment.beach_id, assessment_id=assessment.assessment_id,
                     disqualifying_policy_ids=assessment.disqualifying_policy_ids)
        current, safety_report = proposed.state, proposed
        return {**visit("evaluate_safety"), "investigation": current}

    def finalize(state: _GraphState):
        nonlocal current, published_result, published_validation
        budget.close()
        if dispatcher is not None:
            dispatcher.close()
        if exchange is not None:
            exchange.close()
        if result_generation:
            if validated_result is None:
                raise ResultValidationError("No validated result is available for finalization")
            terminal = {
                Outcome.RECOMMENDATIONS: (InvestigationStatus.COMPLETED, TraceEventType.INVESTIGATION_COMPLETED),
                Outcome.NO_RECOMMENDATION: (InvestigationStatus.ABSTAINED, TraceEventType.INVESTIGATION_ABSTAINED),
                Outcome.ERROR: (InvestigationStatus.FAILED, TraceEventType.INVESTIGATION_FAILED),
            }
            status, event = terminal[validated_result.outcome]
            proposed_state = _updated(state["investigation"], status=status, outcome=validated_result.outcome,
                                      result_id=validated_result.result_id, completion_reason="Validated " + validated_result.outcome.value)
            emit(event, result_id=validated_result.result_id, outcome=validated_result.outcome,
                 stop_reason=state["reason"], error_code=validated_result.error_code)
            current, published_result = proposed_state, validated_result
            published_validation = result_validation
            return {**visit("finalize_investigation"), "investigation": current}
        current = _updated(state["investigation"], status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                           result_id=str(uuid4()), completion_reason=state["reason"])
        emit(TraceEventType.INVESTIGATION_FAILED, reason=state["reason"])
        return {**visit("finalize_investigation"), "investigation": current}

    def compare(state: _GraphState):
        nonlocal result_context, comparison, trusted_error_code
        if evidence_report is None or safety_report is None:
            raise ResultValidationError("Current evidence and assessments are required for comparison")
        result_context = ResultContext(state["investigation"], evidence_report, safety_report, catalog,
                                       evidence_policy, dispatcher.driver.bindings, request_step)
        comparison = compare_candidates(result_context)
        # A handled provider response ERROR is not a contract rejection. An
        # unrecovered malformed/failed specialist boundary with no eligible
        # alternative is an operational error, not environmental abstention.
        trusted_error_code = ("INVESTIGATION_EXECUTION_FAILED" if latest_contract_failure
                              and not comparison.selected_assessment_ids else None)
        return visit("compare_candidates")

    def construct(state: _GraphState):
        nonlocal proposed_result
        generated_at = datetime.now(timezone.utc)
        proposed_result = (build_error_result(state["investigation"], generated_at=generated_at, error_code=trusted_error_code)
                           if trusted_error_code else build_result(result_context, generated_at=generated_at, stop_reason=state["reason"]))
        return visit("construct_result")

    def validate_output(state: _GraphState):
        nonlocal validated_result, result_validation
        if trusted_error_code:
            candidate = validate_error_result(proposed_result, state["investigation"], now=datetime.now(timezone.utc),
                                               error_code=trusted_error_code)
        else:
            candidate = validate_result(proposed_result, result_context, now=datetime.now(timezone.utc), stop_reason=state["reason"])
        emit(TraceEventType.RESULT_VALIDATED, result_id=candidate.result_id, outcome=candidate.outcome,
             assessment_ids=[r.assessment_id for r in candidate.recommendations])
        validated_result = candidate
        result_validation = ResultValidationSnapshot(
            InvestigationState.model_validate(state["investigation"].model_dump()), state["reason"], trusted_error_code, request_step,
        )
        return visit("validate_result")

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
    if result_generation:
        graph.add_node("compare_candidates", compare)
        graph.add_node("construct_result", construct)
        graph.add_node("validate_result", validate_output)
        routes["stop"] = "compare_candidates"
        graph.add_edge("compare_candidates", "construct_result")
        graph.add_edge("construct_result", "validate_result")
        graph.add_edge("validate_result", "finalize_investigation")
    if exchange is not None:
        graph.add_node("plan_evidence", plan_evidence)
        graph.add_node("validate_and_merge_specialist_responses", merge_responses)
        routes["dispatch"] = "plan_evidence"
        graph.add_conditional_edges("plan_evidence", lambda state: state["route"],
                                    {"authorize": "authorize_dispatch", "stop": routes["stop"]})
    graph.add_conditional_edges("validate_request", lambda state: state["route"], routes)
    graph.add_edge("authorize_dispatch", "weather_investigation")
    graph.add_edge("authorize_dispatch", "ocean_investigation")
    join = "validate_and_merge_specialist_responses" if exchange is not None else "decide_next_action"
    graph.add_edge(["weather_investigation", "ocean_investigation"], join)
    if exchange is not None:
        if evidence_policy is not None:
            graph.add_node("validate_evidence", evaluate_evidence)
            graph.add_edge(join, "validate_evidence")
            if safety_evaluation:
                graph.add_node("evaluate_safety", assess_candidates)
                graph.add_edge("validate_evidence", "evaluate_safety")
                graph.add_edge("evaluate_safety", "decide_next_action")
            else:
                graph.add_edge("validate_evidence", "decide_next_action")
        else:
            graph.add_edge(join, "decide_next_action")
    graph.add_conditional_edges("decide_next_action", lambda state: state["route"], routes)
    graph.add_edge("finalize_investigation", END)
    trace_writable = True
    try:
        # Suppress remote tracing even if ambient SDK variables enable it.
        with tracing_context(enabled=False):
            await graph.compile().ainvoke(
                {"investigation": initial, "signals": (), "visited": (), "deliveries": ()},
                config={"recursion_limit": initial.max_iterations * (7 if safety_evaluation else 6 if evidence_policy is not None else 5) + 8},
            )
    except Exception as error:
        reason = ("TRACE_WRITE_FAILED" if trace_failed else
                  "SPECIALIST_CONTRACT_FAILED" if isinstance(error, SpecialistContractError) else
                  "RESULT_VALIDATION_FAILED" if result_generation and isinstance(error, ResultValidationError) else
                  "INVESTIGATION_EXECUTION_FAILED" if result_generation else
                  "SKELETON_EXECUTION_FAILED")
        trace_writable = not trace_failed
        budget.close()
        if safety_evaluation:
            current = _updated(current, assessments=[])
            safety_report = None
        counts = budget.snapshot()
        current = _updated(current, tool_call_count=counts.tool_calls, retry_count=counts.retries,
                           fallback_attempted=bool(counts.fallbacks))
        published_result = None
        published_validation = None
        candidate_error = None
        candidate_validation = None
        try:
            if result_generation and trace_writable and current.activity is not None and current.target_time_window is not None:
                code = "RESULT_VALIDATION_FAILED" if isinstance(error, ResultValidationError) else "INVESTIGATION_EXECUTION_FAILED"
                candidate_error = build_error_result(current, generated_at=datetime.now(timezone.utc), error_code=code)
                candidate_error = validate_error_result(candidate_error, current, now=datetime.now(timezone.utc), error_code=code)
                candidate_validation = ResultValidationSnapshot(
                    InvestigationState.model_validate(current.model_dump()), None, code, request_step,
                )
                emit(TraceEventType.RESULT_VALIDATED, result_id=candidate_error.result_id, outcome=candidate_error.outcome,
                     assessment_ids=[])
            failed_state = _updated(current, status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                                    result_id=candidate_error.result_id if candidate_error else str(uuid4()), completion_reason=reason)
            if trace_writable:
                emit(TraceEventType.INVESTIGATION_FAILED, reason=reason, result_id=failed_state.result_id,
                     error_code=candidate_error.error_code if candidate_error else None)
            current, published_result = failed_state, candidate_error
            published_validation = candidate_validation
        except _TraceFailure:
            trace_writable = False
            current = _updated(current, status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                               result_id=str(uuid4()), completion_reason="TRACE_WRITE_FAILED")
        except ResultValidationError:
            # An incomplete request cannot be forced into the result schema by
            # inventing its activity/window. Keep only the operational diagnostic.
            current = _updated(current, status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                               result_id=str(uuid4()), completion_reason=reason)
            if trace_writable:
                try:
                    emit(TraceEventType.INVESTIGATION_FAILED, reason=reason, result_id=current.result_id)
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
                          dispatcher.driver.bindings if dispatcher is not None else (), evidence_report, safety_report,
                          comparison, published_result, published_validation)


async def run_synthetic_tool_graph(
    request: NormalizedRequest, *, catalog: BeachCatalog, candidate_beach_ids: tuple[str, ...],
    plan: SpecialistPlanner, tool_plan: Callable[[SpecialistInvestigationRequest], tuple[ToolAction, ...]],
    driver_inputs: DriverInputs, record_event: EventRecorder, session_id: str | None = None,
    request_step: int = 1,
    evidence_policy: PolicyConfiguration | None = None,
    safety_evaluation: bool = False,
    result_generation: bool = False,
    session_request: SessionRequest | None = None,
) -> SkeletonReport:
    """Execute explicitly planned synthetic retrievals; never an acceptance run.

    Driver inputs stay in the trusted layer; planners receive no script/oracle.
    Optional evidence_policy enables independent synthetic validation; the
    safety_evaluation flag additionally creates trusted Candidate Assessments.
    result_generation additionally validates controlled synthetic outcomes.
    Optional session admission carries a revision into fresh IDs and budgets;
    it never accepts previous graph state. Authoritative JSONL and full acceptance
    remain deferred. The CLI exposes explicit synthetic component demos only.
    """
    if type(request_step) is not int or not 1 <= request_step <= len(driver_inputs.script.requests):
        raise ValueError("Invalid synthetic request step")
    if type(safety_evaluation) is not bool or (safety_evaluation and evidence_policy is None):
        raise ValueError("Safety evaluation requires an explicit evidence policy and boolean flag")
    if type(result_generation) is not bool or (result_generation and not safety_evaluation):
        raise ValueError("Result generation requires explicit safety evaluation and a boolean flag")
    return await _run_graph(
        request, candidate_beach_ids=candidate_beach_ids, catalog=catalog, plan=plan,
        tool_plan=tool_plan, driver_inputs=driver_inputs, request_step=request_step,
        record_event=record_event, session_id=session_id, session_request=session_request,
        evidence_policy=evidence_policy,
        safety_evaluation=safety_evaluation,
        result_generation=result_generation,
    )
