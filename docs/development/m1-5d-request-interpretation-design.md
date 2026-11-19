# M1.5-D — Request interpretation and candidate-selection design review

**Status:** Design approved November 19, 2026, with the afternoon-window amendment.

This is a documentation-only increment. The implementation remains M1.5-C;
source code, tests, synthetic fixtures, dependencies and the existing approved
requirement/architecture baselines are unchanged. No natural-language CLI command
or provider integration is enabled.

## Deliverables

- [Approved design](../implementation/m1-request-interpretation-and-candidate-selection-design.md):
  request/validation interfaces, temporal and geographic rules, hard versus soft
  meanings, origin-preserving follow-ups, catalog selection, outcome/trace behavior,
  twenty-two future acceptance checks and ten approved decisions.
- [README](../../README.md): current status, design link and approval
  items, while retaining existing setup/demo/test instructions and project history.

The user explicitly requested approval of the document with the afternoon-window
update. Version 0.2 records acceptance of RI-OD-001 through RI-OD-010, including
the RI-OD-002 amendment. This approves a design supplement; it is not evidence
of implementation or acceptance-test PASS. A later application increment still
requires its own implementation request.

## Findings that affect implementation

1. **RI-C01 — source tension:** architecture §10.2 filters unsupported activities
   before investigation, while SC-003 expects actual A/E UNSUPPORTED assessments.
   The state contract requires assessed IDs in the candidate set. The approved
   resolution retains an assessment/state set and a narrower supported dispatch
   set resolves this tension under RI-OD-005; a selection log cannot substitute for
   required Candidate Assessments.
2. **RI-G01 — admission/accounting gap:** the present session API takes normalized
   requests before graph creation. A live normalization call cannot be placed ahead
   of investigation identity, shared budget accounting and required tracing.
3. **RI-G02/G05 — semantic/origin gaps:** generic constraint dictionaries are UNKNOWN,
   and supplied follow-up fields are marked explicit. A new recognized geographic
   constraint needs independent catalog evaluation; derived morning/afternoon
   precision must remain an assumption even when requested in a follow-up.
4. **RI-G03 — empty-selection gap:** the present early stop is not a valid
   Result Validator construction path. Valid empty catalog selection needs a
   grounded NO_RECOMMENDATION route, distinct from operational failure.
5. **RI-G04 — starting-location gap:** the product requests extraction, but there is
   no dedicated normalized field. The design preserves attributed runtime context
   without silently introducing a new logical field or proximity calculation.

## Approved choices

The approved defaults are **08:00–11:00 HST for morning** and **12:00–16:00 HST
(noon–4 p.m.) for afternoon**, using the injected Hawaii reference clock. Explicit
hours override either default. Both default intervals are disclosed assumptions;
environmental evidence must cover the entire selected interval. These are scheduling
conventions, not safety thresholds. Unconfigured dayparts such as evening and
materially missing/ambiguous values still require clarification.

The design specifies canonical catalog geography, soft “near/prefer” meanings, and hard
activity-location “in/only/at” targets when unambiguous. Minimal versioned payloads
cover LOCATION_RESTRICTION, CALM_WATER and UNINTERPRETED. Hard geographic meaning
is independently checked; environmental calm-water meaning remains UNKNOWN pending
separate policy work. The design adds no hazard threshold or inferred travel time.

It preserves the full supported investigation pool and uses preferred-area groups
only for planning order. It changes no recommendation ranking policy or three-result
limit. The shared model ledger includes actual normalization dispatches; authoring
callbacks are component seams, not proof of a working model-driven Coordinator.

## Approval and next increment

**RI-OD-001 through RI-OD-010 are approved.** The supplement's approval record
identifies the explicit user instruction, the 12:00–16:00 HST afternoon amendment,
the retained morning default, and RI-OD-005's assessment/dispatch resolution of
RI-C01. The earlier approved source documents remain unchanged.

The recommended next increment is **M1.5-E — deterministic request
validation and catalog selection components**, using authored synthetic proposals.
Raw session/graph integration and grounded empty-selection results need later
integration work. General conversational runtime still requires authoritative
JSONL, separately reviewed provider/model activation, agentic planning and proper
independent scenario execution. Active clarification resumption, evidence-reference
reuse and persistent sessions remain deferred.

## Verification

Review relative Markdown links, decision/test identifier uniqueness, fixture/catalog
examples and the source references. The RI-T01–RI-T22 table defines approved future
test obligations, not tests run by this documentation change. RI-T03/04/05/09 were
updated for the approved defaults/resolution; RI-T21 covers afternoon resolution and
preserved follow-up origin, and RI-T22 covers partial evidence and elapsed windows.

The original review-draft checks passed: all **36 relative Markdown links**,
balanced code fences,
**10 unique decision IDs** and **20 unique proposed-test IDs**. The SC-003 pool
example was checked against the authored common catalog (A/B/E for assessment, B
supporting SUP dispatch). `git diff --check` passed. The unchanged regression suite
passed **912 tests in 12.25s** on Python 3.14, with the 13 existing upstream
LangSmith deprecation warnings. This verifies the existing implementation, not
execution of the RI-T tests. Those figures describe the original draft before
approval and the two additional afternoon test obligations. The approval amendment
is limited to the README, this note and the design document; it does not modify
runtime code or executable tests.

Approval-amendment checks passed: **36 relative links**, balanced code fences,
**10 unique approved-decision IDs** and **22 unique future-test IDs**. Both time
defaults, explicit-time precedence, full-window evidence requirements and the
approval record were checked for consistency; obsolete pending-approval and
unconfigured-afternoon statements were removed. `git diff --check` passed.
The runtime suite was not rerun for this documentation-only amendment.
