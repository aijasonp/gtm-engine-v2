#!/usr/bin/env node
/**
 * CDP Browser Video Recorder — Uses Chrome DevTools Protocol Page.startScreencast
 * for frame-by-frame capture with higher quality than Playwright's recordVideo.
 *
 * Usage:
 *   node record-cdp.mjs <choreography.json>              # Scripted recording
 *   node record-cdp.mjs --url <url> [options]             # Quick capture
 *
 * Quick capture options:
 *   --url <url>           Page to record
 *   --duration <seconds>  How long to record (default: 10)
 *   --output <path>       Output file (default: recording.mp4)
 *   --width <px>          Viewport width (default: 1280)
 *   --height <px>         Viewport height (default: 720)
 *   --scroll              Auto-scroll the page slowly
 *   --title <text>        Show title overlay at start
 *   --fps <number>        Output framerate (default: 30)
 *   --quality <number>    JPEG quality 1-100 (default: 90)
 */

import { chromium } from 'playwright';
import { readFileSync, existsSync, mkdirSync, readdirSync, unlinkSync, rmdirSync, writeFileSync } from 'fs';
import { resolve, dirname, join } from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { tmpdir } from 'os';
import { randomBytes } from 'crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FFMPEG = '/opt/homebrew/bin/ffmpeg';

// ─── CLI Parsing ────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = argv.slice(2);
  if (args.length === 0) {
    console.error('Usage: node record-cdp.mjs <choreography.json> | --url <url> [options]');
    process.exit(1);
  }

  // Check if first arg is a JSON file (choreography mode)
  if (!args[0].startsWith('--') && (args[0].endsWith('.json') || existsSync(args[0]))) {
    const choreoPath = resolve(args[0]);
    const choreo = JSON.parse(readFileSync(choreoPath, 'utf-8'));

    // Parse additional flags after the choreo file
    for (let i = 1; i < args.length; i++) {
      switch (args[i]) {
        case '--fps': choreo._fps = parseInt(args[++i], 10); break;
        case '--quality': choreo._quality = parseInt(args[++i], 10); break;
        case '--headed': choreo.headed = true; break;
      }
    }

    return { mode: 'choreography', choreo, choreoDir: dirname(choreoPath) };
  }

  // Quick capture mode
  const opts = {
    mode: 'quick',
    url: null,
    duration: 10,
    output: 'recording.mp4',
    width: 1280,
    height: 720,
    scroll: false,
    title: null,
    headed: false,
    fps: 30,
    quality: 90,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--url': opts.url = args[++i]; break;
      case '--duration': opts.duration = parseInt(args[++i], 10); break;
      case '--output': opts.output = args[++i]; break;
      case '--width': opts.width = parseInt(args[++i], 10); break;
      case '--height': opts.height = parseInt(args[++i], 10); break;
      case '--scroll': opts.scroll = true; break;
      case '--title': opts.title = args[++i]; break;
      case '--headed': opts.headed = true; break;
      case '--fps': opts.fps = parseInt(args[++i], 10); break;
      case '--quality': opts.quality = parseInt(args[++i], 10); break;
    }
  }

  if (!opts.url) {
    console.error('Error: --url is required for quick capture mode');
    process.exit(1);
  }

  return opts;
}

// ─── Injected CSS & Animations ──────────────────────────────────────────────

