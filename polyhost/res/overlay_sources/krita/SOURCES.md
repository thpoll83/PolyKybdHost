# Krita overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild.

## Shortcuts

Krita default key bindings (the STABLE GLOBAL set — actions present in every
document, not tool-options sub-shortcuts). Verified against:

- Krita Manual — Shortcut Settings:
  https://docs.krita.org/en/reference_manual/preferences/shortcut_settings.html
- Krita Manual — Introduction coming from Photoshop (lists the brush/eraser/
  mirror/preset/brush-size defaults):
  https://docs.krita.org/en/user_manual/introduction_from_other_software/introduction_from_photoshop.html
- KDE Community Wiki — Krita/Shortcuts:
  https://community.kde.org/Krita/Shortcuts
- KDE Community Wiki — Predefined Zoom Shortcuts (the 1/2/3 view keys):
  https://community.kde.org/Krita/Docs/Predefined_Zoom_Shortcuts
- Krita 5.2 Default Keyboard Shortcut Guide (community reference):
  https://krita-artists.org/t/krita-5-2-default-keyboard-shortcut-guide/93570

28 shortcuts placed across channels (note: only the 90 mapped keycaps carry a
cell; Ctrl+Alt+Shift and GUI/Win combos are skipped):

⚠️ Both ARE representable since protocol 12 (Ctrl+Alt+Shift on the extra tier, GUI on combo A); the wording here claimed a format limit and was stale.

- **Ctrl** (primary R): N New, O Open, S Save, W Close, Z Undo, C Copy, X Cut,
  V Paste, A Select-all, T Transform, E Merge-down, G Group
- **Ctrl+Shift** (combo R): Z Redo, S Save-as, A Deselect, I Invert-selection,
  C Copy-merged, E Flatten-image
- **no-mod / tools** (primary A): B Freehand-brush, E Eraser, M Mirror-view,
  / Switch-to-previous-preset, `[` Decrease-brush-size, `]` Increase-brush-size,
  1 Zoom-100%, 2 Fit-page, 3 Fit-width

### Dropped / no confirmed default (NOT invented)

Krita has fewer global default shortcuts than Office/Adobe apps. The following
were on the starting list but have **no confirmed Krita default** and were
deliberately dropped:

