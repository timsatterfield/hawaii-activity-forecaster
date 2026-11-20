"""Synthetic component graph for scoped investigation and trusted evaluation."""

from collections.abc import Awaitable, Callable
from asyncio import wait_for
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from inspect import isawaitable
import json
from operator import add
from pathlib import Path
from typing import Annotated, TypedDict
from uuid import uuid4

from pydantic import ValidationError

from langgraph.graph import END, START, StateGraph
from langsmith.run_helpers import tracing_context

from hawaii_activity_forecaster.config import load_config
from hawaii_activity_forecaster.config.settings import ExecutionTimeouts, InvestigationLimits, TraceSettings
from hawaii_activity_forecaster.observability import (
    JsonlTraceWriter, TraceValidation, TraceValidationError, TraceWriteError, inspect_trace,
)
from hawaii_activity_forecaster.models import (
    BeachCatalog, InvestigationState, NormalizedRequest, SpecialistInvestigationRequest,
    TimeRange, TraceEvent, RecommendationResult,
)
from hawaii_activity_forecaster.models.enums import (
    AgentType, InvestigationStatus, Outcome, TraceActor, TraceEventType,
)
from hawaii_activity_forecaster.observability.failure_codes import agent_failure_code, request_failure_code
from .budgets import BudgetManager, BudgetSnapshot
from .specialists import SpecialistContractError, SpecialistDelivery, SpecialistExchange
from .session import RawSessionRequest, SessionRequest
from .model_calls import ComponentModelCalls, SyntheticModelAdapter
from hawaii_activity_forecaster.interpretation import (
    CandidateSelection, RequestContext, ValidatedRequest, select_candidates, validate_request, verify_request, verify_selection,
)
from hawaii_activity_forecaster.interpretation.validation import interpreter_input
from hawaii_activity_forecaster.harness.contracts import DriverInputs
from hawaii_activity_forecaster.harness.synthetic import DispatchBinding, SyntheticDriver
from hawaii_activity_forecaster.tools.synthetic import SyntheticToolDispatcher, ToolAction, ToolPlanError
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
    request_context: RequestContext | None = None
    request_receipt: ValidatedRequest | None = None
    selection: CandidateSelection | None = None
    trace_path: Path | None = None
    trace_validation: TraceValidation | None = None
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


@dataclass(frozen=True)
class RawPlanningInput:
    """Detached planner state and trusted dispatch scope for a raw component run."""

    state: InvestigationState
    investigation_candidate_ids: tuple[str, ...]
    planning_order: tuple[str, ...]
    models: ComponentModelCalls
    budgets: BudgetSnapshot | None = None


class _TraceFailure(RuntimeError):
    pass


def _updated(state: InvestigationState, **changes) -> InvestigationState:
    # Rebuild because model_copy(update=...) skips validation.
    return InvestigationState.model_validate({
        **state.model_dump(), **changes, "updated_at": datetime.now(timezone.utc),
    })


