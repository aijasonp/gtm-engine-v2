# Lemlist Event Campaign System (Jason, 2026-09-22)

The standard post-event follow-up machine. One master template, cloned per event, with scheduled calls + signal-triggered calls on top.

## Components

| Piece | Path | What it does |
|---|---|---|
| Master template | `scripts/outbound-engine/sequences/event-post-event-30day-v1.json` | 30-day cadence: 7 emails + 7 paired call steps (call 1 day after each email) |
| Campaign builder | `scripts/outbound-engine/lemlist_campaign_builder.py` | Builds a Lemlist campaign from the template (email/phone/manual step types) |
| Signal trigger | `scripts/outbound-engine/lemlist_signal_call_trigger.py` | Polls activities every 15 min, creates a Lemlist phone task on hot signals |
| Config | `scripts/outbound-engine/config/outbound-config.yaml` (`lemlist.signal_call_trigger`, `lemlist.event_template`) | Routing, Aircall flag, sender user IDs |
| Cron | `4-49/15 * * * * run_lemlist_signal_call_trigger.sh` | Signal poll every 15 min (jittered) |

## Cadence (31 days, 14 touches)

- Email days: 0, 3, 7, 12, 18, 25, 30
- Call days: 1, 4, 8, 13, 19, 26, 31 (each 1 day after its email)
- Never shorter than 30 days. Every email gets a paired call.

## Signal-triggered calls (in addition to scheduled calls)

Signals that create a phone task for the owning BDR, due within 2h (weekend-safe):
`emailsOpened`, `emailsClicked`, `linkedinInviteAccepted`, `linkedinOpened`, `linkedinReplied`.

Dedupe: one task per lead per signal type per 24h. Task = Lemlist `phone` task, priority 2, assigned to the owner resolved from `signal_call_trigger.routing` (default {{AE_2}}; keyword `east`/`jake` routes to {{AE_5}}). Slack alert fires to the reply webhook channel. When `aircall_enabled: true` and creds exist, the trigger also pushes the lead's number into the BDR's Aircall dialer.

## Per-event launch checklist

1. Clone the template JSON, set `campaign_name` + swap `{{event_name}}`.
2. Write per-lead `event_hook` (1 sentence, agent-authored, anti-slop scanned).
3. Build: `python3 lemlist_campaign_builder.py --template <clone>.json --sender-user-id <usr>` (senders: jason `usr_REDACTED`, agent `usr_REDACTED`, jake `usr_REDACTED`).
4. Load leads within 24h of receiving the list (`lemlist_lead_loader.py`, same suppression gates as Smartlead).
5. Send test emails for EVERY step to rep@example.com; Jason approves copy before activation (per `references/outbound-copy.md`).
6. Start campaign. Signal trigger picks it up automatically on the next 15-min poll.

## Open dependencies

- **Aircall**: license pending. `aircall_enabled: false` until creds (`AIRCALL_API_ID`, `AIRCALL_API_TOKEN`, per-BDR `aircall_user_id`) land in `~/.openclaw/.env` + config.
- **{{AE_2}} LinkedIn**: CONNECTED 2026-09-23 (confirmed by Jason; all 5 channels live on his sender: email, phone, linkedinVisit, linkedinInvite, linkedinSend).
- **Warm-up**: all 11 mailboxes lemwarm-active as of 2026-09-22; first cold sends no earlier than ~Oct 6.

## Black Hat campaign state (2026-09-23 cleanup)

LIVE campaigns (all paused, senders assigned, error-free):
- `cam_DBKkzYJJDfLS2Gi6Q` — Black Hat Re-Engagement - {{AE_2}} (Day 3 Entry) v2 — 72 leads, sender {{AE_2}} (all 5 channels)
- `cam_2jkFvGwMLdLpHp2vW` — Black Hat Re-Engagement - {{AE_5}} (Day 3 Entry) v2 — 66 leads, sender {{AE_5}}
- `cam_JnPskrrzmL4qaWCZZ` — Black Hat Re-Engagement - {{AE_5}} (Day 10 Entry) v2 — 7 leads, sender {{AE_5}}

ARCHIVED (renamed `zzz-ARCHIVED ...`, still paused — Lemlist API has no campaign DELETE):
- `cam_6rEdmmxdW8KFtNvxm` ({{AE_2}} D3 v1 — 72 leads migrated to v2 on 2026-09-23)
- `cam_W4AvAqomRv3ys2A5G` ({{AE_5}} D3 v1 — same 66 leads as v2)
- `cam_zoXWqQngD5oc3MJ2M` ({{AE_5}} D10 v1 — same 7 leads as v2)
- `cam_WGPgoCLXnxkzo7npK` (PROBE-ANDREW-CH, 0 leads)
- `cam_N3E2nJSFTGDccfzs2` (PROBE-DELETE-ME conditional test)

Workflow note: the v2 campaigns are the canonical structure. Linear spine (email d0 → call d1 → email d3 → call d4 …) + `conditional` wait-until-opened branches that route openers into LinkedIn touch sub-sequences (level-1: linkedinVisit → linkedinInvite → linkedinSend). That IS Lemlist's recommended multichannel pattern (help.lemlist.com articles 0000000/0000000) — a straight line with zero branching cannot react to opens. All 3 v2s share identical step structure; D10 variants intentionally start at email 2 (later entry point).

Migration pattern that works: pull leads from source campaign, fetch each `/contacts/{contactId}`, `add_lead` to dest with `deduplicate=True`, on 409 retry with `deduplicate=False` (same pattern as `lemlist_lead_loader.upload_leads`).
