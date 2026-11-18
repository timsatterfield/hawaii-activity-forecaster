"""Harness definitions and deliberately separate application/driver/evaluator views."""

from typing import Literal, Self

from pydantic import Field, model_validator

from hawaii_activity_forecaster.fixtures.manifest import FixtureManifest
from hawaii_activity_forecaster.models import BeachCatalog, EnvironmentalToolResponse
from hawaii_activity_forecaster.models.common import ContractModel, JsonValue, Text, Timestamp, unique
from hawaii_activity_forecaster.models.enums import AgentType

from .assertions import ExpectedResults
from .behavior import BehaviorScript
from .policy import PolicyConfiguration, Version


class ScenarioRegistration(ContractModel):
    scenario_id: Text
    path: Text


class HarnessManifest(FixtureManifest):
    harness_contract_version: Text
    scenarios: list[ScenarioRegistration] = Field(min_length=1)

    @model_validator(mode="after")
    def registrations(self) -> Self:
        unique([s.scenario_id for s in self.scenarios], "scenario IDs")
        unique([s.path for s in self.scenarios], "scenario paths")
        return self


class SourceSet(ContractModel):
    harness_contract_version: Version
    agent_type: AgentType
    source_fixture_ids: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        unique(self.source_fixture_ids, "source set IDs")
        return self


class ExpectedReference(ContractModel):
    path: Text


class BehaviorReference(ContractModel):
    script: Text


class ScenarioFile(ContractModel):
    scenario_id: Text
    description: Text
    requirement_ids: list[Text] = Field(min_length=1)
    user_request: Text
    reference_time: Timestamp
    catalog_fixture: Text
    weather_fixture: Text | None = None
    ocean_fixture: Text | None = None
    tool_behavior: BehaviorReference | None = None
    policy_configuration: Text
    expected_results: ExpectedReference
    test_status: Literal["ACTIVE", "BLOCKED", "DISABLED"]

    @model_validator(mode="after")
    def requirements(self) -> Self:
        unique(self.requirement_ids, "scenario requirement IDs")
        return self


class TestScenario(ScenarioFile):
    """The logical harness-owned record; never given to application/model code."""
    expected_results: ExpectedResults

    @model_validator(mode="after")
    def matching_oracle(self) -> Self:
        if self.expected_results.scenario_id != self.scenario_id:
            raise ValueError("expected results belong to a different scenario")
        covered = {rid for a in self.expected_results.assertions if a.mandatory for rid in a.requirement_ids}
        if not set(self.requirement_ids) <= covered:
            raise ValueError("scenario requirements need independent mandatory assertion coverage")
        return self


class ApplicationInputs(ContractModel):
    """Only user input, clock, catalog and approved synthetic policy configuration."""
    user_request: Text
    reference_time: Timestamp
    catalog: BeachCatalog
    policy_configuration: PolicyConfiguration


class DriverInputs(ContractModel):
    """Trusted test-driver configuration, never Coordinator/specialist model context."""
    script: BehaviorScript
    source_responses: dict[str, EnvironmentalToolResponse]
    malformed_responses: dict[str, JsonValue]


class EvaluatorInputs(ContractModel):
    expected_results: ExpectedResults
    artifact_digests: dict[Text, Text]


class ExecutionReadiness(ContractModel):
    outcome: Literal["BLOCKED", "NOT_RUN"]
    reason: Text
