# Outbound Pipeline Rules (Jason, 2026-06-18, PERMANENT)

Pipeline: **find companies → push to Clay → Clay enriches + enrolls into Smartlead.**
- Target: 10-12 contacts per company. 1,500+ emails/week.
- Discovery cron Mon-Fri 12:00 UTC. Dispatch cron Mon-Fri 13:00 UTC.
- When the pipeline breaks, fix it immediately. Jason should never manually run any part.

## Clay Dispatch Quality Gate (PERMANENT)
Every account pushed to Clay must afford a $150-250K solution. ICP floor: 1,000+ employees, $250M+ revenue. Never dispatch spam domains, solo consultants, tiny startups. When in doubt, don't dispatch.

## Reachability Gate (added 2026-10-27)
Clay output passes through `scripts/reachability-gate/gate.py` before Smartlead enrollment. Spec: `scripts/reachability-gate/README.md`.
- A/B same domain → main Smartlead campaign. C catch-all → isolated low-volume inbox pool. D → LinkedIn then phone. Job change → re-source. Free-mail / cross-domain → review.
- Nothing is deleted. A D grade means the mailbox is dead, not the person.
- Grades cache 30 days in `$GTM_DATA_DIR/reachability.db`; re-dispatch never re-spends.
- Wire-up: Clay enrolls from `send.csv` and `send_low_volume.csv` only.

## Mobile Sourcing Workflow (Jason, 2026-10-07, PERMANENT)
Standing path for sourcing mobile numbers for every campaign:
1. **HubSpot name backfill** — every lead carries first/last before enrichment.
2. **Clay phone waterfall (primary)** — POST full lead payload (email, first/last, company, domain, job_title, `linkedin_url` mandatory) to the waterfall: Lyne → Wiza → BetterContact. The Clay workflow must be PUBLISHED before results are trusted (unpublished workflows fire stale versions).
3. **Floqer backstop** — runs in parallel; skip when the account is out of credits (check balance first).
4. **LinkedIn-gated providers** (LeadMagic / Findymail / Prospeo) run OFF the critical path so leads without a LinkedIn URL don't block phone flow.
5. **Quality gates** — reject toll-free (800/888/877/866/855/844/833), reject HubSpot company-main-line matches, no corporate fallbacks (Rule #6). Added 2026-10-27: run `scripts/phone-compliance/phone_gate.py` (adds line type + do-not-call hash match). Only `cleared_to_call` rows move to step 6; `pending_checks` is never dialed.
6. **Write-back** — `mobilephone` + `hs_linkedin_url` written to the HubSpot contact record.
7. **Immediate push** — sourced numbers go into Aircall (BDR campaign + dialer) and Lemlist (lead `phone` field) for all active campaigns right after sourcing.

## Signal Sourcing Spec (PERMANENT)
Full spec at `rules/signal-sourcing-spec.md`.
- **No signal = no send.**
- **4-tier:** SEC 10-K/10-Q → AI initiative press releases → hiring signals → exec appointments.
- **Industry from seed list, NEVER default "Technology".**
- **signal_score = "High" or "Medium"** (not numeric).
- **Hard exclusions:** investors/VC/PE, staffing/lead-gen, agencies, parked domains, micro-startups.
- **Volume: 15-25 qualified accounts per dispatch.** Never pad with junk.
- **NEVER discover companies from web search snippets.**

## Pipeline Script Change Protocol (Jason, 2026-06-23, PERMANENT)
For ANY change to scripts in `scripts/outbound-engine/`:
1. BEFORE: `grep -r "from <module> import\|import <module>" scripts/outbound-engine/`
2. AFTER: Test every consumer imports: `python3 -c "import <module>; print('OK')"`
3. Run each affected cron script with `--dry-run` or `--help`
4. If removing/renaming exports: update ALL consumers in same commit, or add shims
5. Check NEXT cron execution log within 1 hour

## Dispatch Reporting Verification (Jason, 2026-06-25, PERMANENT)
After every dispatch cron run, the Slack summary MUST match the actual dispatch log.
- Summary script always receives `--dispatch-log <path>` (never `--batch-file`)
- Zero-dispatch summaries investigated same-day
- Key files: `run_volume_dispatch.sh`, `post_dispatch_summary.py`, `volume-dispatch-log-YYYYMMDD.json`
