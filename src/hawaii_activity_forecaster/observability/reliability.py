"""Read-only summaries of validated local traces and digest-bound saved reports.

No inference, fixture evaluation, trace repair, or provider access occurs here.
Recorded execution modes describe the input evidence, not independent proof of
network provenance. Operational outcomes and scenario acceptance stay separate.
"""

from collections import Counter, defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re
from statistics import median

from pydantic import TypeAdapter, ValidationError

from hawaii_activity_forecaster.harness.execution import ExecutionEvaluation
from .failure_codes import AGENT_FAILURE_CODES, REQUEST_FAILURE_CODES
from .validation import TraceValidationError, inspect_trace

_CODES = AGENT_FAILURE_CODES | REQUEST_FAILURE_CODES
_OUTCOMES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")


def _files(inputs, suffix, issues):
    files = set()
    for item in inputs:
        path = Path(item)
        try:
            if path.is_dir():
                files.update(p.resolve() for p in path.rglob("*" + suffix) if p.is_file())
            elif path.is_file() and path.suffix == suffix:
                files.add(path.resolve())
            else:
                issues.append(dict(path=str(path), code="INPUT_NOT_FOUND_OR_WRONG_TYPE"))
        except (OSError, RuntimeError):
            issues.append(dict(path=str(path), code="INPUT_UNREADABLE"))
    return sorted(files)


def _stats(values):
    return dict(count=len(values), total=sum(values), minimum=min(values) if values else None,
                median=median(values) if values else None, maximum=max(values) if values else None)


def _trace(path):
    receipt = inspect_trace(path)
    payload = path.read_bytes()
    if sha256(payload).hexdigest() != receipt.digest:
        raise TraceValidationError("TRACE_CHANGED_DURING_REPORT")
    events = [json.loads(line) for line in payload.splitlines()]
    first, last = events[0], events[-1]
    profile = first["details"]["configuration"].get("model_profile")
    component_mode = ("SYNTHETIC_ADAPTER" if any(e["details"].get("contract") == "synthetic_model_dispatch"
                                               for e in events) else "AUTHORED_COMPONENT")
    status = (last["details"]["final_status"] if receipt.complete else
              "AWAITING_CLARIFICATION" if last["event_type"] == "CLARIFICATION_REQUESTED" else "INCOMPLETE")
    failures = []
    for event in events:
        d = event["details"]
        stage = None
        if d.get("contract") == "model_dispatch" and d.get("phase") == "FAILED":
            stage = d["operation"]
        elif d.get("contract") == "request_interpretation" and d.get("valid") is False:
            stage = "request_validation"
        elif event["event_type"] == "AGENT_FAILED":
            stage = d["agent_type"].lower() + "_execution"
        if stage:
            code = d.get("error_code")
            failures.append(dict(stage=stage, code=code if code in _CODES else "UNCLASSIFIED"))
    if status == "FAILED" and not failures:
        failures.append(dict(stage="investigation", code="UNCLASSIFIED"))
    return dict(investigation_id=first["details"]["investigation_id"],
                session_id=first["details"]["session_id"], request_revision=first["request_revision"], sha256=receipt.digest,
                profile_id=profile["profile_id"] if profile else "NO_MODEL_PROFILE",
                execution_mode=profile["execution_mode"] if profile else component_mode,
                status=status, complete=receipt.complete, metrics=asdict(receipt.metrics), failure_events=failures)


