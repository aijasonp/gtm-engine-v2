#!/bin/bash
# Cron Health Monitor — alerts Jason Polanco via Slack DM when crons go silent
# Runs every 4 hours via crontab
# Checks: log file modification time vs expected max interval

SLACK_BOT_TOKEN=$(grep SLACK_BOT_TOKEN $HOME/.openclaw/.env | cut -d= -f2)
JASON_SLACK_ID="SLACK_ID"
TEAMMATE_SLACK_ID="SLACK_ID"

alert() {
    local msg="$1"
    curl -s -X POST "https://slack.com/api/chat.postMessage" \
        -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"channel\": \"$JASON_SLACK_ID\", \"text\": \"$msg\"}" > /dev/null
}

# Infra/ops failures (workspace backup, monitor itself) go to {{ADMIN_1}}, not Jason
# ({{ADMIN_1}}, 2026-10-13: "alert me if it's silent, not Jason")
alert_admin() {
    local msg="$1"
    curl -s -X POST "https://slack.com/api/chat.postMessage" \
        -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"channel\": \"$TEAMMATE_SLACK_ID\", \"text\": \"$msg\"}" > /dev/null
}

now=$(date +%s)
failures=()
admin_failures=()

check_log() {
    local name="$1"
    local log_file="$2"
    local max_age_hours="$3"

    if [ ! -f "$log_file" ]; then
        failures+=("❌ *${name}*: log file missing (${log_file})")
        return
    fi

    local mtime=$(stat -c %Y "$log_file" 2>/dev/null)
    local age_hours=$(( (now - mtime) / 3600 ))

    if [ "$age_hours" -gt "$max_age_hours" ]; then
        failures+=("❌ *${name}*: last ran ${age_hours}h ago (max: ${max_age_hours}h) — log: ${log_file}")
    fi
}

# Check each monitored cron [name, log, max_age_hours]
check_log "Post-Call Brief Nightly" \
    "$HOME/.openclaw/workspace/scripts/logs/post-call-brief-nightly.log" 26

check_log "Pre-Call Brief" \
    "$HOME/projects/scripts/meeting-precall-brief.log" 20

check_log "Reply Monitor (2h)" \
    "$HOME/.openclaw/workspace/scripts/outbound-engine/output/reply-monitor.log" 3

check_log "Lemlist Reply Monitor (2h)" \
    "$HOME/.openclaw/workspace/scripts/outbound-engine/output/lemlist-reply-monitor.log" 3

check_log "Instantly Reply Monitor (2h)" \
    "$HOME/.openclaw/workspace/scripts/outbound-engine/output/instantly-reply-monitor.log" 3

check_log "{{AE_1}} Prospect Follow-Up (4h)" \
    "$HOME/.openclaw/workspace/scripts/logs/ae-prospect-followup.log" 5

check_log "Meeting CRM Listener (30min)" \
    "$HOME/.openclaw/workspace/scripts/meeting-crm-listener.log" 2

check_log "GitHub Auth Refresh (50min)" \
    "$HOME/.config/github-app/gh-auth-refresh.log" 2

check_log "Linear Token Refresh (20h)" \
    "$HOME/.openclaw/linear-refresh.log" 22

check_log "Demo Call Review (weekly Fri)" \
    "$HOME/.openclaw/workspace/logs/demo-call-review.log" 170

check_log "{{AE_4}} Tracker HubSpot Sync (daily 8am UTC)" \
    "$HOME/.openclaw/workspace/logs/ae-hubspot-sync.log" 26

check_log "{{SDR_1}} Monday Pipeline Update (weekly Mon 8am CT)" \
    "$HOME/.openclaw/workspace/scripts/logs/ae-pipeline-update.log" 170

# Workspace sync failures alert {{ADMIN_1}} only, not Jason ({{ADMIN_1}}, 2026-10-13)
ws_log="$HOME/.openclaw/workspace/scripts/logs/workspace-sync.log"
if [ ! -f "$ws_log" ]; then
    admin_failures+=("❌ *Workspace Sync to GitHub*: log file missing (${ws_log})")
