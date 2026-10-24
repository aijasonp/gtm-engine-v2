# Smartlead API Rules (PERMANENT)

## Sequences Endpoint is REPLACE (Jun 29 incident)
POST `/campaigns/{id}/sequences` **REPLACES the entire list.** Always send ALL sequences in a single POST call. Never send individual sequence updates — last call wins, everything else is wiped.

## Email Formatting (Jason, 2026-07-09)
Every campaign: `send_as_plain_text: false` + `<br><br>` between paragraphs. Gmail strips CSS properties like `margin-block`, so styled `<p>` tags render with zero spacing. Only `<br><br>` reliably creates paragraph breaks across all email clients. Never use `<p>` tags. Never use `send_as_plain_text: true` (strips all HTML). Full spec in `rules/smartlead-email-formatting.md`.

### Salutation Formatting (Jason, 2026-07-09)
**Salutation ALWAYS gets its own line.** Format:
```
{{first_name}},<br><br>Body text starts here...
```
NEVER run the salutation into the first sentence (e.g. `{{first_name}}, 50 banks just discovered...`). The name must stand alone, followed by `<br><br>`, then the body paragraph starts with a capital letter.

## Campaign Policy
Before creating or uploading any campaign content:
1. ONLY use `{{variable_name}}` merge tags — NO Jinja2, Liquid, or template logic EVER
2. Run pre-flight checklist from `rules/smartlead-email-formatting.md`
3. Verify all leads have referenced fields populated
4. **MANDATORY: Send test emails to rep@example.com for EVERY sequence step via `POST /campaigns/{id}/send-test-email` BEFORE activating. Jason must confirm. No exceptions.**

## {{personalization_line}} REMOVED (Jason, 2026-06-30)
**Never use `{{personalization_line}}`** — Clay AI fills it with fabricated slop we don't control.

## HubSpot Activity Sync + Webhook Registration (PERMANENT — Oct 9 2026 incident)
Every Smartlead reply must land on the HubSpot contact timeline as an activity NOTE (live path: `smartlead_webhook_receiver.sync_smartlead_reply_to_hubspot`; backfill: `smartlead_hubspot_reply_backfill.py`). If a rep reports activities missing from HubSpot, check webhooks FIRST:

1. **Smartlead campaign webhooks die silently on tunnel restart.** Campaign webhooks point at trycloudflare quick-tunnel URLs, which change every time cloudflared restarts. Instead of assuming delivery, verify: `GET /campaigns/{id}/webhooks?api_key=` and compare the URL to the LIVE tunnel (`ps aux | grep cloudflared`; curl the /healthz). After ANY tunnel restart or new campaign creation, re-register webhooks on every ACTIVE campaign via `register_smartlead_webhooks.py --campaign-ids ... --url <current-tunnel>/smartlead`.
2. **Backfill path for missed replies:** `python3 projects/scripts/outbound-engine/smartlead_hubspot_reply_backfill.py --dry-run` then `--commit`. It dedupes against live-webhook state, so it is always safe to rerun. Never hand-edit notes for this.
3. **API gotchas:** `leads-export` returns CSV (not JSON — don't call `.json()`); message-history reply entries are `type=REPLY` (not REPLIED); webhook timestamps use `+00:00`, history API uses `.000Z` — normalize before dedupe keys.
4. **Durable fix still open:** quick tunnels are ephemeral. Move to a named Cloudflare tunnel (fixed hostname) or Tailscale Funnel so webhook URLs survive restarts. Until then, post-restart webhook re-registration is mandatory.
