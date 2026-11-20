"""Preflight → isolated runtime → verified capture → independent reporting.

The runtime is either an authored component or the model-driven agent runtime.
Neither receives a LoadedScenario, expected file, evaluator object or artifact
digest. The evaluator, not the caller, decides from each verified trace whether a
capture came from a genuine model target; only those can yield scenario PASS.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal

from hawaii_activity_forecaster.config import load_config
from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.fixtures import FixtureLoadError
from .contracts import DriverInputs
from .policy import PolicyConfiguration
from .loading import load_scenario
from .evaluation import (
    CaptureError, EvaluationReport, Outcome, capture_report, evaluate_assertions, evaluate_loaded,
)

if TYPE_CHECKING:
    from hawaii_activity_forecaster.orchestration import RawSessionRequest, SkeletonReport


@dataclass(frozen=True)
class ComponentExecutionInput:
    admission: RawSessionRequest
    request_step: int
    trace_settings: TraceSettings
    _driver: bytes = field(repr=False)
    _policy: bytes = field(repr=False)

    @property
    def driver_inputs(self) -> DriverInputs:
        return DriverInputs.model_validate_json(self._driver)

    @property
    def policy(self) -> PolicyConfiguration:
        return PolicyConfiguration.model_validate_json(self._policy)


Mode = Literal["AUTHORED_COMPONENT", "AGENT_RUNTIME"]


@dataclass(frozen=True)
class ExecutionEvaluation:
    outcome: Outcome
    mode: Mode
    attempted_steps: tuple[int, ...]
    component: EvaluationReport | None
    scenario: EvaluationReport
    execution_modes: tuple[str, ...] = ()
    tool_allowlist_digest: str | None = None


ComponentRunner = Callable[[ComponentExecutionInput], Awaitable["SkeletonReport"]]


def _failure(scenario_id, category):
    return EvaluationReport(scenario_id, "SCENARIO", "FAIL", category, (),
                            {key: 0 for key in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")})


async def execute_scenario(root, scenario_id, *, runtime: ComponentRunner | None = None,
                           trace_settings: TraceSettings | None = None,
                           mode: Mode = "AUTHORED_COMPONENT") -> ExecutionEvaluation:
    """Execute an explicitly supplied runtime after complete preflight.

    Missing runtime is BLOCKED; failures after admission are FAIL. Oracle snapshots
    are loaded once and remain solely on this evaluator/harness side of the seam.
    """
    from hawaii_activity_forecaster.orchestration.session import SessionManager
    try:
        loaded = load_scenario(root, scenario_id)
    except FixtureLoadError:
        result = _failure(scenario_id, "FIXTURE_INVALID")
        return ExecutionEvaluation(result.outcome, mode, (), None, result)
    except Exception:
        result = _failure(scenario_id, "EVALUATOR_ERROR")
        return ExecutionEvaluation(result.outcome, mode, (), None, result)
    if loaded.definition.test_status != "ACTIVE" or runtime is None:
        result = evaluate_loaded(loaded)
        return ExecutionEvaluation(result.outcome, mode, (), None, result)

    captures, attempted = [], []
    failure = None
    session = SessionManager()
    application, driver = loaded.application, loaded.driver
    try:
        settings = TraceSettings.model_validate((trace_settings or load_config().trace).model_dump())
        for step in driver.script.requests:
            async def run(admission):
                attempted.append(step.request_step)
                inputs = ComponentExecutionInput(admission, step.request_step, settings,
                    driver.model_dump_json(exclude_unset=True).encode(), application.policy_configuration.model_dump_json().encode())
                return await runtime(inputs)
            if step.request_step == 1:
                report = await session.start_raw(step.user_request, catalog=application.catalog,
                                                reference_time=step.reference_time, run=run)
            else:
                report = await session.follow_up_raw(step.user_request, catalog=application.catalog,
                                                    reference_time=step.reference_time, run=run)
            captures.append(capture_report(step.request_step, report, catalog=application.catalog,
                            policy=application.policy_configuration, driver_inputs=driver))
            if report.state.status == "FAILED":
                failure = "APPLICATION_FAILURE"
                break
    except CaptureError:
        failure = "CAPTURE_INVALID"
    except Exception:
        failure = "APPLICATION_FAILURE"
    finally:
        session.close()
    try:
        component = evaluate_assertions(loaded.evaluator.expected_results, tuple(captures))
        result = evaluate_loaded(loaded, captures=tuple(captures))
        modes = tuple(c.execution_mode for c in captures)
        # A declared mode must agree with what the verified traces recorded.
        if not failure and any((m == "AUTHORED_COMPONENT") != (mode == "AUTHORED_COMPONENT") for m in modes):
            failure = "CAPTURE_CONTEXT_MISMATCH"
        if failure:
            component = replace(component, outcome="FAIL", category=failure)
            result = replace(result, outcome="FAIL", category=failure)
    except Exception:
        component, result, modes = None, _failure(scenario_id, "EVALUATOR_ERROR"), ()
    return ExecutionEvaluation(result.outcome, mode, tuple(attempted), component, result, modes)