const INJECTED_STYLES = `
  /* Custom cursor */
  .__bv_cursor {
    position: fixed;
    top: 0; left: 0;
    pointer-events: none;
    z-index: 2147483647;
    filter: drop-shadow(1px 2px 2px rgba(0,0,0,0.35));
    transition: transform 0.08s cubic-bezier(0.22, 1, 0.36, 1);
    will-change: transform;
  }

  /* Click ripple */
  @keyframes __bv_ripple {
    0% { transform: translate(-50%, -50%) scale(0.3); opacity: 1; }
    100% { transform: translate(-50%, -50%) scale(2.5); opacity: 0; }
  }
  .__bv_click_ring {
    position: fixed;
    width: 40px; height: 40px;
    border-radius: 50%;
    border: 3px solid #3b82f6;
    background: rgba(59, 130, 246, 0.15);
    pointer-events: none;
    z-index: 2147483646;
    animation: __bv_ripple 0.6s ease-out forwards;
  }

  /* Text overlay base */
  .__bv_overlay {
    position: fixed;
    pointer-events: none;
    z-index: 2147483645;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
    -webkit-font-smoothing: antialiased;
    transition: opacity 0.4s ease, transform 0.4s ease;
  }

  /* Overlay positions */
  .__bv_overlay--top { top: 32px; left: 50%; transform: translateX(-50%); }
  .__bv_overlay--bottom { bottom: 32px; left: 50%; transform: translateX(-50%); }
  .__bv_overlay--center { top: 50%; left: 50%; transform: translate(-50%, -50%); }
  .__bv_overlay--top-left { top: 32px; left: 32px; }
  .__bv_overlay--top-right { top: 32px; right: 32px; }
  .__bv_overlay--bottom-left { bottom: 32px; left: 32px; }
  .__bv_overlay--bottom-right { bottom: 32px; right: 32px; }

  /* Overlay styles */
  .__bv_overlay--title {
    background: rgba(0, 0, 0, 0.82);
    color: #fff;
    padding: 20px 40px;
    border-radius: 12px;
    font-size: 28px;
    font-weight: 600;
    letter-spacing: -0.02em;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  }

  .__bv_overlay--subtitle {
    background: rgba(0, 0, 0, 0.72);
    color: rgba(255,255,255,0.9);
    padding: 14px 28px;
    border-radius: 8px;
    font-size: 18px;
    font-weight: 400;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.2);
  }

  .__bv_overlay--default {
    background: rgba(0, 0, 0, 0.75);
    color: #fff;
    padding: 14px 28px;
    border-radius: 8px;
    font-size: 18px;
    font-weight: 500;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.2);
  }

  .__bv_overlay--callout {
    background: rgba(59, 130, 246, 0.9);
    color: #fff;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 15px;
    font-weight: 500;
    box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
  }

  .__bv_overlay--step {
    background: rgba(0, 0, 0, 0.85);
    color: #fff;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .__bv_step_num {
    background: #3b82f6;
    color: #fff;
    width: 28px; height: 28px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px;
    font-weight: 700;
    flex-shrink: 0;
  }

  /* Highlight box around element */
  .__bv_highlight_box {
    position: fixed;
    pointer-events: none;
    z-index: 2147483644;
    border: 2px solid #3b82f6;
    border-radius: 4px;
    background: rgba(59, 130, 246, 0.08);
    box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.15);
    transition: all 0.3s ease;
  }

  /* Fade animations */
  @keyframes __bv_fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes __bv_fadeOut {
    from { opacity: 1; }
    to { opacity: 0; }
  }

  /* Zoom transition on body */
  .__bv_zooming {
    transition: transform var(--__bv_zoom_duration, 800ms) cubic-bezier(0.4, 0, 0.2, 1);
    transform-origin: var(--__bv_zoom_origin, center center);
  }
`;

const CURSOR_SVG = `<svg width="20" height="24" viewBox="0 0 20 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M2 1L18 12L10 13.5L6 22L2 1Z" fill="white" stroke="black" stroke-width="1.5" stroke-linejoin="round"/>
</svg>`;

// ─── Page Injection Helpers ─────────────────────────────────────────────────

async function injectBaseStyles(page) {
  await page.addStyleTag({ content: INJECTED_STYLES });
}

