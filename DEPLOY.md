# Deployment Guide

This document covers every step required to bring the project online:
1. Provision external services (Supabase, Upstash, OpenRouter, Google Drive).
2. Set up the database schema and import the seed dataset.
3. Deploy the back-end to a free-tier GCP VM (with **or** without Docker).
4. (Future) Deploy the front-end to Vercel.

> All command snippets assume a Debian/Ubuntu-style Linux VPS. Adapt for other distros as needed.

---

## 1. External services

### 1.1 Supabase (PostgreSQL, free tier ~500 MB)

1. Create an account at <https://supabase.com> and start a new project.
2. Wait for the database to provision, then open **Project Settings → Database**.
3. Copy the **Connection string (URI, Transaction mode)**. The async SQLAlchemy engine expects a URL like:
   ```
   postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
   ```
   (The application rewrites `postgresql://` → `postgresql+asyncpg://` automatically.)
4. Open **SQL Editor → New query** and run the contents of `back_end/db_extra_tables.sql`. This creates the tables that are not in the initial schema: `refresh_tokens`, `chat_histories`, `ai_chart_history`. The script is idempotent (uses `CREATE TABLE IF NOT EXISTS`).
5. Optional: run `back_end/db_init_supabase.sql` if you need to rebuild the full schema from scratch.

### 1.2 Upstash Redis (free tier ~256 MB)