def _trace_groups(records):
    groups = defaultdict(list)
    for row in records:
        groups[row["profile_id"], row["execution_mode"]].append(row)
    results = []
    for (profile, mode), rows in sorted(groups.items()):
        terminal = [r for r in rows if r["complete"]]
        successful = sum(r["metrics"]["outcome"] in {"RECOMMENDATIONS", "NO_RECOMMENDATION"} for r in terminal)
        failures = Counter((e["stage"], e["code"]) for r in rows for e in r["failure_events"])
        results.append(dict(profile_id=profile, execution_mode=mode, investigations=len(rows),
            statuses=dict(sorted(Counter(r["status"] for r in rows).items())),
            terminal_outcomes=dict(sorted(Counter(r["metrics"]["outcome"] for r in terminal).items())),
            operational_success=dict(numerator=successful, denominator=len(terminal),
                rate=successful / len(terminal) if terminal else None),
            terminal_duration_ms=_stats([r["metrics"]["duration_ms"] for r in terminal]),
            model_calls=_stats([r["metrics"]["model_calls"] for r in rows]),
            tool_calls=_stats([r["metrics"]["tool_calls"] for r in rows]),
            failure_events=[dict(stage=stage, code=code, events=count,
                investigations=sum(any(e["stage"] == stage and e["code"] == code for e in r["failure_events"]) for r in rows))
                for (stage, code), count in sorted(failures.items())]))
    return results


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _scenario_reports(paths, records, issues):
    """Import saved outcomes, without claiming to rerun or certify their assertions."""
    adapter = TypeAdapter(ExecutionEvaluation)
    traces = {r["sha256"]: r for r in records}
    candidates, duplicates = {}, 0
    for path in paths:
        if path.name == "batch-status.json":
            continue  # Selection/deferment metadata is not a scenario execution report.
        try:
            payload = path.read_bytes()
            json.loads(payload, object_pairs_hook=_unique_object)
            report = adapter.validate_json(payload, strict=True)
            scenario = report.scenario
            if (not re.fullmatch(r"SC-\d{3}", scenario.scenario_id) or scenario.scope != "SCENARIO"
                    or report.outcome != scenario.outcome or not scenario.trace_digests
                    or scenario.counts != {
                        k: sum(a.outcome == k for a in scenario.assertions) for k in _OUTCOMES}):
                raise ValueError()
            steps, digests = zip(*scenario.trace_digests)
            if (tuple(steps) != report.attempted_steps or tuple(steps) != tuple(range(1, len(steps) + 1))
                    or len(set(digests)) != len(digests) or any(d not in traces for d in digests)):
                raise ValueError()
            bound = [traces[d] for d in digests]
            modes = tuple(r["execution_mode"] for r in bound)
            if (len({r["session_id"] for r in bound}) != 1
                    or tuple(r["request_revision"] for r in bound) != tuple(steps)
                    or any((mode in {"AUTHORED_COMPONENT", "SYNTHETIC_ADAPTER"}) != (report.mode == "AUTHORED_COMPONENT") for mode in modes)
                    or report.execution_modes != modes or (scenario.outcome == "PASS"
                    and (not all(r["complete"] for r in bound) or not set(modes) <= {"LIVE_PROVIDER", "LOCAL_PROVIDER"}))):
                raise ValueError()
            key = scenario.scenario_id, tuple(digests)
            canonical = json.dumps(asdict(report), sort_keys=True)
            if key in candidates:
                old = candidates[key]
                if old[0] == canonical:
                    duplicates += 1
                else:
                    old[3] = True
                    issues.append(dict(path=str(path), code="REPORT_CONFLICT"))
                continue
            candidates[key] = [canonical, report, bound, False]
        except (OSError, ValueError, TypeError, ValidationError, RecursionError):
            issues.append(dict(path=str(path), code="REPORT_INVALID_OR_UNBOUND"))
    owners = defaultdict(set)
    for key in candidates:
        for digest in key[1]:
            owners[digest].add(key)
    ambiguous = set().union(*(keys for keys in owners.values() if len(keys) > 1)) if owners else set()
    if ambiguous:
        issues.append(dict(code="REPORT_TRACE_BINDING_AMBIGUOUS", count=len(ambiguous)))
    groups = defaultdict(list)
    for key, (_, report, bound, conflict) in candidates.items():
        if not conflict and key not in ambiguous:
            groups[key[0], tuple(sorted({r["profile_id"] for r in bound})),
                   tuple(sorted({r["execution_mode"] for r in bound}))].append(report.scenario)
    rows = []
    for (scenario, profiles, modes), reports in sorted(groups.items()):
        rows.append(dict(scenario_id=scenario, profiles=list(profiles), execution_modes=list(modes),
            runs=len(reports), recorded_outcomes={k: sum(r.outcome == k for r in reports) for k in _OUTCOMES},
            optional_failures=sum(not a.mandatory and a.outcome == "FAIL" for r in reports for a in r.assertions),
            optional_blocked=sum(not a.mandatory and a.outcome == "BLOCKED" for r in reports for a in r.assertions)))
    return rows, duplicates


