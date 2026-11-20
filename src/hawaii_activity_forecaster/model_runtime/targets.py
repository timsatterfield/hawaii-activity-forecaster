"""Closed model targets; no discovery, implicit selection or automatic failover."""

from dataclasses import dataclass
from types import MappingProxyType

PROFILE = "m1-agent-runtime-0.1"
SATURDAY_PROFILE_V1 = "m1-saturday-runtime-0.1"
SATURDAY_PROFILE_V2 = "m1-saturday-runtime-0.2"
# 0.3: identical prompts/schemas to 0.2; larger input bound for revised follow-ups.
SATURDAY_PROFILE = "m1-saturday-runtime-0.3"
OLLAMA_PROFILE_V1 = "m1-ollama-qwen3.5-9b-0.1"
OLLAMA_PROFILE_V2 = "m1-ollama-qwen3.5-9b-0.2"
OLLAMA_PROFILE_V3 = "m1-ollama-qwen3.5-9b-0.3"
OLLAMA_PROFILE_V4 = "m1-ollama-qwen3.5-9b-0.4"
OLLAMA_PROFILE = "m1-ollama-qwen3.5-9b-0.5"
MODEL = "gpt-6-luna"
OLLAMA_MODEL = "qwen3.5:9b"
CALL_RESERVE_MICROUSD = 2500
DEFAULT_INPUT_LIMIT = 8000
SATURDAY_INPUT_LIMIT = 12000
# 12,000 input x $0.125/M (cache-write rate) + 2,048 output x $0.50/M = 2,524 microUSD,
# so the 2,500 reserve no longer covers the bound. Pricing checked 2026-11-19.
SATURDAY_RESERVE_MICROUSD = 2600


@dataclass(frozen=True)
class ModelTarget:
    provider: str
    model_identifier: str
    execution_mode: str
    reserved_cost_microusd: int
    input_limit: int = DEFAULT_INPUT_LIMIT


TARGETS = MappingProxyType({
    PROFILE: ModelTarget("openai", MODEL, "LIVE_PROVIDER", CALL_RESERVE_MICROUSD),
    SATURDAY_PROFILE_V1: ModelTarget("openai", MODEL, "LIVE_PROVIDER", CALL_RESERVE_MICROUSD),
    SATURDAY_PROFILE_V2: ModelTarget("openai", MODEL, "LIVE_PROVIDER", CALL_RESERVE_MICROUSD),
    SATURDAY_PROFILE: ModelTarget("openai", MODEL, "LIVE_PROVIDER", SATURDAY_RESERVE_MICROUSD, SATURDAY_INPUT_LIMIT),
    OLLAMA_PROFILE_V1: ModelTarget("ollama", OLLAMA_MODEL, "LOCAL_PROVIDER", 0),
    OLLAMA_PROFILE_V2: ModelTarget("ollama", OLLAMA_MODEL, "LOCAL_PROVIDER", 0),
    OLLAMA_PROFILE_V3: ModelTarget("ollama", OLLAMA_MODEL, "LOCAL_PROVIDER", 0),
    OLLAMA_PROFILE_V4: ModelTarget("ollama", OLLAMA_MODEL, "LOCAL_PROVIDER", 0),
    OLLAMA_PROFILE: ModelTarget("ollama", OLLAMA_MODEL, "LOCAL_PROVIDER", 0),
})
SUPPORTED_PROFILES = frozenset(TARGETS)
