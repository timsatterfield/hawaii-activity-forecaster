# M1.8-B — Terminal exclusion disclosure

The terminal output now names candidates that a safety policy or hard constraint
excluded, and says why. Before this, an advisory run printed only the remaining
recommendations, so an excluded preferred beach simply disappeared. That confused
the first owner demo: `--case advisory` looked identical to a favorable run with a
different third beach. This is presentation only. Assessments, results, the
validator, traces and the result schema are unchanged.

```
Not recommended (excluded):
  - Fictional Test Beach A (SYNTHETIC): an applicable official water-contact avoidance advisory
```

## Rules

- **Source.** The section is built from the assessments of the already-verified
  terminal state. `_verified` proves that state matches its validation basis
  before anything renders. It is never built from proposals, source text or the
  model.
- **Which candidates.** Only `EXCLUDED` candidates are listed, in both the
  RECOMMENDATIONS and NO_RECOMMENDATION outputs. The section is omitted when none
  are excluded. UNSUPPORTED and NEEDS_INVESTIGATION candidates remain covered by
  the existing general limitations.
- **Reason wording.** Each reason is a fixed phrase per disqualifying policy in
  `validation/safety.py` `_HAZARDS`. A test keeps that table and `_EXCLUSIONS` in
  step. Unknown policies fall back to "a disqualifying safety policy".
- **Hard constraints.** A failed location constraint reads "outside your required
  region (South Maui)", derived from the constraint's fixed description shape.
  Other failed constraints read "a required condition you specified is not met".
- **No identifiers.** Policy identifiers are not shown, which keeps the existing
  presentation rule that internal IDs are not display fields. The trace keeps
  `HM-WATER-001` and the other policy IDs.
- **No claims beyond the policy.** The section never calls a beach unsafe, never
  ranks, and never shows source text. SC-011's injected instruction never appears.

## Evidence

`tests/test_exclusion_disclosure.py` covers the following:

- The authored advisory demo names Beach A with its reason, outside the
  recommendations and before the general limitations, with no policy ID.
- An offline agent run of SC-011 (hard South Maui restriction) names Beach A and
  never displays the injected text.
- SC-001, which has no exclusions, renders no section.
- The wording table covers every disqualifying policy.
- Constraint and unknown-policy reasons use fixed wording only.

`test_presentation.py`'s advisory test now checks that Beach A is absent from the
recommendations and disclosed in the new section. The outage demo output is
unchanged. Suite: 1463 passed, 1 xfailed.
