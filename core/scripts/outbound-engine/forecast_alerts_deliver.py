#!/usr/bin/env python3
"""Run forecast_change_alerts.py and send each recipient's Slack DM.

Usage: forecast_alerts_deliver.py [--pm-window] [--test RECIPIENT_KEY]

Recipients and their Slack member IDs come from the same config file as the
alerts script (FORECAST_ALERTS_CONFIG). Delivery uses the Slack Web API with
SLACK_BOT_TOKEN (scopes: chat:write, im:write).
Prints a one-line JSON summary for logs. No silent failures: exit 1 with the
raw error on any failure.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ALERTS = HERE / "forecast_change_alerts.py"
ENV_FILE = Path(os.path.expanduser(os.environ.get("GTM_ENV_FILE", "~/.gtm/.env")))
CONFIG_FILE = Path(os.environ.get("FORECAST_ALERTS_CONFIG", HERE / "forecast_alerts.config.json"))


def load_env():
    env = dict(os.environ)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if "=" not in line or line.startswith("#"):
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if k in ("HUBSPOT_TOKEN", "SLACK_BOT_TOKEN") and k not in env:
                env[k] = v.strip().strip('"').strip("'")
    return env


def slack_dm(token, user_id, text):
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    r = requests.post("https://slack.com/api/conversations.open", headers=h, json={"users": user_id}, timeout=30).json()
    if not r.get("ok"):
        return r.get("error", "conversations.open failed")
    ch = r["channel"]["id"]
    r = requests.post("https://slack.com/api/chat.postMessage", headers=h, json={"channel": ch, "text": text}, timeout=30).json()
    return None if r.get("ok") else r.get("error", "chat.postMessage failed")


def main():
    pm = "--pm-window" in sys.argv
    test_key = sys.argv[sys.argv.index("--test") + 1] if "--test" in sys.argv else None
    env = load_env()
    for k in ("HUBSPOT_TOKEN", "SLACK_BOT_TOKEN"):
        if k not in env:
            print(json.dumps({"error": f"{k} not in env or GTM_ENV_FILE"}))
            return 1
    if not CONFIG_FILE.exists():
        print(json.dumps({"error": f"missing config {CONFIG_FILE}"}))
        return 1
    slack_ids = {r["key"]: r["slack_id"] for r in json.loads(CONFIG_FILE.read_text())["recipients"]}

    cmd = [sys.executable, str(ALERTS)] + (["--pm-window"] if pm else [])
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print(json.dumps({"error": "alerts script failed", "stdout": r.stdout[-2000:], "stderr": r.stderr[-2000:]}))
        return 1
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        print(json.dumps({"error": f"bad JSON from alerts script: {e}", "stdout": r.stdout[-2000:]}))
        return 1
    if out.get("skipped"):
        print(json.dumps(out))
        return 0
    if out.get("error"):
        print(json.dumps(out))
        return 1

    messages = out.get("messages", {})
    if test_key:
        messages = {test_key: messages.get(test_key)}
        if messages[test_key]:
            messages[test_key] = "[TEST RUN: forecast change alerts, not live yet]\n\n" + messages[test_key]

    sent, failed = [], []
    for key, msg in messages.items():
        if not msg:
            continue
        if key not in slack_ids:
            failed.append({"recipient": key, "error": "no slack_id in config"})
            continue
        err = slack_dm(env["SLACK_BOT_TOKEN"], slack_ids[key], msg)
        (failed.append({"recipient": key, "error": err}) if err else sent.append(key))

    print(json.dumps({"sent": sent, "failed": failed, "alerts": out.get("alert_count", 0),
                      "in_scope": out.get("in_scope_deal_count", 0), "test": test_key, "pm_window": pm}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
