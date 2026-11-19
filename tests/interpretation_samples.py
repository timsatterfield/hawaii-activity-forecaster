"""Authored synthetic proposals; expected values never come from the validator."""

from datetime import datetime
from pathlib import Path

from hawaii_activity_forecaster.fixtures import load_fixture_inputs
from hawaii_activity_forecaster.interpretation import RequestContext

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = datetime.fromisoformat("2026-11-16T09:00:00-10:00")


def context(text, **kwargs):
    values = dict(original_request=text, reference_time=REFERENCE, catalog=load_fixture_inputs(ROOT / "fixtures").catalog,
                  session_id="synthetic-session", investigation_id="synthetic-investigation", request_revision=1)
    return RequestContext(**(values | kwargs))


def window(day="2026-11-17", start="08:00", end="11:00"):
    return {"start": day + "T" + start + ":00-10:00", "end": day + "T" + end + ":00-10:00"}


def span(text, fragment, **kwargs):
    start = text.index(fragment)
    return dict(start=start, end=start + len(fragment), **kwargs)


def proposal(text, changes, supports, *, removed=(), unresolved=()):
    return dict(changed_values=changes, source_spans=[span(text, fragment, field=name) for name, fragment in supports.items()],
                removed_entries=list(removed), unresolved_spans=[span(text, fragment) for fragment in unresolved])


def morning(text="Snorkel tomorrow morning near Kihei.", **kwargs):
    return context(text, **kwargs), proposal(text, {
        "activity": "SNORKELING", "target_date": "2026-11-17", "target_time_window": window(), "preferred_area": "Kihei",
    }, {"activity": "Snorkel", "target_date": "tomorrow", "target_time_window": "morning", "preferred_area": "near Kihei"})
