"""Per-investigation trusted reservations. No provider or tool execution lives here."""

from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from typing import Literal

from hawaii_activity_forecaster.config.settings import InvestigationLimits
from hawaii_activity_forecaster.models.enums import AgentType


class BudgetError(RuntimeError):
    """Dispatch is denied; callers must not execute the proposed work."""


@dataclass(frozen=True)
class BudgetSnapshot:
    iterations: int
    tool_calls: int
    model_calls: int
    reserved_tool_calls: int
    reserved_model_calls: int
    retries: int
    fallbacks: int
    active_specialists: int
    closed: bool


@dataclass
class _Call:
    kind: Literal["tool", "model"]
    state: str = "reserved"
    retry_of: str | None = None
    fallback_gap: str | None = None
    retryable: bool = False


class BudgetManager:
    """Atomic reserve/dispatch/finish bookkeeping for one investigation.

    Reservations consume capacity, but only dispatch increments invocation counts.
    Failed and timed-out dispatched calls are never refunded. Recovery identifiers
    come from trusted code; this component cannot determine semantic gap identity.
    """

    def __init__(self, limits: InvestigationLimits | None = None):
        self._limits = InvestigationLimits.model_validate(limits or InvestigationLimits())
        self._lock = RLock()
        self._calls: dict[str, _Call] = {}
        self._active: set[AgentType] = set()
        self._iterations = 0
        self._closed = False

    def _open(self):
        if self._closed:
            raise BudgetError("investigation execution is closed")

    def begin_iteration(self) -> int:
        with self._lock:
            self._open()
            if self._iterations >= self._limits.max_coordinator_iterations:
                raise BudgetError("Coordinator iteration limit reached")
            self._iterations += 1
            return self._iterations

    def reserve(self, call_id: str, kind: Literal["tool", "model"], *,
                retry_of: str | None = None, fallback_gap: str | None = None) -> None:
        with self._lock:
            self._open()
            if not isinstance(call_id, str) or not call_id.strip() or call_id in self._calls:
                raise BudgetError("call ID must be nonempty and never reused")
            if kind not in ("tool", "model"):
                raise BudgetError("unknown invocation kind")
            if (retry_of is not None or fallback_gap is not None) and kind != "tool":
                raise BudgetError("environmental recovery allowances apply only to tools")
            live = [c for c in self._calls.values() if c.state != "cancelled"]
            cap = (self._limits.max_environmental_tool_invocations if kind == "tool"
                   else self._limits.max_llm_invocations)
            if sum(c.kind == kind for c in live) >= cap:
                raise BudgetError(f"{kind} invocation limit reached")
            if retry_of is not None:
                original = self._calls.get(retry_of)
                if (fallback_gap is not None or original is None or original.kind != "tool"
                        or original.state != "failed" or not original.retryable
                        or original.retry_of is not None):
                    raise BudgetError("retry requires a retryable failed original tool call")
                if sum(c.retry_of == retry_of for c in live) >= self._limits.max_retries_per_failed_invocation:
                    raise BudgetError("retry allowance exhausted")
            if fallback_gap is not None:
                if not isinstance(fallback_gap, str) or not fallback_gap.strip():
                    raise BudgetError("fallback requires a stable evidence-gap ID")
                if sum(c.fallback_gap == fallback_gap for c in live) >= self._limits.max_fallback_attempts_per_evidence_gap:
                    raise BudgetError("fallback allowance exhausted")
            self._calls[call_id] = _Call(kind, retry_of=retry_of, fallback_gap=fallback_gap)

    def dispatch(self, call_id: str) -> None:
        with self._lock:
            self._open()
            call = self._get(call_id)
            if call.state != "reserved":
                raise BudgetError("only a reserved call may dispatch")
            call.state = "dispatched"

    def finish(self, call_id: str, *, failed: bool = False, retryable: bool = False) -> None:
        with self._lock:
            call = self._get(call_id)
            if call.state != "dispatched":
                raise BudgetError("only a dispatched call may finish")
            call.state = "failed" if failed else "succeeded"
            call.retryable = failed and retryable

    def cancel(self, call_id: str) -> None:
        with self._lock:
            call = self._get(call_id)
            if call.state != "reserved":
                raise BudgetError("dispatched work cannot be refunded")
            call.state = "cancelled"

    def _get(self, call_id: str) -> _Call:
        try:
            return self._calls[call_id]
        except KeyError:
            raise BudgetError("unknown call ID") from None

    @contextmanager
    def specialist_slot(self, agent_type: AgentType):
        with self._lock:
            self._open()
            if not isinstance(agent_type, AgentType):
                raise BudgetError("unsupported specialist role")
            if agent_type in self._active or len(self._active) >= self._limits.max_concurrent_specialists:
                raise BudgetError("specialist concurrency limit reached")
            self._active.add(agent_type)
        try:
            yield
        finally:
            with self._lock:
                self._active.remove(agent_type)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            for call in self._calls.values():
                if call.state == "reserved":
                    call.state = "cancelled"

    def snapshot(self) -> BudgetSnapshot:
        with self._lock:
            calls = list(self._calls.values())
            dispatched = [c for c in calls if c.state in ("dispatched", "failed", "succeeded")]
            return BudgetSnapshot(
                self._iterations, sum(c.kind == "tool" for c in dispatched),
                sum(c.kind == "model" for c in dispatched),
                sum(c.kind == "tool" and c.state == "reserved" for c in calls),
                sum(c.kind == "model" and c.state == "reserved" for c in calls),
                sum(c.retry_of is not None for c in dispatched),
                sum(c.fallback_gap is not None for c in dispatched),
                len(self._active), self._closed,
            )

    def fallback_allowance_exhausted(self, gap_id: str) -> bool:
        """Observed dispatched capacity only; availability is not script-driven."""
        with self._lock:
            if not isinstance(gap_id, str) or not gap_id.strip():
                raise BudgetError("fallback allowance requires a stable evidence-gap ID")
            return sum(c.fallback_gap == gap_id and c.state in {"dispatched", "failed", "succeeded"}
                       for c in self._calls.values()) >= self._limits.max_fallback_attempts_per_evidence_gap
