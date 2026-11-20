# M1 integration completion report

**Evidence reviewed:** 2026-11-20  
**Implementation baseline:** `eb8761f4aee9792eb56a47aae7b782b68d3dca41`  
**Current configuration:** `m1-saturday-runtime-0.7`, `gpt-6-luna`  
**Current scenario pack:** dataset `1.6.0`, fixture format `2.0.0`

## Conclusion and scope

Evidence supports all fifteen approved [M1 completion criteria](../implementation/m1-technical-plan.md#16-m1-completion-criteria)
within the [approved synthetic release scope](../implementation/m1-saturday-release-scope.md).
All twelve registered scenarios have recorded live scenario-level PASS results.
Eleven passed on profile 0.6; SC-002 passed on 0.7. This is not a single all-twelve
confirmation on the latest profile or a measured reliability rate. A subsequent
owner-authorized 0.7 batch passed 10/12; SC-006 and SC-008 failed, as detailed below. Earlier failed
attempts remain in the linked development records and local traces.

Scenario-level PASS does not mean every assertion passed: optional failures and
blocked checks remain explicit below. This is M1 synthetic integration evidence,
not full real-world MVP acceptance or a claim of verified ocean conditions.
Owner sign-off is separate from this evidence report.

The owner subsequently authorized one live clarification investigation, which
passed on profile 0.7 as recorded below. No commit, push, requirements change or
architecture change was made for this close-out. The owner also authorized the all-twelve 0.7 rerun recorded below. No additional
paid calls were made while investigating its failures.

## Approved completion criteria

| # | Criterion | Evidence | Review status |
|---|---|---|---|
| 1 | CLI accepts supported activity requests | `test_request_validation.py`, `test_release_cli.py`, `test_agent_release.py`; pilot all three activities | Verified; live clarification passed on profile 0.7 during close-out |
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
| 15 | Selected M1 scenarios pass their executable scope | Twelve live PASS reports and thirteen verified traces, indexed below; `test_agent_scenarios.py` | Verified for mandatory synthetic assertions; optional FAIL/BLOCKED rows retained |

Criterion 1's supported-activity CLI behavior is verified. The original pilot did
not exercise live clarification; the separately authorized close-out check now
confirms it, alongside the offline SDK/CLI checks. Criterion 11 covers the
approved post-terminal revision lifecycle; active clarification resumption is deferred.

## Registered live scenario evidence

All rows below are historical owner-run reports from 2026-11-20. During close-out,
all thirteen corresponding JSONL files were independently validated as complete,
matched to the report's SHA-256, and checked for `LIVE_PROVIDER`. This validates
trace integrity and the recorded mode; it does not regrade historical runs against
newer datasets, policies or oracles. The linked increment documents retain the
applicable versions, owner decisions and failed attempts.

Reports and traces under `traces/acceptance/` are ignored local artifacts, absent
from a fresh clone. Report basenames and full trace digests below allow an owner
with those files to reproduce the integrity check without paid calls. No raw
request, model payload, credential or trace contents are copied into this report.

| Scenario | Mandatory PASS | Profile | Optional outcomes | Local report basename | Decision / evidence record |
|---|---|---|---|---|---|
| SC-001 | 86/86 | 0.6 | None | `final06-SC-001.json` | [Record](m1-9b-profile-0.4-rebaseline.md) |
| SC-002 | 65/65 | 0.7 | None | `m112-SC-002.json` | [Record](m1-12-sc-002-wind-chop.md) |
| SC-003 | 55/55 | 0.6 | None | `final06-SC-003.json` | [Record](m1-9b-profile-0.4-rebaseline.md) |
| SC-004 | 84/84 | 0.6 | None | `final06-SC-004.json` | [Record](m1-9b-profile-0.4-rebaseline.md) |
| SC-005 | 59/59 | 0.6 | 1 BLOCKED | `m111b-SC-005.json` | [Record](m1-11-sc-005-sc-008.md) |
| SC-006 | 62/62 | 0.6 | 1 BLOCKED | `m110-SC-006.json` | [Record](m1-10-sc-006-sc-007-sc-011.md) |
| SC-007 | 78/78 | 0.6 | 6 FAIL, 1 BLOCKED | `m110c-SC-007.json` | [Record](m1-10-sc-006-sc-007-sc-011.md) |
| SC-008 | 45/45 | 0.6 | 1 BLOCKED | `m111b-SC-008.json` | [Record](m1-11-sc-005-sc-008.md) |
| SC-009 | 73/73 | 0.6 | None | `final06-SC-009.json` | [Record](m1-9b-profile-0.4-rebaseline.md) |
| SC-010 | 61/61 | 0.6 | None | `final06-SC-010.json` | [Record](m1-9b-profile-0.4-rebaseline.md) |
| SC-011 | 70/70 | 0.6 | None | `m110-SC-011.json` | [Record](m1-10-sc-006-sc-007-sc-011.md) |
| SC-012 | 83/83 | 0.6 | 1 BLOCKED | `final06-SC-012.json` | [Record](m1-9b-profile-0.4-rebaseline.md) |

### Optional outcomes and approved interpretations

- **SC-005:** wind measurement/orientation-to-hazard classification remains BLOCKED;
  the executable scenario enforces a declared synthetic disqualifying hazard.
- **SC-006:** clear-water preference interpretation is BLOCKED. The preference is
  retained as UNINTERPRETED; it cannot be claimed satisfied.
- **SC-007:** production freshness cutoffs are BLOCKED. Six optional Snorkel Store
  assertions FAIL because that redundant report was skipped. Mandatory HWT stale
  report checks pass; retrieval time does not make stale data current. The owner
  approved the optional-source treatment in M1.10; earlier failing reports were
  not overwritten.
- **SC-008:** automatic material-conflict classification is BLOCKED; enforcement
  of a declared synthetic material conflict passes.
- **SC-012:** historical evidence reuse representation is BLOCKED; each revision
  retrieves its own evidence.
- **SC-001:** exact catalog locality matching makes only A preferred for Kihei;
  no nearby-area inference is made. The owner-recorded deviation is in [M1.9](m1-9-sc-001-sc-003.md).
- **SC-002:** the owner approved swimming wind-chop MIXED permission under HM-T05,
  clause recognition and profile 0.7. C is FAVORABLE and A MIXED with disclosure;
  recommendations carry no numeric rank. See [M1.12](m1-12-sc-002-wind-chop.md).

## Close-out verification

- `uv run --locked pytest -q`: **1499 passed, 1 xfailed, 13 warnings in 84.10s**,
  using the existing Python 3.14 environment. Warnings are upstream LangSmith
  asyncio deprecations. The strict expected failure is the deferred Ollama
  preferred-area input bound; it is not a failure of the OpenAI release profile.
- Thirteen complete live traces matched all twelve selected passing reports and
  passed the current independent trace validator, without provider access.
- The earlier clean Python 3.12 rehearsal is recorded in the
  [readiness checklist](m1-release-readiness-and-demo.md#clean-environment-validation-2026-11-19-macos-arm64-uv-01219).
  It predates the later scenario additions; it is not a new 3.12 run of this baseline.
- Hosted CI and required-check enforcement need confirmation from GitHub. Local
  test results do not establish remote branch-protection settings.

The [demo runbook](../demo-runbook.md) contains the offline rehearsal, current
profile, optional all-twelve command batch and separate clarification command.
The all-twelve rerun would normally use about 65 model calls in thirteen
investigations. The authorized rerun results are recorded below.

## Authorized live clarification check (2026-11-20)

One owner-authorized invocation used `haf.release.example.toml`, profile
`m1-saturday-runtime-0.7`, `gpt-6-luna`, `LIVE_PROVIDER`, the synthetic release
fixtures and `--max-investigations 1`. It was run once, with no rerun.

- **Request:** "Where tomorrow morning?"
- **CLI response:** "Which supported activity do you want: swimming, snorkeling or SUP?"
- **Exit code:** `2`, the expected clarification result.
- **Validated trace:** 1 model call, 0 specialist requests, 0 environmental tool
  calls, 0 Coordinator iterations, 0 retries and 0 fallbacks; no recommendations.
- **Last event:** `CLARIFICATION_REQUESTED`. The independent validator accepted
  the trace with `complete: false`, as expected for a nonterminal investigation
  awaiting clarification. This differs from the thirteen terminal scenario traces.
- **Trace file:** local
  `traces/clarification-0.7-closeout-1795206148959/a375edc9-050a-4b88-953b-18ba4dc65899.jsonl`.
- **SHA-256:** `e2fc2c3a3266a3aaa00bb3c976af5fe5b5c7b611c6855e4d4efa57c3c7f92974`.

Active clarification resumption remains deferred; the CLI instructs the user to
submit a complete clarified request in a new run. This check adds live evidence
for the existing behavior without changing it.

## Profile 0.7 rerun and SC-006 investigation (2026-11-20)

The owner authorized one all-twelve rerun. Its saved reports are under local
`traces/acceptance-0.7-closeout-1795206283375/SC-NNN.json`, with per-command exit
codes in `batch-status.json`. **10/12 scenarios passed**; SC-006 and SC-008 failed.
All thirteen terminal traces independently validate. The historical passes above
remain valid historical observations; the current rerun is not all green.
SC-007 again passed with six optional FAIL assertions and one optional BLOCKED.
No failed scenario was automatically rerun.

### SC-006: unsupported preference omitted during normalization

The owner's separate failing report, `traces/acceptance/m111b-SC-006.json`, binds to
`traces/acceptance/e6d06c16-f61f-4fae-acf3-1dd54ae8f882.jsonl`, SHA-256
`f5d95546cfb4e4ddda1b1606e3aa9a8b8c3d502dd811c5bb4b4555bcc132bd45`.
The trace independently validates and records:

- One successful model response for `normalize_request`, profile 0.7.
- A rejected request interpretation: `REQUEST_CHANGE_OMITTED`, field `soft_preferences`.
- Zero environmental tools and no specialist dispatch before terminal `ERROR`.
- Scenario `APPLICATION_FAILURE`: 6 PASS, 56 FAIL, 1 optional BLOCKED. Most assertion
  failures are downstream consequences of the early normalization failure.

The earlier batch's SC-006 trace has the same rejection code and field.
The request's "prefer clear water" must be retained as an UNINTERPRETED soft
preference, because no clear-water interpretation is approved. Omitting both that
field and a covering unresolved phrase span is rejected. Offline reproduction
confirmed that the omitted proposal fails with this exact code, whereas either
an explicit UNINTERPRETED entry with a full source span or a full unresolved phrase
span passes request validation and retains the preference. Neither requires
clarification or claims the preference is satisfied.

The current prompt gives an explicit CALM_WATER example but no corresponding
UNINTERPRETED preference example. It mentions unsupported "constraint meaning"
without showing the precise representation. This is a likely prompt-guidance gap;
raw model proposals are deliberately not retained, so the exact returned spans
cannot be reconstructed. It is not evidence of failed MIXED safety evaluation:
that stage was never reached.

Recommended next change for owner review: a new prompt/profile version with an
explicit generic unsupported-soft-preference example and whole-phrase span guidance,
retaining profile 0.7 bytes and all deterministic guards. No prompt, policy, schema,
fixture, application code or test file was changed during this investigation.
SC-008's separate assertion failure is not diagnosed by the SC-006 finding.

## Work outside this completion claim

Verified real-beach catalog completion, live environmental providers, production
freshness/hazard/materiality rules, generalized capability profiles, cross-delegation
recovery, active clarification resumption, persistent sessions, optional LangSmith
dashboards and local Qwen qualification remain outside this close-out. Approved
scope and explicit optional assertion blockers govern further work.

## Trace integrity index

All filenames below are relative to local `traces/acceptance/`. Use `hafi trace`
on a file to validate it and inspect actual call/recovery metrics. Earlier profiles
and prompt digests are retained for historical trace validation.

| Scenario / request step | JSONL filename | SHA-256 |
|---|---|---|
| SC-001 / 1 | `5aba39c3-a6ec-441a-bf74-d18f097f8b11.jsonl` | `b540608debf8535c6961a1d5a64392f3dbdfc67f343816426ca3662f0b985f1d` |
| SC-002 / 1 | `edb6aa2f-7b6f-4708-9d46-29d936022a85.jsonl` | `4beb255d47db1d40ce9feb91e44cb36665a556fa1775e47340bc6e0bde0d6020` |
| SC-003 / 1 | `258e4eb4-8646-4642-8610-5f83729b5ca2.jsonl` | `0818fde75e0f9986ab3ff571a4d3f308d534c6f14024f255811de991d140638d` |
| SC-004 / 1 | `08c7af3b-72ec-4071-8423-6a1cf82d8d78.jsonl` | `b4bbc1b2b17d65a6f2ba95efdeda2ea7bd67ca4378367dcd5d404fe810ab2c9e` |
| SC-005 / 1 | `8176fb03-18dc-4947-bbd8-20cca6fafb62.jsonl` | `02e1fdfd354510dd33e23798aab06f662c57bf43b2241f2f219e8cc2ccb7dc75` |
| SC-006 / 1 | `08a0be67-ade9-40ed-8f61-ec1bdaa0ca09.jsonl` | `b5b1b83275fe00d919033919a6274d8c5d4eb1acad3a603a386185611d7d4b95` |
| SC-007 / 1 | `84299097-fcf8-40e7-96eb-a69bad254cb4.jsonl` | `2b6a2d8fe75ef2186caa52a5a86109e4ba5405c8d1040c7415126d9975a50d1f` |
| SC-008 / 1 | `8ba61f9f-cafa-4573-9036-027aa00dda1a.jsonl` | `d68314adb63a6cd332beb67ccee36071a1791e5942c8b903de3806b91690e8b2` |
| SC-009 / 1 | `037e50d2-c829-4a6c-9cf5-1082538be158.jsonl` | `ea92e9f20f777a0a5af5c80d87999d324f2adf00fbaa238e3fb3025a99a624cd` |
| SC-010 / 1 | `01f5bda1-e427-4761-aa83-78413f9bd0d4.jsonl` | `c0d0604ad3089d28cc9580803d163c8ec5a4ed85654260c609f120d90c524e3e` |
| SC-011 / 1 | `eefb7e7c-d69c-4523-ae6e-20140c820416.jsonl` | `68c7b6caf538e4bfba6c06ae2740397052c90c8dd5e38ccedb393b8cfbaaa341` |
| SC-012 / 1 | `fbde8822-7093-469b-b55a-819dcbc9cc50.jsonl` | `d45e7b56073cdb853a51104f76b33c7afabc41d097efca2c18dcfadd3562ae7a` |
| SC-012 / 2 | `0a4e9de0-8252-4685-81fe-fbf7066d66f7.jsonl` | `c150ce0be258dbeb6692739089be854f8b799254566a6e9db99fd454802077aa` |
