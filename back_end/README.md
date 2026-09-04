# Back end and AI Agent Harness

This directory contains two cooperating FastAPI services:

| Service | Default address | Responsibility |
| --- | --- | --- |
| Product API | `http://127.0.0.1:8000` | Authentication/RBAC, games and dashboard APIs, durable chat sessions/runs/events, OpenRouter agent loop, SSE |
| MCP tool server | `http://127.0.0.1:8001/mcp` | Tool discovery/execution, read-only Steam queries, E2B Python analysis, chart creation and chart-cache access |

Only port `8000` should be public. Port `8001` is an internal service protected by `MCP_SHARED_SECRET`; browsers and Vercel never call it directly.

## Agent workflow

```text
Frontend -> API :8000 -> OpenRouter model
                       -> MCP :8001 -> read-only Supabase role
                                    -> E2B Python sandbox
                                    -> ai_chart_history cache/catalog
```

The model receives schema descriptions, statistics, small samples and bounded tool results rather than a full database dump. It can call:

- `steam_catalog_overview`
- `describe_steam_table`
- `query_steam_data`
- `analyze_with_python`
- `monthly_game_releases`
- `create_chart`
- `search_saved_charts`
- `get_saved_chart`

Test-only failure tools are also available for harness verification. SQL is validated as read-only and is executed with `steam_readonly`. Non-aggregate data returned to the model is limited to a small sample; aggregate series may contain up to 1,200 points. Python receives at most 5,000 rows/5 MB and runs remotely in E2B. Charts are persisted in `ai_chart_history` and can be reused by later runs.

Sessions, runs and append-only events are stored in `agent_sessions`, `agent_runs` and `agent_events`. Queued/running work interrupted by a restart is recovered on startup. One active run per session is enforced by the database.

## Active API surface

The main application exposes:

- `/api/v1/auth/*` - register, login, refresh, logout and profile
- `/api/v1/games/*` - game/review REST operations with RBAC
- `/api/v1/dashboard/*` - dashboard aggregates
- `/api/v1/agent-rpc/sessions` - list/create sessions
- `/api/v1/agent-rpc/sessions/{id}` - rename/delete a session
- `/api/v1/agent-rpc/sessions/{id}/tasks` - submit a durable task (`202`)
- `/api/v1/agent-rpc/runs/{id}` - run status/result
- `/api/v1/agent-rpc/runs/{id}/events` - persisted event trace
- `/api/v1/agent-rpc/runs/{id}/stream` - SSE event replay/live stream
- `/api/v1/agent-rpc/runs/{id}/cancel` - durable cancellation
- `/api/v1/admin/*` - user/role administration
- `/health`, `/docs` and `/agent-demo`

Legacy `/api/v1/ai`, `/chat` and `/data-files` routes are disabled by default with `ENABLE_LEGACY_AI=False`. They are compatibility code, not the current chat workflow.

## Database setup

Run these scripts manually in Supabase SQL Editor:

1. `supabase_agent_harness.sql`
2. `db_readonly_user.sql`
3. Set a real password with the script's commented `ALTER ROLE` statement.

Then configure both `DATABASE_URL` and `DATABASE_URL_READONLY`. Percent-encode reserved URI characters in credentials; for example `@` becomes `%40`.

## Local development

From the repository root on Windows, the simplest option is:

```powershell
.\scripts\start_local_stack.ps1
```

It starts MCP on `8001`, the API on `8000`, and Next.js on `3000`, and uses one ephemeral shared MCP secret for both backend processes.

To start services manually, set the same 32+ character `MCP_SHARED_SECRET` in both processes and start MCP first:

```powershell
cd back_end
.\.venv\Scripts\python.exe -m uvicorn app.mcp_server:app --host 127.0.0.1 --port 8001
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Do not use `--reload` in production. Open `http://127.0.0.1:8000/docs` or `http://127.0.0.1:8000/agent-demo`.

## Tests

```powershell
.\scripts\test_backend_unit.ps1
.\scripts\test_agent_local.ps1
.\scripts\test_agent_local.ps1 -ConversationSuite
```

The first command runs isolated unit tests. The smoke test starts both backend services when needed and validates login, persistent sessions, tool calls, events and cancellation. `-ConversationSuite` creates multiple multilingual sessions with multiple turns and chart requests.

## Deployment

See [DEPLOY_GCP_FREE_TIER.md](DEPLOY_GCP_FREE_TIER.md). A 1 GB e2-micro can run the project, but two Python containers plus Docker itself leave little memory; two single-worker `systemd` services are the recommended free-tier deployment. If Docker Compose is used, build the image in CI, keep Supabase/Redis/E2B external, and monitor memory.

Architecture and security details:

- [AGENT_HARNESS_ARCHITECTURE.md](AGENT_HARNESS_ARCHITECTURE.md)
- [BACKEND_HARDENING.md](BACKEND_HARDENING.md)

## AI-assisted error email

Optional operational notifications cover unhandled HTTP 500 errors, startup
failures and terminal Agent Run failures. Before calling OpenRouter, the service
removes common credentials, excludes request bodies/headers and truncates the
context. OpenRouter produces a short Vietnamese `title` and `body`; SMTP sends
the result. Repeated identical failures are suppressed for a configurable
interval, and a local fallback summary is used if OpenRouter is unavailable.

Enable it only in the protected deployment `.env`:

```dotenv
ERROR_NOTIFICATIONS_ENABLED=True
ERROR_NOTIFICATION_TO=your-alert-address@example.com
ERROR_NOTIFICATION_ENVIRONMENT=production
ERROR_NOTIFICATION_MIN_INTERVAL_SECONDS=300
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender@example.com
SMTP_PASSWORD=<provider app password>
SMTP_FROM_EMAIL=your-sender@example.com
SMTP_STARTTLS=True
```

For Gmail, `SMTP_PASSWORD` must be an App Password; do not use or commit the
normal account password. Alert delivery is best-effort and never changes the
original API/run result.

After configuring the protected `.env`, send one controlled test from
`back_end/`:

```bash
./venv/bin/python3 -m app.services.error_notification_service
```
