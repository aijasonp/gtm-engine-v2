#!/bin/bash
# Watchdog: restart enrichment if it died before completing.
# Runs every 2 min via crontab. Self-removes when .done marker appears.

BASE="$HOME/.openclaw/workspace/output"
DONE="$BASE/.contacts-enriched.done"
SCRIPT="$HOME/.openclaw/workspace/scripts/contacts-enrichment/enrich_contacts_free.py"
LOG="$BASE/enrich-run.log"
CRON_TAG="contacts-enrich-watchdog"

if [ -f "$DONE" ]; then
    # Job finished — remove this watchdog from crontab
    crontab -l 2>/dev/null | grep -v "$CRON_TAG" | crontab -
    exit 0
fi

if ! pgrep -f "enrich_contacts_free.py" > /dev/null; then
    echo "[$(date -u +%FT%TZ)] watchdog: enrichment not running, restarting (resume from checkpoint)" >> "$LOG"
    cd $HOME/.openclaw/workspace
    nohup python3 "$SCRIPT" >> "$LOG" 2>&1 &
fi
