"""Owner-selected live acceptance subset; default invocation only previews work."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


# SC-006 and SC-008 re-enabled after fixes and live passes on profile 0.8 (M1.13).
DEFERRED: dict[str, str] = {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="execute paid calls; otherwise preview only")
    parser.add_argument("--include-deferred", action="store_true", help="explicitly include SC-006 and SC-008")
    parser.add_argument("--output", type=Path, help="new output directory; existing directories are rejected")
    args = parser.parse_args()
    selected, rows = [], []
    for number in range(1, 13):
        scenario = f"SC-{number:03d}"
        if scenario in DEFERRED and not args.include_deferred:
            rows.append(dict(scenario_id=scenario, outcome="NOT_RUN", reason=DEFERRED[scenario]))
            print(f"{scenario}: NOT_RUN (temporarily deferred)")
        else:
            selected.append(scenario)
    print(f"Selected {len(selected)} scenarios; deferred {len(rows)}.", flush=True)
    if not args.live:
        print("Preview only. --live executes paid calls using locally configured access.")
        return 0
    output = args.output or Path("traces") / f"acceptance-subset-{uuid4()}"
    output.mkdir(parents=True, exist_ok=False)

    def save():
        ordered = sorted(rows, key=lambda row: row["scenario_id"])
        (output / "batch-status.json").write_text(json.dumps(ordered, indent=2) + "\n")

    save()
    for scenario in selected:
        command = [sys.executable, "-m", "hawaii_activity_forecaster", "evaluate", scenario,
                   "--fixtures", "fixtures/scenario-pack-v1", "--agent",
                   "--config", "haf.release.example.toml", "--live", "--trace-directory", str(output)]
        with (output / f"{scenario}.json").open("w") as report_file, (output / f"{scenario}.stderr.log").open("w") as log:
            try:
                code = subprocess.run(command, stdout=report_file, stderr=log, timeout=300).returncode
            except subprocess.TimeoutExpired:
                code = 124
        try:
            report = json.loads((output / f"{scenario}.json").read_text())["scenario"]
            outcome, counts = report["outcome"], report["counts"]
        except (ValueError, KeyError, TypeError):
            outcome, counts = "INVALID_REPORT", {}
        rows.append(dict(scenario_id=scenario, outcome=outcome, counts=counts, exit_code=code))
        save()
        print(f"{scenario}: {outcome}, exit {code}, {counts}", flush=True)
    passed = sum(row.get("exit_code") == 0 and row["outcome"] == "PASS" for row in rows)
    print(f"{passed}/{len(selected)} selected scenarios passed; {12 - len(selected)} deferred. Reports: {output}")
    return 0 if passed == len(selected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
