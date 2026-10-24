# Active Systems & Pipelines
_Moved from MEMORY.md 2026-10-21 by {{PROVISIONING_AGENT}}._

## Active Systems & Pipelines

_Source of truth for cron schedules: `crontab -l` + `openclaw cron list`. Scripts at `scripts/` and `projects/scripts/outbound-engine/`._

| System | Script/Cron | Status |
|--------|-------------|--------|
| Clay outbound dispatch | `simple_dispatch.py` | Working (25 dispatched Jul 31); **DRY-RUN — needs Jason go** |
| Territory dispatch | `territory_dispatch.py` | Mon-Fri 13:07 UTC — **DRY-RUN** (needs Jason go) |
| Company discovery | `run_daily_discovery.sh` | **DISABLED 2026-07-08** |
| Signal scanner | `run_signal_scanner.sh` | **RE-ENABLED 2026-09-15**; full seed list rotation |
| Reply monitor | `run_reply_monitor.sh` | Every 2h |
| Meeting CRM listener | `meeting-crm-listener.py` | Every 30min |
| Post-call briefs | `post-call-brief-nightly.sh` | Daily 02:00 UTC |
| Pre-call briefs | `meeting-precall-brief.py` | 08:00 + 18:00 UTC |
| Cron health monitor | `cron-health-monitor.sh` | Every 4h |
| {{AE_1}} prospect follow-up | `ae-prospect-followup.py` | Every 4h |
| Demo call reviewer | `demo-call-reviewer.py` | Fri 15:00 UTC |
| Calendar activity | `calendar-activity-monitor/` | Fri 7:45 AM CT |
| EOD sweep | `eod-sweep.py` | 23:30 UTC |
| Nightly doc curation | OpenClaw cron `76f7ed21` | 00:11 UTC |
| Daily GTM report | OpenClaw cron `c8f2087b` | 8:07 AM CT (#gtm-bizdev) |
| Weekly forecast AEs | OpenClaw cron `616ba130` | Thu 7 AM PT |
| Weekly forecast {{AE_1}} | OpenClaw cron `844eb3e3` | Fri 7 AM CT |
| Weekly forecast {{SALES_LEADER}} | OpenClaw cron `9cba19f7` | Fri 7 AM CT |
| Forecast daily pull | OpenClaw cron `d8ee4ea1` | 4 AM PT → {{REVOPS_1}} DM |
| Feedback loop + optimizer | `feedback_loop.sh` / `auto_copy_optimizer.sh` | Fri 14:00 / 15:30 UTC |
| Perf sync | `daily_perf_sync.sh` | Mon-Fri 06:00 UTC |
| LinkedIn Radar | `linkedin_radar.py` | `29 * * * *` |
| Gmail Triage | `gmail_triage.py` | `41 * * * *` |
| Lemlist signal trigger | `lemlist_signal_call_trigger.py` | `4-49/15 * * * *` |
| Webhook stack | `webhook_stack.sh` | System crontab every 15 min |
| Stack audit | `stack_audit.py` | 1st/15th 09:00 UTC |
| Event attendee scan | `event-attendee-scan.py` | 8:13 AM PT (max 5/day) |
| {{AE_4}} news refresh | `scripts/matt-tracker-news-weekly-append.py` | Weekly (cron) |
| Entity resolution | TypeSafe dedup | Sun 03:19 UTC |

**Clay campaigns**: WB1 (0000000), WB3 (0000000), WB4 (0000000), A/B WB1 (0000000), A/B WB4 (0000000), A/B WB3 (0000000), Champions (0000000, 0000000), Palantir (0000000). All ACTIVE.
**Mega campaign**: LinkedIn + AI4 + Pipeline (0000000). ACTIVE (2,090 leads).
**Seed list**: 2,428 companies (624 eligible after suppression).
**GTM vault**: `gtm-vault/` — 10 verticals, angle library, objection patterns.
