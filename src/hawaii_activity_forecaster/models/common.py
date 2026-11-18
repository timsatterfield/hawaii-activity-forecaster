"""Shared structural types and approved fixture serialization conventions."""

from datetime import date, datetime
import re
from typing import Annotated, Self

from pydantic import (
    AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field,
    JsonValue, StrictFloat, StrictInt, StringConstraints, model_validator,
)

Text = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"\S")]
PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
Number = StrictInt | StrictFloat
JsonObject = dict[str, JsonValue]


def _timestamp_input(value: object) -> object:
    if not isinstance(value, (str, datetime)):
        raise ValueError("timestamp must be an ISO 8601 string or aware datetime")
    if isinstance(value, str) and "T" not in value.upper():
        raise ValueError("timestamp must include an ISO 8601 date and time")
    return value


def _date_input(value: object) -> object:
    if isinstance(value, datetime) or not isinstance(value, (str, date)):
        raise ValueError("date must be an ISO calendar date or date object")
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise ValueError("calendar date must use YYYY-MM-DD")
    return value


Timestamp = Annotated[AwareDatetime, BeforeValidator(_timestamp_input)]
CalendarDate = Annotated[date, BeforeValidator(_date_input)]


class ContractModel(BaseModel):
    """Validate snapshots; external references and runtime policy need later validators."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=False, revalidate_instances="always",
    )


class TimeRange(ContractModel):
    """Start-inclusive, end-exclusive range (FX-OD-002/003)."""

    start: Timestamp
    end: Timestamp

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start >= self.end:
            raise ValueError("time range start must precede end")
        return self


class NumberRange(ContractModel):
    """Reported measurement range (FX-OD-005), without unit conversion."""

    min: Number
    max: Number

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.min > self.max:
            raise ValueError("measurement min cannot exceed max")
        return self


def unique(values: list[object], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}")


def chronological(start: datetime | None, end: datetime | None, label: str) -> None:
    if start is not None and end is not None and end < start:
        raise ValueError(f"{label} ends before it starts")
