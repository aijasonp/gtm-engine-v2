#!/usr/bin/env python3
"""
frame_audit.py — Multimodal critique loop for HyperFrames renders.

Pattern adopted from damkina7's "Autonomous Motion Studio" article (2026-10-07).
Renders -> extract checkpoint frames -> multimodal audit -> score -> patch notes.

Usage:
    python3 frame_audit.py <video.mp4> [--checkpoints 1.5,4,8.5,14] \\
        [--brief "what this video is supposed to do"] \\
        [--out audit.json] [--min-score 8] [--model claude-sonnet-4-6]

Exit codes: 0 = pass (avg score >= min), 1 = fail (score below), 2 = error.

Writes audit JSON with per-frame findings + consolidated patch plan.
Optional: emits frame stills next to the video as .audit/frame-XX.png.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

COMPANY_BASE = "https://llm.example.com/v1/chat/completions"
UA = "Mozilla/5.0 (X11; Linux x86_64) OpenClaw/1.0"


def sh(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"cmd failed: {cmd}\nstdout:{r.stdout}\nstderr:{r.stderr}")
    return r


def get_duration(mp4):
    out = sh(f"ffprobe -v error -show_entries format=duration "
             f"-of default=noprint_wrappers=1:nokey=1 '{mp4}'").stdout.strip()
    return float(out)


def extract_frame(mp4, t, out_path, width=768):
    # JPEG at modest width keeps 4 frames under the API payload limit while
    # staying legible enough for layout/contrast checks.
    sh(f"ffmpeg -y -v error -ss {t} -i '{mp4}' -frames:v 1 "
       f"-vf 'scale={width}:-2' -q:v 4 '{out_path}'")


def default_checkpoints(dur):
    # 10%, 30%, 60%, 90% of runtime — 4 stills is the sweet spot per the article.
    return [round(dur * f, 2) for f in (0.10, 0.30, 0.60, 0.90)]


def audit_frames(frames, brief, model, api_key, extra_checks=None):
    checks = extra_checks or [
        "Typographic contrast: is any text low-contrast against its background?",
        "Layout collisions: are any elements overlapping unintentionally or clipped at the edges?",
        "Inertia/settle: do animated elements appear frozen mid-motion or landed cleanly?",
        "Brand drift: does the palette/typography look like generic AI output instead of the intended brand?",
        "Black/blank frames or unintended empty space",
        "Motion feel: does this frame suggest dead linear easing vs physical spring motion?",
    ]
    checks_block = "\n".join(f"{i+1}. {c}" for i, c in enumerate(checks))

    prompt = f"""You are a motion-design director auditing still frames from a product video.

Video brief:
{brief or '(no brief provided — judge on general launch-video craft)'}

I'm attaching {len(frames)} frames extracted at fixed checkpoints. For EACH frame, answer the checks below, then give a 1-10 polish score.

Checks per frame:
{checks_block}

Then give a CONSOLIDATED verdict across all frames:
- avg_score (1-10, one decimal)
- top_defects (the 2 most glaring issues across the whole video)
- patch_plan (concrete, code-level fixes — name the file/element/timing to change, not vibes)