1. Sign up at <https://upstash.com> and create a Redis database.
2. Copy the **Endpoint** URL (the rediss:// form, including TLS). Paste it into `REDIS_URL` in your `.env`.

### 1.3 OpenRouter (AI models)

1. Sign up at <https://openrouter.ai>, generate an API key.
2. Pick a free model (e.g. `deepseek/deepseek-chat-v3.1:free`) and a fallback (`meta-llama/llama-3.3-70b-instruct:free`).
3. Put the key and model names into `.env`.

### 1.4 Seed dataset (Google Drive)

The project ships with the application database schema but **not** the seed dataset. Steam game metadata and reviews are provided as CSV files on Google Drive:

- **Folder**: <https://drive.google.com/drive/u/0/folders/1VMBv31EJ_DY3yga17HYiGjyGXS_9tzwd>

Expected files (typical Steam store dump):
- `metadata.csv` – game metadata (one row per `steam_appid`).
- `reviews.csv` – review rows (one row per `recommendationid`).

To populate the database on Supabase:

1. **Easiest path (CSV → Supabase UI):**
   - In Supabase Dashboard → **Table Editor** → open `games`, click **Insert → Import data from CSV**, upload `metadata.csv` mapped to the columns.
   - Repeat for `reviews` and `users`.
   - Watch out for type mismatches (CSV `True/False` → Postgres `boolean`, dates → `DATE` / `TIMESTAMPTZ`).

2. **Programmatic path (recommended for the large reviews file):**
   - Download both CSVs from the Drive folder to your local machine.
   - Use the `psql` `\copy` command for fast bulk loading:
     ```bash
     psql "<DATABASE_URL>" <<SQL
     \copy games(steam_appid, name, is_free, supported_languages, required_age, release_date, publishers, developers, categories, genres, price_text) \
       FROM 'metadata.csv' WITH (FORMAT csv, HEADER true);
     \copy users(steamid, personaname, num_games_owned) \
       FROM 'users.csv' WITH (FORMAT csv, HEADER true);  -- if available
     \copy reviews(recommendationid, steam_appid, steamid, language, review_text, timestamp_created, timestamp_updated, refunded, received_for_free, written_during_early_access, primarily_steam_deck, playtime_at_review, playtime_last_two_weeks, playtime_forever) \
       FROM 'reviews.csv' WITH (FORMAT csv, HEADER true);
     SQL
     ```
   - If your CSV has columns in a different order, edit the column list accordingly.
   - Use Supabase's connection string with **Session mode** (port `5432`, direct) for `psql`.

3. **Verify row counts:**
   ```sql
   SELECT 'games'   AS t, COUNT(*) FROM games
   UNION ALL
   SELECT 'reviews', COUNT(*) FROM reviews
   UNION ALL
   SELECT 'users',   COUNT(*) FROM users;
   ```

---

## 2. Back-end environment configuration

Copy the example file and fill in the real values:

```bash
cd back_end
cp .env.example .env
nano .env
```

Mandatory variables:

| Variable | Example | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres` | Supabase connection string |
| `REDIS_URL` | `rediss://default:PASSWORD@xxx.upstash.io:6379` | Upstash endpoint (TLS) |
| `SECRET_KEY` | random 64-hex-char string | Generate with `openssl rand -hex 32` |
| `OPENROUTER_API_KEY` | `sk-or-v1-...` | Required for AI features |
| `OPENROUTER_MODEL` | `deepseek/deepseek-chat-v3.1:free` | Primary model |
| `OPENROUTER_FALLBACK_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | Used when primary fails |
| `BOOTSTRAP_ADMIN_EMAIL` | `admin@yourdomain.com` | Created on first start |
| `BOOTSTRAP_ADMIN_PASSWORD` | strong password | Created on first start |
| `CORS_ORIGINS` | `["https://your-frontend.vercel.app"]` | Comma-separated JSON list |

---

## 3. Deploy the back-end to a free-tier GCP VM

Recommended VM: **e2-micro** (free in us-central1 / us-west1 / us-east1), 1 GB RAM, 10 GB SSD.
Recommended OS: **Debian 12** or **Ubuntu 22.04 LTS**.

### 3.1 Provision the VM

```bash
# In Google Cloud Console
gcloud compute instances create steam-api-vm \
  --machine-type=e2-micro \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --zone=us-central1-a \
  --tags=http-server,https-server,ssh

# Open firewall for the API port (default 8000)
gcloud compute firewall-rules create allow-steam-api \
  --direction=INGRESS --priority=1000 \
  --network=default --action=ALLOW \
  --rules=tcp:8000 --source-ranges=0.0.0.0/0
```

### 3.2 SSH into the VM and install prerequisites

```bash
ssh <user>@<vm-external-ip>

sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-venv python3-pip nginx
```

### 3.3 Clone the repository

```bash
sudo mkdir -p /opt/steam-game
sudo chown $USER:$USER /opt/steam-game
cd /opt/steam-game
git clone https://github.com/<your-account>/Steam-Game-Data-Demo.git .
```

### 3.4 Choose: with Docker or without Docker

#### Option A — Without Docker (recommended for free-tier VMs)

Because the project is intentionally lightweight, you can run the FastAPI service directly with `systemd` and let Nginx act as a reverse proxy. This keeps RAM usage under 200 MB and avoids Docker overhead.

1. **Set up the venv and install dependencies:**
   ```bash
   cd /opt/steam-game/back_end
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Create the `.env` file** (see section 2):
   ```bash
   cp .env.example .env
   nano .env
   chmod 600 .env
   ```

3. **Run a quick smoke test:**
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   # In another terminal: curl http://127.0.0.1:8000/health
   # Stop with Ctrl+C once you see {"status":"healthy",...}
   ```

4. **Install the systemd unit:**
   ```bash
   sudo tee /etc/systemd/system/steam-api.service > /dev/null <<'UNIT'
   [Unit]
   Description=Steam Game Data API
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/opt/steam-game/back_end
   EnvironmentFile=/opt/steam-game/back_end/.env
   ExecStart=/opt/steam-game/back_end/.venv/bin/uvicorn app.main:app \
       --host 127.0.0.1 --port 8000 --workers 1 --log-level info
   Restart=on-failure
   RestartSec=5
   StandardOutput=append:/var/log/steam-api.log
   StandardError=append:/var/log/steam-api.err.log

   [Install]
   WantedBy=multi-user.target
   UNIT

   # Make sure www-data owns the directory and the venv
   sudo chown -R www-data:www-data /opt/steam-game
   sudo systemctl daemon-reload
   sudo systemctl enable steam-api
   sudo systemctl start steam-api
   sudo systemctl status steam-api
   ```

5. **Reverse-proxy with Nginx (recommended):**
   ```bash
   sudo tee /etc/nginx/sites-available/steam-api > /dev/null <<'NGINX'
   server {
       listen 80;
       server_name api.yourdomain.com;   # or the VM IP

       client_max_body_size 10m;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_http_version 1.1;
           proxy_read_timeout 120s;
       }
   }
   NGINX

   sudo ln -sf /etc/nginx/sites-available/steam-api /etc/nginx/sites-enabled/steam-api
   sudo nginx -t && sudo systemctl reload nginx
   ```

6. **(Optional) Free TLS with Let's Encrypt:**
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d api.yourdomain.com
   ```

