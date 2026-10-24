# Print Specifications Reference

## Bleed, Trim & Safe Zone

| Spec | Measurement | Rule |
|---|---|---|
| Bleed | 3mm / 0.125in all edges | Background colors and images must extend to bleed edge |
| Safe zone | 5mm / 0.2in from trim edge | Keep all critical content (text, logos, CTAs) inside this |
| Trim | The actual cut size | Design to this size in your software |
| Live area | Inside safe zone | Where everything important lives |

**Bleed setup in document:**
- Document size = trim size + 6mm / 0.25in (bleed on all sides)
- Example: A4 flyer (210 × 297mm) becomes 216 × 303mm in layout
- Any background element must reach the document edge (the bleed edge)

## Paper Sizes

### US Sizes
| Name | Inches | Common uses |
|---|---|---|
| Letter | 8.5 × 11 | Standard documents, reports |
| Legal | 8.5 × 14 | Legal documents |
| Half-letter | 5.5 × 8.5 | Small brochures, booklets |
| Tabloid/Ledger | 11 × 17 | Posters, large presentations |
| A2 | 16.5 × 23.4 | Large posters |

### International (ISO)
| Name | mm | Common uses |
|---|---|---|
| A3 | 297 × 420 | Posters, folded to A4 |
| A4 | 210 × 297 | Standard document (international) |
| A5 | 148 × 210 | Booklets, small brochures |
| A6 | 105 × 148 | Postcards, cards |
| A7 | 74 × 105 | Business cards (non-standard), tags |

### Business Cards
| Standard | 88 × 54mm / 3.5 × 2in |
|---|---|
| US Standard | 3.5 × 2in |
| European | 85 × 55mm |
| Square | 65 × 65mm |
| Mini | 70 × 28mm |

## Color for Print

### CMYK Essentials
- All colors going to commercial print must be specified in CMYK
- RGB colors will be converted at the printer — results are unpredictable
- **Rich black** (for large black areas): C:60 M:40 Y:40 K:100 (not K:100 alone — looks gray)
- **Pure black text**: K:100 only — never rich black on small text (registration issues)
- Maximum ink density (TAC — Total Area Coverage): 300% for most coated paper, 280% for uncoated
- **Danger colors**: RGB red (#FF0000 = C:0 M:99 Y:100 K:0) often looks orange/brick in CMYK
- **Danger colors**: RGB blue (#0000FF = C:100 M:100 Y:0 K:0) loses vibrancy in CMYK
- **Neons and fluorescents**: Not reproducible in standard CMYK. Use Pantone spot colors.

### Spot Colors (Pantone)
- Use Pantone when a color must be exact and consistent (logos, brand colors)
- Pantone Process vs Pantone Solid: Solid for most brand work
- Budget impact: each Pantone color adds ~$300-500 to a print run
- Pantone to CMYK conversion is approximation only — always get a press proof for critical matches

### Paper Stock Considerations
| Stock | Effect on color | Notes |
|---|---|---|
| Coated gloss | Saturated, vibrant | Best for photography and rich color |
| Coated matte/silk | Slightly muted, readable | Best for text-heavy pieces |
| Uncoated | Absorbed ink, flat | Colors appear 15-20% duller — account for this |
| Kraft / recycled | Warm tint | All colors read warm; white is cream |

## Fold Types & Panel Sizing

### Tri-fold (Letter 8.5 × 11 folded)
- Panels are NOT equal — the tuck panel (right-most when flat) must be 0.125in narrower
- Right panel: 3.875in / Left panel: 3.875in / Middle (tuck) panel: 3.75in
- Front cover = right panel / Back = left panel / Inside = three inside panels

### Bi-fold (standard)
- Two equal panels
- 8.5 × 11 folded = two 5.5 × 8.5 panels
- Clean but less panel real estate

### Z-fold
- Three equal panels folded in accordion/Z pattern
- No tuck compensation needed (panels don't nest)
- Good for timelines and step-by-step content

### Gate-fold
- Two outer panels fold in to meet at center
- Outer panels = ~half width each (with gap for fold)
- Great for dramatic reveals — used in luxury brochures

## Binding Types

| Type | Best for | Minimum pages | Notes |
|---|---|---|---|
| Saddle-stitch | Booklets, catalogs | 8 | Pages must be in multiples of 4 |
| Perfect bind | Thick books, reports | 48+ | Flat spine = room for title |
| Spiral / comb | Reference books | Any | Lays flat when open |
| Case bind | Hard cover books | 64+ | Premium, most expensive |
| Staple | Internal documents | Any | 2 staples in corner or spine |

## Special Finishes

| Finish | Effect | Cost impact |
|---|---|---|
| Spot UV | Gloss over specific areas on matte base | High — requires separate plate |
| Matte laminate | Soft-touch matte over entire surface | Medium |
| Gloss laminate | Glossy protection | Low-medium |
| Soft-touch laminate | Velvet feel | High |
| Foil stamping | Metallic or holographic areas | High — requires die |
| Emboss / deboss | Raised or recessed without ink | Medium-high |
| Die cut | Custom shape cuts | High — requires die |

**Production rule:** Always specify special finishes in a separate layer or swatch in the final file. Name the layer clearly (e.g., "SPOT UV — DO NOT PRINT").

## Image Resolution

| Use | Minimum DPI | Target |
|---|---|---|
| Large format print (posters, banners) | 100–150 DPI at final size | 150 DPI |
| Commercial print (brochures, books) | 250 DPI at final size | 300 DPI |
| Business cards, small collateral | 300 DPI | 350 DPI |
| Newspaper | 200 DPI | — |
| Screen only | 72–96 DPI | 96+ DPI |

**Rule:** Always check image resolution at 100% zoom in layout software before sending to print. An image that looks fine on screen at small size may be 72 DPI — unusable for print.

## Print-Ready File Checklist

- [ ] Bleed: 3mm on all edges
- [ ] Safe zone: all critical content 5mm from trim
- [ ] Color mode: CMYK (not RGB)
- [ ] Images: 300 DPI minimum at final size
- [ ] Fonts: all embedded or outlined
- [ ] Black text: K:100 only
- [ ] Rich black large areas: C:60 M:40 Y:40 K:100
- [ ] Overprint black: enabled for text under 10pt
- [ ] Transparency: flattened or properly handled
- [ ] PDF export: PDF/X-1a or PDF/X-4 for commercial print
- [ ] Crop marks and registration marks: included
- [ ] Spot colors: named correctly (Pantone names, not RGB approximations)
- [ ] Total ink coverage: within TAC limits
