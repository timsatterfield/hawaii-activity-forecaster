# M1.6-D — Model provider and agent runtime design

This increment creates the [draft model/runtime design](../implementation/m1-model-provider-and-agent-runtime-design.md)
and updates README navigation/status. It changes documentation only. The approved
requirements/implementation documents, Python code, fixtures, dependencies and
lockfile are preserved. No provider SDK is installed, credentials accessed, paid
calls dispatched, model configuration enabled or full scenario PASS claimed.

## Proposal scope

- Compare official OpenAI, Anthropic and Google documentation; recommend one
  provisional low-cost OpenAI profile across the existing three roles.
- Specify credentials, provider retention considerations, default-disabled
  activation, proposed token/spending ceilings and a future pilot checklist.
- Define closed structured proposals for normalization, Coordinator decisions
  and specialist plans, with trusted conversion to existing logical contracts.
- Preserve deterministic evidence, safety, eligibility, comparison and results.
- Design a real-provider gateway with shared budgets, explicit zero SDK retries,
  timeout/failure accounting and authoritative trace migration.
- Propose independent legal source-capability metadata so planning does not read
  behavior scripts, expected answers or future source outcomes.
- Explain iteration placement and the five-cycle/twelve-model-call arithmetic;
  define guarded recovery and proposed tests MR-T01–MR-T17.

The new document is **Draft — Human Review Required**. Its decision table separates
proposals from approved safeguards. Existing provider configuration stays disabled.
The owner confirmed no provider preference and requested a low-cost starting
recommendation; this does not authorize the proposed spending ceilings or paid runs.
Model availability, account access, spending, data handling, concrete capability
profile schema and actual pilot performance remain review/implementation gates.
No missing approved specification or new contradiction was found. Older open
technology/safeguard statements remain resolved by the configuration baseline;
its provider/model and monetary decisions are still open pending this review.

Current blockers are concrete: synthetic model callbacks cannot stand in for real
provider calls; the trace reader currently rejects non-null model identifiers;
the harness lacks a genuine-runtime mode; the driver expects exact authored query
shapes. This proposal records the required changes instead of bypassing those
guards or treating current component success as agentic acceptance.

## Verification

Validation on Python 3.14.8:

- `uv run --locked pytest`: **1,233 passed, 13 warnings in 42.24s**. The warnings
  are the existing upstream LangSmith asyncio deprecations.
- `uv run --locked hafi --version`: `hawaii-activity-forecaster 0.1.0`, exit 0.
- All 38 relative documentation links across the three changed/new files resolve;
  fenced blocks are balanced and both proposed cost calculations check out.
- Whitespace checks pass. Only README and the two new documents changed; approved
  specifications, application/test code, fixtures, pyproject.toml and uv.lock are
  unchanged.

These offline regressions cannot validate unimplemented provider behavior or live
quality. No live-provider tests or paid pilot were run.

Unchanged developer commands:

```bash
uv sync --locked
uv run --locked hafi --version
uv run --locked pytest
```

Recommended next increment after design review: **M1.6-E — Provider Gateway and
Structured Model Contracts**, with offline transport tests and disabled execution
by default. Genuine agent integration and an explicitly authorized paid pilot
follow separately. No commit or push is performed by this increment.
