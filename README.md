# Steam Game Data Demo — AI Agent Harness

A deployed Steam analytics platform and bounded AI agent harness built for the
Celesnity 2026 AI Track assessment.

## Assessment submission

The main deliverable is:

- [AI Agent Track Submission](AI_AGENT_TRACK_SUBMISSION.md) — architecture,
  requirement mapping, design decisions, trade-offs, failure semantics,
  verification, demo plan and production roadmap.

Supporting technical documents:

- [Backend and local setup](back_end/README.md)
- [Agent Harness architecture](back_end/AGENT_HARNESS_ARCHITECTURE.md)
- [Security and hardening](back_end/BACKEND_HARDENING.md)
- [GCP Free Tier deployment](back_end/DEPLOY_GCP_FREE_TIER.md)
- [Local test scripts](scripts/README.md)

## Current architecture

| Component | Responsibility |
| --- | --- |
| Next.js frontend | Authentication UI, dashboard, durable chat sessions, event progress and interactive Plotly charts |
| FastAPI product API (`:8000`) | JWT/RBAC, Steam REST APIs, session/run lifecycle, OpenRouter agent loop, status/events/SSE/cancellation |
| MCP-compatible tool server (`:8001`) | Approved read-only data tools, E2B Python analysis, chart generation/cache and failure-injection tools |
| Supabase PostgreSQL | Steam data plus durable agent sessions, runs, events and saved charts |
| Upstash Redis | Rate limiting and product cache |
| OpenRouter | Real LLM provider behind the project-owned `ModelProvider` interface |
| E2B | Isolation boundary for model-written Python |

Only port `8000` is public. The API calls the independently running tool server
on loopback with a shared service secret.

## Repository layout

```text
back_end/
  app/agent_harness/       transport-neutral types, loop, provider, gateway, store
  app/api/v1/agent_rpc.py  authenticated REST/SSE session and run transport
  app/mcp_server.py        independently runnable MCP-compatible HTTP service
  tests/                   unit tests for loop, tools, persistence contracts and security
front_end/                 Next.js dashboard and Agent Harness chat workspace
scripts/                   local stack, unit and end-to-end smoke-test entrypoints
.github/workflows/         CI and two-service VPS deployment
```

## Run locally on Windows

Configure the gitignored `back_end/.env`, then run from the repository root:

```powershell
.\scripts\start_local_stack.ps1
```

This starts MCP on `8001`, the product API on `8000`, and Next.js on `3000`.

Tests:

```powershell
.\scripts\test_backend_unit.ps1
.\scripts\test_agent_local.ps1
.\scripts\test_agent_local.ps1 -ConversationSuite
```

Database migrations are intentionally supplied as SQL files for manual review
and execution in Supabase. Secrets, `.env` files and runtime logs are not stored
in the repository.
