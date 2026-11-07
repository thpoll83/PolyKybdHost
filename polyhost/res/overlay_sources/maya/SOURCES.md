# Autodesk Maya overlay: sources

One spec, `bindings.yaml`, two artwork sets: `maya_template.*` (Windows and
Linux) and `maya_template_mac.*` (macOS). Rebuild with `fetch_icons.py`, then
`scripts/generate_app_overlays.py` on the spec.

## Shortcuts

- **Source:** Autodesk, Maya 2026 help, *Keyboard Shortcuts* section (read
  2026-11-07). The 2025 pages have the same tables; only the page metadata
  differs.
  - All Maya Hotkeys,
    <https://help.autodesk.com/cloudhelp/2026/ENU/Maya-KeyboardShortcuts/files/GUID-30CACC9D-8FBE-4B85-8A8F-C5ADF32DDD4E.htm>
  - Interface hotkeys,
    <https://help.autodesk.com/cloudhelp/2026/ENU/Maya-KeyboardShortcuts/files/GUID-F5379746-7A11-48C0-AFBA-D4B333D3B63A.htm>
  - Tool and action hotkeys,
    <https://help.autodesk.com/cloudhelp/2026/ENU/Maya-KeyboardShortcuts/files/GUID-8370FB55-6BE6-4571-872B-F8291A187EC0.htm>
  - Modeling hotkeys,
    <https://help.autodesk.com/cloudhelp/2026/ENU/Maya-KeyboardShortcuts/files/GUID-0B937D23-49D1-47D4-9B81-3356BA7FD815.htm>
  - Animation hotkeys,
    <https://help.autodesk.com/cloudhelp/2026/ENU/Maya-KeyboardShortcuts/files/GUID-0639ADA0-EBE5-4703-A874-92C80E4A0516.htm>
  - Hotkeys in Maya for MacOS,
    <https://help.autodesk.com/cloudhelp/2026/ENU/Maya-KeyboardShortcuts/files/GUID-4670578A-61B8-4A02-A003-9DBA6E53003B.htm>
- **Context drawn:** the Maya Default hotkey set while a viewport or the scene
  has focus: tool operations, actions, hotbox, show and hide, display settings,
  file and edit operations, snapping, selection, menu sets, window and view
  operations, pick walk, modeling, animation keys, playback and Time Slider
  bookmarks.
- **Keys with two meanings in the tables:** 1 / 2 / 3 are both the polygon
  smoothness (no smoothing, cage + smooth, smooth) and the NURBS display
  quality (rough, medium, smooth); the labels name both. Ctrl+1 is listed as
  Isolate Select > View Selected and, in the Animation table, as "switches
  between joints, controls, and character visibility"; it is labelled
  Isolate select. Insert is both "Enter tool Edit mode" and "switch between
  move pivot and move object".
- **Held keys:** a key held for a marking menu (Space for the hotbox; Q, W, E,
  R and A held with the left mouse button) also has a tap action, and the tap
  action is drawn. The snapping keys X, C, V, J and Shift+J and the curve key
  L act while held during a drag; they are drawn with "(hold)" in the label.
- **`=` and `+`:** "=, +" increase the manipulator size; both `=` and
  Shift+`=` are drawn.

135 keys on Windows and Linux, 145 on macOS, plus the ESC mark.

### macOS

Autodesk's note on every hotkey page: on macOS, Alt = Option, Ctrl = Control,
Windows key = Command. The File and Edit rows read "Ctrl (or Cmd)". So the
macOS set keeps every Ctrl chord on Control and adds a Cmd copy of New, Open,
Save, Save As, Exit, Undo, Redo, Cut, Copy and Paste (`only: [macos]`).
⚠️ Not checked on a Mac. If Maya maps more Ctrl chords to Cmd than the table
says, those keys show on Control only. Ctrl+Space is the macOS input-source
shortcut by default and may not reach Maya.

### Left out