- **Print (Ctrl+P)** — Krita has **no print function at all** in current versions;
  Ctrl+P does nothing. (krita-artists.org "Why does Krita not have a printing
  function?", "Where is Print command in Krita 5.2.2?")
- **Wrap-around mode (W)** — the old `W` binding was **removed**; wrap-around has
  **no default shortcut** now. (docs-krita-org commit "Remove mentions of wrap
  around shortcuts"). The task's `W=Wrap-around` hint is outdated.
- **Reset zoom (Ctrl+0)** — "Reset Zoom" is **not defined by default** (must be
  user-assigned). Kept the confirmed view keys 1/2/3 instead.
- **Zoom in / Zoom out (+ / −)** — Krita's zoom-in/out use the bare `+`/`−`
  (and numpad) keys; their behaviour vs. Shift differs by layout and they map
  awkwardly onto the `=`/`-` keycaps, so they were dropped in favour of the
  unambiguous 1/2/3 zoom-level keys.
- **Pick color (Ctrl held)** — the color sampler is reached by **holding Ctrl**
  while a paint tool is active, not a discrete keypress; the on-canvas selectors
  (Shift+I / Shift+N / Shift+M) are popup widgets, not single-shot actions. Not a
  cleanly representable shortcut → dropped.
- **Ctrl+R** — no confirmed stable global default; dropped (not invented).

## Icons

Action/tool glyphs are the **KDE Breeze icons** — the icon set Krita's own UI
uses — with one **Microsoft Fluent (MIT)** holdout and a few **drawn-in-code**
glyphs. Breeze is **LGPLv3**, license-compatible now that the host is
**GPL-3.0-or-later** (see the repo README/`LICENSE`); this is why the authentic
icons can be bundled (an earlier version of this overlay used Fluent stand-ins
because the host was then GPL-2.0-only).

### Breeze (LGPLv3) — 23 glyphs

`KDE/breeze-icons`, `master`, `icons/actions/<size>/<name>.svg`, rendered to 96px
RGBA via cairosvg. `_breeze()` in `fetch_icons.py` probes sizes `22,24,16,32`
(then `apps/`) and takes the first that resolves — deterministic for a given
breeze-icons state. Mapping (`BREEZE_ICONS`): file/edit/view actions map to the
standard freedesktop names (`document-*`, `edit-*`, `zoom-*`), plus `draw-brush`,
`draw-eraser`, `object-flip-horizontal` (Mirror), `object-group` (Group).

The four cells that needed care (a Breeze name that actually reads at 1-bit):

- **Transform (Ctrl+T)** → `transform-scale` — dotted bounding-box + handles (the
  free-transform metaphor); `transform-move` was just 4-way arrows ("move").
- **Merge down (Ctrl+E)** → `layer-bottom` — a down-arrow into stacked layers.
- **Flatten (Ctrl+Shift+E)** → `layer-visible-on` — solid stacked sheets,
  deliberately distinct from Merge-down (which has the arrow). The generic
  `merge` glyph was an unreadable blob and dup'd between the two.

### Fluent (MIT) — 1 holdout

`copymerged` → "Layer Diagonal" (`microsoft/fluentui-system-icons`). **Copy
merged** has no readable Breeze glyph — every `edit-copy-*` variant 404s and
plain `edit-copy` just duplicates Copy — so it keeps the Fluent layer glyph,
which stays visually distinct from `edit-copy` (Copy).

### Drawn glyphs (white-on-transparent, `mode: alpha`)

For painting actions with no clean Fluent match (drawn in `fetch_icons.py`):

- `brushdec.png`, `brushinc.png`, `fillbg.png`, `fillfg.png` are Photoshop's drawings,
  shared pixel-for-pixel. Fill FG = solid square, fill BG = framed square (Krita
  had them the other way round). `fetch_icons.py` leaves these committed files as-is.
  Brush decrease is the small dot and brush increase the large one, a size pair on
  `[` / `]`.
- `preset.png` — two swatches (one filled, one outlined) with a swap arrow
  between them (switch-to-previous-preset; distinct from undo/redo arrows).

## Program icon (ESC, all layers)

`program_icon: krita.png` is a **generic "Kr" monogram drawn in code** (NOT
Krita's logo): a rounded-square **outline** with `Kr` drawn inside — the unified
outlined-monogram style shared with the other creative-app marks (Ai, Ps, Fi).
Drawn by `_draw_krita_logo()` → `_draw_outlined_monogram()` in `fetch_icons.py`
(white-on-transparent → `program_icon_mode: alpha`), reproducible.

> **Why not the real Krita logo?** Krita is GPLv3, and since the host moved to
> **GPL-3.0-or-later** its logo is now licence-compatible. But the real logo
> (`krita/pics/branding/default/*-apps-krita.png`) is a colour, organic shape:
> reduced to the keycap's 1-bit monochrome it collapses to an unrecognisable
> blob (alpha silhouette) or a fragmented mess (luma threshold). The clean
> monogram is far more legible at this resolution, so it is kept deliberately.
> Krita's **tool** icons (line-art, from the `breeze-icons` repo) would reduce
> fine and are now usable too, should authentic tool glyphs be wanted later.

## Transformations

`bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [36, 32]`,
`anchor: bottom-right` (icon sits bottom-right so it never overwrites the
firmware-drawn key letter in the top-left); drawn glyphs use `mode: alpha`.
Program icon bottom-right `[46, 40]`, `mode: alpha`. Fluent `.svg` → cairosvg
96px in `fetch_icons.py`. Pin the branch→SHA for byte-exact reproducibility; the
committed `icons/` freeze the render.

## Mapping stanza (paste into `polyhost/res/overlay-mapping.poly.yaml`)

```yaml
krita:
  overlay: [krita_template.mods.png, krita_template.combo.mods.png]
```

## macOS

The spec serves Windows and macOS from one file: `krita_template.*`
(Windows/Linux) and `krita_template_mac.*` (macOS). Krita's defaults are Qt key
sequences, and Qt reads `Ctrl` as **Command** on macOS (Krita does not set
`AA_MacDontSwapCtrlAndMeta`), so all 20 Ctrl chords are `CMDCTRL`.

Sources (Krita's own source is the authority — docs.krita.org was egress-blocked):

- <https://github.com/KDE/krita> `krita/krita.action`, `krita/kritamenu.action`,
  `plugins/**/*.action` — the default shortcuts, including the per-OS
  `<shortcut operatingSystem="macos">` overrides that
  `libs/widgetutils/kis_action_registry.cpp` applies on macOS.
- <https://github.com/KDE/kconfig> `src/gui/kstandardshortcut.cpp` — New / Open /
  Save / Save As / Close / Undo / Redo / Cut / Copy / Paste / Select all / Deselect
  carry no macOS branch.
- `krita/data/input/kritadefault.profile` — the 1/2/3 zoom keys are
  platform-independent canvas-input keys.

| Action | Windows / Linux | macOS | Why |
|---|---|---|---|
| Fill with background color | `Backspace` | `Delete` (forward delete) | `kritamenu.action` sets `Del` for `operatingSystem="macos"`; on macOS Backspace is Clear. Written twice with `only:`. |

Nothing is dropped. No macOS chord drawn here is system-reserved.

⚠️ Uncertain: **New layer on `Insert`** is unchanged on macOS in Krita's action
file, but Mac keyboards have no Insert key and macOS reports the HID Insert usage
as the Help key, so the Mac cell may never fire. Left as-is; verify on hardware.

Fixed 2026-09-30 against Krita's tool action files: "Rect select" moved from
bare `R` to `Ctrl+R` (⌘R on the Mac; `KisToolSelectRectangular.action`), and
bare `V` "Line tool" is gone (`KritaShape/KisToolLine` has no default shortcut in
`tools.action`).

## Standard editing chords (shared Fluent concepts, 2026-10)

Nothing added. New/Open/Save/Close/Undo/Redo(Ctrl+Shift+Z)/Cut/Copy/Paste/Select all
were already drawn (KStandardAction set in `libs/ui/KisMainWindow.cpp`).

- **Print**: Krita creates no Print action.
- **Find / Find next / Replace**: none in Krita.
- **Zoom**: the defaults are bare `+` / `-` (https://docs.krita.org/en/reference_manual/tools/zoom.html);
  Ctrl+= has to be user-assigned, so it is not drawn.
