# M2 — Local Web Interface Design

**Version:** 0.1 — Accepted
**Status:** Approved — M2 Local Web Interface Design
**Date:** 2026-11-20 (owner approval 2026-11-20)
**Scope:** Design only; no application code, dependency, test, fixture, prompt or policy change

## 1. Authority and purpose

This proposal records a design change for owner review, as `AGENTS.md` requires.
It adds a **local, optional web interface** on top of the existing M1 workflow.
It does not change the approved [technical plan](m1-technical-plan.md), the
[session lifecycle](m1-session-lifecycle.md), the
[execution design](m1-langgraph-execution-design.md) or any of the seven
[requirements specifications](../requirements/). The owner approved this design
on 2026-11-20. It authorizes no implementation in M1.

An earlier private design prototype explored four screens: Plan, Evidence,
No-result and Run inspector. This document defines how they would be connected to
the real workflow without letting the interface decide anything the trusted
Python components decide today.

### 1.1 Relationship to approved requirements

| Source | What it says | How this proposal relates |
|---|---|---|
| Product requirements §2.4 | The initial interface is a CLI; a graphical interface is not required for the MVP | The CLI stays the required interface. The web layer is additional and optional |
| Product requirements §8, out of scope | "Mobile applications or production web interfaces" | This is a local development and demonstration interface, not a production one. It binds to the loopback address only and has no accounts, hosting or real users |
| Test acceptance §11 | The CLI is the MVP's required user interface | Unchanged. All acceptance scenarios keep running through the existing harness |
| `AGENTS.md` | Feature freeze; three agents; no added agents or architecture without approval | No agent, graph, validator or policy is added or changed. Approval of this document is the required design change |

**Decision (2026-11-20): accepted** as M2 work, after the M1 submission. It is
not part of the submitted M1 release. The owner settled the §9 decisions the
same day, taking the proposed defaults.

## 2. Goals and non-goals

**Goals**

- Show the same validated results the CLI shows, with evidence, exclusions,
  limitations and source attribution easier to read.
- Let a reviewer browse an investigation's trace event by event.
- Make the three evidence types visible: authored demonstration, recorded
  genuine-model run, and a live run started from the page.
- Run fully offline for authored demonstrations and saved traces.

**Non-goals**

- No new agents, tools, prompts, profiles, safety rules or recommendation logic.
- No real environmental data or real beaches.
- No hosting, accounts, persistence of user requests or remote access.
- No active clarification resumption; that stays deferred as in the CLI.
- No new third-party Python dependency (WEB-OD-001).

## 3. Architecture

```
Browser (static HTML/JS, same origin)
   │  JSON over HTTP on 127.0.0.1
   ▼
hafi web  ──►  web adapter (new, thin)
                 ├─ AgentSession.ask(text)          existing, live or local runs
                 ├─ run_demo / run_session_demo     existing, authored runs
                 ├─ inspect_trace / read_trace      existing, trace validation
                 ├─ build_reliability_report        existing, evidence summary
                 └─ report_view(report, …)          new, beside render_report
```

**The interface only displays.** Eligibility, exclusions, evidence quality,
recommendations and abstention all come from the existing validated
`SkeletonReport`. The adapter never computes or reorders them.

### 3.1 New pieces

| Piece | Location | Responsibility |
|---|---|---|
| `report_view()` | `presentation.py`, beside `render_report()` | Returns a JSON-safe structure from a committed report. It goes through the same `_verified()` check as `render_report()`, so the text and web views cannot diverge or show an unvalidated result |
| `trace_view()` | new `web/views.py` | Maps an `InvestigationTrace` and its `TraceValidation` to rows for the Run inspector. Sanitized fields only, as already stored |
| Web adapter | new `web/server.py` | Routes requests to the existing functions above. Holds at most one `AgentSession` per process |
| `hafi web` | `cli.py`, new subcommand | Starts the server with the same explicit flags as `hafi run` |
| Static assets | `web/static/` | Plain HTML, CSS and JavaScript ported from the prototype. No build step, no CDN |

