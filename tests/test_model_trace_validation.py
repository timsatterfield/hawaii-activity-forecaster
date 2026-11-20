"""MR-T14: independent provider metadata/lifecycle checks on actual JSONL events."""

import asyncio

import pytest

from hawaii_activity_forecaster.observability import inspect_trace, TraceValidationError
from model_runtime_samples import Probe, normalization, response
from trace_samples import records, rewrite


@pytest.mark.parametrize('mutation', ['null_model','profile','synthetic','mode','operation','schema','template',
                                     'missing_dispatch','duplicate_dispatch','request_digest','usage','count','reservation'])
def test_provider_trace_tampering_cannot_pass_independent_validation(tmp_path,mutation):
    _, _, wire=normalization()
    async def handler(_): return response(wire)
    probe=Probe(tmp_path,handler)
    asyncio.run(probe.gateway.invoke('normalize_request',probe.inputs))
    path=probe.finish()
    assert inspect_trace(path).metrics.model_calls==1
    events=records(path)
    model=[e for e in events if e['details'].get('contract')=='model_dispatch']
    last=model[-1]['details']
    if mutation=='null_model': events[0]['details']['trace_metadata']['model_identifier']=None
    elif mutation=='profile': events[0]['details']['configuration']['model_profile']['provider']='other'
    elif mutation=='synthetic': last['synthetic_adapter']=True
    elif mutation=='mode': last['execution_mode']='LIVE'
    elif mutation=='operation': last['operation']='ocean_investigation'
    elif mutation=='schema': last['schema_digest']='0'*64
    elif mutation=='template': last['template_digest']='0'*64
    elif mutation=='missing_dispatch': events.remove(model[1])
    elif mutation=='duplicate_dispatch':
        duplicate=dict(model[1],event_id='duplicate-event')
        events.insert(events.index(model[1])+1,duplicate)
    elif mutation=='request_digest': last['provider_request_digest']='private-identifier'
    elif mutation=='usage': last['input_token_count']=True
    elif mutation=='reservation': last['reserved_cost_microusd']=0
    else: events[-1]['details']['total_model_calls']=0
    rewrite(path,events)
    with pytest.raises(TraceValidationError): inspect_trace(path)


def test_reader_accepts_future_live_metadata_without_activating_or_claiming_a_live_run(tmp_path):
    # A schema-level reader check, deliberately relabeling a test copy. This does
    # not create genuine runtime evidence or change the harness readiness gate.
    _, _, wire=normalization()
    async def handler(_): return response(wire)
    probe=Probe(tmp_path,handler)
    asyncio.run(probe.gateway.invoke('normalize_request',probe.inputs))
    path=probe.finish()
    events=records(path)
    events[0]['details']['configuration']['model_profile']['execution_mode']='LIVE_PROVIDER'
    for event in events:
        if event['details'].get('contract')=='model_dispatch':
            event['details']['execution_mode']='LIVE_PROVIDER'
    rewrite(path,events)
    assert inspect_trace(path).metrics.model_calls==1
    assert len(probe.requests)==1  # Only the explicit mock HTTP handler was called.
