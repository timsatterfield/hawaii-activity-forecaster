# Saturday synthetic release data

These are fictional input environments for the owner-approved
[M1 release scope](../../docs/implementation/m1-saturday-release-scope.md).
They are not observations or forecasts for real Maui beaches.

The catalog retains the five clearly labeled fictional records from the original
fixture package. Each environment uses the existing v1 input manifest, logical
schema `0.1`, policy `0.2`, behavior `1.0.0` and synthetic-policy `1.0.0` contracts.
Existing packages and registered scenario assertions are preserved.

The owned clock is **2026-11-16 09:00 HST**. Inputs cover **2026-11-17 08:00–11:00**
and **12:00–16:00 HST**, for swimming, snorkeling and SUP. The clock is deliberately
fixed: a request for "tomorrow" is reproducible, independent of today's date.
Requests for other intervals are outside this dataset's coverage.

| Environment | Source behavior |
|---|---|
| `favorable` | Successful official checks and applicable synthetic evidence. |
| `advisory` | Same environment with an official water-contact avoidance advisory affecting fictional Beach A. |
| `recovery` | Primary marine timeout, failed single retry, successful alternate surf/current retrievals. |
| `outage` | Primary marine failure, failed single retry, failed alternate surf/current retrievals. |

All environments use the same public interfaces in `tools.json`. Descriptive
allowlist names identify source purpose and fictional candidate scope; they do not
reveal success, failures, script IDs, policy premises or expected recommendations.
The trusted runtime offers one exact regional batch for its frozen supported
candidate pool, plus individual beach water checks. The finite configuration
covers all 31 nonempty subsets of the five catalog records; it does not expose
overlapping alternatives within an investigation. Source permissions and delegated
time/geographic/category scope remain independently checked.

Each behavior file declares 382 exact query signatures across the two windows,
including the alternate interfaces. Recovery stays conditional on actual observed
failure/gaps. No script outcome chooses the model's next action. One delegation
per role prevents another label/delegation from resetting query recovery limits.

`policy.json` provides explicit hypothetical, attributed policy premises. It does
not contain final eligibility verdicts or invented real-world numerical hazard
thresholds. Recovery premises require the actual alternate findings to be retrieved
and validated; a source template's presence on disk is insufficient.

The model sees verified request/catalog projections, canonical assessments and
legal task/tool identifiers. Behavior scripts, source templates, policy premises,
and evaluator inputs are not model context. Model proposals still pass the existing
request, specialist, tool, evidence, safety, result and independent trace checks.

Independent assertions live in `tests/test_agent_release.py`, `test_release_cli.py`
and `test_release_profile.py`, outside this application input package. Additional
tests inject stale, malformed and adversarial source content at the real synthetic
delivery boundary and supply explicit conflict/wind/visibility policy facts. They
exercise the installed SDK using mock HTTP, without credentials or paid calls.
These are focused release checks, not newly registered full SC-001–012 passes.

See the [development guide](../../docs/development-guide.md#model-driven-synthetic-release) for opt-in
execution and [integration notes](../../docs/development/m1-integration-release.md)
for acceptance scope and remaining limitations.
