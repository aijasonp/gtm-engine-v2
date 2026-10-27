# Competitor engagers

People who comment on a competitor's LinkedIn posts, scored and exported for Clay. Feeds the vault's `community-intent` category.

| Signal | When |
| --- | --- |
| `competitor-post-engagement` | commented on one tracked competitor (medium, 30-day decay) |
| `competitor-multi-engagement` | commented on two or more tracked competitors (high, 30-day decay) |

Scoring drops competitor employees, your own team and excluded titles (recruiters, sellers, students), tiers the persona from `persona_tiers`, applies freshness from `gtm-vault/signals/decay-config.json`, and sets `push=yes` for tier 3 and up that has not expired. Pair the export with an account-level signal and the `community-plus-account-signal` stacking rule lifts it to high priority.

## Run

```bash
cp competitors.example.json competitors.json          # fill in competitors, personas, exclusions
python3 engagers.py pull   --config competitors.json --dry-run
python3 engagers.py pull   --config competitors.json  # spends Apify credits
python3 engagers.py score  --config competitors.json
python3 engagers.py export --config competitors.json --out competitor_engagers.csv
```

Needs `APIFY_TOKEN` in the environment or in `GTM_ENV_FILE`. Uses the harvestapi LinkedIn post and comment actors through the Apify REST API (`core/lib/apify_client.py`), no CLI login. Data lives in `$GTM_DATA_DIR/competitor_engagers.db`. Re-pulls are idempotent and only fetch comments for posts not yet processed.

The export columns (`first_name`, `last_name`, `title`, `company`, `linkedin_url`, `signal_id`, `priority`, `sample_comment`) map straight onto the Clay dispatch table. Run the output through the reachability gate before Smartlead.

Adapted from the nexus-intel engager pipeline in shawnla90/gtm-coding-agent (MIT). See `THIRD_PARTY.md`.
