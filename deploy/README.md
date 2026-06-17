# Auto-sync from GitHub to VPS

These files let the VPS pull the latest back-end code from GitHub every minute, **excluding** `db_admin/` (local-only Flask panel) and `front_end/` (deployed on Vercel). This keeps the free-tier VM lightweight and avoids accidentally exposing the admin panel.

## Files

| File | Purpose |
|---|---|
| `vps_sync.sh` | Bash script: `git pull` into a staging dir, then `rsync` to the live dir (excluding `db_admin/` and `front_end/`), then `systemctl restart steam-api`. |
| `steam-sync.service` | systemd unit that runs `vps_sync.sh` as a one-shot task. |
| `steam-sync.timer` | systemd timer that triggers the service every 60 seconds. |

## One-time setup on the VPS

```bash
# 1) Install rsync (usually pre-installed, but just in case)
sudo apt update && sudo apt install -y rsync

# 2) Clone the repo into a "staging" directory (full clone, includes db_admin + front_end)
sudo mkdir -p /opt
sudo git clone https://github.com/<owner>/Steam-Game-Data-Demo.git /opt/steam-game-staging
sudo chown -R $USER:$USER /opt/steam-game-staging

# 3) Create the "live" directory (the rsync target - this is what the API runs from)
sudo mkdir -p /opt/steam-game
sudo chown -R www-data:www-data /opt/steam-game

# 4) Copy the sync script and make it executable
sudo cp /opt/steam-game-staging/deploy/vps_sync.sh /opt/steam-game/deploy/vps_sync.sh
sudo chmod +x /opt/steam-game/deploy/vps_sync.sh

# 5) Run it once to populate /opt/steam-game (excluding db_admin + front_end)
/opt/steam-game/deploy/vps_sync.sh

# 6) Install the systemd service + timer
sudo cp /opt/steam-game-staging/deploy/steam-sync.service /etc/systemd/system/steam-sync.service
sudo cp /opt/steam-game-staging/deploy/steam-sync.timer   /etc/systemd/system/steam-sync.timer
sudo systemctl daemon-reload
sudo systemctl enable --now steam-sync.timer

# 7) Verify
systemctl list-timers | grep steam-sync
sudo systemctl status steam-sync.service
tail -f /var/log/steam-sync.log
```

## Manual sync

If you do not want the timer, just run the script manually after each `git push`:

```bash
ssh <user>@<vps-ip>
/opt/steam-game/deploy/vps_sync.sh
```

## How it works

```
GitHub repo (full content)
       │
       ▼  git fetch + reset --hard origin/main
/opt/steam-game-staging/   (full clone: back_end + db_admin + front_end + ...)
       │
       ▼  rsync -a --delete --exclude=db_admin/ --exclude=front_end/
/opt/steam-game/            (only back_end + docs + deploy scripts)
       │
       ▼  systemctl restart steam-api
FastAPI service (uvicorn)
```

## Overriding defaults

All paths can be customised via environment variables:

```bash
STAGING_DIR=/srv/staging \
LIVE_DIR=/srv/live \
GIT_BRANCH=develop \
WATCH_INTERVAL=120 \
./vps_sync.sh --watch
```

## Uninstalling the auto-sync

```bash
sudo systemctl disable --now steam-sync.timer
sudo systemctl stop steam-sync.service
sudo rm /etc/systemd/system/steam-sync.service /etc/systemd/system/steam-sync.timer
sudo systemctl daemon-reload