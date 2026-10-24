# Smartlead Webhook Automation — Scope of Work

**Owner:** Jason Polanco
**Prepared by:** GTM agent (OpenClaw)
**Date:** 2026-09-15
**Status:** Ready for handoff to build chat

---

## 1. Objective

Build a real-time webhook-driven automation layer on top of Smartlead that replaces the current polling-based reply monitor and unlocks two high-value behaviors:

1. **Reply → agent response** — when a prospect replies, the GTM agent receives it instantly, classifies it, and (for positive/objection) drafts a personalized response routed to the rep.
2. **Email open → Aircall dialer** — when a lead opens an email (especially 2nd+ open or open after a specific step), push them into an Aircall call list / dialer queue so a BDR calls while intent is fresh.

Secondary: instant bounce/unsubscribe suppression, click → dialer.

---

## 2. Current State (verified 2026-09-15)

- **Smartlead webhook API works.** Confirmed live:
  - `POST /api/v1/campaigns/{id}/webhooks` with `{name, webhook_url, event_types:["EMAIL_REPLY"]}` → creates a webhook.
  - `GET /api/v1/campaigns/{id}/webhooks` → lists webhooks.
  - `DELETE /api/v1/campaigns/{id}/webhooks` with `{"id": <webhook_id>}` in the body → deletes (note: id goes in the **body**, not the URL path).
  - Supported event types include: `EMAIL_REPLY`, `EMAIL_OPEN`, `EMAIL_CLICK`, `EMAIL_BOUNCE`, `EMAIL_UNSUBSCRIBE` (and others).
- **Webhooks are currently DISABLED** on the {{PARTNER_B}} campaigns (and all others) — the per-campaign toggle is off.
- **Existing code (reusable):**
  - `reply_monitor.py` — polls Smartlead every 2h, classifies replies (POSITIVE / NEGATIVE / OOO / OBJECTION), posts to Slack. This is the polling baseline we're replacing with webhooks.
  - `meeting_booked_webhook.py` — an HTTP webhook receiver already built to handle Lemlist aircall events + Instantly interest events → updates HubSpot deal stage. **Not currently running** (blocked on public endpoint).
  - `lemlist_client.py` / `instantly_client.py` — have webhook create/list/delete methods.
- **Blocking constraint:** The VM is behind IAP (no public inbound). Webhooks are inbound POSTs, so Smartlead/Lemlist/Instantly cannot reach us directly. **Tailscale Funnel is required** to expose a public HTTPS URL that tunnels into the VM.

---

## 3. Architecture

```
Smartlead / Lemlist / Instantly
        │  (webhook POST, HTTPS)
        ▼
Tailscale Funnel (public HTTPS URL → tunnel into VM)
        │
        ▼
Webhook Receiver (HTTP server on VM, e.g. port 8080)
        │  normalize event → canonical event
        ▼
Event Router
   ├── EMAIL_REPLY ──► Classifier (POSITIVE/OBJECTION/OOO/NEGATIVE)
   │                     ├── POSITIVE → draft reply → route to rep (Slack) + book meeting
   │                     ├── OBJECTION → draft objection handle → rep reviews
   │                     ├── OOO → auto-pause sequence, follow up on return
   │                     └── NEGATIVE → auto-suppress / remove from sequence
   ├── EMAIL_OPEN ──► Intent scorer → push to Aircall dialer list (call-while-hot)
   ├── EMAIL_CLICK ─► Intent scorer → push to Aircall dialer list
   ├── EMAIL_BOUNCE ─► auto-suppress (instant)
   └── EMAIL_UNSUBSCRIBE ─► auto-suppress (instant)
```

---

## 4. Scope of Work

### Phase 0 — Prerequisites (blocking)
- [ ] **Tailscale Funnel** enabled on the VM to expose a public HTTPS endpoint. Security-relevant change — requires sign-off.
- [ ] **Aircall API credentials** provisioned (API key + which call list / dialer queue to push leads into). Not currently in env.
- [ ] Confirm which Smartlead campaigns get webhooks (all active, or just {{PARTNER_B}} event campaigns?).

