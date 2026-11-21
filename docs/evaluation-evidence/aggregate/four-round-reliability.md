# Reliability baseline

Observed inputs only. Modes are trace-declared; this report does not certify network provenance.
Operational success includes recommendations and explained abstentions; it is not scenario acceptance.

Validated investigations: 52; duplicate trace copies: 0; input issues: 0.

| Profile | Recorded mode | Runs | Completed | Abstained | Failed | Clarification | Incomplete | Operational success / terminal | Median terminal ms | Model calls total | Tool calls total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| m1-saturday-runtime-0.8 | LIVE_PROVIDER | 52 | 43 | 8 | 1 | 0 | 0 | 51/52 | 9477.0 | 259 | 414 |

## Failure diagnostics

Event counts may include multiple layers of one failure; investigation counts are distinct within each row.

| Profile | Mode | Stage | Code | Events | Investigations |
|---|---|---|---|---|---|
| m1-saturday-runtime-0.8 | LIVE_PROVIDER | ocean_execution | MODEL_PLAN_OPTION_NOT_ALLOWED | 1 | 1 |
| m1-saturday-runtime-0.8 | LIVE_PROVIDER | ocean_investigation | MODEL_PLAN_OPTION_NOT_ALLOWED | 1 | 1 |
| m1-saturday-runtime-0.8 | LIVE_PROVIDER | weather_execution | MODEL_INVESTIGATION_INACTIVE | 1 | 1 |
| m1-saturday-runtime-0.8 | LIVE_PROVIDER | weather_investigation | MODEL_INVESTIGATION_INACTIVE | 1 | 1 |

## Digest-bound saved scenario reports

Recorded outcomes only; assertions are not re-evaluated. A multi-step scenario is one report, several investigations.

| Scenario | Profiles | Modes | Reports | PASS | FAIL | BLOCKED | NOT_RUN | Optional FAIL | Optional BLOCKED |
|---|---|---|---|---|---|---|---|---|---|
| SC-001 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| SC-002 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| SC-003 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| SC-004 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| SC-005 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 0 | 4 |
| SC-006 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 0 | 4 |
| SC-007 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 24 | 4 |
| SC-008 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 0 | 4 |
| SC-009 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| SC-010 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| SC-011 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| SC-012 | m1-saturday-runtime-0.8 | LIVE_PROVIDER | 4 | 3 | 1 | 0 | 0 | 0 | 4 |

Rates describe the supplied sample only. Clarification/incomplete traces and invalid inputs are excluded from terminal denominators.
Deferred cases with no trace are not counted; current live-gate selection remains separate. No inference calls were made.
