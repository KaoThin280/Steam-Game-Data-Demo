# DB Admin Panel

Local Flask panel for browsing and editing the **Supabase PostgreSQL** database and the **Upstash Redis** instance used by the back-end.

> **Important:** This panel is intended for local/internal use. Run it on a developer machine or admin laptop only; this review does not verify what is deployed on the VPS. The back-end VPS stays minimal.

## Features

### PostgreSQL
- Browse tables in the `public` (and `steam`) schemas with row counts and live connection status.
- View, search, paginate, sort, edit, add and delete rows.
- Inspect columns, primary keys, foreign keys, unique constraints and indexes.
- Create new tables (visual builder or raw SQL).
- Drop a table with typed confirmation.
- SQL Console: run any query and view results as JSON.

### Redis (Upstash)
- List keys with pagination and pattern search (e.g. `rate_limit:*`).
- Inspect key types: string, hash, list, set, zset.
- Add / delete keys with optional TTL.

## Setup

```bash
cd db_admin
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Supabase + Upstash credentials

python app.py
# Open http://localhost:5000 and log in with ADMIN_ROOT_USERNAME / PASSWORD
```

## Environment variables

```env
SECRET_KEY=random-session-secret
APP_HOST=127.0.0.1
APP_PORT=5000
DEBUG=False

# Login for the panel itself
ADMIN_ROOT_USERNAME=admin_root
ADMIN_ROOT_PASSWORD=ChangeMe!

# Same credentials the back-end uses
DATABASE_URL=postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres
REDIS_URL=rediss://default:PASSWORD@xxx.upstash.io:6379
```

The panel talks directly to the database with SQLAlchemy/psycopg2, so `DATABASE_URL` should be configured with a tested direct or session-pooler URL for administrative work; this repository does not establish universal incompatibility with every transaction-pooler configuration.

## Directory layout

```
db_admin/
├── app.py                    # Flask application
├── config.py                 # .env loader
├── requirements.txt
├── .env.example
├── README.md
└── templates/
    ├── base.html             # Shared layout
    ├── login.html
    ├── dashboard.html        # Connection status + table list
    ├── pg_table.html         # Browse / edit / delete rows
    ├── pg_create_table.html  # Visual + raw-SQL table builder
    ├── pg_sql.html           # SQL console
    └── redis_logs.html       # Redis browser
```

## Security

The panel bypasses the back-end RBAC and connects directly to the database, so its database access follows the configured database role, not website permissions. Treat `ADMIN_ROOT_PASSWORD` like any other production secret and never expose port 5000 on a public interface.

See [documentation index](../docs/README.md) and [security boundaries](../docs/operations/security.md).
