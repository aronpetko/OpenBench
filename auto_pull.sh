#!/bin/bash

LOG_FILE="/var/ob_auto_pull.log"
REPO_DIR="/var/OpenBench"
SERVICE_NAME="openbench"

echo "[$(date)] Starting auto-pull check..." >> "$LOG_FILE"

# Make sure we're in the right directory
cd "$REPO_DIR" || {
    echo "[$(date)] ERROR: Failed to cd into $REPO_DIR" >> "$LOG_FILE"
    exit 1
}

git fetch origin >> "$LOG_FILE" 2>&1

UPSTREAM="origin/master"
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse "$UPSTREAM")
BASE=$(git merge-base @ "$UPSTREAM")

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "[$(date)] Repo is up-to-date." >> "$LOG_FILE"
elif [ "$LOCAL" = "$BASE" ]; then
    echo "[$(date)] Repo is behind. Pulling and restarting service..." >> "$LOG_FILE"
    git pull >> "$LOG_FILE" 2>&1
    sudo systemctl restart "$SERVICE_NAME"
    echo "[$(date)] Service restarted." >> "$LOG_FILE"
elif [ "$REMOTE" = "$BASE" ]; then
    echo "[$(date)] Local changes not pushed. Skipping pull." >> "$LOG_FILE"
else
    echo "[$(date)] Repo has diverged. Manual merge needed." >> "$LOG_FILE"
fi

echo "[$(date)] Auto-pull check complete." >> "$LOG_FILE"

