# Adobe Photoshop overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild byte-identically (committed `icons/` freeze the render).

## Shortcuts

Adobe Photoshop default keyboard shortcuts (Windows). References:
- https://helpx.adobe.com/photoshop/using/default-keyboard-shortcuts.html (official; returns HTTP 403 to automated fetches)
- https://www.keychron.com/blogs/news/photoshop-keyboard-shortcuts
- https://photoshoptrainingchannel.com/photoshop-keyboard-shortcuts/
- https://www.nobledesktop.com/shortcuts/photoshopcc/pc

56 shortcuts placed across channels (49 in the primary PNG, 7 in the combo PNG):

- **Tools** (no-mod → A channel, 22): V Move · M Marquee · L Lasso · W Quick-select/Magic-wand ·
  C Crop · B Brush · E Eraser · S Clone-stamp · T Type · G Gradient/Paint-bucket · I Eyedropper ·
  Z Zoom · H Hand · P Pen · U Shape · J Healing-brush · O Dodge/Burn · Y History-brush ·
  A Path-selection · X Swap-FG/BG · D Default-colours · Q Quick-mask
- **Ctrl** (R channel, 26): N New · O Open · S Save · W Close · P Print · Z Undo · C Copy · X Cut ·
  V Paste · A Select-all · D Deselect · T Free-transform · J Duplicate-layer · E Merge-down ·
  G Group · L Levels · M Curves · U Hue/Saturation · B Color-balance · I Invert · R Rulers ·
  H Hide-extras · 0 Fit-on-screen · = Zoom-in · - Zoom-out
- **Ctrl+Shift** (combo R channel, 7): S Save-As · N New-layer · I Inverse-selection ·
  U Desaturate · E Merge-visible · Z Redo/Step-forward · C Copy-merged
- **Shift** (B channel, 1): F5 Fill

The no-mod *tool* letter (e.g. B, E, S) and its Ctrl meaning (Color-balance, Merge-down, Save)
coexist on the same key in different channels — that is intended and correct.

### Dropped / not included
- **No Ctrl+Alt+Shift or Win/GUI shortcuts** were requested for this stable global set, so none
  were dropped. (Photoshop's Ctrl+Shift+Alt+E "Stamp Visible" and Ctrl+Alt+N "New layer no-dialog"
  fall in non-representable / less-canonical territory and were intentionally left out in favour of
  the canonical Ctrl+Shift+E / Ctrl+Shift+N.)
- No requested key was left without a documented default — every entry in the task's starting list
  maps to a real Photoshop default.

## Icons

All glyphs are either **Microsoft Fluent UI System Icons (MIT)** or **custom drawn**
(white-on-transparent, `mode: alpha`). MIT is GPL-compatible (host is GPL-3.0-or-later).
Adobe's own tool icons are proprietary and are **not** used.

### Fluent (MIT) — `microsoft/fluentui-system-icons`, branch `main`, `assets/<Name>/SVG/ic_fluent_*_24_regular.svg`

