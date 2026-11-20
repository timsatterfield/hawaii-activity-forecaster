"""OpenAI Responses adapter exercised only through explicit offline HTTP transport.

There is intentionally no live client factory in M1.6-E. Mock transport acceptance
does not establish account access, actual model quality, cost or real activation.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
import json

import httpx
from langchain_openai import ChatOpenAI
from langsmith import tracing_context
import openai

from hawaii_activity_forecaster.config import LLMSettings, ExecutionTimeouts
from .contracts import ProposalError
from .prompts import INPUT_LIMIT, MODEL, OUTPUT_LIMIT, PROFILE, PreparedCall


class ProviderError(RuntimeError):
    """A static code, never an SDK exception with a private request body."""


@dataclass(frozen=True)
class ProviderReply:
    content: str = field(repr=False)
    returned_model: str
    provider_request_digest: str | None
    input_tokens: int | None
    output_tokens: int | None


class OpenAITransportAdapter:
    """An explicit test transport; environment credentials cannot enable networking."""

    def __init__(self, settings: LLMSettings, *, transport: httpx.MockTransport):
        settings = LLMSettings.model_validate(settings.model_dump())
        if (settings.enabled or settings.provider != "openai" or settings.model_identifier != MODEL
                or settings.profile_id != PROFILE):
            raise ProviderError("MODEL_PROFILE_REQUIRED")
        if type(transport) is not httpx.MockTransport:
            raise ProviderError("OFFLINE_TRANSPORT_REQUIRED")
        self._transport = transport

    async def complete(self, call: PreparedCall, on_dispatch: Callable[[], None]) -> ProviderReply:
        sent = False
        boundary_error = None
        async def guarded(request):
            nonlocal sent, boundary_error
            try:
                if sent:
                    raise ProviderError("MODEL_DUPLICATE_HTTP_REQUEST")
                if (request.method != "POST" or str(request.url) != "https://model.invalid/v1/responses"
                        or len(request.content) + 512 > INPUT_LIMIT):
                    raise ProviderError("MODEL_HTTP_INPUT_INVALID")
                payload = json.loads(request.content)
                if (payload.get("model") != MODEL or payload.get("store") is not False
                        or payload.get("max_output_tokens") != OUTPUT_LIMIT
                        or payload.get("stream") is not False
                        or payload.get("tools") or payload.get("previous_response_id")
                        or payload.get("background") or payload.get("temperature") is not None):
                    raise ProviderError("MODEL_HTTP_PROFILE_INVALID")
                on_dispatch()  # Durable authorization and budget before mock HTTP handler.
                sent = True
            except BaseException as error:
                boundary_error = error
                raise
            return await self._transport.handle_async_request(request)

        def reject_sync(_):
            raise ProviderError("MODEL_SYNC_REQUEST_FORBIDDEN")

        try:
            with tracing_context(enabled=False):
                with httpx.Client(transport=httpx.MockTransport(reject_sync), trust_env=False) as sync:
                    async with httpx.AsyncClient(transport=httpx.MockTransport(guarded), trust_env=False) as client:
                        model = ChatOpenAI(model=MODEL, api_key="offline-not-a-credential",
                            base_url="https://model.invalid/v1", organization="", openai_proxy="",
                            http_client=sync, http_async_client=client, max_retries=0,
                            timeout=ExecutionTimeouts().llm_request_seconds,
                            use_responses_api=True, use_previous_response_id=False,
                            reasoning={"effort": "low"}, temperature=None, store=False,
                            max_tokens=OUTPUT_LIMIT, streaming=False, stream_usage=False,
                            include_response_headers=True, cache=False)
                        message = await model.ainvoke([
                            ("system", call.system), ("human", call.payload)],
                            config={"callbacks": []},
                            text={"format": {"type": "json_schema", "name": call.operation,
                                "strict": True, "schema": json.loads(call.schema_json)}})
            metadata = message.response_metadata
            if any(isinstance(b, dict) and b.get("type") == "refusal" for b in message.content):
                raise ProviderError("MODEL_REFUSAL")
            if metadata.get("status") != "completed":
                raise ProviderError("MODEL_INCOMPLETE")
            if metadata.get("model_name") != MODEL:
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
            return ProviderReply(content, MODEL, digest, *counts)
        except Exception as error:
            # SDK connection wrapping must not disguise a rejected local identity,
            # trace write or input guard as an external provider outage.
            if boundary_error is not None:
                raise boundary_error from None
            if isinstance(error, (ProviderError, ProposalError)):
                raise
            if isinstance(error, openai.APITimeoutError):
                code = "MODEL_TIMEOUT"
            elif isinstance(error, openai.APIStatusError):
                code = "MODEL_RATE_LIMIT" if error.status_code == 429 else "MODEL_HTTP_ERROR"
            elif isinstance(error, openai.APIConnectionError):
                code = "MODEL_CONNECTION_ERROR"
            else:
                code = "MODEL_PROVIDER_ERROR"
            raise ProviderError(code) from None
