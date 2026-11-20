"""Ollama target contracts through real SDK requests and in-process transports."""

import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from hawaii_activity_forecaster.agents.data import load_release_data
from hawaii_activity_forecaster.agents.session import AgentSession
from hawaii_activity_forecaster.cli import main
from hawaii_activity_forecaster.config import LLMSettings, TraceSettings, load_config
from hawaii_activity_forecaster.model_runtime.provider import OllamaTransportAdapter, ProviderError, create_adapter
from hawaii_activity_forecaster.model_runtime.targets import OLLAMA_MODEL, OLLAMA_PROFILE, SATURDAY_PROFILE
from hawaii_activity_forecaster.model_runtime.gateway import ModelGateway
from hawaii_activity_forecaster.model_runtime.prompts import prepare
from hawaii_activity_forecaster.observability import TraceValidationError, inspect_trace
from hawaii_activity_forecaster.orchestration.budgets import BudgetError, BudgetManager
from model_runtime_samples import normalization
from release_samples import adapter, chat_response
from test_agent_release import ROOT
from trace_samples import records, rewrite


REQUEST = 'Where should I snorkel tomorrow morning?'


def local_settings():
    return LLMSettings(provider='ollama', model_identifier=OLLAMA_MODEL, profile_id=OLLAMA_PROFILE)


def investigate(tmp_path, client):
    session = AgentSession(load_release_data(ROOT), client, trace_settings=TraceSettings(directory=tmp_path))
    try:
        return asyncio.run(session.ask(REQUEST))
    finally:
        session.close()


def test_local_target_requires_explicit_configuration_but_no_openai_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    settings = load_config('haf.ollama.example.toml', environ={}).llm
    client = create_adapter(settings)
    assert type(client) is OllamaTransportAdapter
    assert client.execution_mode == 'LOCAL_PROVIDER' and client.reserved_cost_microusd == 0
    assert client.model_identifier == OLLAMA_MODEL
    with pytest.raises(ProviderError, match='MODEL_ACTIVATION_REQUIRED'):
        create_adapter(local_settings())
    for patch in ({'provider': 'openai'}, {'model_identifier': 'qwen3.5:cloud'},
                  {'profile_id': 'm1-saturday-runtime-0.1'}):
        with pytest.raises(ValueError):
            LLMSettings(**(settings.model_dump() | patch))


def test_local_sdk_uses_loopback_schema_token_limit_and_no_cloud_credential(tmp_path, monkeypatch):
    calls, requests = [], []
    stand_in = adapter(calls, profile=OLLAMA_PROFILE)
    monkeypatch.setenv('OPENAI_API_KEY', 'private-unused-openai-key')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://untrusted.invalid/v1')
    monkeypatch.setenv('OLLAMA_HOST', 'https://untrusted.invalid')

    async def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        assert str(request.url) == 'http://127.0.0.1:11434/v1/chat/completions'
        assert request.headers['authorization'] == 'Bearer ollama-local-not-a-credential'
        assert body['model'] == OLLAMA_MODEL and body['max_tokens'] == 2048
        assert body['reasoning_effort'] == 'low' and body['temperature'] == 0
        assert body['response_format']['json_schema']['strict'] is True
        assert body['stream'] is False and body['store'] is False
        assert not set(body) & {'tools', 'previous_response_id', 'max_completion_tokens'}
        return await stand_in._transport.handle_async_request(request)

    def factory(**kwargs):
        assert kwargs == dict(retries=0, trust_env=False)
        return httpx.MockTransport(handler)

    monkeypatch.setattr(httpx, 'AsyncHTTPTransport', factory)
    report = investigate(tmp_path, create_adapter(load_config('haf.ollama.example.toml', environ={}).llm))
    assert report.result and report.result.outcome == 'RECOMMENDATIONS'
    assert len(requests) == report.budgets.model_calls == 5
    assert inspect_trace(report.trace_path).complete
    events = records(report.trace_path)
    model_events = [e['details'] for e in events if e['details'].get('contract') == 'model_dispatch']
    assert all(d['provider'] == 'ollama' and d['execution_mode'] == 'LOCAL_PROVIDER'
               and d['reserved_cost_microusd'] == 0 for d in model_events)
    assert 'private-unused-openai-key' not in report.trace_path.read_text()