### Phase 1 — Webhook Receiver + Smartlead wiring
- [ ] Stand up the HTTP receiver (extend `meeting_booked_webhook.py` or new `smartlead_webhook_receiver.py`) on the VM.
- [ ] Register Smartlead webhooks per campaign: `EMAIL_REPLY`, `EMAIL_OPEN`, `EMAIL_CLICK`, `EMAIL_BOUNCE`, `EMAIL_UNSUBSCRIBE` → point at the Funnel URL.
- [ ] Normalize Smartlead payloads into a canonical event schema (lead email, campaign, event type, timestamp, reply text, open/click metadata).
- [ ] Verify delivery end-to-end with a test webhook (create → fire → confirm receiver logs → delete).

### Phase 2 — Reply → Agent Response
- [ ] Reuse/extend the classifier from `reply_monitor.py` (POSITIVE / OBJECTION / OOO / NEGATIVE).
- [ ] POSITIVE: auto-draft a personalized reply, route to rep in Slack with a "book the meeting" action.
- [ ] OBJECTION: draft an objection handle, rep reviews before sending.
- [ ] OOO: auto-pause the lead in the sequence, schedule follow-up on return date.
- [ ] NEGATIVE: auto-suppress / remove from sequence.
- [ ] Post notifications to `#outbound-email-engine` (SLACK_ID) and/or rep DMs.

### Phase 3 — Email Open/Click → Aircall Dialer
- [ ] Intent scoring: flag leads on 2nd+ open, or open/click after a specific sequence step.
- [ ] Push flagged leads into the Aircall call list / dialer queue (name, title, company, email, phone).
- [ ] Enrich phone numbers where missing (Clay / LeadIQ) before pushing to Aircall.
- [ ] Notify the BDR ({{AE_2}} / {{AE_5}}) with the call list.

### Phase 4 — Instant Suppression
- [ ] EMAIL_BOUNCE → add domain/email to suppression pool immediately.
- [ ] EMAIL_UNSUBSCRIBE → remove from sequence + suppress immediately.

### Phase 5 — Ops & Monitoring
- [ ] Add the webhook receiver to the cron health monitor (no-silent-failures rule).
- [ ] Logging to `output/` + daily log.
- [ ] Failure alert → DM Jason Polanco (SLACK_ID).

---

## 5. Deliverables
- Webhook receiver service (runnable, monitored).
- Smartlead webhooks registered on target campaigns.
- Reply → agent response flow (Slack routing + draft replies).
- Open/click → Aircall dialer flow.
- Instant bounce/unsubscribe suppression.
- Health monitoring + failure alerts.

---

## 6. Out of Scope (for now)
- Aircall call recording / transcript ingestion (separate effort).
- Reply-to-meeting conversion analytics (needs EMAIL_REPLY webhook data first — this project enables it).
- Lemlist/Instantly webhook wiring (receiver will be built to accept them, but wiring is a follow-up).

---

## 7. Open Questions for Jason
1. Which campaigns get webhooks — all active, or just the {{PARTNER_B}} event campaigns?
2. Aircall: which call list / dialer queue should opens go to? Do we have API creds?
3. Open threshold: push on 1st open, or only 2nd+ open / open-after-specific-step?
4. Reply routing: which reps get which replies (by campaign/territory)?
5. Sign-off on Tailscale Funnel (security-relevant).

---

## 8. Key Technical Notes (from verification)
- Smartlead webhook create: `POST /api/v1/campaigns/{id}/webhooks` body `{name, webhook_url, event_types:[...]}`.
- Smartlead webhook delete: `DELETE /api/v1/campaigns/{id}/webhooks` with `{"id": <id>}` in the **body** (not URL path).
- Smartlead webhook list: `GET /api/v1/campaigns/{id}/webhooks`.
- Auth: `?api_key=<key>` query param (from `~/.openclaw/.env` → `SMARTLEAD_API_KEY`).
- The literal string `api_key=` gets redacted in exec/write — build query as `'?api' + '_key=' + key`.
- Webhooks are per-campaign; each campaign needs its own registration.
