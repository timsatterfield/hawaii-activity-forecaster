"""Independent assertion grammar and typed pointer validation; no execution oracle."""

from enum import StrEnum
import json
import re
from types import UnionType
from typing import Annotated, Literal, Self, Union, get_args, get_origin

from pydantic import BaseModel, Field, JsonValue, StrictBool, TypeAdapter, ValidationError, model_validator

from hawaii_activity_forecaster.models import (
    CandidateAssessment, EnvironmentalFinding, InvestigationState, Recommendation,
    RecommendationResult, TraceEvent,
)
from hawaii_activity_forecaster.models.common import (
    ContractModel, JsonObject, NonNegativeInt, PositiveInt, Text, unique,
)
from hawaii_activity_forecaster.models.enums import Activity, TraceActor, TraceEventType

from .policy import Version


class Readiness(StrEnum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    DISABLED = "DISABLED"
    PARTIALLY_BLOCKED = "PARTIALLY_BLOCKED"


class Target(StrEnum):
    INVESTIGATION_STATE = "investigation_state"
    CANDIDATE_ASSESSMENT = "candidate_assessment"
    ENVIRONMENTAL_FINDING = "environmental_finding"
    RECOMMENDATION_RESULT = "recommendation_result"
    RECOMMENDATION = "recommendation"
    TRACE_EVENT = "trace_event"
    HARNESS_EXECUTION = "harness_execution"


class Operator(StrEnum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    ALL_EQUALS = "ALL_EQUALS"
    INCLUDES = "INCLUDES"
    EXCLUDES = "EXCLUDES"
    COUNT_EQUALS = "COUNT_EQUALS"
    COUNT_AT_MOST = "COUNT_AT_MOST"
    EXISTS = "EXISTS"
    ABSENT = "ABSENT"
    SAME_AS = "SAME_AS"
    DIFFERENT_FROM = "DIFFERENT_FROM"


class StepSelector(ContractModel):
    request_step: PositiveInt


class AssessmentSelector(StepSelector):
    beach_id: Text | None = None
    activity: Activity | None = None


class RecommendationSelector(StepSelector):
    beach_id: Text | None = None


class RelatedFinding(ContractModel):
    source_fixture_id: Text
    template_finding_id: Text
    operation_id: Text | None = None
    attempt: PositiveInt | None = None

    @model_validator(mode="after")
    def pairing(self) -> Self:
        if (self.operation_id is None) != (self.attempt is None):
            raise ValueError("operation_id and attempt must appear together")
        return self


class RelatedCall(ContractModel):
    operation_id: Text
    attempt: PositiveInt


class FindingSelector(StepSelector):
    source_fixture_id: Text | None = None
    template_finding_id: Text | None = None
    operation_id: Text | None = None
    attempt: PositiveInt | None = None

    @model_validator(mode="after")
    def pairing(self) -> Self:
        if (self.source_fixture_id is None) != (self.template_finding_id is None):
            raise ValueError("source/template finding references must appear together")
        if (self.operation_id is None) != (self.attempt is None):
            raise ValueError("operation_id and attempt must appear together")
        return self


class TraceSelector(StepSelector):
    event_type: TraceEventType | None = None
    actor: TraceActor | None = None
    related_finding_ref: RelatedFinding | None = None
    related_call_ref: RelatedCall | None = None


class ExecutionSummary(ContractModel):
    """Typed observation projection, never populated with configuration maxima."""
    session_id: Text
    investigation_id: Text
    request_revision: PositiveInt
    tool_invocation_count: NonNegativeInt
    model_invocation_count: NonNegativeInt
    iteration_count: NonNegativeInt
    max_concurrent_specialists: NonNegativeInt


SELECTORS = {
    Target.INVESTIGATION_STATE: StepSelector, Target.CANDIDATE_ASSESSMENT: AssessmentSelector,
    Target.ENVIRONMENTAL_FINDING: FindingSelector, Target.RECOMMENDATION_RESULT: StepSelector,
    Target.RECOMMENDATION: RecommendationSelector, Target.TRACE_EVENT: TraceSelector,
    Target.HARNESS_EXECUTION: StepSelector,
}
TARGET_MODELS = {
    Target.INVESTIGATION_STATE: InvestigationState, Target.CANDIDATE_ASSESSMENT: CandidateAssessment,
    Target.ENVIRONMENTAL_FINDING: EnvironmentalFinding, Target.RECOMMENDATION_RESULT: RecommendationResult,
    Target.RECOMMENDATION: Recommendation, Target.TRACE_EVENT: TraceEvent,
    Target.HARNESS_EXECUTION: ExecutionSummary,
}
# Only the fields expressly documented in 03 §§7.5–7.8 may be inspected under details.
TRACE_DETAIL_TYPES = {
    "tool_call_id": Text, "tool_name": Text, "agent_type": Literal["WEATHER", "OCEAN"],
    "execution_status": Literal["SUCCESS", "PARTIAL", "ERROR", "TIMEOUT"],
    "duration_ms": NonNegativeInt, "result_reference_ids": list[Text], "error_code": Text,
    "arguments_summary": JsonObject,
    "finding_id": Text, "validation_status": Literal["ACCEPTED", "LIMITED", "REJECTED"],
    "validation_rule_ids": list[Text], "validation_reasons": list[Text], "source_id": Text,
    "assessment_id": Text, "beach_id": Text, "activity": Activity,
    "eligibility": CandidateAssessment.model_fields["eligibility"].annotation,
    "environmental_suitability": CandidateAssessment.model_fields["environmental_suitability"].annotation,
    "evidence_quality": CandidateAssessment.model_fields["evidence_quality"].annotation,
    "applied_policy_ids": list[Text], "decision_reasons": list[Text],
    "final_status": Literal["COMPLETED", "ABSTAINED", "FAILED"], "result_id": Text,
    "recommended_beach_ids": list[Text], "completion_reason": Text,
    "total_iterations": NonNegativeInt, "total_tool_calls": NonNegativeInt,
    "total_retries": NonNegativeInt, "total_duration_ms": NonNegativeInt,
}


def pointer_tokens(pointer: str) -> list[str]:
    if not pointer.startswith("/") or pointer == "/" or re.search(r"~(?![01])", pointer):
        raise ValueError("field must be a nonroot JSON Pointer with valid escapes")
    tokens = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    if any(not token or "*" in token or re.fullmatch(r"-\d+", token) for token in tokens):
        raise ValueError("empty, wildcard and negative pointer locations are forbidden")
    return tokens


def _options(annotation):
    if get_origin(annotation) is Annotated:
        return _options(get_args(annotation)[0])
    if get_origin(annotation) in (Union, UnionType):
        return [option for arg in get_args(annotation) if arg is not type(None) for option in _options(arg)]
    return [annotation]


def field_type(target: Target, pointer: str):
    tokens = pointer_tokens(pointer)
    if target == Target.TRACE_EVENT and tokens[0] == "details":
        if len(tokens) < 2 or tokens[1] not in TRACE_DETAIL_TYPES:
            raise ValueError("trace detail field is not an approved observation")
        current = TRACE_DETAIL_TYPES[tokens[1]]
        tokens = tokens[2:]
    else:
        current = TARGET_MODELS[target]
    for token in tokens:
        choices = []
        for option in _options(current):
            if isinstance(option, type) and issubclass(option, BaseModel) and token in option.model_fields:
                choices.append(option.model_fields[token].rebuild_annotation())
            elif get_origin(option) is list and re.fullmatch(r"0|[1-9]\d*", token):
                choices.append(get_args(option)[0])
        if not choices:
            raise ValueError("pointer does not name a documented target field")
        current = choices[0] if len(choices) == 1 else Union[tuple(choices)]
    return current


def _same_json_types(left, right) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return True  # Both are JSON numbers; strict integer constraints are checked first.
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_json_types(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_json_types(left[k], right[k]) for k in left)
    return True


class ActualReference(ContractModel):
    target: Target
    selector: dict[str, JsonValue]
    field: Text

    @model_validator(mode="after")
    def structure(self) -> Self:
        SELECTORS[self.target].model_validate(self.selector)
        field_type(self.target, self.field)
        return self


class Assertion(ContractModel):
    assertion_id: Text
    requirement_ids: list[Text] = Field(min_length=1)
    mandatory: StrictBool
    test_status: Readiness
    target: Target
    selector: dict[str, JsonValue]
    operator: Operator
    field: Text | None = None
    expected: JsonValue = None
    expected_ref: ActualReference | None = None
    blocking_reason: Text | None = None

    @model_validator(mode="after")
    def structure(self) -> Self:
        SELECTORS[self.target].model_validate(self.selector)
        if (self.test_status == Readiness.ACTIVE) != (self.blocking_reason is None):
            raise ValueError("active assertions have no blocker; inactive assertions require a reason")
        fields = self.model_fields_set & {"field", "expected", "expected_ref"}
        op = self.operator
        needed = set()
        if op in {Operator.EQUALS, Operator.NOT_EQUALS, Operator.ALL_EQUALS, Operator.INCLUDES, Operator.EXCLUDES}:
            needed = {"field", "expected"}
        elif op in {Operator.COUNT_EQUALS, Operator.COUNT_AT_MOST}:
            needed = {"expected"}
        elif op in {Operator.SAME_AS, Operator.DIFFERENT_FROM}:
            needed = {"field", "expected_ref"}
        if fields != needed:
            raise ValueError("assertion operand fields do not match its operator")
        if "field" in needed:
            if self.field is None:
                raise ValueError("comparison requires field")
            annotation = field_type(self.target, self.field)
            if op in {Operator.INCLUDES, Operator.EXCLUDES}:
                arrays = [o for o in _options(annotation) if get_origin(o) is list]
                if len(arrays) != 1:
                    raise ValueError("membership operator requires an array field")
                annotation = get_args(arrays[0])[0]
            if "expected" in needed:
                adapter = TypeAdapter(annotation)
                value = adapter.validate_json(json.dumps(self.expected, allow_nan=False), strict=True)
                if not _same_json_types(self.expected, adapter.dump_python(value, mode="json", exclude_unset=True)):
                    raise ValueError("expected operand must match the serialized target type")
            else:
                if self.expected_ref is None:
                    raise ValueError("comparison requires actual reference")
                other = field_type(self.expected_ref.target, self.expected_ref.field)
                if TypeAdapter(annotation).json_schema() != TypeAdapter(other).json_schema():
                    raise ValueError("cross-observation comparison types must agree")
        elif "expected" in needed:
            TypeAdapter(NonNegativeInt).validate_python(self.expected)
        unique(self.requirement_ids, "assertion requirement IDs")
        return self


class ExpectedResults(ContractModel):
    harness_contract_version: Version
    scenario_id: Text
    assertions: list[Assertion] = Field(min_length=1)

    @model_validator(mode="after")
    def structure(self) -> Self:
        unique([a.assertion_id for a in self.assertions], "assertion IDs")
        return self
