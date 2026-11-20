# M1 release readiness and demo preparation

Implements the owner-approved next batch on `m1-release-readiness-and-demo` under
the [Saturday release scope](../implementation/m1-saturday-release-scope.md).
Approved requirements/architecture, fixtures, schemas, safety decisions, model
targets and execution limits remain unchanged. Local Qwen work is deferred.
No paid model call, commit or push is part of this batch.

> Current live gate: the owner temporarily deferred SC-006 and SC-008 after the
> profile 0.7 rerun passed 10/12. The selected rerun now reports them as NOT_RUN;
> offline tests and safety validation remain enabled. See the
> [deferment record](m1-live-acceptance-deferments.md). Historical passes below do
> not establish that the current all-twelve live rerun is green.

## GitHub test gate

The old `.github/workflow/tests.yml` contained two shell commands and was not a
discoverable GitHub Actions workflow. Its replacement is
[`.github/workflows/tests.yml`](../../.github/workflows/tests.yml).

The workflow runs on pull requests, pushes to `main`, and manual dispatch. Its
stable required-check name is **`pytest`**, under workflow **`Tests`**. It selects
Python 3.12, installs uv 0.12.19, runs `uv sync --locked`, then `uv run --locked pytest`.
There are no model credentials or live inference commands. The two setup actions
are pinned to verified full commit SHAs; the job has read-only contents permission,
a ten-minute timeout and cancellation of superseded runs for the same ref.

This deliberately uses the existing uv/pytest stack, one Python job and the existing
lockfile. It adds no service, deployment, test framework or dependency upgrade.

### Enable required status checking after publication

The repository file defines the check; a GitHub setting makes it a merge gate.
After the owner pushes the branch and opens a PR, let **Tests / pytest** run once.
Then, in repository **Settings → Branches**, edit/create the protection rule for
`main`, enable **Require status checks to pass before merging**, and select the
**pytest** check produced by **GitHub Actions**. If a ruleset already protects
`main`, add the same required check there instead of creating a conflicting rule.
Retain any existing protections. Requiring the branch to be up to date also ensures
the check tests the current merge base.

Confirm the PR displays this check as required and a failure prevents merging
under that rule. Keep the job name stable. Hosted execution and branch-protection
enforcement cannot be claimed from local tests; no GitHub settings or remote refs
are changed by this batch.