async function injectCursor(page) {
  await page.evaluate((svg) => {
    // Hide real cursor globally
    const hideStyle = document.createElement('style');
    hideStyle.textContent = '* { cursor: none !important; }';
    document.head.appendChild(hideStyle);

    const cursor = document.createElement('div');
    cursor.className = '__bv_cursor';
    cursor.innerHTML = svg;
    document.body.appendChild(cursor);

    // Track mouse position
    let cx = -100, cy = -100;
    document.addEventListener('mousemove', (e) => {
      cx = e.clientX;
      cy = e.clientY;
      cursor.style.transform = `translate(${cx}px, ${cy}px)`;
    }, true);
  }, CURSOR_SVG);
}

async function injectOverlayRoot(page) {
  await page.evaluate(() => {
    if (document.getElementById('__bv_overlay_root')) return;
    const root = document.createElement('div');
    root.id = '__bv_overlay_root';
    root.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:2147483645;overflow:hidden;';
    document.documentElement.appendChild(root);
  });
}

async function setupPage(page) {
  await injectBaseStyles(page);
  await injectCursor(page);
  await injectOverlayRoot(page);
}

// ─── Action Handlers ────────────────────────────────────────────────────────

async function doWait(page, action) {
  await page.waitForTimeout(action.ms || action.duration || 1000);
}

async function doNavigate(page, action) {
  await page.goto(action.url, { waitUntil: action.waitUntil || 'networkidle', timeout: 30000 });
  await setupPage(page);
  await page.waitForTimeout(500);
}

async function doClick(page, action) {
  const selector = action.selector;

  if (action.highlight !== false) {
    const box = await page.locator(selector).first().boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 20 });
      await page.waitForTimeout(200);

      await page.evaluate(({ x, y }) => {
        const ring = document.createElement('div');
        ring.className = '__bv_click_ring';
        ring.style.left = x + 'px';
        ring.style.top = y + 'px';
        document.body.appendChild(ring);
        setTimeout(() => ring.remove(), 600);
      }, { x: box.x + box.width / 2, y: box.y + box.height / 2 });
    }
  }

  await page.click(selector);
  await page.waitForTimeout(action.delay || 300);
}

async function doHover(page, action) {
  const box = await page.locator(action.selector).first().boundingBox();
  if (box) {
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 25 });
  }
  await page.waitForTimeout(action.duration || 500);
}

async function doType(page, action) {
  if (action.selector) {
    await page.click(action.selector);
    await page.waitForTimeout(200);
  }
  await page.keyboard.type(action.text, { delay: action.delay || 60 });
  await page.waitForTimeout(300);
}

async function doScroll(page, action) {
  if (action.selector) {
    await page.locator(action.selector).first().scrollIntoViewIfNeeded();
  } else {
    const y = action.y || 300;
    const smooth = action.smooth !== false;
    await page.evaluate(({ y, smooth }) => {
      window.scrollBy({ top: y, behavior: smooth ? 'smooth' : 'auto' });
    }, { y, smooth });
  }
  await page.waitForTimeout(action.duration || 800);
}

async function doOverlay(page, action) {
  const id = action.id || '__bv_overlay_default';
  const position = action.position || 'bottom';
  const style = action.style || 'default';

  if (action.step) {
    await page.evaluate(({ id, text, step, position, style }) => {
      const root = document.getElementById('__bv_overlay_root') || document.body;
      let el = document.getElementById(id);
      if (!el) {
        el = document.createElement('div');
        el.id = id;
        root.appendChild(el);
      }
      el.className = `__bv_overlay __bv_overlay--${position} __bv_overlay--step`;
      el.innerHTML = `<span class="__bv_step_num">${step}</span><span>${text}</span>`;
      el.style.opacity = '0';
      el.style.animation = '__bv_fadeIn 0.4s ease forwards';
    }, { id, text: action.text, step: action.step, position, style });
  } else {
    await page.evaluate(({ id, text, position, style }) => {
      const root = document.getElementById('__bv_overlay_root') || document.body;
      let el = document.getElementById(id);
      if (!el) {
        el = document.createElement('div');
        el.id = id;
        root.appendChild(el);
      }
      el.className = `__bv_overlay __bv_overlay--${position} __bv_overlay--${style}`;
      el.textContent = text;
      el.style.opacity = '0';
      el.style.animation = '__bv_fadeIn 0.4s ease forwards';
    }, { id, text: action.text, position, style });
  }

  await page.waitForTimeout(400);
}

