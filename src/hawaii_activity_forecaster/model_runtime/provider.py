"""Explicit OpenAI and local Ollama adapters using the installed LangChain client.

Live execution requires the reviewed synthetic-release configuration and local
credentials. Mock transport acceptance does not establish live model quality.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os

import httpx
from langchain_openai import ChatOpenAI
from langsmith import tracing_context
import openai
from pydantic import SecretStr

from hawaii_activity_forecaster.config import LLMSettings, ExecutionTimeouts
from .contracts import ProposalError
from .prompts import INPUT_LIMIT, OUTPUT_LIMIT, PreparedCall
from .targets import TARGETS


class ProviderError(RuntimeError):
    """A static code, never an SDK exception with a private request body."""


@dataclass(frozen=True)
class ProviderReply:
    content: str = field(repr=False)
    returned_model: str
    provider_request_digest: str | None
    input_tokens: int | None
    output_tokens: int | None


class _ChatTransportAdapter:
    """Shared SDK, dispatch, deadline and response checks for the two targets.

    Presence of a key never selects/activates a provider. Configuration and the
    calling CLI/API must explicitly opt into the reviewed profile first.
    """

    def __init__(self, settings: LLMSettings, *, transport: httpx.MockTransport | None = None):
        settings = LLMSettings.model_validate(settings.model_dump())
        target = TARGETS.get(settings.profile_id)
        if target is None or target.provider != self.provider_name:
            raise ProviderError("MODEL_PROFILE_REQUIRED")
        if transport is None:
            if not settings.enabled or settings.activation != "synthetic-release":
                raise ProviderError("MODEL_ACTIVATION_REQUIRED")
            if self.provider_name == "openai":
                key = os.environ.get("OPENAI_API_KEY", "")
                if not key.strip():
                    raise ProviderError("MODEL_CREDENTIAL_REQUIRED")
                self._key = SecretStr(key)
            else:
                self._key = SecretStr("ollama-local-not-a-credential")
            self.execution_mode = target.execution_mode
            self._base_url = self.live_base_url
        elif type(transport) is not httpx.MockTransport or settings.enabled:
            raise ProviderError("OFFLINE_TRANSPORT_REQUIRED")
        else:
            self._key = SecretStr("offline-not-a-credential")
            self.execution_mode = "OFFLINE_TRANSPORT"
            self._base_url = "https://model.invalid/v1"
        self._transport = transport
        self.profile_id = settings.profile_id
        self.model_identifier = target.model_identifier
        self.reserved_cost_microusd = target.reserved_cost_microusd

    @property
    def _responses(self):
        return self.provider_name == "openai"

    def _validate_payload(self, payload, call):
        if (payload.get("model") != self.model_identifier or payload.get("store") is not False
                or payload.get("stream") is not False or payload.get("n") not in {None, 1}
                or payload.get("tools") or payload.get("previous_response_id") or payload.get("background")):
            raise ProviderError("MODEL_HTTP_PROFILE_INVALID")
        if self._responses:
            valid = (payload.get("max_output_tokens") == OUTPUT_LIMIT
                     and payload.get("service_tier") == "default" and payload.get("temperature") is None)
        else:
            valid = (payload.get("max_tokens") == OUTPUT_LIMIT and payload.get("temperature") == 0
                     and payload.get("reasoning_effort") == "low"
                     and payload.get("response_format") == self._format(call))
        if not valid:
            raise ProviderError("MODEL_HTTP_PROFILE_INVALID")

    @staticmethod
    def _format(call):
        return dict(type="json_schema", json_schema=dict(
            name=call.operation, strict=True, schema=json.loads(call.schema_json)))

    async def complete(self, call: PreparedCall, on_dispatch: Callable[[], None]) -> ProviderReply:
        sent = False
        boundary_error = None
        backend = self._transport or httpx.AsyncHTTPTransport(retries=0, trust_env=False)
        async def guarded(request):
            nonlocal sent, boundary_error
            try:
                if sent:
                    raise ProviderError("MODEL_DUPLICATE_HTTP_REQUEST")
                endpoint = "/responses" if self._responses else "/chat/completions"
                if (request.method != "POST" or str(request.url) != self._base_url + endpoint
                        or len(request.content) + 512 > INPUT_LIMIT):
                    raise ProviderError("MODEL_HTTP_INPUT_INVALID")
                payload = json.loads(request.content)
                self._validate_payload(payload, call)
                on_dispatch()  # Durable authorization and budget before HTTP dispatch.
                sent = True
            except BaseException as error:
                boundary_error = error
                raise
            return await backend.handle_async_request(request)

        def reject_sync(_):
            raise ProviderError("MODEL_SYNC_REQUEST_FORBIDDEN")

        try:
            with tracing_context(enabled=False):
                with httpx.Client(transport=httpx.MockTransport(reject_sync), trust_env=False) as sync:
                    async with httpx.AsyncClient(transport=httpx.MockTransport(guarded), trust_env=False) as client:
                        options = (dict(reasoning={"effort": "low"}, service_tier="default") if self._responses
                                   else dict(reasoning_effort="low", presence_penalty=0, frequency_penalty=0,
                                             extra_body={"max_tokens": OUTPUT_LIMIT}))
                        model = ChatOpenAI(model=self.model_identifier, api_key=self._key.get_secret_value(),
                            base_url=self._base_url, organization="", openai_proxy="",
                            http_client=sync, http_async_client=client, max_retries=0,
                            timeout=ExecutionTimeouts().llm_request_seconds,
                            use_responses_api=self._responses, use_previous_response_id=False,
                            temperature=None if self._responses else 0, store=False,
                            max_tokens=OUTPUT_LIMIT if self._responses else None, streaming=False, stream_usage=False,
                            include_response_headers=True, cache=False, **options)
                        output_format = (dict(text={"format": {"type": "json_schema", "name": call.operation,
                            "strict": True, "schema": json.loads(call.schema_json)}}) if self._responses
                            else dict(response_format=self._format(call)))
                        message = await model.ainvoke([
                            ("system", call.system), ("human", call.payload)],
                            config={"callbacks": []}, **output_format)
            metadata = message.response_metadata
            if (message.additional_kwargs.get("refusal") or
                    any(isinstance(b, dict) and b.get("type") == "refusal" for b in message.content)):
                raise ProviderError("MODEL_REFUSAL")
            if (metadata.get("status") != "completed" if self._responses else metadata.get("finish_reason") != "stop"):
                raise ProviderError("MODEL_INCOMPLETE")
            if metadata.get("model_name") != self.model_identifier:
                raise ProviderError("MODEL_IDENTIFIER_MISMATCH")
            blocks = message.content
            if isinstance(blocks, str):
                content = blocks
            else:
                text = [b["text"] for b in blocks if isinstance(b, dict) and b.get("type") in {"text", "output_text"}]
                if len(text) != 1 or any(b.get("type") not in {"text", "output_text", "reasoning"} for b in blocks):
                    raise ProviderError("MODEL_OUTPUT_INVALID")
                content = text[0]
            if not isinstance(content, str) or len(content.encode()) > 64000:
                raise ProviderError("MODEL_OUTPUT_INVALID")
            usage = message.usage_metadata
            counts = (usage.get("input_tokens"), usage.get("output_tokens")) if usage else (None, None)
            if any(n is not None and (type(n) is not int or n < 0 or n > cap)
                   for n, cap in zip(counts, (INPUT_LIMIT, OUTPUT_LIMIT))):
                raise ProviderError("MODEL_USAGE_INVALID")
            if None in counts:
                counts = None, None
            request_id = metadata.get("headers", {}).get("x-request-id")
            digest = sha256(request_id.encode()).hexdigest() if isinstance(request_id, str) else None
            return ProviderReply(content, self.model_identifier, digest, *counts)
        except Exception as error:
            # SDK connection wrapping must not disguise a rejected local identity,
            # trace write or input guard as an external provider outage.
            if boundary_error is not None:
                raise boundary_error from None
            if isinstance(error, (ProviderError, ProposalError)):
                raise
            if isinstance(error, openai.APITimeoutError):
                code = "MODEL_TIMEOUT"
            elif isinstance(error, openai.LengthFinishReasonError):
                code = "MODEL_INCOMPLETE"
            elif isinstance(error, openai.ContentFilterFinishReasonError):
                code = "MODEL_REFUSAL"
            elif isinstance(error, openai.APIStatusError):
                code = "MODEL_RATE_LIMIT" if error.status_code == 429 else "MODEL_HTTP_ERROR"
            elif isinstance(error, openai.APIConnectionError):
                code = "MODEL_CONNECTION_ERROR"
            else:
                code = "MODEL_PROVIDER_ERROR"
            raise ProviderError(code) from None
        finally:
            if self._transport is None:
                await backend.aclose()


class OpenAITransportAdapter(_ChatTransportAdapter):
    """Reviewed OpenAI Responses target; API access requires explicit activation."""

    provider_name = "openai"
    live_base_url = "https://api.openai.com/v1"


class OllamaTransportAdapter(_ChatTransportAdapter):
    """Installed Qwen on the fixed loopback endpoint; no credentials or downloads."""

    provider_name = "ollama"
    live_base_url = "http://127.0.0.1:11434/v1"


ModelAdapter = OpenAITransportAdapter | OllamaTransportAdapter


def create_adapter(settings: LLMSettings) -> ModelAdapter:
    if settings.provider == "openai":
        return OpenAITransportAdapter(settings)
    if settings.provider == "ollama":
        return OllamaTransportAdapter(settings)
    raise ProviderError("MODEL_PROFILE_REQUIRED")