| icon | Fluent asset | used for |
|---|---|---|
| move | Arrow Move | V Move tool |
| crop | Crop | C Crop tool |
| brush | Paint Brush | B Brush tool |
| eraser | Eraser | E Eraser tool |
| type | Text T | T Type tool |
| fill | Paint Bucket | Shift+F5 Fill (the G Gradient tool is drawn — see below) |
| eyedropper | Eyedropper | I Eyedropper tool |
| zoom / zoomin | Zoom In | Z Zoom tool, Ctrl+= Zoom in |
| hand | Hand Right | H Hand tool |
| pen | Pen | P Pen tool |
| shape | Shapes | U Shape tool |
| historybrush | History | Y History brush |
| new | Document Add | Ctrl+N New |
| open | Folder Open | Ctrl+O Open |
| save | Save | Ctrl+S Save |
| saveas | Save Edit | Ctrl+Shift+S Save As |
| close | Document Dismiss | Ctrl+W Close |
| print | Print | Ctrl+P Print |
| undo | Arrow Undo | Ctrl+Z Undo |
| redo | Arrow Redo | Ctrl+Shift+Z Redo/Step forward |
| copy | Copy | Ctrl+C Copy |
| cut | Cut | Ctrl+X Cut |
| paste | Clipboard Paste | Ctrl+V Paste |
| selectall | Select All On | Ctrl+A Select all |
| deselect | Select All Off | Ctrl+D Deselect |
| freetransform | Resize | Ctrl+T Free transform |
| duplayer | Layer | Ctrl+J Duplicate layer |
| mergedown | Layer Diagonal | Ctrl+E Merge down, Ctrl+Shift+E Merge visible |
| group | Group | Ctrl+G Group layers |
| newlayer | Add Square | Ctrl+Shift+N New layer |
| levels | Data Histogram | Ctrl+L Levels |
| curves | Data Line | Ctrl+M Curves |
| huesat | Color | Ctrl+U Hue/Saturation |
| colorbalance | Color Fill | Ctrl+B Color balance |
| invert | Color Background | Ctrl+I Invert |
| desaturate | Color Line | Ctrl+Shift+U Desaturate |
| invertsel | Arrow Swap | Ctrl+Shift+I Inverse selection |
| copymerged | Copy Select | Ctrl+Shift+C Copy merged |
| rulers | Ruler | Ctrl+R Rulers |
| extras | Eye Off | Ctrl+H Hide extras |
| fitscreen | Full Screen Maximize | Ctrl+0 Fit on screen |
| zoomout | Zoom Out | Ctrl+- Zoom out |

Weaker matches worth knowing: **Merge-down** and **Merge-visible** both reuse "Layer Diagonal";
**Inverse-selection** → "Arrow Swap" (no dedicated invert-selection glyph). All rendered
`mode: luma`, `threshold: 150`. (The **Gradient** tool used to reuse "Paint Bucket" too, making it
indistinguishable from **Fill** — it is now a drawn diagonal swatch; see below.)

All Fluent asset names were probed for HTTP 404 before use — every name above resolved.
**None 404'd**, so no substitutions were needed for stock glyphs.

### Custom-drawn glyphs (white-on-transparent, `mode: alpha`; drawn in `fetch_icons.py`)

Photoshop's signature tools have no good Fluent equivalent, so they are drawn:

| icon | drawn as | used for |
|---|---|---|
| marquee | dashed rectangle | M Marquee tool |
| lasso | freeform loop + tail/knot | L Lasso tool |
| magicwand | diagonal wand + 4-point sparkle | W Quick-select/Magic-wand tool |
| clonestamp | rubber-stamp silhouette (handle/neck/base) | S Clone-stamp tool |
| healing | rotated band-aid / plaster | J Healing-brush tool |
| dodgeburn | dodge "lollipop" (circle on a stick) | O Dodge/Burn tool |
| pathselect | solid arrow cursor | A Path-selection tool |
| defaultcolors | filled + hollow square pair (black/white) | D Default colours |
| gradient | swatch split on the diagonal (lit / unlit halves) | G Gradient tool (distinct from the Fill bucket) |
| quickmask | canvas rect with inner circle (+ masked region) | Q Quick mask |

Each is generated at 4× supersample and downscaled (LANCZOS); the alpha channel is the shape.
Guarded by an exists-check so a committed hand-edit survives a `fetch_icons.py` re-run.

X Swap FG/BG uses GIMP's swap glyph, copied from `../gimp/icons` by
`icon_fetch.borrow` (`region: [72, 40]`, centred, `mode: alpha` to match), so the
three image editors share one icon.

## Program icon (ESC, all layers)

`program_icon: photoshop.png` — a **generic, license-clean** 2px rectangle with
the letters **"Ps"** inside, built by the shared `../rect_mark.py` at the size
the whole Adobe family shares. It replaced an in-file `_draw_ps_logo()`
rounded-square monogram, which is why that function may still exist unused in
`fetch_icons.py`. Deliberately **not** Adobe's logo styling or colours — just a
plain monogram, white-on-transparent (`program_icon_mode: alpha`), so it carries
no trademark/licence risk. Guarded by an exists-check. Region `[37, 32]`,
bottom-right, so the firmware's key legend (top-left) stays clear.

## Transformations

