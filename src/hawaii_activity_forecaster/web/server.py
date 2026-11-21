"""Loopback-only HTTP adapter over the existing CLI workflow (M2 WEB-A).

The adapter routes requests to functions the CLI already uses: authored demos,
``AgentSession.ask`` for model-driven runs, ``inspect_trace`` for traces and the
reliability summary for the published evidence package. It never computes
eligibility, safety or recommendations; ``report_view`` supplies validated
results under the same checks as ``render_report``.
"""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import secrets
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import unquote, urlsplit

from hawaii_activity_forecaster.presentation import PresentationError, report_view
from .views import EvidencePackage, trace_view

_STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
           "/index.html": ("index.html", "text/html; charset=utf-8"),
           "/app.js": ("app.js", "text/javascript; charset=utf-8"),
           "/styles.css": ("styles.css", "text/css; charset=utf-8")}
_HEADERS = {
    "Content-Security-Policy": ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
                                "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"),
    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
}
_MAX_BODY = 16_384
_TOKEN_HEADER = "X-HAF-Token"
# The same sanitized wording as the CLI; exception text never reaches the browser.
TECHNICAL_ERROR = "Technical error: no validated result is available for this investigation."
DEMO_ERROR = "Technical error: the synthetic demonstration could not be completed."
SESSION_ERROR = "Technical error: the synthetic session could not be completed."
FIXTURE_ERROR = "Cannot load the synthetic fixture package. Check --fixtures and its validated contents."
CONFIG_ERROR = "Cannot load a valid application configuration."


class WebRequestError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status, self.message = status, message


@dataclass
class Run:
    run_id: str
    kind: str                 # "authored" | "live" | "local"
    label: str
    request_text: str | None
    view: dict | None
    trace_path: Path | None
    session_key: str | None = None
    extra: dict = field(default_factory=dict)

    def summary(self) -> dict:
        view = self.view or {}
        return {"run_id": self.run_id, "kind": self.kind, "label": self.label, "request_text": self.request_text,
                "outcome": view.get("outcome") or self.extra.get("outcome"),
                "request_revision": view.get("request_revision"), "session_key": self.session_key,
                "has_trace": self.trace_path is not None, "has_view": self.view is not None,
                "message": self.extra.get("message"), "questions": self.extra.get("questions")}


