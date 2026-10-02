#!/usr/bin/env bash
# Daily sync for Indiana appellate opinions from CourtListener.
# Run via cron: 0 6 * * * /Users/danielle/projects/indiana-law/scripts/daily_sync.sh
#
# Reads COURTLISTENER_API_KEY from ~/.indiana-law-env if it exists.

set -euo pipefail

PROJECT="$HOME/projects/indiana-law"
VENV="$PROJECT/.venv"
LOG_DIR="$PROJECT/logs"
DATE=$(date '+%Y-%m-%d')
LOG="$LOG_DIR/sync-opinions-${DATE}.log"

mkdir -p "$LOG_DIR"

# Load credentials if present
[[ -f "$HOME/.indiana-law-env" ]] && source "$HOME/.indiana-law-env"

echo "[$(date '+%H:%M:%S')] Starting opinion sync..." >> "$LOG"

"$VENV/bin/python" "$PROJECT/scripts/sync_opinions.py" >> "$LOG" 2>&1
EXIT=$?

if [[ $EXIT -eq 0 ]]; then
    echo "[$(date '+%H:%M:%S')] Sync complete." >> "$LOG"
    # Telegram notify (uses farm worker-04 like other scripts)
    ssh transcribe@192.168.68.104 \
        "~/scripts/telegram-notify.sh 'Indiana law sync complete ${DATE}.'" \
        2>/dev/null || true
else
    echo "[$(date '+%H:%M:%S')] Sync FAILED (exit $EXIT)." >> "$LOG"
    ssh transcribe@192.168.68.104 \
        "~/scripts/telegram-notify.sh 'ALERT: Indiana law sync failed ${DATE}. Check logs.'" \
        2>/dev/null || true
fi

exit $EXIT
