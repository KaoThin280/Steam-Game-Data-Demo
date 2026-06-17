# Steam Game Data Demo

A multi-user web platform that lets visitors explore metadata and reviews of ~10,000 Steam games and ~169,000 user reviews, with interactive dashboards and an AI assistant that can run read-only SQL queries and render charts on the fly. Application-level users authenticate with username/email + password and are assigned roles (admin / analyst / scientist / viewer) with fine-grained permissions.

## Repository layout

```
Steam-Game-Data-Demo/
├── back_end/                 # FastAPI service (deploy to a VPS - GCP)
│   ├── app/
│   │   ├── api/v1/           # auth, games, reviews, dashboard, AI agent, admin
│   │   ├── core/             # config, security, rate-limit, exceptions
│   │   ├── db/               # async session + SQLAlchemy base
│   │   ├── models/           # games, reviews, users (Steam + app_users), RBAC tables
│   │   ├── schemas/          # Pydantic request/response models
│   │   └── services/         # auth, steam, AI agent (Charting + ExecuteQuery tools)
│   ├── db_extra_tables.sql   # Tables NOT yet created on Supabase -> run once
│   ├── db_init_supabase.sql  # Full reference schema (only if you need to rebuild)
│   ├── Dockerfile            # Optional container image
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md             # Backend-specific setup
│
├── db_admin/                 # Optional Flask admin panel (run locally only)
│   ├── app.py
│   ├── config.py
│   ├── templates/
│   └── README.md
│
├── front_end/                # Placeholder for the Vercel-hosted front-end
│   └── README.md
│
├── SCHEMA_DOCUMENTATION.md   # Database schema reference
├── Instruction.md            # Project brief (Vietnamese)
├── DEPLOY.md                 # Deployment guide (with / without Docker)
└── .gitignore
```

## Stack

| Layer | Technology |
|---|---|
| Back-end | Python 3.11+, FastAPI, SQLAlchemy 2 (async), asyncpg, Redis, OpenAI SDK (OpenRouter), JWT auth, RBAC |
| Database | PostgreSQL on Supabase (free tier, public schema) |
| Cache / Rate-limit | Redis on Upstash (free tier) |
| AI | OpenRouter API (free models), tool-calling agent (Charting + ExecuteQuery) |
| Admin panel | Flask + SQLAlchemy (run locally, NOT on the VPS) |
| Front-end (future) | Next.js / React on Vercel |

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
2. Create an Upstash Redis database, copy the connection URL.
3. Get an OpenRouter API key.
4. Configure `back_end/.env` (copy from `.env.example`).
5. Deploy `back_end/` to a VPS (GCP free tier) — see DEPLOY.md.
6. (Optional) `db_admin/` is a local-only Flask panel for direct DB inspection.
7. (Future) build the front-end in `front_end/` and deploy to Vercel.

## License

Internal demo project. Not published under an open-source license.