### 3.2 Command

```
hafi web --fixtures PATH [--config PATH] [--live | --local] [--case …]
         [--max-investigations 1..10] [--trace-directory PATH] [--port N]
```

- Without `--live` or `--local`, only authored demonstrations and saved traces
  are available, and no model is ever called.
- `--live` and `--local` behave exactly as in `hafi run`: `--config` becomes
  required, the same configuration and credential checks apply, and the same
  sanitized error messages are shown.
- `--case` takes the same synthetic cases as `hafi run`: `favorable`,
  `advisory`, `outage`, `recovery`.
- `--max-investigations` keeps its meaning: a hard per-process limit, default 3.
- The server binds to `127.0.0.1` only. There is no host option.

### 3.3 Endpoints

| Method and path | Calls | Model calls |
|---|---|---|
| `GET /api/status` | Configuration summary: mode, model identifier, profile, fixture clock, available windows, investigations remaining | None |
| `POST /api/demo/{advisory,outage,session}` | `run_demo` / `run_session_demo` | None |
| `POST /api/ask` | `AgentSession.ask(text)` | Yes, only when started with `--live` or `--local` |
| `GET /api/runs/{investigation_id}` | `report_view()` for a run made by this process | None |
| `GET /api/traces/{investigation_id}` | `inspect_trace` on a trace written by this process | None |
| `GET /api/evidence` | `build_reliability_report` over `docs/evaluation-evidence/` | None |

`/api/traces` reads only traces this process wrote, plus the published
evidence package. It never accepts a path from the browser.

## 4. Safety, cost and privacy controls

- **Loopback only.** The server refuses to start on anything except
  `127.0.0.1`.
- **Request token.** At startup the server prints a URL containing a random
  one-time token. Every `POST` must carry it, so other local pages cannot start
  paid runs.
- **One run at a time.** A second `POST /api/ask` while one is running returns
  HTTP 409. The investigation limit is checked before any model call.
- **Mode banner on every page.** It shows "Synthetic data · authored, no model
  calls", "Synthetic data · live model `gpt-6-luna`" or the local target. The
  wording comes from `/api/status`, not page text.
- **Same error handling as the CLI.** Provider, configuration and fixture
  errors map to the existing sanitized messages. Exception text, credentials and
  raw payloads are never sent to the browser.
- **Nothing new stored.** Requests and results stay in process memory and
  vanish on exit. Traces are written exactly as the CLI writes them.
- **Clarification.** An `AWAITING_CLARIFICATION` result shows the questions and
  states that a complete request must be submitted again, as the CLI does.

## 5. Session behavior

The page wraps one `AgentSession`, just as `hafi run --interactive` does.
A follow-up after a terminal result goes to `session.ask()` and becomes a new
investigation with a new trace, as in SC-012. A technical failure ends the
session, matching the CLI. Closing the server calls `session.close()`.

## 6. Data shown versus data computed

| Shown in the page | Source | Computed by the web layer? |
|---|---|---|
| Recommendations, labels, limitations | `RecommendationResult` via `report_view()` | No |
| Exclusions and reasons | Validated state, as `render_report()` uses | No |
| Evidence and attribution per beach | Validated findings | No |
| Abstention reason | `completion_reason` / `no_recommendation_reason` | No |
| Event timeline and totals | Trace events and `TraceValidation` metrics | Formatting only |
| Durations | Recorded `duration_ms` and timestamps | Formatting only |

## 7. Screens

| Screen | Purpose | Data |
|---|---|---|
| Plan | Request entry, recommendations, exclusions, follow-up box | `/api/status`, `/api/ask` or `/api/demo/*`, `/api/runs/*` |
| Evidence | Per-beach evidence with sources and validation status | `/api/runs/*` |
| No-result | Explained abstention: what is missing, what was tried, limits used | `/api/runs/*`, `/api/traces/*` |
| Run inspector | Event timeline, filters and event detail | `/api/traces/*` |

