"""Closed internal model proposals; never evidence, safety or execution authority."""

from __future__ import annotations

import json
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from hawaii_activity_forecaster.harness.policy import Category
from hawaii_activity_forecaster.interpretation.contracts import InterpretationProposal, ValueField
from hawaii_activity_forecaster.models import NormalizedRequest, SpecialistInvestigationRequest
from hawaii_activity_forecaster.models.enums import AgentType, Eligibility, EvidenceQuality, EnvironmentalSuitability

Operation = Literal["normalize_request", "coordinator_plan", "weather_investigation", "ocean_investigation"]
Role = Literal["COORDINATOR", "WEATHER", "OCEAN"]
Index = Annotated[int, Field(strict=True, ge=0)]
Identifier = Annotated[str, Field(strict=True, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
Ids = Annotated[list[Identifier], Field(max_length=64)]
StopReason = Literal["SUFFICIENT_EVIDENCE", "NO_SUPPORTED_CANDIDATES", "NO_LEGAL_ACTION", "NO_MATERIAL_BENEFIT", "LIMIT_REACHED"]


class ProposalError(ValueError):
    """Static diagnostic only; rejected private content is never echoed."""


def decode_json(value: str) -> object:
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = item
        return result
    def constant(_):
        raise ValueError("nonfinite number")
    try:
        return json.loads(value, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError, RecursionError):
        raise ProposalError("MODEL_JSON_INVALID") from None


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True,
                              revalidate_instances="always", hide_input_in_errors=True,
                              allow_inf_nan=False)


class InvocationIdentity(WireModel):
    session_id: Identifier
    investigation_id: Identifier
    request_revision: Annotated[int, Field(strict=True, ge=1)]


class Span(WireModel):
    start: Index
    end: Annotated[int, Field(strict=True, ge=1)]

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("MODEL_SPAN_INVALID")
        return self


class SourceSpan(Span):
    field: ValueField
    entry_index: Index | None


class RemovedEntry(Span):
    field: Literal["hard_constraints", "soft_preferences"]
    previous_index: Index


class Change(WireModel):
    field: ValueField
    value_json: Annotated[str, Field(max_length=16000)]


class NormalizationProposal(WireModel):
    changes: Annotated[list[Change], Field(max_length=7)]
    source_spans: Annotated[list[SourceSpan], Field(max_length=64)]
    removed_entries: Annotated[list[RemovedEntry], Field(max_length=64)]
    unresolved_spans: Annotated[list[Span], Field(max_length=64)]

    def to_interpretation(self) -> InterpretationProposal:
        values = {}
        for change in self.changes:
            if change.field in values:
                raise ProposalError("MODEL_DUPLICATE_CHANGE")
            value = decode_json(change.value_json)
            try:
                TypeAdapter(NormalizedRequest.model_fields[change.field].annotation).validate_json(
                    json.dumps(value, allow_nan=False))
            except ValueError:
                raise ProposalError("MODEL_CHANGE_VALUE_INVALID") from None
            values[change.field] = value
        return InterpretationProposal(changed_values=values,
            source_spans=[s.model_dump() for s in self.source_spans],
            removed_entries=[s.model_dump() for s in self.removed_entries],
            unresolved_spans=[s.model_dump() for s in self.unresolved_spans])


class DelegationTask(WireModel):
    agent_type: AgentType
    candidate_ids: Annotated[Ids, Field(min_length=1)]
    evidence_categories: Annotated[list[Category], Field(min_length=1, max_length=7)]
    gap_ids: Ids

    @model_validator(mode="after")
    def unique_fields(self) -> Self:
        for values in (self.candidate_ids, self.evidence_categories, self.gap_ids):
            if len(values) != len(set(values)):
                raise ValueError("MODEL_DUPLICATE_TASK_SCOPE")
        return self


class CoordinatorDecision(WireModel):
    action: Literal["DELEGATE", "CONCLUDE"]
    tasks: Annotated[list[DelegationTask], Field(max_length=2)]
    reason_code: Literal["INVESTIGATE_GAPS"] | StopReason
    evidence_refs: Ids

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if ((self.action == "DELEGATE") != bool(self.tasks)
                or (self.action == "DELEGATE") != (self.reason_code == "INVESTIGATE_GAPS")
                or len({t.agent_type for t in self.tasks}) != len(self.tasks)):
            raise ValueError("MODEL_DECISION_INVALID")
        return self


class PlanStep(WireModel):
    option_id: Identifier
    condition: Literal["ALWAYS", "RETRY_IF_RETRYABLE_FAILURE", "FALLBACK_IF_REQUIRED_GAP_UNRESOLVED"]
    origin_step: Index | None


class SpecialistPlan(WireModel):
    steps: Annotated[list[PlanStep], Field(max_length=12)]
    unresolved_gap_ids: Ids
    reason_code: Literal["PLANNED_WORK", "NO_LEGAL_ACTION"]

    @model_validator(mode="after")
    def acyclic(self) -> Self:
        if bool(self.steps) != (self.reason_code == "PLANNED_WORK"):
            raise ValueError("MODEL_PLAN_REASON_INVALID")
        retried = set()
        for index, step in enumerate(self.steps):
            if step.condition == "ALWAYS":
                valid = step.origin_step is None
            else:
                valid = step.origin_step is not None and step.origin_step < index
            if not valid:
                raise ValueError("MODEL_RECOVERY_REFERENCE_INVALID")
            if (step.condition == "RETRY_IF_RETRYABLE_FAILURE"
                    and self.steps[step.origin_step].condition != "ALWAYS"):
                raise ValueError("MODEL_RETRY_REQUIRES_ORIGINAL")
            if step.condition == "RETRY_IF_RETRYABLE_FAILURE":
                if step.origin_step in retried:
                    raise ValueError("MODEL_RETRY_ALLOWANCE_EXCEEDED")
                retried.add(step.origin_step)
        return self


class AssessmentSummary(WireModel):
    beach_id: Identifier
    eligibility: Eligibility
    evidence_quality: EvidenceQuality
    environmental_suitability: EnvironmentalSuitability


class ObservationSummary(WireModel):
    reference_id: Identifier
    candidate_ids: Ids
    category: Category
    status: Literal["ACCEPTED", "LIMITED", "REJECTED", "ERROR", "TIMEOUT", "PARTIAL"]


class CoordinatorInput(WireModel):
    identity: InvocationIdentity
    request: NormalizedRequest
    candidate_ids: Ids
    assessments: Annotated[list[AssessmentSummary], Field(max_length=64)]
    observations: Annotated[list[ObservationSummary], Field(max_length=64)]
    legal_tasks: Annotated[list[DelegationTask], Field(max_length=64)]
    evidence_refs: Ids
    allowed_stop_reasons: Annotated[list[StopReason], Field(max_length=5)]
    remaining_model_calls: Annotated[int, Field(ge=0, le=12)]
    remaining_tool_calls: Annotated[int, Field(ge=0, le=12)]
    remaining_iterations: Annotated[int, Field(ge=0, le=5)]


class SpecialistInput(WireModel):
    identity: InvocationIdentity
    request: SpecialistInvestigationRequest
    gap_ids: Ids
    legal_option_ids: Ids
    observations: Annotated[list[ObservationSummary], Field(max_length=64)]
    remaining_tool_calls: Annotated[int, Field(ge=0, le=12)]

    @property
    def agent_type(self):
        return self.request.agent_type

    @property
    def candidate_ids(self):
        return self.request.candidate_beach_ids


OUTPUTS = {"normalize_request": NormalizationProposal, "coordinator_plan": CoordinatorDecision,
           "weather_investigation": SpecialistPlan, "ocean_investigation": SpecialistPlan}


def parse_proposal(operation: Operation, content: str, context: dict) -> WireModel:
    value = decode_json(content)
    try:
        proposal = OUTPUTS[operation].model_validate_json(json.dumps(value, allow_nan=False))
        if isinstance(proposal, NormalizationProposal):
            proposal.to_interpretation()
            text = context["original_request"]
            for span in (*proposal.source_spans, *proposal.removed_entries, *proposal.unresolved_spans):
                if span.end > len(text):
                    raise ProposalError("MODEL_SPAN_OUTSIDE_REQUEST")
        elif isinstance(proposal, CoordinatorDecision):
            if not set(proposal.evidence_refs) <= set(context["evidence_refs"]):
                raise ProposalError("MODEL_REFERENCE_NOT_ALLOWED")
            legal = [DelegationTask.model_validate_json(json.dumps(t)) for t in context["legal_tasks"]]
            if any(task not in legal for task in proposal.tasks):
                raise ProposalError("MODEL_DELEGATION_NOT_ALLOWED")
            if proposal.action == "DELEGATE" and (
                    len(proposal.tasks) > context["remaining_model_calls"] - 1
                    or context["remaining_iterations"] < 1 or context["remaining_tool_calls"] < 1):
                raise ProposalError("MODEL_PLAN_NOT_ALLOWED")
            if proposal.action == "CONCLUDE" and proposal.reason_code not in context["allowed_stop_reasons"]:
                raise ProposalError("MODEL_STOP_NOT_ALLOWED")
        else:
            # One closed code per rejected condition, so a live failure names its cause.
            if any(step.option_id not in context["legal_option_ids"] for step in proposal.steps):
                raise ProposalError("MODEL_PLAN_OPTION_NOT_ALLOWED")
            if not set(proposal.unresolved_gap_ids) <= set(context["gap_ids"]):
                raise ProposalError("MODEL_PLAN_GAP_NOT_ALLOWED")
            if len(proposal.steps) > context["remaining_tool_calls"]:
                raise ProposalError("MODEL_PLAN_TOO_LONG")
        return proposal
    except ProposalError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError):
        raise ProposalError("MODEL_PROPOSAL_INVALID") from None
