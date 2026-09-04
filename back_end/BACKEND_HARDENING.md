# Backend hardening notes

## Implemented controls

- Production fails closed for weak/default JWT and MCP secrets, wildcard credentialed CORS, missing OpenRouter credentials and a missing isolated AI database URL.
- JWT issuer, audience, issued-at, not-before, expiry and unique token ID are validated.
- Refresh tokens are stored as SHA-256 digests, rotated after use and revoked after password changes.
- PostgreSQL TLS verification is enabled by default.
- AI SQL runs as `steam_readonly`, restricted to an explicit Steam-table allowlist. It cannot read accounts, RBAC, refresh tokens or agent traces.
- SQL is read-only validated; model-visible rows, Python input, chart points, event payloads, history and step counts are bounded.
- Python executes in E2B, with unsafe patterns rejected before submission.
- User/run identity for saved charts is supplied by the authenticated API across the MCP trust boundary. The model cannot choose another owner.
- Legacy global chat/E2B/file routes are disabled by default.
- Session ownership is checked for list/read/rename/delete/task operations. One active run per session is database-enforced.
- Runs/events are durable, cancellation is persisted and orphaned runs are recovered after restart.
- Proxy headers are not blindly trusted, public errors are sanitized and baseline security headers are applied.

## Production deployment checklist

1. Back up Supabase; run `supabase_agent_harness.sql` and `db_readonly_user.sql` manually.
2. Set a long random password for `steam_readonly`, then configure `DATABASE_URL_READONLY`. Percent-encode reserved URI characters.
3. Rotate every secret previously exposed in logs or screenshots: database, Redis, OpenRouter, E2B and JWT secrets.
4. Generate independent random 32+ character values for `SECRET_KEY` and `MCP_SHARED_SECRET`.
5. Set explicit `CORS_ORIGINS`, `JWT_ISSUER`, `JWT_AUDIENCE`, `OPENROUTER_API_KEY` and `DB_SSL_VERIFY=True`.
6. Bind MCP to `127.0.0.1:8001` (or a private container network). Expose only API `8000` through Nginx/HTTPS.
7. Start MCP and pass health/tool discovery before starting API. Run one Uvicorn worker per service and never use `--reload`.
8. Run unit and smoke tests after deployment. Existing tokens may require users to log in again after secret/auth changes.
9. Add retention for expired refresh tokens, old events/sessions and obsolete chart payloads.

See `DEPLOY_GCP_FREE_TIER.md` for a resource-conscious GCP setup.

## Remaining production work

- Use a leased Postgres worker with heartbeat/retry/idempotency before running multiple API replicas.
- Migrate the tool transport to the official MCP SDK/Streamable HTTP if third-party MCP-client interoperability is required.
- Add per-tool authorization, outbound network allowlists, secret rotation and audit-event redaction/encryption.
- Store downloadable artifacts in private object storage with per-user authorization; local VPS/container storage is not a durable artifact store.
- Add real-Postgres migration/integration tests, dependency/container scanning, structured metrics/traces and load tests.
- Add CSRF protection if browser authentication moves to cross-site cookies; Bearer tokens do not use that mechanism.
