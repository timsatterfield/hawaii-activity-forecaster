# M1.5-D — Request interpretation and candidate-selection design review

This is a documentation-only increment. The implementation remains M1.5-C;
source code, tests, synthetic fixtures, dependencies and approved specifications
are unchanged. No natural-language CLI command or provider integration is enabled.

## Deliverables

- [Proposed design](../implementation/m1-request-interpretation-and-candidate-selection-design.md):
  request/validation interfaces, temporal and geographic rules, hard versus soft
  meanings, origin-preserving follow-ups, catalog selection, outcome/trace behavior,
  twenty proposed acceptance checks and ten decisions for human review.
- [README](../../README.md): current status, proposal link and important approval
  items, while retaining existing setup/demo/test instructions and project history.

The draft is deliberately marked **PROPOSED**. It is not an amendment to approved
requirements or evidence of implementation/acceptance. Approval has not been
recorded. The current work was authorized as a design review; a later application
increment needs accepted decisions and its own implementation request.

## Findings that affect implementation

1. **RI-C01 — source tension:** architecture §10.2 filters unsupported activities
   before investigation, while SC-003 expects actual A/E UNSUPPORTED assessments.
   The state contract requires assessed IDs in the candidate set. The proposed
   resolution retains an assessment/state set and a narrower supported dispatch
   set. This must be reviewed explicitly; a selection log cannot substitute for
   required Candidate Assessments.
2. **RI-G01 — admission/accounting gap:** the present session API takes normalized
   requests before graph creation. A live normalization call cannot be placed ahead
   of investigation identity, shared budget accounting and required tracing.
3. **RI-G02/G05 — semantic/origin gaps:** generic constraint dictionaries are UNKNOWN,
   and supplied follow-up fields are marked explicit. A new recognized geographic
   constraint needs independent catalog evaluation; derived morning precision must
   remain an assumption even when requested in a follow-up.
4. **RI-G03 — empty-selection gap:** the present early stop is not a valid
   Result Validator construction path. Valid empty catalog selection needs a
   grounded NO_RECOMMENDATION route, distinct from operational failure.
5. **RI-G04 — starting-location gap:** the product requests extraction, but there is
   no dedicated normalized field. The proposal preserves attributed runtime context
   without silently introducing a new logical field or proximity calculation.

## Proposed choices requiring review

The draft recommends an explicit, disclosed **08:00–11:00 HST morning default**,
using the injected Hawaii reference clock. This is a proposed resolution of the
open omitted/default-time policy, not an existing requirement or safety threshold.
Other unconfigured dayparts and materially missing/ambiguous values clarify.

It recommends canonical catalog geography, soft “near/prefer” meanings, and hard
activity-location “in/only/at” targets when unambiguous. Minimal versioned payloads
cover LOCATION_RESTRICTION, CALM_WATER and UNINTERPRETED. Hard geographic meaning
is independently checked; environmental calm-water meaning remains UNKNOWN pending
separate policy work. The proposal adds no hazard threshold or inferred travel time.

It preserves the full supported investigation pool and uses preferred-area groups
only for planning order. It changes no recommendation ranking policy or three-result
limit. The shared model ledger includes actual normalization dispatches; authoring
callbacks are component seams, not proof of a working model-driven Coordinator.

## Approval and next increment

Review **RI-OD-001 through RI-OD-010** in the draft, particularly RI-C01's candidate
set interpretation and the proposed morning/time/location defaults. Record explicit
human acceptance/amendments before making the draft an approved source of truth.
Approved documents remain untouched; the proposed design supplement carries the
review record.

After approval, the recommended increment is **M1.5-E — deterministic request
validation and catalog selection components**, using authored synthetic proposals.
Raw session/graph integration and grounded empty-selection results need later
integration work. General conversational runtime still requires authoritative
JSONL, separately reviewed provider/model activation, agentic planning and proper
independent scenario execution. Active clarification resumption, evidence-reference
reuse and persistent sessions remain deferred.

## Verification

Review relative Markdown links, decision/test identifier uniqueness, fixture/catalog
examples and the source references. Confirm that only this draft, these notes and
the README changed, and that no proposal is labelled approved. Run the existing
pytest suite as a regression check; no new runtime tests are introduced for a
documentation-only increment. The RI-T01–RI-T20 table defines future test obligations,
not tests run by this change.

Actual checks passed: all **36 relative Markdown links**, balanced code fences,
**10 unique decision IDs** and **20 unique proposed-test IDs**. The SC-003 pool
example was checked against the authored common catalog (A/B/E for assessment, B
supporting SUP dispatch). `git diff --check` passed. The unchanged regression suite
passed **912 tests in 12.25s** on Python 3.14, with the 13 existing upstream
LangSmith deprecation warnings. This verifies the existing implementation, not
execution of the proposed RI-T tests. Changes are limited to the README, this note
and the proposed design document.
