"""Input-package metadata; these fields do not extend application contracts."""

from typing import Self

from pydantic import StrictBool, model_validator

from hawaii_activity_forecaster.models.common import ContractModel, Text, TimeRange, Timestamp, unique
from hawaii_activity_forecaster.models.enums import AgentType, SourceId


class SourceFixture(ContractModel):
    fixture_id: Text
    path: Text
    agent_type: AgentType
    source_id: SourceId


class FixtureManifest(ContractModel):
    fixture_format_version: Text
    fixture_package_version: Text
    schema_version: Text
    policy_version: Text
    synthetic: StrictBool
    reference_time: Timestamp
    target_time_window: TimeRange
    catalog_fixture: Text
    source_fixtures: list[SourceFixture]

    @model_validator(mode="after")
    def structure(self) -> Self:
        if not self.synthetic:
            raise ValueError("fixture input packages must be explicitly synthetic")
        unique([entry.fixture_id for entry in self.source_fixtures], "source fixture IDs")
        unique([entry.path for entry in self.source_fixtures], "source fixture paths")
        return self
