# SideFX Houdini overlay: sources

Five specs. `bindings.yaml` is the Scene View set, with two artwork sets:
`houdini_template.*` (Windows and Linux) and `houdini_template_mac.*` (macOS).
The other four are loaded while the Houdini package (`houdini-package/`)
reports that pane under the pointer: `network.yaml` the Network Editor
(`houdini_network_template*`, *Network Editor set* below), `anim.yaml` the
Animation Editor (`houdini_anim_template*`), and `python.yaml` and
`textport.yaml` the Python Shell and the Textport (*Animation Editor set* and
*Python Shell and Textport sets* below). Rebuild with
`fetch_icons.py`, then `scripts/generate_app_overlays.py` on the spec.

## Shortcuts

- **Main source:** SideFX, *Hotkey quick reference*, Houdini 22.0,
  <https://www.sidefx.com/docs/houdini/start/hotkeys.html> (read 2026-11-07).
- **Scene View keys from the Basics pages** (Houdini 22.0, read 2026-11-07):
  - <https://www.sidefx.com/docs/houdini/basics/select.html>: Shift+B select
    boundary, Shift+P pattern selection, Shift+` secure selection.
  - <https://www.sidefx.com/docs/houdini/basics/view.html>: M first-person
    navigation, P tool parameters, Shift+A home all, Shift+\ pin current camera.
  - <https://www.sidefx.com/docs/houdini/basics/handles.html>: Insert pivot
    handle.
  - <https://www.sidefx.com/docs/houdini/basics/radialmenus.html>: X snapping,
    C current radial menu, V view radial menu.
- **macOS:** <https://www.sidefx.com/docs/houdini/basics/macosx.html>: "Most
  hotkeys that use Ctrl on Windows instead use ⌘ on macOS." Every Ctrl chord is
  `CMDCTRL`; Alt is Option. ⚠️ The page says "most", and does not name the
  exceptions, so a Ctrl key on the macOS set may still be Ctrl.
- **Full default table.** Since Houdini 20.5 the defaults are in
  `houdini/config/Hotkeys/HotkeyDefaultBindings.json` (with
  `HotkeyContexts.json` and `HotkeyActions.json`), described on
  <https://www.sidefx.com/docs/houdini/basics/hotkeys.html>. No official public
  copy was found: a web search and a GitHub search for the file name found
  none, and the installers (the free Apprentice one included) were not
  downloaded. The set was therefore built from the documentation pages above
  only; unofficial lists were read only to cross-check.

### Context

Houdini gives a key a different meaning in each pane, and the window title does
not say which pane has the focus. **This set draws the Scene View (3D
viewport) meanings plus the keys that work in every pane** (timeline, pane
tabs, Alt+1..9 pane types). Most of the time the pointer is over the viewport
while the tool letters are used, and the quick reference lists the viewport
keys first. No key mixes the two contexts.

With the Houdini package installed, the Network Editor meanings are drawn by
`network.yaml` (next section). Network Editor meanings of the same keys, from
<https://www.sidefx.com/docs/houdini/network/shortcuts.html>:

| Key | Network Editor |
|---|---|
| Tab | Add a node from the menu (same as drawn) |
| H / G | Show all nodes / show the selected nodes |
| `=` | Add a File node |
| Q, W, E, R, T | Node flags (Q or B is bypass) |
| Y (hold) | Cut wires |
| A, Shift+A, Alt+A (hold) | Lay out, align, distribute nodes |
| P | Floating parameter editor |
| O | Network overview |
| C | Color palette |
| Z | Shape palette |
| N | Navigation radial menu |
| U | Go up a level |
| Enter | Go inside the selected node |
| `` ` `` | Previous view |
| PgUp / PgDn | Select the node upstream / downstream |
| Shift+PgUp / Shift+PgDn | Select the previous / next sibling |
| Ctrl+1..5 / Shift+1..5 | Set / go to a quick mark |
| Shift+O | Network box |
| Shift+P | Sticky note |
| Shift+W | Tree view of the network |
| Shift+J / Shift+K / Shift+M | Minimize / restore / fit notes and boxes |
| Ctrl+F or `/` | Find |
| Ctrl+G or `>` / Ctrl+Shift+G | Next / previous match |
| 8 (while dropping a node) | Do not wire into the wire under it |