Respond ONLY with valid JSON of this exact shape:
{{
  "frames": [
    {{"t": <seconds>, "score": <1-10>, "issues": [<string>], "notes": <string>}}
  ],
  "avg_score": <float>,
  "top_defects": [<string>, <string>],
  "patch_plan": [<string>]
}}"""

    content = [{"type": "text", "text": prompt}]
    for (t, png_path) in frames:
        with open(png_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content.append({"type": "text", "text": f"Frame at t={t}s:"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })

    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 4096,
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        COMPANY_BASE,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
    )
    raw = urllib.request.urlopen(req, timeout=240).read()
    data = json.loads(raw)
    choice = data["choices"][0]
    text = choice["message"]["content"].strip()
    finish = choice.get("finish_reason")

    # Strip markdown fences if the model added them despite instructions.
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()

    try:
        return json.loads(text), data.get("usage", {})
    except json.JSONDecodeError as e:
        # Salvage: if the model got cut off mid-JSON, try to close it cleanly.
        # This keeps the loop usable instead of dying on a long patch plan.
        salvaged = text
        for closer in ("]}", "\"]}\n", "}"):
            try:
                return json.loads(salvaged + closer), data.get("usage", {})
            except json.JSONDecodeError:
                continue
        raise RuntimeError(
            f"Unparseable audit JSON (finish={finish}): {e}\n"
            f"First 400 chars: {text[:400]}\nLast 400 chars: {text[-400:]}"
        )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video", help="Path to rendered MP4")
    p.add_argument("--checkpoints", help="Comma-separated seconds (default: 10/30/60/90%)")
    p.add_argument("--brief", default="", help="What this video is supposed to accomplish")
    p.add_argument("--out", help="Write audit JSON here (default: <video>.audit.json)")
    p.add_argument("--min-score", type=float, default=8.0)
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--frames-dir", help="Keep extracted frames here (default: tempdir)")
    args = p.parse_args()

    mp4 = Path(args.video).resolve()
    if not mp4.exists():
        print(f"ERROR: {mp4} not found", file=sys.stderr)
        sys.exit(2)

    api_key = os.environ.get("COMPANY_API_KEY")
    if not api_key:
        # Fall back to ~/.openclaw/.env
        env_path = Path.home() / ".openclaw" / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("COMPANY_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        print("ERROR: COMPANY_API_KEY not set", file=sys.stderr)
        sys.exit(2)

    dur = get_duration(str(mp4))
    if args.checkpoints:
        checkpoints = [float(x) for x in args.checkpoints.split(",")]
    else:
        checkpoints = default_checkpoints(dur)

    frames_dir = Path(args.frames_dir) if args.frames_dir else Path(
        tempfile.mkdtemp(prefix="frame_audit_"))
    frames_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    for t in checkpoints:
        if t >= dur:
            continue
        out = frames_dir / f"frame-{t:06.2f}s.jpg"
        extract_frame(str(mp4), t, str(out))
        frames.append((t, str(out)))

    if not frames:
        print("ERROR: no frames extracted", file=sys.stderr)
        sys.exit(2)

    print(f"Extracted {len(frames)} frames from {mp4.name} (dur={dur:.2f}s)")

    try:
        audit, usage = audit_frames(frames, args.brief, args.model, api_key)
    except Exception as e:
        print(f"ERROR during audit: {e}", file=sys.stderr)
        sys.exit(2)

    audit["_meta"] = {
        "video": str(mp4),
        "duration_s": dur,
        "checkpoints": checkpoints,
        "model": args.model,
        "usage": usage,
        "frames_dir": str(frames_dir),
        "min_score": args.min_score,
    }

    out_path = Path(args.out) if args.out else mp4.with_suffix(mp4.suffix + ".audit.json")
    out_path.write_text(json.dumps(audit, indent=2))

    avg = audit.get("avg_score", 0)
    verdict = "PASS" if avg >= args.min_score else "FAIL"
    print(f"\n=== {verdict} — avg score {avg}/10 (min {args.min_score}) ===")
    for f in audit.get("frames", []):
        print(f"  t={f.get('t'):>5}s  score={f.get('score')}/10  issues={len(f.get('issues', []))}")
    if audit.get("top_defects"):
        print("\nTop defects:")
        for d in audit["top_defects"]:
            print(f"  - {d}")
    if audit.get("patch_plan"):
        print("\nPatch plan:")
        for i, p in enumerate(audit["patch_plan"], 1):
            print(f"  {i}. {p}")
    print(f"\nAudit JSON: {out_path}")

    sys.exit(0 if avg >= args.min_score else 1)


if __name__ == "__main__":
    main()