def _initial(request: NormalizedRequest, candidates: tuple[str, ...], session_id: str,
             request_revision: int = 1, investigation_id: str | None = None) -> InvestigationState:
    now = datetime.now(timezone.utc)
    limits = InvestigationLimits()
    return InvestigationState(
        **request.model_dump(), investigation_id=investigation_id or str(uuid4()), session_id=session_id,
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
    session_request=None, raw_admission=None, interpreter=None, model_adapter=None,
    trace_settings=None,
    provider_adapter=None, agent_runtime=False,
) -> SkeletonReport:
    if record_event is not None and trace_settings is not None:
        raise ValueError("Choose authoritative local tracing or an explicit component recorder")
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
                       raw_admission.request_revision if raw_admission else
                       session_request.request_revision if session_request is not None else 1,
                       raw_admission.investigation_id if raw_admission else None)
    budget = BudgetManager()
    current = initial
    visited: list[str] = []
    sequence = 0
    trace_id = str(uuid4())
    trace_failed = False
    trace_failure_reason = "TRACE_WRITE_FAILED"
    local_trace = None
    trace_validation = None
    exchange = SpecialistExchange(initial, catalog) if catalog is not None and raw_admission is None else None
    request_context = raw_admission.context if raw_admission else None
    request_receipt = None
    selection = None
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
        counts = budget.snapshot()
        actor = TraceActor.ORCHESTRATOR
        if event_type in {TraceEventType.CONTRACT_VALIDATED, TraceEventType.EVIDENCE_RECEIVED,
                          TraceEventType.EVIDENCE_VALIDATED, TraceEventType.EVIDENCE_REJECTED,
                          TraceEventType.EVIDENCE_CONFLICT_DETECTED, TraceEventType.POLICY_EVALUATED,
                          TraceEventType.CANDIDATE_ASSESSED, TraceEventType.CANDIDATE_EXCLUDED,
                          TraceEventType.CANDIDATE_ELIGIBLE, TraceEventType.RESULT_VALIDATED}:
            actor = TraceActor.VALIDATOR
        if event_type in {TraceEventType.AGENT_STARTED, TraceEventType.AGENT_COMPLETED, TraceEventType.AGENT_FAILED,
                          TraceEventType.TOOL_CALLED, TraceEventType.TOOL_COMPLETED, TraceEventType.TOOL_FAILED,
                          TraceEventType.RETRY_INITIATED, TraceEventType.FALLBACK_INITIATED}:
            actor = TraceActor(details["agent_type"])
        event = TraceEvent(
            event_id=str(uuid4()), trace_id=trace_id, sequence_number=sequence,
            timestamp=datetime.now(timezone.utc), event_type=event_type,
            actor=actor, request_revision=initial.request_revision,
            related_ids=related_ids,
            details={"investigation_id": initial.investigation_id, "session_id": initial.session_id,
                     "model_call_count": counts.model_calls, "tool_call_count": counts.tool_calls,
                     "iteration_count": counts.iterations, "retry_count": counts.retries,
                     "fallback_count": counts.fallbacks, **details},
        )
        try:
            if local_trace is not None:
                local_trace.append(event)
            else:
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

    driver = SyntheticDriver(driver_inputs) if driver_inputs is not None else None

    def evidence_reference():
        return request_context.reference_time if request_context else driver.reference_time(request_step)

    def tool_dispatcher(scope=None):
        return SyntheticToolDispatcher(
            driver, budget, investigation_id=initial.investigation_id, request_revision=initial.request_revision,
            reference_time=evidence_reference(), emit=emit, request_step=request_step,
            investigation_candidate_ids=scope,
        )

    if provider_adapter is not None:
        from hawaii_activity_forecaster.model_runtime.gateway import ModelGateway
        from hawaii_activity_forecaster.model_runtime.contracts import InvocationIdentity
        model_metadata = dict(provider=provider_adapter.provider_name, model_identifier=provider_adapter.model_identifier,
                              profile_id=provider_adapter.profile_id,
                              execution_mode=provider_adapter.execution_mode)
        identity = InvocationIdentity(session_id=initial.session_id, investigation_id=initial.investigation_id,
                                      request_revision=initial.request_revision)
        models = ModelGateway(identity=identity, budget=budget, adapter=provider_adapter, emit=emit,
            is_current=lambda value: (value.investigation_id == current.investigation_id
                and value.request_revision == current.request_revision
                and current.status not in {"COMPLETED", "ABSTAINED", "FAILED"}))
    else:
        model_metadata = None
        models = ComponentModelCalls(model_adapter, budget, emit)
    if driver is not None and raw_admission is None:
        dispatcher = tool_dispatcher()
        specialist_callback = dispatcher.run

    def initialize(state: _GraphState):
        nonlocal local_trace, trace_failed
        if record_event is None:
            try:
                settings = trace_settings if trace_settings is not None else load_config().trace
                local_trace = JsonlTraceWriter(settings, trace_id=trace_id, investigation_id=initial.investigation_id,
                                               session_id=initial.session_id, request_revision=initial.request_revision)
            except Exception:
                trace_failed = True
                budget.close()
                raise _TraceFailure("mandatory trace startup failed") from None
        emit(TraceEventType.INVESTIGATION_STARTED,
             component_probe=not agent_runtime or provider_adapter.execution_mode == "OFFLINE_TRANSPORT", status=initial.status,
             iteration_count=initial.iteration_count, tool_call_count=initial.tool_call_count,
             retry_count=initial.retry_count, model_call_count=0, fallback_attempted=False,
             trace_metadata=dict(schema_version=initial.schema_version, configuration_version="0.1",
                                 policy_version=evidence_policy.policy_version if evidence_policy else "not-applied",
                                 model_identifier=model_metadata["model_identifier"] if model_metadata else None),
             configuration=dict(limits=InvestigationLimits().model_dump(), timeouts=ExecutionTimeouts().model_dump(),
                                environment_mode="synthetic", remote_tracing_enabled=False,
                                policy_configuration_version=evidence_policy.policy_configuration_version if evidence_policy else None,
                                **({"model_profile": model_metadata} if model_metadata else {})),
             candidate_beach_ids=list(initial.candidate_beach_ids), raw_payloads_retained=False)
        if raw_admission is not None:
            emit(TraceEventType.REQUEST_RECEIVED, original_request=request.original_request,
                 reference_time=request_context.reference_time.isoformat(), rule_profile=request_context.rule_profile)
            if raw_admission.previous_investigation_id is not None:
                emit(TraceEventType.REQUEST_REVISED, related_ids=[raw_admission.previous_investigation_id],
                     previous_investigation_id=raw_admission.previous_investigation_id,
                     previous_request_revision=initial.request_revision - 1,
                     prior_status=raw_admission.prior_status)
        elif session_request is not None:
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
        elif local_trace is not None:
            emit(TraceEventType.REQUEST_RECEIVED, original_request=request.original_request)
            emit(TraceEventType.REQUEST_NORMALIZED, normalized_request=request.model_dump(mode="json"),
                 user_provided_fields=[], assumed_fields=[])
        return visit("initialize_investigation")

    def terminal_details(snapshot, result=None):
        stats = budget.snapshot()
        return dict(final_status=snapshot.status.value, outcome=snapshot.outcome.value,
                    result_id=snapshot.result_id, completion_reason=snapshot.completion_reason,
                    recommended_beach_ids=[r.beach_id for r in result.recommendations] if result else [],
                    recommendation_count=len(result.recommendations) if result else 0,
                    no_recommendation_reason=result.no_recommendation_reason if result else None,
                    candidate_beach_ids=list(snapshot.candidate_beach_ids),
                    total_iterations=stats.iterations, total_tool_calls=stats.tool_calls,
                    total_model_calls=stats.model_calls, total_retries=stats.retries, total_fallbacks=stats.fallbacks,
                    total_duration_ms=max(0, int((datetime.now(timezone.utc) - initial.created_at).total_seconds() * 1000)))

    def audit_local(snapshot, result=None):
        nonlocal trace_validation, trace_failed, trace_failure_reason
        if local_trace is None:
            return
        try:
            local_trace.close()
            trace_validation = inspect_trace(
                local_trace.path, state=snapshot, result=result, budgets=budget.snapshot(),
                bindings=dispatcher.driver.bindings if dispatcher else (), evidence=evidence_report, safety=safety_report,
            )
        except TraceWriteError:
            trace_failed = True
            raise _TraceFailure("mandatory trace close failed") from None
        except TraceValidationError:
            trace_failed = True
            trace_failure_reason = "TRACE_VALIDATION_FAILED"
            raise _TraceFailure("mandatory trace validation failed") from None

    async def normalize_raw(state: _GraphState):
        nonlocal current, request, request_receipt
        visit("normalize_request")
        inputs = interpreter_input(request_context)
        try:
            if provider_adapter is not None:
                proposal = (await models.invoke("normalize_request", inputs)).to_interpretation()
            else:
                proposal = (await models.invoke("normalize_request", inputs) if model_adapter is not None
                            else interpreter(inputs))
            receipt = verify_request(validate_request(proposal, request_context), request_context)
        except Exception as error:
            if not trace_failed:
                emit(TraceEventType.CONTRACT_VALIDATED, contract="request_interpretation", valid=False,
                     reason="REQUEST_NORMALIZATION_FAILED", error_code=request_failure_code(error))
            raise
        proposed = _updated(state["investigation"], **receipt.request.model_dump())
        emit(TraceEventType.CONTRACT_VALIDATED, contract="request_interpretation", valid=True,
             context_digest=receipt.context_digest)
        emit(TraceEventType.REQUEST_NORMALIZED, normalized_request=receipt.request.model_dump(mode="json"),
             reference_time=request_context.reference_time.isoformat(), rule_profile=request_context.rule_profile,
             context_digest=receipt.context_digest, origins=[json.loads(json.dumps(asdict(o))) for o in receipt.origins],
             changed_fields=list(receipt.changed_fields), user_provided_fields=sorted(receipt.user_provided_fields),
             assumed_fields=sorted(receipt.assumed_fields), limitations=list(receipt.limitations))
        current, request, request_receipt = proposed, receipt.request, receipt
        return {"investigation": current, "visited": ("normalize_request",)}

    def select_raw(state: _GraphState):
        nonlocal current, candidates, selection, exchange, dispatcher, specialist_callback
        update = visit("select_candidates")
        if request.clarification_needed:
            return update
        audit = verify_selection(select_candidates(request_receipt, request_context), request_receipt, request_context)
        proposed = _updated(state["investigation"], candidate_beach_ids=list(audit.assessment_candidate_ids),
                            remaining_candidate_ids=list(audit.planning_order))
        emit(TraceEventType.CONTRACT_VALIDATED, contract="candidate_selection", valid=True,
             **json.loads(json.dumps(asdict(audit))))
        current, candidates, selection = proposed, audit.assessment_candidate_ids, audit
        exchange = SpecialistExchange(current, catalog, investigation_candidate_ids=audit.investigation_candidate_ids)
        dispatcher = tool_dispatcher(audit.investigation_candidate_ids)
        specialist_callback = dispatcher.run
        return {**update, "investigation": current}

    def validate(state: _GraphState):
        nonlocal current
        current = state["investigation"]
        update = visit("validate_request")
        if request.clarification_needed or request.activity is None or request.target_time_window is None:
            current = _updated(current, status=InvestigationStatus.AWAITING_CLARIFICATION,
                               clarification_needed=True)
            emit(TraceEventType.CLARIFICATION_REQUESTED, questions=current.clarification_questions)
            return {**update, "investigation": current, "route": "end"}
        if selection is not None and not selection.investigation_candidate_ids:
            current = _updated(current, status=InvestigationStatus.EVALUATING)
            return {**update, "investigation": current, "route": "assess_stop", "reason": "NO_SUPPORTED_CANDIDATES"}
        if not candidates:
            return {**update, "route": "stop", "reason": "NO_SELECTED_CANDIDATES"}
        current = _updated(current, status=InvestigationStatus.INVESTIGATING)
        return {**update, "investigation": current, "route": "dispatch"}

    def authorize(state: _GraphState):
        nonlocal current
        iteration = budget.snapshot().iterations if agent_runtime else budget.begin_iteration()
        current = _updated(state["investigation"], status=InvestigationStatus.INVESTIGATING,
                           iteration_count=iteration)
        return {**visit("authorize_dispatch"), "investigation": current}

    async def plan_evidence(state: _GraphState):
        nonlocal current, safety_report
        snapshot = InvestigationState.model_validate(state["investigation"].model_dump())
        if evidence_policy is not None and snapshot.iteration_count == 0:
            # Validate the supplied configuration before any environmental call.
            # No findings exist yet, so this produces no observed-evidence events
            # or committed category/issue decisions.
            validate_evidence(snapshot, catalog=catalog, policy=evidence_policy, bindings=(),
                              reference_time=evidence_reference(), request_step=request_step)
        if agent_runtime:
            snapshot = _updated(snapshot, iteration_count=budget.begin_iteration())
            current = snapshot
            state = {**state, "investigation": snapshot}
        try:
            planned = plan(RawPlanningInput(snapshot, selection.investigation_candidate_ids,
                                           selection.planning_order, models, budget.snapshot())) if raw_admission else plan(snapshot)
            if isawaitable(planned):
                planned = await planned
            requests = tuple(SpecialistInvestigationRequest.model_validate(
                r.model_dump() if isinstance(r, SpecialistInvestigationRequest) else deepcopy(r),
            ) for r in planned)
        except (ValidationError, ValueError, TypeError):
            emit(TraceEventType.CONTRACT_VALIDATED, contract="specialist_request", valid=False,
                 reason="REQUEST_SCHEMA_INVALID")
            raise SpecialistContractError("REQUEST_SCHEMA_INVALID") from None
        if not requests:
            if dispatcher is not None and evidence_report is not None and safety_report is not None:
                needs = {a.beach_id for a in safety_report.assessments if a.eligibility == "NEEDS_INVESTIGATION"}
                missing = {(c.beach_id, category.category) for c in evidence_report.candidates
                           for category in c.categories if category.priority == "MANDATORY" and not category.covered}
                for gap in dispatcher.exhausted_recovery_gaps:
                    if any(beach in needs and (beach, gap.category) in missing for beach in gap.candidate_beach_ids):
                        emit(TraceEventType.INVESTIGATION_LIMIT_REACHED, budget_kind="fallback_per_evidence_gap",
                             configured_limit=InvestigationLimits().max_fallback_attempts_per_evidence_gap,
                             gap_id=gap.gap_id, category=gap.category, candidate_beach_ids=list(gap.candidate_beach_ids),
                             reason="FALLBACK_ALLOWANCE_EXHAUSTED_WITH_UNRESOLVED_EVIDENCE")
            reason = ("NO_FURTHER_ACTION" if result_generation else
                      "RESULT_VALIDATION_NOT_IMPLEMENTED" if safety_evaluation else "VALIDATORS_NOT_IMPLEMENTED")
            return {**visit("plan_evidence"), "investigation": current,
                    "route": "assess_stop" if raw_admission else "stop", "reason": reason}
        try:
            proposed = exchange.authorize(state["investigation"], requests, now=datetime.now(timezone.utc))
            if dispatcher is not None and not agent_runtime:
                for scoped in requests:
                    detached = SpecialistInvestigationRequest.model_validate(scoped.model_dump())
                    dispatcher.register(scoped, tuple(tool_plan(detached)))
        except SpecialistContractError as error:
            emit(TraceEventType.CONTRACT_VALIDATED, contract="specialist_request", valid=False,
                 reason=str(error), request_ids=[r.request_id for r in requests])
            raise
        except ToolPlanError:
            emit(TraceEventType.CONTRACT_VALIDATED, contract="tool_plan", valid=False,
                 reason="TOOL_PLAN_INVALID", request_ids=[r.request_id for r in requests])
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
            started = datetime.now(timezone.utc)
            correlation = dict(request_id=scoped_request.request_id if scoped_request else f"{role.value}-component-{snapshot.iteration_count}",
                               attempt_number=scoped_request.attempt_number if scoped_request else 1,
                               agent_type=role.value)
            emit(TraceEventType.AGENT_STARTED, **correlation, iteration=snapshot.iteration_count,
                 candidate_beach_ids=list(scoped_request.candidate_beach_ids) if scoped_request else list(candidates),
                 requested_evidence=[r.model_dump(mode="json") for r in scoped_request.requested_evidence] if scoped_request else [],
                 target_time_window=snapshot.target_time_window.model_dump(mode="json"))
            if exchange is not None:
                detached = SpecialistInvestigationRequest.model_validate(scoped_request.model_dump())
                try:
                    if agent_runtime:
                        actions = await tool_plan(detached, models, budget.snapshot())
                        dispatcher.register(detached, actions)
                    if scoped_request.deadline_at is None:
                        response = await specialist_callback(detached)
                    else:
                        seconds = (scoped_request.deadline_at - datetime.now(timezone.utc)).total_seconds()
                        if seconds <= 0:
                            raise TimeoutError("delegation expired before dispatch")
                        response = await wait_for(specialist_callback(detached), timeout=seconds)
                    # Capture now; callbacks may retain and later mutate their own payload.
                    response = deepcopy(response)
                except Exception as error:
                    emit(TraceEventType.AGENT_FAILED, **correlation, execution_status="ERROR",
                         error_code=agent_failure_code(error),
                         duration_ms=max(0, int((datetime.now(timezone.utc) - started).total_seconds() * 1000)))
                    # Let the native parallel join collect both outcomes before
                    # terminating. Raising here can strand a sibling's completed
                    # response without its required contract-validation event.
                    delivery = SpecialistDelivery(scoped_request.request_id, scoped_request.attempt_number,
                                                  execution_failed=True)
                else:
                    valid_response = response if isinstance(response, dict) else (
                        response.model_dump(mode="json") if hasattr(response, "model_dump") else {})
                    reported_status = valid_response.get("status") if isinstance(valid_response, dict) else None
                    emit(TraceEventType.AGENT_COMPLETED, **correlation,
                         execution_status=reported_status if isinstance(reported_status, str) and reported_status in
                         {"SUCCESS", "PARTIAL", "UNAVAILABLE", "ERROR"} else "UNVALIDATED",
                         missing_evidence_count=len(valid_response.get("unresolved_gaps", []))
                         if isinstance(valid_response.get("unresolved_gaps"), list) else 0,
                         duration_ms=max(0, int((datetime.now(timezone.utc) - started).total_seconds() * 1000)))
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
            emit(TraceEventType.AGENT_COMPLETED, **correlation, iteration=snapshot.iteration_count,
                 execution_status="SUCCESS", duration_ms=max(0, int((datetime.now(timezone.utc) - started).total_seconds() * 1000)))
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
                 finding_ids=sorted(f.finding_id for f in report.state.weather_findings + report.state.ocean_findings),
                 validation_status="PENDING")
        stats = budget.snapshot()
        current = _updated(report.state, tool_call_count=stats.tool_calls, retry_count=stats.retries,
                           fallback_attempted=bool(stats.fallbacks))
        if agent_runtime and latest_contract_failure:
            raise SpecialistContractError("AGENT_EXECUTION_FAILED")
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
        if agent_runtime:
            stats = budget.snapshot()
            repeat = current.iteration_count < current.max_iterations and stats.model_calls < 12 and not stats.closed
            if stats.model_calls >= 12:
                emit(TraceEventType.INVESTIGATION_LIMIT_REACHED, budget_kind="model", configured_limit=12)
        boundary = ("ASSESSMENT_COMPLETE" if result_generation else
                    "RESULT_VALIDATION_NOT_IMPLEMENTED" if safety_evaluation else "VALIDATORS_NOT_IMPLEMENTED")
        at_iteration_limit = current.iteration_count >= current.max_iterations
        reason = ("ITERATION_LIMIT_REACHED" if more and at_iteration_limit else
                  "NO_FURTHER_ACTION" if agent_runtime and more and not repeat else boundary)
        if more and not repeat and at_iteration_limit:
            emit(TraceEventType.INVESTIGATION_LIMIT_REACHED, iteration=current.iteration_count,
                 budget_kind="coordinator_iterations", configured_limit=current.max_iterations)
        return {**visit("decide_next_action"), "investigation": current,
                "route": "dispatch" if repeat else "stop", "reason": reason}

    def evaluate_evidence(state: _GraphState):
        nonlocal current, evidence_report
        proposed = validate_evidence(
            _updated(state["investigation"], status=InvestigationStatus.EVALUATING),
            catalog=catalog, policy=evidence_policy, bindings=dispatcher.driver.bindings,
            reference_time=evidence_reference(), request_step=request_step,
            retrieval_gaps=dispatcher.gap_scopes,
        )
        for decision in proposed.decisions:
            event_type = (TraceEventType.EVIDENCE_REJECTED if decision.status == "REJECTED"
                          else TraceEventType.EVIDENCE_VALIDATED)
            finding = next(f for f in proposed.state.weather_findings + proposed.state.ocean_findings
                           if f.finding_id == decision.finding_id)
            emit(event_type, related_ids=[decision.finding_id], finding_id=decision.finding_id, rule_id=decision.rule_id,
                 beach_id=decision.beach_id, category=decision.category,
                 validation_status=decision.status, reasons=list(decision.reasons), valid=decision.status != "REJECTED",
                 validation_rule_ids=[decision.rule_id] if decision.rule_id else [], validation_reasons=list(decision.reasons),
                 source_id=finding.source_id, coverage_type=finding.coverage_type, coverage_id=finding.coverage_id,
                 retrieved_at=finding.retrieved_at.isoformat(), issued_at=finding.issued_at.isoformat() if finding.issued_at else None,
                 observed_at=finding.observed_at.isoformat() if finding.observed_at else None,
                 valid_from=finding.valid_from.isoformat() if finding.valid_from else None,
                 valid_until=finding.valid_until.isoformat() if finding.valid_until else None)
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
                     activity=assessment.activity, explanation=result.explanation,
                     supporting_finding_ids=result.supporting_finding_ids)
            emit(TraceEventType.CANDIDATE_ASSESSED, assessment_id=assessment.assessment_id,
                 assessment_version=assessment.assessment_version, beach_id=assessment.beach_id,
                 eligibility=assessment.eligibility, evidence_quality=assessment.evidence_quality,
                 environmental_suitability=assessment.environmental_suitability, activity=assessment.activity,
                 applied_policy_ids=[r.policy_id for r in assessment.policy_results],
                 decision_reasons=list(assessment.decision_reasons),
                 disqualifying_policy_ids=list(assessment.disqualifying_policy_ids),
                 unresolved_policy_ids=list(assessment.unresolved_policy_ids),
                 recommended_next_actions=list(assessment.recommended_next_actions))
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
            emit(event, **terminal_details(proposed_state, validated_result),
                 stop_reason=state["reason"], error_code=validated_result.error_code)
            proposed_state = _updated(proposed_state)
            audit_local(proposed_state, validated_result)
            current, published_result = proposed_state, validated_result
            published_validation = result_validation
            return {**visit("finalize_investigation"), "investigation": current}
        current = _updated(state["investigation"], status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                           result_id=str(uuid4()), completion_reason=state["reason"])
        emit(TraceEventType.INVESTIGATION_FAILED, **terminal_details(current), reason=state["reason"])
        current = _updated(current)
        audit_local(current)
        return {**visit("finalize_investigation"), "investigation": current}

    def compare(state: _GraphState):
        nonlocal result_context, comparison, trusted_error_code
        if evidence_report is None or safety_report is None:
            raise ResultValidationError("Current evidence and assessments are required for comparison")
        result_context = ResultContext(state["investigation"], evidence_report, safety_report, catalog,
                                       evidence_policy, dispatcher.driver.bindings, request_step,
                                       request_context, request_receipt, selection)
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
        proposed_result = (build_error_result(state["investigation"], generated_at=generated_at, error_code=trusted_error_code,
                                             request_context=request_context, request_receipt=request_receipt)
                           if trusted_error_code else build_result(result_context, generated_at=generated_at, stop_reason=state["reason"]))
        return visit("construct_result")

    def validate_output(state: _GraphState):
        nonlocal validated_result, result_validation
        try:
            if trusted_error_code:
                candidate = validate_error_result(proposed_result, state["investigation"], now=datetime.now(timezone.utc),
                                                   error_code=trusted_error_code,
                                                   request_context=request_context, request_receipt=request_receipt)
            else:
                candidate = validate_result(proposed_result, result_context, now=datetime.now(timezone.utc), stop_reason=state["reason"])
        except ResultValidationError:
            emit(TraceEventType.RESULT_VALIDATED, result_id=proposed_result.result_id, valid=False,
                 error_code="RESULT_VALIDATION_FAILED", assessment_ids=[])
            raise
        emit(TraceEventType.RESULT_VALIDATED, result_id=candidate.result_id, outcome=candidate.outcome, valid=True,
             assessment_ids=[r.assessment_id for r in candidate.recommendations])
        validated_result = candidate
        result_validation = ResultValidationSnapshot(
            InvestigationState.model_validate(state["investigation"].model_dump()), state["reason"], trusted_error_code, request_step,
            authoritative_trace=local_trace is not None,
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
    if raw_admission:
        graph.add_node("normalize_request", normalize_raw)
        graph.add_node("select_candidates", select_raw)
        graph.add_edge("initialize_investigation", "normalize_request")
        graph.add_edge("normalize_request", "select_candidates")
        graph.add_edge("select_candidates", "validate_request")
    else:
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
    if catalog is not None:
        graph.add_node("plan_evidence", plan_evidence)
        graph.add_node("validate_and_merge_specialist_responses", merge_responses)
        routes["dispatch"] = "plan_evidence"
        graph.add_conditional_edges("plan_evidence", lambda state: state["route"],
                                    {"authorize": "authorize_dispatch", "stop": routes["stop"],
                                     **({"assess_stop": "validate_evidence"} if raw_admission else {})})
    if raw_admission:
        routes["assess_stop"] = "validate_evidence"
    graph.add_conditional_edges("validate_request", lambda state: state["route"], routes)
    graph.add_edge("authorize_dispatch", "weather_investigation")
    graph.add_edge("authorize_dispatch", "ocean_investigation")
    join = "validate_and_merge_specialist_responses" if catalog is not None else "decide_next_action"
    graph.add_edge(["weather_investigation", "ocean_investigation"], join)
    if catalog is not None:
        if evidence_policy is not None:
            graph.add_node("validate_evidence", evaluate_evidence)
            graph.add_edge(join, "validate_evidence")
            if safety_evaluation:
                graph.add_node("evaluate_safety", assess_candidates)
                graph.add_edge("validate_evidence", "evaluate_safety")
                graph.add_conditional_edges("evaluate_safety", lambda state: (
                    "stop" if raw_admission and state.get("route") == "assess_stop" else "decide"),
                    {"stop": routes["stop"], "decide": "decide_next_action"})
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
                config={"recursion_limit": initial.max_iterations * (7 if safety_evaluation else 6 if evidence_policy is not None else 5)
                        + 8 + (2 if raw_admission else 0)},
            )
    except Exception as error:
        reason = (trace_failure_reason if trace_failed else
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
                candidate_error = build_error_result(current, generated_at=datetime.now(timezone.utc), error_code=code,
                                                     request_context=request_context, request_receipt=request_receipt)
                candidate_error = validate_error_result(candidate_error, current, now=datetime.now(timezone.utc), error_code=code,
                                                        request_context=request_context, request_receipt=request_receipt)
                candidate_validation = ResultValidationSnapshot(
                    InvestigationState.model_validate(current.model_dump()), None, code, request_step,
                    authoritative_trace=local_trace is not None,
                )
                emit(TraceEventType.RESULT_VALIDATED, result_id=candidate_error.result_id, outcome=candidate_error.outcome,
                     assessment_ids=[], valid=True)
            failed_state = _updated(current, status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                                    result_id=candidate_error.result_id if candidate_error else str(uuid4()), completion_reason=reason)
            if trace_writable:
                emit(TraceEventType.INVESTIGATION_FAILED, **terminal_details(failed_state, candidate_error), reason=reason,
                     error_code=candidate_error.error_code if candidate_error else None)
                failed_state = _updated(failed_state)
                audit_local(failed_state, candidate_error)
            current, published_result = failed_state, candidate_error
            published_validation = candidate_validation
        except _TraceFailure:
            trace_writable = False
            current = _updated(current, status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                               result_id=str(uuid4()), completion_reason=trace_failure_reason)
        except ResultValidationError:
            # An incomplete request cannot be forced into the result schema by
            # inventing its activity/window. Keep only the operational diagnostic.
            current = _updated(current, status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                               result_id=str(uuid4()), completion_reason=reason)
            if trace_writable:
                try:
                    emit(TraceEventType.INVESTIGATION_FAILED, **terminal_details(current), reason=reason)
                    current = _updated(current)
                    audit_local(current)
                except _TraceFailure:
                    trace_writable = False
                    current = _updated(current, completion_reason=trace_failure_reason)
    finally:
        budget.close()
        if dispatcher is not None:
            dispatcher.close()
        if exchange is not None:
            exchange.close()
        if local_trace is not None:
            try:
                local_trace.close()
            except TraceWriteError:
                trace_failed = True
    stats = budget.snapshot()
    current = _updated(current, tool_call_count=stats.tool_calls, retry_count=stats.retries,
                       fallback_attempted=bool(stats.fallbacks))
    if local_trace is not None and not trace_failed and trace_validation is None:
        try:
            audit_local(current, published_result)
        except _TraceFailure:
            pass
    if trace_failed:
        trace_writable = False
        published_result = published_validation = trace_validation = None
        current = _updated(current, status=InvestigationStatus.FAILED, outcome=Outcome.ERROR,
                           result_id=str(uuid4()), completion_reason=trace_failure_reason)
    return SkeletonReport(current, stats, tuple(visited), trace_writable,
                          dispatcher.driver.bindings if dispatcher is not None else (), evidence_report, safety_report,
                          comparison, published_result, published_validation,
                          request_context, request_receipt, selection,
                          local_trace.path if local_trace else None, trace_validation)


async def run_synthetic_tool_graph(
    request: NormalizedRequest, *, catalog: BeachCatalog, candidate_beach_ids: tuple[str, ...],
    plan: SpecialistPlanner, tool_plan: Callable[[SpecialistInvestigationRequest], tuple[ToolAction, ...]],
    driver_inputs: DriverInputs, record_event: EventRecorder | None = None, session_id: str | None = None,
    request_step: int = 1,
    evidence_policy: PolicyConfiguration | None = None,
    safety_evaluation: bool = False,
    result_generation: bool = False,
    session_request: SessionRequest | None = None,
    trace_settings: TraceSettings | None = None,
) -> SkeletonReport:
    """Execute explicitly planned synthetic retrievals; never an acceptance run.

    Driver inputs stay in the trusted layer; planners receive no script/oracle.
    Optional evidence_policy enables independent synthetic validation; the
    safety_evaluation flag additionally creates trusted Candidate Assessments.
    result_generation additionally validates controlled synthetic outcomes.
    Optional session admission carries a revision into fresh IDs and budgets;
    it never accepts previous graph state. By default, local JSONL must pass
    independent validation before publication. An explicit record_event callback
    is a memory/component seam. Full scenario acceptance remains deferred.
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
        trace_settings=trace_settings,
    )


async def run_raw_synthetic_tool_graph(
    admission: RawSessionRequest, *,
    interpreter: Callable | None = None,
    model_adapter: SyntheticModelAdapter | None = None,
    plan: Callable[[RawPlanningInput], object],
    tool_plan: Callable[[SpecialistInvestigationRequest], tuple[ToolAction, ...]],
    driver_inputs: DriverInputs, evidence_policy: PolicyConfiguration,
    record_event: EventRecorder | None = None, request_step: int = 1,
    trace_settings: TraceSettings | None = None,
) -> SkeletonReport:
    """Integrate admitted raw work with the existing synthetic component graph.

    Supply either an authored synchronous interpreter (zero model usage) or an
    explicit synthetic model adapter (shared-ledger accounting test double).
    Trusted planners may be synchronous/async; only they receive the model-call
    seam and independently enforced investigation subset. No provider is enabled,
    no general CLI is exposed, and memory recorders are not authoritative JSONL.
    """
    if not isinstance(admission, RawSessionRequest):
        raise ValueError("Raw work requires session admission before interpretation")
    if (interpreter is None) == (model_adapter is None):
        raise ValueError("Supply exactly one authored interpreter or synthetic model adapter")
    if model_adapter is not None and not isinstance(model_adapter, SyntheticModelAdapter):
        raise ValueError("Only an explicit synthetic accounting adapter is supported")
    if type(request_step) is not int or not 1 <= request_step <= len(driver_inputs.script.requests):
        raise ValueError("Invalid synthetic request step")
    # Use the admission's detached catalog, not a caller-replaced scope snapshot.
    return await _run_graph(
        admission.request, candidate_beach_ids=(), catalog=admission.context.catalog,
        session_id=admission.session_id, raw_admission=admission,
        interpreter=interpreter, model_adapter=model_adapter, plan=plan, tool_plan=tool_plan,
        driver_inputs=driver_inputs, evidence_policy=evidence_policy, request_step=request_step,
        safety_evaluation=True, result_generation=True, record_event=record_event,
        trace_settings=trace_settings,
    )
