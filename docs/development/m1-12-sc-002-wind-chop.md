# M1.12 — SC-002 and the swimming wind-chop MIXED permission

Registers SC-002, the last of the twelve acceptance scenarios, on dataset **`1.6.0`**.
It needed three owner-approved changes (2026-11-20). Requirements and harness
contracts are unchanged.

| Scenario | Assertions | Offline agent runtime |
|---|---|---|
| SC-002 geographic preference vs environmental suitability | 65 | 65/65 PASS; scenario BLOCKED `OFFLINE_MODEL_TRANSPORT` |

## 1. Permitted non-disqualifying limitation for swimming: wind-driven chop

The approved safety policy already states the basis:

- **§8.1 Swimming:** "DISCLOSE non-disqualifying wind and chop."
- **The policy matrix row:** "Non-disqualifying wind or chop: DISCLOSE" for every
  activity.
- **Test case HM-T05:** "Non-disqualifying wind-driven chop: DISCLOSE."

§15 sets the five MIXED conditions, and §15.1 lists "non-disqualifying wind-driven
chop" as a potentially permissible example. The code previously expressed only the
snorkeling poor-visibility case.

**Change.** `harness/policy.py` now defines `REVIEWED_LIMITATIONS`, mapping
(activity, code) to (evidence category, governing requirement):

| Activity | Code | Evidence | Basis |
|---|---|---|---|
| SNORKELING | `SYNTHETIC_POOR_VISIBILITY` | UNDERWATER_VISIBILITY | HM-VIS-003 (unchanged) |
| SWIMMING | `SYNTHETIC_WIND_CHOP` | WIND_CONDITIONS | HM-T05 (new) |

**Validation.** Premises and permissions validate against this table.

- A limitation premise or permission outside it is rejected.
- A permission must cite its pair's basis.

**Safety evaluation.** `validation/safety.py` evaluates the declared limitation with
its own category and policy ID. The five §15 conditions are unchanged:

- evidence SUFFICIENT,
- no failed disqualifying policy,
- mandatory hazards resolved,
- the limitation documented as non-disqualifying,
- the limitation disclosed.

When no limitation is declared, behavior is exactly as before, so all 41 existing
traces still validate. Owner choices: swimming only, with SUP deferred. No
real-world chop threshold is set. If chop were ever hazardous, the existing surf,
current and weather checks would exclude the beach; the limitation never overrides
them.

## 2. Request interpretation: "I'd" and "prefer somewhere near <area>"

SC-002's wording, "I'd prefer somewhere near Kihei.", hit two gaps in the approved
clause rules (`interpretation/clauses.py`):

- **"I'd".** It was not a filler word, so it triggered a "please restate"
  clarification. It is now in the filler list.
- **"prefer somewhere near".** The word "somewhere" broke the `prefer near` match,
  so the area stayed uninterpreted. "prefer somewhere near" is now a soft
  area-preference prefix, like "prefer near".

An unknown area ("…near Atlantis") is still kept as an uninterpreted preference with
no nearby inference. Existing phrasings are unchanged.

## 3. Model profile 0.7

Because "prefer somewhere near" is now a recognized clause, the validator expects
the model to cite the whole phrase. `m1-saturday-runtime-0.7` equals 0.6 except for
the normalize template, `normalize_request-release-0.4`, which appends:

> 'prefer somewhere near' before an area is the same soft preferred_area preference;
> cite the whole phrase, such as 'prefer somewhere near Kihei'.

`haf.release.example.toml` now uses 0.7. Tests pin 0.6's Ocean change and limit 0.7
to the normalize addition.

## SC-002 assertions

"Where should I swim tomorrow morning? I'd prefer somewhere near Kihei." A (Kihei)
and C (Napili) have complete premises. A also has a wind-chop limitation supported
by the accepted wind finding. B, D and E are undeclared. The assertions require:

- Preferred area Kihei, as a soft preference, with no hard constraints.
- A ELIGIBLE/MIXED/SUFFICIENT and `PREFERRED_AREA`, recommended with a MIXED label
  and non-empty limitations. The chop is disclosed, and the soft preference does not
  override safety.
- C ELIGIBLE/FAVORABLE and `OUTSIDE_PREFERRED_AREA`. It is the farther beach with
  clean conditions.
- Exactly two recommendations with no rank, so no drive-time or numeric ordering.

**Recorded interpretation, owner default.** The spec says "C should be preferred".
Recommendations carry no rank, so preference is checked through the labels: C is
FAVORABLE and A is MIXED with a disclosure. This follows the §15.3 principle that
MIXED ranks below comparable FAVORABLE.

## Evidence

- `tests/test_wind_chop_permission.py` covers three things:
  - Permission and premise validation for every activity/code pair.
  - The rule that a chop permission must cite HM-T05.
  - The "I'd" and "prefer somewhere near" phrasings, plus the unknown-area case.
- `test_sc002_without_the_chop_permission_fails` shows the permission is
  load-bearing: without it, A is non-recommendable and SC-002 fails.

Suite: 1499 passed, 1 xfailed.

## Owner-run live evidence (2026-11-20, profile 0.7)

| Attempt | Result | Trace |
|---|---|---|
| SC-002 #1 | **PASS** 65/65, `LIVE_PROVIDER`, template `normalize_request-release-0.4`. Kihei normalized as the preferred area from "I'd prefer somewhere near Kihei"; A ELIGIBLE/MIXED/SUFFICIENT with chop disclosed; C ELIGIBLE/FAVORABLE. 5 model calls, 9 tool calls | `edb6aa2f…` (`4beb255d…`) |

With this run, all twelve acceptance scenarios (SC-001 to SC-012) are registered
and each has a live full pass. Every scenario except SC-002 passed on profile 0.6,
whose Coordinator, Weather and Ocean prompts are identical in 0.7; 0.7 changes only
the normalize prompt. A final all-twelve pass on 0.7 would confirm it end to end.
