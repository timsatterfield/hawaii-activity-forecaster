"""Source domains from requirements 04 §13; no retrieval or evidence approval."""

from .enums import SourceId

WEATHER_SOURCES = frozenset({
    SourceId.NWS_WEATHER, SourceId.NWS_ALERTS, SourceId.HWT_WIND, SourceId.HWT_NARRATIVE,
})
OCEAN_SOURCES = frozenset({
    SourceId.NWS_MARINE, SourceId.HI_DOH_CWB, SourceId.NDBC,
    SourceId.SNORKEL_STORE, SourceId.HWT_VISIBILITY, SourceId.HWT_SURF,
})
