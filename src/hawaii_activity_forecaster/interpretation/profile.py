"""The approved immutable daypart/profile rules; no environment/config loading."""

from dataclasses import dataclass
from datetime import date, datetime, time

from hawaii_activity_forecaster.catalog import HST
from hawaii_activity_forecaster.models import TimeRange
from .contracts import PROFILE_ID, RequestValidationError


@dataclass(frozen=True)
class RequestRuleProfile:
    version: str = PROFILE_ID

    def __post_init__(self):
        if self.version != PROFILE_ID:
            raise RequestValidationError("Unsupported request-rule profile.")

    def daypart_window(self, daypart: str, target_date: date) -> TimeRange:
        hours = {"morning": (8, 11), "afternoon": (12, 16)}
        if daypart not in hours:
            raise RequestValidationError("Daypart requires explicit hours.")
        start, end = hours[daypart]
        return TimeRange(start=datetime.combine(target_date, time(start), HST),
                         end=datetime.combine(target_date, time(end), HST))
