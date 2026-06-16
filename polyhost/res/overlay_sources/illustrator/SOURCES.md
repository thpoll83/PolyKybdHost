# Adobe Illustrator overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild.

## Shortcuts

Adobe Illustrator default keyboard shortcuts. Primary reference:
- https://helpx.adobe.com/illustrator/using/default-keyboard-shortcuts.html
  (Adobe's official page returns **HTTP 403** to automated fetchers; the tool
  letters and menu accelerators below were cross-checked against multiple public
  mirrors of the same defaults — Noble Desktop, KeyCombiner, hotkeycheatsheet,
  trainingconnection AI cheat sheet — and these are long-standing, stable global
  defaults.)

56 shortcuts placed (+ the ESC program mark), spread across channels:

- **Tools (no modifier → A channel of primary)** — 24:
  V Selection, A Direct-selection, Y Magic-wand, Q Lasso, P Pen, T Type,
  `\` Line-segment, M Rectangle, L Ellipse, B Paintbrush, N Pencil, C Scissors,
  R Rotate, O Reflect, S Scale, U Mesh, G Gradient, I Eyedropper,
  K Live-paint-bucket, Z Zoom, H Hand, E Eraser, X Swap-fill/stroke,
  D Default-fill/stroke.
- **Ctrl (→ R channel of primary)** — 20:
  N New, O Open, S Save, P Print, Z Undo, C Copy, X Cut, V Paste, A Select-all,
  D Transform-again, F Paste-in-front, B Paste-in-back, G Group, 2 Lock,
  7 Make-clip-mask, 8 Make-compound-path, `]` Bring-forward, `[` Send-backward,
  `=` Zoom-in, `-` Zoom-out.
- **Ctrl+Shift (→ R channel of combo)** — 7:
  S Save-as, O Create-outlines, G Ungroup, V Paste-in-place, P Place,
  `]` Bring-to-front, `[` Send-to-back.
- **Shift (→ B channel of primary)** — 4:
  E Free-transform, W Width-tool, B Blob-brush, L Live-paint-selection.

### Corrections to the starting list (verified)

- **E = Eraser** (no-mod), **Shift+E = Free Transform** — the starting list had
  these the wrong way round. Verified across mirrors.
- **W = Blend tool** (no-mod), **Shift+W = Width tool** — the starting list's
  "Shift+W = Warp" is wrong; Shift+W is the Width tool. There is no plain "Warp"
  tool letter (Warp lives in the Liquify group with no default single key).
- **Shift+L = Live Paint Selection** (the starting list's "Shift+L = ?").
- **Shift+B = Blob Brush**, **Shift+N = Shaper** (the starting list's
  "Shift+W=Warp" / "Shift+B=Blob-brush" — Blob brush confirmed on Shift+B).
- `Ctrl++` / `Ctrl+-` zoom are the **`=` / `-`** keys (KC_EQUAL / KC_MINUS) on a
  US layout.

### Dropped / not placed (flagged)

- **W (no-mod) = Blend tool** — *dropped*: no clean Fluent glyph (Fluent "Blend"
  404s) and Blend is a niche tool; the W cell is used by Shift+W (Width tool)
  instead. Flagged here rather than drawn.
- **Shift+N Shaper, Shift+M Shape-builder, Shift+R Puppet-warp, Shift+O Artboard,
  Shift+P Perspective-grid** — valid defaults but *not placed*: they would land on
  the same primary B (Shift) channel as keys already used and add little value to
  the curated set. Documented here as known omissions, not invented.
- **Ctrl+5 Make-guides, Ctrl+Shift+K Document-setup, Ctrl+Alt+* combos** —
  *dropped*: Ctrl+Alt+Shift is not representable, and the curated set already
  covers the high-value Object/Edit accelerators.
- **GUI/Win combos** — dropped (firmware drops the GUI overlay channel).
- **Ctrl+Alt+Shift** — not representable by the firmware (hard limit).

No shortcut in the placed set lacked a documented default; nothing was invented.

## Icons

### Fluent (MIT) — 43 glyphs

Microsoft Fluent UI System Icons (`microsoft/fluentui-system-icons`, `main`,
`assets/<Name>/SVG/ic_fluent_*_24_regular.svg`), MIT-licensed (GPLv2-compatible).
**Every asset name was probed (raw fetch, 404-checked) before use.** Mapping in
`fetch_icons.py`; each binding's `source:` notes the glyph. Notable weaker
matches (best available Fluent glyph for an Illustrator concept):

- Direct-selection → **Select Object**, Magic-wand → **Wand**, Reflect →
  **Flip Horizontal**, Scale & Free-transform → **Resize**, Mesh → **Grid**,
  Gradient → **Color Line**, Live-paint-bucket & Live-paint-select →
  **Paint Bucket**, Compound-path → **Shape Subtract**, Clip-mask → **Crop**,
  Create-outlines → **Text Effects**, Transform-again → **Arrow Repeat All**,
  Paste-in-front/back → **Arrow Up / Arrow Down**, Bring/Send (to front/back) →
  **Position To Front / Position To Back**, Place → **Image Add**,
  Blob-brush → **Paint Brush** (same as Paintbrush).

### Drawn glyphs (no clean Fluent match) — 6, `mode: alpha`

White-on-transparent glyphs drawn in `fetch_icons.py` (Fluent has no good vector-
editing equivalent):

- **pen.png** — Pen tool: a **filled** pen-nib silhouette (tall blade tapering to
  a point) with a round vent hole + centre slit cut out. A solid fill reads far
  better at 1-bit than the old thin-outline triangle.
- **scissors.png** — Scissors tool: two finger-loops + crossed blades (distinct
  from Fluent "Cut" reused for Ctrl+X).
- **line.png** — Line-segment tool: diagonal stroke with end nodes.
- **width.png** — Width tool: a swelling stroke (lens) with a vertical
  double-arrow handle.
- **swap.png** — Swap fill/stroke (X): a filled + a hollow square with a diagonal
  swap arrow.
- **default.png** — Default fill/stroke (D): the canonical white-fill +
  black-stroke swatch pair.

### Fluent 404s encountered while sourcing

Probed names that returned 404 and were substituted/drawn:
**Brush**, **Draw**, **Blend**, **Text Add**, **Arrow Join** — none were needed
(substituted with the verified names above, or drawn).

## Program icon (ESC, all layers)

`program_icon: illustrator.png` is a **generic, license-clean rounded-square "Ai"
monogram drawn in code** (NOT Adobe's logo): a rounded-rectangle frame with an
"Ai" wordmark. Drawn by `_draw_ai_logo()` in `fetch_icons.py`
(white-on-transparent → `program_icon_mode: alpha`), so it is fully reproducible
and carries no trademark/licence risk. Drop a real mark as `icons/illustrator.png`
to override (committed assets are left untouched).

## Transformations

`bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [36, 32]`,
`anchor: bottom-right`, `margin: 0`; drawn glyphs use per-binding `mode: alpha`.
Program icon bottom-right `[46, 40]`, `program_icon_mode: alpha`. Fluent `.svg` →
cairosvg 96px in `fetch_icons.py`. Pin branch→SHA for byte-exact reproducibility;
committed `icons/` freeze the render.

## Mapping stanza

Paste into `polyhost/res/overlay-mapping.poly.yaml`:

```yaml
illustrator:
  overlay: [illustrator_template.mods.png, illustrator_template.combo.mods.png]
```

## Coverage audit additions (2026-06)

Added 12 high-value defaults that were missing (55 → 67): `Ctrl+Y` outline mode
(drawn wireframe), `Ctrl+J` join (Link), `Ctrl+R` rulers (Ruler), `Ctrl+;` guides
(drawn dashed cross), `Ctrl+U` smart guides (drawn), `Ctrl+H` hide edges (Eye
Off), `Ctrl+L` new layer (Add Square), `Ctrl+K` preferences (Settings),
`Ctrl+Shift+E` apply last effect (Sparkle), `Ctrl+Alt+J` average (drawn),
`Ctrl+Alt+B` make blend (drawn), `Ctrl+Alt+3` show all (Eye). Fluent (MIT) +
drawn glyphs; sources per binding `source:`.
