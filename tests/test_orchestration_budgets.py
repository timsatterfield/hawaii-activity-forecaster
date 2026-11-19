"""Trusted budget acceptance checks using synthetic invocations only."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from hawaii_activity_forecaster.models.enums import AgentType
from hawaii_activity_forecaster.orchestration import BudgetError, BudgetManager


@pytest.mark.parametrize("kind", ["tool", "model"])
def test_concurrent_reservations_cannot_oversubscribe(kind):
    budget = BudgetManager()
    barrier = Barrier(16)

    def invoke(number):
        barrier.wait()
        try:
            budget.reserve(str(number), kind)
        except BudgetError:
            return False
        budget.dispatch(str(number))
        budget.finish(str(number), failed=True, retryable=True)
        return True

    with ThreadPoolExecutor(max_workers=16) as pool:
        assert sum(pool.map(invoke, range(16))) == 12
    snapshot = budget.snapshot()
    assert getattr(snapshot, f"{kind}_calls") == 12
    with pytest.raises(BudgetError, match="limit"):
        budget.reserve("thirteenth", kind)
    other = "model" if kind == "tool" else "tool"
    budget.reserve("independent", other)
    budget.dispatch("independent")
    assert getattr(budget.snapshot(), f"{other}_calls") == 1


def test_pending_reservations_consume_capacity_but_cancelled_work_does_not_count():
    budget = BudgetManager()
    for number in range(12):
        budget.reserve(str(number), "tool")
    assert budget.snapshot().tool_calls == 0
    assert budget.snapshot().reserved_tool_calls == 12
    with pytest.raises(BudgetError):
        budget.reserve("extra", "tool")
    budget.cancel("0")
    budget.reserve("replacement", "tool")
    budget.dispatch("replacement")
    with pytest.raises(BudgetError):
        budget.cancel("replacement")
    with pytest.raises(BudgetError):
        budget.reserve("0", "tool")
    assert budget.snapshot().tool_calls == 1


def failed_call(budget, call_id, **recovery):
    budget.reserve(call_id, "tool", **recovery)
    budget.dispatch(call_id)
    budget.finish(call_id, failed=True, retryable=True)


def test_retry_and_fallback_are_scoped_and_consume_shared_calls():
    budget = BudgetManager()
    failed_call(budget, "first")
    failed_call(budget, "retry", retry_of="first")
    with pytest.raises(BudgetError, match="exhausted"):
        budget.reserve("second-retry", "tool", retry_of="first")
    with pytest.raises(BudgetError, match="original"):
        budget.reserve("retry-of-retry", "tool", retry_of="retry")
    failed_call(budget, "fallback", fallback_gap="gap-1")
    with pytest.raises(BudgetError, match="fallback allowance"):
        budget.reserve("fallback-2", "tool", fallback_gap="gap-1")
    failed_call(budget, "fallback-retry", retry_of="fallback")
    failed_call(budget, "different-fallback", fallback_gap="gap-2")
    assert budget.snapshot().tool_calls == 5
    assert budget.snapshot().retries == 2
    assert budget.snapshot().fallbacks == 2


@pytest.mark.parametrize("recovery", [
    {"retry_of": "missing"}, {"fallback_gap": ""},
    {"retry_of": "missing", "fallback_gap": "gap"},
])
def test_invalid_recovery_is_denied(recovery):
    with pytest.raises(BudgetError):
        BudgetManager().reserve("call", "tool", **recovery)


def test_only_retryable_failed_originals_can_retry():
    budget = BudgetManager()
    budget.reserve("pending", "tool")
    with pytest.raises(BudgetError):
        budget.reserve("retry-pending", "tool", retry_of="pending")
    budget.dispatch("pending")
    budget.finish("pending", failed=True, retryable=False)
    with pytest.raises(BudgetError):
        budget.reserve("retry-permanent", "tool", retry_of="pending")
    with pytest.raises(BudgetError):
        budget.reserve("model-retry", "model", retry_of="pending")


def test_cancelled_recovery_does_not_consume_attempt_allowance():
    budget = BudgetManager()
    failed_call(budget, "original")
    budget.reserve("unused", "tool", retry_of="original")
    budget.cancel("unused")
    failed_call(budget, "actual-retry", retry_of="original")
    assert budget.snapshot().retries == 1


def test_recovery_does_not_bypass_total_tool_limit():
    budget = BudgetManager()
    for number in range(12):
        failed_call(budget, str(number))
    with pytest.raises(BudgetError):
        budget.reserve("retry", "tool", retry_of="0")
    with pytest.raises(BudgetError):
        budget.reserve("fallback", "tool", fallback_gap="gap")


def test_one_slot_per_specialist_and_release_on_failure():
    budget = BudgetManager()
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with budget.specialist_slot(AgentType.WEATHER):
            with budget.specialist_slot(AgentType.OCEAN):
                assert budget.snapshot().active_specialists == 2
                with pytest.raises(BudgetError):
                    with budget.specialist_slot(AgentType.WEATHER):
                        pass
                raise RuntimeError("synthetic failure")
    assert budget.snapshot().active_specialists == 0
    with pytest.raises(BudgetError):
        with budget.specialist_slot("ADDITIONAL_AGENT"):
            pass


def test_five_cycles_close_and_independent_investigation():
    budget = BudgetManager()
    assert [budget.begin_iteration() for _ in range(5)] == [1, 2, 3, 4, 5]
    with pytest.raises(BudgetError):
        budget.begin_iteration()
    budget.reserve("pending", "model")
    budget.reserve("active", "tool")
    budget.dispatch("active")
    budget.close()
    budget.close()
    budget.finish("active", failed=True)  # Late completion counts, never reopens.
    assert budget.snapshot().tool_calls == 1
    assert budget.snapshot().reserved_model_calls == 0
    for action in (lambda: budget.begin_iteration(),
                   lambda: budget.reserve("new", "tool"),
                   lambda: budget.dispatch("pending")):
        with pytest.raises(BudgetError):
            action()
    assert BudgetManager().begin_iteration() == 1


@pytest.mark.parametrize("operation", ["dispatch", "finish", "cancel"])
def test_invalid_call_transitions(operation):
    budget = BudgetManager()
    with pytest.raises(BudgetError, match="unknown"):
        getattr(budget, operation)("unknown")
    budget.reserve("call", "tool")
    with pytest.raises(BudgetError):
        budget.finish("call")
    budget.dispatch("call")
    with pytest.raises(BudgetError):
        budget.dispatch("call")