**Corrections needed when porting the prototype.** The prototype used
illustrative values. The real build must show recorded values:

- Error codes come from the trace, for example `SOURCE_UNAVAILABLE` and
  `SOURCE_TIMEOUT`, not the prototype's `PROVIDER_UNAVAILABLE`.
- Tool names are the trace's uppercase identifiers, such as `NWS_MARINE`.
- Model-call counts must reflect the run: 0 for authored demonstrations, 4–5
  for the recorded `gpt-6-luna` runs. The page labels which kind of run it is.
- The prototype's `clarification_needed` field does not exist in traces and is
  dropped.
- Timelines use recorded timestamps, not illustrative timings.

## 8. Testing

Every test is offline and uses synthetic data. Proposed acceptance tests:

| ID | Check |
|---|---|
| WEB-T01 | `report_view()` rejects an unvalidated or uncommitted report exactly as `render_report()` does |
| WEB-T02 | For each authored demo, `report_view()` and `render_report()` list the same recommended, excluded and abstained beaches |
| WEB-T03 | Without `--live`/`--local`, `POST /api/ask` is refused and no provider client is constructed |
| WEB-T04 | A `POST` without the startup token is refused |
| WEB-T05 | The server refuses a non-loopback address |
| WEB-T06 | A second concurrent `POST /api/ask` returns 409; the investigation limit is enforced before any model call |
| WEB-T07 | Provider, configuration and fixture errors return the CLI's sanitized messages, with no exception text |
| WEB-T08 | `/api/traces` cannot read a path outside this process's traces and the evidence package |
| WEB-T09 | `trace_view()` of each published evidence trace matches `hafi trace` metrics |
| WEB-T10 | A follow-up via mock HTTP creates a second investigation in the same session, as in SC-012 |
| WEB-T11 | Every page shows the mode banner from `/api/status` |
| WEB-T12 | The existing suite, all twelve acceptance scenarios and the CLI output are unchanged |

Live checks stay owner-run and paid, as today.

## 9. Owner decisions

Settled by the owner on 2026-11-20, taking the proposed defaults.

| ID | Question | Decision |
|---|---|---|
| WEB-OD-001 | Server library: standard library `http.server` or a framework such as FastAPI | **Standard library.** No new dependency and no lockfile change |
| WEB-OD-002 | Allow live runs from the page in M2, or only authored demonstrations and saved traces | **Allow live runs**, with the controls in §4 |
| WEB-OD-003 | Include follow-ups in the interface | **Yes, matching `--interactive`, in WEB-A.** Live sessions and follow-ups ship in the first increment (owner decision, 2026-11-20) |
| WEB-OD-004 | Add browser-level tests to CI | **No.** API and view tests only |
| WEB-OD-005 | Record the evaluated source revision in future traces (the M1 evidence gap) here or separately | **Separately.** Not part of this design |

## 10. Effort and increments

The estimated size is about 2,000 lines including tests, in **one increment,
WEB-A**. The owner moved live sessions and follow-ups into it on 2026-11-20. Live
runs cannot ship without the §4 controls, so those come with it, and the
earlier second increment no longer exists. WEB-A is built in this order:

1. **Offline first.** `report_view()`, `trace_view()`, the server, the four
   screens, authored demonstrations and saved traces. WEB-T01–T05, T08, T09,
   T11.
2. **Live second.** `/api/ask`, session follow-ups, the request token, the
   one-run limit and error mapping. WEB-T06, T07, T10.
3. **Regression.** WEB-T12 over the whole increment.

WEB-A is complete only when all twelve tests pass. Live checks stay owner-run
and paid.

The main risk is the view mapping in `report_view()`. Building it on the same
helpers as `render_report()` and testing the two against each other (WEB-T02)
keeps that risk contained.

## 11. Out of scope

Hosting or remote access, user accounts, mobile layouts beyond responsive pages,
real environmental providers, real beaches, active clarification resumption,
and any change to agent behavior, prompts, profiles or safety policy.
