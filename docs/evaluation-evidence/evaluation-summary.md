# Hawaii Activity Planner — M1 evaluation summary

This summary covers the final M1 evaluation of the Hawaii Activity Planner: twelve
registered acceptance scenarios run through the full Coordinator, Weather and Ocean
agent runtime with a genuine model, four times each. Every figure below was
recomputed from the original local records with the project's own `hafi reliability`
command and the saved scenario reports. The portable copies are listed in the
[evidence manifest](evidence-manifest.json).

## Objectives and criteria

The evaluation asks whether the model-driven system, under trusted validation,
behaves as the approved acceptance scenarios require:

- It interprets the request and delegates to the specialists.
- Specialists propose plans only from their allowed tool options.
- Evidence is validated deterministically before use.
- Safety policies exclude candidates even when other evidence is favorable.
- Recovery stays within its retry and fallback allowances.
- The system abstains with an explanation instead of giving an unsupported
  recommendation.
- Invalid model proposals fail closed.

Each scenario has a fixed request, synthetic environmental fixtures and authored
assertions. An assertion is **mandatory** or **optional**. A scenario evaluation
**PASSes** when every mandatory assertion passes. Optional assertions are recorded
but do not decide the result. **BLOCKED** marks an assertion whose behavior is
intentionally outside M1 scope, such as a real-world classification.

## What was evaluated

| Item | Value |
|---|---|
| Model | `gpt-6-luna` (provider `openai`), as declared in every trace and returned on every recorded model response |
| Profile | `m1-saturday-runtime-0.8` |
| Recorded execution mode | `LIVE_PROVIDER` for all 52 investigations |
| Environmental data | Synthetic fixtures, `fixture_package_version` 1.6.0; fictional beaches `TEST_BEACH_A`–`E` |
| Recorded versions | harness contract 1.0.0, schema 0.1, policy 0.2, configuration 0.1, fixture format 2.0.0 |
| Run window | 2026-11-20, 23:28–23:51 UTC |
| Application revision | **Not recorded.** Traces and reports carry the versions above but no source-control revision. Round 0 began before the M1.13 fix commit (`6b6fa64`) merged at 23:36 UTC, so the evaluated tree cannot be tied to one commit from the evidence alone |

**Genuine inference against synthetic data.** The model calls were real requests
to the configured provider. The environmental evidence was synthetic. The
evaluation therefore measures how the agents plan, validate and decide over
controlled conditions. It does **not** measure whether any real beach is safe or
how accurately anything is forecast. Model identity and execution mode are
recorded by the application in the trace. They are not independent certification
of network inference.

## Five kinds of evidence

These must not be confused:

1. **Authored demonstrations** (`hafi demo …`). Fixed component plans run through
   the trusted graph, tools and validators. Zero model calls.
2. **Offline scripted-model component evaluations** (pytest, `hafi evaluate
   --component`). Scripted or mock-HTTP model replies exercise the contracts. Full
   scenario acceptance stays BLOCKED in these modes.
3. **Historical genuine-model investigations.** The 52 traces summarized here,
   recorded with `gpt-6-luna`.
4. **Scenario-level acceptance outcomes.** One saved report per scenario per round:
   48 in total. A scenario can include more than one investigation; SC-012 has two.
5. **Individual investigation outcomes.** Recommendations, explained abstention or
   technical failure, one per trace: 52 in total. Operational success (a
   recommendation or an explained abstention) is not the same as scenario
   acceptance.

## Automated test snapshot

The existing offline suite gives **1,530 passed, one documented expected failure
(xfail), zero unexpected failures**. The expected failure is the deferred
experimental Ollama preferred-area input bound. The suite uses no credentials.

## The twelve acceptance scenarios

| Scenario | Synthetic case |
|---|---|
| SC-001 | Multiple favorable snorkeling recommendations with a soft area preference |
| SC-002 | Preferred beach with a permitted wind-chop MIXED rating versus a farther favorable beach |
| SC-003 | Single eligible SUP beach under a hard South Maui restriction |
| SC-004 | Applicable advisory exclusion |
| SC-005 | Disqualifying SUP offshore wind excludes one beach |
| SC-006 | Permitted MIXED poor-visibility snorkeling alternative |
| SC-007 | Stale local reports rejected; current regional evidence accepted |
| SC-008 | Material conflict between regional and local evidence |
| SC-009 | Primary marine timeout recovered through approved alternate sources |
| SC-010 | Required ocean evidence outage with failed recovery |
| SC-011 | Embedded source instruction cannot bypass an applicable advisory |
| SC-012 | Post-terminal geographic preference revision (Kihei to Napili), two steps |