else
    ws_age_hours=$(( (now - $(stat -c %Y "$ws_log" 2>/dev/null || echo 0)) / 3600 ))
    if [ "$ws_age_hours" -gt 26 ]; then
        admin_failures+=("❌ *Workspace Sync to GitHub*: last ran ${ws_age_hours}h ago (max: 26h)")
    fi
fi

# Weekly Forecast Call skill ({{SALES_LEADER}}, 2026-09-18) - weekly cadence, 170h max age
FORECAST_DIR="$HOME/.openclaw/workspace/skills/forecast-call/logs"
check_log "Forecast Wed Reminder (weekly Wed 9am PT)" "$FORECAST_DIR/weekly-reminder.log" 170
check_log "Forecast Thu Call (weekly Thu 8am PT)" "$FORECAST_DIR/thursday-call.log" 170
check_log "Forecast Thu Nudge (weekly Thu 4pm PT)" "$FORECAST_DIR/thursday-nudge.log" 170
check_log "Forecast Fri Summary (weekly Fri 8am PT)" "$FORECAST_DIR/friday-summary.log" 170

check_log "Account Knowledge Pruner (weekly Sun)" \
    "$HOME/projects/scripts/outbound-engine/output/knowledge-pruner.log" 170

# Mon-Fri jobs: extend max age over weekends (Sat/Sun) so Friday runs don't false-positive
DOW=$(date -u +%u)  # 1=Mon .. 6=Sat, 7=Sun
if [ "$DOW" -ge 6 ]; then
    BDR_MAX_AGE=72  # Friday 12:00 UTC run -> up to 60h by Mon 00:00, pad to 72
else
    BDR_MAX_AGE=26
fi
check_log "BDR Morning Setup / Call Down List (Mon-Fri)" \
    "$HOME/projects/scripts/bdr-calldown.log" "$BDR_MAX_AGE"

check_log "Territory Dispatch (Mon-Fri 13:07 UTC)" \
    "$HOME/projects/scripts/outbound-engine/output/territory-dispatch.log" "$BDR_MAX_AGE"

check_log "Company Discovery (Mon-Fri 12:00 UTC)" \
    "$HOME/projects/scripts/outbound-engine/output/discovery.log" "$BDR_MAX_AGE"

# Smartlead webhook handling moved into unified_webhook_server.py on 2026-09-22
# (routes POST /smartlead -> smartlead_webhook_receiver.handle_event). The old
# standalone `smartlead_webhook_receiver.py server --port 8080` process no longer
# exists, so pgrep for it false-positives forever. Instead of a process check,
# hit the unified server's /healthz — it only responds when the server is up AND
# the smartlead module imported cleanly at startup. webhook_stack.sh watchdog
# (every 15 min) restarts the server on failure, so this alerts only when the
# watchdog ALSO failed to recover it.
if ! curl -sf -m 5 "http://127.0.0.1:8788/healthz" > /dev/null 2>&1; then
    failures+=("❌ *Unified Webhook Server*: not responding on :8788/healthz (Smartlead/Lemlist/Aircall events not being received)")
fi

# If failures found, DM Jason
if [ ${#failures[@]} -gt 0 ]; then
    msg="⚠️ *GTM agent Cron Health Alert* — silent crons detected:\n\n"
    for f in "${failures[@]}"; do
        msg="${msg}${f}\n"
    done
    msg="${msg}\nChecked at $(date -u '+%Y-%m-%d %H:%M UTC'). I'm investigating."
    alert "$msg"
fi

# Infra/ops failures (workspace sync) DM {{ADMIN_1}} instead
if [ ${#admin_failures[@]} -gt 0 ]; then
    bmsg="⚠️ *GTM agent Infra Alert* — silent job detected:\n\n"
    for f in "${admin_failures[@]}"; do
        bmsg="${bmsg}${f}\n"
    done
    bmsg="${bmsg}\nChecked at $(date -u '+%Y-%m-%d %H:%M UTC')."
    alert_admin "$bmsg"
fi

# Always write a heartbeat line so this monitor's own log mtime updates on every
# run (success = no output = no mtime change = monitor looks dead). This keeps
# the monitor self-observable and prevents silent-blindness.
echo "[cron-health-monitor] $(date -u '+%Y-%m-%d %H:%M:%S UTC') check complete: ${#failures[@]} failure(s)" >> "$(dirname "$0")/logs/cron-health-monitor.log"
