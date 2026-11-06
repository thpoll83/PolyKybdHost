# Cadence OrCAD X Capture overlay: sources

One spec, `bindings.yaml`, rendered by `scripts/generate_app_overlays.py` into
`orcad_capture_template` (2 files); `fetch_icons.py` rebuilds `icons/`.
OrCAD X Capture runs on Windows only.

## How the program is recognised (unverified)

The process `Capture.exe`, reported as `capture`. Not checked on an install.
OrCAD Capture 17.x and Capture CIS use the same executable name, so they get
this set too; their default keys are mostly the same (W, P, B, J, ... are in
the Capture 9.2 quick reference card as well), but that was not compared key
by key. Allegro X Capture, if it reports the same name, gets it too. Another
program whose executable is called `capture.exe` would also match.

## Shortcut reference

OrCAD X Capture User Guide, chapter "21 - Shortcut Keys", published
December 16, 2025, read 2026-11-06:
<https://resources.pcb.cadence.com/orcad-x-capture-user-guide/21-shortcut-keys>.
The page loads the chapter from
`https://read.uberflip.com/orcad-x-technical-docs-source/21-shortcut-keys`
(an embedded viewer). The chapter has 125 rows in ten tables: all Capture
windows, text editor, schematic page editor, part editor, property editor,
schematic page and part editors, session log, text boxes, browse spreadsheet
editor and fisheye view. The chapter names no product version.

The set draws the schematic page editor, the schematic page and part editors
table, the fisheye view table and F1. F11 (run the PSpice simulation) and F12
(view simulation results) are named in the chapter's overview text rather
than in a table.

### Left out

- Keys of other windows: the property editor (spreadsheet navigation and
  editing, Ctrl+U for the propagation delay dialog), the session log
  (Ctrl+Del clears it), text boxes, the browse spreadsheet editor, the text
  editor (Ctrl+F4), the Place Part dialog (Ctrl+F4 closes it, Alt+D reloads
  the library) and the part editor (Ctrl+B and Ctrl+N, previous and next
  part). They run in the same `capture` process, but the set cannot tell the
  windows apart.
- B and E while a wire, bus or polyline is being drawn (begin and end it):
  B and E are drawn with their schematic page meaning, place bus and place bus
  entry.
- Shift+D compares an active test bench with the master design; it is drawn
  with its other meaning, descend hierarchy.
- Shift+I and Shift+N (edit the source component, edit the PSpice component):
  the chapter does not say what a component's "source" is here, so the label
  could not be made exact.
- Ctrl+Shift+Left Click (lock a component): a mouse action.
- The arrow keys and Ctrl+arrow keys (move one grid, or snap and move five
  grids), Enter and Space (act as a double-click and a click), Esc (deselect
  and return to the select tool), Backspace (delete, the same as Del).
- Ctrl+F6 (switch windows), Ctrl+F2 (select the contents of a cell), Alt+F4
  and the Alt menu sequences (exit, change product).
- Allegro X / OrCAD X Presto PCB Editor: Cadence publishes no default key
  table for it, and users define their own.

## ESC mark

No OrCAD X application icon is published at a size that can be traced:
orcad.com redirects to cadence.com, and both serve a 16x16 favicon. The mark
is drawn in `fetch_icons.py` instead: `program_marks.letter_mark()` draws a
rounded tile with "OX" cut out at 256 px, and `fetch_icons.py` reduces it to
32x32 with LANCZOS and lights pixels with alpha 128 or more. The PNG is drawn
at the keycap size and the generator copies it 1:1. The file is guarded: a
committed `orcad.png` is not redrawn. It does not reproduce the OrCAD logo.
OrCAD is a trademark of Cadence Design Systems, Inc.

## Icons

Fluent UI System Icons (`microsoft/fluentui-system-icons`, `main`) and
Material Symbols (`google/material-design-icons`, weight 300), fetched by
`icon_fetch.fluent`. A copy from KiCad is byte-identical, for the same
schematic tool. Run simulation uses the same glyph as Altium's F9.

| File | Source | Licence |
|---|---|---|
| `database.png` | Fluent `Database` | MIT |
| `fisheyedyn.png` | Material Symbols `lens_blur` | Apache-2.0 |
| `fisheyeset.png` | Material Symbols `loupe` | Apache-2.0 |
| `fisheyereset.png` | Material Symbols `blur_off` | Apache-2.0 |
| `descend.png` | Material Symbols `login` | Apache-2.0 |
| `testbench.png` | Material Symbols `science` | Apache-2.0 |
| `sendpcb.png` | Material Symbols `upload` | Apache-2.0 |
| `rectangle.png` | Material Symbols `rectangle` | Apache-2.0 |
| `selfilter.png` | Fluent `Filter` | MIT |
| `ungroup.png` | Material Symbols `join_left` | Apache-2.0 |
| `groupadd.png` | Material Symbols `add_box` | Apache-2.0 |
| `groupremove.png` | Material Symbols `indeterminate_check_box` | Apache-2.0 |
| `snaptoggle.png` | Material Symbols `grid_on` | Apache-2.0 |
| `panup.png` | Material Symbols `keyboard_double_arrow_up` | Apache-2.0 |
| `pandown.png` | Material Symbols `keyboard_double_arrow_down` | Apache-2.0 |
| `panleft.png` | Material Symbols `keyboard_double_arrow_left` | Apache-2.0 |
| `panright.png` | Material Symbols `keyboard_double_arrow_right` | Apache-2.0 |
| `simulate.png` | Material Symbols `play_circle` | Apache-2.0 |
| `simresults.png` | Material Symbols `monitoring` | Apache-2.0 |
| `wire.png` | copy of `kicad/icons/wire.png` | as there |
| `bus.png` | copy of `kicad/icons/bus.png` | as there |
| `busentry.png` | copy of `kicad/icons/busentry.png` | as there |
| `junction.png` | copy of `kicad/icons/junction.png` | as there |
| `noconnect.png` | copy of `kicad/icons/noconnect.png` | as there |
| `power.png` | copy of `kicad/icons/power.png` | as there |
| `netlabel.png` | copy of `kicad/icons/netlabel.png` | as there |
| `symbol.png` | copy of `kicad/icons/symbol.png` | as there |
| `text.png` | copy of `kicad/icons/text.png` | as there |
| `lines.png` | copy of `kicad/icons/lines.png` | as there |
| `mirrorh.png` | copy of `kicad/icons/mirrorh.png` | as there |
| `mirrorv.png` | copy of `kicad/icons/mirrorv.png` | as there |
| `rotccw.png` | copy of `kicad/icons/rotccw.png` | as there |
| `repeat.png` | copy of `kicad/icons/repeat.png` | as there |
| `refresh.png` | copy of `kicad/icons/refresh.png` | as there |
| `center.png` | copy of `kicad/icons/center.png` | as there |
| `leavesheet.png` | copy of `kicad/icons/leavesheet.png` | as there |
| `properties.png` | copy of `kicad/icons/properties.png` | as there |
| `expandconn.png` | copy of `kicad/icons/expandconn.png` | as there |
| `ground.png` | drawn in `fetch_icons.py` (stem and three bars) | this repo |
| `orcad.png` | drawn in `fetch_icons.py` (see ESC mark) | this repo |
