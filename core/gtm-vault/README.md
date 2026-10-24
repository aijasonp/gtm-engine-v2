# GTM Vault — Persistent Outbound Intelligence

_Inspired by Karpathy's autoresearch: a compounding memory layer for {{COMPANY}}'s outbound engine._

---

## The Concept

Traditional outbound is a one-shot campaign. You build a list, write copy, hit send, and hope. When the campaign ends, all the learnings die with it.

This vault changes that. It's the persistent memory layer that makes every campaign smarter than the last.

**The loop:**
1. **Human sets direction** — ICP definitions, vertical priorities, angle hypotheses
2. **Vault holds memory** — everything outbound has ever learned: what angles work, what objections come up, how prospects actually talk about their problems, which verticals respond
3. **Agent reads vault + executes** — pipeline scripts read from the vault before building lists, writing copy, or generating sequences
4. **Market votes** — prospects reply (or don't). Every reply is signal.
5. **Results write back** — reply analysis extracts insights and writes them back into the vault
6. **Loop restarts smarter** — next campaign has richer context, better angles, pre-handled objections

Nothing is ever lost. The system compounds.

## Directory Structure

```
gtm-vault/
├── verticals/         # Per-industry intelligence profiles
│   ├── banking.md
│   ├── healthcare.md
│   ├── ...
│   └── _template.md
├── angles/            # Tracked angle library with win/loss records
│   ├── angle-library.json
│   └── README.md
├── signals/           # Signal taxonomy + decay engine powering sourcing logic
│   ├── signal-taxonomy.json
│   └── decay-config.json
├── objections/        # Objection patterns from replies + calls
│   ├── objection-patterns.json
│   └── README.md
├── language/          # Actual phrases prospects use
│   ├── customer-language.json
│   └── README.md
└── feedback/          # Per-step copy performance + weekly insights
    ├── copy-performance.json
    ├── weekly-insights.md
    └── README.md
```

## How Scripts Interact

| Script | Reads From | Writes To |
|--------|-----------|-----------|
| `reply_monitor.py` | — | `language/`, `objections/`, `feedback/`, `verticals/` |
| `feedback_loop.py` | `feedback/`, `angles/` | `angles/`, `verticals/` (winning/failed angles), `feedback/weekly-insights.md` |
| `vault_campaign_builder.py` | `verticals/`, `angles/`, `objections/`, `language/`, `signals/` | `sequences/` |
| `auto_copy_optimizer.py` | `feedback/`, `angles/`, `language/` | `sequences/variants/` |
| `build_daily_batch.py` | `angles/`, `signals/` (taxonomy + decay) | — |
| `signal_scorer.py` | `signals/signal-taxonomy.json`, `signals/decay-config.json` | scored output files |
| `winloss_signal_miner.py` | HubSpot deals, dispatch logs, `signals/` | `feedback/signal-performance.json`, `verticals/` |
| `clay_credit_optimizer.py` | dispatch logs, `signals/` | `feedback/credit-optimization.json`, `output/` reports |
| `campaign_sync.py` | Smartlead campaigns | `feedback/copy-performance.json` |
| `copy_critique_loop.py` | `verticals/`, `language/` | `output/critique-results/` |
| `sam_gov_importer.py` | SAM.gov API | `output/` (seed candidates) |

## Rules

- **Vertical files**: human-editable sections (Industry Context, Pain Points, Angle Hypotheses, Key Signals) plus auto-populated sections (Winning Angles, Failed Angles, Objection Patterns, Customer Language). Don't manually edit auto-populated sections.
- **JSON files**: append-only by scripts, atomic writes (tmp + rename). Human review welcome but scripts own the data.
- **Weekly cadence**: `feedback_loop.py` runs Fridays and updates angle library + vertical files with accumulated performance data.
- **Continuous**: `reply_monitor.py` writes back after every poll cycle (every 15 min via cron).

---

_This vault is {{COMPANY}}'s outbound brain. Feed it data. It gets sharper._