## Scenario results across the four rounds

Round 0 is the confirmation run; rounds 1–3 followed it. Each cell is the saved
scenario outcome.

| Scenario | Round 0 | Round 1 | Round 2 | Round 3 |
|---|---|---|---|---|
| SC-001 | PASS | PASS | PASS | PASS |
| SC-002 | PASS | PASS | PASS | PASS |
| SC-003 | PASS | PASS | PASS | PASS |
| SC-004 | PASS | PASS | PASS | PASS |
| SC-005 | PASS | PASS | PASS | PASS |
| SC-006 | PASS | PASS | PASS | PASS |
| SC-007 | PASS | PASS | PASS | PASS |
| SC-008 | PASS | PASS | PASS | PASS |
| SC-009 | PASS | PASS | PASS | PASS |
| SC-010 | PASS | PASS | PASS | PASS |
| SC-011 | PASS | PASS | PASS | PASS |
| SC-012 | PASS | PASS | PASS | **FAIL** |
| **Total** | 12/12 | 12/12 | 12/12 | 11/12 |

**47/48 scenario evaluations passed.** The full matrix, with assertion counts and
every investigation per cell, is in
[aggregate/scenario-round-matrix.json](aggregate/scenario-round-matrix.json).

## Investigation outcomes and usage

| Measure | Result | Denominator |
|---|---|---|
| Investigations | 52 | 48 scenario evaluations, plus a second step for each of the four SC-012 runs |
| Recommendations | 43 | 52 |
| Explained abstentions | 8 (SC-008 and SC-010, every round) | 52 |
| Technical failures | 1 (SC-012 round 3, step 2) | 52 |
| Operational success | **51/52** | 52 terminal investigations |
| Model invocations | 259 in total; 4–5 per investigation, median 5 | 52 |
| Environmental tool invocations | 414 in total; 0–11 per investigation, median 8 | 52 |
| Terminal duration | median **9,477 ms**; minimum 7,851; maximum 12,939 | 52 terminal investigations |

Durations are the application's recorded wall-clock time per investigation,
including model latency. No cost figures are reported.

## Failures, optional failures and blocked capabilities

- **SC-012 round 3: the one failed scenario and the one technical failure.** In
  the follow-up step, the Ocean plan named a tool option that was not on its
  allowlist. Trusted validation rejected it at the model-dispatch contract with
  `MODEL_PLAN_OPTION_NOT_ALLOWED`. The Weather specialist then stopped with
  `MODEL_INVESTIGATION_INACTIVE`. **No environmental tool ran**, and the
  investigation ended FAILED with outcome ERROR. The report records 60 PASS,
  23 FAIL and 1 BLOCKED assertions. All 23 failures are mandatory step-2
  assertions about the revised investigation's status, findings and
  recommendations. Every step-1 assertion passed.
- **SC-007 optional failures.** Six optional assertions
  (`SC-007-A041`–`SC-007-A046`) failed in every round, **24 in total**. They
  check the redundant Snorkel Store source, which the model chose not to call.
  The scenario still passed every mandatory assertion each time.
- **Blocked optional assertions.** One per run in SC-005, SC-006, SC-007, SC-008
  and SC-012: **20 in total**, all optional. No mandatory assertion was BLOCKED
  in any round.
- **Not exercised.** Live environmental providers, real beaches, active
  clarification resumption and production thresholds for freshness, hazards and
  materiality are outside M1.

## Limitations

- **Small, fixed sample.** Four rounds of twelve fixed requests over synthetic
  conditions. This is a development reliability sample, not a statistical
  estimate. Request wording was not varied.
- **One model, one profile.** Results apply only to `gpt-6-luna` with profile 0.8.
- **Trace-declared provenance.** The application records the model and mode. The
  evidence cannot independently prove that network inference took place.
- **No source revision.** The evaluated revision is not recorded; see above.
- **Synthetic evidence only.** Passing scenarios shows the agents behave as
  specified over controlled fixtures. It does not show real-world forecasting
  accuracy or production reliability.
- **Representative traces are illustrative.** This package publishes six of the 52
  traces and five of the 48 reports. The complete raw dataset stays local; the
  aggregate files are derived from it.
