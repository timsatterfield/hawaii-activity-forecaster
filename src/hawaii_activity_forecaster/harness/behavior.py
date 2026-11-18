"""Behavior declarations only; no dispatch, clocks, retry or fallback execution."""

import json
from typing import Literal, Self

from pydantic import Field, model_validator

from hawaii_activity_forecaster.models.common import (
    ContractModel, JsonObject, NonNegativeInt, PositiveInt, Text, TimeRange, Timestamp, unique,
)
from hawaii_activity_forecaster.models.enums import AgentType, SourceId

from .policy import Category, Version


class RequestStep(ContractModel):
    request_step: PositiveInt
    user_request: Text
    reference_time: Timestamp


class BehaviorAttempt(ContractModel):
    attempt: PositiveInt
    behavior: Literal["SUCCESS", "PARTIAL", "UNAVAILABLE", "ERROR", "TIMEOUT", "MALFORMED", "DUPLICATE"]
    simulated_duration_ms: NonNegativeInt
    response_fixture_id: Text | None = None
    raw_response_path: Text | None = None
    invalid_fields: list[Text] | None = None
    delivery_count: PositiveInt | None = None

    @model_validator(mode="after")
    def shape(self) -> Self:
        required = {"attempt", "behavior", "simulated_duration_ms"}
        if self.behavior in {"SUCCESS", "PARTIAL", "UNAVAILABLE", "ERROR", "DUPLICATE"}:
            required.add("response_fixture_id")
        if self.behavior == "DUPLICATE":
            required.add("delivery_count")
            if self.delivery_count is None or self.delivery_count < 2:
                raise ValueError("duplicate delivery requires delivery_count >= 2")
        if self.behavior == "MALFORMED":
            required.update({"raw_response_path", "invalid_fields"})
            if not self.invalid_fields:
                raise ValueError("malformed behavior requires explicit invalid fields")
            from .assertions import pointer_tokens
            for pointer in self.invalid_fields:
                pointer_tokens(pointer)
        if self.model_fields_set != required or any(getattr(self, name) is None for name in required):
            raise ValueError("behavior-specific fields do not match the selected behavior")
        if (self.behavior == "TIMEOUT") != (self.simulated_duration_ms > 10_000):
            raise ValueError("TIMEOUT must exceed 10000 ms; other deliveries must not")
        return self


class Operation(ContractModel):
    operation_id: Text
    request_step: PositiveInt
    agent_type: AgentType
    source_id: SourceId
    candidate_beach_ids: list[Text] = Field(min_length=1)
    requested_evidence: list[Category] = Field(min_length=1)
    target_time_window: TimeRange
    geographic_scope: JsonObject
    attempts: list[BehaviorAttempt] = Field(min_length=1)

    @model_validator(mode="after")
    def shape(self) -> Self:
        unique(self.candidate_beach_ids, "operation candidates")
        unique(self.requested_evidence, "operation categories")
        if [a.attempt for a in self.attempts] != list(range(1, len(self.attempts) + 1)):
            raise ValueError("tool attempts must be contiguous from 1")
        if len(self.attempts) > 2:
            raise ValueError("only one retry per original operation is approved")
        if len(self.attempts) == 2 and self.attempts[0].behavior not in {"ERROR", "TIMEOUT", "UNAVAILABLE", "MALFORMED"}:
            raise ValueError("a retry cannot follow a successful/partial delivery")
        return self

    def match_key(self) -> tuple:
        return (self.request_step, self.agent_type, self.source_id, tuple(sorted(self.candidate_beach_ids)),
                tuple(sorted(self.requested_evidence)), self.target_time_window.start,
                self.target_time_window.end, json.dumps(self.geographic_scope, sort_keys=True))


class BehaviorScript(ContractModel):
    harness_contract_version: Version
    requests: list[RequestStep] = Field(min_length=1)
    operations: list[Operation]

    @model_validator(mode="after")
    def shape(self) -> Self:
        if [r.request_step for r in self.requests] != list(range(1, len(self.requests) + 1)):
            raise ValueError("request steps must be contiguous from 1")
        unique([op.operation_id for op in self.operations], "operation IDs")
        unique([op.match_key() for op in self.operations], "operation dispatch patterns")
        if any(op.request_step > len(self.requests) for op in self.operations):
            raise ValueError("operation refers to an absent request step")
        return self
