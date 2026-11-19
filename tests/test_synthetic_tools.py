"""SH-T07..10, CFG and tool contract execution checks with synthetic inputs only."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone
from threading import Barrier

import pytest

from hawaii_activity_forecaster.harness.synthetic import ScriptDispatchError, SyntheticDriver
from hawaii_activity_forecaster.orchestration import BudgetManager
from hawaii_activity_forecaster.tools.synthetic import SyntheticToolDispatcher, ToolPlanError
from specialist_samples import NOW, request
from tool_samples import action, inputs, operation


def setup(data=None, parent=None, emit=None, budget=None):
    parent = parent or request()
    budget = budget or BudgetManager()
    driver = SyntheticDriver(data or inputs())
    events = []
    dispatcher = SyntheticToolDispatcher(
        driver, budget, investigation_id=parent.investigation_id, request_revision=parent.request_revision,
        reference_time=NOW, emit=emit if emit is not None else lambda event, **details: events.append((event, details)),
    )
    return dispatcher, parent, budget, driver, events


def execute(dispatcher, parent, actions):
    dispatcher.register(parent, actions)
    return asyncio.run(dispatcher.run(parent))


@pytest.mark.parametrize("behavior", ["SUCCESS", "PARTIAL", "UNAVAILABLE", "ERROR", "TIMEOUT", "MALFORMED", "DUPLICATE"])
def test_scripted_behaviors_consume_one_actual_invocation_and_preserve_pending_evidence(behavior):
    data = inputs(operation(behaviors=(behavior,)))
    before = data.model_dump_json(exclude_unset=True)
    dispatcher, parent, budget, driver, events = setup(data)
    result = execute(dispatcher, parent, (action(),))
    assert budget.snapshot().tool_calls == 1
    assert budget.snapshot().model_calls == 0
    assert len(driver.bindings) == 1
    assert data.model_dump_json(exclude_unset=True) == before
    if behavior in {"SUCCESS", "PARTIAL", "DUPLICATE"}:
        assert len(result.findings) == 1
        found = result.findings[0]
        assert found.validation_status == "PENDING"
        assert found.finding_id != "WEATHER-finding"
        assert found.investigation_id == parent.investigation_id
        assert found.coverage_type == "REGIONAL" and found.beach_id is None
        assert found.retrieved_at == NOW
        assert driver.bindings[0].findings[0].runtime_finding_id == found.finding_id
    else:
        assert not result.findings
        assert result.unresolved_gaps
    if behavior == "DUPLICATE":
        assert events[-1][1]["delivery_count"] == 3
    if behavior == "TIMEOUT":
        assert result.errors[0].error_code == "SOURCE_TIMEOUT"
        assert events[-1][1]["elapsed_ms"] == 10000
        assert events[-1][1]["virtual_completed_at"] == (NOW + timedelta(seconds=10)).isoformat()
        assert not driver.bindings[0].findings
    if behavior == "MALFORMED":
        assert result.errors[0].error_code == "SOURCE_RESPONSE_INVALID"


def test_exact_deadline_is_timely_and_fresh_materializations_get_unique_bindings():
    data = inputs(operation(durations=(10000,)), operation(op_id="other", zone="OTHER", durations=(1,)))
    dispatcher, parent, budget, driver, _ = setup(data)
    result = execute(dispatcher, parent, (action(), action("other", zone="OTHER")))
    assert len(result.findings) == 2
    assert len({f.finding_id for f in result.findings}) == 2
    assert len({b.runtime_tool_call_id for b in driver.bindings}) == 2
    assert budget.snapshot().tool_calls == 2
    assert not result.errors


def test_retry_requires_explicit_plan_and_counts_separately_from_specialist_attempt():
    data = inputs(operation(behaviors=("TIMEOUT", "SUCCESS")))
    dispatcher, parent, budget, driver, _ = setup(data)
    result = execute(dispatcher, parent, (action(),))
    assert len(driver.bindings) == 1  # Available second attempt did not cause a retry.
    dispatcher, parent, budget, driver, _ = setup(data)
    result = execute(dispatcher, parent, (action(), action("retry", retry_of="main")))
    assert result.attempt_number == parent.attempt_number == 1
    assert budget.snapshot().tool_calls == 2 and budget.snapshot().retries == 1
    assert [b.attempt for b in driver.bindings] == [1, 2]
    assert len(result.findings) == 1
    assert result.errors[0].error_code == "SOURCE_TIMEOUT"  # Failure history is preserved.
    assert not result.unresolved_gaps


def test_success_skips_planned_recovery_and_partial_preserves_available_work():
    dispatcher, parent, budget, driver, _ = setup()
    execute(dispatcher, parent, (action(), action("retry", retry_of="main")))
    assert budget.snapshot().tool_calls == 1
    dispatcher, parent, budget, driver, _ = setup(inputs(operation(behaviors=("PARTIAL",))))
    result = execute(dispatcher, parent, (action(), action("retry", retry_of="main")))
    assert budget.snapshot().tool_calls == 1
    assert result.findings and result.unresolved_gaps


def test_required_gap_fallback_is_explicit_bounded_and_can_have_its_own_retry():
    data = inputs(operation(behaviors=("ERROR",)), operation(op_id="alternate", source="HWT_WIND", behaviors=("TIMEOUT", "SUCCESS")))
    dispatcher, parent, budget, driver, _ = setup(data)
    result = execute(dispatcher, parent, (
        action(), action("alternate", source="HWT_WIND", fallback_of="main"),
        action("retry-alternate", source="HWT_WIND", retry_of="alternate"),
    ))
    assert budget.snapshot().tool_calls == 3
    assert budget.snapshot().fallbacks == 1 and budget.snapshot().retries == 1
    assert len(result.findings) == 1 and not result.unresolved_gaps
    assert [b.attempt for b in driver.bindings] == [1, 1, 2]


@pytest.mark.parametrize("bad", [
    lambda: action(source="NWS_MARINE"),
    lambda: action(categories=("WATER_QUALITY_ADVISORY_CHECK",)),
    lambda: action("retry", retry_of="missing"),
    lambda: action("retry", source="HWT_WIND", retry_of="main"),
    lambda: action("fallback", fallback_of="main"),
])
def test_invalid_source_or_recovery_is_blocked_before_any_dispatch(bad):
    dispatcher, parent, budget, driver, _ = setup()
    with pytest.raises(ToolPlanError):
        dispatcher.register(parent, (action(), bad()))
    assert budget.snapshot().tool_calls == 0
    assert not driver.bindings


def test_retry_of_retry_is_not_a_new_original_and_script_excess_does_not_dispatch():
    dispatcher, parent, budget, driver, _ = setup(inputs(operation(behaviors=("ERROR", "ERROR"))))
    with pytest.raises(ToolPlanError):
        dispatcher.register(parent, (action(), action("r", retry_of="main"), action("rr", retry_of="r")))
    assert not driver.bindings
    dispatcher.register(parent, (action(), action("unlabelled-second-original")))
    with pytest.raises(ScriptDispatchError):
        asyncio.run(dispatcher.run(parent))
    assert budget.snapshot().tool_calls == 1


def test_unmatched_geographic_scope_does_not_consume_script_or_budget():
    dispatcher, parent, budget, driver, _ = setup()
    dispatcher.register(parent, (action(zone="UNAUTHORIZED_ZONE"),))
    with pytest.raises(ScriptDispatchError):
        asyncio.run(dispatcher.run(parent))
    assert not driver.bindings and budget.snapshot().tool_calls == 0


def test_same_semantic_gap_cannot_refresh_fallback_allowance_by_renaming_requests():
    data = inputs(operation(behaviors=("ERROR",)), operation(op_id="alternate", source="HWT_WIND", behaviors=("ERROR",)),
                  operation(op_id="second-primary", zone="SECOND", behaviors=("ERROR",)),
                  operation(op_id="second-alternate", source="HWT_WIND", zone="SECOND", behaviors=("ERROR",)))
    dispatcher, parent, budget, driver, _ = setup(data)
    execute(dispatcher, parent, (action(), action("alternate", source="HWT_WIND", fallback_of="main")))
    shifted = {
        "start": parent.target_time_window.start.astimezone(timezone(timedelta(hours=-10))),
        "end": parent.target_time_window.end.astimezone(timezone(timedelta(hours=-10))),
    }
    second = request(request_id="renamed-delegation", target_time_window=shifted)
    result = execute(dispatcher, second, (action("other", zone="SECOND"),
                                        action("other-alt", source="HWT_WIND", zone="SECOND", fallback_of="other")))
    assert budget.snapshot().fallbacks == 1
    assert budget.snapshot().tool_calls == 3
    assert any(error.error_code == "EXECUTION_LIMIT_REACHED" for error in result.errors)


def test_budget_exhaustion_preserves_previous_findings_and_does_not_advance_script():
    budget = BudgetManager()
    for number in range(11):
        budget.reserve(f"previous-{number}", "tool")
        budget.dispatch(f"previous-{number}")
        budget.finish(f"previous-{number}")
    dispatcher, parent, _, driver, _ = setup(inputs(operation(), operation(op_id="second", zone="SECOND")), budget=budget)
    result = execute(dispatcher, parent, (action(), action("second", zone="SECOND")))
    assert budget.snapshot().tool_calls == 12
    assert len(driver.bindings) == 1 and len(result.findings) == 1
    assert any(error.error_code == "EXECUTION_LIMIT_REACHED" for error in result.errors)


@pytest.mark.parametrize("failure_at", ["TOOL_CALLED", "TOOL_COMPLETED"])
def test_trace_failure_closes_execution_and_never_refunds_dispatched_calls(failure_at):
    def emit(event, **details):
        if event == failure_at:
            raise OSError("synthetic trace failure")
    dispatcher, parent, budget, driver, _ = setup(emit=emit)
    dispatcher.register(parent, (action(),))
    with pytest.raises(OSError):
        asyncio.run(dispatcher.run(parent))
    assert budget.snapshot().closed
    assert budget.snapshot().reserved_tool_calls == 0
    assert budget.snapshot().tool_calls == (0 if failure_at == "TOOL_CALLED" else 1)


def test_concurrent_dispatches_share_cap_and_do_not_consume_uninvoked_operations():
    budget = BudgetManager()
    for index in range(11):
        budget.reserve(str(index), "tool")
        budget.dispatch(str(index))
        budget.finish(str(index))
    dispatcher, parent, _, driver, _ = setup(inputs(operation(), operation(op_id="other", zone="OTHER")), budget=budget)
    other = request(request_id="other")
    dispatcher.register(parent, (action(),))
    dispatcher.register(other, (action("other", zone="OTHER"),))
    barrier = Barrier(2)
    def run(p):
        barrier.wait()
        return asyncio.run(dispatcher.run(p))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (parent, other)))
    assert budget.snapshot().tool_calls == 12
    assert len(driver.bindings) == 1
    assert sorted(len(r.findings) for r in results) == [0, 1]


def test_optional_gap_cannot_authorize_fallback_and_closed_execution_cannot_dispatch():
    optional = request(requested_evidence=[dict(requirement_id="wind", evidence_type="WIND_CONDITIONS", priority="OPTIONAL")])
    dispatcher, parent, budget, driver, _ = setup(parent=optional)
    with pytest.raises(ToolPlanError):
        dispatcher.register(parent, (action(), action("fallback", source="HWT_WIND", fallback_of="main")))
    dispatcher.register(parent, (action(),))
    dispatcher.close()
    with pytest.raises(ToolPlanError):
        asyncio.run(dispatcher.run(parent))
    assert not driver.bindings and budget.snapshot().tool_calls == 0


def test_driver_snapshots_templates_and_preserves_offshore_context():
    from hawaii_activity_forecaster.models import EnvironmentalFinding
    data = inputs(operation(source="NDBC", role="OCEAN", categories=("SURF_WAVE_CONDITIONS",)))
    template = data.source_responses["NDBC-SUCCESS"]
    template.findings[0] = EnvironmentalFinding.model_validate(template.findings[0].model_dump() | {
        "coverage_type": "OFFSHORE", "coverage_id": "SYNTHETIC_BUOY", "beach_id": None,
    })
    dispatcher, parent, budget, driver, _ = setup(data, parent=request("OCEAN"))
    original = template.findings[0].model_dump()
    template.findings.clear()  # Mutating caller-owned input cannot rewrite the driver snapshot.
    result = execute(dispatcher, parent, (action(source="NDBC", categories=("SURF_WAVE_CONDITIONS",)),))
    found = result.findings[0]
    actual = found.model_dump()
    for key in original:
        if key not in {"finding_id", "investigation_id", "validation_status"}:
            assert actual[key] == original[key]
    assert found.coverage_type == "OFFSHORE" and found.beach_id is None


def test_out_of_scope_material_is_rejected_after_dispatch_and_never_becomes_evidence():
    from hawaii_activity_forecaster.models import EnvironmentalFinding
    data = inputs()
    source = data.source_responses["NWS_WEATHER-SUCCESS"]
    source.findings[0] = EnvironmentalFinding.model_validate(source.findings[0].model_dump() | {
        "coverage_type": "BEACH", "beach_id": "TEST_BEACH_B",
    })
    dispatcher, parent, budget, driver, _ = setup(data)
    result = execute(dispatcher, parent, (action(),))
    assert budget.snapshot().tool_calls == 1
    assert not result.findings
    assert result.errors[0].error_code == "SOURCE_RESPONSE_INVALID"
