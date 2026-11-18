"""Validated M1 configuration, governed by m1-configuration-baseline.md.

These models describe settings, not runtime counters, permissions, or dispatch.
"""

from pathlib import Path
import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

from hawaii_activity_forecaster.models.common import Text


class ConfigurationModel(BaseModel):
    """Reject unknown/coerced settings and validate nested defaults and instances."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_default=True,
        revalidate_instances="always", hide_input_in_errors=True,
    )


class InvestigationLimits(ConfigurationModel):
    """CFG §§6/7: approved maxima, with scope explicit in each setting name.

    A revised baseline is required to change these values. No counters live here.
    """

    max_coordinator_iterations: StrictInt = Field(default=5, ge=5, le=5)
    max_environmental_tool_invocations: StrictInt = Field(default=12, ge=12, le=12)
    max_retries_per_failed_invocation: StrictInt = Field(default=1, ge=1, le=1)
    max_fallback_attempts_per_evidence_gap: StrictInt = Field(default=1, ge=1, le=1)
    max_concurrent_specialists: StrictInt = Field(default=2, ge=2, le=2)
    max_recommendations: StrictInt = Field(default=3, ge=3, le=3)
    max_llm_invocations: StrictInt = Field(default=12, ge=12, le=12)


class ExecutionTimeouts(ConfigurationModel):
    """CFG §§7/8: approved per-invocation timeouts, expressed in seconds."""

    llm_request_seconds: StrictInt = Field(default=30, ge=30, le=30)
    synthetic_tool_seconds: StrictInt = Field(default=10, ge=10, le=10)


class EnvironmentalSettings(ConfigurationModel):
    """Live environmental retrieval has no enabled mode in M1."""

    mode: Literal["synthetic"] = "synthetic"


class LLMSettings(ConfigurationModel):
    """Provider-neutral settings; credentials are not configuration fields."""

    enabled: StrictBool = False
    provider: Text | None = None
    model_identifier: Text | None = None

    @model_validator(mode="after")
    def activation_boundary(self) -> Self:
        if self.enabled:
            if self.provider is None or self.model_identifier is None:
                raise ValueError("model execution requires explicit provider and model_identifier (CFG-T14)")
            raise ValueError("real-model execution is unavailable pending provider activation review and integration")
        return self


class TraceSettings(ConfigurationModel):
    """Local trace configuration; filesystem checks and writes occur later."""

    directory: Path = Path("traces")
    format: Literal["jsonl"] = "jsonl"
    write_failure_policy: Literal["fail_closed"] = "fail_closed"

    @field_validator("directory", mode="before")
    @classmethod
    def local_path(cls, value: object) -> str | Path:
        if not isinstance(value, (str, Path)):
            raise ValueError("trace directory must be a local path")
        path = str(value)
        if not path.strip() or "\x00" in path or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", path):
            raise ValueError("trace directory must be a nonempty local filesystem path")
        return value


class LangSmithSettings(ConfigurationModel):
    """An explicit opt-in setting only; this increment installs no integration.

    Enabling this flag does not transmit data or replace the required review of
    tracing credentials, costs, sanitization, and data handling (CFG §10.2).
    """

    enabled: StrictBool = False


class AppConfig(ConfigurationModel):
    limits: InvestigationLimits = Field(default_factory=InvestigationLimits)
    timeouts: ExecutionTimeouts = Field(default_factory=ExecutionTimeouts)
    environment: EnvironmentalSettings = Field(default_factory=EnvironmentalSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    trace: TraceSettings = Field(default_factory=TraceSettings)
    langsmith: LangSmithSettings = Field(default_factory=LangSmithSettings)
