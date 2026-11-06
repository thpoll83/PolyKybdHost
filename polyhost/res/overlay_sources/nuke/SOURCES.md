# Foundry Nuke overlay: sources

One spec, `bindings.yaml`, with two artwork sets: `nuke_template.*` (Windows
and Linux) and `nuke_template_mac.*` (macOS). Rebuild with `fetch_icons.py`,
then `scripts/generate_app_overlays.py` on the spec.

## Shortcuts

- **Source:** Foundry, *Keyboard Shortcuts*, Nuke 17.1v3 online help,
  <https://learn.foundry.com/nuke/Content/misc/hotkeys_studio.html> (read
  2026-11-06).
- **Contexts drawn:** the *Global* table and the *Node Graph* table. The other
  tables (Nuke Studio's Timeline Viewer and Timeline, 2D and 3D Compositing
  Viewer, Project bin, Properties Panel, Curve Editor / Dope Sheet, Script
  Editor, Roto/RotoPaint) give many of the same keys other meanings (in the
  Viewer, B is the blue channel; in the Node Graph it inserts a Blur), so they
  are not drawn. The set shows the keys while the Node Graph has focus.
- **Conflicts:** where the two drawn tables disagree, the Node Graph meaning is
  drawn: Ctrl+D is "Disconnect upstream node" (Global: duplicate). Backspace /
  Delete deletes the selected nodes in both.
- **macOS:** Foundry: "On Mac, replace the Ctrl key with the Cmd key." Every
  Ctrl chord is `CMDCTRL`; Alt is Option.

94 keys per platform, plus the ESC mark.

Left out:

- `+` (zoom in): Shift+= or the keypad on most layouts. `-` (zoom out) is drawn.
- `1`, `2`, `3` ... and Shift+`1` ... (connect Viewer inputs A / B), Alt+`#` and
  Ctrl+`#` (zoom percentage), Ctrl+F7..F10 / Shift+F7..F10 (save / restore
  locations 1 to 4), Ctrl+F1..F6 (save window layout), Shift+F1..F6 (change
  workspace), Alt+Shift+1..6 (open recent): slot keys, a row of keys that each
  do the same thing for another number.
- U, Y, Shift+U, Shift+Y, Alt+U, Alt+Shift+U: six "splay" variants that no
  icon tells apart.
- Ctrl+*node key* (replace the selected node, e.g. Ctrl+B with a Blur) and
  Shift+*node key* (create in a new branch): they overlap the drawn Ctrl+B
  (toggle node buffer) and Shift+A (AddMix), and the table names them only as
  a pattern.
- Shift+Esc (close tab): the ESC cell shows the program mark.
- Space long press (right-click menu), numeric keypad arrows, Ctrl+Alt+A on a
  node and every mouse chord.

## Icons

| File | Source | Licence |
|---|---|---|
| `clearcache, saveas, tab_cycle, tab_next, tab_prev, dot, blur, colorcorrect, grade, copynode, roto, rotopaint, read, write, addmix, snapall, snapsel, info, jumpbookmark, bookmark, autoplace, scriptinfo_named, scriptinfo, properties, projectsettings, nodesearch, command, versiondown, versionup, versionlatest, hideinputs, stickynote, runscript, buffer, disconnect, downstream, upstream, livegroup, proxy, pasteknobs, searchreplace, nodecolor, gizmogroup, pastebranch, newsession, precomp, extract, copyclone, declone, forceclone, rendersel` | [Material Symbols](https://github.com/google/material-design-icons) (`ms:` names in `fetch_icons.py`) | Apache-2.0 |
| `fullscreen, new, open, save, close, quit, undo, redo, copy, cut, paste, selectall, delete, zoomout` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `maximize, ed_graph, ed_dopesheet, preferences, deselect, workspace_next, workspace_prev, search, fit_view, mute, hier_child, hier_parent, merge, rename, move, swap, render_anim, play_rendered, duplicate, duplicate_linked, extrude_forked, link, node_preview, group, ungroup, group_enter, viewer` | byte copies of `../blender/icons/` (same action; Material Symbols) | Apache-2.0 |
| `nuke.png` (ESC mark) | Simple Icons `nuke`, see below | artwork CC0-1.0; Foundry's mark |

Labels that name a shared concept (Undo, Redo, Copy, Cut, Paste, Select all,
Save) are drawn by the host's shared renderer, not from `icons/`.

**ESC mark.** The Nuke logo from Simple Icons,
<https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/nuke.svg>
(source given there: <https://www.foundry.com/products/nuke>), rendered at
256 px, contain-fitted into 32x32 with LANCZOS and cut at luma 128 with the
dark pixels lit (`dcc_glyphs.trace_mark`). The Simple Icons artwork is
CC0-1.0; the logo is a Foundry trademark, used only to name the app on its own
key (nominative use, as `../brand_marks.py` describes).

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are GPL-3.0-compatible.

## Routing

The process name has the version in it, so the entry is matched three ways:

- **Linux** `Nuke17.1` and **macOS** `Nuke17.1v3` (the app bundle is named
  after the install folder) reach the `nuke` key through the glued-version rule
  in `mapping_key()` (`polyhost/handler/common.py`, documented in
  `overlay-mapping.md`). A future version needs no change.
- **Windows** `Nuke17.1.exe` is cut at its first dot by the window handler, to
  `nuke17`, before any rule runs. The entry lists `nuke11` to `nuke20`. A major
  version after 20 needs one more name.
- `nukex` (the macOS NukeX app, `NukeX17.1v3`) is listed too. On Windows and
  Linux NukeX and Nuke Studio run the same executable with a flag.

⚠️ None of these names was checked on an install. Nuke Studio's and Hiero's own
macOS apps, and Nuke Assist, are not routed: their timeline keys differ.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/nuke/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/nuke/bindings.yaml --preview /tmp/nuke_preview
```

`fetch_icons.py` does not redraw the mark when `icons/nuke.png` exists. Delete
it first to redraw it.
