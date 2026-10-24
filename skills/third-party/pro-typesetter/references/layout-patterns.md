# Layout Patterns Reference

## Grid Systems

### 12-Column Grid (Digital / Web)
- 12 columns with equal gutters
- Gutter width: 24px (desktop), 16px (tablet), 12px (mobile)
- Margin: 80–120px (desktop), 40px (tablet), 16–24px (mobile)
- Span patterns: full (12), two-thirds (8), half (6), third (4), quarter (3)
- Never use odd column spans (5, 7, 9, 11) without strong compositional reason

### 9-Column Grid (Print Editorial)
- More flexibility than 12 — allows 3+6, 4+5, 3+3+3, 1+8
- Use for magazines, annual reports, editorial whitepapers
- 1-column sidebar (3/9) + main content (6/9) is a classic report layout

### 6-Column Grid (Print Brochures)
- Simple and flexible for marketing collateral
- Half-half (3+3), thirds (2+2+2), feature (4+2)

### Baseline Grid
- Set baseline grid = body line height (e.g., 14pt body × 1.4 = 20pt baseline)
- All text elements should sit on baseline grid multiples
- Images and rules should also snap to grid where possible

## Composition Frameworks

### Rule of Thirds
- Divide the canvas into a 3×3 grid
- Place primary subject at intersection points (4 power points)
- Horizon lines (real or visual) should fall on horizontal thirds, not dead center
- Never place the primary subject dead center unless the design intentionally subverts it

### Golden Ratio (Φ = 1.618)
- Golden rectangle: one dimension × 1.618 = other dimension
- Golden spiral: content flows from largest area to smallest — where the eye travels
- Use for: primary image area, content/sidebar proportions, headline vs. body mass

### Visual Weight & Balance
- Large elements pull visual weight — balance with space, not more elements
- Dark colors are heavier than light
- Isolated elements have more visual weight than grouped elements
- Diagonal lines create energy; horizontal lines create calm

## Format-Specific Templates

### One-Pager / Sell Sheet

```
┌─────────────────────────────────────┐  ← Bleed edge
│  [Logo]                             │  ← 5mm safe zone
│  ─────────────────────────────────  │
│  HEADLINE — THE BUYER'S PROBLEM     │  ← 40% of page height
│  Sub-headline: value in one line    │
│  [Big stat or key visual]           │
│─────────────────────────────────────│  ← 40% line
│  PROBLEM (col 1)   SOLUTION (col 2) │  ← 35% of page
│  • Pain point 1    • How it fixes 1 │
│  • Pain point 2    • How it fixes 2 │
│  • Pain point 3    • How it fixes 3 │
│─────────────────────────────────────│  ← 75% line
│  [Logo] [Logo] [Logo]  "Quote"  ★   │  ← 15% of page
│  [Metric]  [Metric]  [CTA button]   │
│  [Contact info / QR code]           │
└─────────────────────────────────────┘
```

**Rules:**
- Everything above the 40% line must work as a standalone if the reader sees nothing else
- Problem and solution columns must be visually parallel — same weight, same structure
- One CTA. Not two. Not three. One.

### Report / Whitepaper (Multi-page)

**Front matter:**
- Cover: Title, subtitle, author/company, date — nothing else
- Table of contents: page 2–3 — linked if digital
- Executive summary: page 3–5 — standalone, conclusive, no "see page X for details"

**Body structure:**
- Running header: document title (left) / section name (right)
- Page numbers: footer, centered or outer margin
- Section opener pages: full-bleed treatment, section title only — no body text
- Body pages: 2-column or 3-column grid, with sidebar for pull quotes/callouts
- Every section must start with a summary sentence — then detail

**Back matter:**
- Methodology / appendix (if applicable)
- References / citations
- Contact / about

### Pitch Deck

```
Slide structure for 12-slide deck:
1.  Title — company name, tagline, date
2.  Problem — the specific pain, with evidence (stat, story)
3.  Why now — market shift, timing, urgency signal
4.  Solution — what you built (one clear concept)
5.  Product — show it working (screenshot, flow, demo still)
6.  Business model — how money flows
7.  Traction — proof it's working (revenue, users, growth)
8.  Market — how big, how segmented, where you play
9.  Team — who you are, why you're the ones to build this
10. Competition — honest, with a clear differentiator
11. Financials — 3-year projection, key assumptions visible
12. Ask — exactly how much, exactly what for
```

**Slide design rules:**
- One idea per slide. If you can't explain a slide without the presenter, it has too much on it.
- Title = the takeaway/conclusion, not the topic. "Revenue growing 40% MoM" not "Revenue."
- All text minimum 18pt. If it doesn't fit, cut the content — not the font size.
- Every chart must have a labeled conclusion. The data doesn't speak for itself.
- Consistent visual template — same font sizes, same margins, same brand treatment slide to slide.

### Brochure Layouts

**Tri-fold (inside panels, left to right):**
```
Panel 4 (back)  | Panel 5 (inside left) | Panel 6 (inside right, tuck)
Problem intro   | Solution details       | CTA + contact
```
```
Panel 1 (cover, rightmost) | Panel 2 (inside center) | Panel 3 (inside left when open)
Strong headline + image    | Main story content       | Proof + testimonial
```

**Gate-fold (luxury brochure):**
- Left outer flap: teaser image + headline
- Right outer flap: continuation of image + subheadline
- Open: full-spread reveal — major image, key message
- Inside back: detail content, contact, CTA

### Email Newsletter

**Single column (most reliable):**
- Max width: 600px
- Section blocks: alternating background colors for visual separation
- Image: full-width (600px) at top
- Body text: 16px, 1.6 line height, max 500px wide for text columns
- CTA button: centered, minimum 44×44px touch target, high contrast
- Footer: unsubscribe link, legal, physical address (required by law)

**Two-column (desktop only — collapses to single on mobile):**
- Left column (2/3): main content
- Right column (1/3): sidebar — highlights, quick links, secondary CTA

## Spacing Scale

Use an 8-point grid. All spacing values are multiples of 8.

| Token | Value | Use |
|---|---|---|
| space-1 | 4pt / 4px | Tight gaps (icon to label, tight list items) |
| space-2 | 8pt / 8px | Default small gap |
| space-3 | 16pt / 16px | Paragraph spacing, form field gaps |
| space-4 | 24pt / 24px | Section gaps, card padding |
| space-5 | 40pt / 40px | Major section breaks |
| space-6 | 64pt / 64px | Page-level section separation |
| space-7 | 96pt / 96px | Hero padding, maximum breathing room |

**Rule:** If your spacing value isn't on this scale, find the nearest step up or down. "Feels about right" is not a value.
