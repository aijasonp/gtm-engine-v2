# Color Systems Reference

## Palette Structure

Every document gets exactly one palette built from four roles:

| Role | Count | Purpose |
|---|---|---|
| Dominant | 1 | Sets the tone — most surface area |
| Accent | 1 | CTAs, key highlights, links — use sparingly |
| Neutral | 1–2 | Body text, borders, subtle fills |
| White / Black | as needed | Text on dark, backgrounds |

**Maximum colors in any single document: 4 (not counting black and white)**

Brand guidelines override this only when the brand explicitly defines an expanded palette for multi-product or seasonal use. "We like more colors" is not an override.

## Palette Generation from a Single Color

Given one brand color, generate a full palette:

1. **Primary:** The given brand color
2. **Dark variant:** Reduce lightness by 20–30% (use in text, heavy accents)
3. **Light variant:** Increase lightness to 90–95% (use for backgrounds, tints)
4. **Accent:** Use the complementary or split-complementary. If primary is cool, accent is warm.
5. **Neutral:** Near-black (#1a1a1a or #222222) and light gray (#f5f5f5 or similar)

**Example: building from Deep Blue (#1F4E79):**
```
Primary:    #1F4E79  (headings, key accents, CTAs)
Dark:       #153656  (pressed states, heavy text applications)
Light:      #E6EEF6  (background tints, subtle fills)
Accent:     #D9822B  (warm amber complement, used very sparingly)
Text:       #111827  (body copy)
Background: #FFFFFF  (base) / #F7F8F8 (secondary surface)
```

## WCAG Contrast Requirements

Use `scripts/contrast-checker.py` to verify. Never ship a color combination without checking.

| Text size | Minimum ratio (AA) | Enhanced ratio (AAA) |
|---|---|---|
| Body text (< 18pt regular, < 14pt bold) | 4.5:1 | 7:1 |
| Large text (≥ 18pt regular, ≥ 14pt bold) | 3:1 | 4.5:1 |
| UI components & graphical objects | 3:1 | — |
| Decorative elements | No requirement | — |

**Common passing pairs (example palette):**
- White (#FFFFFF) on Ink (#111827): **pass**, about 17.7:1
- White (#FFFFFF) on Deep Blue (#1F4E79): **pass**, about 8.7:1
- Ink (#111827) on Light Gray (#F7F8F8): **pass**, about 16.7:1
- Deep Blue (#1F4E79) on Light Gray (#F7F8F8): **pass**, about 8.1:1
- Mid Gray (#9CA3AF) on White: **FAIL** for body text (about 2.5:1); use only for decorative dividers

**Common failing pairs to avoid:**
- Light gray text on white background
- Yellow or lime on white
- Red on green (color-blind inaccessibility)
- Medium gray on medium blue

## Color Psychology Quick Reference

| Color | Associations | Use when |
|---|---|---|
| Deep blue | Trust, authority, precision | Financial, enterprise tech, healthcare |
| Electric blue/indigo | Innovation, intelligence, future | AI/tech, startups, innovation |
| Green | Growth, success, nature, go | Finance (positive), health, sustainability |
| Red | Urgency, energy, error, stop | CTAs, warnings, high-energy marketing |
| Orange | Enthusiasm, warmth, creativity | Mid-market SaaS, consumer apps |
| Purple/violet | Premium, creativity, wisdom | Luxury, AI/tech (widely used — differentiate carefully) |
| Black | Power, sophistication, authority | Luxury, premium tech, fashion |
| White | Clarity, simplicity, space | Minimalist, healthcare, clean tech |
| Gold/amber | Prestige, achievement, premium | Awards, financial success, enterprise |

## Color Application Rules

**Background colors:**
- White or near-white for most professional documents
- Dark backgrounds (near-black) for premium/impact sections — not entire documents unless deliberate
- Never use medium gray as a page background — it reads as unfinished or unintentional
- Tints (5–10% opacity) are preferable to mid-tone fills for callout boxes

**Text colors:**
- Body text: #1a1a1a or #222222 (never pure #000000 — too harsh)
- Secondary/caption text: #444444 or #555555
- Disabled/placeholder: #999999 (ensure contrast if on non-white background)
- Link text: brand accent color, underlined on hover
- White text minimum on backgrounds with 4.5:1 contrast ratio minimum

**Accent color discipline:**
- Accent color touches maximum 10–15% of the page
- Use for: primary CTA, key statistics, important callouts, links
- If accent is used for everything, it becomes background noise — it stops being accent

## Color Mistakes That Signal Amateur Work

1. **Too many colors** — If the palette has 8 colors and none of them are neutral, it's a website header from 2004.
2. **Purple gradient on white** — The default "I made this with AI" signature. Avoid.
3. **Neon on white** — Looks great on screen, fails in contrast, screams default.
4. **Inconsistent saturation** — Mixing highly saturated primaries with washed-out pastels in the same document.
5. **Color for decoration, not function** — Every color choice should serve hierarchy or wayfinding.
6. **Random accent application** — If you can't state in one sentence why a thing is the accent color, remove it.

## Dark Mode Considerations

If designing documents that will be viewed in dark mode:

- Never use pure white (#FFFFFF) on pure black (#000000) — too harsh, use #E8E8E8 on #121212
- Elevation: lighter backgrounds indicate higher elevation (opposite of light mode)
- Shadows become highlights in dark mode — rethink depth cues
- Brand colors may need lightened variants for dark mode legibility (run contrast-checker.py)
- A saturated primary like #1F4E79 may need to become #4A7FB5 or lighter for AA on dark backgrounds
