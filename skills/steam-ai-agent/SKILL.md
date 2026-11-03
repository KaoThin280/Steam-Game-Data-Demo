---
name: steam-ai-agent
description: Develop and debug the Steam Game Data Demo Agent Harness, including prompts, model adapters, MCP-style tools, run lifecycle, chart analysis, and RAG extensions. Use for changes to this project's AI workflow; ordinary REST, auth, and database work belongs to steam-backend.
---

# Steam AI Agent development

Work against the user's active Steam Game Data Demo checkout. Resolve paths below from its repository root, not from the installed skill directory. Verify `back_end/app/agent_harness` and `docs/README.md` exist; if another project is active, locate the requested checkout before editing. Do not hard-code a developer's machine path.

## Establish the affected flow

Read `docs/architecture/agent-harness.md` and the relevant source before choosing an edit. Use `docs/maintenance/documentation-audit.md` as a list of leads to recheck, not an immutable defect list.

| Requested change | Read first |
|---|---|
| Prompt, language, loop, repeated tools | `back_end/app/agent_harness/runtime.py` |
| Model parameters or fallback | `back_end/app/agent_harness/provider.py`, `types.py`, `back_end/app/core/config.py` |
| Tool schema, SQL, Python, chart | `back_end/app/agent_harness/mcp.py`, `back_end/app/mcp_server.py` |
| History, task submission, cancel, recovery | `back_end/app/api/v1/agent_rpc.py`, `back_end/app/agent_harness/store.py`, `back_end/app/models/agent.py` |
| Missing chart/progress in UI | Above contract plus `front_end/src/hooks/useAgentHarness.ts`, `components/chat/AgentChatWorkspace.tsx`, `components/Renderers/PlotlyChartRenderer.tsx` |
| RAG | `docs/proposals/rag.md`, then `docs/proposals/rag-implementation.md` |

For a bug, identify the failing boundary: request -> persisted run -> history -> provider -> gateway -> tool -> event/result -> UI. Inspect a focused trace or reproduce with controlled dependencies. Do not treat a prompt change as a fix for missing schema, RLS, wrong chart shape, or an API contract mismatch.

## Preserve the actual boundaries

- Current frontend chat uses `/api/v1/agent-rpc`. Legacy `services/ai_service.py` and `agentic_workflow.py` are not the default harness; edit them only for a legacy task.
- Keep `AgentRuntime` expressed through `ModelProvider`, `ToolGateway`, and `RunStore`. Put SQL/E2B work behind tools and provider-specific behavior in the provider adapter. If a new interface is needed, explain the boundary it adds.
- Frontend transport is REST/polling with an available SSE event endpoint. Gateway to `/mcp` uses a JSON-RPC tools subset. A transport change needs compatibility tests; do not label the existing subset full MCP compliance.
- Recheck limits in config and handlers rather than copying historical numbers. Tool schema, handler validation, bounded result, and UI chart shape must agree. Model tool arguments are untrusted; owner/session/run context comes from authenticated application code.
- History currently reconstructs completed input/output pairs in PostgreSQL. Redis is rate limiting. Persisted events are not checkpoints or unrestricted reasoning traces.
- Recovery replays work and in-memory duplicate suppression does not survive restart. Changes with external effects need explicit replay/idempotency semantics; do not add API workers as a shortcut for agent concurrency.

## Implement the requested change

State the intended behavior and how it will be observed. For a new tool, update discovery/schema, dispatch/handler, context authorization and error/result contract together. Define how timeout, cancellation, empty data and repeat execution behave when relevant. SQL validation supplements actual restricted database grants; Python pattern checks supplement E2B isolation.

For RAG, follow the proposal only as a starting design: distinguish implemented behavior from proposed modules. Preserve authoritative SQL tools for current numeric facts. Filter retrieval by trusted access scope before selecting context, preserve source/version metadata, and treat retrieved text as data rather than instructions. Do not index `.env`, logs, tokens or all chat histories by default. Do not add a vector database or embedding dependency until the requested milestone needs it.

## Verify and report

Use focused tests in `back_end/tests/test_agent_runtime.py` and `test_agent_mcp_contract.py` for changed contracts. Choose cases that expose the change: tool result reaches the next model turn, invalid input is rejected, another user's chart cannot be fetched, cancellation is durable, or replay does not duplicate a newly introduced effect. For RAG, include the acceptance cases in the implementation proposal; use fake embeddings/retrievers for deterministic unit tests.

Run the backend unit entrypoint in `docs/guides/testing.md` when appropriate. Real smoke/conversation tests require configured services and can consume quota/create sessions; distinguish them from unit evidence. If only files/scripts were requested or the runtime is unavailable, deliver the implementation and state what remains unverified. Do not launch a deployment or apply production migrations merely because this skill is active.

Update affected architecture, API, prompt/tool reference and RAG status alongside code. Explain the result in Vietnamese, retaining English code identifiers, and show the concrete message/data path when discussing architecture. Report actual validation and remaining limits without claiming provider accuracy from mocked tests.
