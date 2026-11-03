# Chạy API và MCP bằng systemd hoặc Compose

Đây là mẫu triển khai hai process để áp dụng thủ công, không phải mô tả systemd đang được workflow dùng. Workflow hiện tại dùng `nohup`; xem [deployment](deployment.md) trước khi chọn cơ chế quản lý process. Repository không chứng minh quota Free Tier, chi phí hoặc mức RAM tối thiểu. Đo startup/peak memory trên host thực tế; giữ PostgreSQL, Redis và E2B bên ngoài VPS theo cấu hình dự án.

## Recommended systemd deployment

Assume the repository is at `/home/APP_USER/Steam-Game-Data-Demo` and the virtual environment is `back_end/.venv`. Replace `APP_USER` in both units.

Create `/etc/systemd/system/steam-mcp.service`:

```ini
[Unit]
Description=Steam MCP tool server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=APP_USER
WorkingDirectory=/home/APP_USER/Steam-Game-Data-Demo/back_end
EnvironmentFile=/home/APP_USER/Steam-Game-Data-Demo/back_end/.env
ExecStart=/home/APP_USER/Steam-Game-Data-Demo/back_end/.venv/bin/python -m uvicorn app.mcp_server:app --host 127.0.0.1 --port 8001 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/steam-api.service`:

```ini
[Unit]
Description=Steam product API and agent runtime
After=network-online.target steam-mcp.service
Wants=network-online.target
Requires=steam-mcp.service

[Service]
Type=simple
User=APP_USER
WorkingDirectory=/home/APP_USER/Steam-Game-Data-Demo/back_end
EnvironmentFile=/home/APP_USER/Steam-Game-Data-Demo/back_end/.env
ExecStart=/home/APP_USER/Steam-Game-Data-Demo/back_end/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

In addition to DATABASE_URL, DATABASE_URL_READONLY, REDIS_URL, SECRET_KEY, OPENROUTER_API_KEY, model and explicit CORS origins described in [deployment](deployment.md), the production `.env` must contain:

```dotenv
DEBUG=False
ENABLE_LEGACY_AI=False
MCP_SERVER_URL=http://127.0.0.1:8001/mcp
MCP_SHARED_SECRET=<one random 32+ character value>
```

The same environment file is intentionally read by both processes so the secret matches. Protect it with `chmod 600` and never commit it.

Enable and verify:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now steam-mcp
curl --fail http://127.0.0.1:8001/health
sudo systemctl enable --now steam-api
curl --fail http://127.0.0.1:8000/health
sudo systemctl status steam-mcp steam-api
```

Configure Nginx and TLS to proxy the public hostname to `127.0.0.1:8000`. Do not proxy or open firewall port `8001`.

The checked-in GitHub action currently uses nohup, not these units. Before adopting systemd, adapt the workflow to restart both units, MCP first, and verify readiness. Do not run both process managers against the same ports.

## Optional Docker Compose deployment

From repository directory `back_end/`, using [docker-compose.agent.yml](../../back_end/docker-compose.agent.yml):

```bash
docker compose -f docker-compose.agent.yml build
docker compose -f docker-compose.agent.yml up -d
docker compose -f docker-compose.agent.yml ps
docker stats --no-stream
```

Prefer pulling an image built by GitHub Actions instead of compiling/installing dependencies on the e2-micro. Keep only port `8000` published; MCP should remain on the Compose network. Use Docker Compose resource limits only after measuring actual startup and peak usage; limits that are too low turn memory pressure into repeated OOM restarts.

Check the host before and after deployment:

```bash
free -h
df -h
docker stats --no-stream
```

A 1-2 GB swap file can reduce abrupt OOM failures, but it is disk-backed and does not make the VM faster. If the API and MCP regularly swap or restart, upgrade the VM rather than increasing timeouts.

The API health endpoint may return HTTP 200 with status degraded. Check its JSON fields, not only curl exit status.

## Post-deploy checks

1. API startup logs confirm PostgreSQL, read-only PostgreSQL, MCP discovery and Redis; `/health` confirms the main database and Redis remain connected.
2. Login works and `/api/v1/auth/me` returns the expected roles.
3. Create a session, ask for total games and request a bar chart.
4. Confirm tool events exist and the chart reloads from session history.
5. Restart `steam-api` during a queued/running test and verify recovery.
6. Confirm port `8001` is not reachable from the internet.
