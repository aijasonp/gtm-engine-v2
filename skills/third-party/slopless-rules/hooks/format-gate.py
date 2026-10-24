#!/usr/bin/env python3
"""
format-gate.py - PostToolUse hook. Formats an edited source file, but ONLY with a
formatter the project itself configures, and reports what it did.

WHY THIS REPLACED THE SHELL ONE-LINER
-------------------------------------
The old hook was a `case` statement in settings.json ending every branch in
`2>/dev/null || true`. It had two defects, both found by running controls
against it rather than by reading it.

1. IT REFORMATTED REPOS THAT NEVER ASKED FOR IT. Plain `npx prettier --write`
   resolves from npm's cache even when the project has no prettier config, and
   then applies prettier's DEFAULTS. A repo written at ~120 columns met
   prettier's 80, and editing one 113-line file would have produced a 48-line
   formatting diff, none of it related to the change. That is the single most
   reliable way to get a pull request rejected on sight, and the hook did it
   silently on the first edit.

2. IT COULD NOT FAIL. `2>/dev/null || true` swallowed everything, so eslint -
   which is not installed and cannot run non-interactively - had never executed
   once, and nothing said so. An instrument that cannot fail certifies whatever
   you point it at (METHOD.md).

THE RULE HERE: a formatter runs only where the project opted in.
- prettier / eslint / ruff / biome: require a config file in the repo, or the
  matching key in package.json / pyproject.toml.
- gofmt / rustfmt: unconditional. They are the language's single canonical style,
  there is nothing to disagree with, and Go and Rust repos already expect them.

It WARNS and never blocks. A formatting difference is not worth stopping a turn
over, but a silent rewrite of someone else's file is worth being told about.

    --selftest   run the built-in controls (both directions) and exit
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# suffix -> (marker files, package.json / pyproject key, argv template)
# A marker is a filename the project puts in a directory at or above the file.
PRETTIER_MARKERS = (
    ".prettierrc", ".prettierrc.json", ".prettierrc.yml", ".prettierrc.yaml",
    ".prettierrc.json5", ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.mjs",
    ".prettierrc.toml", "prettier.config.js", "prettier.config.cjs",
    "prettier.config.mjs",
)
ESLINT_MARKERS = (
    "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs",
    "eslint.config.ts", ".eslintrc", ".eslintrc.js", ".eslintrc.cjs",
    ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml",
)
RUFF_MARKERS = ("ruff.toml", ".ruff.toml")
BIOME_MARKERS = ("biome.json", "biome.jsonc")

JS_LIKE = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
WEB_LIKE = {".json", ".css", ".scss", ".html", ".md", ".yaml", ".yml"}


def find_up(start, names):
    """First directory at or above `start` holding any of `names`, stopping at the repo root.

    Without the stop, a `~/.prettierrc` or a home-level pyproject.toml would opt
    every repo below it into a formatter it never asked for.
    """
    for parent in [start] + list(start.parents):
        for name in names:
            if (parent / name).exists():
                return parent / name
        if (parent / ".git").exists():
            break
    return None


def package_json_has(start, key):
    found = find_up(start, ("package.json",))
    if not found:
        return False
    try:
        return key in json.loads(found.read_text())
    except Exception:
        return False


def pyproject_has_ruff(start):
    found = find_up(start, ("pyproject.toml",))
    if not found:
        return False
    try:
        return "[tool.ruff" in found.read_text()
    except Exception:
        return False


def planned_commands(path):
    """The formatters this project has opted into for this file. May be empty."""
    suffix = path.suffix.lower()
    here = path.parent
    cmds = []

    if suffix == ".go":
        cmds.append(["gofmt", "-w", str(path)])
    elif suffix == ".rs":
        cmds.append(["rustfmt", str(path)])
    elif suffix in JS_LIKE or suffix in WEB_LIKE:
        if find_up(here, BIOME_MARKERS):
            cmds.append(["npx", "--no-install", "biome", "format", "--write", str(path)])
        else:
            if suffix in JS_LIKE and find_up(here, ESLINT_MARKERS):
                cmds.append(["npx", "--no-install", "eslint", "--fix", str(path)])
            if find_up(here, PRETTIER_MARKERS) or package_json_has(here, "prettier"):
                cmds.append(["npx", "--no-install", "prettier", "--write", str(path)])
    elif suffix in {".py", ".pyi"}:
        if find_up(here, RUFF_MARKERS) or pyproject_has_ruff(here):
            cmds.append(["ruff", "check", "--fix", str(path)])
            cmds.append(["ruff", "format", str(path)])

    return cmds


def run(path):
    """Format in place. Returns human-readable notes about anything worth saying."""
    notes = []
    before = path.read_bytes()

    for cmd in planned_commands(path):
        # A missing binary is not a failure. The project asked for it; the machine
        # does not have it. Say so once rather than pretending the file was checked.
        if cmd[0] != "npx" and shutil.which(cmd[0]) is None:
            notes.append(f"{cmd[0]} is configured for this project but not installed")
            continue
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except Exception as err:
            notes.append(f"{cmd[0]} could not run: {err}")
            continue
        # eslint --fix exits non-zero on problems it could not fix. That is the
        # signal the old hook threw away, and it is the one worth surfacing.
        if done.returncode != 0:
            detail = (done.stdout or done.stderr or "").strip().splitlines()
            if detail:
                notes.append(f"{cmd[0]} reported: " + " | ".join(detail[:6]))

    if path.read_bytes() != before:
        notes.append(f"reformatted by the project's own formatter: {path.name}")
    return notes


def target_from_env(payload):
    raw = os.environ.get("CLAUDE_TOOL_FILE_PATH") or (
        payload.get("tool_input", {}).get("file_path")
    )
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def selftest():
    """Both directions, on real shapes. A gate run only on its deny cases is half a control."""
    import tempfile

    ok = True

    def check(label, condition):
        nonlocal ok
        print(f"  {'PASS' if condition else 'FAIL'}  {label}")
        ok = ok and condition

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # DENY side: a JS repo with no formatter config must get no commands.
        bare = root / "bare"
        bare.mkdir()
        (bare / "package.json").write_text('{"name":"bare"}')
        wide = bare / "wide.js"
        wide.write_text("const a = 1;\n")
        check("js repo with no prettier config -> no formatter runs", planned_commands(wide) == [])

        # ALLOW side: the same repo, opted in, must get prettier.
        (bare / ".prettierrc").write_text("{}")
        cmds = planned_commands(wide)
        check("js repo WITH .prettierrc -> prettier runs", any("prettier" in c for c in cmds))

        # package.json key is the other opt-in shape.
        keyed = root / "keyed"
        keyed.mkdir()
        (keyed / "package.json").write_text('{"name":"k","prettier":{"semi":false}}')
        f2 = keyed / "b.js"
        f2.write_text("const b = 2;\n")
        check("prettier key in package.json -> prettier runs",
              any("prettier" in c for c in planned_commands(f2)))

        # Config in a PARENT directory must count; source rarely sits at the root.
        nested = bare / "src" / "deep"
        nested.mkdir(parents=True)
        f3 = nested / "c.js"
        f3.write_text("const c = 3;\n")
        check("config in an ancestor directory is found",
              any("prettier" in c for c in planned_commands(f3)))

        # A config ABOVE the repo root must not count: the repo never opted in.
        outer = root / "outer"
        repo = outer / "repo"
        (repo / ".git").mkdir(parents=True)
        (outer / ".prettierrc").write_text("{}")
        (repo / "package.json").write_text('{"name":"r"}')
        f4 = repo / "d.js"
        f4.write_text("const d = 4;\n")
        check("config above the repo root is ignored", planned_commands(f4) == [])

        # Python without ruff config stays untouched; with it, runs.
        py = root / "py"
        py.mkdir()
        p1 = py / "m.py"
        p1.write_text("x = 1\n")
        check("python with no ruff config -> no formatter runs", planned_commands(p1) == [])
        (py / "ruff.toml").write_text("line-length = 100\n")
        check("python WITH ruff.toml -> ruff runs",
              any("ruff" in c for c in planned_commands(p1)))

        # Language-canonical formatters need no opt-in.
        g = root / "g.go"
        g.write_text("package main\n")
        check("go always formats", any("gofmt" in c for c in planned_commands(g)))

    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())

    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    target = target_from_env(payload)
    if target is None:
        sys.exit(0)

    try:
        messages = run(target)
    except Exception:
        sys.exit(0)  # fail open: a formatter must never break a turn

    if messages:
        print(json.dumps({"systemMessage": "format-gate: " + "; ".join(messages)}))
    sys.exit(0)
