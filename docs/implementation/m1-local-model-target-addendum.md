# Local model target addendum

**Status:** Owner requested implementation in chat, November 19, 2026  
**Scope:** Explicit Ollama development target alongside the existing OpenAI target

The owner requested both local Ollama/Qwen and OpenAI as valid execution targets.
This narrows the earlier multi-provider deferment in the Saturday release scope to
permit these two explicit targets. General provider discovery, automatic failover,
per-role model routing and additional providers remain deferred. Approved logical
requirements, three-agent architecture and safety/execution limits are unchanged.

The local inventory contains `qwen3.5:9b` (ID `d63f830f28d5`, 7.6 GB), with
completion, tools and thinking capabilities. The inspected Ollama client is 0.40.16.
Local inference uses the fixed loopback endpoint `http://127.0.0.1:11434/v1` and that
already-installed tag. It requires no API key or download; OpenAI remains explicitly
configured and uses its existing credential/paid-pilot boundary.

Use the installed LangChain/OpenAI-compatible client for both targets. Ollama uses
Chat Completions with a JSON-schema response format, temperature zero, neutral
repetition penalties and low reasoning effort (enabling this model's boolean
thinking mode); OpenAI retains its reviewed Responses API settings. Both share the same
gateway, strict proposal parser, request/evidence/safety/result validators and local
JSONL. There is no new graph or model-specific decision/safety implementation.

The selection is process-wide and explicit: `haf.ollama.example.toml` with `--local`,
or `haf.release.example.toml` with `--live`. A missing/unavailable/invalid target
fails without silently calling the other provider. Default execution stays disabled.
The existing twelve-model/twelve-tool, five-cycle and thirty-second-per-model-call
bounds apply locally too; slow hardware is reported rather than changing the baseline.

Traces bind provider, requested/returned model, profile and execution mode.
Real Ollama requests use `LOCAL_PROVIDER`, mocks use `OFFLINE_TRANSPORT`, and paid
OpenAI requests retain `LIVE_PROVIDER`. Local calls count toward the same invocation
budget but reserve zero API dollars; OpenAI retains its conservative reservation.
Recorded zero API cost does not describe electricity/hardware cost or model quality.

Offline tests must cover both SDK payload shapes, explicit selection, missing
OpenAI access, no cross-provider fallback, sanitization, budgets and trace identity.
A bounded real local smoke investigation checks the installed model; mock success
alone does not establish local model quality or full scenario acceptance. No paid
OpenAI call is required by this addendum. Keep existing requirements/draft documents
and acceptance gates intact, and do not commit or push automatically.

Sources consulted: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility),
and [LangChain's Ollama integration](https://docs.langchain.com/oss/python/integrations/chat/ollama).