### Counts

61 keys on each platform, plus the ESC mark: 28 without a modifier, 9 Shift,
12 Ctrl (Cmd on macOS), 11 Alt, 1 Alt+Shift.

### Left out

- **Esc** (View tool): the ESC cell shows the program mark on every layer.
- **Keys held together with Space** cannot be drawn, because the keyboard has
  no Space modifier layer: Space+Z (tumble pivot), Space+H (home), Space+A
  (show all), Space+G and Space+F (show selected), Space+L (tumble around the
  view centre), Space+B (single / quad viewports), Space+O (orthographic /
  perspective), Space+E (one view / all views), Space+1..5 (Perspective, Top,
  Front, Side, UV viewport), and the Space+mouse tumble, dolly, track, tilt and
  zoom.
- **Mouse chords**: Shift-, Ctrl- and Ctrl+Shift-click selection modes,
  Ctrl+Alt+drag box zoom, Ctrl+Alt+Shift+click (open in the hotkey editor),
  holding Alt for the View tool.
- **O, Z and F** ("cycle between available handles", handles page): one action
  on three keys, and the page does not say what each key picks.
- **Shift+Up / Ctrl+Shift+Up** (expand a selection pattern): active only during
  pattern selection.
- **Ctrl+L** (edit the path of the pane's location bar).
- **Redo, Save As, Quit, Cut, Copy, Paste**: no SideFX page names their keys,
  and the third-party lists disagree (one gives Save As as Alt+S). The runtime
  shortcut harvest can still draw these keys from the menus.

⚠️ **Not on a SideFX page, drawn from the File and Edit menus:** Ctrl+N (New
scene), Ctrl+O (Open scene), Ctrl+S (Save), Ctrl+Z (Undo). Not checked on an
install.

## Network Editor set

`network.yaml`, from <https://www.sidefx.com/docs/houdini/network/shortcuts.html>
(Houdini 22.0, read 2026-11-13), plus the keys of `bindings.yaml` that work in
every pane: the timeline arrows, pane tabs, Alt+1..9 pane types, Auto-key and
the File and Edit menu keys. 70 keys on each platform, plus the ESC mark.
Routed in `overlay-mapping.poly.yaml` on `houdini://network`, for every network
type (the page lists one set of keys for all of them).

Left out: W, E, R and T (node flags whose meaning depends on the network type;
the page does not name them), the S, A and Y mouse chords other than the ones
drawn as "hold", `8` while dropping a node, and every mouse action.

New icons: `file_node, cut_wires, net_overview, color_palette, shape_palette,
prev_view, layout_nodes, align_nodes, distribute_nodes, network_box, notes_min,
notes_restore, box_fit, sibling_prev, sibling_next, mark_set, match_next,
match_prev` are Material Symbols (`ms:` names in `fetch_icons.py`,
Apache-2.0). `fit_view, group_enter, group_exit, mute, search` are byte copies
of `../blender/icons/`, and `upstream, downstream, stickynote, jumpbookmark` of
`../nuke/icons/` (Material Symbols there, Apache-2.0).

## Animation Editor set

`anim.yaml`, routed on `houdini://anim`. 45 keys on each platform, plus the ESC
mark. The package reports the Animation Editor pane but not which of its three
views (graph, dopesheet, table) is shown, so the set draws the graph view keys.
Sources (Houdini 22.0, read 2026-11-14):

- <https://www.sidefx.com/docs/houdini/ref/panes/changraph.html> (graph view):
  K set keyframe, Del delete the selected keys, 0 slopes to zero, 9 slopes to
  automatic, `,` or Shift+Left previous keyframe, `.` or Shift+Right next
  keyframe, Ctrl+C or Alt+C copy key values, Ctrl+V or Alt+V paste key values,
  I isolate channels, Shift+I revert isolate, S (hold) box-select handles on
  one channel only.
- <https://www.sidefx.com/docs/houdini/ref/panes/animeditor.html>: 1, 2 and 3
  switch to the graph, dopesheet and table view; Ctrl+Left / Ctrl+Right go to
  the previous / next bookmark. These replace the quick reference's "previous /
  next scoped keyframe" on the same keys, because the hotkey goes to the pane
  under the pointer.
- The keys of `bindings.yaml` that work in every pane: the timeline arrows,
  Ctrl+Up, pane tabs, Alt+1..9 pane types, Alt+K Auto-key, and the File and
  Edit menu keys (Ctrl+N, Ctrl+O, Ctrl+S, Ctrl+Z, not on a SideFX page).

Left out: the dopesheet keys (W ripple tool, A and Shift+A expand the selection
to the row or column, <https://www.sidefx.com/docs/houdini/ref/panes/dopesheet.html>),
the channel list keys (S select the object, G channel group, Ctrl+Del delete
channels, Ctrl+2 / Ctrl+4 subpanes,
<https://www.sidefx.com/docs/houdini/ref/panes/chanlist.html>), and every mouse
chord (Alt+click add a key, Ctrl+drag, Shift+drag). Y (box handle), named in
an earlier audit, is on no SideFX page that was found, so it is not drawn.

## Python Shell and Textport sets

Letters, digits and most chords type text in these two panes, so each set
draws only the keys SideFX names for it; every other key is blank (the route
has `layer: false`, so the Scene View set is not drawn under it). One artwork
set serves every OS: no binding uses Cmd.

- `python.yaml`, routed on `houdini://python`, 9 keys. Source:
  <https://www.sidefx.com/docs/houdini/hom/intro.html> (Getting Started, read
  2026-11-14): Home or Ctrl+A start of the line, End or Ctrl+E end of the line,
  Up / Down history, Ctrl+C sends KeyboardInterrupt (it does not copy), Ctrl+D
  closes a floating Python Shell window. Enter runs the line. ⚠️ The page gives
  the chords as Ctrl. Whether they are Ctrl or Cmd on macOS is not checked;
  they are drawn as Ctrl.
- `textport.yaml`, routed on `houdini://textport`, 7 keys. Source:
  <https://www.sidefx.com/docs/houdini/ref/windows/textport.html> (read
  2026-11-14): PgUp / PgDn scroll, Home scroll to the top, End scroll to the
  end, Up / Down history. Enter runs the command.

Not checked in Houdini: whether the pane keys (Alt+1..9, Ctrl+T, Ctrl+W) still
act while the pointer is over these panes. They are not drawn.

## Icons

| File | Source | Licence |
|---|---|---|
| `select_tool, display_options, sel_object, sel_particles, sel_dynamics, sel_boundary, secure_select, sel_pattern, tool_parms, radial_current, tab_new, tab_close, tab_tearoff, details_view, camera` | [Material Symbols](https://github.com/google/material-design-icons) (`ms:` names in `fetch_icons.py`) | Apache-2.0 |
| `selectall` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `move, rotate, scale, gizmo, sel_vert, sel_edge, sel_face, deselect, play_reverse, frame_prev, key_next, key_prev, frame_all, view_pie, ed_console, ed_graph` | byte copies of `../blender/icons/` (same action; Material Symbols) | Apache-2.0 |
| `snap` | byte copy of `../blender/icons/` (drawn there) | GPL-3.0-or-later |
| `shading, key_insert, autokey, play, frame_next, jump_start, walk, pivot` | byte copies of `../3dsmax/icons/` (same action; Material Symbols) | Apache-2.0 |
| `nodesearch, tab_next, tab_prev` | byte copies of `../nuke/icons/` (Material Symbols) | Apache-2.0 |
| `closeall, view_persp, nodeeditor, attributes, objectmanager` | byte copies of `../cinema4d/icons/` (Material Symbols) | Apache-2.0 |
| `new, open, save, undo` | byte copies of `../cinema4d/icons/` (Fluent) | MIT |
| `sel_vertex, obj_comp_toggle, material_palette, badge_key, badge_pin` | drawn in `fetch_icons.py` | GPL-3.0-or-later |
| `space_view` | the F8 object cube with four arrows, drawn in `fetch_icons.py` through `../space_hint.py` on the whole 72x40 keycap. Space shows that holding it is the view tool; the Space+key combinations stay undrawn | GPL-3.0-or-later |
| `key_move, key_rotate, key_scale, key_handle, pin_camera` | composites, `../dcc_glyphs.py` `with_badge` (move / rotate / scale / gizmo + `badge_key`, `camera` + `badge_pin`) | as their parts |
| `houdini.png` (ESC mark) | Simple Icons `houdini`, see below | artwork CC0-1.0; SideFX's mark |

| `slope_flat, slope_auto, isolate, isolate_revert, sel_channel, ed_table` (Animation Editor) | Material Symbols (`ms:` names in `fetch_icons.py`) | Apache-2.0 |
| `ed_dopesheet` | byte copy of `../blender/icons/` (Material Symbols there) | Apache-2.0 |
| `key_delete` | byte copy of `../blender/icons/` (keyframe diamond drawn there) | GPL-3.0-or-later |
| `copy, paste` | byte copies of `../maya/icons/` (Fluent, from `../cinema4d/`) | MIT |
| `bm_prev, bm_next` | byte copies of `../maya/icons/` (Material Symbols bookmark with an arrow, `../dcc_glyphs.py` composite) | as their parts |
| `line_start, line_end, file_start, file_end, page_up, page_down` (Python Shell, Textport) | byte copies of `../nano/icons/` (drawn there) | GPL-3.0-or-later |
| `exit` | byte copy of `../nano/icons/` (Fluent) | MIT |
| `histprev, histnext` | byte copies of `../jupyter/icons/` (Material Symbols) | Apache-2.0 |
| `run` | byte copy of `../jupyter/icons/` (Fluent) | MIT |
| `stop` | byte copy of `../aicli/icons/` (Fluent) | MIT |

`camera`, `badge_key` and `badge_pin` are inputs of the composites; no binding
draws them directly. Labels that name a shared concept (Select all, Save, Undo)
are drawn by the host's shared renderer, not from `icons/`.

Two of the borrowed icons have a different label in their source set but show
the same kind of thing: `view_pie` is Blender's view pie menu (here the V view
radial menu), and `attributes` is Cinema 4D's Attribute Manager (here the
Parameters pane).

