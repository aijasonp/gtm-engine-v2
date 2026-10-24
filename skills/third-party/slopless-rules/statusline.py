#!/usr/bin/env python3
"""Claude Code status line. Reads the JSON Claude Code passes on stdin; stdlib only, no API
calls, no transcript parsing.

Shows: directory and git branch, model and effort, context bar with tokens and the
autoCompactWindow point, 5h and 7d rate-limit windows, cost and burn rate, prompt-cache hit
ratio and time to expiry, agent and vim mode. Segments drop right-to-left by priority when the
terminal is narrow.

Wire it in settings.json:  "statusLine": {"type": "command", "command": "python3 ~/.claude/statusline.py"}
"""
import json
import os
import subprocess
import sys
import tempfile
import time

# palette: 256-colour
OK, WARN, HOT = 108, 179, 167      # #87af87 #d7af5f #d75f5f
DIR, BRANCH, MODEL, DIM = 110, 108, 180, 244
RESET = "\033[0m"


def c(n, text, bold=False):
    return f"\033[{'1;' if bold else ''}38;5;{n}m{text}{RESET}"


def level(pct):
    return HOT if pct >= 85 else WARN if pct >= 60 else OK


def tok(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k"
    return str(int(n))


def dur(seconds):
    m = max(0, round(seconds / 60))
    if m >= 1440:
        return f"{m // 1440}d{(m % 1440) // 60}h"
    if m >= 60:
        return f"{m // 60}h{m % 60:02d}m"
    return f"{m}m"


def bar(pct, width=8):
    filled = max(0, min(width, round(pct / 100 * width)))
    return "▰" * filled + "▱" * (width - filled)


def epoch(v):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v / 1000 if v > 1e12 else v


def dig(d, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def git_info(cwd, sid):
    """Branch and dirty flag, cached 10s per session so a repaint never waits on git."""
    cache = os.path.join(tempfile.gettempdir(), f"cc-sl-git-{sid or 'x'}")
    try:
        if time.time() - os.path.getmtime(cache) < 10:
            with open(cache) as fh:
                data = json.load(fh)
            if data.get("cwd") == cwd:
                return data.get("branch"), data.get("dirty")
    except Exception:
        pass
    branch, dirty = None, False
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True, timeout=1)
        if r.returncode == 0:
            branch = r.stdout.strip() or None
        if branch:
            s = subprocess.run(["git", "-C", cwd, "status", "--porcelain", "-uno"],
                               capture_output=True, text=True, timeout=1)
            dirty = bool(s.stdout.strip())
    except Exception:
        pass
    try:
        with open(cache, "w") as fh:
            json.dump({"cwd": cwd, "branch": branch, "dirty": dirty}, fh)
    except Exception:
        pass
    return branch, dirty


def compact_window():
    try:
        with open(os.path.expanduser("~/.claude/settings.json")) as fh:
            v = json.load(fh).get("autoCompactWindow")
        return v if isinstance(v, (int, float)) and v > 0 else None
    except Exception:
        return None


def build(d):
    now = time.time()
    segs = []  # (plain_len, rendered) in priority order

    def add(plain, rendered):
        segs.append((len(plain), rendered))

    # 1. directory + branch
    cwd = dig(d, "workspace", "current_dir") or d.get("cwd") or os.getcwd()
    name = os.path.basename(cwd.rstrip("/")) or cwd
    branch, dirty = git_info(cwd, d.get("session_id"))
    plain, rend = name, c(DIR, name, bold=True)
    if branch:
        b = branch + ("*" if dirty else "")
        plain += f" ⎇ {b}"
        rend += " " + c(BRANCH, f"⎇ {b}")
    add(plain, rend)

    # 2. model + effort
    model = dig(d, "model", "display_name") or dig(d, "model", "id")
    if model:
        effort = dig(d, "effort", "level")
        plain = model + (f" · {effort}" if effort else "")
        rend = c(MODEL, model) + (c(DIM, f" · {effort}") if effort else "")
        add(plain, rend)

    # 3. context: bar, %, tokens/window, compaction point
    pct = dig(d, "context_window", "used_percentage")
    size = dig(d, "context_window", "context_window_size")
    cu = dig(d, "context_window", "current_usage") or {}
    used = sum(cu.get(k) or 0 for k in
               ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    if pct is None and size and used:
        pct = used * 100 / size
    if pct is not None:
        pct = float(pct)
        body = f"{bar(pct)} {round(pct)}%"
        plain = f"ctx {body}"
        rend = c(DIM, "ctx ") + c(level(pct), body)
        if used and size:
            t = f" {tok(used)}/{tok(size)}"
            plain += t
            rend += c(DIM, t)
        ca = compact_window()
        if ca and used:
            t = f" ⟲{tok(ca)}"
            plain += t
            rend += c(HOT if used / ca >= 0.9 else WARN if used / ca >= 0.75 else DIM, t)
        add(plain, rend)

    # 4-5. rate-limit windows (subscription only, after the first response)
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        w = dig(d, "rate_limits", key)
        if isinstance(w, dict) and w.get("used_percentage") is not None:
            p = float(w["used_percentage"])
            plain = f"{label} {round(p)}%"
            rend = c(DIM, f"{label} ") + c(level(p), f"{round(p)}%")
            r = epoch(w.get("resets_at"))
            if r:
                t = f" ↻{dur(r - now)}"
                plain += t
                rend += c(DIM, t)
            add(plain, rend)

    # 6. cost and burn rate
    cost = dig(d, "cost", "total_cost_usd")
    if cost is not None:
        plain = f"${cost:.2f}"
        rend = c(DIM, plain)
        ms = dig(d, "cost", "total_duration_ms") or 0
        if ms >= 360_000:
            t = f" · ${cost / (ms / 3_600_000):.1f}/h"
            plain += t
            rend += c(DIM, t)
        add(plain, rend)

    # 7. prompt cache: hit ratio and time to expiry
    pc = d.get("prompt_cache")
    if isinstance(pc, dict) and pc.get("hit_ratio") is not None:
        h = float(pc["hit_ratio"]) * 100
        colour = OK if h >= 70 else WARN if h >= 40 else HOT
        plain = f"cache {round(h)}%"
        rend = c(DIM, "cache ") + c(colour, f"{round(h)}%")
        exp = epoch(pc.get("expires_at"))
        if pc.get("warm") and exp:
            t = f" ♨{dur(exp - now)}"
            plain += t
            rend += c(DIM, t)
        elif pc.get("warm") is False:
            plain += " ❄"
            rend += c(HOT, " ❄")
        add(plain, rend)

    # 8. agent / vim, only when present
    tail = []
    if dig(d, "agent", "name"):
        tail.append("agent " + d["agent"]["name"])
    if dig(d, "vim", "mode"):
        tail.append(d["vim"]["mode"])
    if tail:
        t = " · ".join(tail)
        add(t, c(DIM, t))

    return segs


def render(segs, width):
    sep_plain, sep = " │ ", c(240, " │ ")
    out, used = [], 0
    for plain_len, rendered in segs:
        need = plain_len + (len(sep_plain) if out else 0)
        if out and used + need > width:
            break
        out.append(rendered)
        used += need
    return sep.join(out)


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        d = {}
    try:
        width = int(os.environ.get("COLUMNS", "0")) or 200
    except ValueError:
        width = 200
    line = render(build(d), width - 2)
    if line:
        print(line)


if __name__ == "__main__":
    main()
