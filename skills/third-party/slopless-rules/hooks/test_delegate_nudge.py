#!/usr/bin/env python3
"""Both-direction control for delegate-nudge.py.

The hook once counted only Edit/Write/MultiEdit, so a session that ran ~25 inline
ssh/psql/docker calls against a remote host and edited no local file incremented nothing
and was never nudged. Bash is now counted on its own threshold (BASH_THRESHOLD), with
read-only local shapes (ls/cat/grep/git status) deliberately excluded.

Runs BOTH directions on purpose. A control run only on the cases that should fire proves
the hook catches and says nothing about what it wrongly catches. The two REGRESSION rows
guard the edit path.

Tests the hook that sits NEXT TO this file, with state in a temp dir, so running it from
the repo checks the repo copy and writes nothing under ~/.claude.

Run: python3 hooks/test_delegate_nudge.py"""
import json, subprocess, os, shutil, sys, uuid, tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "delegate-nudge.py")
STATE = tempfile.mkdtemp(prefix="delegate-nudge-ctl-")
ENV = dict(os.environ, DELEGATE_NUDGE_STATE=STATE)
ENV.pop("DELEGATE_NUDGE", None)

if os.path.exists(os.path.expanduser("~/.claude/.delegate-nudge-off")):
    print("CONTROL CANNOT RUN: ~/.claude/.delegate-nudge-off is set, so every case would read silent.")
    sys.exit(2)


def feed(tool, payload_field, value, sid, n):
    """Send n PostToolUse payloads; return the number that emitted additionalContext."""
    hits = 0
    for _ in range(n):
        p = {"tool_name": tool, "tool_input": {payload_field: value}, "session_id": sid}
        r = subprocess.run([sys.executable, HOOK], input=json.dumps(p),
                           capture_output=True, text=True, env=ENV)
        if "additionalContext" in (r.stdout or ""):
            hits += 1
    return hits


fails = []

# POSITIVE: delegable bash must fire at BASH_THRESHOLD (10)
sid = "ctl-pos-" + uuid.uuid4().hex[:8]
hits = feed("Bash", "command", "ssh build-host 'psql -c \"select 1\"'", sid, 12)
print(f"  POSITIVE  12x ssh/psql            -> fired {hits}x  ({'PASS' if hits==1 else 'FAIL'})")
if hits != 1: fails.append("delegable bash did not fire exactly once")

# NEGATIVE: read-only local shell must stay silent
sid = "ctl-neg1-" + uuid.uuid4().hex[:8]
hits = feed("Bash", "command", "ls -la ~/apps", sid, 25)
print(f"  NEGATIVE  25x ls                  -> fired {hits}x  ({'PASS' if hits==0 else 'FAIL'})")
if hits: fails.append("ls triggered the nudge")

sid = "ctl-neg2-" + uuid.uuid4().hex[:8]
hits = feed("Bash", "command", "git status --porcelain", sid, 25)
print(f"  NEGATIVE  25x git status          -> fired {hits}x  ({'PASS' if hits==0 else 'FAIL'})")
if hits: fails.append("git status triggered the nudge")

# NEGATIVE: below threshold must stay silent
sid = "ctl-neg3-" + uuid.uuid4().hex[:8]
hits = feed("Bash", "command", "ssh build-host 'docker ps'", sid, 9)
print(f"  NEGATIVE  9x ssh (below 10)       -> fired {hits}x  ({'PASS' if hits==0 else 'FAIL'})")
if hits: fails.append("fired below BASH_THRESHOLD")

# REGRESSION: the edit path must still fire at EDIT_THRESHOLD (8)
sid = "ctl-edit-" + uuid.uuid4().hex[:8]
hits = feed("Edit", "new_string", "x = 1", sid, 10)
print(f"  REGRESSION 10x Edit               -> fired {hits}x  ({'PASS' if hits==1 else 'FAIL'})")
if hits != 1: fails.append("edit path regressed")

# REGRESSION: unrelated tool still ignored
sid = "ctl-other-" + uuid.uuid4().hex[:8]
hits = feed("Read", "file_path", "/tmp/x", sid, 20)
print(f"  REGRESSION 20x Read               -> fired {hits}x  ({'PASS' if hits==0 else 'FAIL'})")
if hits: fails.append("unrelated tool fired")

# SCOPE: one large write fires on its own, and the message points at something that
# exists on a stock install: the Agent tool and rules/subagent-models.md.
sid = "ctl-msg-" + uuid.uuid4().hex[:8]
p = {"tool_name": "Write", "tool_input": {"content": "x\n" * 200}, "session_id": sid}
out = subprocess.run([sys.executable, HOOK], input=json.dumps(p), capture_output=True, text=True, env=ENV).stdout
need = [w for w in ("Agent tool", "rules/subagent-models.md") if w not in out]
ok = "additionalContext" in out and not need
print(f"  SCOPE     big write message       -> {'PASS' if ok else 'FAIL'}{' (missing ' + ', '.join(need) + ')' if need else ''}")
if not ok: fails.append("big write did not fire, or the message does not point at the Agent tool")

shutil.rmtree(STATE, ignore_errors=True)
print()
if fails:
    print("CONTROL FAILED: " + "; ".join(fails)); sys.exit(1)
print("CONTROL PASSED in both directions.")
