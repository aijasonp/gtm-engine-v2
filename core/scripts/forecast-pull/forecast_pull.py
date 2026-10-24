#!/usr/bin/env python3
"""Daily HubSpot pull for the {{COMPANY}} Weekly Forecast Tracker.

Spec: GTM_Agent_Build_Spec_Forecast_Tracker.md §5. One snapshot per forecast week
(Tue–Mon, labeled by Friday). Appends/replaces the current week's block in
'HubSpot Pull' columns A:AB. Never rewrites older rows, never deletes rows,
never touches AC:AZ or row 1.

Cron: 4:00 AM America/Los_Angeles daily.

Failure behavior (§5.4): any failure → stop WITHOUT changing the sheet, alert
{{REVOPS_1}} by Slack DM.

Split 2026-10-07 into the `forecast/` package (config, dtutil, gws, hubspot,
mapping, sheets, rollover, alerting); this file is the thin entrypoint + main().
"""
import json
import sys
from datetime import datetime, timedelta

from forecast.alerting import slack_alert
from forecast.config import HUBSPOT_TOKEN, MAX_ROW, PT
from forecast.dtutil import forecast_week, forecast_week_of_serial, serial_of
from forecast.gws import gws_values_clear, gws_values_update
from forecast.hubspot import pull_companies, pull_deals, pull_owners
from forecast.mapping import map_deal
from forecast.rollover import rollover
from forecast.sheets import (read_quarter_ref, read_roster, read_snapshot_col,
                             read_week_list)


def main():
    if not HUBSPOT_TOKEN:
        print("HUBSPOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    today = datetime.now(PT).date()
    sw = forecast_week(today - timedelta(days=1))       # Snapshot Week (Friday)
    q_label, q_start, q_end = read_quarter_ref()

    if sw > q_end:
        q_label, q_start, q_end = rollover(sw, None)
    elif sw < q_start - timedelta(days=7):
        # One-week grace before quarter open so forecasting can start the week
        # prior ({{REVOPS_1}}, 2026-09-24). Pull filter still uses true q_start, so
        # only in-quarter deals are pulled.
        slack_alert(f"Snapshot Week {sw} is more than a week before quarter start {q_start} — no write. (If the quarter was set early by mistake, fix Quarter Reference!B4.)")
        print("ABORT: SW before quarter start")
        return

    # pull
    try:
        deals = pull_deals(q_start, q_end)
    except Exception as e:
        slack_alert(f"HubSpot pull failed: {e}. Sheet unchanged.")
        print("ABORT: HubSpot failure", e)
        return

    # guard: 0 deals when last snapshot had some
    ab_col = read_snapshot_col()
    prev_rows = [(r, v) for r, v in ab_col if v not in (None, "")]
    if not deals and prev_rows:
        slack_alert("HubSpot returned 0 deals but previous snapshot had rows. Sheet unchanged.")
        print("ABORT: 0 deals")
        return

    owners = pull_owners()
    companies = pull_companies([str(d["id"]) for d in deals])
    roster = read_roster()

    # map + dedupe
    unknown_flags = []
    seen, rows = set(), []
    for d in deals:
        oid = str(d["id"])
        if oid in seen:
            continue
        seen.add(oid)
        rows.append(map_deal(d, owners, companies, roster, unknown_flags))

    today_serial = serial_of(today)
    for r in rows:
        r[27] = today_serial  # AB Snapshot Date

    # find write position (§5.4 step 3)
    first_sw_row, last_used, out_of_order = None, 1, False
    seen_other_after_sw = False
    for r, v in ab_col:
        if v in (None, ""):
            continue
        last_used = max(last_used, r)
        wk = forecast_week_of_serial(v)
        if wk == sw:
            if first_sw_row is None:
                first_sw_row = r
        else:
            if first_sw_row is not None:
                out_of_order = True

    if out_of_order:
        slack_alert("HubSpot Pull rows out of order (same-week row above other-week row). Sheet unchanged.")
        print("ABORT: out of order")
        return

    start_row = first_sw_row if first_sw_row else last_used + 1
    end_row = start_row + len(rows) - 1
    if end_row > MAX_ROW:
        slack_alert(f"Capacity exceeded: block would reach row {end_row} (max {MAX_ROW}). Sheet unchanged.")
        print("ABORT: capacity")
        return

    # clear old block A:AB from start_row to last_used (values only)
    if last_used >= start_row:
        gws_values_clear(f"HubSpot Pull!A{start_row}:AB{last_used}")

    # write RAW (A:Z + AB then AA separately)
    # columns: A..Z = idx 0..25, AB = idx 27. Never write AA (formula column) via RAW.
    az = [r[:26] for r in rows]
    ab = [[r[27]] for r in rows]
    gws_values_update(f"HubSpot Pull!A{start_row}:Z{end_row}", az, "RAW")
    gws_values_update(f"HubSpot Pull!AB{start_row}:AB{end_row}", ab, "RAW")
    aa = [[f"=HYPERLINK('Quarter Reference'!$B$8&Y{r},\"Open\")"] for r in range(start_row, end_row + 1)]
    gws_values_update(f"HubSpot Pull!AA{start_row}:AA{end_row}", aa, "USER_ENTERED")

    # stamp latest snapshot date so the header 'HubSpot as of' stays current.
    # Done BEFORE the week-picker write so a picker failure can never leave the
    # reference date stale (2026-10-07 incident: a renamed tab crashed the run
    # here and froze the waterfalls on the prior week).
    gws_values_update("Quarter Reference!B6", [[today_serial]], "RAW")

    # week picker P2 = forecast week of today, if in B13:B26.
    # Tab was renamed Leadership View -> CRO View (2026-10-06). Keep the update
    # non-fatal: log/alert on failure so a future rename never silently kills
    # the whole pull after snapshot data has already been written.
    this_week = forecast_week(today)
    week_serials = read_week_list()
    if serial_of(this_week) in week_serials:
        try:
            gws_values_update("CRO View!P2", [[serial_of(this_week)]], "RAW")
        except Exception as e:
            slack_alert(f"Week-picker write (CRO View!P2) failed: {e}. Snapshot + as-of date written; picker not advanced.")

    for f in unknown_flags:
        slack_alert(f"Unmapped value: {f}. Raw value written; map it in the spec.")

    print(json.dumps({
        "run_date": str(today), "snapshot_week": str(sw), "quarter": q_label,
        "deals_written": len(rows), "start_row": start_row, "end_row": end_row,
        "replaced_same_week": first_sw_row is not None,
        "unknown_flags": unknown_flags,
    }))


if __name__ == "__main__":
    main()
