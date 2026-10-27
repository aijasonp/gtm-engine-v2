# Phone compliance gate

The last check before a sourced number reaches Aircall or Lemlist. Runs after the Clay phone waterfall and the Floqer backstop, before write-back and push.

Checks, in order: E.164 normalization, toll-free (800/888/877/866/855/844/833), company main line, line type (when present), do-not-call.

| Route | Meaning |
| --- | --- |
| `cleared_to_call` | every check passed; push to the dialer |
| `email_only` | the number failed; the lead still has an email |
| `no_channel` | the number failed and there is no email |
| `pending_checks` | a check could not run (no DNC file, or line type required and missing). Do not dial. |

## Run

```bash
# one-time: build a hash file from a raw suppression list or registry download
python3 phone_gate.py hash-list internal_dnc.csv --column phone > ~/.gtm/dnc/internal.txt

# every batch
python3 phone_gate.py check sourced_phones.csv --dnc ~/.gtm/dnc/internal.txt --dnc ~/.gtm/dnc/registry.txt
```

Writes `phones_checked.csv` (every row, with `phone_e164`, `phone_route`, `phone_reason`) and `cleared_to_call.csv`.

DNC files hold SHA-256 hashes of E.164 numbers, one per line. A file of raw numbers also works; it is hashed on load. Keep DNC files outside the repo.

## Wired in

`bounce-reenrichment/clay_enrich.py` now calls `check_number()` for every Clay phone hit. Set `PHONE_DNC_FILES=/path/a.txt:/path/b.txt`. Without it, numbers are kept but marked `pending_checks` and a warning prints. Filter on `clay_phone_route == "cleared_to_call"` before any dialer push.

Hash format and routing order adapted from shawnla90/gtm-coding-agent (MIT). See `THIRD_PARTY.md`.
