# Slicer overlays: sources

One key table, `keys.yaml`, serves PrusaSlicer, Bambu Studio and OrcaSlicer.
`gen_slicer_bindings.py` writes one binding file per set from it
(`bindings_*.yaml`, generated, do not edit) and, with `--render`, runs
`scripts/generate_app_overlays.py` on each. `fetch_icons.py` rebuilds `icons/`.

    python polyhost/res/overlay_sources/slicers/fetch_icons.py
    python polyhost/res/overlay_sources/slicers/gen_slicer_bindings.py --render --preview /tmp/slicers_preview

| Set | Loads for |
|---|---|
| `prusaslicer_template` (2 files), `_mac` (3) | PrusaSlicer, editor window |
| `prusa_gcodeviewer_template` (1), `_mac` (3) | PrusaSlicer G-code Viewer |
| `bambustudio_template` (2), `_linux` (2), `_mac` (3) | Bambu Studio |
| `orcaslicer_template` (2), `_mac` (3) | OrcaSlicer |

Each set has its own ESC mark, so the user can see which slicer's set is loaded.

## Shortcut sources

Each app's keyboard-shortcuts dialog, at the default branch, read 2026-10-30
from raw.githubusercontent.com:

| App | File | Commit (date) |
|---|---|---|
| PrusaSlicer | [`src/slic3r/GUI/KBShortcutsDialog.cpp`](https://github.com/prusa3d/PrusaSlicer/blob/30ef59195e0f3ee6f270b185bb5f9fb5f349f81f/src/slic3r/GUI/KBShortcutsDialog.cpp) | `30ef591` (2026-09-21), byte-identical to the 2.9.5 release |
| Bambu Studio | [`src/slic3r/GUI/KBShortcutsDialog.cpp`](https://github.com/bambulab/BambuStudio/blob/79df7ae309be398ed30c9f397c13c9911c2edc57/src/slic3r/GUI/KBShortcutsDialog.cpp) | `79df7ae` (2026-10-13), byte-identical to release v02.08.04.61 |
| OrcaSlicer | [`src/slic3r/GUI/KBShortcutsDialog.cpp`](https://github.com/SoftFever/OrcaSlicer/blob/304924a69a68d1014a48f9fc7a72003938783042/src/slic3r/GUI/KBShortcutsDialog.cpp) and [`src/slic3r/GUI/Shortcuts.cpp`](https://github.com/SoftFever/OrcaSlicer/blob/304924a69a68d1014a48f9fc7a72003938783042/src/slic3r/GUI/Shortcuts.cpp) | `304924a` (2026-10-30) |

Other files read to settle a key the dialog states unclearly:

* PrusaSlicer 2.9.5 `GLCanvas3D.cpp` (`on_char`): which view each of the digits
  0-6 selects (0 iso, 1 top, 2 bottom, 3 front, 4 rear, 5 left, 6 right).
* Bambu Studio `src/slic3r/GUI/Gizmos/GLGizmo*.cpp`: the gizmo keys. The dialog
  lists M, S, R, C, F, L and P; the gizmos also set B (mesh boolean), T (text),
  H (fuzzy skin), N (colour painting), U (measure), Y (assemble) and E (brim
  ears), and `GLGizmosManager::handle_shortcut()` opens any gizmo by its key.
  Those seven are drawn, with the gizmo file as their source.
* OrcaSlicer's dialog lists only the fixed rows; the customisable shortcuts and
  their defaults are `shortcut_table` in `Shortcuts.cpp`.

⚠️ **OrcaSlicer's shortcut table is new.** `Shortcuts.cpp` first ships in
v2.5.0-beta; the latest stable release, v2.4.2, still has the older Bambu-style
dialog. These keys are drawn here but are not bound in 2.4.2: Ctrl+Shift+E
(Publish 3MF), Ctrl+J, Ctrl+Shift+A, Ctrl+K on the plater (2.4.2 binds it in
the object list), + and -, N, D, Ctrl+7, Ctrl+E, Ctrl+F, Ctrl+Shift+K,
Ctrl+Shift+Enter, Ctrl+Shift+Tab, PgUp/PgDn, F5, Ctrl+Q, Space and Alt+0-9. In
2.4.2 Preferences is Cmd+P on macOS, not Cmd+, , and the shortcut list is `?`.

`CMDCTRL` stands for the dialogs' `ctrl` prefix (`shortkey_ctrl_prefix()` in
PrusaSlicer and Bambu Studio, `wxMOD_CONTROL` in Orca's table), which is Cmd on
macOS. Orca's next/previous tab keys use the physical Control key on every OS
(`wxMOD_RAW_CONTROL` on macOS), so they are written `CTRL`. `+` and `?` are
characters: on a US layout they are Shift+= and Shift+/, which is where they
are drawn.

## Keys drawn (3D plater)

Each row is the key and the label each app's cell shows; an empty cell means
the app does not bind the key. Ctrl/Cmd is Cmd on macOS.

| Key | PrusaSlicer | Bambu Studio | OrcaSlicer |
|---|---|---|---|
| Ctrl/Cmd+N | New project | New project | New project |
| Ctrl/Cmd+O | Open | Open | Open |
| Ctrl/Cmd+S | Save | Save | Save |
| Ctrl/Cmd+Alt+S | Save as |  |  |
| Ctrl/Cmd+Shift+S |  | Save as | Save as |
| Ctrl/Cmd+I | Import model | Import model | Import model |
| Ctrl/Cmd+L | Import config | Show overhang |  |
| Ctrl/Cmd+Alt+L | Load config and merge |  |  |
| Ctrl/Cmd+E | Export config | Labels by layer | Show labels |
| Ctrl/Cmd+Shift+E |  |  | Publish 3MF |
| Ctrl/Cmd+Shift+I | New instance |  |  |
| Ctrl/Cmd+R | Slice | Slice | Slice |
| Ctrl/Cmd+G | Export G-code | Export G-code | Export G-code |
| Ctrl/Cmd+Shift+G | Send G-code | Print plate | Print plate |
| Ctrl/Cmd+J | Upload queue |  | Upload queue |
| Ctrl/Cmd+U | Export to SD card |  |  |
| Ctrl/Cmd+T | Eject SD card |  |  |
| Ctrl/Cmd+A | Select all | Select all | Select all |
| Ctrl/Cmd+Shift+A |  |  | Select all plates |
| Ctrl/Cmd+Z | Undo | Undo | Undo |
| Ctrl/Cmd+Y | Redo | Redo | Redo |
| Ctrl/Cmd+Shift+Z |  | Redo |  |
| Ctrl/Cmd+X |  | Cut | Cut |
| Ctrl/Cmd+C | Copy | Copy | Copy |
| Ctrl/Cmd+V | Paste | Paste | Paste |
| Delete | Delete |  |  |
| Delete (not macos) |  | Delete | Delete |
| Backspace (only macos) |  | Delete | Delete |
| Ctrl/Cmd+Delete | Delete all |  |  |
| Ctrl/Cmd+Shift+D |  | Delete all |  |
| Ctrl/Cmd+D |  |  | Delete all |
| Ctrl/Cmd+K |  | Clone | Clone |
| F5 (not macos) | Reload from disk |  |  |
| Ctrl/Cmd+Shift+R (only macos) | Reload from disk |  |  |
| Ctrl/Cmd+F | Search |  | Search |
| A | Arrange | Arrange | Arrange |
| Shift+A | Arrange selection | Arrange plate | Arrange plate |
| Q |  |  | Auto orient |
| Shift+Q |  |  | Auto orient plate |
| Shift+R |  | Auto orient |  |
| + (Shift+=) | Add instance |  | Add instance |
| - | Remove instance |  | Remove instance |
| V |  |  | Toggle printable |
| PgUp | Rotate 45° CCW |  | Rotate 45° CCW |
| PgDn | Rotate 45° CW |  | Rotate 45° CW |
| Up | Move +Y 10 mm | Move +Y 10 mm | Move +Y 10 mm |
| Down | Move -Y 10 mm | Move -Y 10 mm | Move -Y 10 mm |
| Left | Move -X 10 mm | Move -X 10 mm | Move -X 10 mm |
| Right | Move +X 10 mm | Move +X 10 mm | Move +X 10 mm |
| Shift+Up | Move +Y 1 mm | Move +Y 1 mm | Move +Y 1 mm |
| Shift+Down | Move -Y 1 mm | Move -Y 1 mm | Move -Y 1 mm |
| Shift+Left | Move -X 1 mm | Move -X 1 mm | Move -X 1 mm |
| Shift+Right | Move +X 1 mm | Move +X 1 mm | Move +X 1 mm |
| Ctrl/Cmd+Up | Move up (camera) | Move up (camera) | Move up (camera) |
| Ctrl/Cmd+Down | Move down (camera) | Move down (camera) | Move down (camera) |
| Ctrl/Cmd+Left | Move left (camera) | Move left (camera) | Move left (camera) |
| Ctrl/Cmd+Right | Move right (camera) | Move right (camera) | Move right (camera) |
| 1 | Top view | Filament 1 | Filament 1 |
| 2 | Bottom view | Filament 2 | Filament 2 |
| 3 | Front view | Filament 3 | Filament 3 |
| 4 | Rear view | Filament 4 | Filament 4 |
| 5 | Left view | Filament 5 | Filament 5 |
| 6 | Right view | Filament 6 | Filament 6 |
| 7 |  | Filament 7 | Filament 7 |
| 8 |  | Filament 8 | Filament 8 |
| 9 |  | Filament 9 | Filament 9 |
| M | Move | Move | Move |
| S | Scale | Scale | Scale |
| R | Rotate | Rotate | Rotate |
| C | Cut object | Cut object | Cut object |
| F | Place on face | Place on face | Place on face |
| L | Paint supports | Paint supports | Paint supports |
| P | Paint seam | Paint seam | Paint seam |
| H | Fuzzy skin | Fuzzy skin | Fuzzy skin |
| N | Paint colors | Paint colors | Paint colors |
| T | Text | Text | Text |
| B | Zoom to bed | Mesh boolean | Mesh boolean |
| U |  | Measure | Measure |
| Y |  | Assemble | Assemble |
| E | Show labels | Brim ears | Brim ears |
| D |  |  | Paint texture |
| 0 | Iso view |  |  |
| Ctrl/Cmd+0 |  | Default view | Default view |
| Ctrl/Cmd+1 | Plater tab | Top view | Top view |
| Ctrl/Cmd+2 | Print settings | Bottom view | Bottom view |
| Ctrl/Cmd+3 | Filament settings | Front view | Front view |
| Ctrl/Cmd+4 | Printer settings | Rear view | Rear view |
| Ctrl/Cmd+5 | 3D view | Left view | Left view |
| Ctrl/Cmd+6 | Preview | Right view | Right view |
| Ctrl/Cmd+7 |  | Iso view | Plate view |
| K | Camera type |  |  |
| Z | Zoom to selection | Zoom to selection |  |
| I | Zoom in |  | Zoom in |
| O | Zoom out |  | Zoom out |
| Ctrl/Cmd+M (not macos) | 3Dconnexion settings |  | 3Dconnexion settings |
| Ctrl/Cmd+Shift+M (only macos) | 3Dconnexion settings |  | 3Dconnexion settings |
| Shift+E |  | Labels by object |  |
| Ctrl/Cmd+Shift+K |  |  | Collision volumes |
| Ctrl/Cmd+Shift+Enter |  |  | Wireframe |
| Tab | Prepare / Preview |  | Prepare / Preview |
| Shift+Tab | Collapse sidebar | Collapse sidebar | Collapse sidebar |
| Ctrl+Tab |  |  | Next tab |
| Ctrl+Shift+Tab |  |  | Previous tab |
| Ctrl/Cmd+Tab (not macos) |  | Next tab |  |
| Ctrl/Cmd+W |  | Reset layout |  |
| Ctrl/Cmd+P (not macos) | Settings | Settings | Settings |
| Ctrl/Cmd+, (only macos) | Settings | Settings | Settings |
| ? | Keyboard shortcuts |  | Keyboard shortcuts |
| ? (not windows) |  | Keyboard shortcuts |  |
| Alt+? (only windows) |  | Keyboard shortcuts |  |
| F5 |  |  | Reload device page |
| Ctrl/Cmd+Q |  |  | Quit |
| Space |  |  | Speed Dial |
| Alt+1 |  |  | Favorite 1 |
| Alt+2 |  |  | Favorite 2 |
| Alt+3 |  |  | Favorite 3 |
| Alt+4 |  |  | Favorite 4 |
| Alt+5 |  |  | Favorite 5 |
| Alt+6 |  |  | Favorite 6 |
| Alt+7 |  |  | Favorite 7 |
| Alt+8 |  |  | Favorite 8 |
| Alt+9 |  |  | Favorite 9 |
| Alt+0 |  |  | Favorite 10 |

## PrusaSlicer G-code Viewer

PrusaSlicer ships the G-code Viewer as `prusa-gcodeviewer.exe` on Windows, a
`prusa-gcodeviewer` symlink on Linux, and `prusa-slicer --gcodeviewer` from the
Linux .desktop file and on macOS. In viewer mode the dialog shows only its
Commands and Preview pages, and none of the plater keys; the editor set would
draw gizmos that do nothing there. So the viewer has its own set:

| Key | Action |
|---|---|
| Ctrl/Cmd+O | open a G-code file |
| F5 (macOS: Cmd+Shift+R) | reload from disk |
| Up / W, Down / S | vertical slider: layer up / down |
| Left / A, Right / D | horizontal slider: move back / forward |
| X | one layer mode |
| L | legend |
| C | G-code window |

Bambu Studio and OrcaSlicer build no G-code Viewer (no `gcodeviewer` target or
symlink in `src/CMakeLists.txt`), so they have no viewer set.

## One key, several meanings

The plater meaning is drawn. The other meanings:

| App | Key | Other context: meaning |
|---|---|---|
| all | Esc | plater: deselect all (the cell shows the program mark) |
| PrusaSlicer | H, L | SLA printer: hollow, SLA support points (FDM meaning drawn) |
| PrusaSlicer | F | scale gizmo: scale to fit the print volume |
| PrusaSlicer | P, 0, 1-9 | object list: printable, default extruder, extruder N |
| PrusaSlicer | W, A, S, D, X, L, C, arrows | preview: sliders, one layer mode, legend, G-code window |
| PrusaSlicer | +, - | vertical slider: add / delete a colour change |
| Bambu Studio | L | preview: one layer mode |
| Bambu Studio | 1-9 | object list: extruder N (same meaning) |
| OrcaSlicer | D | object list: Auto Drop |
| OrcaSlicer | C, L, B | preview: G-code window, one layer mode, raw G-code (belt printers) |
| OrcaSlicer | arrows, Home, End, Shift+G | preview: slider thumbs, jump to layer |
| OrcaSlicer | C, S, F, G, T, H | painting gizmo: circle, sphere, fill, gap fill, triangle, height range |

## Left out

* Mouse actions and modifier-only rows (Ctrl, Shift or Alt held while
  dragging or scrolling).
* Keys with meaning only outside the plater (the table above) except the
  G-code Viewer's, which have their own set.
* Cmd+M on macOS in PrusaSlicer: the system's minimise, listed in the dialog.
* Bambu Studio's 3Dconnexion dialog key. The dialog says Ctrl+Shift+M
  (Cmd+M on macOS); `GLCanvas3D::on_char` handles Ctrl+M (Windows only with
  the legacy 3Dconnexion option) and Cmd+Shift+M on macOS. The two disagree,
  so neither is drawn.
* Bambu Studio's Alt+A (arrange outside the plate) and 0 (filament 10) are in
  `GLCanvas3D::on_char` but not in the dialog.
* OrcaSlicer's Ctrl+B (pin an action in the Speed Dial; only inside the Speed
  Dial) and the Go-to-tab shortcuts, which have no default key.
* Space in Bambu Studio's object list (rename).

## Process names

From each project's build files (Windows executable and Linux binary:
`OUTPUT_NAME` in `src/CMakeLists.txt`; `StartupWMClass` in the .desktop file;
macOS: `SLIC3R_APP_KEY` in `version.inc`, the bundle name):

| App | Windows | Linux | macOS |
|---|---|---|---|
| PrusaSlicer | `prusa-slicer.exe` | `prusa-slicer`, `com.prusa3d.PrusaSlicer` (Flatpak) | `PrusaSlicer` |
| G-code Viewer | `prusa-gcodeviewer.exe` | `prusa-gcodeviewer`, or `prusa-slicer` with the viewer title | `PrusaSlicer` with the viewer title; `PrusaGCodeViewer` (symlink in the bundle) |
| Bambu Studio | `bambu-studio.exe` | `bambu-studio`, `com.bambulab.BambuStudio` (Flatpak) | `BambuStudio` (Info.plist.in) or `Bambu Studio` (CMake bundle name) |
| OrcaSlicer | `orca-slicer.exe` | `orca-slicer`, `com.orcaslicer.OrcaSlicer` (Flatpak), `io.github.softfever.OrcaSlicer` (older Flathub id) | `OrcaSlicer` |

Not checked on an install: every macOS name, `com.bambulab.BambuStudio` (the
Flathub manifest is not in the repo) and `io.github.softfever.OrcaSlicer`.
The viewer title is "`<file>` - PrusaSlicer G-code Viewer-`<version>`"
(`MainFrame::update_title()`, 2.9.5); the editor title has
"PrusaSlicer-`<version>`", so the two words "PrusaSlicer G-code" select the
viewer set.

## Icons

Microsoft Fluent UI System Icons (MIT,
<https://github.com/microsoft/fluentui-system-icons>) by default; Material
Symbols (Apache-2.0, <https://github.com/google/material-design-icons>) where
`fetch_icons.py` names `ms:<name>`. Open, Save, Save as, Undo, Redo, Cut, Copy,
Paste, Select all, Delete, Zoom in, Zoom out, Settings and Quit are drawn by
the shared concept renderer.

The apps ship their own SVG icons, but PrusaSlicer is AGPL-3.0 and the forks
inherit it, so none of their art is used.

| File | Source | Licence |
|---|---|---|
| `new_project`, `import_model`, `import_config`, `export_config` | Fluent `Document Add`, `Cube Add`, `Document Arrow Left`, `Document Arrow Right` | MIT |
| `merge_config`, `send_gcode`, `print`, `tab_printer` | Fluent `Merge`, `Cloud Arrow Up`, `Print`, `Print` | MIT |
| `host_queue`, `new_instance`, `clone`, `select_plates` | Fluent `Text Bullet List Square`, `Window New`, `Square Multiple`, `Select All On` | MIT |
| `reload`, `reload_device`, `search`, `tab_plater`, `preview` | Fluent `Arrow Clockwise`, `Arrow Sync`, `Search`, `Home`, `Eye` | MIT |
| `switch_view`, `sidebar`, `next_tab`, `prev_tab` | Fluent `Arrow Swap`, `Panel Right Contract`, `Arrow Next`, `Arrow Previous` | MIT |
| `labels`, `layer_labels`, `camera_type`, `zoom_fit`, `shortcuts` | Fluent `Tag`, `Tag Multiple`, `Camera Switch`, `Zoom Fit`, `Keyboard` | MIT |
| `add_instance`, `remove_instance`, `rotate_ccw`, `rotate_cw` | Fluent `Add Square`, `Subtract Square`, `Arrow Rotate Counterclockwise`, `Arrow Rotate Clockwise` | MIT |
| `gizmo_move`, `gizmo_scale`, `gizmo_cut`, `gizmo_assembly`, `gcode_window` | Fluent `Arrow Move`, `Arrow Maximize`, `Split Vertical`, `Puzzle Piece`, `Code` | MIT |
| `layer_up`, `layer_down`, `move_back`, `move_fwd` | Fluent `Chevron Double Up`, `Chevron Double Down`, `Previous`, `Next` | MIT |
| `export_gcode`, `sd_card`, `eject`, `publish`, `slice` | Material `download`, `sd_card`, `eject`, `publish`, `stacks` | Apache-2.0 |
| `delete_all`, `tab_print`, `view_3d`, `window_reset`, `overhang` | Material `delete_sweep`, `tune`, `view_in_ar`, `view_compact`, `roofing` | Apache-2.0 |
| `collision`, `wireframe`, `zoom_bed`, `mouse3d`, `speed_dial` | Material `deployed_code_alert`, `change_history`, `fit_screen`, `joystick`, `speed` | Apache-2.0 |
| `arrange`, `arrange_sel`, `orient`, `printable` | Material `grid_view`, `dashboard_customize`, `explore`, `print_disabled` | Apache-2.0 |
| `gizmo_rotate`, `gizmo_face`, `gizmo_fuzzy`, `gizmo_text`, `gizmo_boolean`, `gizmo_measure` | Material `3d_rotation`, `vertical_align_bottom`, `grain`, `text_fields`, `join_inner`, `straighten` | Apache-2.0 |
| `one_layer`, `legend` | Material `filter_1`, `legend_toggle` | Apache-2.0 |
| `view_*` (except `view_3d`) | Fluent `Cube` above ISO / TOP / BOT / FRNT / REAR / LEFT / RGHT / DEF / PLAT, drawn 1-bit 40x40 | MIT (glyph) |
| `paint_*` | Fluent `Paint Brush` above SUP / SEAM / MMU / TEX | MIT (glyph) |
| `move_<dir>_10`, `_1`, `_cam` | Fluent `Arrow Up/Down/Left/Right` above 10mm / 1mm / VIEW | MIT (glyph) |
| `fav_1` … `fav_10` | Fluent `Star` above the number | MIT (glyph) |
| `spool`, `filament_1` … `filament_9`, `brim_ears` | drawn in `fetch_icons.py` | this repo |
| `_parts/*` | the Fluent glyphs the composites are built from | MIT |
| `bambustudio` (ESC) | Simple Icons `bambulab` | CC0-1.0 (nominative use) |
| `prusaslicer`, `orcaslicer`, `prusa_gcodeviewer` (ESC) | drawn letter tiles P / O / G with two print-layer lines (Simple Icons has no mark for these apps) | this repo |

Words on composites are Liberation Sans Bold 13 px.
