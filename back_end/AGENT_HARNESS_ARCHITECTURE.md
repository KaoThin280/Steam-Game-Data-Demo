# AI Agent Harness architecture

## Components and trust boundaries

1. **Product API (`app.main`, port 8000)** authenticates users, checks session ownership, persists sessions/runs/events and executes the bounded OpenRouter tool loop.
2. **Agent runtime** depends on replaceable `ModelProvider`, `ToolGateway` and `RunStore` interfaces. It is not tied to FastAPI or a particular model SDK.
3. **MCP-compatible tool server (`app.mcp_server`, port 8001)** exposes JSON-RPC `tools/list` and `tools/call` over HTTP. It is independently runnable and requires a bearer `MCP_SHARED_SECRET`.
4. **Data and execution plane** uses a restricted `steam_readonly` Supabase connection for Steam data and E2B for isolated Python. The MCP service uses the main database connection only for the user-owned chart catalog/cache.

Port 8001 is an internal boundary, not a public product API. The current transport implements the MCP tool concepts and JSON-RPC methods needed by the harness; adopting the official MCP SDK and Streamable HTTP transport is a future interoperability improvement.

## Request lifecycle

```text
create/select session
  -> submit task (HTTP 202)
  -> queued -> running
  -> model request
  -> zero or more MCP tools/list or tools/call cycles
  -> completed | failed | cancelled
```

Clients poll the run/events endpoints or consume SSE. Every model/tool boundary and terminal state is appended to `agent_events`. Tool results are returned to the model so it can revise invalid SQL, choose another tool or explain an unavailable result.

Conversation context is rebuilt from completed runs in the same session. Session titles can be changed and sessions can be deleted by their owner.

## Data-analysis policy

- The system prompt identifies the agent as a Steam data analyst and describes the backend/tool contract.
- The model does not receive complete tables. It receives schema, descriptive statistics, a small sample and bounded aggregate results.
- `query_steam_data` permits only read-only `SELECT`/`WITH`. General row samples are capped at 10; aggregate time series are capped at 1,200.
- `analyze_with_python` can retrieve up to 5,000 rows/5 MB, execute guarded code in E2B, and return summaries/charts rather than the raw frame.
- `create_chart` respects an explicit chart type (`bar`, `line`, `scatter`, `area`, `pie`, `doughnut`) and limits rendered points.
- Chart metadata and payloads are stored in `ai_chart_history`. `search_saved_charts` and `get_saved_chart` let later tasks reuse them; deterministic monthly charts also support cache keys.
- User/run context used for chart ownership is injected by the trusted API, not accepted from model-generated tool arguments.

## Durability and cancellation

Supabase is the source of truth. A partial unique index permits only one queued/running run per session. Cancellation sets `cancel_requested` durably and also cancels a live task in the current process.

At shutdown, unfinished non-cancelled work is put back in `queued`. At startup, the API records `run.recovered` and replays orphaned work. Current data tools are read-only and chart writes use reusable keys, making replay safe for the supported workflow.

This design targets one API worker. Horizontal scaling requires a Postgres-leased worker (`FOR UPDATE SKIP LOCKED`), heartbeat/lease expiry and idempotency for every write-capable tool.

## Failure behavior and bounds

- Unknown tool -> structured `TOOL_NOT_FOUND`
- Invalid SQL/tool input -> structured error returned to the model
- Tool timeout -> `TOOL_TIMEOUT`
- MCP connection failure -> `MCP_DISCONNECTED`
- Repeated tool loop -> stopped at `AGENT_MAX_STEPS`
- Runtime/provider exception -> sanitized `run.failed` event and terminal state
- Oversized event/tool result -> bounded before persistence/model context

`AGENT_TOOL_TIMEOUT` governs normal tool calls; long-running E2B work uses its configured sandbox timeout. Token/time/rate limits remain necessary because free OpenRouter models can be slow or unavailable.

## Assessment demo

1. Start MCP `8001`, then API `8000`, then the frontend or `/agent-demo`.
2. Log in and create two sessions in different languages.
3. In each session ask: identity, total games, and a monthly release chart.
4. Show the event trace containing model and MCP tool boundaries.
5. Ask for the chart again and show reuse through the saved-chart tools/cache.
6. Cancel a slow run, then restart the API during another run to demonstrate persistence/recovery.
7. Run unit tests and the multilingual conversation suite.
