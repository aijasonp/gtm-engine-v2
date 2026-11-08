# Reachability gate

Runs between Clay enrichment and Smartlead enrollment. Every lead gets an A-F email grade from MoltSets and a route. Bad grades are routed, not deleted.

| Grade / state | Route | File |
| --- | --- | --- |
| A or B, same domain | Smartlead, main inboxes | `send.csv` |
| C (catch-all) | Smartlead, isolated low-volume pool | `send_low_volume.csv` |
| D (bounce, complaint, spam trap) | LinkedIn, then phone waterfall | `linkedin.csv` |
| F or not in graph | second pass, then LinkedIn or hold | `linkedin.csv` / `hold.csv` |
| Person moved companies | re-source at the new company | `resource.csv` |
| Free-mail or cross-domain | human review | `hold.csv` |

`all.csv` holds every row. `summary.json` holds counts by route, grade and verifier delta. Columns from the input file pass through, so campaign and sequence fields survive the gate.

## Run

```bash
python3 gate.py clay_export.csv                  # grade + route
python3 gate.py clay_export.csv --second-pass    # recover F / 404 rows by name + domain
python3 gate.py clay_export.json --dry-run       # plan only, no spend
python3 gate.py clay_export.csv --sheet          # also build the review sheet (core/lib/sheet_engine.py)
```

Needs `MOLTSETS_API_KEY` in the environment or in `GTM_ENV_FILE`. Grades are cached in `$GTM_DATA_DIR/reachability.db` (default `~/.gtm/data`) for `--max-age-days` (30), so a lead that comes back through dispatch is not re-spent. Every API call is logged in the same database. The run stops spending when `records_remaining_5h` drops under `MOLTSETS_RECORDS_FLOOR` (25) and routes the rest to `hold.csv`.

## Verifier deltas

If the export carries a ZeroBounce, NeverBounce, MillionVerifier or Bouncer verdict (`zb_status`, `verifier_status`, `email_status` and similar), each row also gets a `delta_class`. The ones worth acting on:

- `molt_downgrades_valid`: verifier said valid, MoltSets says D. Suppress.
- `molt_upgrades_catchall`: verifier said catch-all, MoltSets saw real activity. Candidate for the main pool.
- `molt_corrects_address` / `molt_recovers_invalid`: MoltSets found a better same-domain address.

## Files

- `gate.py` CLI and waterfall
- `reachability.py` pure grade, tier, route and delta functions
- `moltsets_client.py` never-raising client, response-shape normalizers, call ledger, budget floors

`reachability.py` and `moltsets_client.py` are vendored from shawnla90/gtm-coding-agent (MIT). See `THIRD_PARTY.md`.