async function doRemoveOverlay(page, action) {
  const id = action.id || '__bv_overlay_default';
  await page.evaluate((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.style.animation = '__bv_fadeOut 0.3s ease forwards';
      setTimeout(() => el.remove(), 300);
    }
  }, id);
  await page.waitForTimeout(350);
}

async function doHighlight(page, action) {
  const box = await page.locator(action.selector).first().boundingBox();
  if (!box) return;

  const id = action.id || '__bv_highlight';
  const pad = action.padding || 8;
  await page.evaluate(({ id, box, pad }) => {
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement('div');
      el.id = id;
      el.className = '__bv_highlight_box';
      document.body.appendChild(el);
    }
    el.style.left = (box.x - pad) + 'px';
    el.style.top = (box.y - pad) + 'px';
    el.style.width = (box.width + pad * 2) + 'px';
    el.style.height = (box.height + pad * 2) + 'px';
    el.style.opacity = '1';
  }, { id, box, pad });

  await page.waitForTimeout(action.duration || 500);
}

async function doRemoveHighlight(page, action) {
  const id = action.id || '__bv_highlight';
  await page.evaluate((id) => {
    const el = document.getElementById(id);
    if (el) el.remove();
  }, id);
}

async function doZoom(page, action) {
  const duration = action.duration || 800;
  const scale = action.scale || 1.5;

  let originX = '50%', originY = '50%';
  if (action.selector) {
    const box = await page.locator(action.selector).first().boundingBox();
    if (box) {
      originX = (box.x + box.width / 2) + 'px';
      originY = (box.y + box.height / 2) + 'px';
    }
  } else if (action.x !== undefined && action.y !== undefined) {
    originX = action.x + 'px';
    originY = action.y + 'px';
  }

  await page.evaluate(({ originX, originY, scale, duration }) => {
    document.body.style.setProperty('--__bv_zoom_duration', duration + 'ms');
    document.body.style.setProperty('--__bv_zoom_origin', `${originX} ${originY}`);
    document.body.classList.add('__bv_zooming');
    document.body.style.transformOrigin = `${originX} ${originY}`;
    document.body.style.transform = `scale(${scale})`;
  }, { originX, originY, scale, duration });

  await page.waitForTimeout(duration + 100);
}

async function doZoomReset(page, action) {
  const duration = action.duration || 600;
  await page.evaluate((duration) => {
    document.body.style.setProperty('--__bv_zoom_duration', duration + 'ms');
    document.body.style.transform = 'scale(1)';
  }, duration);
  await page.waitForTimeout(duration + 100);
}

async function doMoveCursor(page, action) {
  if (action.selector) {
    const box = await page.locator(action.selector).first().boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: action.steps || 25 });
    }
  } else if (action.x !== undefined && action.y !== undefined) {
    await page.mouse.move(action.x, action.y, { steps: action.steps || 25 });
  }
  await page.waitForTimeout(action.pause || 300);
}

// Action dispatcher
const ACTIONS = {
  wait: doWait,
  navigate: doNavigate,
  click: doClick,
  hover: doHover,
  type: doType,
  scroll: doScroll,
  overlay: doOverlay,
  removeOverlay: doRemoveOverlay,
  highlight: doHighlight,
  removeHighlight: doRemoveHighlight,
  zoom: doZoom,
  zoomReset: doZoomReset,
  moveCursor: doMoveCursor,
};

// ─── CDP Frame Capture ──────────────────────────────────────────────────────

