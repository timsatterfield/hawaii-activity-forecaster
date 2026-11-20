# M1.9-B — Live re-baseline on profile 0.4

On 2026-11-20 the owner ran the four registered scenarios that had last passed live
on profiles 0.2 or 0.3. They ran once each on the current release profile
`m1-saturday-runtime-0.4` (`gpt-6-luna`), with
`hafi evaluate <id> --agent --live`. No code, fixture or profile changed. Every
trace is complete, was recorded with profile 0.4 and `LIVE_PROVIDER`, and its
digest matches its report.

| Scenario | Result | Trace | Notes |
|---|---|---|---|
| SC-004 advisory exclusion | **PASS** 84/84 | `dbf33e1f…` (`98109ad6…`) | 5 model calls, 9 tool calls |
| SC-009 fallback recovery | **FAIL** 16/73, `APPLICATION_FAILURE` | `24354a57…` (`8ea4ee79…`) | See below |
| SC-010 outage abstention | **PASS** 61/61 | `fcfab432…` (`9f0fe00c…`) | 1 retry, 2 fallbacks, `NO_RECOMMENDATION` |
| SC-012 preference revision | **PASS** 83/83 mandatory, 1 optional BLOCKED | `5ea417b6…` (`2f0cb5b4…`), `7fcaf13e…` (`39555dc7…`) | Two steps in one session; 10 model calls |

Together with SC-001 and SC-003 from M1.9, **five of the six registered scenarios
have passed live on profile 0.4.** Across all eight live runs on 0.4, 7 passed and
1 failed.

## SC-009 failure: Ocean recovery plan rejected

- **Request interpretation succeeded**, and the Coordinator delegated both
  specialists.
- **Weather** ran its two tools and completed.
- **Ocean's plan was rejected.** The model's plan passed the wire schema (1,037
  input and 400 output tokens), but the runtime rejected it with
  **`AGENT_FAILED.error_code = PLAN_RECOVERY_CONDITION_INVALID`**: "Recovery cannot be
  relabeled as a new original".
- **Likely cause.** The model gave a recovery option, `SURF_ABCDE` or
  `CURRENTS_ABCDE` (fallbacks of `MARINE_ABCDE`), a condition other than
  `FALLBACK_IF_REQUIRED_GAP_UNRESOLVED`. In practice that usually means scheduling it
  unconditionally.
- **Outcome.** No ocean tool ran. The investigation ended `ERROR` with no
  recommendation, so it failed closed.

This is the first categorized Ocean-plan failure. SC-010 #1 on profile 0.2 was also
a rejected Ocean recovery plan, but it predated the reason codes. Profile 0.4
changed only the request-interpretation prompt. The Ocean prompt (`release-0.2`)
already says "Never use ALWAYS for a retry/fallback option", so the model
occasionally ignores an existing instruction rather than lacking one.

## Live failures by category