`bindings.yaml` file-level: `mode: luma`, `threshold: 150`, `region: [36, 32]`,
`anchor: bottom-right`, `margin: 0`. Drawn glyphs override per-binding to `mode: alpha`.
Fluent `.svg` → cairosvg 96px in `fetch_icons.py`. Pin the branch to a SHA for byte-exact
reproducibility if needed; the committed `icons/` freeze the current render.

## Coverage audit additions (2026-06)

Added 12 high-value defaults that were missing (55 → 67): `[` `]` brush size and
`Shift+[` `Shift+]` brush hardness (drawn dots / rings), `F` screen mode
(Full Screen Maximize), `Alt+Bksp` / `Ctrl+Bksp` fill FG/BG (drawn solid / framed
square), `Ctrl+Alt+Z` step backward (History), `Ctrl+1` zoom 100% (Ratio One To
One), `Ctrl+Shift+J` new layer via cut (Add Square), `Shift+F6` feather (Blur),
`Shift+Bksp` Fill dialog (reuses the Paint Bucket). All representable; sourced
per binding `source:`.

## Program mark

The Adobe apps share one treatment (`../rect_mark.py`): a **2px rectangle with
the product's two letters inside** — `Ps` / `Ai` / `Pr` / `Ae`. They are a
family, and what identifies one is its letter pair, so the mark is deliberately
plain. Adobe's real logos are proprietary and cannot ship here; the letters are
the app's own naming, not its trademark styling — no rounded-square gradient, no
brand colours, no attempt to resemble the product tile.

Authored **1:1** at the `[37, 32]` region so the generator never rescales it and
the 2px frame stays exactly 2px; the letter size is *measured* per pair (the
widest that clears the frame by >=2px), since `Ai` is much narrower than `Pr`
and one hardcoded size would either clip or float.

## macOS

The spec serves Windows/Linux and macOS from one file (`CMDCTRL` → Ctrl / Cmd;
see `overlay_specification.md` → *The `CMDCTRL` modifier*); the generator writes
a second set `*_mac.*` for the `os: macos:` branch.

Sources. Adobe's official pages list the Windows and macOS columns side by side:

- https://helpx.adobe.com/photoshop/using/default-keyboard-shortcuts.html

`helpx.adobe.com` is blocked by this environment's egress proxy (WebFetch and curl
both 403), so the macOS column was confirmed from web-search result snippets of
those pages and of reputable mirrors (community.adobe.com threads on Cmd+H; jkost.com (Fill); nobledesktop.com Photoshop Mac shortcuts; suffolk.edu Photoshop Mac/PC cheat sheet). Each chord below
was cross-checked against at least one of them; the rest follow Adobe's documented
convention for these apps (Ctrl -> Cmd, Alt -> Option, Shift unchanged).

Every `CTRL` binding (36, including `CTRL+SHIFT` and `CTRL+ALT`) is now `CMDCTRL`:
the macOS chord is the same key with Cmd for Ctrl and Option for Alt.
Backspace is the Mac's Delete key (same HID key), so `Ctrl+Backspace` → `Cmd+Delete`
(Fill BG) and `Alt+Backspace` → `Option+Delete` (Fill FG) need no remap. Tool
letters, `[`/`]`, `Shift+F5`/`Shift+F6` are identical on macOS (F-keys may need
`fn` depending on the user's keyboard setting).

Remapped on macOS: **none**. Dropped on macOS: **none**.

| Action | macOS chord | Note |
|---|---|---|
| Hide extras | ⌘H | **macOS reserved (Hide app).** Adobe documents ⌘H; on first use Photoshop asks whether ⌘H should hide Photoshop or Hide Extras. ⌃⌘H is the alternate if the user chose the Mac standard. Drawn as ⌘H. |
| Curves | ⌘M | **macOS reserved (Minimize)**, but Photoshop claims ⌘M for Curves by default. Drawn as ⌘M. |

## Standard editing chords (shared Fluent concepts, 2026-10)

Nothing added. New/Open/Save/Close/Print/Undo/Redo (Ctrl+Shift+Z,
"Redo / Step fwd")/Cut/Copy/Paste/Select all and Ctrl+= / Ctrl+- zoom were all
already drawn.

- **Ctrl+Y is NOT Redo** in Photoshop — it is Proof Colors — so no Ctrl+Y cell.
- **Find / Find next / Replace**: Photoshop has no document find with a default chord.