class FrameCollector {
  constructor(frameDir, fps) {
    this.frameDir = frameDir;
    this.fps = fps;
    this.frameDuration = 1000 / fps; // ms per frame
    this.frames = [];          // raw captured frames with timestamps
    this.startTime = null;
    this.frameCount = 0;
    this.lastFrameData = null; // most recent frame data for duplication
  }

  addFrame(data, timestamp) {
    if (!this.startTime) this.startTime = timestamp;
    this.lastFrameData = data;
    this.frames.push({ data, timestamp });
    this.frameCount++;
  }

  /**
   * Write frames to disk at consistent FPS.
   * Since screencast delivers frames irregularly, we resample:
   * - For each output frame slot (1/fps intervals), pick the closest captured frame.
   * - Duplicate the last frame to fill any gaps at the end.
   */
  writeFrames() {
    if (this.frames.length === 0) return 0;

    const totalDuration = this.frames[this.frames.length - 1].timestamp - this.startTime;
    const totalOutputFrames = Math.max(1, Math.ceil((totalDuration / 1000) * this.fps));

    let written = 0;
    let srcIdx = 0;

    for (let i = 0; i < totalOutputFrames; i++) {
      const targetTime = this.startTime + (i * this.frameDuration);

      // Advance source index to the closest frame at or before targetTime
      while (srcIdx < this.frames.length - 1 &&
             this.frames[srcIdx + 1].timestamp <= targetTime) {
        srcIdx++;
      }

      const frameNum = String(i + 1).padStart(5, '0');
      const framePath = join(this.frameDir, `frame-${frameNum}.jpg`);
      writeFileSync(framePath, Buffer.from(this.frames[srcIdx].data, 'base64'));
      written++;
    }

    console.log(`  Resampled ${this.frameCount} captured frames → ${written} output frames at ${this.fps}fps`);
    return written;
  }
}

// ─── Recording Engine ───────────────────────────────────────────────────────

