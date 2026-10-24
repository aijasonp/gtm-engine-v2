# Typography Reference

## Font Pairing Database

### Marketing / Brand Documents (decks, one-pagers, proposals)
| Heading | Body | Character |
|---|---|---|
| Neue Haas Grotesk / Helvetica Neue | Garamond / EB Garamond | Classic authority, modern confidence |
| GT Walsheim / Futura PT | Source Serif 4 | Geometric precision + humanist warmth |
| Canela / Freight Display | Freight Text | Editorial luxury |
| Editorial New | Suisse Int'l | High fashion, contemporary |
| Instrument Serif | Instrument Sans | Clean, modern, neutral |
| Playfair Display | Lato | Approachable premium |

### Corporate / Enterprise Documents (reports, whitepapers, proposals)
| Heading | Body | Character |
|---|---|---|
| Grilli Type GT America | GT America Mono (code) | Authoritative Swiss modernism |
| Aktiv Grotesk | Freight Text Pro | Corporate but refined |
| Libre Baskerville | Source Sans Pro | Trustworthy editorial |
| Merriweather | Open Sans | Readable corporate |
| Bitter | Raleway | Modern professional |

### Technical / Developer Documents
| Heading | Body | Code |
|---|---|---|
| JetBrains Mono (display) | Inter | JetBrains Mono |
| Söhne Mono | Söhne | Söhne Mono |
| IBM Plex Sans | IBM Plex Serif | IBM Plex Mono |

### Google Fonts Pairings (free, widely available)
| Heading | Body | Notes |
|---|---|---|
| Cormorant Garamond | Proza Libre | Elegant editorial |
| Playfair Display | Source Sans 3 | Classic editorial |
| Fraunces | Epilogue | Distinctive, modern |
| DM Serif Display | DM Sans | Clean, contemporary |
| Libre Baskerville | Libre Franklin | Traditional authority |
| Raleway | Merriweather | Corporate warmth |
| Space Grotesk | Space Mono | Technical, futuristic |

### Google Docs Fallback Pairings (built-in fonts)
| Heading | Body | Notes |
|---|---|---|
| Playfair Display | Lato | Best premium feel in Google Docs |
| Montserrat | Merriweather | Strong hierarchy |
| Raleway | EB Garamond | Sophisticated |
| Oswald | Source Serif Pro | High contrast, punchy |

## Type Scale Calculator

### How to Set a Scale
Base size (body text): 11pt print / 16px web

**Major Second (1.125x)** — subtle, dense documents
```
Caption:  8.9pt | Body: 10pt | H4: 11.25pt | H3: 12.7pt | H2: 14.2pt | H1: 16pt | Display: 18pt
```

**Major Third (1.25x)** — reports, whitepapers, proposals
```
Caption:  8pt | Body: 10pt | H4: 12.5pt | H3: 15.6pt | H2: 19.5pt | H1: 24.4pt | Display: 30.5pt
```

**Perfect Fourth (1.333x)** — editorial, marketing docs
```
Caption:  7.5pt | Body: 10pt | H4: 13.3pt | H3: 17.8pt | H2: 23.7pt | H1: 31.6pt | Display: 42pt
```

**Golden Ratio (1.618x)** — maximum contrast, hero marketing
```
Caption:  6.2pt | Body: 10pt | H4: 16.2pt | H3: 26.2pt | H2: 42.4pt | H1: 68.5pt
(Use sparingly — only for single-page marketing pieces with minimal body text)
```

## Line Height Rules

| Use | Line Height | Notes |
|---|---|---|
| Large display (60pt+) | 0.9–1.0x | Headings need to stack tight |
| Headings (24–60pt) | 1.1–1.2x | Slight breathing room |
| Subheadings (14–24pt) | 1.2–1.3x | |
| Body text (10–14pt) | 1.4–1.6x | Readability sweet spot |
| Captions / small text | 1.3–1.4x | Tighter than body |
| Code blocks | 1.6–1.8x | Needs extra air |

## Letter Spacing (Tracking) Rules

| Context | Tracking | Why |
|---|---|---|
| Display type (48pt+) | −20 to −50 | Large glyphs have optical gaps — close them |
| Headings (24–48pt) | −10 to −20 | Tighten but not cramped |
| Body text | 0 (no tracking) | Never touch body tracking. Designers hate this. |
| Small body (8–10pt) | +10 to +20 | Open up for legibility |
| ALL CAPS labels | +50 to +150 | Always track caps. Always. |
| Spaced caps headline | +200 to +400 | Deliberate stylistic choice — own it |

## Paragraph Style Rules

**Digital documents:**
- Space after paragraph: 0.5–1x body font size
- No first-line indent
- Slightly tighter spacing inside list items

**Long-form print:**
- First-line indent: 1–1.5x body font size
- No space between paragraphs (indents serve this purpose)
- Exception: first paragraph after a heading = no indent (classic book rule)

## OpenType Feature Checklist

When the font and platform support it, enable:
- `liga` — Standard ligatures (fi, fl, ff, ffi, ffl)
- `kern` — Kerning (on by default in most apps, verify it's not disabled)
- `onum` — Old-style figures for body text numbers (look better in running text)
- `lnum` — Lining figures for tables and data
- `tnum` — Tabular figures for any column of numbers
- `frac` — Automatic fractions (1/2 not 1/2)
- `sups` / `subs` — Superscripts and subscripts
- `smcp` — Small caps for acronyms and abbreviations

## Widow & Orphan Rules

- **Widow:** Last line of a paragraph at top of a new column/page. Minimum 2 words on a widow line. Fix with tracking, forced break, or rewrite.
- **Orphan:** First line of a paragraph at bottom of a column/page. Never acceptable. Fix with Keep Lines Together setting or manual break.
- **Short last line:** Avoid a single word or very short word cluster at the end of a paragraph. Fix with a pull word from the line above via very slight tracking adjustment.

## Hierarchy of Fixes (in order of preference)

1. Rewrite (1–2 words) to fix the line
2. Adjust tracking by ±5–10 units on the paragraph
3. Adjust the text box width slightly
4. Manual line break (last resort)
