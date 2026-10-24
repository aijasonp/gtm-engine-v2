---
name: browser-video
description: Record browser videos with overlays, click highlights, zoom, and custom cursor. Produces polished demo/walkthrough videos from a choreography script or quick URL capture. Powered by Playwright + ffmpeg.
---

# Browser Video Recording

Record browser interactions as polished demo videos. Supports text overlays, click highlights, zoom effects, step indicators, element highlighting, and a custom visible cursor.

## Dependencies

- Playwright Chromium: `npx playwright install chromium`
- ffmpeg: `brew install ffmpeg` (for webm → mp4 conversion)
- Node modules: `cd {baseDir} && npm install` (playwright pinned at 1.58.2)

## Quick Capture

```bash
node {baseDir}/scripts/record.mjs --url "http://localhost:3000" --duration 10 --output demo.mp4
```

Options:
- `--url <url>` — Page to record (required)
- `--duration <seconds>` — Recording length (default: 10)
- `--output <path>` — Output .mp4 path (default: recording.mp4)
- `--width <px>` — Viewport width (default: 1280)
- `--height <px>` — Viewport height (default: 720)
- `--scroll` — Auto-scroll the page slowly during recording
- `--title <text>` — Show a title card at the start
- `--headed` — Show browser window (default: headless)

## Choreography Mode

```bash
node {baseDir}/scripts/record.mjs choreography.json
```

### Choreography JSON Format

```json
{
  "viewport": { "width": 1280, "height": 720 },
  "output": "demo.mp4",
  "deviceScaleFactor": 2,
  "colorScheme": "dark",
  "headed": false,
  "scenes": [
    {
      "url": "http://localhost:3000",
      "waitUntil": "networkidle",
      "actions": [
        { "type": "overlay", "text": "Dashboard Overview", "style": "title", "position": "center" },
        { "type": "wait", "ms": 3000 },
        { "type": "removeOverlay" },
        { "type": "overlay", "text": "4 active routes processing events", "style": "subtitle", "position": "bottom" },
        { "type": "click", "selector": "#metrics-tab", "highlight": true },
        { "type": "zoom", "selector": "#chart-panel", "scale": 1.5, "duration": 800 },
        { "type": "wait", "ms": 2000 },
        { "type": "zoomReset", "duration": 600 },
        { "type": "scroll", "y": 400, "smooth": true }
      ]
    }
  ]
}
```

### Available Actions

| Action | Description | Key Properties |
|--------|------------|----------------|
| `wait` | Pause recording | `ms` (milliseconds) |
| `navigate` | Go to URL | `url`, `waitUntil` |
| `click` | Click element with ripple effect | `selector`, `highlight` (default: true), `delay` |
| `hover` | Hover over element | `selector`, `duration` |
| `type` | Type text into input | `selector`, `text`, `delay` (per char, default: 60ms) |
| `scroll` | Scroll page | `y` (pixels), `selector` (scroll to element), `smooth` (default: true) |
| `moveCursor` | Move cursor without clicking | `selector` or `x`/`y`, `steps`, `pause` |
| `overlay` | Show text overlay | `text`, `position`, `style`, `id`, `step` (number) |
| `removeOverlay` | Fade out overlay | `id` (default: removes default overlay) |
| `highlight` | Draw highlight box around element | `selector`, `id`, `padding`, `duration` |
| `removeHighlight` | Remove highlight box | `id` |
| `zoom` | Zoom into area | `selector` or `x`/`y`, `scale` (default: 1.5), `duration` |
| `zoomReset` | Reset zoom to 1x | `duration` |

### Overlay Positions

`top`, `bottom`, `center`, `top-left`, `top-right`, `bottom-left`, `bottom-right`

### Overlay Styles

- `title` — Large bold text, dark glassmorphic background
- `subtitle` — Medium text, lighter background
- `default` — Standard text overlay
- `callout` — Blue background, for highlighting info
- `step` — Numbered step indicator (use with `step` property)

### Step Indicators

Show numbered steps to guide viewers:

```json
{ "type": "overlay", "text": "Click the metrics tab", "step": 1, "position": "bottom" }
```

### Multiple Overlays

Use `id` to show multiple overlays simultaneously:

```json
{ "type": "overlay", "text": "Title", "style": "title", "position": "top", "id": "title" },
{ "type": "overlay", "text": "Step 1: Open settings", "step": 1, "position": "bottom", "id": "step" }
```

Remove individually: `{ "type": "removeOverlay", "id": "title" }`

## Features

- *Custom cursor*: SVG cursor visible in headless recordings (auto-injected)
- *Click ripple*: Blue ripple animation on every click
- *Smooth cursor movement*: Cursor glides to targets (20-25 steps)
- *Zoom*: CSS transform zoom with configurable origin and eased animation
- *Text overlays*: Fade in/out, glassmorphic styling, multiple positions
- *Step indicators*: Numbered badges for walkthrough sequences
- *Element highlights*: Blue border + subtle background on target elements
- *HiDPI*: 2x device scale factor by default for crisp output
- *Dark mode*: `colorScheme: "dark"` by default

## Output

- Records as .webm (Playwright VP8), auto-converts to .mp4 (H.264, yuv420p)
- Optimized for web sharing (`-movflags +faststart`)
- Default quality: CRF 22 (good quality, reasonable file size)

## Tips

- Use `wait` between actions to give viewers time to process
- Zoom in on important details, then `zoomReset` before moving on
- Layer overlays: title at top + step indicator at bottom
- For long pages, use `scroll` with `selector` to scroll specific elements into view
- The cursor auto-moves to click targets — no need for separate `moveCursor` before `click`
- `navigate` re-injects cursor and styles automatically after page load