async function recordChoreography(choreo) {
  const viewport = {
    width: choreo.viewport?.width || 1280,
    height: choreo.viewport?.height || 720,
  };
  const outputPath = resolve(choreo.output || 'recording.mp4');
  const headed = choreo.headed || false;
  const deviceScaleFactor = choreo.deviceScaleFactor || 2;
  const fps = choreo._fps || 30;
  const quality = choreo._quality || 90;

  // Create temp directory for frames
  const frameDir = join(tmpdir(), `bv-cdp-${randomBytes(6).toString('hex')}`);
  mkdirSync(frameDir, { recursive: true });

  console.log(`Recording (CDP): ${viewport.width}x${viewport.height} @ ${fps}fps, quality ${quality}`);
  console.log(`  Output: ${outputPath}`);
  console.log(`  Frame dir: ${frameDir}`);

  const browser = await chromium.launch({
    headless: !headed,
  });

  const context = await browser.newContext({
    viewport,
    deviceScaleFactor,
    colorScheme: choreo.colorScheme || 'dark',
  });

  const page = await context.newPage();

  // Open CDP session
  const cdpSession = await page.context().newCDPSession(page);
  const collector = new FrameCollector(frameDir, fps);

  // Listen for screencast frames
  cdpSession.on('Page.screencastFrame', async (params) => {
    const { data, metadata, sessionId } = params;
    collector.addFrame(data, metadata.timestamp * 1000); // convert to ms

    // Acknowledge frame so Chrome sends the next one
    try {
      await cdpSession.send('Page.screencastFrameAck', { sessionId });
    } catch {
      // Session may be closed already
    }
  });

  // Start screencast
  await cdpSession.send('Page.startScreencast', {
    format: 'jpeg',
    quality,
    everyNthFrame: 1,
    maxWidth: viewport.width * deviceScaleFactor,
    maxHeight: viewport.height * deviceScaleFactor,
  });

  console.log(`  CDP screencast started`);

  // Auto re-inject styles after navigation
  page.on('load', async () => {
    try { await setupPage(page); } catch {}
  });

  // Process scenes
  for (const scene of (choreo.scenes || [])) {
    if (scene.url) {
      console.log(`  Navigating to ${scene.url}`);
      await page.goto(scene.url, {
        waitUntil: scene.waitUntil || 'networkidle',
        timeout: 30000,
      });
      await setupPage(page);
      await page.waitForTimeout(500);
    }

    for (const action of (scene.actions || [])) {
      const handler = ACTIONS[action.type];
      if (!handler) {
        console.warn(`  Unknown action type: ${action.type}`);
        continue;
      }
      console.log(`  > ${action.type}${action.text ? ': "' + action.text + '"' : ''}${action.selector ? ' -> ' + action.selector : ''}`);
      await handler(page, action);
    }
  }

  // Give a final moment for any pending frames
  await page.waitForTimeout(200);

  // Stop screencast
  try {
    await cdpSession.send('Page.stopScreencast');
  } catch {}

  console.log(`  CDP screencast stopped. Captured ${collector.frameCount} frames`);

  await cdpSession.detach();
  await context.close();
  await browser.close();

  // Write resampled frames to disk
  const totalFrames = collector.writeFrames();

  if (totalFrames === 0) {
    console.error('Error: No frames captured');
    cleanup(frameDir);
    process.exit(1);
  }

  // Ensure output directory exists
  mkdirSync(dirname(outputPath), { recursive: true });

  // Encode with ffmpeg
  console.log(`  Encoding ${totalFrames} frames with ffmpeg...`);
  const mp4Path = outputPath.endsWith('.mp4') ? outputPath : outputPath.replace(/\.[^.]+$/, '.mp4');
  const ffmpegCmd = [
    FFMPEG,
    '-y',
    '-framerate', String(fps),
    '-i', join(frameDir, 'frame-%05d.jpg'),
    '-c:v', 'libx264',
    '-crf', '18',
    '-preset', 'medium',
    '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart',
    `"${mp4Path}"`,
  ].join(' ');

  try {
    execSync(ffmpegCmd, { stdio: 'pipe' });
  } catch (err) {
    console.error(`  ffmpeg error: ${err.stderr?.toString() || err.message}`);
    cleanup(frameDir);
    process.exit(1);
  }

  // Cleanup temp frames
  cleanup(frameDir);

  console.log(`  Done: ${mp4Path}`);
  return mp4Path;
}

function cleanup(frameDir) {
  try {
    const files = readdirSync(frameDir);
    for (const f of files) {
      unlinkSync(join(frameDir, f));
    }
    rmdirSync(frameDir);
  } catch {}
}

async function recordQuick(opts) {
  const choreo = {
    viewport: { width: opts.width, height: opts.height },
    output: opts.output,
    headed: opts.headed,
    _fps: opts.fps,
    _quality: opts.quality,
    scenes: [{
      url: opts.url,
      actions: [],
    }],
  };

  if (opts.title) {
    choreo.scenes[0].actions.push(
      { type: 'overlay', text: opts.title, style: 'title', position: 'center' },
      { type: 'wait', ms: 3000 },
      { type: 'removeOverlay' },
    );
  }

  if (opts.scroll) {
    const scrollSteps = Math.ceil(opts.duration / 2);
    for (let i = 0; i < scrollSteps; i++) {
      choreo.scenes[0].actions.push(
        { type: 'scroll', y: 300, smooth: true },
        { type: 'wait', ms: 2000 },
      );
    }
  } else {
    choreo.scenes[0].actions.push({ type: 'wait', ms: opts.duration * 1000 });
  }

  return recordChoreography(choreo);
}

// ─── Main ───────────────────────────────────────────────────────────────────

async function main() {
  const opts = parseArgs(process.argv);

  try {
    if (opts.mode === 'choreography') {
      await recordChoreography(opts.choreo);
    } else {
      await recordQuick(opts);
    }
  } catch (err) {
    console.error(`Error: ${err.message}`);
    if (err.stack) console.error(err.stack);
    process.exit(1);
  }
}

main();
