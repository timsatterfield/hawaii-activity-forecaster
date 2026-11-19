"""Actual synthetic trace samples, with no evaluator/oracle access."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path

from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.demo import run_demo
from hawaii_activity_forecaster.models import TraceEvent
from hawaii_activity_forecaster.observability import JsonlTraceWriter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/scenario-pack-v1"


def output(tmp_path, case="advisory"):
    return asyncio.run(run_demo(case, FIXTURES, trace_settings=TraceSettings(directory=tmp_path)))


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def rewrite(path, events):
    """Only tests corrupt/reorder files; application code never rewrites them."""
    events = deepcopy(events)
    for sequence, event in enumerate(events, 1):
        event["sequence_number"] = sequence
    path.write_text("".join(json.dumps(event) + "\n" for event in events))


def writer(tmp_path, first):
    return JsonlTraceWriter(TraceSettings(directory=tmp_path), trace_id=first.trace_id,
        investigation_id=first.details["investigation_id"], session_id=first.details["session_id"],
        request_revision=first.request_revision)


def events(path):
    return [TraceEvent.model_validate(item) for item in records(path)]
