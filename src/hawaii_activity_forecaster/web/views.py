"""Read-only trace and evidence-package views for the local web interface.

Every value comes from an existing validated record: a JSONL trace checked by
``inspect_trace`` or the published evidence manifest. Nothing is reconstructed,
scored or inferred here; this module only reshapes stored fields for display.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hawaii_activity_forecaster.observability import inspect_trace, read_trace

_GROUPS = (
    ("tool", ("AGENT_", "TOOL_", "RETRY_", "FALLBACK_")),
    ("evidence", ("EVIDENCE_",)),
    ("safety", ("POLICY_", "CANDIDATE_", "RESULT_", "CONTRACT_")),
)
_SUMMARY_KEYS = ("agent_type", "tool_name", "beach_id", "error_code", "validation_status", "contract",
                 "reason", "outcome", "final_status", "completion_reason", "stop_reason")
_FIELD_LIMIT = 400


def _group(event_type: str) -> str:
    for name, prefixes in _GROUPS:
        if event_type.startswith(prefixes):
            return name
    return "lifecycle"


def _compact(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    return text if len(text) <= _FIELD_LIMIT else text[:_FIELD_LIMIT] + " …"


def _summary(event_type: str, details: dict) -> str:
    parts = [f"{key}={details[key]}" for key in _SUMMARY_KEYS
             if isinstance(details.get(key), (str, int, bool)) and details.get(key) not in ("", None)]
    if details.get("valid") is False:
        parts.append("valid=false")
    return " · ".join(parts) if parts else event_type.replace("_", " ").lower()


def trace_view(path: str | Path) -> dict:
    """Validate a trace with the existing checker, then reshape its stored events."""
    validation = inspect_trace(path)
    trace = read_trace(path)
    events = sorted(trace.events, key=lambda e: e.sequence_number)
    start = events[0].timestamp if events else None
    first = events[0].details if events else {}
    profile = ((first.get("configuration") or {}).get("model_profile") or {}) if isinstance(first, dict) else {}
    rows = []
    for event in events:
        details = event.details if isinstance(event.details, dict) else {}
        rows.append({
            "seq": event.sequence_number,
            "t": round((event.timestamp - start).total_seconds(), 3) if start else 0.0,
            "timestamp": event.timestamp.isoformat(),
            "type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
            "actor": event.actor.value if hasattr(event.actor, "value") else str(event.actor),
            "group": "",
            "summary": "",
            "fields": [[key, _compact(value)] for key, value in sorted(details.items())],
        })
        rows[-1]["group"] = _group(rows[-1]["type"])
        rows[-1]["summary"] = _summary(rows[-1]["type"], details)
    metrics = asdict(validation)["metrics"]
    return {
        "trace_id": validation.trace_id, "investigation_id": trace.investigation_id,
        "event_count": validation.event_count, "digest": validation.digest, "complete": validation.complete,
        "final_status": trace.final_status.value if hasattr(trace.final_status, "value") else trace.final_status,
        "model_identifier": trace.model_identifier,
        "provider": profile.get("provider"), "profile_id": profile.get("profile_id"),
        "execution_mode": profile.get("execution_mode") or ("AUTHORED_COMPONENT" if not trace.model_identifier else None),
        "raw_payloads_retained": first.get("raw_payloads_retained") if isinstance(first, dict) else None,
        "duration_s": rows[-1]["t"] if rows else 0.0,
        "metrics": metrics,
        "events": rows,
    }


class EvidencePackage:
    """The published docs/evaluation-evidence package, addressed by manifest name only."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self._traces: dict[str, dict] = {}
        manifest = self.root / "evidence-manifest.json"
        if manifest.is_file():
            data = json.loads(manifest.read_text())
            for item in data.get("artifacts", []):
                if item.get("artifact_type") == "TRACE_JSONL":
                    name = Path(item["portable_path"]).name
                    self._traces[name] = item

    @property
    def available(self) -> bool:
        return bool(self._traces)

    def listing(self) -> list[dict]:
        keys = ("scenario_id", "evaluation_round", "scenario_step", "model_identifier", "profile_id",
                "execution_mode", "investigation_status", "investigation_outcome", "demonstrates")
        return [{"name": name, **{key: item.get(key) for key in keys}} for name, item in sorted(self._traces.items())]

    def trace_path(self, name: str) -> Path | None:
        """Only names listed in the manifest resolve; any other string is refused."""
        item = self._traces.get(name)
        return None if item is None else self.root / item["portable_path"]

    def summary(self) -> dict | None:
        if not self.available:
            return None
        from hawaii_activity_forecaster.observability.reliability import build_reliability_report
        report = build_reliability_report([self.root / "representative-traces"],
                                          report_inputs=[self.root / "representative-reports"])
        return {"valid_investigations": report["valid_investigations"], "issues": len(report["issues"]),
                "trace_groups": report["trace_groups"], "scenario_groups": report["scenario_groups"]}