7. **Updating the service after a `git pull`:**
   ```bash
   cd /opt/steam-game && git pull
   cd back_end && source .venv/bin/activate
   pip install -r requirements.txt     # only when requirements.txt changed
   sudo systemctl restart steam-api
   ```

#### Option B — With Docker (alternative path)

Use Docker only if your environment requires it (e.g. you want parity with another project). It does add ~100 MB of RAM overhead.

1. Install Docker:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   newgrp docker
   ```

2. Build and run:
   ```bash
   cd /opt/steam-game/back_end
   cp .env.example .env && nano .env

   docker build -t steam-api:latest .
   docker run -d --name steam-api \
     --restart unless-stopped \
     --env-file .env \
     -p 127.0.0.1:8000:8000 \
     steam-api:latest
   ```

3. Or use Docker Compose (`docker-compose.yml` snippet below):
   ```yaml
   services:
     steam-api:
       build: ./back_end
       container_name: steam-api
       restart: unless-stopped
       env_file: ./back_end/.env
       ports:
         - "127.0.0.1:8000:8000"
   ```
   ```bash
   docker compose up -d
   ```

4. Update with Docker:
   ```bash
   cd /opt/steam-game && git pull
   cd back_end
   docker build -t steam-api:latest .
   docker compose up -d   # or: docker restart steam-api
   ```

### 3.5 Verify the deployment

```bash
curl http://127.0.0.1:8000/health
# Expect: {"status":"healthy","version":"...","database":"connected","redis":"connected"}

curl http://<vm-ip>/docs   # Swagger UI
```

Try logging in with the bootstrap admin credentials:
```bash
curl -X POST http://<vm-ip>/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@yourdomain.com","password":"<password>"}'
```

---

## 4. `db_admin/` (local only)

The Flask admin panel in `db_admin/` is a developer convenience for browsing and editing rows directly. It is **NOT** deployed to the public VPS. Run it locally:

```bash
cd db_admin
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # point to the same DATABASE_URL / REDIS_URL
python app.py          # http://localhost:5000 (login: ADMIN_ROOT_USERNAME / PASSWORD)
```

---

## 5. Front-end on Vercel (future)

When the front-end code is ready inside `front_end/`:

1. Push to GitHub (already in this repo).
2. In Vercel dashboard: **Add New → Project → Import Git Repository**.
3. Set **Root Directory** to `front_end`.
4. Framework Preset: Vercel auto-detects (Next.js / Vite / etc.).
5. Add environment variables:
   - `NEXT_PUBLIC_API_URL` = public URL of the back-end (e.g. `https://api.yourdomain.com`).
6. Deploy. Vercel gives you a `https://<project>.vercel.app` URL immediately.

Subsequent pushes to `main` automatically trigger a new Vercel deployment.

---

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL` | `DATABASE_URL` is malformed. Ensure it is a single line starting with `postgresql://` or `postgresql+asyncpg://`. |
| `Redis connection refused` | Check `REDIS_URL` is `rediss://...` (TLS) and your IP is allowed in the Upstash dashboard. |
| `OpenRouter 401 / 402` | Verify `OPENROUTER_API_KEY` and that the chosen model is still free. |
| AI tool returns `SQL chứa từ khóa bị cấm` | The model tried to write DML/DDL. The execute_query tool only accepts `SELECT` / `WITH`. |
| `502 Bad Gateway` from Nginx | `sudo journalctl -u steam-api -n 50` to inspect the service logs. |

---

## 7. Updating the project

```powershell
# On your dev machine
git add .
git commit -m "describe your change"
git push origin main

# On the VPS (without Docker)
ssh <user>@<vm-ip>
cd /opt/steam-game && git pull
cd back_end && source .venv/bin/activate
pip install -r requirements.txt   # only when requirements changed
sudo systemctl restart steam-api

# On the VPS (with Docker)
cd /opt/steam-game && git pull
cd back_end && docker build -t steam-api:latest . && docker compose up -d