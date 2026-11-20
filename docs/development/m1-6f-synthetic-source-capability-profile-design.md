# M1.6-F — Synthetic source capability profile design

Creates the [draft profile design](../implementation/m1-synthetic-source-capability-profile-design.md)
and updates README status/navigation. This increment changes documentation only.
Approved specifications, fixture bytes, application/tests, dependencies, lockfile
and CI are preserved. No executable profile, source integration, model call, new
wire profile, commit or push is introduced.

## Concrete proposal

The proposed `capability_format_version=1.0.0` describes a finite set of exact
role/source/candidate/category/time/zone query interfaces bound to the selected
catalog bytes. It is standalone runtime configuration, not a new logical schema
or an unreviewed extension to manifest/scenario/behavior files. It grants no safety,
eligibility, provenance, source-authority or environmental outcome claims.

A future loader/offer layer uses independently authored capability metadata,
validated requests, catalog scope, canonical requirements and observed history.
Agents receive meaningful query descriptors and opaque option IDs. Script operation
IDs, attempts, fault schedules, outcome payloads, raw routing zones, evaluator data
and private configuration identifiers remain outside model views. Private coverage
preflight checks all declared query signatures and reachable retries; it must not
create a source-selection plan or remove alternatives based on their future outcomes.

The draft records CP-OD-001–008 and twenty proposed acceptance tests, CP-T01–20.
All remain **PROPOSED**, including these material decisions:

- Fixed exact batches/intervals and a nonoverlapping candidate partition per
  category/window preserve stable existing fallback keys. Arbitrary subsets or
  overlapping query families are not silently enabled.
- An investigation-wide query/gap ledger prevents later delegations and labels
  from resetting primary/retry/fallback capacity. Mandatory evidence/source rules
  determine action purpose; the model cannot relabel recovery as a new original.
- A proposed internal v0.2 wire revision adds meaningful option descriptors and
  required-nullable `origin_call_id` for already observed recovery origins. It does
  not alter the approved logical specialist/tool contracts or v0.1 behavior now.
- Coverage failures are classified by phase: unavailable preflight components can
  block readiness; invalid profile/fixture bindings fail; attempted runtime faults
  remain failures with actual counts. A real source outage is an observed execution
  condition, not a substitute for a missing query implementation.

## Findings and compatibility gates

`SyntheticDriver.peek` matches exact signature material and distinguishes original
dispatch from its one possible retry. `SyntheticToolDispatcher.register` currently
requires recovery references to earlier actions in the same registered plan. Its
retrieval-gap tracking is separate from subsequent evidence validation. M1.6-E
inputs contain allowed option IDs but no query descriptors or observed-origin wire
reference. These are implementation gaps for genuine iterative planning, not new
conflicts between approved requirements.
The current dispatcher also seeds gaps for the whole parent candidate set; future
split-batch aggregation must use the same canonical groups as its query/action gaps
instead of retaining an extra unresolved parent-wide gap.
The existing trace reader also expects a failing/partial fallback origin. Supporting
SUCCESS followed by rejected/insufficient evidence requires independently verifiable
gap proof in that reader, without allowing retries of success or fabricated gaps.

SC-010's broad and single-candidate marine variants overlap for the same categories
and interval. A v1 profile would select one reviewed interface family, rather than
expose both as a way to refresh a gap allowance. SC-004 has different category-specific
batches. Neither existing scenario is automatically declared compatible or fully
agentic. Scenario-specific zone labels and punctuation differences must stay private
and match verbatim; they do not establish geographic applicability.

All seven core requirements and eight approved implementation documents are present.
M1.6-D and the new M1.6-F remain drafts. Existing path irregularities are unchanged;
no replacement specification is invented. The new profile example is explicitly
illustrative, with a placeholder catalog digest, not an executable source artifact.

## Verification and next increment

Final verification on Python 3.14.8:

- `uv run --locked pytest`: **1,306 passed, 13 warnings in 43.93s**. The warnings
  are the existing upstream LangSmith asyncio deprecations.
- All 45 relative documentation links across the three changed/new files resolve;
  fenced blocks balance and the illustrative profile JSON parses.
- The example query passes existing Operation/TimeRange validation and agrees with
  catalog IDs and source/domain/category permissions. Its placeholder catalog digest
  remains explicitly non-executable. No operation is dispatched by this check.
- Whitespace and protected-file preservation checks pass; only README and the two
  new draft/development documents changed.

Documentation/example validation does not establish profile-loader correctness,
model planning or live-provider quality. No CP-T acceptance test is claimed
implemented by this documentation work.

Unchanged developer commands:

```bash
uv sync --locked
uv run --locked hafi --version
uv run --locked pytest
```

Recommended next increment after review: **M1.6-G — Capability Profile Loading and
Validation**, initially offline with independent component fixtures. Stage model
offers/wire v0.2, cross-delegation recovery and agent integration afterward. The
source-capability artifact itself does not enable paid models, increase budgets,
change deterministic safety or remove the full scenario/M1 acceptance gates.
