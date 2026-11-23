# M2 WEB-A — Local web interface

Implements the single increment of the accepted
[M2 local web interface design](../implementation/m2-local-web-ui-design.md), as
authorized by the owner on 2026-11-20. M1 behavior is unchanged: no agent, graph,
prompt, profile, validator, safety policy, fixture, dependency or lockfile change.

## Commands

Offline, authored demonstrations and recorded runs only, with no credentials and
no model calls:

```bash
uv run --locked hafi web --fixtures fixtures/scenario-pack-v1
```

With live model runs (paid calls, same opt-in and configuration as `hafi run`):

```bash
uv run --locked --env-file keys/apsi.env hafi web --fixtures fixtures/scenario-pack-v1 --release-fixtures fixtures/saturday-release --config haf.release.example.toml --live --max-investigations 2
```

Open the printed `http://127.0.0.1:<port>/#token=…` URL. Ctrl+C stops the server.

## What was built

| Piece | Location |
|---|---|
| `report_view()` | `presentation.py`, beside `render_report()`; shares `_verified()` and the fixed wording helpers |
| `trace_view()`, `EvidencePackage` | `web/views.py` |
| `WebApp`, `create_server()` | `web/server.py` (standard-library `http.server`) |
| `hafi web` | `web/cli.py`, registered in `cli.py` |
| Pages | `web/static/index.html`, `app.js`, `styles.css` |
| Tests | `tests/test_web.py`, WEB-T01–T12 |

Two small refactors keep the CLI and web wording identical: the exclusion reasons
and measurement text are now helpers (`_exclusion_reasons`, `_measurement`) called
by both `render_report()` and `report_view()`. `render_report()` output is unchanged.

**Screens.** Plan (request, demos, runs, result), Evidence (per-beach judgments,
source timeline, evidence used and not used, checks, catalog facts), Run inspector
(totals, actor timeline, filtered events, event detail) and Recorded runs (the six
published `gpt-6-luna` traces). An abstention renders in the prototype's
No-result layout inside Plan, with "What was tried" read from the run's trace.

## Controls (design §4)

- Binds `127.0.0.1` only; `create_server()` refuses any other address, and
  requests with an unexpected `Host` header are refused.
- Every `POST` needs the per-process token from the printed URL. The page keeps it
  in `sessionStorage` for that tab and removes it from the address bar.
- One run at a time (HTTP 409). The process allowance is checked before any session
  admission or model call (HTTP 429).
- The banner comes from `/api/status`. Errors use the CLI's sanitized wording;
  exception text never reaches the browser. Request lines are not logged.
- Content-Security-Policy `default-src 'none'` with same-origin scripts and styles;
  no inline scripts or handlers, no external fonts or CDNs.
- Traces open only by a run made in this process or by a name listed in the
  evidence manifest. Static files are a fixed list.

## Deviations from the design, for owner review

| Design | Implementation | Reason |
|---|---|---|
| One `--fixtures` flag | `--fixtures` (scenario pack, demos) and `--release-fixtures` (required with `--live`/`--local`) | Authored demos load `fixtures/scenario-pack-v1`; live runs load `fixtures/saturday-release`, as `hafi demo` and `hafi run` already do |
| Endpoints in §3.3 | Adds `POST /api/session/reset` | Starts a new session without restarting, matching a new `hafi run` |
| Evidence path fixed | Adds optional `--evidence PATH` (default `docs/evaluation-evidence`) | Lets the server run from outside the repository root |
| Four prototype screens | No-result is a Plan state; a Recorded runs screen is added | An abstention belongs to a run; the recorded traces need an entry point |

No deviation adds a dependency or changes M1 behavior.

## Verification (2026-11-20)

- `tests/test_web.py`: **26 passed** (WEB-T01–T12, some parametrized).
- Full suite: **1,556 passed, 1 xfailed** (1,530 existing plus 26 new; the same
  documented expected failure).
- Browser check with authored demonstrations: Plan, Evidence, No-result layout,
  Run inspector, Recorded runs and the session follow-up all render with no console
  errors; no horizontal scrolling at 375 px width.
- **Not yet verified:** a live `gpt-6-luna` run through the page. It makes paid
  calls and is owner-run, using the second command above. Live sessions and
  follow-ups are covered offline through SDK mock HTTP (WEB-T06, T07, T10).