Sources: [GitHub workflow location and structure](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows),
[Astral uv integration](https://docs.astral.sh/uv/guides/integration/github/),
[setup-uv inputs](https://github.com/astral-sh/setup-uv),
[required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule).

> Current close-out: see the [M1 completion report](m1-completion-report.md) for
> consolidated criterion coverage, all twelve live passes, optional assertion
> outcomes, the passing live clarification check and the subsequent 0.7 scenario rerun (10/12 PASS, with SC-006 and SC-008 failures). Earlier validation below is
> historical and retains its original versions.

## M1 completion-criterion review

The following maps the fifteen criteria in the approved
[technical plan §16](../implementation/m1-technical-plan.md#16-m1-completion-criteria)
to existing evidence. "Verified" is limited to supported synthetic behavior.
The [OpenAI pilot](m1-openai-pilot.md) is a bounded observation; routine tests use
mock HTTP or authored components, not paid inference.

| # | Criterion | Evidence | Review status |
|---|---|---|---|
| 1 | CLI accepts supported activity requests | `test_request_validation.py`, `test_release_cli.py`, `test_agent_release.py`; pilot all three activities | Verified; separately authorized live clarification passed on profile 0.7 ([close-out evidence](m1-completion-report.md#authorized-live-clarification-check-2026-11-20)) |
| 2 | LangGraph executes Coordinator workflow | `test_orchestration_skeleton.py`, `test_raw_request_graph.py`, `test_agent_release.py`; real pilot role/cycle traces | Verified |
| 3 | Specialists use approved contracts | `test_specialist_exchange.py`, `test_specialist_graph.py`, `test_model_runtime_contracts.py`; pilot Weather/Ocean calls | Verified |
| 4 | Specialist concurrency is bounded | `test_orchestration_budgets.py`, `test_specialist_graph.py`; trace reconstruction | Verified |
| 5 | Calls, retry and fallback stay bounded | `test_synthetic_tools.py`, `test_model_gateway.py`, `test_ollama_target.py`, `test_orchestration_budgets.py`; recovery pilot | Verified; thirteenth model dispatch blocked in offline tests |
| 6 | Synthetic findings preserve metadata | `test_models.py`, `test_fixtures.py`, `test_synthetic_tools.py`, `test_trace_validation.py` | Verified |
| 7 | Evidence validation is enforced | `test_evidence_validation.py`, `test_evidence_graph.py`, delivery-boundary tests in `test_agent_release.py` | Verified; real-world freshness/materiality rules remain out of scope |
| 8 | Deterministic policies govern eligibility | `test_safety_evaluation.py`, `test_safety_graph.py`; pilot advisory exclusion | Verified for explicit synthetic policies |
| 9 | Only supported eligible candidates are recommended | `test_results.py`, `test_result_graph.py`, `test_presentation.py`; pilot SUP dispatches only B | Verified |
| 10 | Unresolved mandatory evidence causes abstention | `test_results.py`, `test_agent_release.py`; outage pilot | Verified |
| 11 | Follow-ups use approved lifecycle | `test_session_lifecycle.py`, `test_raw_session_lifecycle.py`, `test_release_cli.py`; same-session pilot revision | Verified for post-terminal follow-ups; active clarification resumption remains deferred |
| 12 | Results pass schema and grounding checks | `test_results.py`, `test_result_graph.py`, `test_presentation.py`; independent pilot trace/result checks | Verified |
| 13 | Local traces satisfy required assertions | `test_trace_storage.py`, `test_trace_validation.py`, `test_model_trace_validation.py`; ten independently checked pilot traces | Verified |
| 14 | LangSmith is optional | `test_model_gateway.py`; shared disabled remote-tracing contexts; offline commands need no tracing credentials | Verified |
| 15 | Selected acceptance scenarios pass executable scope | `test_scenario_execution.py`, `test_harness_evaluation.py`, `test_agent_scenarios.py`; 84 SC-004 / 61 SC-010 assertions pass for authored plans and for the agent runtime over offline transport | Adapter connected ([M1.7-A](m1-7a-agentic-scenario-adapter.md)); Full PASS observed live for SC-004 (84/84) and SC-010 (61/61), on 2 of 3 and 1 of 2 live attempts; failed attempts failed closed. SC-009 full PASS live (73/73, 1 of 1 attempt); SC-012 full PASS live on profile 0.3 (83/83 mandatory, 1 of 1 attempt); SC-001 full PASS live (2 of 4; 1 of 1 on profile 0.4), SC-003 full PASS live on profile 0.4 (1 of 2), SC-002 deferred ([M1.9](m1-9-sc-001-sc-003.md)) ([M1.8](m1-8-sc-009-sc-012.md)); final pass on release profile 0.6: **6/6 registered scenarios PASS live** ([M1.9-B](m1-9b-profile-0.4-rebaseline.md)); SC-006, SC-007 and SC-011 PASS live on 0.6; **all nine registered scenarios have passed live** ([M1.10](m1-10-sc-006-sc-007-sc-011.md)); SC-005 and SC-008 PASS live on 0.6: **all eleven registered scenarios have passed live** ([M1.11](m1-11-sc-005-sc-008.md)); SC-002 PASS live on 0.7: **all twelve acceptance scenarios registered with live passes** ([M1.12](m1-12-sc-002-wind-chop.md)); **profile 0.8 all-twelve live batch: 12/12** ([completion report](m1-completion-report.md)) |

The broader SC-001–012 behavior mapping is retained in the
[integration notes](m1-integration-release.md#acceptance-evidence-and-limits).
This checklist does not mark all approved product requirements or formal full
scenario acceptance complete. Exact geographic/suitability tradeoff criteria,
production hazard thresholds, operational conflict rules, real-beach verification
and live environmental providers remain explicit unresolved/deferred work.

## Precise registered-scenario blocker

> **Superseded by [M1.7-A](m1-7a-agentic-scenario-adapter.md).** The adapter described
> below is now connected; `SCENARIO_ADAPTER_UNAVAILABLE` is retired in favor of
> `AGENT_EXECUTION_NOT_RUN`, `AUTHORED_COMPONENT_SCOPE` and `OFFLINE_MODEL_TRANSPORT`.
> The clean-environment results below were recorded before that change.

The real agent runtime works through `hafi run` with the explicit release tool
allowlists and release fixture package. The registered scenario harness still
accepts only `AUTHORED_COMPONENT` runners and captures. Its SC-004/SC-010 input
package has its own batches, zones, behavior bindings and expected artifacts.
Those interfaces are not connected to scoped agent options and verified agentic
capture/evaluation. This is the missing integration, not absent OpenAI access or
absent Coordinator/Weather/Ocean implementations.

`execution_readiness.reason` now explains that distinction. The report category is
**`SCENARIO_ADAPTER_UNAVAILABLE`**, replacing **`AGENTIC_RUNTIME_UNAVAILABLE`**.
This is diagnostic metadata; outcome enums, assertion semantics, input preflight,
mandatory-failure precedence and the full-scenario gate are unchanged. A failed
active mandatory assertion still yields FAIL; authored success alone remains
BLOCKED for full scenario acceptance. No blocked assertion is changed to PASS.

Connecting those registered scenarios remains separate work under the approved
scope. It does not require reviving the deferred generalized capability-profile
framework or importing expected results into model context.

## Demo and verification

Use the [demo runbook](../demo-runbook.md) for the short offline rehearsal and
reference real-model command cards. It records fixed dates, expected outcomes,
exit codes, actual trace counts and the distinction between authored, mock and
real-model evidence. Existing pilot files are optional local evidence, not files
available in a fresh clone.

### Clean-environment validation (2026-11-19, macOS arm64, uv 0.12.19)

Tracked and non-ignored files were copied into a temporary tree without `.git`,
`.venv`, ignored keys or traces (only the placeholder `keys/apsi.env.example`).
`OPENAI_API_KEY` was unset. `uv sync --locked --python 3.12` installed from the
unchanged lockfile.

| Check | Result |
|---|---|
| `uv run --locked pytest` | **1362 passed**, after updating `test_scenario_fixtures.py`'s stale `'not implemented'` readiness-reason assertion to the new wording (BLOCKED assertion unchanged) |
| `hafi --version`, `hafi run --help` | `0.1.0`; help printed, no model executed; exit 0 |
| `demo advisory` | Only Beach B recommended; exit 0. Trace: complete, 6 tool calls, 0 model calls, 1 iteration, 1 excluded candidate (`CANDIDATE_EXCLUDED` for TEST_BEACH_A) |
| `demo outage` | `No recommendation`; exit 0. Trace: complete, 8 tool calls, 1 retry, 2 fallbacks, outcome `NO_RECOMMENDATION` |
| `demo session` | Revisions 1 and 2, two distinct trace files; exit 0 |
| `evaluate SC-004 --component` | exit 2; component PASS 84/84; scenario BLOCKED `SCENARIO_ADAPTER_UNAVAILABLE` |
| `evaluate SC-010 --component` | exit 2; component PASS 61/61; scenario BLOCKED `SCENARIO_ADAPTER_UNAVAILABLE` |

Workflow action pins were checked against upstream tags: `actions/checkout`
v7.0.1 → `3d3c42e5…`, `astral-sh/setup-uv` v10.3.3 → `68559e99…`.
Linux-hosted CI remains pending the owner's push/PR, and no paid model check was
authorized or executed.

Presentation observations (not blockers): the outage abstention repeats "Synthetic
fact is not declared" for every beach. Excluded candidates are now named in a
"Not recommended (excluded)" section ([M1.8-B](m1-8b-cli-exclusion-disclosure.md)).
