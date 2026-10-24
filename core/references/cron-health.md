# Cron Health Monitoring (PERMANENT — Jul 2 incident, extended Jul 30)

**Every daily session must verify ALL active crons ran in the previous 24 hours.**
**Automated monitor: `scripts/cron-health-monitor.sh` runs every 4h and DMs Jason Polanco (SLACK_ID) on any silent cron.**

Active crons to check:
- Post-call brief nightly (02:00 UTC) — `post-call-brief-nightly.log`
- Pre-call brief (08:00 + 18:00 UTC) — `projects/scripts/meeting-precall-brief.log` ← RESTORED 2026-07-30 after 6-week gap
- GitHub auth refresh (every 50 min) — `gh auth status`
- Linear token refresh (every 20h)
- Demo call review (Fri 15:00 UTC)
- {{AE_1}} prospect follow-up (every 4h) — `ae-prospect-followup.log`
- Reply monitor (every 2h) — `run_reply_monitor.sh`
- Meeting CRM listener (every 30min) — `meeting-crm-listener.log`
- Cron health monitor (every 4h) — `logs/cron-health-monitor.log`
- Workspace sync to GitHub (daily 03:17 UTC) — `scripts/logs/workspace-sync.log` — pushes allowlisted core files (AGENTS/SOUL/TOOLS/IDENTITY/USER/HEARTBEAT/MEMORY) to `gtm-agent/` in example-org/openclaw-workspaces per the repo README sync model (push-only, allowlist-only; memory/, skills/, scripts/, account-knowledge/ excluded). Added 2026-10-13 after {{ADMIN_1}} found the original nightly backup cron was lost in the 2026-06-18 crontab wipe and never restored.
- Shadow AI inbound queue drain (every 2 min, `2-59/2 * * * *`) — `output/shadowai-inbound-hook.log` — runs `run_shadowai_inbound_hook.sh`, drains `output/shadowai-inbound-queue/` into Lemlist paused campaigns. Added 2026-10-20.
- Shadow AI inbound HubSpot poller (every 5 min, `1-56/5 * * * *`) — `output/shadowai-inbound-poller.log` — runs `shadowai_inbound_poller.py`, finds new Shadow AI form converts and enqueues them. Added 2026-10-20.

_Disabled (Jul 8 pipeline rebuild): volume dispatch, company discovery. simple_dispatch.py is now live (25 dispatched 2026-07-31) but cron wiring broken (wrong path) + vertical routing broken (all go to WB4, show "?"). Signal scanner still disabled — re-enable to resume new account discovery._

**No silent failures rule (Jason Polanco, 2026-07-30, PERMANENT):** Any cron that stops running must immediately trigger a DM to Jason. Do NOT wait for Jason to discover it. The automated monitor handles this, but daily sessions must also verify. When a cron is added, immediately add it to `cron-health-monitor.sh` AND the list above.

If ANY cron produced no log output in 24+ hours → immediate fix. "Transcript pending" is not a permanent skip — systems must retry.

## No Silent Failures (Jason, 2026-06-17, PERMANENT)
All background processes must:
1. Run truly detached (`nohup`, no `timeout` wrapper)
2. Write output atomically (`.tmp` + rename)
3. Log `COMPLETED` or `FAILED` explicitly
4. Verify output before reporting (file exists, non-empty, expected count, completion line)
5. Monitor actively for jobs >5 min
6. Report failures immediately

Daily cron health check: every weekday, first session checks previous day's logs for errors. If `Traceback`, `ImportError`, `FAILED`, or 0 output for >1 day → fix immediately and alert Jason.

## Cron Scheduling — Always Jitter
Never schedule at round times (`:00`, `:15`, `:30`, `:45`). Use offsets like `:07`, `:11`, `:17`, `:22`, `:23`.

**Every cron with `announce` delivery MUST specify an explicit target channel.** Without it, OpenClaw resolves dynamically to the last main session — silently lands in random DMs. Always set the `--to` target (e.g., `SLACK_ID` for #gtm-agent, `SLACK_ID` for #outbound-email-engine). (Adopted from {{OPS_AGENT}}, 2026-07-17.)
