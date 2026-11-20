"""MR-T01–05/13/14/16: actual SDK HTTP path, entirely in-process and offline."""

import asyncio
import json

import httpx
import pytest

from hawaii_activity_forecaster.config import AppConfig, ConfigurationError, LLMSettings, load_config
from hawaii_activity_forecaster.model_runtime.contracts import ProposalError
from hawaii_activity_forecaster.model_runtime.prompts import MODEL, OUTPUT_LIMIT, PROFILE
from hawaii_activity_forecaster.model_runtime.provider import OpenAITransportAdapter, ProviderError
from hawaii_activity_forecaster.observability import inspect_trace
from hawaii_activity_forecaster.orchestration.budgets import BudgetError
from model_runtime_samples import Probe, normalization, coordinator, specialist, response


def test_profile_configuration_is_explicit_default_disabled_and_has_no_credential_field(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'private-provider-key')
    assert AppConfig().llm.model_dump() == dict(enabled=False, provider=None, model_identifier=None, profile_id=None, activation="disabled")
    settings = load_config(environ=dict(HAF_LLM_PROVIDER='openai', HAF_LLM_MODEL_IDENTIFIER=MODEL,
                                       HAF_LLM_PROFILE_ID=PROFILE)).llm
    assert not settings.enabled and 'private-provider-key' not in repr(settings)
    with pytest.raises(ConfigurationError):
        load_config(environ=dict(HAF_LLM_ENABLED='true', HAF_LLM_PROVIDER='openai',
                                HAF_LLM_MODEL_IDENTIFIER=MODEL, HAF_LLM_PROFILE_ID=PROFILE))
    for extra in ({'api_key':'private'}, {'automatic_retries':1}, {'profile_id':PROFILE}):
        with pytest.raises(ValueError): LLMSettings(**extra)
    with pytest.raises(ProviderError, match='MODEL_PROFILE_REQUIRED'):
        OpenAITransportAdapter(LLMSettings(), transport=httpx.MockTransport(lambda _: None))
    with pytest.raises(ProviderError, match='OFFLINE_TRANSPORT_REQUIRED'):
        OpenAITransportAdapter(settings, transport=httpx.AsyncHTTPTransport())


def test_locked_sdk_payload_suppresses_storage_hosted_tools_remote_tracing_and_env_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'private-real-key')
    monkeypatch.setenv('OPENAI_API_BASE', 'https://untrusted.invalid/v1')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://untrusted.invalid/v1')
    monkeypatch.setenv('LANGSMITH_TRACING', 'true')
    monkeypatch.setenv('LANGCHAIN_TRACING_V2', 'true')
    monkeypatch.setenv('LANGSMITH_API_KEY', 'private-remote-key')
    monkeypatch.setenv('LANGSMITH_ENDPOINT', 'https://untrusted.invalid')
    def forbidden(*args, **kwargs):
        pytest.fail('real HTTP transport or remote tracing was reached')
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', forbidden)
    import requests
    monkeypatch.setattr(requests.Session, 'request', forbidden)
    _, _, wire = normalization()
    async def handler(request):
        body = json.loads(request.content)
        assert str(request.url) == 'https://model.invalid/v1/responses'
        assert request.headers['authorization'] == 'Bearer offline-not-a-credential'
        assert body['model'] == MODEL and body['store'] is False and body['stream'] is False
        assert body['max_output_tokens'] == OUTPUT_LIMIT and body['reasoning'] == {'effort':'low'}
        assert body['service_tier'] == 'default'
        assert body['text']['format']['strict'] is True
        assert body['text']['format']['type'] == 'json_schema'
        assert not set(body) & {'tools','previous_response_id','background','temperature','conversation'}
        assert [m['role'] for m in body['input']] == ['system','user']
        return response(wire)
    probe = Probe(tmp_path, handler)
    result = asyncio.run(probe.gateway.invoke('normalize_request', probe.inputs))
    assert result.to_interpretation().changed_values['activity'] == 'SNORKELING'
    path = probe.finish()
    assert inspect_trace(path, budgets=probe.budget.snapshot()).metrics.model_calls == 1
    text = path.read_text()
    for private in ('private-real-key','private-remote-key','private-provider-request', 'near Kihei', 'value_json'):
        assert private not in text
    assert 'OFFLINE_TRANSPORT' in text and 'model_dispatch' in text


@pytest.mark.parametrize('operation,role', [('coordinator_plan',None),('weather_investigation','WEATHER'),('ocean_investigation','OCEAN')])
def test_other_operation_wire_formats_use_the_same_gateway(tmp_path, operation, role):
    inputs, wire = coordinator() if role is None else specialist(role)
    async def handler(_): return response(wire)
    probe = Probe(tmp_path, handler)
    probe.emit('REQUEST_NORMALIZED')
    result = asyncio.run(probe.gateway.invoke(operation, inputs))
    assert result.reason_code in {'INVESTIGATE_GAPS','PLANNED_WORK'}
    assert len(probe.requests) == probe.budget.snapshot().model_calls == 1
    inspect_trace(probe.finish(), budgets=probe.budget.snapshot())


