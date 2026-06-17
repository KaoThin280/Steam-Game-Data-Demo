#!/usr/bin/env bash
# ============================================================
# vps_sync.sh
# ------------------------------------------------------------
# Sync code from GitHub to the VPS, EXCLUDING:
#   - db_admin/   (local-only Flask panel)
#   - front_end/  (deployed on Vercel, not on the VPS)
#
# Usage:
#   ./vps_sync.sh                 # one-shot sync
#   ./vps_sync.sh --watch         # loop every N seconds (default 60)
#
# First-time setup on the VPS:
#   1) Clone the repo once to a "staging" directory:
#        cd /opt
#        sudo git clone https://github.com/<owner>/Steam-Game-Data-Demo.git steam-game-staging
#        sudo chown -R $USER:$USER /opt/steam-game-staging
#
#   2) Initialise the "live" directory (rsync target):
#        sudo mkdir -p /opt/steam-game
#        sudo chown $USER:$USER /opt/steam-game
#
#   3) Make sure rsync is installed:
#        sudo apt install -y rsync
#
#   4) Run this script once to populate /opt/steam-game.
#
# Optional: install a systemd timer or cronjob for auto-sync.
# ============================================================
set -euo pipefail

# ---------- Configuration ----------
STAGING_DIR="${STAGING_DIR:-/opt/steam-game-staging}"   # full clone from GitHub
LIVE_DIR="${LIVE_DIR:-/opt/steam-game}"                  # runtime copy on the VPS
GIT_BRANCH="${GIT_BRANCH:-main}"
WATCH_INTERVAL="${WATCH_INTERVAL:-60}"                   # seconds (when --watch)
EXCLUDE_PATTERN="--exclude=db_admin/ --exclude=front_end/"

# The LIVE_DIR is owned by www-data. rsync needs root to write into it.
SUDO=""
if [[ $EUID -ne 0 ]]; then
    SUDO="sudo"
fi

# ---------- Functions ----------
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

sync_once() {
    log "Pulling latest from origin/$GIT_BRANCH..."
    git -C "$STAGING_DIR" fetch origin "$GIT_BRANCH" --prune
    git -C "$STAGING_DIR" reset --hard "origin/$GIT_BRANCH"

    log "Syncing to $LIVE_DIR (excluding db_admin/, front_end/)..."
    # -a  : archive (recursive, preserves perms, symlinks, times)
    # --delete : remove files in LIVE that no longer exist in STAGING
    # --exclude : drop db_admin and front_end
    # We MUST run rsync as root (or with sudo) because $LIVE_DIR is owned by www-data.
    $SUDO rsync -a --delete $EXCLUDE_PATTERN \
        "$STAGING_DIR/" "$LIVE_DIR/"

    log "Restarting steam-api service..."
    if $SUDO systemctl list-unit-files | grep -q '^steam-api.service'; then
        $SUDO systemctl restart steam-api || log "WARN: systemctl restart failed"
    else
        log "INFO: steam-api.service not found, skipping restart"
    fi

    # Re-install requirements only if requirements.txt changed
    if ! $SUDO cmp -s "$STAGING_DIR/back_end/requirements.txt" "$LIVE_DIR/back_end/requirements.txt" 2>/dev/null; then
        log "requirements.txt changed, re-installing..."
        $SUDO -u www-data "$LIVE_DIR/back_end/.venv/bin/pip" install \
            -r "$LIVE_DIR/back_end/requirements.txt" \
            || log "WARN: pip install failed"
    fi

    log "Sync done."
}

# ---------- Main ----------
case "${1:-}" in
    --watch|-w)
        log "Watching for changes every ${WATCH_INTERVAL}s (Ctrl+C to stop)..."
        while true; do
            sync_once || log "ERROR during sync (will retry)"
            sleep "$WATCH_INTERVAL"
        done
        ;;
    --help|-h)
        sed -n '2,30p' "$0"
        ;;
    *)
        sync_once
        ;;
esac