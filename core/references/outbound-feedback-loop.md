# Outbound Feedback Loop — Rep Feedback → GitHub PR

**Owner:** GTM agent · **Reviewer:** Jason Polanco · **Status:** Active

This is the **human feedback loop** for {{COMPANY}}'s outbound system. When BDRs/AEs
flag bad data, weak copy, or suppression-worthy leads in Slack, the GTM agent turns that
feedback into a structured record + a GitHub PR that Jason reviews. It
complements the automated reply-data loop in `feedback_loop.py` (which is
unchanged).

## How reps submit

Reps submit feedback in **natural language** — no forms, no templates. Either:

- **DM the GTM agent** describing the issue, or
- **Post in `#outbound-email-engine`** describing the issue.

The GTM agent reads the message, classifies it, and handles the rest. Reps don't need to
know the taxonomy — they just describe what's wrong.

## Classification taxonomy

The GTM agent classifies each piece of feedback into exactly one type:

| Type | Meaning | Examples |
|------|---------|----------|
| `data-quality` | Wrong or stale contact/company data | Wrong email, wrong title, wrong company info, dead domain |
| `copy` | Weak or off-brand sequence language | Email reads like AI slop, off-brand tone, bad subject line, confusing CTA |
| `suppression` | Lead should not be contacted | Hard bounce, unsubscribe, wrong person, out-of-ICP, do-not-contact |
| `signal-miss` | Company showed intent we didn't catch | New funding, hiring spree, security breach, job posting we missed |
| `process` | Workflow or tooling issue | Campaign misconfigured, duplicate task, broken integration, timing bug |

## What happens

1. **Rep submits** feedback in Slack (DM or `#outbound-email-engine`).
2. **The GTM agent classifies** the feedback into one of the five types above.
3. **The GTM agent writes a record** to
   `gtm-vault/feedback/rep-feedback/YYYY-MM-DD-<slug>.md` (all fields + UTC
   timestamp + `status: pending-review`).
4. **The GTM agent opens a PR** in `example-org/openclaw-workspaces` (mirrored under
   `gtm-agent/gtm-vault/feedback/rep-feedback/`), branch
   `rep-feedback/YYYY-MM-DD-<slug>`.
5. **The GTM agent posts the PR link** back in the original Slack thread.
6. **Jason reviews** at his own pace:
   - **Merge** = feedback accepted → GTM agent applies the action mapping below.
   - **Close** = feedback rejected → no action taken.

## Action mapping (after merge)

| Type | Action after merge |
|------|--------------------|
| `suppression` | Add the company/domain to Smartlead + Clay suppression lists |
| `copy` | Edit `references/outbound-copy.md` with the corrected/approved language |
| `data-quality` | Note the correction in `account-knowledge/<slug>.md` for that account |
| `signal-miss` | Tune `signal_scanner` config to catch the missed signal type |
| `process` | Fix the workflow/tooling issue; log the fix |

## SLA

- **PR opened within minutes** of feedback being submitted (GTM agent runs the
  pipeline immediately on classification).
- **Jason reviews at his pace** — no automated pestering. Merge/close is the
  signal.

## Tooling

- CLI: `python3 projects/scripts/outbound-engine/rep_feedback_pr.py`
- Idempotent: identical open PRs are not duplicated.
- **Never auto-merges.** Merge/close is always a human decision.
- No silent failures: every step logs to stderr; any failure exits non-zero.
