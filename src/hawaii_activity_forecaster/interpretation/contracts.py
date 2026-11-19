"""Internal proposal transport and detached audit snapshots, not logical schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol, Self

from pydantic import Field, model_validator

from hawaii_activity_forecaster.models import BeachCatalog, NormalizedRequest
from hawaii_activity_forecaster.models.common import ContractModel, JsonObject, NonNegativeInt, PositiveInt

PROFILE_ID = "m1-request-rules-0.1"
ValueField = Literal["activity", "target_date", "target_time_window", "preferred_area", "experience_level", "hard_constraints", "soft_preferences"]
VALUE_FIELDS = frozenset(NormalizedRequest.model_fields) - {"original_request", "clarification_needed", "clarification_questions"}


class RequestValidationError(ValueError):
    """The input/proposal/audit cannot be trusted; expose no raw private payload."""


class TextSpan(ContractModel):
    start: NonNegativeInt
    end: PositiveInt

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start >= self.end:
            raise ValueError("source span must be nonempty")
        return self


class SourceSpan(TextSpan):
    field: ValueField
    entry_index: NonNegativeInt | None = None


class RemovedEntry(TextSpan):
    field: Literal["hard_constraints", "soft_preferences"]
    previous_index: NonNegativeInt


class InterpretationProposal(ContractModel):
    changed_values: JsonObject
    source_spans: list[SourceSpan]
    removed_entries: list[RemovedEntry] = Field(default_factory=list)
    unresolved_spans: list[TextSpan] = Field(default_factory=list)

    @model_validator(mode="after")
    def allowed(self) -> Self:
        if not self.changed_values.keys() <= VALUE_FIELDS:
            raise ValueError("proposal contains unauthorized fields")
        return self


@dataclass(frozen=True)
class Origin:
    field: str
    entry_index: int | None
    source: Literal["USER", "DEFAULT", "INHERITED"]
    span: tuple[int, int] | None = None
    assumed: bool = False
    default_rule: str | None = None
    inherited_from: str | None = None


@dataclass(frozen=True)
class ContextLocation:
    scope: str
    value: str
    span: tuple[int, int] | None
    inherited_from: str | None = None


@dataclass(frozen=True)
class ValidatedRequest:
    session_id: str
    investigation_id: str
    request_revision: int
    context_digest: str
    origins: tuple[Origin, ...]
    changed_fields: tuple[str, ...]
    limitations: tuple[str, ...]
    starting_locations: tuple[ContextLocation, ...]
    _request: bytes = field(repr=False)
    _proposal: bytes = field(repr=False)

    @property
    def request(self) -> NormalizedRequest:
        return NormalizedRequest.model_validate_json(self._request)

    @property
    def user_provided_fields(self) -> frozenset[str]:
        return frozenset(o.field for o in self.origins if not o.assumed)

    @property
    def assumed_fields(self) -> frozenset[str]:
        return frozenset(o.field for o in self.origins if o.assumed)

    @property
    def assumption_disclosures(self) -> tuple[str, ...]:
        window = self.request.target_time_window
        if window is None or "target_time_window" not in self.assumed_fields:
            return ()
        return (f"Assumed daypart window: {window.start.isoformat()} to {window.end.isoformat()} (Hawaii time).",)


@dataclass(frozen=True)
class RequestContext:
    original_request: str
    reference_time: datetime
    catalog: BeachCatalog
    session_id: str
    investigation_id: str
    request_revision: int = 1
    inherited: ValidatedRequest | None = None
    prior_status: Literal["COMPLETED", "ABSTAINED", "FAILED"] | None = None
    rule_profile: str = PROFILE_ID


@dataclass(frozen=True)
class InterpreterInput:
    original_request: str
    reference_time: datetime
    session_id: str
    investigation_id: str
    request_revision: int
    rule_profile: str
    # Immutable identity metadata only; no driver, oracle or source payloads.
    catalog_summary: tuple[tuple[str, str, tuple[str, ...], str, str], ...]
    inherited_origins: tuple[Origin, ...]
    _inherited_request: bytes | None = field(repr=False)

    @property
    def inherited_request(self) -> NormalizedRequest | None:
        return NormalizedRequest.model_validate_json(self._inherited_request) if self._inherited_request else None


class Interpreter(Protocol):
    def __call__(self, inputs: InterpreterInput) -> object: ...
