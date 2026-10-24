#!/usr/bin/env python3
"""
Generate/combine images via Gemini API using only stdlib.
No external dependencies — just urllib, json, base64.
"""
import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path


def load_api_key():
    """Read Gemini API key from OpenClaw config."""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    with open(config_path) as f:
        config = json.load(f)
    return config["skills"]["entries"]["nano-banana-pro"]["apiKey"]


def encode_image(path: str) -> tuple[str, str]:
    """Read and base64-encode an image file. Returns (b64_data, mime_type)."""
    p = Path(path)
    suffix = p.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp", ".svg": "image/svg+xml"}
    mime = mime_map.get(suffix, "image/png")
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode(), mime


def main():
    parser = argparse.ArgumentParser(description="Generate images via Gemini API")
    parser.add_argument("--prompt", "-p", required=True)
    parser.add_argument("--output", "-o", required=True)
    parser.add_argument("--input", "-i", action="append", dest="inputs", default=[])
    parser.add_argument("--model", default="gemini-3-pro-image-preview")
    args = parser.parse_args()

    api_key = load_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{args.model}:generateContent?key={api_key}"

    # Build parts: input images first, then text prompt
    parts = []
    for img_path in args.inputs:
        b64, mime = encode_image(img_path)
        parts.append({"inlineData": {"mimeType": mime, "data": b64}})
    parts.append({"text": args.prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        }
    }

    print(f"Sending request to Gemini ({args.model})...")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"API error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)

    # Extract image from response
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image_saved = False

    for candidate in result.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "text" in part:
                print(f"Model: {part['text']}")
            elif "inlineData" in part:
                img_data = base64.b64decode(part["inlineData"]["data"])
                with open(output_path, "wb") as f:
                    f.write(img_data)
                image_saved = True

    if image_saved:
        full_path = output_path.resolve()
        print(f"\nImage saved: {full_path}")
        print(f"MEDIA: {full_path}")
    else:
        print("Error: No image in response", file=sys.stderr)
        print(json.dumps(result, indent=2)[:2000], file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
