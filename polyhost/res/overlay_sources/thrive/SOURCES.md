# Thrive overlay: sources

`scripts/generate_app_overlays.py` renders `thrive.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `thrive_template` (2 files) | Thrive: `Thrive` or `Thrive.x86_64` on Linux, `Thrive.exe` on Windows |

Thrive is a Godot project. `export_presets.cfg` gives the export paths
`builds/Thrive.x86_64` (Linux) and `builds/Thrive.exe` (Windows), and
`project.godot` has `config/name="Thrive"`. The repository has no desktop file
and no Flatpak manifest for the game. The name of the macOS application, the
name under Steam with Proton and the name a Thrive Launcher install reports
were not looked up, so they are not in the mapping. Names not checked on an
install.

## Shortcut reference

<https://github.com/Revolutionary-Games/Thrive>, release tag `v1.7.0` (commit
`607a682a985b7f0867b22909657d6a3d1522ceb0`), read 2026-11-14:

- `project.godot`, section `[input]`: the default events of every action. The
  keys are physical key codes (`physical_keycode`), so they do not move with the
  keyboard layout.
- `simulation_parameters/common/input_options.json`: the name of each action and
  the game part it belongs to (`Game`, `3DGame`, `Editor`, `3DEditor`,
  `StrategyGame`).

A player changes the keys in Options > Inputs; this overlay shows the defaults.
The microbe stage (`Game`) meaning is drawn where a key has another meaning in
the editor or in a later stage.

| Key | Microbe stage (drawn) | Other parts (not drawn) |
|---|---|---|
| W, Up | Move forward (`g_move_forward`) | 3D editor: W increases the item size; editor: Up pans the camera |
| S, Down | Move backwards (`g_move_backwards`) | 3D editor: S decreases the item size; editor: Down pans the camera |
| A, Left | Move left (`g_move_left`) | editor: rotate left, Left pans the camera |
| D, Right | Move right (`g_move_right`) | editor: rotate right, Right pans the camera |
| X | Auto-move forwards (`g_hold_forward`) | |
| E | Fire toxin (`g_fire_toxin`) | |
| R | Secrete slime (`g_secrete_slime`) | |
| G | Toggle engulf mode (`g_toggle_engulf`) | |
| H | Eject engulfed objects (`g_eject_engulfed`) | |
| V | Hold for the pack commands menu (`g_pack_commands`) | |
| T | Toggle mucocyst defence (`g_toggle_mucocyst`) | strategy stages: science menu |
| I | Fire siderophore (`g_fire_siderophore`) | later stage: inventory |
| B | Toggle binding mode (`g_toggle_binding`) | |
| U | Unbind all (`g_unbind_all`) | |
| Shift+U | Toggle unbinding mode (`g_toggle_unbinding`) | |
| Y | Germinate spore (`g_germinate_spore`) | |
| M | Reproduce (`g_reproduce`) | editor: move organelle |
| Space | Toggle pause (`g_pause`) | 3D stages: move up or jump |
| J | Toggle fast mode (`g_toggle_speed_mode`) | |
| F1 | Help screen (`help`) | |
| F2 | Hide or show the HUD (`g_toggle_gui`) | |
| F3 | Toggle the FPS display (`toggle_FPS`) | |
| Shift+F3 | Toggle the performance metrics (`toggle_metrics`) | |
| Ctrl+F3 | Toggle the debug panel (`toggle_debug_panel`) | |
| F5 | Quick save (`g_quick_save`) | |
| F9 | Quick load (`quick_load`) | |
| F10 | Toggle the debug console (`toggle_debug_console`) | |
| F11, Alt+Enter | Toggle full screen (`toggle_fullscreen`) | |
| F12, Print Screen | Take a screenshot (`screenshot`) | |

Editor keys with no microbe stage meaning, drawn with the meaning they have:

| Key | Meaning |
|---|---|
| Ctrl+Z | Undo (`e_undo`) |
| Ctrl+Y, Ctrl+Shift+Z | Redo (`e_redo`) |
| Delete | Delete organelle (`e_delete`) |

`g_fire_siderophore` (I) is in `project.godot` but has no entry in
`input_options.json`. It is drawn because it is the microbe stage meaning of
the key.

## Left out

- Escape (`ui_cancel`; editor: cancel the current action): the key shows the
  program mark.
- Left Shift (sprint; 3D editor: hold for pan or rotate mode): a modifier key has
  no cell.
- The cheat keys O (glucose), L (ammonia), K (phosphates), P (enable the editor)
  and F6 (cheat menu): they act only when cheats are on.
- F7 (`d_physics_debug`): a debug key that `input_options.json` does not list.
- Keys of the later stages only: F (interact), N (build structure), Z (move down
  or crouch), C (hold to show the cursor; editor: reset the camera).
- Keypad + and - (zoom) and keypad 1, 3 and 7 (3D editor camera): the keypad has
  no cell.
- The mouse and controller events.
- The menu keys (`ui_*`: arrows, Enter, Space).

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge and
uses the full height (40×40), and the firmware clears 3 px around it, so a
letter legend stays whole. F1 to F5 use 34×40; F9 to F12 use 40×40 and cover the
right end of their legends.

All icons are flat 1-bit silhouettes. Solid shapes fill a smaller box in the
bottom-right corner (`INK` in `fetch_icons.py`). F5 and F9 are the floppy disk
and the open folder with a bolt in the top-left corner, cut out by a 2 px gap
(`quick()`).

Two keys that do the same thing (W and Up, F11 and Alt+Enter, F12 and Print
Screen, Ctrl+Y and Ctrl+Shift+Z) show the same icon.

ESC shows "Thrive" in Righteous (SIL OFL 1.1,
`ofl/righteous/Righteous-Regular.ttf` from google/fonts at commit e7db6ca) at the
largest size that fits 70 px wide, drawn over the whole cell without the ESC
legend (`program_icon_legend: false`, protocol v25).

The game's own logo and icons are not used. The code is GPL-3.0-or-later
(`LICENSE.txt`), but `assets/README.txt` says the assets use the Creative
Commons licence in `assets/LICENSE.txt`, which is Attribution-ShareAlike 3.0
Unported. CC BY-SA is not on the list of licences this repository accepts for
art.

## Icons

Licence texts for the icon and font licences named in this file:

- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Material Design Icons are from Templarian/MaterialDesign at commit 2424e74.

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png`, `backwards.png`, `left.png`, `right.png` | Material Design Icons `arrow-up-bold`, `arrow-down-bold`, `arrow-left-bold`, `arrow-right-bold` | Pictogrammers | Apache-2.0 |
| `autoforward.png` | Font Awesome Free 6.5.2 `angles-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `toxin.png` | Font Awesome Free 6.5.2 `skull-crossbones` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `slime.png` | game-icons.net `delapouite/slime` | delapouite | CC BY 3.0 |
| `engulf.png` | Material Design Icons `pac-man` | Pictogrammers | Apache-2.0 |
| `eject.png` | Material Design Icons `eject` | Pictogrammers | Apache-2.0 |
| `packcommands.png` | Font Awesome Free 6.5.2 `bullhorn` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mucocyst.png` | Font Awesome Free 6.5.2 `shield-halved` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `siderophore.png` | Material Design Icons `magnet` | Pictogrammers | Apache-2.0 |
| `binding.png` | Font Awesome Free 6.5.2 `link` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `unbindall.png` | Font Awesome Free 6.5.2 `link-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `unbinding.png` | Material Design Icons `link-variant-minus` | Pictogrammers | Apache-2.0 |
| `germinate.png` | Font Awesome Free 6.5.2 `seedling` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reproduce.png` | Material Design Icons `circle-multiple` | Pictogrammers | Apache-2.0 |
| `fastmode.png` | Font Awesome Free 6.5.2 `forward-fast` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hidehud.png` | Material Design Icons `eye-off` | Pictogrammers | Apache-2.0 |
| `fps.png` | Material Design Icons `counter` | Pictogrammers | Apache-2.0 |
| `metrics.png` | Font Awesome Free 6.5.2 `chart-line` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `debugpanel.png` | Font Awesome Free 6.5.2 `bug` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quickload.png` | Font Awesome Free 6.5.2 `folder-open` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Material Design Icons `console` | Pictogrammers | Apache-2.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `undo.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `redo.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `delete.png` | Font Awesome Free 6.5.2 `trash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "Thrive" set in Righteous by `fetch_icons.py` | Astigmatic (font) | SIL OFL 1.1 |
