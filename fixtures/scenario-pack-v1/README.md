# SC-004, SC-009, SC-010 and SC-012 synthetic scenario inputs

**Dataset:** `1.2.0`; **fixture format:** `2.0.0`; **harness contracts:** `1.0.0`.
The directory name identifies the first authored scenario pack, not the fixture
format version. All geography, numeric measurements, reporting regions, advisory
issuers and environmental statements are fictional. No live provider is queried.

The package contains four ACTIVE **definitions** (SC-004, SC-009, SC-010, SC-012).
SC-012's follow-up needs model profile `m1-saturday-runtime-0.3`, whose input bound is larger. Preflight passing is not a scenario acceptance pass.
SC-009 and SC-012 were added in dataset `1.2.0`. Their inputs derive from the release
`recovery`/`favorable` environments, and their assertions were written by hand. See
[M1.8](../../docs/development/m1-8-sc-009-sc-012.md).

```python
from hawaii_activity_forecaster.harness import load_scenario

case = load_scenario("fixtures/scenario-pack-v1", "SC-004")
application_inputs = case.application
trusted_driver_inputs = case.driver
independent_expected_results = case.evaluator
assert case.execution_readiness.outcome == "BLOCKED"
```

`agent_tools/<scenario_id>.json` holds each scenario's explicit tool allowlist for
model-driven execution (`hafi evaluate --agent`). It is an application input outside
the manifest. Preflight checks that every option is answerable by the scenario's
script; options are never derived from scripts or outcomes. See
[M1.7-A](../../docs/development/m1-7a-agentic-scenario-adapter.md).

Keep the evaluator and the full `case.definition` out of application/model/adapter
inputs. Expected JSON files were authored independently of the policy inputs and
application outputs. They contain no recorded or fabricated execution results.

## SC-004 — applicable water-contact avoidance advisory

Request: “Where should I snorkel tomorrow morning near Kihei?”

A/B have explicit fictional weather-alert, wind, regional marine and water-contact
checks for November 17, 2026, 08:00–11:00 HST. A has an applicable avoidance
advisory; B has an explicitly completed authoritative check with no applicable
listed advisory. Neither an empty advisory array alone nor the word “SUCCESS”
establishes that check or implies safe water quality.

Inputs explicitly declare hypothetical non-disqualifying surf/current/weather/
persistent characteristics and positive activity support for A/B. These are
scoped synthetic premises with references; they are not inferred from 1–2 ft surf
or 8 kn wind, and favorable physical conditions cannot override A's advisory.
Visibility is explicitly unavailable. C/D have explicit gaps in all environmental
categories, and E's catalog does not support snorkeling. No other location is
silently assumed favorable to pad the output.

The expected plan requires A excluded, B eligible/favorable/sufficient, exactly
one recommendation for B, no recommendations for A/C/D/E, meaningful B limitations,
accepted supporting findings with original scope/timestamps, source attribution,
correlated assessment/result/trace identities and actual safety/terminal events.

## SC-010 — required ocean evidence unavailable

Request: “Where should I snorkel tomorrow morning?”

A–D are the supported snorkeling cohort. Weather/alert and complete water-contact
check inputs are available, but do not resolve surf/wave/current evidence. Primary
NWS_MARINE calls fail, and HWT_SURF and SNORKEL_STORE provide failed alternative
surf/current paths. Visibility is also explicitly unavailable. Missing marine
hazard/support/conflict facts are **omitted**, never filled with false or favorable
values. E remains unsupported by its catalog activity list.

Regional and candidate-specific primary queries are distinct declared geographic
requests. Each original operation offers at most one retry; fallback operations
are separate. The script offers 16 potential invocation slots, not an instruction
to execute all 16. The trusted runtime must authorize each dispatch, correlate
semantic evidence gaps, enforce one fallback per gap, count all failures/retries,
and enforce the approved 12-call/5-iteration limits. A new operation name does not
refresh retry/fallback permissions.

The independent plan requires supported candidates to remain
NEEDS_INVESTIGATION/UNDETERMINED/INSUFFICIENT, failed fallback call correlations,
no recommendations, an explained NO_RECOMMENDATION with ABSTAINED state, and an
actual INVESTIGATION_LIMIT_REACHED event. It does not prescribe a Coordinator
reasoning sequence or which approved investigation budget is exhausted. An earlier
safe abstention may be valid application behavior but does not exercise this
scenario's required budget-boundary condition and cannot count as SC-010 passing.

Successful optional weather/water calls are available but not mandatory oracle
observations: a safe investigation may stop after mandatory ocean evidence fails.
No fake successful evidence events should be emitted to satisfy an expectation.

## Validation and remaining gates

```bash
uv run --locked pytest tests/test_scenario_fixtures.py
uv run --locked pytest
```

The 84/61 JSON assertions are necessary, not sufficient, for end-to-end acceptance.
Independent runtime checks must still validate full contract/source permissions,
source-to-finding/assessment/result links, mandatory evidence, policy precedence,
actual counter/concurrency limits, evidence-supported recommended windows,
trace completeness and grounding of material claims. Prose must not imply every
beach is unsafe because a provider failed. Existence of RESULT_VALIDATED alone is
not proof that validation passed.

The v2 loader/contract tests cannot enforce those execution semantics; runtime
and evaluator implementation remain blockers. See the [authoring/coverage notes](../../docs/development/m1-1g-scenario-fixtures.md)
for the full requirement mapping and limits. The v1 catalog/source JSON package
in the parent directory remains unchanged and is loaded through its original API.
