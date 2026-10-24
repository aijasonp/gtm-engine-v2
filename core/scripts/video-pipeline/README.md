# Video Pipeline — Frame Audit Critique Loop

Multimodal self-critique for HyperFrames renders. Adopted from damkina7's
"Autonomous Motion Studio" pattern (2026-10-07): render → extract checkpoint
frames → multimodal audit → score → patch plan. Two passes minimum before a
human reviews the export.

## Components

### `frame_audit.py`

Single-file Python script, stdlib only (no pip installs). Uses {{COMPANY}} API
(`claude-sonnet-4-6` by default — vision-capable and cheap) as the auditor.

```bash
python3 scripts/video-pipeline/frame_audit.py <video.mp4> \
  [--checkpoints 1.5,4,8.5,14] \   # default: 10/30/60/90% of duration
  [--brief "what the video should accomplish"] \
  [--min-score 8] \                # PASS threshold (exit 0), FAIL exit 1
  [--model claude-sonnet-4-6] \
  [--frames-dir /tmp/audit-frames] \
  [--out audit.json]
```

Per frame it checks: typographic contrast, layout collisions, inertia/settle
(frozen mid-animation?), brand drift, blank/dead frames, dead linear easing.
Then it consolidates: `avg_score`, `top_defects` (the two most damaging), and
`patch_plan` (code-level fixes — file/element/timing, not vibes).

Exit code is the gate: 0 = ship, 1 = patch and re-render.

## Wired into the workflow

Use it after any HyperFrames render and before showing a human:

```bash
npx hyperframes render -o renders/v1.mp4
python3 ~/.openclaw/workspace/scripts/video-pipeline/frame_audit.py \
  renders/v1.mp4 \
  --brief "$(cat brief.md)" || echo "needs patch pass"
```

If it fails, apply the patch_plan to the composition, re-render, re-audit.
The smoke test on `demo-v15.mp4` caught a frozen
spinner, a white-on-orange contrast failure, an unanchored asterisk, and a
double-period typo on the hero overlay — none of which were caught by eye.

## Installed skill kits (2026-10-12)

- `skills/product-launch-motion/` — AbubakrChan's launch-film director skill
  (script → word-locked VO sync → camera moves → grade → master). 14-shot
  catalog + 34-trap index in `references/`. MIT.
- `skills/hyperframes-student-kit/` — nateherkai's kit: transcript-driven
  editing, silence/mistake cutting, 406-card motion-graphics style library,
  short-form-edit and motion-showreel skills. The seven useful skills are
  symlinked to `skills/hf-<name>/` for OpenClaw discovery.

Skipped from the X threads: three.js/fabric.js/deck.gl (we render through
HyperFrames, not raw WebGL), react/motion (not our use case), the official
GSAP/Lottie skills (HyperFrames abstracts them), motion-graphics-skills
(overlaps HyperFrames).

## Model choice

Default `claude-sonnet-4-6` via {{COMPANY}}. ~26 models on the gateway support
vision; sonnet-4-6 is the cheapest reliable multimodal one. Per audit ≈
4 frames × ~1.5k image tokens + ~2k text = pennies. Bump to `claude-opus-4-8`
for hero frames where the audit itself needs more judgment. The {{COMPANY}} gateway
needs a browser User-Agent or it 403s (Cloudflare 1010) — already handled in
the script.

## Known limits

- Frame extraction uses `-ss` before `-i` (fast seek). On heavy codecs this
  can land ±1 frame off — fine for layout/contrast checks, not for beat-sync
  verification.
- The audit checks stills, not motion. A composition can pass every frame and
  still have a janky cut between them. Beat-sync and transition feel still
  need a human watch or a future video-native model pass.
- Long patch plans can truncate the model's JSON. The script salvages what it
  can; if it hard-fails, rerun with a tighter `--brief`.
