"""M2 WEB-A local web interface: WEB-T01–T12 from the accepted design.

Offline only: authored demonstrations, explicit SDK mock HTTP and the published
evidence package. No credentials, model server or network access are used.
"""

import asyncio
import json
import re
import threading
import urllib.error
import urllib.request
from argparse import Namespace
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from hawaii_activity_forecaster.agents.data import load_release_data
from hawaii_activity_forecaster.cli import main
from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.demo import run_demo, run_session_demo
from hawaii_activity_forecaster.model_runtime.prompts import SATURDAY_PROFILE
from hawaii_activity_forecaster.observability import inspect_trace
from hawaii_activity_forecaster.presentation import PresentationError, render_report, report_view
from hawaii_activity_forecaster.web import WebApp, create_server
from hawaii_activity_forecaster.web.server import TECHNICAL_ERROR
from hawaii_activity_forecaster.web.views import EvidencePackage, trace_view
from release_samples import adapter

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "fixtures/scenario-pack-v1"
RELEASE = ROOT / "fixtures/saturday-release"
EVIDENCE = ROOT / "docs/evaluation-evidence"
STATIC = ROOT / "src/hawaii_activity_forecaster/web/static"


def _config(model="gpt-6-luna", provider="openai"):
    return SimpleNamespace(llm=SimpleNamespace(model_identifier=model, profile_id=SATURDAY_PROFILE, provider=provider))


def _live_app(tmp_path, calls, *, limit=3, failure=None):
    return WebApp(demo_fixtures=DEMO, trace_settings=TraceSettings(directory=tmp_path), evidence_dir=EVIDENCE,
                  mode="live", release=load_release_data(RELEASE), adapter=adapter(calls, failure=failure),
                  config=_config(), max_investigations=limit)


def _authored_app(tmp_path):
    return WebApp(demo_fixtures=DEMO, trace_settings=TraceSettings(directory=tmp_path), evidence_dir=EVIDENCE)


