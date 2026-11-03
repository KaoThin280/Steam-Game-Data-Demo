---
name: steam-backend
description: Develop and debug Steam Game Data Demo FastAPI APIs, authentication, RBAC, PostgreSQL models and migrations, Redis rate limits, and backend operations. Use for this project's backend changes; model reasoning, AI tools, and retrieval behavior belong to steam-ai-agent.
---

# Steam backend development

Use the active Steam Game Data Demo repository, verifying `back_end/app/main.py` and `docs/README.md`. Paths below are relative to that repository, not this installed skill. Check the current working tree and preserve unrelated changes. These instructions support the requested scope; they do not authorize publishing, changing live data, or redesigning the entire application.

## Find the owning contract

Read `docs/architecture/system.md` plus the reference for the requested area. Treat documentation and `docs/maintenance/documentation-audit.md` as navigation; verify behavior against current code before repeating a known issue.

| Work | Source and reference |
|---|---|
| REST endpoint | `back_end/app/api/v1/`, `app/schemas/`, owning service; `docs/reference/api.md` |
| Auth/RBAC | `app/api/v1/auth.py`, `admin.py`, `app/api/dependencies.py`, `app/services/auth_service.py`, `app/core/security.py`, `app/utils/auth_cookies.py` |
| Database | `app/models/`, `app/db/session.py`, SQL files and `alembic/versions/`; `docs/reference/database-schema.md` |
| Rate limit | `app/core/rate_limit.py`, callers and `app/core/config.py` |
| Startup/deployment | `app/main.py`, `app/mcp_server.py`, `.github/workflows/`, `back_end/docker-compose.agent.yml`; `docs/operations/deployment.md` |

## Change APIs end to end

Trace input validation -> active user/permission/ownership -> service/query -> transaction -> response. Match field names, status codes, pagination and error shape to the consumer. Inspect `front_end/src/lib/api.ts`, `lib/types.ts`, relevant hooks/store when changing a client-facing contract; an OpenAPI declaration alone does not prove the frontend uses it correctly.

Backend supports cookie and Bearer access auth. Refresh credentials are cookie/header based in the inspected implementation; do not add refresh token plaintext to response JSON simply to satisfy an old frontend assumption. Verify current behavior before fixing refresh; test cookie attributes, expiry, rotation and logout across the intended origins. UI role guards do not enforce API authorization, and authenticated ownership is distinct from role permission.

For filtering/aggregation, verify the service applies the parameter and avoid JOIN fan-out. Distinguish game counts from review counts and distinct-game counts. Parameterize SQL values; validate identifiers/sort choices through a finite mapping. Do not confuse Steam `users` with website `app_users`.

## Evolve data without assuming baseline completeness

Current ORM, deployed schema and checked-in migrations can differ. Inspect all three when available; never infer that `alembic upgrade head` or `CREATE TABLE IF NOT EXISTS` upgrades every existing table. For schema changes, provide migration/backfill ordering, required grants/RLS and index changes, plus a rollback or forward-recovery strategy suited to the change.

Test a fresh database and an upgrade from the affected older shape when migration correctness matters. Use a disposable/test database; if none is available, prepare SQL and clearly distinguish static review from executed validation. Do not apply migrations to the configured production connection by default.

AI SQL uses `DATABASE_URL_READONLY`, while application state and chart persistence use the main connection. A URL or role name does not prove effective read-only privileges; verify grants/RLS when the task requires live access validation. Avoid repairing invisible data by broadly granting access to account, token or agent trace tables.

## Preserve execution and operations semantics

The product API and internal tool server are separate processes; startup requires MCP availability. Agent scheduling is currently in the API process with durable PostgreSQL records and one-worker assumptions. If a backend change touches run lifecycle, inspect the harness contracts rather than treating tasks as a distributed queue.

Health HTTP 200 can contain a degraded payload; readiness checks must examine the intended dependency result. Verify the chosen process manager before editing deployment: the checked-in SSH workflow, proposed systemd units and legacy rsync timer are different paths. Do not fix a documentation request by starting/restarting services. Check whether a helper such as log rotation is actually invoked before documenting it as active.

## Verify and maintain

Use `docs/guides/testing.md` for available commands. Add focused behavioral tests for changed permissions, refresh rotation, filter semantics, transaction failures or migration compatibility. Run only checks relevant to the change; do not replace missing database evidence with mocks and call it integration-tested. For frontend contract changes, include its type/build checks and test the interaction when the runtime is available.

Update `docs/reference/api.md`, `database-schema.md` or operations guides when their contract changes. Record resolved audit findings as resolved after verification instead of preserving stale warnings. Summarize in Vietnamese what changed, why, validation performed, and any remaining runtime or migration limitations.
