#!/usr/bin/env python3
"""
PostToolUse delegate nudge.

rules/subagent-models.md says AUTO-ROUTE bounded work to a subagent and keep main
context for the spec, the plan and the review. A standing rule the model reads every
turn still loses to the habit of just doing the edits inline: passive text does not
fire under load. This hook fires at the moment it matters: once a session has done
enough hands-on work to clear the auto-route anchor, it injects ONE advisory line into
Claude's context. Zero prompts for the human (additionalContext only, never `ask`).
Fires once per session; self-instruments to fires.log so its hit rate can be watched.

The nudge points at the Agent tool with an explicit model (sonnet for code, haiku for
mechanical work). It names no custom agent, so it works on a stock install.

Two surfaces, counted separately:
  - Edit/Write/MultiEdit: cumulative file edits, or one large write.
  - Bash: only remote/stateful verbs (ssh, docker, kubectl, psql, systemctl, ...).
    Read-only local shapes (ls/cat/grep/git status) are NOT counted: a nudge that
    fires on `ls` gets muted, and a muted gate is the same end state as no gate.

Off-switch: `touch ~/.claude/.delegate-nudge-off` (or export DELEGATE_NUDGE=off).
State dir override (tests): DELEGATE_NUDGE_STATE=<dir>.
Rollback: unregister from settings.json and/or delete this file. FAIL-OPEN throughout.
Control: python3 hooks/test_delegate_nudge.py (both directions).
"""
import json, os, re, sys, time, glob

STATE_DIR = os.environ.get("DELEGATE_NUDGE_STATE") or os.path.expanduser("~/.claude/.delegate-nudge")
OFF_FLAG  = os.path.expanduser("~/.claude/.delegate-nudge-off")
FIRE_LOG  = os.path.join(STATE_DIR, "fires.log")
EDIT_THRESHOLD = 8     # cumulative Edit/Write/MultiEdit calls in one session
BIGWRITE_LINES = 150   # a single write this large is delegable on its own

BASH_THRESHOLD = 10    # cumulative delegable-shaped Bash calls in one session
BASH_VERBS = re.compile(
    r"(?:^|[|;&]\s*|\$\(\s*)(ssh|scp|rsync|psql|mysql|docker|podman|systemctl|"
    r"launchctl|pg_dump|pg_restore|kubectl|terraform|ansible)\b")
# A read-only probe over ssh still counts: the threshold sits far above normal traffic, so
# inflating it slightly is cheaper than parsing the remote command and getting that wrong.


def allow():
    sys.exit(0)


def bigwrite(tool, ti):
    if tool == "MultiEdit":
        content = "\n".join(e.get("new_string", "") for e in (ti.get("edits") or []))
    else:
        content = ti.get("content") or ti.get("new_string") or ""
    return content.count("\n") + 1 >= BIGWRITE_LINES


if os.path.exists(OFF_FLAG) or os.environ.get("DELEGATE_NUDGE") == "off":
    allow()

try:
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "") or ""
    ti = data.get("tool_input", {}) or {}
    sid = data.get("session_id") or "nosession"
except Exception:
    allow()  # fail-open: never wedge a tool on a parse error

IS_BASH = tool == "Bash"
if tool not in ("Edit", "Write", "MultiEdit", "Bash"):
    allow()

if IS_BASH and not BASH_VERBS.search(ti.get("command") or ""):
    allow()  # local read-only shell is not a delegable ops sequence

n, big = 0, False
try:
    os.makedirs(STATE_DIR, exist_ok=True)
    # opportunistic cleanup: drop per-session state older than 7 days
    cutoff = time.time() - 7 * 86400
    for f in glob.glob(os.path.join(STATE_DIR, "*")):
        try:
            if os.path.basename(f) != "fires.log" and os.path.getmtime(f) < cutoff:
                os.remove(f)
        except Exception:
            pass

    cfile = os.path.join(STATE_DIR, sid + (".bash" if IS_BASH else ""))
    fired = os.path.join(STATE_DIR, sid) + ".fired"  # one nudge per session, either surface
    if os.path.exists(fired):
        allow()  # already nudged this session: one line, once

    if os.path.exists(cfile):
        try:
            n = int((open(cfile).read().strip() or "0"))
        except Exception:
            n = 0
    n += 1
    open(cfile, "w").write(str(n))

    big = (not IS_BASH) and bigwrite(tool, ti)
    threshold = BASH_THRESHOLD if IS_BASH else EDIT_THRESHOLD
    if n < threshold and not big:
        allow()

    open(fired, "w").write(str(time.time()))
    try:
        open(FIRE_LOG, "a").write(
            f"{time.strftime('%Y-%m-%d %H:%M')} sid={sid} "
            f"{'bash' if IS_BASH else 'edit'}={n} big={int(big)}\n")
    except Exception:
        pass
except Exception:
    allow()  # fail-open on any state error

if IS_BASH:
    trigger = f"{n} remote/stateful shell calls (ssh/docker/kubectl/systemctl class)"
    shape = "≥5 shell or remote calls with a known sequence"
else:
    trigger = "a large single write" if big else f"{n} file edits"
    shape = "≥3 files / ≥80 lines / ≥5 similar items"
reason = (
    f"DELEGATE NUDGE (advisory, no user action): this session has done substantial "
    f"hands-on work in main context ({trigger}). If the REMAINING work is a bounded, "
    f"spec-able batch ({shape}) in a git repo or on a known host, hand it to a subagent "
    f"via the Agent tool per rules/subagent-models.md, with an explicit model (sonnet for "
    f"code, haiku for mechanical work). Main context keeps the spec, the git-diff review "
    f"and the gate. The delegation moment is the "
    f"boundary where discovery ends and execution begins: a plan being agreed IS the "
    f"dispatch signal, not permission to start typing. IGNORE if the work is iterative / "
    f"voice / judgment / architecture, below the anchor, or you have already delegated "
    f"this session."
)
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PostToolUse", "additionalContext": reason}}))
sys.exit(0)
