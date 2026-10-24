# Digital Specifications Reference

## Screen PDFs & Google Docs

### Color
- Color mode: RGB (not CMYK)
- sRGB color space for maximum cross-device consistency
- Never specify CMYK values for digital-only documents
- Screen brightness makes colors appear more saturated — calibrate accordingly

### Font Sizes (Screen Reading)
| Element | Minimum | Ideal |
|---|---|---|
| Body text | 11pt | 12pt |
| Small caption | 9pt | 10pt |
| Navigation / UI labels | 10pt | 11pt |
| Display / hero | 24pt | 36–72pt |

### Font Embedding
- Always embed fonts in PDFs — never subset below 100%
- If the font is not available on the recipient's system, embed or outline before exporting
- Google Docs: fonts that aren't in Google Fonts library may not render correctly for all users — stick to Google Fonts pairings

### Interactive PDFs
- Hyperlinks: blue or brand accent, underlined. Never ambiguous.
- Bookmarks: add for every major section in documents over 10 pages
- Table of contents: linked to page anchors
- Form fields: if present, tab order must be logical
- Accessibility: add alt text to all images. Set document language.

### Screen PDF Export Settings
- Resolution: 150 DPI (screen) or 300 DPI (print-quality screen PDF)
- Compression: lossless for text/graphics; JPEG high quality for photos
- Color: sRGB embedded
- PDF standard: PDF/A for archival, PDF 1.7 for general use, PDF/UA for accessibility

## Web Content & Blog Posts

### Responsive Typography
| Breakpoint | Body | H1 | H2 |
|---|---|---|---|
| Mobile (<768px) | 16px | 28–32px | 22–26px |
| Tablet (768–1024px) | 16–18px | 36–42px | 28–32px |
| Desktop (1024px+) | 18–20px | 48–64px | 32–40px |

**Line length for web:**
- Set max-width on content containers: 65–75ch (characters)
- Never full-width text on large monitors — unreadable

### Web Font Loading
- Use `font-display: swap` to prevent invisible text during load
- Limit font weights to what you actually use (each weight = separate HTTP request)
- Self-host fonts where possible for performance
- WOFF2 format first, WOFF as fallback
- System font stack fallback: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`

### Blog Post Structure
```
H1: Article title (one only — ever)
Deck/standfirst: Supporting subtitle or key insight (optional, italic)
[Featured image: 16:9, minimum 1200×675px, 150KB–400KB compressed]

Introduction: 2–3 short paragraphs, no more
---
H2: First major section
[Body text — paragraphs max 4–5 lines]
[Subheading every 200–300 words]
[Break with: pull quote / inline image / callout / list]
---
H2: Second section
...
---
Conclusion: Named H2 ("Final thoughts," "Takeaway," etc.)
CTA: Clear next action
```

### Web Image Specs
| Usage | Aspect | Min resolution | Max file size |
|---|---|---|---|
| Hero/banner | 16:9 | 1920×1080 | 500KB |
| Inline article | 4:3 or 3:2 | 800×600 | 200KB |
| Square (social, cards) | 1:1 | 800×800 | 150KB |
| Portrait | 3:4 | 600×800 | 150KB |
| Open Graph (social share) | 1.91:1 | 1200×630 | 300KB |
| Twitter Card | 2:1 | 1200×600 | 300KB |

**Format guide:**
- Photos: WebP (with JPEG fallback) for best compression
- Graphics with transparency: PNG
- Icons and illustrations: SVG (vector, infinitely scalable)
- Animation: CSS animation over GIF/video where possible

## DOCX / Microsoft Word Documents

### Style System
Always override the default Normal style before starting:
- Normal: Font of choice, 11pt, line spacing 1.15–1.5, space after 6pt
- Heading 1: Font of choice, 24pt, bold, space before 24pt space after 6pt
- Heading 2: 16pt, bold, space before 16pt space after 4pt
- Heading 3: 13pt, bold or semibold, space before 12pt space after 2pt
- Caption: 9pt, italic, gray (#666666), space after 4pt
- Quote/Block: Left-indented, italic, gray (#444444)

### Word-Specific Rules
- Never use the spacebar to indent — use tab stops or paragraph indent settings
- Never use consecutive returns for spacing — use space before/after paragraph
- Use styles consistently — find-and-replace formatting inconsistencies before delivery
- Track Changes: accept all before final delivery unless revision history is required
- Compatibility mode: always save for the target Word version (specify if unknown)

## Presentation Files (PPTX / Google Slides)

### Slide Sizes
| Standard | 10 × 7.5in | 4:3 legacy |
|---|---|---|
| Widescreen | 13.33 × 7.5in | 16:9 standard |
| Ultra-wide | 13.33 × 5in | 21:9 cinematic |
| Square | 8 × 8in | Social, modern |

Always design in 16:9 widescreen unless the brief specifies otherwise.

### Export for Different Contexts
| Use | Export format | Settings |
|---|---|---|
| Email / send to client | PDF | High quality, include presenter notes if relevant |
| Live presentation | PPTX / native | Keep animations, embed fonts |
| Video recording | PDF or recorded video | — |
| Web embed | PDF or exported images | Compress images |

### Accessibility Checklist (Digital Docs)
- [ ] Reading order: logical tab order set
- [ ] Images: alt text for all non-decorative images
- [ ] Color alone: never use color as the only differentiator
- [ ] Contrast: pass WCAG AA (verify with contrast-checker.py)
- [ ] Fonts: minimum 12pt for captions, 14pt for body
- [ ] Language: document language specified
- [ ] Headings: proper semantic hierarchy (H1 > H2 > H3)
- [ ] Links: descriptive anchor text (not "click here")
