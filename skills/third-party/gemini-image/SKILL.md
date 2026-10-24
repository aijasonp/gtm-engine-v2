---
name: gemini-image
description: Generate or edit images via Gemini API (image generation models). Use when asked to create, combine, edit, or generate images. Supports multi-image input for composition/editing.
---

# Gemini Image Generation

Generate or edit images using Google's Gemini image generation models. Uses only Python stdlib — no external dependencies.

## API Key

Read from `skills.entries.nano-banana-pro.apiKey` in `~/.openclaw/openclaw.json`.

## Generate

```bash
python3 {baseDir}/scripts/gen_image.py --prompt "description" --output "output.png"
```

## Edit / Combine (multi-image input)

```bash
python3 {baseDir}/scripts/gen_image.py --prompt "combine these" --output "output.png" -i img1.png -i img2.png
```

## Options

- `--model` — Gemini model (default: `gemini-3-pro-image-preview`)
- `--output` / `-o` — Output file path (required)
- `--prompt` / `-p` — Image description or edit instructions (required)
- `--input` / `-i` — Input image(s) for editing/composition (repeatable, up to 14)

## Models

- `gemini-3-pro-image-preview` — Best quality, 1024x1024 output (default)
- `gemini-2.5-flash-image` — Faster but lower quality/resolution
- `nano-banana-pro-preview` — Alias for gemini-3-pro

## Notes

- Always request square dimensions in the prompt for profile pictures/avatars.
- The script prints `MEDIA: <path>` for OpenClaw auto-attachment.
- No `uv run` or pip dependencies — stdlib only (urllib, json, base64).
