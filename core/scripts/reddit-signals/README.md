# Reddit buyer signals

Buyer language from Reddit, classified into vault `community-intent` signals and copy-ready phrases.

| Kind | Signal | Strength / decay |
| --- | --- | --- |
| comparison (X vs Y) | `reddit-vendor-comparison` | high / 45 days |
| recommendation ask | `reddit-recommendation-ask` | high / 30 days |
| pain (price, complexity, limits) | `reddit-vendor-pain` | medium / 60 days |
| general question | `reddit-category-question` | low / 30 days |

An item only counts if it names a tracked vendor or a category noun, so careers, gaming and politics threads stay out. Vendor names are word-bounded, so short names do not match inside other words.

## Run

```bash
cp reddit.example.json reddit.json                         # vendors, category nouns, topics
python3 reddit_signals.py import export.json --config reddit.json   # Clearbox, Apify dataset, CSV or JSONL
python3 reddit_signals.py pull --config reddit.json                 # optional: Apify actor named in config
python3 reddit_signals.py export --config reddit.json --out reddit_signals.csv
python3 reddit_signals.py export --config reddit.json --vault-language
```

`--vault-language` appends comparison, recommendation and pain phrases to `core/gtm-vault/language/community-language.json` (source `reddit`) with the same fields as the reply and call phrase library, so the campaign builder can use buyer wording. Already-written phrases are skipped.

Most Reddit authors are anonymous. Treat these as account-agnostic market signals and copy input; they become account signals only when a thread names a company or links to a known profile.

Data lives in `$GTM_DATA_DIR/reddit_signals.db`. Adapted from the reddit-buyer-signals starter in shawnla90/gtm-coding-agent (MIT). See `THIRD_PARTY.md`.