@pytest.mark.parametrize('failure,code', [
    ('429','MODEL_RATE_LIMIT'), ('500','MODEL_HTTP_ERROR'), ('connection','MODEL_CONNECTION_ERROR'),
    ('timeout','MODEL_TIMEOUT'), ('refusal','MODEL_REFUSAL'), ('incomplete','MODEL_INCOMPLETE'),
    ('model','MODEL_IDENTIFIER_MISMATCH'), ('malformed','MODEL_JSON_INVALID'), ('usage','MODEL_USAGE_INVALID'),
    ('private_exception','MODEL_PROVIDER_ERROR'),
])
def test_failed_dispatches_charge_exactly_once_with_no_retry_or_repair(tmp_path, failure, code):
    _, _, wire = normalization()
    async def handler(request):
        if failure in {'429','500'}:
            return httpx.Response(int(failure), json={'error':{'message':'private-provider-body'}},
                                  headers={'retry-after':'0'})
        if failure == 'connection': raise httpx.ConnectError('private-provider-body', request=request)
        if failure == 'timeout': raise httpx.ReadTimeout('private-provider-body', request=request)
        if failure == 'private_exception': raise RuntimeError('private-provider-body')
        result = response(wire, refusal=failure=='refusal', status='incomplete' if failure=='incomplete' else 'completed',
                          model='unexpected-private-model' if failure=='model' else MODEL)
        if failure == 'malformed': return response('private-malformed-output')
        if failure == 'usage':
            payload=json.loads(result.content)
            payload['usage']['input_tokens']=8001
            return httpx.Response(200, json=payload)
        return result
    probe = Probe(tmp_path, handler)
    with pytest.raises((ProviderError,ProposalError)):
        asyncio.run(probe.gateway.invoke('normalize_request', probe.inputs))
    assert len(probe.requests) == probe.budget.snapshot().model_calls == 1
    assert probe.budget.snapshot().closed
    with pytest.raises(ProviderError): asyncio.run(probe.gateway.invoke('normalize_request', probe.inputs))
    path = probe.finish()
    inspect_trace(path, budgets=probe.budget.snapshot())
    assert code in path.read_text()
    assert 'private-provider-body' not in path.read_text() and 'private-malformed-output' not in path.read_text()


def test_parallel_calls_cannot_oversubscribe_and_environmental_budget_is_independent(tmp_path):
    _, _, wire = normalization()
    async def handler(_):
        await asyncio.sleep(0)
        return response(wire)
    probe=Probe(tmp_path, handler)
    probe.budget.reserve('independent-tool','tool')
    probe.budget.dispatch('independent-tool')
    probe.budget.finish('independent-tool')
    async def run():
        return await asyncio.gather(*(probe.gateway.invoke('normalize_request',probe.inputs) for _ in range(13)), return_exceptions=True)
    results=asyncio.run(run())
    assert sum(isinstance(r,BudgetError) for r in results) == 1
    assert sum(isinstance(r,Exception) for r in results) == 1
    assert len(probe.requests) == probe.budget.snapshot().model_calls == 12
    assert probe.budget.snapshot().tool_calls == 1 and probe.budget.snapshot().reserved_model_calls == 0
    # This probe has no environmental event producer, so do not claim its partial
    # model-only trace independently reconstructs the unrelated tool call.
    probe.writer.close()


@pytest.mark.parametrize('failure_at,charged,requests', [('AUTHORIZED',0,0),('DISPATCHED',1,0),('RETURNED',1,1)])
def test_required_trace_failure_closes_execution_without_refunding_entered_dispatch(tmp_path, failure_at, charged, requests):
    _, _, wire=normalization()
    async def handler(_): return response(wire)
    probe=Probe(tmp_path, handler, fail_at=failure_at)
    with pytest.raises(Exception): asyncio.run(probe.gateway.invoke('normalize_request',probe.inputs))
    assert probe.budget.snapshot().model_calls == charged and len(probe.requests) == requests
    assert probe.budget.snapshot().closed and not probe.budget.snapshot().reserved_model_calls
    with pytest.raises(ProviderError): asyncio.run(probe.gateway.invoke('normalize_request',probe.inputs))
    assert len(probe.requests) == requests
    probe.writer.close()


def test_gateway_deadline_uses_approved_thirty_seconds_and_charges_timeout(tmp_path, monkeypatch):
    import hawaii_activity_forecaster.model_runtime.gateway as module
    original = asyncio.wait_for
    timeouts=[]
    async def shorten(awaitable,*,timeout):
        timeouts.append(timeout)
        return await original(awaitable, timeout=.02)
    monkeypatch.setattr(module.asyncio,'wait_for',shorten)
    async def handler(_): await asyncio.Event().wait()
    probe=Probe(tmp_path,handler)
    with pytest.raises(ProviderError): asyncio.run(probe.gateway.invoke('normalize_request',probe.inputs))
    assert timeouts==[30] and len(probe.requests)==probe.budget.snapshot().model_calls==1
    assert 'MODEL_TIMEOUT' in probe.finish().read_text()


