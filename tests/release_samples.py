"""Explicit offline model stand-in; sees only actual public request projections."""

import json
import httpx

from hawaii_activity_forecaster.config import LLMSettings
from hawaii_activity_forecaster.model_runtime.prompts import SATURDAY_PROFILE
from hawaii_activity_forecaster.model_runtime.targets import OLLAMA_MODEL, TARGETS
from hawaii_activity_forecaster.model_runtime.provider import OllamaTransportAdapter, OpenAITransportAdapter
from model_runtime_samples import response


def adapter(calls, *, failure=None, profile=SATURDAY_PROFILE):
    target = TARGETS[profile]
    async def handler(request):
        body=json.loads(request.content)
        local = target.provider == 'ollama'
        operation=body['response_format']['json_schema']['name'] if local else body['text']['format']['name']
        content=body['messages'][1]['content'] if local else body['input'][1]['content']
        data=json.loads(content if isinstance(content,str) else content[0]['text'])
        calls.append((operation,data))
        if failure==operation:
            return httpx.Response(429,json={'error':{'message':'private provider error'}})
        if operation=='normalize_request':
            text=data['original_request']
            inherited=data['inherited_request']
            activity=next(((word,value) for word,value in [('snorkel','SNORKELING'),('swim','SWIMMING'),('SUP','SUP')] if word in text),None)
            values={}; spans=[]
            def add(field,value,fragment):
                values[field]=value
                start=text.index(fragment)
                spans.append(dict(field=field,start=start,end=start+len(fragment),
                                  entry_index=0 if field in ('hard_constraints','soft_preferences') else None))
            if activity: add('activity',activity[1],activity[0])
            if 'tomorrow' in text: add('target_date','2026-11-17','tomorrow')
            for part,start,end in [('morning','08:00','11:00'),('afternoon','12:00','16:00')]:
                if part in text:
                    add('target_time_window',dict(start='2026-11-17T'+start+':00-10:00',end='2026-11-17T'+end+':00-10:00'),part)
            for area in ('Kihei','Napili','Wailea'):
                if area in text: add('preferred_area',area,('near '+area) if 'near '+area in text else area)
            if 'only South Maui' in text:
                add('hard_constraints',[dict(kind='LOCATION_RESTRICTION',scope='REGION',value='SOUTH_MAUI')],'only South Maui')
            if 'intermediate' in text: add('experience_level','INTERMEDIATE','intermediate')
            if 'prefer calm water' in text:
                add('soft_preferences',[dict(kind='CALM_WATER')],'prefer calm water')
            result=dict(changes=[dict(field=k,value_json=json.dumps(v)) for k,v in values.items()],source_spans=spans,removed_entries=[],unresolved_spans=[])
        elif operation=='coordinator_plan':
            tasks=data['legal_tasks']
            result=dict(action='DELEGATE' if tasks else 'CONCLUDE',tasks=tasks,
                reason_code='INVESTIGATE_GAPS' if tasks else data['allowed_stop_reasons'][0],evidence_refs=[])
        else:
            options=data['legal_option_ids']; marine=next((i for i,n in enumerate(options) if n.startswith('MARINE_')),None)
            steps=[]
            for name in options:
                condition='RETRY_IF_RETRYABLE_FAILURE' if name.startswith('RETRY_') else 'FALLBACK_IF_REQUIRED_GAP_UNRESOLVED' if name.startswith(('SURF_','CURRENTS_')) else 'ALWAYS'
                steps.append(dict(option_id=name,condition=condition,origin_step=None if condition=='ALWAYS' else marine))
            result=dict(steps=steps,unresolved_gap_ids=[],reason_code='PLANNED_WORK')
        return chat_response(result) if local else response(result)
    implementation = OllamaTransportAdapter if target.provider == 'ollama' else OpenAITransportAdapter
    return implementation(LLMSettings(provider=target.provider,model_identifier=target.model_identifier,profile_id=profile),
                          transport=httpx.MockTransport(handler))


def chat_response(wire, *, finish_reason='stop', model=OLLAMA_MODEL, usage=True):
    value = dict(id='chatcmpl-local-test', object='chat.completion', created=1, model=model,
        choices=[dict(index=0, finish_reason=finish_reason, message=dict(role='assistant',
            content=wire if isinstance(wire, str) else json.dumps(wire)))])
    if usage:
        value['usage'] = dict(prompt_tokens=100, completion_tokens=40, total_tokens=140)
    return httpx.Response(200, json=value)
