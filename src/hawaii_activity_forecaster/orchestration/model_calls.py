"""Synthetic adapter accounting seam; no provider configuration or SDK dispatch.

Authored interpretation/planning callbacks do not use this ledger. Tests may
explicitly inject this adapter to exercise the shared model budget and timeout.
It does not use BehaviorScript or imply that a real model has been invoked.
"""

from asyncio import wait_for
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from uuid import uuid4

from hawaii_activity_forecaster.config.settings import ExecutionTimeouts
from hawaii_activity_forecaster.models.enums import TraceEventType
from .budgets import BudgetError, BudgetManager


class ModelCallError(RuntimeError):
    """Sanitized operational adapter failure; never an interpretation verdict."""


@dataclass(frozen=True)
class SyntheticModelAdapter:
    """Explicit accounting test double, independent of the environmental script."""

    respond: Callable[[str, object], Awaitable[object]]


class ComponentModelCalls:
    """One graph's synthetic adapter, sharing its environmental dispatch ledger.

    Only trusted component planners receive this object. Interpreter inputs and
    model-authored proposals never receive a gateway or the BudgetManager.
    """

    def __init__(self, adapter: SyntheticModelAdapter | None, budget: BudgetManager, emit):
        self._adapter, self._budget, self._emit = adapter, budget, emit

    async def invoke(self, operation: str, inputs: object) -> object:
        if self._adapter is None:
            raise ModelCallError("No synthetic model adapter was supplied")
        if operation not in {"normalize_request", "coordinator_plan", "weather_investigation", "ocean_investigation"}:
            raise ModelCallError("Unknown synthetic model operation")
        call_id = str(uuid4())
        try:
            self._budget.reserve(call_id, "model")
        except BudgetError:
            if not self._budget.snapshot().closed:
                self._emit(TraceEventType.INVESTIGATION_LIMIT_REACHED, budget_kind="model", configured_limit=12)
            raise
        details = dict(contract="synthetic_model_dispatch", synthetic_adapter=True,
                       operation=operation, call_id=call_id)
        try:
            self._emit(TraceEventType.CONTRACT_VALIDATED, **details, phase="AUTHORIZED")
            self._budget.dispatch(call_id)
        except BaseException:
            # A required event failure closes/cancels the reservation. There was
            # no dispatch, so no call may be charged or adapter callback run.
            if not self._budget.snapshot().closed:
                self._budget.cancel(call_id)
            raise
        try:
            answer = await wait_for(self._adapter.respond(operation, deepcopy(inputs)),
                                    timeout=ExecutionTimeouts().llm_request_seconds)
            answer = deepcopy(answer)
        except BaseException as error:
            self._budget.finish(call_id, failed=True)
            self._emit(TraceEventType.CONTRACT_VALIDATED, **details, phase="FAILED", valid=False,
                       error_code="MODEL_TIMEOUT" if isinstance(error, TimeoutError) else "MODEL_EXECUTION_FAILED")
            if not isinstance(error, Exception):
                raise
            raise ModelCallError("Synthetic model operation failed") from None
        self._budget.finish(call_id)
        self._emit(TraceEventType.CONTRACT_VALIDATED, **details, phase="RETURNED")
        return answer