def test_stale_revision_and_late_response_never_return_a_proposal(tmp_path):
    current=[True]
    _, _, wire=normalization()
    async def handler(_):
        current[0]=False
        return response(wire)
    probe=Probe(tmp_path, handler, current=lambda _:current[0])
    with pytest.raises(ProviderError,match='MODEL_INVESTIGATION_INACTIVE'):
        asyncio.run(probe.gateway.invoke('normalize_request',probe.inputs))
    assert probe.budget.snapshot().model_calls==1
    inspect_trace(probe.finish(), budgets=probe.budget.snapshot())


def test_missing_usage_is_explicit_and_failed_input_never_calls_http(tmp_path):
    _, _, wire=normalization()
    async def handler(_): return response(wire,usage=False)
    probe=Probe(tmp_path,handler)
    with pytest.raises(ProposalError): asyncio.run(probe.gateway.invoke('normalize_request',object()))
    assert not probe.requests and probe.budget.snapshot().model_calls==0
    asyncio.run(probe.gateway.invoke('normalize_request',probe.inputs))
    done=next(e.details for e in probe.events if e.details.get('phase')=='RETURNED')
    assert done['usage_known'] is False and done['input_token_count'] is done['output_token_count'] is None
    assert done['reserved_cost_microusd']==2500
    inspect_trace(probe.finish(), budgets=probe.budget.snapshot())


def test_normalization_coordinator_and_both_roles_share_one_twelve_call_ledger(tmp_path):
    _, _, normalize_wire = normalization()
    coord, coord_wire = coordinator()
    weather, weather_wire = specialist('WEATHER')
    ocean, ocean_wire = specialist('OCEAN')
    async def handler(request):
        name = json.loads(request.content)['text']['format']['name']
        return response({'normalize_request':normalize_wire,'coordinator_plan':coord_wire,
                         'weather_investigation':weather_wire,'ocean_investigation':ocean_wire}[name])
    probe=Probe(tmp_path,handler)
    async def run():
        await probe.gateway.invoke('normalize_request',probe.inputs)
        probe.emit('REQUEST_NORMALIZED')
        for _ in range(9): await probe.gateway.invoke('coordinator_plan',coord)
        await asyncio.gather(probe.gateway.invoke('weather_investigation',weather),
                             probe.gateway.invoke('ocean_investigation',ocean))
        with pytest.raises(BudgetError): await probe.gateway.invoke('coordinator_plan',coord)
    asyncio.run(run())
    assert len(probe.requests)==probe.budget.snapshot().model_calls==12
    assert inspect_trace(probe.finish(),budgets=probe.budget.snapshot()).metrics.model_calls==12


def test_revision_changed_after_authorization_cancels_reservation_without_http(tmp_path):
    checks=[]
    def current(_):
        checks.append(True)
        return len(checks)==1
    async def handler(_): pytest.fail('stale admission must never reach HTTP')
    probe=Probe(tmp_path,handler,current=current)
    with pytest.raises(ProviderError,match='MODEL_INVESTIGATION_INACTIVE'):
        asyncio.run(probe.gateway.invoke('normalize_request',probe.inputs))
    assert probe.budget.snapshot().model_calls==0 and not probe.requests
    assert not probe.budget.snapshot().reserved_model_calls
    inspect_trace(probe.finish(),budgets=probe.budget.snapshot())


def test_elapsed_deadline_rejects_a_late_provider_return_even_if_cancellation_was_ignored(tmp_path,monkeypatch):
    import hawaii_activity_forecaster.model_runtime.gateway as module
    readings=iter([0,31,32])
    monkeypatch.setattr(module,'monotonic',lambda:next(readings))
    _, _, wire=normalization()
    async def handler(_): return response(wire)
    probe=Probe(tmp_path,handler)
    with pytest.raises(ProviderError,match='MODEL_TIMEOUT'):
        asyncio.run(probe.gateway.invoke('normalize_request',probe.inputs))
    assert probe.budget.snapshot().model_calls==1
    inspect_trace(probe.finish(),budgets=probe.budget.snapshot())


def test_cancellation_charges_dispatched_call_and_leaves_no_live_reservation(tmp_path):
    entered=asyncio.Event()
    async def handler(_):
        entered.set()
        await asyncio.Event().wait()
    probe=Probe(tmp_path,handler)
    async def run():
        task=asyncio.create_task(probe.gateway.invoke('normalize_request',probe.inputs))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    asyncio.run(run())
    assert probe.budget.snapshot().model_calls==1 and probe.budget.snapshot().closed
    assert 'MODEL_CANCELLED' in probe.finish().read_text()