| Call | Code | Seen in |
|---|---|---|
| `normalize_request` | `REQUEST_SPAN_MISSING` | SC-001 #2 (0.3) |
| `normalize_request` | `REQUEST_CHANGE_UNSUPPORTED` / `preferred_area` | SC-003 #1 (0.3) |
| `ocean_investigation` | `PLAN_RECOVERY_CONDITION_INVALID` | SC-009 (0.4) |
| Earlier, uncategorized | Request rejection (SC-004 #1); Ocean plan rejection (SC-010 #1) | 0.2 |

Profile 0.4 addressed the two request-interpretation rules. The remaining live
failure mode is Ocean recovery conditions. Options for the owner:

1. **Accept and rerun** SC-009 to record a 0.4 pass. Its plan failed once, just as
   SC-010's did on 0.2 before later passing.
2. **Profile 0.5: Ocean prompt hardening.** For example, state that each option ID
   carries a fixed condition and give one worked recovery example. This changes the
   Ocean template only, as 0.4 did for normalize.
3. **Deterministic condition assignment.** The runtime already knows each option's
   configured role. It could fill in the condition itself, so the model would only
   choose which options to include. This is an architecture change: it moves a
   model decision into trusted code, so it needs explicit approval.

## Owner decision (2026-11-20): option 2, profile 0.5

`m1-saturday-runtime-0.5` is now the release profile in `haf.release.example.toml`.
It equals 0.4 except for the Ocean template, `ocean_investigation-release-0.3`,
which appends guidance mirroring the runtime's fixed option roles:

- Each option ID has exactly one condition. `RETRY_MARINE_` options use
  `RETRY_IF_RETRYABLE_FAILURE`, `SURF_` and `CURRENTS_` options use
  `FALLBACK_IF_REQUIRED_GAP_UNRESOLVED`, and every other option is an `ALWAYS`
  original with a null origin.
- Recovery steps point to their `MARINE_` step and come after it. Surf and currents
  are never scheduled unconditionally.
- One worked example plan is included. A test parses that example through the real
  `SpecialistPlan` schema.

The option names are the model's only signal of each option's role, since it sees
legal option IDs and not `retry_of`/`fallback_of`. The guidance therefore keys on
the existing allowlist naming convention. The runtime check is unchanged and still
rejects any mismatch.

| | 0.4 | 0.5 |
|---|---|---|
| Normalize, Coordinator and Weather prompts | as 0.4 | Identical |
| Ocean prompt | `release-0.2` | `release-0.3` (0.4 text plus the guidance above) |
| Input bound and reserve | 12,000 bytes, 2,600 µUSD | Identical |

Name-based profile checks in `prompts.py` now use explicit sets (`_SATURDAY_RELEASE`,
`_NORMALIZE_GUIDED`, `_OCEAN_GUIDED`) rather than bare `SATURDAY_PROFILE`. Adding a
profile therefore cannot silently change an older one, which nearly happened when
0.4 was added. Tests pin 0.3 to 0.2's prompts, 0.4 to the normalize change and 0.5
to the Ocean change. All 21 existing traces still validate. Suite: 1432 passed,
1 xfailed.

**Live effect not yet measured.** Rerun SC-009, which failed on 0.4, and SC-010,
the other recovery scenario.

## Profile 0.5 live results (2026-11-20)

| Scenario | Result | Trace |
|---|---|---|
| SC-009 | **FAIL** 16/73. The same `AGENT_FAILED.error_code = PLAN_RECOVERY_CONDITION_INVALID` (Ocean) | `2ff8f528…` (`d8aa9c1c…`) |
| SC-010 | **PASS** 61/61. 1 retry, 2 fallbacks, `NO_RECOMMENDATION` | `fa4053e0…` (`65be969b…`) |

Both traces confirm profile 0.5 and `ocean_investigation-release-0.3`. SC-009 has
now failed on both 0.4 and 0.5 and passed once on 0.3. SC-010 passed on both.

**Leading hypothesis.** SC-009 is the only allowlist that offers fallbacks (`SURF_`,
`CURRENTS_`) **without** a `RETRY_MARINE_` option. The retry was deliberately
omitted so the spec's "remaining retry capacity" condition holds. SC-010 and the
release `tools.json` both include the retry. The Ocean prompts describe the
retry-then-fallback pattern, so a model that finds no retry option may give a
fallback a retry condition, which this rule rejects. The current code does not
record which condition the model proposed, so this is unconfirmed.

## Owner decision (2026-11-20): diagnose before changing prompts or fixtures

`PLAN_RECOVERY_CONDITION_INVALID` is now split by the option's configured role and
the condition the model proposed. That gives six closed codes:

| Configured role \ proposed | Original (`ALWAYS`) | Retry | Fallback |
|---|---|---|---|
| Original | — | `PLAN_ORIGINAL_LABELED_RETRY` | `PLAN_ORIGINAL_LABELED_FALLBACK` |
| Retry | `PLAN_RETRY_LABELED_ORIGINAL` | — | `PLAN_RETRY_LABELED_FALLBACK` |
| Fallback | `PLAN_FALLBACK_LABELED_ORIGINAL` | `PLAN_FALLBACK_LABELED_RETRY` | — |

The runtime raises one fixed message per combination, and `failure_codes.py` maps
each message to its code. These remain constants: no option IDs or model text are
recorded. `PLAN_RECOVERY_CONDITION_INVALID` stays in the vocabulary so earlier
traces validate. A test checks that all six combinations map to distinct closed
codes. The offline rejected-plan test now records `PLAN_ORIGINAL_LABELED_FALLBACK`.
All 23 existing traces still validate. Suite: 1433 passed, 1 xfailed.

**How to read the next SC-009 result:**

- `PLAN_FALLBACK_LABELED_RETRY` confirms the missing-retry hypothesis.
- `PLAN_FALLBACK_LABELED_ORIGINAL` means the model ran surf or currents
  unconditionally.
- An `ORIGINAL_LABELED_*` code means it made an original, such as visibility or
  water, conditional.

## Diagnosis confirmed (SC-009 rerun on 0.5)

| Scenario | Result | Trace |
|---|---|---|
| SC-009 | **FAIL** 16/73. `AGENT_FAILED.error_code = PLAN_ORIGINAL_LABELED_RETRY` (Ocean) | `5a7acaba…` (`fab381ed…`) |

The model gave an **original** option the retry condition. With no `RETRY_MARINE_`
option offered, it almost certainly reused `MARINE_ABCDE` as a second, retry-labeled
step, improvising the retry the prompts describe. This confirms the
missing-retry-option cause in a slightly different form than predicted. It also
explains why SC-010 and the release data, which both list a retry, pass.

The application must handle any valid allowlist, including one without a retry, so
the fix belongs in guidance rather than in the fixture. Ocean guidance should
state: retry only through a listed `RETRY_MARINE_` option; when none is listed,
there is no retry, so never repeat an option or give an original the retry
condition.

## Owner decision (2026-11-20): profile 0.6

`m1-saturday-runtime-0.6` is now the release profile. It equals 0.5 except for the
Ocean template, `ocean_investigation-release-0.4`, which appends the following:

> Retry only through a listed RETRY_MARINE_ option. If no RETRY_MARINE_ option is
> listed, there is no retry: never repeat an option, and never give an original the
> retry condition. Use each option ID at most once. Without a retry, list SURF_ and
> CURRENTS_ fallbacks with origin_step pointing directly at their MARINE_ step.

| | 0.5 | 0.6 |
|---|---|---|
| Normalize, Coordinator and Weather prompts | as 0.5 | Identical |
| Ocean prompt | `release-0.3` | `release-0.4` (0.5 text plus the paragraph above) |
| Input bound and reserve | 12,000 bytes, 2,600 µUSD | Identical |

Tests pin 0.5's Ocean change and limit 0.6 to the no-retry paragraph. A no-retry
plan with SC-009's shape (fallbacks pointing straight at `MARINE_`) parses under the
real `SpecialistPlan` schema. All 24 existing traces still validate. The SC-009
allowlist is unchanged and remains the only no-retry coverage. **Live effect not yet
measured.**

## Profile 0.6 live result

| Scenario | Result | Trace |
|---|---|---|
| SC-009 | **Full scenario PASS** 73/73, `LIVE_PROVIDER`, `ocean_investigation-release-0.4`. Marine `SOURCE_TIMEOUT`, no retry, both fallbacks completed, all five candidates eligible. 5 model calls, 11 tool calls | `f3d15525…` (`ab5ff9ec…`) |

The diagnosed rule (`PLAN_ORIGINAL_LABELED_RETRY`) did not recur after the
no-retry guidance. This is one observation, not a reliability rate.

**Status on the current profile.** Profiles 0.4, 0.5 and 0.6 share the normalize,
Coordinator and Weather prompts; 0.5 and 0.6 differ from 0.4 only in the Ocean
prompt. Latest live result per scenario:

| Scenario | Latest | Profile |
|---|---|---|
| SC-001 | PASS | 0.4 |
| SC-003 | PASS | 0.4 |
| SC-004 | PASS | 0.4 |
| SC-009 | PASS | **0.6** |
| SC-010 | PASS | 0.5 |
| SC-012 | PASS | 0.4 |

Every registered scenario has a passing live run on a 0.4-family profile. Only
SC-009 has run on 0.6. A final all-scenario pass on 0.6 would confirm the Ocean
changes cause no regression: about 40 model calls for six scenarios, SC-012 having
two steps.

## Final all-scenario pass on profile 0.6 (2026-11-20)

All six registered scenarios were run once each, back to back, on
`m1-saturday-runtime-0.6` (`gpt-6-luna`, `LIVE_PROVIDER`). Each report's trace
digest was matched to a complete, independently validated trace recorded with
profile 0.6.

| Scenario | Result | Model / tool calls | Notes | Trace |
|---|---|---|---|---|
| SC-001 | **PASS** 86/86 | 5 / 8 | A, B, C recommended | `5aba39c3…` (`b540608d…`) |
| SC-003 | **PASS** 55/55 | 5 / 5 | B only, hard South Maui restriction | `258e4eb4…` (`0818fde7…`) |
| SC-004 | **PASS** 84/84 | 5 / 11 | A excluded (HM-WATER-001), B only | `08c7af3b…` (`b4bbc1b2…`) |
| SC-009 | **PASS** 73/73 | 5 / 11 | Timeout, 2 fallbacks, 5 eligible | `037e50d2…` (`ea92e9f2…`) |
| SC-010 | **PASS** 61/61 | 5 / 8 | 1 retry, 2 fallbacks, abstained | `01f5bda1…` (`c0d0604a…`) |
| SC-012 | **PASS** 83/83 mandatory, 1 optional BLOCKED | 10 / 16 | Two steps, same session | `fbde8822…` (`d45e7b56…`), `0a4e9de0…` (`c150ce0b…`) |

**6 of 6 passed on the current release profile**, using 40 model calls. Together
with the earlier SC-009 run, profile 0.6 is 7 of 7 live. These are observations
over single runs, not a measured reliability rate. Earlier failures are preserved
in this document and in M1.7-A, M1.8 and M1.9.
