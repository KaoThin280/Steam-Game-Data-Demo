# Steam Game Data Demo

A multi-user web platform that lets visitors explore metadata and reviews of ~10,000 Steam games and ~169,000 user reviews, with interactive dashboards and an AI assistant that can run read-only SQL queries and render charts on the fly. Application-level users authenticate with username/email + password and are assigned roles (admin / analyst / scientist / viewer) with fine-grained permissions.

## Repository layout

```
Steam-Game-Data-Demo/
├── back_end/                  # FastAPI service (deploy to a VPS / Cloud Run)
│   ├── app/
│   │   ├── api/v1/            # auth, games, reviews, dashboard, AI agent, admin
│   │   ├── core/              # config, security, rate-limit, exceptions, log_config
│   │   ├── db/                # async session + SQLAlchemy base (read-only engine)
│   │   ├── models/            # games, reviews, users (Steam + app_users), RBAC tables
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── services/          # auth, steam, AI agent (Charting + ExecuteQuery tools)
│   │   └── utils/             # auth_cookies, signed_urls
│   ├── alembic/               # Database migrations
│   ├── db_extra_tables.sql    # Tables NOT yet created on Supabase -> run once
│   ├── db_init_supabase.sql   # Full reference schema (only if you need to rebuild)
│   ├── db_readonly_user.sql   # Read-only DB role for AI SQL execution (defense-in-depth)
│   ├── Dockerfile             # Optional container image
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── .env.example
│   └── README.md              # Backend-specific setup
│
├── db_admin/                  # Optional Flask admin panel (run locally only)
│   ├── app.py
│   ├── config.py
│   ├── templates/
│   └── README.md
│
├── front_end/                 # Next.js 14 (App Router) deployed to Vercel
│   ├── src/
│   │   ├── app/               # routes, error.tsx, global-error.tsx, not-found.tsx, loading.tsx
│   │   ├── components/        # UI components + renderers
│   │   ├── hooks/             # useAuth, useDashboard, ...
│   │   ├── lib/               # api.ts (axios + httpOnly cookies), auth.ts, types.ts
│   │   ├── store/             # Zustand stores (auth, serverStatus)
│   │   ├── middleware.ts      # Security headers + auth redirect
│   │   └── utils/             # permissions.ts, format.ts
│   ├── .env.local.example
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   ├── vercel.json
│   └── README.md
│
├── deploy/
│   ├── nginx/steam-api.conf   # Production nginx config (SSL + security headers)
│   ├── steam-sync.service     # systemd unit for data sync
│   ├── steam-sync.timer       # systemd timer
│   └── vps_sync.sh            # Manual sync script
│
├── .github/workflows/ci.yml   # CI pipeline (backend tests + frontend lint/build)
├── SCHEMA_DOCUMENTATION.md    # Database schema reference
├── Instruction.md             # Project brief (Vietnamese)
├── DEPLOY.md                  # Deployment guide (with / without Docker)
└── .gitignore
```

## Stack

| Layer | Technology |
|---|---|
| Back-end | Python 3.11+, FastAPI, SQLAlchemy 2 (async), asyncpg, Redis, OpenAI SDK (OpenRouter), JWT auth + httpOnly cookies, RBAC |
| Database | PostgreSQL on Supabase (free tier, public schema) + read-only role for AI |
| Cache / Rate-limit | Redis on Upstash (free tier) |
| AI | OpenRouter API (free models), tool-calling agent (Charting + ExecuteQuery) |
| Migrations | Alembic |
| Admin panel | Flask + SQLAlchemy (run locally, NOT on the VPS) |
| Front-end | Next.js 14 (App Router) + TypeScript + Tailwind, httpOnly cookie auth |
| Reverse proxy | nginx (SSL termination, rate-limit, security headers) |
| Deploy | Back-end on GCP Cloud Run / VPS, front-end on Vercel (both free tier) |
| CI/CD | GitHub Actions |

## Security features

- **httpOnly cookies** for JWT (XSS-resistant)
- **HMAC signed URLs** for sandbox-generated files
- **Read-only DB role** for AI SQL execution (defense-in-depth)
- **Rate limiting** (per-IP, per-bucket) for all endpoints
- **Security headers** in FastAPI middleware + nginx + Next.js
- **CORS** allowlist (not `*`) in production
- **Path traversal** protection for file serving
- **Prepared statement cache disabled** to avoid issues through pgbouncer
- **CORS-aware middleware** that normalises DATABASE_URL passwords
- **session-level isolation** (main engine for writes, readonly engine for AI)

## Roles & permissions

| Role | Capabilities |
|---|---|
| `admin` | Full access: read / write / delete games, reviews, users + manage roles |
| `scientist` | Read + write games and reviews (no delete, no user management) |
| `analyst` | Read-only across games, reviews, users |
| `viewer` | Read-only on games and reviews |

Default permissions: `games_read`, `games_write`, `games_delete`, `reviews_read`, `reviews_write`, `reviews_delete`, `users_read`, `users_write`, `users_delete`, `users_manage_roles`, `system_admin`.

## Quick start

Read **[DEPLOY.md](DEPLOY.md)** for the full step-by-step guide (with and without Docker).

In short:
1. Create a Supabase project, run `back_end/db_extra_tables.sql` once.
2. (Recommended) Run `back_end/db_readonly_user.sql` to create the `steam_readonly` role.
3. (Recommended) Run `back_end/alembic upgrade head` instead of running raw SQL.
4. Create an Upstash Redis database, copy the connection URL.
5. Get an OpenRouter API key.
6. Configure `back_end/.env` (copy from `.env.example`).
7. Deploy `back_end/` to a VPS (GCP free tier) or Cloud Run — see DEPLOY.md.
8. (Optional) `db_admin/` is a local-only Flask panel for direct DB inspection.
9. Configure `front_end/.env.local` and deploy to Vercel.

## Testing

```bash
# Backend
cd back_end
pip install -r requirements.txt
pytest

# Frontend
cd front_end
npm ci
npm run lint
npm run build
```

## License

Internal demo project. Not published under an open-source license.