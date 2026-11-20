"""Process-local natural-language session, preserving existing lifecycle checks."""

from .execution import run_agent_investigation
from .data import ReleaseData
from .runtime import AgentRuntime
from hawaii_activity_forecaster.config import TraceSettings
from hawaii_activity_forecaster.model_runtime.provider import ModelAdapter
from hawaii_activity_forecaster.orchestration import SessionManager, SkeletonReport


class AgentSession:
    def __init__(self, data: ReleaseData, adapter: ModelAdapter, *,
                 trace_settings: TraceSettings | None = None, max_investigations: int = 3):
        if type(max_investigations) is not int or not 1 <= max_investigations <= 10:
            raise ValueError("A synthetic release run permits one to ten investigations")
        self.data, self.adapter, self.trace_settings = data, adapter, trace_settings
        self.manager = SessionManager()
        self._limit = max_investigations
        self._admissions = 0

    async def ask(self, text: str) -> SkeletonReport:
        if self._admissions >= self._limit:
            raise ValueError("The configured investigation allowance is exhausted")
        self._admissions += 1

        async def execute(admission):
            return await run_agent_investigation(admission,
                runtime=AgentRuntime(self.adapter, self.data.options), driver_inputs=self.data.driver,
                policy=self.data.policy, trace_settings=self.trace_settings)
        if self._admissions == 1:
            return await self.manager.start_raw(text, catalog=self.data.catalog,
                reference_time=self.data.reference_time, run=execute)
        return await self.manager.follow_up_raw(text, catalog=self.data.catalog,
            reference_time=self.data.reference_time, run=execute)

    def close(self) -> None:
        self.manager.close()