**ESC mark.** The Houdini logo from Simple Icons,
<https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/houdini.svg>
(source given there: <https://www.sidefx.com/products/houdini/>), rendered at
256 px, contain-fitted into 32x32 with LANCZOS and cut at luma 128 with the dark
pixels lit (`dcc_glyphs.trace_mark`): a lit square with the spiral cut out, as
the logo is a solid square with a white spiral. The Simple Icons artwork is
CC0-1.0 (the set's licence; the entry names no other); the logo is a SideFX
trademark, used only to name the app on its own key (nominative use, as
`../brand_marks.py` describes).

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are GPL-3.0-compatible.

## Routing

`overlay-mapping.poly.yaml`, one entry with an `os: macos` branch. Names
(⚠️ none checked on an install):

- **Windows:** `houdini.exe`; the per-licence launchers `houdinifx.exe`,
  `houdinicore.exe`, `happrentice.exe`, `hindie.exe` and `hescape.exe`. The
  command-line page (<https://www.sidefx.com/docs/houdini/ref/commandline.html>)
  names `houdini` and `houdinicore`; a SideFX forum post lists `houdinifx.exe`,
  `houdinicore.exe` and `hescape.exe` in `bin` beside `houdini.exe`
  (<https://www.sidefx.com/forum/post/238223/>). `happrentice` and `hindie` are
  not on a SideFX page that was found.
- **Linux:** the same launcher names, and `houdini-bin`, the binary the launcher
  script runs, in case the window handler reports that process.
- **macOS:** the apps in `/Applications/Houdini/HoudiniX.X.XXX/`, expected as
  "Houdini FX <version>", "Houdini Core <version>", "Houdini Apprentice
  <version>" and "Houdini Indie <version>". The matcher drops the trailing
  dotted version (`houdini fx 22.0.368` → `houdini fx`). Houdini started from
  the Houdini Terminal reports `houdini`.

`tests/handler/houdini_routing_test.py` pins these names.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/houdini/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/houdini/bindings.yaml --preview /tmp/houdini_preview
```

Run the Blender, 3ds Max, Nuke, Cinema 4D, Maya, nano, Jupyter and AI CLI
(`aicli`) `fetch_icons.py` first on a fresh
checkout: the borrowed icons are copied from those sets. `fetch_icons.py` does
not redraw a drawn icon, a composite or the mark when the PNG exists. Delete it
first to redraw it.