@pytest.mark.parametrize('fault,code', [
    ('connection', 'MODEL_CONNECTION_ERROR'), ('timeout', 'MODEL_TIMEOUT'),
    ('429', 'MODEL_RATE_LIMIT'), ('500', 'MODEL_HTTP_ERROR'),
    ('length', 'MODEL_INCOMPLETE'), ('model', 'MODEL_IDENTIFIER_MISMATCH'),
    ('malformed', 'MODEL_JSON_INVALID'), ('usage', 'MODEL_USAGE_INVALID'),
])
def test_local_failures_charge_once_without_retry_or_openai_fallback(tmp_path, fault, code):
    requests = []

    async def handler(request):
        requests.append(request)
        if fault == 'connection':
            raise httpx.ConnectError('private-local-detail', request=request)
        if fault == 'timeout':
            raise httpx.ReadTimeout('private-local-detail', request=request)
        if fault in {'429', '500'}:
            return httpx.Response(int(fault), json={'error': {'message': 'private-local-detail'}})
        if fault == 'length':
            return chat_response({}, finish_reason='length')
        if fault == 'model':
            return chat_response({}, model='unapproved-model')
        if fault == 'usage':
            payload = json.loads(chat_response({}).content)
            payload['usage']['prompt_tokens'] = 8001
            return httpx.Response(200, json=payload)
        return chat_response('private-local-detail')

    client = OllamaTransportAdapter(local_settings(), transport=httpx.MockTransport(handler))
    report = investigate(tmp_path, client)
    assert report.state.status == 'FAILED' and report.result is None
    assert len(requests) == report.budgets.model_calls == 1 and report.budgets.tool_calls == 0
    assert inspect_trace(report.trace_path).complete
    text = report.trace_path.read_text()
    assert code in text and 'private-local-detail' not in text
    assert 'openai' not in text


@pytest.mark.parametrize('field,value', [
    ('provider', 'openai'), ('model_identifier', 'gpt-6-luna'),
    ('execution_mode', 'LIVE_PROVIDER'), ('reserved_cost_microusd', 2500),
    ('returned_model_identifier', 'gpt-6-luna'),
])
def test_local_trace_rejects_provider_model_mode_and_cost_substitution(tmp_path, field, value):
    report = investigate(tmp_path, adapter([], profile=OLLAMA_PROFILE))
    events = records(report.trace_path)
    last = [e['details'] for e in events if e['details'].get('contract') == 'model_dispatch'][-1]
    last[field] = value
    rewrite(report.trace_path, events)
    with pytest.raises(TraceValidationError):
        inspect_trace(report.trace_path)


@pytest.mark.parametrize('config,switch', [
    ('haf.ollama.example.toml', '--live'), ('haf.release.example.toml', '--local'),
])
def test_cli_switch_must_match_configured_target_before_client_construction(tmp_path, monkeypatch, capsys, config, switch):
    def forbidden(_):
        pytest.fail('Mismatched opt-in must not construct either client')
    monkeypatch.setattr('hawaii_activity_forecaster.agents.cli.create_adapter', forbidden)
    assert main(['run', REQUEST, '--fixtures', str(ROOT), '--config', config, switch]) == 2
    assert 'must match' in capsys.readouterr().err


def test_cli_runs_local_target_without_env_file_and_reports_local_identity(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    calls = []
    monkeypatch.setattr('hawaii_activity_forecaster.agents.cli.create_adapter',
                        lambda _: adapter(calls, profile=OLLAMA_PROFILE))
    assert main(['run', REQUEST, '--fixtures', str(ROOT), '--config', 'haf.ollama.example.toml',
                 '--local', '--max-investigations', '1', '--trace-directory', str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert 'ollama / qwen3.5:9b' in out and 'SYNTHETIC' in out and 'Local trace:' in out
    assert len(calls) == 5


@pytest.mark.parametrize('profile', [OLLAMA_PROFILE, SATURDAY_PROFILE])
def test_model_token_offsets_are_mechanical_unicode_positions_without_normalized_answers(profile):
    identity, inputs, _ = normalization()
    text = '🤿 Please snorkel tomorrow morning.'
    call = prepare('normalize_request', replace(inputs, original_request=text), identity, profile)
    context = json.loads(call.payload)
    tokens = context['request_tokens']
    assert tokens[0] == dict(text='🤿', start=0, end=1)
    assert all(text[t['start']:t['end']] == t['text'] for t in tokens)
    assert next(t for t in tokens if t['text'] == 'snorkel')['start'] == 9
    assert all(set(t) == {'text', 'start', 'end'} for t in tokens)
    assert 'changes' not in context and context['original_request'] == text


def test_local_inference_keeps_the_shared_twelve_call_limit_and_zero_api_reserve():
    identity, inputs, wire = normalization()
    requests, events = [], []

    async def handler(request):
        requests.append(request)
        await asyncio.sleep(0)
        return chat_response(wire)

    client = OllamaTransportAdapter(local_settings(), transport=httpx.MockTransport(handler))
    budget = BudgetManager()
    gateway = ModelGateway(identity=identity, budget=budget, adapter=client,
        emit=lambda kind, **details: events.append(details), is_current=lambda _: True)

    async def run():
        return await asyncio.gather(*(gateway.invoke('normalize_request', inputs) for _ in range(13)),
                                    return_exceptions=True)

    results = asyncio.run(run())
    assert sum(isinstance(r, Exception) for r in results) == 1
    assert sum(isinstance(r, BudgetError) for r in results) == 1
    assert len(requests) == budget.snapshot().model_calls == 12
    assert budget.snapshot().tool_calls == budget.snapshot().reserved_model_calls == 0
    assert all(e['reserved_cost_microusd'] == 0 for e in events if e.get('contract') == 'model_dispatch')