class Client:
    def __init__(self, app):
        self.app = app
        self.server = create_server(app, port=0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def call(self, method, path, body=None, *, token=True, host=None, content_type="application/json"):
        headers = {}
        data = None
        if method == "POST":
            headers["Content-Type"] = content_type
            data = json.dumps(body or {}).encode()
            if token is True:
                headers["X-HAF-Token"] = self.app.token
            elif token:
                headers["X-HAF-Token"] = token
        if host:
            headers["Host"] = host
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                raw, status, got = response.read(), response.status, dict(response.headers)
        except urllib.error.HTTPError as error:
            raw, status, got = error.read(), error.code, dict(error.headers)
        payload = json.loads(raw) if got.get("Content-Type") == "application/json" else raw
        return status, payload, got

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.app.close()


@pytest.fixture
def authored(tmp_path):
    client = Client(_authored_app(tmp_path))
    yield client
    client.close()


def _demo_outputs(case, tmp_path):
    settings = TraceSettings(directory=tmp_path)
    if case == "session":
        return asyncio.run(run_session_demo(DEMO, trace_settings=settings)).investigations
    return (asyncio.run(run_demo(case, DEMO, trace_settings=settings)),)


# WEB-T01 ------------------------------------------------------------------------
def test_web_t01_report_view_rejects_what_render_report_rejects(tmp_path):
    output = _demo_outputs("advisory", tmp_path)[0]
    good = output.report
    assert report_view(good, catalog=output.catalog, policy=output.policy)["outcome"] == "RECOMMENDATIONS"
    tampered = [
        replace(good, trace_writable=False),
        replace(good, result=None),
        replace(good, result_validation=None),
        replace(good, result=good.result.model_copy(update={"outcome": type(good.result.outcome)("NO_RECOMMENDATION")})),
    ]
    for report in tampered:
        with pytest.raises(PresentationError):
            render_report(report, catalog=output.catalog, policy=output.policy)
        with pytest.raises(PresentationError):
            report_view(report, catalog=output.catalog, policy=output.policy)
    for kwargs in ({"catalog": None, "policy": output.policy}, {"catalog": output.catalog, "policy": None}):
        with pytest.raises(PresentationError):
            report_view(good, **kwargs)


# WEB-T02 ------------------------------------------------------------------------
@pytest.mark.parametrize("case", ["advisory", "outage", "session"])
def test_web_t02_view_and_cli_text_name_the_same_beaches(tmp_path, case):
    for output in _demo_outputs(case, tmp_path):
        text = render_report(output.report, catalog=output.catalog, policy=output.policy)
        view = report_view(output.report, catalog=output.catalog, policy=output.policy)
        json.dumps(view)  # JSON-safe throughout
        recommended = re.findall(r"^- (.+)$", text, re.M)
        assert [r["name"] for r in view["recommendations"]] == recommended
        section = text.split("Not recommended (excluded):\n")[1].split("\n") if "Not recommended (excluded):" in text else []
        excluded = []
        for line in section:
            if not line.startswith("  - "):
                break
            excluded.append(line[4:])
        assert [f"{e['name']}: {'; '.join(e['reasons'])}" for e in view["exclusions"]] == excluded
        if view["outcome"] == "NO_RECOMMENDATION":
            assert view["abstention"]["explanation"] in text
            for name in view["abstention"]["affected"]:
                assert f"  - {name}" in text
        assert view["request_revision"] == output.report.state.request_revision
        assert {b["beach_id"] for b in view["beaches"]} == {a.beach_id for a in output.report.state.assessments}


# WEB-T03 ------------------------------------------------------------------------
def test_web_t03_authored_mode_never_constructs_a_provider(tmp_path, monkeypatch):
    import hawaii_activity_forecaster.model_runtime.provider as provider
    monkeypatch.setattr(provider, "create_adapter", lambda *a, **k: pytest.fail("provider constructed"))
    from hawaii_activity_forecaster.web.cli import web_command
    arguments = Namespace(fixtures=DEMO, release_fixtures=None, config=None, live=False, local=False, case="favorable",
                          max_investigations=3, trace_directory=tmp_path, evidence=EVIDENCE, port=0)
    app, server = web_command(arguments, serve=False)
    client = Client.__new__(Client)
    client.app, client.server, client.port = app, server, server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        status, payload, _ = client.call("POST", "/api/ask", {"text": "Where should I snorkel tomorrow morning?"})
        assert status == 403 and "--live or --local" in payload["error"]
        assert app.status()["live_enabled"] is False and app.used == 0
    finally:
        client.close()


def test_web_t03_live_flag_requires_config_and_release_fixtures(capsys):
    with pytest.raises(SystemExit):
        main(["web", "--fixtures", str(DEMO), "--live"])
    assert "--config and --release-fixtures" in capsys.readouterr().err


# WEB-T04 ------------------------------------------------------------------------
def test_web_t04_posts_need_the_startup_token(authored):
    assert authored.call("POST", "/api/demo/advisory", token=None)[0] == 403
    assert authored.call("POST", "/api/demo/advisory", token="wrong")[0] == 403
    assert authored.call("POST", "/api/demo/advisory", content_type="text/plain")[0] == 415
    assert authored.app.runs == {}
    status, payload, _ = authored.call("POST", "/api/demo/advisory")
    assert status == 200 and payload["runs"][0]["outcome"] == "RECOMMENDATIONS"


# WEB-T05 ------------------------------------------------------------------------
@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5", "::", "example.com"])
def test_web_t05_refuses_non_loopback_addresses(tmp_path, host):
    app = _authored_app(tmp_path)
    try:
        with pytest.raises(ValueError):
            create_server(app, host=host, port=0)
    finally:
        app.close()


def test_web_t05_rejects_foreign_host_headers(authored):
    assert authored.call("GET", "/api/status", host=f"attacker.example:{authored.port}")[0] == 403
    assert authored.call("POST", "/api/demo/advisory", host="attacker.example")[0] == 403
    assert authored.call("GET", "/api/status", host=f"localhost:{authored.port}")[0] == 200


# WEB-T06 ------------------------------------------------------------------------
def test_web_t06_one_run_at_a_time_and_allowance_before_model_calls(tmp_path):
    calls = []
    client = Client(_live_app(tmp_path, calls, limit=1))
    try:
        client.app._busy.acquire()
        status, payload, _ = client.call("POST", "/api/ask", {"text": "Where should I snorkel tomorrow morning?"})
        assert status == 409 and calls == []
        client.app._busy.release()
        status, payload, _ = client.call("POST", "/api/ask", {"text": "Where should I snorkel tomorrow morning?"})
        assert status == 200 and payload["run"]["outcome"] == "RECOMMENDATIONS"
        made = len(calls)
        status, payload, _ = client.call("POST", "/api/ask", {"text": "Actually near Napili instead."})
        assert status == 429 and len(calls) == made
        assert client.call("POST", "/api/demo/advisory")[0] == 200  # authored demos make no model calls
        assert len(calls) == made
    finally:
        client.close()


# WEB-T07 ------------------------------------------------------------------------
def test_web_t07_errors_use_cli_wording_without_exception_text(tmp_path, monkeypatch):
    from hawaii_activity_forecaster.agents.session import AgentSession
    from hawaii_activity_forecaster.model_runtime.provider import ProviderError
    client = Client(_live_app(tmp_path, []))
    try:
        async def boom(self, text):
            raise RuntimeError("secret internal detail /Users/someone")
        monkeypatch.setattr(AgentSession, "ask", boom)
        status, payload, _ = client.call("POST", "/api/ask", {"text": "Where should I snorkel tomorrow morning?"})
        assert status == 200 and payload["run"]["message"] == TECHNICAL_ERROR
        assert "secret" not in json.dumps(payload) and "secret" not in json.dumps(client.call("GET", "/api/status")[1])
        assert client.app.status()["session"]["active"] is False

        async def provider_down(self, text):
            raise ProviderError("provider request failed")
        monkeypatch.setattr(AgentSession, "ask", provider_down)
        status, payload, _ = client.call("POST", "/api/ask", {"text": "Where should I snorkel tomorrow morning?"})
        assert payload["run"]["message"] == ("Model access unavailable: provider request failed. "
                                             "Configure local access; no automatic retry was attempted.")
    finally:
        client.close()


def test_web_t07_model_failure_is_a_validated_error_and_ends_the_session(tmp_path):
    calls = []
    client = Client(_live_app(tmp_path, calls, failure="ocean_investigation"))
    try:
        status, payload, _ = client.call("POST", "/api/ask", {"text": "Where should I snorkel tomorrow morning?"})
        assert status == 200 and payload["run"]["outcome"] == "ERROR"
        assert "private provider error" not in json.dumps(payload)
        assert client.app.status()["session"]["active"] is False
    finally:
        client.close()


# WEB-T08 ------------------------------------------------------------------------
@pytest.mark.parametrize("path", [
    "/api/traces/unknown", "/api/traces/..%2F..%2Fpyproject.toml",
    "/api/evidence/traces/..%2Fevidence-manifest.json", "/api/evidence/traces/%2Fetc%2Fpasswd",
    "/api/evidence/traces/representative-traces%2Fsc-001-round0-recommendation.jsonl",
])
def test_web_t08_traces_only_by_run_or_manifest_name(authored, path):
    assert authored.call("GET", path)[0] == 404


def test_web_t08_static_files_are_a_fixed_list(authored):
    assert authored.call("GET", "/../pyproject.toml")[0] == 404
    assert authored.call("GET", "/static/app.js")[0] == 404
    status, body, headers = authored.call("GET", "/")
    assert status == 200 and b'id="mode"' in body
    assert "script-src 'self'" in headers["Content-Security-Policy"] and headers["X-Content-Type-Options"] == "nosniff"


# WEB-T09 ------------------------------------------------------------------------
def test_web_t09_trace_view_matches_hafi_trace_for_published_evidence():
    package = EvidencePackage(EVIDENCE)
    names = [item["name"] for item in package.listing()]
    assert len(names) == 6
    for name in names:
        path = package.trace_path(name)
        view = trace_view(path)
        receipt = inspect_trace(path)
        assert view["metrics"] == asdict(receipt)["metrics"] and view["digest"] == receipt.digest
        assert view["event_count"] == receipt.event_count == len(view["events"])
        assert view["model_identifier"] == "gpt-6-luna" and view["execution_mode"] == "LIVE_PROVIDER"
    failed = trace_view(package.trace_path("sc-012-round3-step2-failed-closed.jsonl"))
    assert failed["metrics"]["tool_calls"] == 0 and failed["final_status"] == "FAILED"
    assert any("MODEL_PLAN_OPTION_NOT_ALLOWED" in e["summary"] for e in failed["events"])


def test_web_t09_authored_traces_are_labelled_without_a_model(authored):
    authored.call("POST", "/api/demo/outage")
    run_id = authored.app.order[-1]
    status, trace, _ = authored.call("GET", f"/api/traces/{run_id}")
    assert status == 200 and trace["model_identifier"] is None and trace["metrics"]["model_calls"] == 0
    assert trace["execution_mode"] == "AUTHORED_COMPONENT"


# WEB-T10 ------------------------------------------------------------------------
def test_web_t10_follow_up_is_a_new_investigation_in_the_same_session(tmp_path):
    calls = []
    client = Client(_live_app(tmp_path, calls))
    try:
        first = client.call("POST", "/api/ask", {"text": "Where should I snorkel tomorrow morning near Kihei?"})[1]["run"]
        second = client.call("POST", "/api/ask", {"text": "Actually near Napili instead."})[1]["run"]
        a = client.call("GET", f"/api/runs/{first['run_id']}")[1]["view"]
        b = client.call("GET", f"/api/runs/{second['run_id']}")[1]["view"]
        assert a["session_id"] == b["session_id"] and a["investigation_id"] != b["investigation_id"]
        assert (a["request_revision"], b["request_revision"]) == (1, 2)
        assert b["request"]["preferred_area"] == "Napili"
        assert first["session_key"] == second["session_key"]
        assert client.call("GET", f"/api/traces/{second['run_id']}")[0] == 200
        assert client.call("POST", "/api/session/reset")[0] == 200
        third = client.call("POST", "/api/ask", {"text": "Where should I swim tomorrow afternoon?"})[1]["run"]
        c = client.call("GET", f"/api/runs/{third['run_id']}")[1]["view"]
        assert c["request_revision"] == 1 and c["session_id"] != a["session_id"]
        assert client.app.used == 3
    finally:
        client.close()


# WEB-T11 ------------------------------------------------------------------------
def test_web_t11_every_page_carries_the_mode_banner_from_status(tmp_path, authored):
    assert authored.call("GET", "/api/status")[1]["banner"] == "Synthetic data · authored demonstrations only · no model calls"
    live = _live_app(tmp_path, [])
    try:
        banner = live.status()["banner"]
        assert "live model gpt-6-luna" in banner and SATURDAY_PROFILE in banner and "paid calls" in banner
    finally:
        live.close()
    page = (STATIC / "index.html").read_text()
    header = page.split("</header>")[0]
    assert 'id="mode"' in header  # one shared header for every route
    script = (STATIC / "app.js").read_text()
    assert "modeChip.textContent = state.status.banner" in script
    assert not re.search(r"\son[a-z]+=", page) and "<script>" not in page  # CSP: no inline handlers or scripts


# WEB-T12 ------------------------------------------------------------------------
def test_web_t12_cli_demo_output_is_unchanged_by_the_shared_helpers(tmp_path, capsys):
    """render_report() still renders every demo; exclusion wording uses the shared helper."""
    assert main(["demo", "advisory", "--fixtures", str(DEMO), "--trace-directory", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Not recommended (excluded):\n  - Fictional Test Beach A (SYNTHETIC): an applicable official water-contact avoidance advisory" in out
    assert "Wind speed: 8 kn" in out
