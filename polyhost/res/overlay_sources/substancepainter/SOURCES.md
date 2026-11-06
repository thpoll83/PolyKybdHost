# Adobe Substance 3D Painter overlay: sources

One spec, `bindings.yaml`, with two artwork sets: `substancepainter_template.*`
(Windows and Linux) and `substancepainter_template_mac.*` (macOS). Rebuild with
`fetch_icons.py`, then `scripts/generate_app_overlays.py` on the spec.

## Shortcuts

- **Source:** Adobe, *Shortcuts*, Substance 3D Painter user guide,
  <https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/interface/settings/shortcuts>
  (page "Last update: October 8, 2026", read 2026-11-06). The page has a
  Windows and a macOS column for every action. Both are drawn.
- **Editable shortcuts** table: every keyboard entry is drawn, except those
  listed below.
- **Non-editable shortcuts** table: the layer stack keys (copy, cut, paste,
  delete, duplicate, group, copy / paste layer content). Adobe notes these work
  only while the pointer is over the layer stack.
- **macOS:** the page gives Cmd where Windows has Ctrl, so those chords are
  `CMDCTRL`. Four actions use a different chord on macOS and are split with
  `only:`: Close project (Ctrl+F4 / Cmd+W), Quit (Alt+F4 / Cmd+Q), Copy and
  Paste layer content (Ctrl+Shift+C/V / Option+Cmd+C/V).
- **Linux** (Painter has a Linux build) uses the Windows set. Not checked on a
  Linux install.

64 keys per platform, plus the ESC mark.

Left out:

- *Increase / Decrease the manipulator size* (`+` / `-`): `+` is Shift+= or the
  keypad on most layouts, so the pair has no cell to share.
- *Pause engine computation* (Shift+Esc): the ESC cell shows the program mark.
- *Save as project*: no default key.
- Every mouse shortcut (camera, stencil, tool size / flow, straight lines,
  context menu) and the modifier-only entries (Ctrl or Shift while dragging).

## Icons

| File | Source | Licence |
|---|---|---|
| `hideui, mode_paint, mode_bake, bakemaps, warp, tool_paint, tool_eraser, tool_projection, tool_smudge, tool_clone, particles, absolute, invertgray, ignorestencil, hideexcluded, cam_persp, cam_ortho, channel, meshmap, animation, layout_3d2d, layout_3d, layout_2d, duplicate, group, copycontent, pastecontent` | [Material Symbols](https://github.com/google/material-design-icons) (`ms:` names in `fetch_icons.py`) | Apache-2.0 |
| `material, undo, redo, open, save, new, close, quit, export, copy, cut, paste, delete` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `gizmo, orientation, move, rotate, scale, mirror, snap, eyedropper, smooth_stroke, stroke, fill, frame_all, swap, br_mask, mask_clear, mask_invert, faceset_isolate, render` | byte copies of `../blender/icons/` (same action) | Apache-2.0 (Material), `snap` drawn, GPL-3.0-or-later |
| `brushinc, brushdec` | byte copies of `../photoshop/icons/` (drawn) | GPL-3.0-or-later |
| `tool_paint_particles, tool_eraser_particles, tool_projection_particles, tool_clone_absolute` | the tool icon with the `particles` / `absolute` icon as a badge, `../dcc_glyphs.py` `with_badge` | Apache-2.0 (bases) |
| `channel_next, channel_prev, meshmap_next, meshmap_prev` | `channel` / `meshmap` with an arrow, `../dcc_glyphs.py` `with_arrow` | Apache-2.0 (bases) |
| `painter.png` (ESC mark) | the Painter app icon, see below | Adobe's mark, used only to name the app |

Labels that name a shared concept (Undo, Redo, Copy, Cut, Paste) are drawn by
the host's shared renderer, not from `icons/`.

**ESC mark.** Adobe's product icon SVG for Painter,
<https://www.adobe.com/cc-shared/assets/img/product-icons/svg/substance-3d-painter.svg>
(the 2025 "Pt" tile, downloaded 2026-11-06), rendered at 256 px, contain-fitted
into 32x32 with LANCZOS and cut at luma 128 with the dark pixels lit
(`dcc_glyphs.trace_mark`). The dark tile is lit and the "Pt" letters are cut
out, which reads closer to the app icon than the light-lit variant. Simple
Icons has no Painter mark. The icon is an Adobe trademark; it is used only to
name the app on its own key, as the other program marks are.

⚠️ Adobe's CDN refused the request from `fetch_icons.py` (HTTP 403) but served
a plain `curl` download. To redraw the mark, download the SVG and pass it:
`fetch_icons.py --icon-svg <file>`.

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are GPL-3.0-compatible.

## Routing

`adobe substance 3d painter` in `overlay-mapping.poly.yaml`, with an
`os: macos` branch. Expected names: Windows `Adobe Substance 3D Painter.exe`,
the macOS app `Adobe Substance 3D Painter`, the Linux executable
`Adobe Substance 3D Painter`. ⚠️ None was checked on an install. The pre-2021
"Substance Painter" (Allegorithmic) is not routed.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/substancepainter/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/substancepainter/bindings.yaml --preview /tmp/painter_preview
```

`fetch_icons.py` does not redraw a composite or the mark whose PNG already
exists in `icons/`. Delete the PNG first to redraw it.
