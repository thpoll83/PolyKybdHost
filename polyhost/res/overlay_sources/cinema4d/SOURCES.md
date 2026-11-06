# Maxon Cinema 4D overlay: sources

One spec, `bindings.yaml`, with two artwork sets: `cinema4d_template.*`
(Windows) and `cinema4d_template_mac.*` (macOS). Cinema 4D has no Linux GUI
build. Rebuild with `fetch_icons.py`, then `scripts/generate_app_overlays.py`
on the spec.

## Shortcuts

- **Source:** Maxon, *Keyboard Shortcuts*, Cinema 4D 2027 help,
  <https://help.maxon.net/c4d/2027/en-us/Content/html/Shortcuts.html> (the
  table read from the page's Markdown copy, `Shortcuts.html.md`, 2026-11-06).
- **Contexts drawn:** the *Editor*, *File*, *General*, *Render*, *Viewport* and
  *Modeling* sections, which apply while the viewport has focus. The Timeline,
  Attribute Manager, BodyPaint 3D, Material Manager, Node Editor, Object
  Manager, Picture Viewer, Structure Manager, Motion Tracker, Script Manager,
  Asset Browser and Sculpt sections give the same keys other meanings (in the
  Timeline, F is "Go to previous key") and are not drawn.
- **Two-key sequences.** Many commands are a sequence of two keys ("M S" is
  Bevel). A sequence's first key is drawn, with a label ending in "...", only
  when every sequence behind it is the same kind of action:
  - **M** "Modeling tools...": M A to M Y, M M, M -, M #, M , are all mesh
    modeling tools and commands.
  - **K** "Knife tools...": K K line cut, K J plane cut, K L loop / path cut.
  - **N** "Display mode...": N A to N R are all viewport display modes
    (Gouraud, Quick, Constant, Hidden lines, Lines, Wireframe, Isoparms, Box,
    Skeleton, Display tag, Backface culling, Textures, X-Ray).
- **macOS:** Maxon: "Mac users please press the CMD key instead of the CTRL
  key." Every Ctrl chord is `CMDCTRL`; Alt is Option.
- **Edit menu keys.** Ctrl+Z (Undo), Ctrl+Y (Redo), Ctrl+X, Ctrl+C and Ctrl+V
  are on Cinema 4D's Edit menu but not on the shortcut page, and Maxon's Edit
  menu pages (<https://help.maxon.net/c4d/2027/en-us/Content/html/5745.html>,
  `5598.html`) name the commands without their keys. ⚠️ They are drawn from the
  menu, not from a Maxon page, and were not checked on an install.

95 keys on Windows and 94 on macOS (Ctrl+Tab is not drawn there, see below),
plus the ESC mark.

Left out:

- **U** sequences: they mix mesh commands (Optimize, Subdivide, Disconnect,
  Reverse normals) with selection commands (Loop, Ring, Fill, Invert
  selection), so no one label fits.
- **T** sequences (T 1 to T 9, T I, T O: key interpolation): Timeline only. In
  the viewport T alone is Scale, which is drawn.
- `.` as the second key for *Set SDS weighting* ("M R, ."): the page does not
  say whether `.` alone is a shortcut.
- Ctrl+Tab (full-screen mode) on macOS: Cmd+Tab is the macOS application
  switcher and never reaches the app. Drawn on Windows.
- Mouse chords (Alt+MMB / RMB / LMB camera moves, J+LMB, MMB on a view) and the
  modifier-only entries (Alt or Shift while dragging a value).

## Icons

| File | Source | Licence |
|---|---|---|
| `objectmanager, materialmanager, nodeeditor, timeline, layermanager, attributes, pictureviewer, coordinates, structure, scripts, commands, parentgen, help, closeall, merge, saveas, lasttool, lasttwotools, commander, cam_move, cam_scale, cam_rotate, zoomselected, zoomobject, axes, view_persp, presets, presets_all, presets_similar, teamrender, rendersettings, renderregion, viewundo, viewredo, isoline, melt, makeeditable, obj_move, obj_scale, obj_rotate, freehand, modelingmode, modelingsettings, quantize, workplane, modeling` | [Material Symbols](https://github.com/google/material-design-icons) (`ms:` names in `fetch_icons.py`) | Apache-2.0 |
| `closewindow, new, open, save, quit, delete, undo, redo, cut, copy, paste, selectall, fullscreen` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `move, rotate, scale, extrude, inset, stitch, knife, dissolve, mirror, orientation, context_menu, save_incremental, render, render_view, play_rendered, refresh, maximize, quadview, frame_all, deselect, select_box, select_circle, parent, adjust_last, shading` | byte copies of `../blender/icons/` (same action; Material Symbols) | Apache-2.0 |
| `snap` | byte copy of `../blender/icons/` (drawn there) | GPL-3.0-or-later |
| `view_front, view_top, axis_x, axis_y, axis_z` | byte copies of `../3dsmax/icons/` (drawn with `../dcc_glyphs.py`) | GPL-3.0-or-later |
| `view_right` | drawn, `../dcc_glyphs.py` `view_cube` | GPL-3.0-or-later |
| `cinema4d.png` (ESC mark) | Simple Icons `cinema4d`, see below | artwork CC0-1.0; Maxon's mark |

Labels that name a shared concept (Undo, Redo, Cut, Copy, Paste, Select all,
Delete) are drawn by the host's shared renderer, not from `icons/`.

**ESC mark.** The Cinema 4D logo from Simple Icons,
<https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/cinema4d.svg>
(source given there: <https://www.maxon.net/en/about-maxon/branding>), rendered
at 256 px, contain-fitted into 32x32 with LANCZOS and cut at luma 128 with the
dark pixels lit (`dcc_glyphs.trace_mark`). The Simple Icons artwork is CC0-1.0;
the logo is a Maxon trademark, used only to name the app on its own key
(nominative use, as `../brand_marks.py` describes).

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are GPL-3.0-compatible.

## Routing

`cinema 4d` in `overlay-mapping.poly.yaml`, with an `os: macos` branch.
Expected names: Windows `Cinema 4D.exe` (reported as `cinema 4d`), the macOS
app `Cinema 4D`. A trailing release year (`Cinema 4D 2026`) is dropped by the
matcher. ⚠️ Not checked on an install.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/cinema4d/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/cinema4d/bindings.yaml --preview /tmp/c4d_preview
```

Run `../3dsmax/fetch_icons.py` first on a fresh checkout: the view cubes and
axis letters are copied from that set. `fetch_icons.py` does not redraw
`view_right.png` or the mark when the PNG exists. Delete it first to redraw it.
