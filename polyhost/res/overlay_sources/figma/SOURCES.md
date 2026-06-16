# Figma overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild.

## Shortcuts

Figma desktop default keyboard shortcuts (Windows; `Ctrl` == `Cmd` on macOS — the
firmware treats both as Ctrl). The in-app **Shortcuts panel** (`Ctrl+Shift+?`) is
the authoritative source; cross-checked against:
- https://help.figma.com/hc/en-us/articles/360040328653-Keyboard-shortcuts-in-Figma (Figma Learn — official; returns 403 to scrapers, read in-app)
- https://www.nobledesktop.com/shortcuts/figma/pc
- https://usethekeyboard.com/figma/
- https://dualite.dev/blog/figma-keyboard-shortcuts
- https://www.domestika.org/en/blog/9913-110-essential-figma-shortcuts-for-designers

45 shortcuts placed across channels (bucket A — stable global set):

- **Tools (no-mod, A channel):** V Move, K Scale, F Frame, R Rectangle, O Ellipse,
  L Line, P Pen, T Text, H Hand, C Comment, I Eyedropper, S Slice
- **Ctrl (primary R):** C Copy, X Cut, V Paste, Z Undo, D Duplicate, G Group,
  A Select-all, S Save, N New-file, R Rename, E Flatten, F Find, B Bold, I Italic,
  U Underline
- **Shift (primary B):** P Pencil, L Arrow, R Rulers, G Layout-grid, O Outline-view,
  1 Zoom-to-fit, 2 Zoom-to-selection
- **Ctrl+Shift (combo R):** G Ungroup, V Paste-over-selection, K Place-image,
  O Outline-stroke, E Export, C Copy-as-PNG, X Strikethrough
- **Ctrl+Alt (combo G):** G Frame-selection, K Create-component, B Detach-instance

### Corrections / confirmations vs the starting list

- **F = Frame** is the only frame tool; there is **no default `A` tool** in Figma —
  the starting list's "A=Frame(or arrow)" was wrong, so **`A` (no-mod) is dropped**
  (no documented default). The "Arrow" tool is **Shift+L** (placed on the Shift layer).
- **Pencil = Shift+P**, **Arrow = Shift+L** — confirmed.
- **Rulers = Shift+R** (not Ctrl+Shift+R). **Outline view = Shift+O**.
- **Zoom to fit = Shift+1**, **Zoom to selection = Shift+2** (Figma's number-row zoom;
  with the "use number keys for opacity" preference *off* these are the bare-Shift
  defaults). **Zoom 100% = Shift+0** is **dropped** — `0` (no-mod) carries no other
  Figma default we map, and Shift+0 vs Shift+1/2 is preference-dependent; we keep the
  two unambiguous ones.
- **Ctrl+I/U/B** are text format; they share the `Ctrl` layer cleanly (no key clash
  with any other Ctrl binding).

### Flagged / dropped

- **No documented default found / dropped:** `A` (no-mod) — no tool bound.
- **Ctrl+Alt+Shift and any GUI/Win combos:** not representable by the firmware /
  dropped per spec — none were in the chosen set.
- **Layout-grid toggle (Shift+G)** and **Outline view (Shift+O)**: Figma also exposes
  layout-grid visibility via `Ctrl+Shift+4` in some builds; the bare-`Shift+G` /
  `Shift+O` toggles used here match the in-app Shortcuts panel and avoid clashing
  with the Ctrl+Shift layer. Verify in-app if a build differs.

## Icons

41 of 45 glyphs are **Microsoft Fluent UI System Icons (MIT)**
(`microsoft/fluentui-system-icons`, `main`, `assets/<Name>/SVG/ic_fluent_*_24_regular.svg`,
except `Cube Add` which only ships a `_20_regular` variant). MIT is GPLv2-compatible.
Every asset name was probed (raw fetch, 200 check) before use. Mapping lives in
`fetch_icons.py`; each binding's `source:` notes the glyph.

### Fluent 404s → substitutions

Probed and found **missing** on `main`, so substituted with a real nearby glyph (or
drawn, below):
- `Text Add`, `Draw`, `Vector`, `Slice`, `Cube Add (24px)`, `Cube Link` — all 404.
- **Pencil** → `Inking Tool` (distinct from Pen's `Pen`).
- **Component (create)** → `Cube Add` **20px** variant (`_24_` does not exist).
- **Detach instance** → `Plug Disconnected` (no `Cube Link`/un-component glyph).
- **Slice** → drawn (no Fluent slice glyph).

### Weaker / approximate matches worth knowing

- **Scale (K)** → `Resize Large` (reads as a maximize/expand glyph).
- **Outline view (O)** → `Eye Off` (hide-render proxy).
- **Outline stroke (Ctrl+Shift+O)** → `Pen Sparkle`.
- **Ellipse (O)** → `Circle`; **Rectangle (R)** → `Rectangle Landscape`.
- **Zoom to selection (Shift+2)** → `Select Object`; **Zoom to fit (Shift+1)** →
  `Full Screen Maximize`.
- **Paste / Paste-over** both use `Clipboard Paste` (same glyph, different layers).

### Drawn glyphs (white-on-transparent, `mode: alpha`)

- `slice.png` — dashed export-region rectangle with corner ticks (`_draw_slice`).
- `frameselection.png` — frame corner-brackets around a solid object (`_draw_frame_selection`).
- `figma.png` — **program icon** (ESC, all layers): a generic, license-clean
  rounded-square **outline** with the monogram **Fi** drawn inside — the unified
  outlined-monogram style shared with the other app marks (Ai, Ps, Kr, Te).
  **NOT** Figma's multi-dot logo — carries no trademark/licence risk
  (`_draw_figma_mark`).

## Transformations

`bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [36, 32]`,
`anchor: bottom-right`; drawn glyphs use per-binding `mode: alpha`. Program icon
bottom-right `[46, 40]`. Fluent `.svg` → cairosvg 96 px in `fetch_icons.py`.
Committed `icons/` freeze the render; pin the Fluent branch→SHA for byte-exact
reproducibility.

## Mapping stanza

Paste into `polyhost/res/overlay-mapping.poly.yaml`:

```yaml
figma:
  overlay: [figma_template.mods.png, figma_template.combo.mods.png]
```

## Coverage audit additions (2026-06)

Added 10 high-value defaults that were missing (44 → 54): `Ctrl+/` search and
`Ctrl+'` pixel grid (reuse the existing Search / Grid glyphs), `Ctrl+]`/`Ctrl+[`
bring-forward / send-backward (Arrow Up/Down), `Ctrl+Shift+]`/`[` to-front /
to-back (Position To Front/Back), `Ctrl+Alt+C`/`V` copy / paste properties (reuse
Copy / Paste), `Ctrl+Alt+M` use as mask (Crop), `Ctrl+Alt+A` select inverse
(Arrow Swap). All Fluent (MIT); sources per binding `source:`.