def build_reliability_report(trace_inputs, *, report_inputs=()):
    """Summarize all supplied attempts, not just successful or latest files."""
    issues = []
    paths = _files(trace_inputs, ".jsonl", issues)
    if not paths:
        issues.append(dict(code="NO_TRACE_FILES"))
    by_id = defaultdict(dict)
    duplicates = 0
    for path in paths:
        try:
            row = _trace(path)
            versions = by_id[row["investigation_id"]]
            if row["sha256"] in versions:
                duplicates += 1
            versions[row["sha256"]] = row
        except (TraceValidationError, OSError, RecursionError):
            # Never copy exception text or unvalidated trace contents into the report.
            issues.append(dict(path=str(path), code="TRACE_INVALID_OR_UNREADABLE"))
    records = []
    for identity, versions in sorted(by_id.items()):
        if len(versions) != 1:
            issues.append(dict(investigation_id=identity, code="TRACE_IDENTITY_CONFLICT", count=len(versions)))
        else:
            records.extend(versions.values())
    scenarios, report_duplicates = _scenario_reports(_files(report_inputs, ".json", issues), records, issues)
    return dict(format_version="1.0", scope="OBSERVED_INPUTS_ONLY", trace_files=len(paths),
                duplicate_traces=duplicates, duplicate_reports=report_duplicates,
                valid_investigations=len(records), trace_groups=_trace_groups(records),
                scenario_groups=scenarios, issues=issues, investigations=records)


def render_markdown(report):
    """A compact shareable aggregate; no raw request, model text or input paths."""
    lines = ["# Reliability baseline", "",
        "Observed inputs only. Modes are trace-declared; this report does not certify network provenance.",
        "Operational success includes recommendations and explained abstentions; it is not scenario acceptance.", "",
        f"Validated investigations: {report['valid_investigations']}; duplicate trace copies: {report['duplicate_traces']}; input issues: {len(report['issues'])}.", "",
        "| Profile | Recorded mode | Runs | Completed | Abstained | Failed | Clarification | Incomplete | Operational success / terminal | Median terminal ms | Model calls total | Tool calls total |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for g in report["trace_groups"]:
        s, rate = g["statuses"], g["operational_success"]
        cells = [g["profile_id"], g["execution_mode"], g["investigations"],
            *(s.get(k, 0) for k in ("COMPLETED", "ABSTAINED", "FAILED", "AWAITING_CLARIFICATION", "INCOMPLETE")),
            f"{rate['numerator']}/{rate['denominator']}", g["terminal_duration_ms"]["median"],
            g["model_calls"]["total"], g["tool_calls"]["total"]]
        lines.append("| " + " | ".join("n/a" if c is None else str(c) for c in cells) + " |")
    lines += ["", "## Failure diagnostics", "",
        "Event counts may include multiple layers of one failure; investigation counts are distinct within each row.", "",
        "| Profile | Mode | Stage | Code | Events | Investigations |", "|---|---|---|---|---|---|"]
    for g in report["trace_groups"]:
        for f in g["failure_events"]:
            lines.append(f"| {g['profile_id']} | {g['execution_mode']} | {f['stage']} | {f['code']} | {f['events']} | {f['investigations']} |")
    lines += ["", "## Digest-bound saved scenario reports", "",
        "Recorded outcomes only; assertions are not re-evaluated. A multi-step scenario is one report, several investigations.", "",
        "| Scenario | Profiles | Modes | Reports | PASS | FAIL | BLOCKED | NOT_RUN | Optional FAIL | Optional BLOCKED |",
        "|---|---|---|---|---|---|---|---|---|---|"]
    for g in report["scenario_groups"]:
        cells = [g["scenario_id"], ", ".join(g["profiles"]), ", ".join(g["execution_modes"]), g["runs"],
            *(g["recorded_outcomes"][k] for k in _OUTCOMES), g["optional_failures"], g["optional_blocked"]]
        lines.append("| " + " | ".join(map(str, cells)) + " |")
    if report["issues"]:
        lines += ["", "## Input issues", ""]
        lines += [f"- {code}: {count}" for code, count in sorted(Counter(i["code"] for i in report["issues"]).items())]
    lines += ["", "Rates describe the supplied sample only. Clarification/incomplete traces and invalid inputs are excluded from terminal denominators.",
        "Deferred cases with no trace are not counted; current live-gate selection remains separate. No inference calls were made."]
    return "\n".join(lines) + "\n"
