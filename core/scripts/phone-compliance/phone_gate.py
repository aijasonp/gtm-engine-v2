#!/usr/bin/env python3
"""phone_gate.py: the last check before a sourced number reaches Aircall or Lemlist.

Runs after the Clay phone waterfall (Lyne -> Wiza -> BetterContact) and the Floqer backstop, and
before the write-back push. One place for every phone quality gate in the outbound pipeline:

  1. normalize    to E.164 (US/CA default for 10-digit numbers)
  2. toll-free    reject 800/888/877/866/855/844/833 (Rule: no corporate fallbacks)
  3. main line    reject numbers that match the company's main line from HubSpot
  4. line type    when the row carries a line type, only "mobile" is dialable
  5. do-not-call  SHA-256 of the E.164 number matched against your DNC hash file(s)

Routes:
  cleared_to_call  every check passed: push to Aircall + Lemlist
  email_only       the number failed a check, but the lead still has an email
  no_channel       the number failed a check and there is no email
  pending_checks   a check could not run (no DNC file loaded, or line type required and missing).
                   Do not dial. The email can still be mailed.

DNC files store hashes, never raw numbers. Build one from your internal suppression list or a
registry download with:  python3 phone_gate.py hash-list raw_numbers.txt > dnc_hashes.txt

  python3 phone_gate.py check phones.csv --dnc dnc_hashes.txt              # annotate + split
  python3 phone_gate.py check phones.csv --dnc a.txt --dnc b.txt --require-line-type
  python3 phone_gate.py hash-list registry_export.csv --column phone > dnc_hashes.txt
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

TOLL_FREE = ("800", "888", "877", "866", "855", "844", "833")

CLEARED, EMAIL_ONLY, NO_CHANNEL, PENDING = "cleared_to_call", "email_only", "no_channel", "pending_checks"

PHONE_COLS = ("mobilephone", "mobile_phone", "phone", "phone_number", "Mobile Phone", "Phone")
EMAIL_COLS = ("email", "work_email", "Email")
MAIN_LINE_COLS = ("company_phone", "company_main_line", "hs_company_phone", "Company Phone")
LINE_TYPE_COLS = ("line_type", "phone_type", "Line Type")


def to_e164(number: str, default_country: str = "1") -> str:
    """Best-effort E.164. '' when the input cannot be a dialable number.
    10 digits -> +1XXXXXXXXXX; 11 digits starting with 1 -> +1...; leading + or 00 kept as international."""
    raw = (number or "").strip()
    if not raw:
        return ""
    raw = re.split(r"\s*(?:x|ext\.?|extension)\s*\d+\s*$", raw, flags=re.I)[0]
    intl = raw.startswith("+") or raw.startswith("00")
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
    if intl:
        return "+" + digits if 8 <= len(digits) <= 15 else ""
    if len(digits) == 10:
        return "+" + default_country + digits
    if len(digits) == 11 and digits.startswith(default_country):
        return "+" + digits
    return ""


def hash_number(number: str) -> str:
    """SHA-256 of the E.164 form. Raw input is normalized first so formatting never breaks a match."""
    e164 = to_e164(number) or re.sub(r"[^\d+]", "", number or "")
    return hashlib.sha256(e164.encode("utf-8")).hexdigest()


def is_toll_free(e164: str) -> bool:
    return e164.startswith("+1") and e164[2:5] in TOLL_FREE


def load_dnc(paths: list[Path]) -> set[str] | None:
    """Union of hash files. None when no file was given (the DNC step cannot run). A file that
    holds raw numbers instead of hashes is hashed on load, so either format works."""
    if not paths:
        return None
    hashes: set[str] = set()
    for p in paths:
        for line in Path(p).read_text().splitlines():
            v = line.strip().split(",")[0].strip().lower()
            if not v or v.startswith("#"):
                continue
            hashes.add(v if re.fullmatch(r"[0-9a-f]{64}", v) else hash_number(v))
    return hashes


def check_number(number: str, *, email: str = "", main_line: str = "", line_type: str = "",
                 dnc: set[str] | None = None, require_line_type: bool = False) -> tuple[str, str, str]:
    """(route, reason, e164) for one number. Pure."""
    fallback = EMAIL_ONLY if (email or "").strip() else NO_CHANNEL
    e164 = to_e164(number)
    if not e164:
        return fallback, "unparseable" if (number or "").strip() else "no_number", ""
    if is_toll_free(e164):
        return fallback, "toll_free", e164
    if main_line and to_e164(main_line) == e164:
        return fallback, "company_main_line", e164
    lt = (line_type or "").strip().lower()
    if lt and lt not in ("mobile", "cell", "wireless"):
        return fallback, f"line_type_{lt}", e164
    if not lt and require_line_type:
        return PENDING, "line_type_missing", e164
    if dnc is None:
        return PENDING, "dnc_not_loaded", e164
    if hash_number(e164) in dnc:
        return fallback, "dnc_match", e164
    return CLEARED, "ok", e164


def first(row: dict, cols: tuple[str, ...]) -> str:
    for c in cols:
        if str(row.get(c) or "").strip():
            return str(row[c]).strip()
    return ""


def cmd_check(args) -> int:
    dnc = load_dnc(args.dnc)
    if dnc is None:
        print("warning: no --dnc file given. Every number will route to pending_checks.", file=sys.stderr)
    with args.input.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    phone_cols = (args.phone_column,) if args.phone_column else PHONE_COLS
    out_rows, counts = [], {}
    for r in rows:
        route, reason, e164 = check_number(first(r, phone_cols), email=first(r, EMAIL_COLS),
                                           main_line=first(r, MAIN_LINE_COLS), line_type=first(r, LINE_TYPE_COLS),
                                           dnc=dnc, require_line_type=args.require_line_type)
        out_rows.append({**r, "phone_e164": e164, "phone_route": route, "phone_reason": reason})
        counts[route] = counts.get(route, 0) + 1
    out_dir = args.out_dir or args.input.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = list(out_rows[0].keys()) if out_rows else ["phone_e164", "phone_route", "phone_reason"]
    for name, keep in (("phones_checked.csv", None), ("cleared_to_call.csv", CLEARED)):
        with (out_dir / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(r for r in out_rows if keep is None or r["phone_route"] == keep)
    print(" ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "no rows")
    print(f"wrote {out_dir / 'phones_checked.csv'} and {out_dir / 'cleared_to_call.csv'}")
    return 0


def cmd_hash_list(args) -> int:
    with args.input.open(newline="", encoding="utf-8-sig") as f:
        if args.column:
            values = [r.get(args.column, "") for r in csv.DictReader(f)]
        else:
            values = [line.split(",")[0] for line in f.read().splitlines()]
    seen = set()
    for v in values:
        if to_e164(v):
            h = hash_number(v)
            if h not in seen:
                seen.add(h)
                print(h)
    print(f"{len(seen)} hashes", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="annotate a CSV of sourced numbers and split out cleared_to_call")
    c.add_argument("input", type=Path)
    c.add_argument("--dnc", type=Path, action="append", default=[], help="DNC hash file (repeatable)")
    c.add_argument("--phone-column", default=None)
    c.add_argument("--require-line-type", action="store_true", help="hold rows with no line type")
    c.add_argument("--out-dir", type=Path, default=None)
    h = sub.add_parser("hash-list", help="turn a raw number list into a DNC hash file on stdout")
    h.add_argument("input", type=Path)
    h.add_argument("--column", default=None, help="CSV column holding the number (default: first field)")
    args = ap.parse_args(argv)
    return cmd_check(args) if args.cmd == "check" else cmd_hash_list(args)


if __name__ == "__main__":
    sys.exit(main())
