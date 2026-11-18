"""Trace snapshots and event structures (03 §7); no trace writer or storage."""

from typing import Literal, Self

from pydantic import model_validator

from .common import ContractModel, JsonObject, PositiveInt, Text, Timestamp, chronological, unique
from .enums import InvestigationStatus, TraceActor, TraceEventType

TerminalStatus = Literal[
    InvestigationStatus.COMPLETED, InvestigationStatus.ABSTAINED, InvestigationStatus.FAILED,
]


class TraceEvent(ContractModel):
    event_id: Text
    trace_id: Text
    sequence_number: PositiveInt
    timestamp: Timestamp
    event_type: TraceEventType
    actor: TraceActor
    request_revision: PositiveInt
    related_ids: list[Text] | None = None
    details: JsonObject


class InvestigationTrace(ContractModel):
    trace_id: Text
    investigation_id: Text
    schema_version: Text
    started_at: Timestamp
    completed_at: Timestamp | None = None
    final_status: TerminalStatus | None = None
    configuration_version: Text
    policy_version: Text
    model_identifier: Text | None = None
    events: list[TraceEvent]

    @model_validator(mode="after")
    def consistency(self) -> Self:
        chronological(self.started_at, self.completed_at, "trace")
        unique([event.event_id for event in self.events], "trace event IDs (IT-002)")
        previous = 0
        terminal_types = {
            TraceEventType.INVESTIGATION_COMPLETED: InvestigationStatus.COMPLETED,
            TraceEventType.INVESTIGATION_ABSTAINED: InvestigationStatus.ABSTAINED,
            TraceEventType.INVESTIGATION_FAILED: InvestigationStatus.FAILED,
        }
        for event in self.events:
            if event.trace_id != self.trace_id:
                raise ValueError("event trace_id does not match parent trace")
            if event.sequence_number <= previous:
                raise ValueError("trace sequence numbers must increase (IT-002)")
            previous = event.sequence_number
            if self.final_status is not None and event.event_type in terminal_types:
                if terminal_types[event.event_type] != self.final_status:
                    raise ValueError("terminal event disagrees with final trace status")
        return self
