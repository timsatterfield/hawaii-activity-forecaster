"""Investigation-owned model dispatch ledger, independent of environmental calls."""

import asyncio
from collections.abc import Callable
import json
from time import monotonic
from uuid import uuid4

from hawaii_activity_forecaster.config.settings import ExecutionTimeouts
from hawaii_activity_forecaster.models.enums import TraceEventType
from hawaii_activity_forecaster.orchestration.budgets import BudgetError, BudgetManager
from .contracts import InvocationIdentity, Operation, ProposalError, parse_proposal
from .prompts import prepare
from .provider import ModelAdapter, OllamaTransportAdapter, OpenAITransportAdapter, ProviderError
from .errors import ERROR_CODES


class ModelGateway:
    """One shared dispatch boundary for the graph's three model-driven roles.

    The trusted owner supplies the same BudgetManager used by every model operation
    and tool call, a durable emitter, and current-revision predicate. Inputs never
    receive this object. Test emitters remain explicit component seams.
    """

    def __init__(self, *, identity: InvocationIdentity, budget: BudgetManager,
                 adapter: ModelAdapter, emit: Callable,
                 is_current: Callable[[InvocationIdentity], bool]):
        if type(adapter) not in {OpenAITransportAdapter, OllamaTransportAdapter}:
            raise ProviderError("OFFLINE_TRANSPORT_REQUIRED")
        self._identity = InvocationIdentity.model_validate(identity.model_dump())
        self._budget, self._adapter, self._emit = budget, adapter, emit
        self._is_current = is_current
        self._failed = False

    @property
    def identity(self):
        return self._identity

    def _active(self):
        if self._failed or self._budget.snapshot().closed or not self._is_current(self._identity):
            raise ProviderError("MODEL_INVESTIGATION_INACTIVE")

    async def invoke(self, operation: Operation, inputs: object):
        self._active()
        call = prepare(operation, inputs, self._identity, self._adapter.profile_id)
        call_id = str(uuid4())
        details = dict(contract="model_dispatch", synthetic_adapter=False, provider=self._adapter.provider_name,
            execution_mode=self._adapter.execution_mode, profile_id=self._adapter.profile_id,
            model_identifier=self._adapter.model_identifier,
            operation=operation, call_id=call_id, agent_type=call.role,
            template_version=call.template_version, template_digest=call.template_digest,
            schema_digest=call.schema_digest, reserved_cost_microusd=self._adapter.reserved_cost_microusd)
        dispatched = False
        reply = None
        started = monotonic()
        def record(phase, **extra):
            try:
                self._emit(TraceEventType.CONTRACT_VALIDATED, **details, phase=phase, **extra)
            except BaseException:
                self._failed = True
                self._budget.close()
                raise
        try:
            self._budget.reserve(call_id, "model")
        except BudgetError:
            if not self._budget.snapshot().closed:
                try:
                    self._emit(TraceEventType.INVESTIGATION_LIMIT_REACHED, budget_kind="model", configured_limit=12)
                except BaseException:
                    self._failed = True
                    self._budget.close()
                    raise
            raise
        try:
            record("AUTHORIZED")
            def dispatch():
                nonlocal dispatched
                self._active()
                self._budget.dispatch(call_id)
                dispatched = True
                record("DISPATCHED")
            deadline = ExecutionTimeouts().llm_request_seconds
            reply = await asyncio.wait_for(self._adapter.complete(call, dispatch), timeout=deadline)
            if monotonic() - started >= deadline:
                raise ProviderError("MODEL_TIMEOUT")
            self._active()
            proposal = parse_proposal(operation, reply.content, json.loads(call.payload))
        except BaseException as error:
            if dispatched:
                self._budget.finish(call_id, failed=True)
            elif not self._budget.snapshot().closed:
                self._budget.cancel(call_id)
            # A broken sink is already closed; do not obscure its original error.
            if not self._failed:
                code = (str(error) if isinstance(error, (ProviderError, ProposalError)) and str(error) in ERROR_CODES else
                        "MODEL_TIMEOUT" if isinstance(error, TimeoutError) else
                        "MODEL_CANCELLED" if isinstance(error, asyncio.CancelledError) else "MODEL_EXECUTION_FAILED")
                record("FAILED" if dispatched else "CANCELLED", valid=False, error_code=code,
                       duration_ms=max(0, int((monotonic() - started) * 1000)),
                       usage_known=reply is not None and reply.input_tokens is not None,
                       input_token_count=reply.input_tokens if reply else None,
                       output_token_count=reply.output_tokens if reply else None,
                       returned_model_identifier=reply.returned_model if reply else None,
                       provider_request_digest=reply.provider_request_digest if reply else None)
            self._budget.close()
            if not isinstance(error, Exception) or isinstance(error, (ProviderError, ProposalError)):
                if isinstance(error, (ProviderError, ProposalError)) and str(error) not in ERROR_CODES:
                    raise ProviderError("MODEL_EXECUTION_FAILED") from None
                raise
            raise ProviderError("MODEL_EXECUTION_FAILED") from None
        self._budget.finish(call_id)
        record("RETURNED", valid=True, returned_model_identifier=reply.returned_model,
            provider_request_digest=reply.provider_request_digest,
            input_token_count=reply.input_tokens, output_token_count=reply.output_tokens,
            usage_known=reply.input_tokens is not None and reply.output_tokens is not None,
            duration_ms=max(0, int((monotonic() - started) * 1000)))
        return proposal
