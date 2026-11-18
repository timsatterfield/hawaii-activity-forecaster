"""Beach records and source attribution (03, section 2)."""

from decimal import Decimal
from typing import Annotated, Self

from pydantic import ConfigDict, Field, RootModel, model_validator

from .common import CalendarDate, ContractModel, JsonObject, Text, unique
from .enums import Activity, CatalogStatus, LifeguardStatus, ReefPresence, Region


class SourceReference(ContractModel):
    source_id: Text
    publisher: Text
    url: Text
    title: Text | None = None
    accessed_at: CalendarDate
    supports_fields: list[Text]
    notes: Text | None = None


class BeachRecord(ContractModel):
    beach_id: Text
    name: Text
    aliases: list[Text] | None = None
    region: Region
    locality: Text
    latitude: Annotated[Decimal, Field(ge=-90, le=90)]
    longitude: Annotated[Decimal, Field(ge=-180, le=180)]
    location_notes: Text | None = None
    # Controlled vocabularies are unresolved; do not invent allowed categories.
    shoreline_orientation: Text | None = None
    coastline_exposure: list[JsonObject] | None = None
    shore_type: Text | list[Text] | None = None
    entry_characteristics: list[JsonObject] | None = None
    reef_presence: ReefPresence | None = None
    reef_notes: Text | None = None
    access_notes: Text | None = None
    supported_activities: list[Activity]
    lifeguard_status: LifeguardStatus
    lifeguard_notes: Text | None = None
    known_hazards: list[JsonObject] | None = None
    activity_notes: list[JsonObject] | None = None
    sources: list[SourceReference]
    last_verified: CalendarDate
    catalog_status: CatalogStatus
    verification_notes: Text | None = None


class BeachCatalog(RootModel[list[BeachRecord]]):
    """JSON array of beach records; no invented catalog envelope metadata."""

    model_config = ConfigDict(frozen=True, revalidate_instances="always")

    @model_validator(mode="after")
    def unique_beaches(self) -> Self:
        unique([beach.beach_id for beach in self.root], "beach IDs (BC-001)")
        return self
