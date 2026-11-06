# Autodesk 3ds Max overlay: sources

One spec, `bindings.yaml`, one artwork set: `3dsmax_template.*`. 3ds Max runs
on Windows only. Rebuild with `fetch_icons.py`, then
`scripts/generate_app_overlays.py` on the spec.

## Shortcuts

- **Source:** Autodesk, *Keyboard Shortcut Tables*, 3ds Max 2026 help,
  <https://help.autodesk.com/cloudhelp/2026/ENU/3DSMax-Basics/files/GUID-A73E1B09-7BFE-4A22-8153-1D3D2237B8E9.htm>
  (read 2026-11-06). The tables describe the default hotkey map used since
  3ds Max 2020.1.
- **Context drawn:** the *Main UI Hotkeys* table only. The Edit, Schematic
  View, Track View, UVW Unwrap, Material Editor, Biped, Hair Styling, Particle
  Flow, Steering Wheel and Misc tables apply while that editor has focus.
- Where one action has two keys (Render: Shift+Q and Shift+F9; Grow selection:
  Ctrl+PgUp and Ctrl+Up; Zoom in: `[` and Ctrl+=; the physical camera: Ctrl+C
  and Alt+Shift+C), both keys are drawn.
- 3ds Max defaults that differ from most applications: Ctrl+V is Clone, Ctrl+C
  creates a physical camera from the view, Ctrl+D is Select None, Ctrl+H is
  Hold. The table lists Spacebar as "Lock" under *Quad Menu Sets*; the key is
  labelled as the table names it.

154 keys, plus the ESC mark.

Left out:

- The quad menu mouse chords (Alt+RMB, Ctrl+RMB, Shift+RMB, ...).
- *Virtual Viewport* pan / zoom / toggle: numeric keypad keys, which have no
  cell.
- *Lock User Interface Toggle* and *Show Main Toolbar Toggle*: no default key.

## Icons

| File | Source | Licence |
|---|---|---|
| `saveas, hold, fetch, assettracking, normalalign, typein, groupattach, cam_physical, cam_standard, endresult, backfacing, loop, ring, refine, setflow, insertloop, polyshift, spinedge, straighten, circleloops, geopoly, geomvisibility, lock, quad_windows, advlighting, animsequence, environment, renderlast, rendersetup, children, selectbyname, cycleselect, windowcrossing, autokey, anglesnap, axisconstraints, centercycle, hide, shortcutoverride, material, pan, pan_view, quickalign, scalecycle, smartplace, statistics, sound, spacing, gizmo_down, gizmo_up, lighting, safeframes, highquality, shadeselected, bracket, zoomextall, zoomextsel, zoom2x, zoommode, trackparams, globalsearch, degradation, cameraview, disableviewport, expert, homeview, orbit, view_persp, viewundo, viewredo, highlights, floating, spotview, bgupdate, edgedfaces, background` and the `cat_*` bases | [Material Symbols](https://github.com/google/material-design-icons) (`ms:` names in `fetch_icons.py`) | Apache-2.0 |
| `new, open, save, undo, redo, delete, selectall, smartselect, zoomin, zoomout` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `move, rotate, scale, align, duplicate, extrude, grow, shrink, proportional, loopcut, save_incremental, ed_console, quadview, render, hier_parent, hier_child, select_invert, deselect, select_similar, snap_options, frame_prev, frame_next, jump_start, jump_end, play, pivot, xray, hide_others, reveal, localview, maximize, edit_mode, frame_all, zoom_region, refresh, walk, shading` | byte copies of `../blender/icons/` (same action; Material Symbols) | Apache-2.0 |
| `sel_vert, sel_edge, sel_face, key_insert, snap` | byte copies of `../blender/icons/` (drawn there) | GPL-3.0-or-later |
| `view_front, view_left, view_top, view_ortho` | drawn, `../dcc_glyphs.py` `view_cube` | GPL-3.0-or-later |
| `axis_x, axis_y, axis_z, axis_plane` | drawn, `../dcc_glyphs.py` `axis_letter` (Liberation Sans Bold) | GPL-3.0-or-later; font SIL OFL 1.1 |
| `sel_border, sel_element` | drawn in `fetch_icons.py` in the style of Blender's select-mode tiles | GPL-3.0-or-later |
| `hide_cameras, hide_geometry, hide_grids, hide_helpers, hide_lights, hide_particles, hide_shapes, hide_spacewarps` | the `cat_*` icon with a diagonal stroke, `../dcc_glyphs.py` `slashed` | Apache-2.0 (bases) |
| `3dsmax.png` (ESC mark) | drawn, see below | GPL-3.0-or-later; font SIL OFL 1.1 |

Labels that name a shared concept (Undo, Redo, Select all) are drawn by the
host's shared renderer, not from `icons/`.

**ESC mark.** Drawn in `fetch_icons.py` (`_max_mark`): a rounded tile with
"3ds" knocked out in Liberation Sans Bold, drawn at 8x and cut to 1 bit at
32x32. Simple Icons has no 3ds Max mark (checked `icons/` and
`data/simple-icons.json` on its `develop` branch, 2026-11-06; it has Autodesk,
Maya and Revit), and the 3ds Max product icon is an Autodesk trademark that is
not published under a licence that allows redistribution. The mark is the
app's own short name, not its icon, in the same family as the drawn AutoCAD
mark.

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are GPL-3.0-compatible.

## Routing

`3dsmax` in `overlay-mapping.poly.yaml`: the window handler reports
`3dsmax.exe` as `3dsmax`. ⚠️ Not checked on an install.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/3dsmax/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/3dsmax/bindings.yaml --preview /tmp/3dsmax_preview
```

`fetch_icons.py` does not redraw a drawn glyph, a composite or the mark whose
PNG already exists in `icons/`. Delete the PNG first to redraw it.