class WebApp:
    """State for one local process: authored runs, at most one live session, one run at a time."""

    def __init__(self, *, demo_fixtures: Path, trace_settings, evidence_dir: Path | None = None,
                 mode: str = "authored", release=None, adapter=None, config=None, max_investigations: int = 3,
                 token: str | None = None):
        if mode not in {"authored", "live", "local"}:
            raise ValueError("Unknown web mode")
        if mode != "authored" and (release is None or adapter is None or config is None):
            raise ValueError("Model-driven mode needs explicit release data, configuration and target")
        if type(max_investigations) is not int or not 1 <= max_investigations <= 10:
            raise ValueError("A web process permits one to ten model-driven investigations")
        self.demo_fixtures, self.trace_settings = Path(demo_fixtures), trace_settings
        self.mode, self.release, self.adapter, self.config = mode, release, adapter, config
        self.limit, self.used = max_investigations, 0
        self.token = token or secrets.token_urlsafe(24)
        self.evidence = EvidencePackage(evidence_dir) if evidence_dir is not None else None
        self.runs: dict[str, Run] = {}
        self.order: list[str] = []
        self._busy = threading.Lock()
        self._session = None
        self._session_key: str | None = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="hafi-web-loop", daemon=True)
        self._thread.start()

    # -- lifecycle -------------------------------------------------------------
    def _await(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result()

    def _end_session(self) -> None:
        if self._session is not None:
            self._session.close()
        self._session, self._session_key = None, None

    def close(self) -> None:
        with self._busy:
            self._end_session()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    # -- read-only -------------------------------------------------------------
    def status(self) -> dict:
        llm = getattr(self.config, "llm", None)
        model = getattr(llm, "model_identifier", None) if self.mode != "authored" else None
        profile = getattr(llm, "profile_id", None) if self.mode != "authored" else None
        if self.mode == "live":
            banner = f"Synthetic data · live model {model} · profile {profile} · paid calls"
        elif self.mode == "local":
            banner = f"Synthetic data · local model {model} · profile {profile}"
        else:
            banner = "Synthetic data · authored demonstrations only · no model calls"
        release = self.release
        return {
            "mode": self.mode, "banner": banner, "model_identifier": model, "profile_id": profile,
            "provider": getattr(llm, "provider", None) if self.mode != "authored" else None,
            "fixture_clock": release.reference_time.isoformat() if release is not None else None,
            "windows": [{"start": w.start.isoformat(), "end": w.end.isoformat()} for w in release.target_windows]
                       if release is not None else [],
            "investigations_used": self.used, "investigations_limit": self.limit,
            "live_enabled": self.mode != "authored", "busy": self._busy.locked(),
            "session": {"active": self._session is not None, "session_key": self._session_key},
            "runs": [self.runs[key].summary() for key in self.order],
            "evidence_available": bool(self.evidence and self.evidence.available),
        }

    def run(self, run_id: str) -> dict:
        run = self.runs.get(run_id)
        if run is None:
            raise WebRequestError(HTTPStatus.NOT_FOUND, "No run with that identifier exists in this process.")
        return {"summary": run.summary(), "view": run.view}

    def run_trace(self, run_id: str) -> dict:
        run = self.runs.get(run_id)
        if run is None or run.trace_path is None:
            raise WebRequestError(HTTPStatus.NOT_FOUND, "No trace is available for that run.")
        return self._trace(run.trace_path)

    def evidence_listing(self) -> dict:
        if not (self.evidence and self.evidence.available):
            return {"available": False, "traces": [], "summary": None}
        return {"available": True, "traces": self.evidence.listing(), "summary": self.evidence.summary()}

    def evidence_trace(self, name: str) -> dict:
        path = self.evidence.trace_path(name) if self.evidence else None
        if path is None:
            raise WebRequestError(HTTPStatus.NOT_FOUND, "Only traces listed in the evidence manifest can be opened.")
        return self._trace(path)

    @staticmethod
    def _trace(path: Path) -> dict:
        from hawaii_activity_forecaster.observability import TraceValidationError
        try:
            return trace_view(path)
        except TraceValidationError:
            raise WebRequestError(HTTPStatus.UNPROCESSABLE_ENTITY, "Trace validation failed.") from None

    # -- runs (one at a time) --------------------------------------------------
    def _exclusive(self):
        if not self._busy.acquire(blocking=False):
            raise WebRequestError(HTTPStatus.CONFLICT, "Another investigation is running. Wait for it to finish.")
        return self._busy

    def _store(self, run: Run) -> dict:
        self.runs[run.run_id] = run
        self.order.append(run.run_id)
        return run.summary()

    def demo(self, case: str) -> dict:
        if case not in {"advisory", "outage", "session"}:
            raise WebRequestError(HTTPStatus.NOT_FOUND, "Unknown synthetic demonstration.")
        lock = self._exclusive()
        try:
            from hawaii_activity_forecaster.demo import DemoUnavailable, run_demo, run_session_demo
            from hawaii_activity_forecaster.fixtures import FixtureLoadError
            from hawaii_activity_forecaster.orchestration import SessionError
            try:
                if case == "session":
                    outputs = self._await(run_session_demo(self.demo_fixtures, trace_settings=self.trace_settings)).investigations
                else:
                    outputs = (self._await(run_demo(case, self.demo_fixtures, trace_settings=self.trace_settings)),)
                views = [report_view(o.report, catalog=o.catalog, policy=o.policy) for o in outputs]
            except DemoUnavailable as error:
                raise WebRequestError(HTTPStatus.SERVICE_UNAVAILABLE, str(error)) from None
            except FixtureLoadError:
                raise WebRequestError(HTTPStatus.SERVICE_UNAVAILABLE, FIXTURE_ERROR) from None
            except PresentationError:
                raise WebRequestError(HTTPStatus.INTERNAL_SERVER_ERROR,
                                      "Technical error: no validated result is available for presentation.") from None
            except SessionError:
                raise WebRequestError(HTTPStatus.INTERNAL_SERVER_ERROR, SESSION_ERROR) from None
            except Exception:
                raise WebRequestError(HTTPStatus.INTERNAL_SERVER_ERROR, DEMO_ERROR) from None
            key = "demo-" + secrets.token_hex(4) if case == "session" else None
            labels = {"advisory": "Authored demo · advisory exclusion", "outage": "Authored demo · source outage",
                      "session": "Authored demo · session"}
            stored = []
            for output, view in zip(outputs, views):
                trace = Path(output.report.trace_path) if output.report.trace_path else None
                label = labels[case] + (f" · revision {view['request_revision']}" if case == "session" else "")
                stored.append(self._store(Run(view["investigation_id"], "authored", label,
                                              view["request"]["original"], view, trace, key)))
            return {"runs": stored}
        finally:
            lock.release()

    def reset_session(self) -> dict:
        lock = self._exclusive()
        try:
            self._end_session()
            return {"session": {"active": False}}
        finally:
            lock.release()

    def ask(self, text: str) -> dict:
        if self.mode == "authored":
            raise WebRequestError(HTTPStatus.FORBIDDEN,
                                  "Model-driven runs are disabled. Start hafi web with --live or --local.")
        if not isinstance(text, str) or not text.strip():
            raise WebRequestError(HTTPStatus.BAD_REQUEST, "Enter a request.")
        lock = self._exclusive()
        try:
            # The allowance is checked before any session admission or model call.
            if self.used >= self.limit:
                raise WebRequestError(HTTPStatus.TOO_MANY_REQUESTS,
                                      "This process's investigation allowance is used. Restart hafi web to continue.")
            from hawaii_activity_forecaster.agents.session import AgentSession
            from hawaii_activity_forecaster.model_runtime.provider import ProviderError
            if self._session is None:
                self._session = AgentSession(self.release, self.adapter, trace_settings=self.trace_settings,
                                             max_investigations=self.limit - self.used)
                self._session_key = "session-" + secrets.token_hex(4)
            key = self._session_key
            self.used += 1
            run_id = "run-" + secrets.token_hex(6)
            try:
                report = self._await(self._session.ask(text.strip()))
            except ProviderError as error:
                self._end_session()
                message = f"Model access unavailable: {error}. Configure local access; no automatic retry was attempted."
                return {"run": self._store(Run(run_id, self.mode, "Technical error", text, None, None, key,
                                               {"outcome": "ERROR", "message": message}))}
            except Exception:
                self._end_session()
                return {"run": self._store(Run(run_id, self.mode, "Technical error", text, None, None, key,
                                               {"outcome": "ERROR", "message": TECHNICAL_ERROR}))}
            trace = Path(report.trace_path) if report.trace_path else None
            if report.state.status == "AWAITING_CLARIFICATION":
                self._end_session()
                return {"run": self._store(Run(run_id, self.mode, "Clarification needed", text, None, trace, key, {
                    "outcome": "AWAITING_CLARIFICATION",
                    "questions": list(report.state.clarification_questions),
                    "message": "Submit a complete clarified request; active clarification resumption is deferred."}))}
            if report.result is None:
                self._end_session()
                return {"run": self._store(Run(run_id, self.mode, "Technical error", text, None, trace, key,
                                               {"outcome": "ERROR", "message": TECHNICAL_ERROR}))}
            try:
                view = report_view(report, catalog=self.release.catalog, policy=self.release.policy)
            except PresentationError:
                self._end_session()
                return {"run": self._store(Run(run_id, self.mode, "Technical error", text, None, trace, key,
                                               {"outcome": "ERROR", "message": TECHNICAL_ERROR}))}
            if view["outcome"] == "ERROR":
                self._end_session()
            label = f"Revision {view['request_revision']}"
            return {"run": self._store(Run(view["investigation_id"], self.mode, label, text, view, trace, key))}
        finally:
            lock.release()


def _loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class _Handler(BaseHTTPRequestHandler):
    server_version = "hafi-web"
    sys_version = ""
    app: WebApp
    allowed_hosts: frozenset[str]

    def log_message(self, format, *args):  # Request lines can carry user text; keep them out of logs.
        return

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in _HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json(status, {"error": message})

    def _host_ok(self) -> bool:
        # Rejects DNS-rebinding requests that reach the loopback port under another name.
        return self.headers.get("Host", "") in self.allowed_hosts

    def do_GET(self):
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "Unexpected host.")
        path = urlsplit(self.path).path
        if path in _STATIC:
            name, content_type = _STATIC[path]
            body = resources.files("hawaii_activity_forecaster.web").joinpath("static", name).read_bytes()
            return self._send(HTTPStatus.OK, body, content_type)
        try:
            parts = [unquote(p) for p in path.strip("/").split("/")]
            app = self.app
            if parts == ["api", "status"]:
                return self._json(HTTPStatus.OK, app.status())
            if len(parts) == 3 and parts[:2] == ["api", "runs"]:
                return self._json(HTTPStatus.OK, app.run(parts[2]))
            if len(parts) == 3 and parts[:2] == ["api", "traces"]:
                return self._json(HTTPStatus.OK, app.run_trace(parts[2]))
            if parts == ["api", "evidence"]:
                return self._json(HTTPStatus.OK, app.evidence_listing())
            if len(parts) == 4 and parts[:3] == ["api", "evidence", "traces"]:
                return self._json(HTTPStatus.OK, app.evidence_trace(parts[3]))
        except WebRequestError as error:
            return self._error(error.status, error.message)
        except Exception:
            return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "Technical error.")
        return self._error(HTTPStatus.NOT_FOUND, "Not found.")

    def do_POST(self):
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "Unexpected host.")
        supplied = self.headers.get(_TOKEN_HEADER, "")
        if not hmac.compare_digest(supplied.encode(), self.app.token.encode()):
            return self._error(HTTPStatus.FORBIDDEN, "Missing or invalid request token. Open the URL printed by hafi web.")
        if not (self.headers.get("Content-Type", "").split(";")[0].strip() == "application/json"):
            return self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Send JSON.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 <= length <= _MAX_BODY:
            return self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request too large.")
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._error(HTTPStatus.BAD_REQUEST, "Malformed JSON.")
        parts = urlsplit(self.path).path.strip("/").split("/")
        try:
            if len(parts) == 3 and parts[:2] == ["api", "demo"]:
                return self._json(HTTPStatus.OK, self.app.demo(parts[2]))
            if parts == ["api", "ask"]:
                return self._json(HTTPStatus.OK, self.app.ask(body.get("text")))
            if parts == ["api", "session", "reset"]:
                return self._json(HTTPStatus.OK, self.app.reset_session())
        except WebRequestError as error:
            return self._error(error.status, error.message)
        except Exception:
            return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "Technical error.")
        return self._error(HTTPStatus.NOT_FOUND, "Not found.")


def create_server(app: WebApp, *, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Bind the loopback interface only; any other address is refused."""
    if not _loopback(host):
        raise ValueError("hafi web binds the loopback interface only")
    handler = type("Handler", (_Handler,), {"app": app, "allowed_hosts": frozenset()})
    server = ThreadingHTTPServer((host, port), handler)
    bound = server.server_address[1]
    handler.allowed_hosts = frozenset({f"{host}:{bound}", f"localhost:{bound}"})
    server.daemon_threads = True
    return server
