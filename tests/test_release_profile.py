"""Opt-in credential and production-client boundaries, with no network access.

The live transport factory is replaced in-process. These checks do not establish
real account/model access, billed cost, latency or live acceptance.
"""

import asyncio

import httpx
import pytest

from hawaii_activity_forecaster.agents.data import load_release_data
from hawaii_activity_forecaster.agents.session import AgentSession
from hawaii_activity_forecaster.config import AppConfig, LLMSettings, TraceSettings, load_config
from hawaii_activity_forecaster.model_runtime.prompts import MODEL, SATURDAY_PROFILE
from hawaii_activity_forecaster.model_runtime.provider import OpenAITransportAdapter, ProviderError
from hawaii_activity_forecaster.observability import inspect_trace
from release_samples import adapter
from test_agent_release import ROOT


def test_enabled_profile_requires_all_activation_fields_and_explicit_local_access(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    assert not AppConfig().llm.enabled
    settings = load_config('haf.release.example.toml', environ={}).llm
    assert settings.enabled and settings.profile_id == SATURDAY_PROFILE
    with pytest.raises(ProviderError, match='MODEL_CREDENTIAL_REQUIRED'):
        OpenAITransportAdapter(settings)
    for patch in ({'profile_id': 'm1-agent-runtime-0.1'}, {'activation': 'disabled'},
                  {'provider': None}, {'model_identifier': 'another-model'}):
        with pytest.raises(ValueError):
            LLMSettings(**(settings.model_dump() | patch))
    disabled = LLMSettings(provider='openai', model_identifier=MODEL, profile_id=SATURDAY_PROFILE)
    monkeypatch.setenv('OPENAI_API_KEY', 'private-test-key')
    with pytest.raises(ProviderError, match='MODEL_ACTIVATION_REQUIRED'):
        OpenAITransportAdapter(disabled)
    with pytest.raises(ProviderError, match='OFFLINE_TRANSPORT_REQUIRED'):
        OpenAITransportAdapter(settings, transport=httpx.MockTransport(lambda _: None))


def test_production_factory_dispatches_once_to_exact_endpoint_and_keeps_secrets_out_of_trace(tmp_path, monkeypatch):
    calls, factories = [], []
    stand_in = adapter(calls, profile=SATURDAY_PROFILE)
    monkeypatch.setenv('OPENAI_API_KEY', 'private-test-key')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://untrusted.invalid/v1')
    monkeypatch.setenv('OPENAI_API_BASE', 'https://untrusted.invalid/v1')

    async def handler(request):
        assert str(request.url) == 'https://api.openai.com/v1/responses'
        assert request.headers['authorization'] == 'Bearer private-test-key'
        return await stand_in._transport.handle_async_request(request)

    def factory(**kwargs):
        assert kwargs == dict(retries=0, trust_env=False)
        factories.append(kwargs)
        return httpx.MockTransport(handler)

    monkeypatch.setattr(httpx, 'AsyncHTTPTransport', factory)
    settings = load_config('haf.release.example.toml', environ={}).llm
    live_client = OpenAITransportAdapter(settings)
    session = AgentSession(load_release_data(ROOT), live_client, trace_settings=TraceSettings(directory=tmp_path))
    report = asyncio.run(session.ask('Where should I snorkel tomorrow morning?'))
    assert report.result and report.result.outcome == 'RECOMMENDATIONS'
    assert len(factories) == len(calls) == report.budgets.model_calls == 5
    assert inspect_trace(report.trace_path).complete
    trace = report.trace_path.read_text()
    assert 'LIVE_PROVIDER' in trace and SATURDAY_PROFILE in trace
    assert 'private-test-key' not in trace and 'untrusted.invalid' not in trace
    assert 'Where should I' not in trace and 'value_json' not in trace
    session.close()


def test_profile_0_3_changes_only_the_input_bound_and_its_cost_reserve():
    from hawaii_activity_forecaster.model_runtime.prompts import input_limit, template_text, template_version
    from hawaii_activity_forecaster.model_runtime.targets import TARGETS, SATURDAY_PROFILE_V2
    old, new = TARGETS[SATURDAY_PROFILE_V2], TARGETS[SATURDAY_PROFILE]
    assert (old.input_limit, old.reserved_cost_microusd) == (8000, 2500)
    assert (new.input_limit, new.reserved_cost_microusd) == (12000, 2600)
    assert (old.provider, old.model_identifier, old.execution_mode) == (new.provider, new.model_identifier, new.execution_mode)
    # The reserve covers the bound at the conservative cache-write rate: 12,000 x 0.125 + 2,048 x 0.50.
    assert new.reserved_cost_microusd * 1_000_000 >= new.input_limit * 125_000 + 2048 * 500_000
    assert input_limit(SATURDAY_PROFILE) == 12000 and input_limit(SATURDAY_PROFILE_V2) == 8000
    for operation in ('normalize_request', 'coordinator_plan', 'weather_investigation', 'ocean_investigation'):
        assert template_text(operation, SATURDAY_PROFILE) == template_text(operation, SATURDAY_PROFILE_V2)
        assert template_version(operation, SATURDAY_PROFILE) == template_version(operation, SATURDAY_PROFILE_V2)