- Mouse chords and drags: Alt + mouse buttons (tumble, track, dolly), `\` +
  mouse (2D pan / zoom; the `\` toggle itself is drawn), Shift / Ctrl+Shift +
  drag of a manipulator (duplicate, extrude, slide), Ctrl + middle-drag,
  D (move pivot, hold + drag), K (virtual Time Slider, middle mouse), I
  (insert key, middle mouse), Time Slider drags.
- Marking menus with no documented tap action: Shift+S (keyframe / tangent
  marking menus), H (menu set marking menu), U (Artisan paint operation), O
  (Poly Brush / Poly UV marking menus).
- Painting operations (Artisan, Sculpt, Blue Pencil): Alt+F, Alt+A, Alt+C,
  Alt+R, B, Shift+B, M, N, `/`. They act only in those tools; Alt+A is drawn
  with its scene meaning (cycle rig display mode).
- Alt+J, Toggle Multicolor Feedback: applies to the Paint Skin Weights tool.
- Graph Editor, Time Editor, Outliner, Attribute Editor panning and Render View
  keys (Ctrl+Left / Ctrl+Right): they apply while that editor has focus. The
  Graph Editor keys Ctrl+Alt+. and Ctrl+Alt+, are drawn because the table says
  they select the next / previous key "without opening it".

## Icons

| File | Source | Licence |
|---|---|---|
| `complete, reference, intermediate, colorchooser, quaddraw, show, textured, quality_default, rigdisplay, proxy_toggle, proxy_both, mainmenu, panelmenu, paneltoolbar, fullpanels, manipulator, hotboxstyle, set_modeling, set_rigging, set_animation, set_rendering, pan2d, bookmark_add, bookmark_quick` and the `b_*` bases | [Material Symbols](https://github.com/google/material-design-icons) (`ms:` names in `fetch_icons.py`) | Apache-2.0 |
| `move, rotate, scale, gizmo, pivot, tab_next, tab_prev, repeat, edit_mode, uv_unwrap, parent, parent_clear, play, jump_start, frame_next, frame_prev, shading, wireframe, localview, hide_others, subdiv_up, subdiv_down, knife, duplicate, group, grow, shrink, frame_all, quadview, maximize, workspace_prev, workspace_next, hier_parent, hier_child, select_left, select_right` | byte copies of `../blender/icons/` (same action; Material Symbols there) | Apache-2.0 |
| `sel_vert, sel_edge, sel_face, key_insert, key_next, key_prev, snap` | byte copies of `../blender/icons/` (drawn there) | GPL-3.0-or-later |
| `smartselect, new, open, save, undo, redo` | byte copies of `../3dsmax/icons/` (Fluent UI System Icons there) | MIT |
| `saveas, gizmo_up, gizmo_down, viewundo, viewredo, background, hide, lighting, zoomextsel` | byte copies of `../3dsmax/icons/` (Material Symbols there) | Apache-2.0 |
| `quit, cut, copy, paste` | byte copies of `../cinema4d/icons/` (Fluent UI System Icons there) | MIT |
| `attributes, help, lasttool, quantize` | byte copies of `../cinema4d/icons/` (Material Symbols there) | Apache-2.0 |
| `smooth1, smooth2, smooth3, shaded, nudge_up, nudge_down, nudge_left, nudge_right` | drawn in `fetch_icons.py` | GPL-3.0-or-later |
| `snap_grid, snap_curve, snap_point, snap_relative, repeat_cursor, sel_vertface, conv_*, key_move, key_rotate, key_scale, ins_*, key_insert_all, selkey_next, selkey_prev, vis_*, show_last, rig_cycle, subdiv, proxy_options, to_subdiv, to_subdiv_options, lock_length, dup_special, dup_transform, frame_all_views, frame_sel_views, bm_*` | composites of the files above, `../dcc_glyphs.py` `with_badge` / `with_arrow` | as their parts (Apache-2.0, MIT, GPL-3.0-or-later) |
| `maya.png` (ESC mark) | see below | CC0-1.0 artwork; Autodesk trademark |

Labels that name a shared concept (Undo, Redo, Cut, Copy, Paste) are drawn by
the host's shared renderer, not from `icons/`.

**ESC mark.** The Autodesk Maya logo from
[Simple Icons](https://github.com/simple-icons/simple-icons) (`autodeskmaya`,
`icons/autodeskmaya.svg` on the `develop` branch, read 2026-11-07; Simple Icons
lists its source as area.autodesk.com). Simple Icons publishes its SVGs under
CC0-1.0; the logo itself is a trademark of Autodesk, Inc., shown here only to
name the application the overlay is for. `fetch_icons.py` (`_maya_mark`)
renders the first two sub-paths of the SVG (the front and back plates) at
256 px and reduces them to 32x32 1 bit. The M is knocked out of the front plate
from the pixel map `MAYA_M`: in a direct trace the M's diagonals are 1 px wide
and break apart, and the word MAYA under it is 3 px tall and unreadable.
White on transparent, `program_icon_mode: alpha`, region [37, 32], anchored
right, margin 0, so the generator places it 1:1.

PolyKybdHost is GPL-3.0-or-later; MIT, Apache-2.0 and CC0-1.0 are
GPL-3.0-compatible.

## Routing

`maya,maya.bin` in `overlay-mapping.poly.yaml`:

- Windows: `maya.exe`, reported as `maya`.
- macOS: the app "Maya", reported as `maya`. If the display name carries the
  release year ("Maya 2026"), `mapping_key()` drops the year.
- Linux: the `maya` launcher script starts the process `maya.bin`, reported
  under that name.

⚠️ None of the three names was checked on an install.
`tests/handler/maya_routing_test.py` pins the routes and that only the macOS
set has Cmd keys.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/maya/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/maya/bindings.yaml --preview /tmp/maya_preview
```

`fetch_icons.py` does not redraw a drawn glyph, a composite or the mark whose
PNG already exists in `icons/`. Delete the PNG first to redraw it.
