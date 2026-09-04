# Deploying on a GCP Free Tier VM

## Is Docker Compose suitable?

It is technically supported, but it is not the best default for an `e2-micro`. Google currently describes this machine as shared-core with 1 GB RAM, while the Free Tier allowance is one eligible `e2-micro` in selected US regions plus 30 GB-month of standard persistent disk.

This project needs two long-lived Python processes (API and MCP). The image also contains data-analysis dependencies, and Docker/build overhead competes with the OS for the same 1 GB. Supabase, Upstash and E2B are external, so a low-traffic demo can fit, but dependency/image builds and concurrent analysis are likely pressure points.

Recommended order:

1. **Free Tier:** Python virtual environment + two `systemd` services.
2. **Compose on e2-micro:** acceptable for a demo if the image is built in CI, one worker is used per container, memory is monitored and swap is available.
3. **Production/container comfort:** move to a VM with at least 2 GB RAM.

Official references: [Google Cloud Free Tier](https://docs.cloud.google.com/free/docs/free-cloud-features) and [E2 machine types](https://docs.cloud.google.com/compute/docs/general-purpose-machines#e2_machine_types).

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

The production `.env` must contain:

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

The existing GitHub deployment action must restart **both** units, MCP first, and health-check `8001` before restarting API. A workflow that starts only `app.main:app` no longer deploys the current architecture correctly.

## Optional Docker Compose deployment

From `back_end/`:

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

## Post-deploy checks

1. API startup logs confirm PostgreSQL, read-only PostgreSQL, MCP discovery and Redis; `/health` confirms the main database and Redis remain connected.
2. Login works and `/api/v1/auth/me` returns the expected roles.
3. Create a session, ask for total games and request a bar chart.
4. Confirm tool events exist and the chart reloads from session history.
5. Restart `steam-api` during a queued/running test and verify recovery.
6. Confirm port `8001` is not reachable from the internet.
