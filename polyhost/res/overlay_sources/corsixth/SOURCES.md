# CorsixTH overlay: sources

`scripts/generate_app_overlays.py` renders `corsixth.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `corsixth_template` (2 files) | CorsixTH, the open source engine for Theme Hospital: `corsix-th` on Linux, `CorsixTH.exe` on Windows and `CorsixTH` on macOS (both lowercase to `corsixth`), `com.corsixth.corsixth` as a Flatpak |

The names are from the build files of v0.70.2: `add_executable(CorsixTH ...)`
in `CorsixTH/CMakeLists.txt`, with
`set_target_properties(CorsixTH PROPERTIES OUTPUT_NAME corsix-th)` for
`UNIX AND NOT APPLE`; `Exec=corsix-th` in
`CorsixTH/com.corsixth.corsixth.desktop`; and the `<id>` of
`CorsixTH/com.corsixth.corsixth.metainfo.xml`. The window title is "CorsixTH"
(`self.caption` in `CorsixTH/Lua/app.lua`). Names not checked on an install.

## Shortcut reference

The default hotkeys in `new_hotkeys_defaults()`,
`CorsixTH/Lua/config_finder.lua`, <https://github.com/CorsixTH/CorsixTH>, tag
`v0.70.2` (commit 7e84444cb0406bb04466dd5880303cd40d21d63c), the latest release
on 2026-11-14, read the same day. Where the keys are registered:
`CorsixTH/Lua/ui.lua` and `CorsixTH/Lua/game_ui.lua` at the same tag. A user's
`hotkeys.txt` changes the keys; this overlay shows the defaults.

| Key | Entry in `new_hotkeys_defaults()` | Action |
|---|---|---|
| F1 to F10 | `ingame_panel_bankManager`, `_bankStats`, `_staffManage`, `_townMap`, `_casebook`, `_research`, `_status`, `_charts`, `_policy`, `_machineMenu` | the fullscreen windows |
| T, R, C, Shift+C | `ingame_panel_map_alt`, `_research_alt`, `_casebook_alt`, `_casebook_alt02` | town map, research, casebook (second keys) |
| Ctrl+H | `ingame_panel_adviserHistory` | Adviser history |
| F, G, V, B | `ingame_panel_buildRoom`, `_furnishCorridor`, `_editRoom`, `_hireStaff` | the four buttons of the bottom panel |
| M | `ingame_openFirstMessage` | Open the first message |
| I | `ingame_toggleInfo` | Toggle the information line |
| J | `ingame_jukebox` | Jukebox |
| Space | `ingame_rotateobject` | Rotate the object being placed |
| Delete | `ingame_sellPickedUpItem` | Sell the picked-up item |
| H | `ingame_patient_gohome` | Send the patient home |
| X, Shift+X | `ingame_setTransparent`, `ingame_toggleTransparent` | Transparent walls while held; toggle them |
| Shift+A | `ingame_toggleAdvisor` | Toggle the adviser |
| P | `ingame_pause` (and `global_pause_movie`) | Pause |
| 1 to 5 | `ingame_gamespeed_slowest`, `_slower`, `_normal`, `_max`, `_thensome` | the five game speeds |
| Z | `ingame_gamespeed_speedup` | Speed up while held |
| =, Shift+= | `ingame_zoom_in`, `ingame_zoom_in_more` | Zoom in, zoom in more |
| -, Shift+- | `ingame_zoom_out`, `ingame_zoom_out_more` | Zoom out, zoom out more |
| 0 | `ingame_reset_zoom` | Reset zoom |
| Alt+A, Alt+S, Alt+M | `ingame_toggleAnnouncements`, `_toggleSounds`, `_toggleMusic` | Toggle announcements, sounds, music |
| Shift+S, Shift+L | `ingame_saveMenu`, `ingame_loadMenu` | Save menu, load menu |
| Alt+Shift+S, Alt+Shift+L | `ingame_quickSave`, `ingame_quickLoad` | Quick save, quick load |
| Shift+R, Shift+Q | `ingame_restartLevel`, `ingame_quitLevel` | Restart the level, quit the level |
| Ctrl+1 to Ctrl+0 | `ingame_recallPosition_1` to `_0` | Recall a map position |
| Alt+1 to Alt+0 | `ingame_storePosition_1` to `_0` | Store a map position |
| Enter, E | `global_confirm`, `global_confirm_alt` | Confirm a dialog |
| Q | `global_cancel_alt`, `global_window_close_alt` (and `global_stop_movie_alt`) | Close the window |
| Alt+Enter | `global_fullscreen_toggle` | Toggle fullscreen |
| Alt+F4 | `global_exitApp` | Exit |
| Shift+F10 | `global_resetApp` | Restart the program |
| Ctrl+F10 | `global_releaseMouse` | Release the mouse |
| Ctrl+S | `global_screenshot` | Screenshot |
| F11 | `ingame_showCheatWindow` | Cheat window |
| F12 | `global_showLuaConsole` | Lua console |
| Shift+D | `global_runDebugScript` | Run the debug script |
| Ctrl+D, Ctrl+T | `ingame_poopLog`, `ingame_poopStrings` | Dump the game log, dump the strings |

Keys with a second meaning that is not drawn:

| Key | Drawn | Not drawn |
|---|---|---|
| P | Pause the game | pause a movie while one plays |
| Q | Close the window | stop a movie while one plays |
| Enter, E | Confirm a dialog | no effect while no dialog is open |

F11, F12 and Shift+D are registered only while the debug option of the game's
configuration is on (`self.app.config.debug` in `ui.lua` and `game_ui.lua`).
They are drawn because the keys do nothing else.

## Left out

- Escape (`global_cancel`, `global_window_close`, `ingame_showmenubar`,
  `global_stop_movie`): ESC shows the program mark.
- The arrow keys (`ingame_scroll_up`, `_down`, `_left`, `_right`: scroll the
  map): the arrows keep their own legends.
- Shift alone (`ingame_scroll_shift`: scroll faster while held): a modifier
  without a key.

## Placement

As for OpenTTD and OpenRCT2: every icon sits at the right edge and uses the
full height, and the firmware clears 3 px around it, so a letter legend stays
whole. F1 to F3 and F8 are 34×40, F4 to F7 30×40 (the widths of the OpenTTD
set); F9 to F12 are 40×40.

All icons are flat 1-bit silhouettes. The same action has the same icon source
as in the OpenTTD and OpenRCT2 sets: pause, zoom, screenshot, save, load, exit,
fullscreen, map, research, graphs, rotate an object, close a window, console,
cheats, music. The solid shapes fill a smaller box in the bottom-right corner
(`INK` in `fetch_icons.py`).

Composed in `fetch_icons.py`:

- 1 to 5 (game speeds): five bars rising to the right, as many lit as the
  speed and the others as a 1 px outline, with the fast-forward arrows at the
  top left (`speeds()`).
- Ctrl+digit and Alt+digit (map positions): the location pin with the digit
  cut out, and for "store" the pin moved up and left with a plus. The layout
  and the measures of the 0 A.D. set's camera positions (`positions()`).
- Shift+= and Shift+- : the zoom glass at 30 px with a second plus or minus at
  the top left. 0: the plain glass with "1:1" above it.
- X: a wall with every second pixel lit inside, as the OpenTTD set draws its
  transparency keys. Shift+X: the same wall at 28 px with a lock, because this
  key keeps the walls transparent.
- Alt+Shift+S and Alt+Shift+L: the disk or the folder with a bolt, as the
  fheroes2 set draws quick save.

## ESC mark

ESC shows the green figure of CorsixTH's logo as a filled silhouette, 40 px
high, at the right edge of the cell, and "Corsix" over "TH" in Archivo Black
(SIL OFL 1.1, `ofl/archivoblack/ArchivoBlack-Regular.ttf` from google/fonts at
commit e7db6ca) in the columns left of it, drawn over the whole cell without
the ESC legend (`program_icon_legend: false`, protocol v25).

The logo is `CorsixTH/Original_Logo.svg` at tag `v0.70.2`. The repository's
`LICENSE.txt` is the MIT licence text, and the SVG has no licence statement of
its own, so it falls under the project's licence. MIT is compatible with this
repository's GPL-3.0-or-later. `fetch_icons.py` renders the SVG, keeps the
pixels where green is the strongest channel (the figure; the black and white
tile behind it and the stethoscope line are dropped) and scales that mask to
40 px high. The figure is flat, so no dither is needed. The game's art comes
from the original Theme Hospital data files, which are proprietary and not
used.

## Icons

Licence texts for the icon, logo and font licences named in this file:

- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- MIT (CorsixTH): https://github.com/CorsixTH/CorsixTH/blob/v0.70.2/LICENSE.txt
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/
- Bitstream Vera licence (DejaVu Sans Bold, the digits):
  https://dejavu-fonts.github.io/License.html

| File | Source | Author | Licence |
|---|---|---|---|
| `confirm.png` | Font Awesome Free 6.5.2 `circle-check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closewindow.png` | Font Awesome Free 6.5.2 `rectangle-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `exit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `restart.png` | Font Awesome Free 6.5.2 `arrows-rotate` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `releasemouse.png` | Font Awesome Free 6.5.2 `computer-mouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `debugscript.png` | Font Awesome Free 6.5.2 `bug` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `dumplog.png` | Font Awesome Free 6.5.2 `file-lines` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `dumpstrings.png` | Font Awesome Free 6.5.2 `language` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cheats.png` | Font Awesome Free 6.5.2 `wand-magic-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `speedup.png` | Font Awesome Free 6.5.2 `forward-fast` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `restartlevel.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quitlevel.png` | Font Awesome Free 6.5.2 `door-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `bankmanager.png` | Font Awesome Free 6.5.2 `building-columns` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `bankstats.png` | Font Awesome Free 6.5.2 `file-invoice-dollar` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `staff.png` | Font Awesome Free 6.5.2 `users-gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `townmap.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `casebook.png` | Font Awesome Free 6.5.2 `book-medical` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `research.png` | Font Awesome Free 6.5.2 `flask` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `status.png` | Font Awesome Free 6.5.2 `list-check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `charts.png` | Font Awesome Free 6.5.2 `chart-line` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `policy.png` | Font Awesome Free 6.5.2 `clipboard-list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `machines.png` | Font Awesome Free 6.5.2 `screwdriver-wrench` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `buildroom.png` | Font Awesome Free 6.5.2 `trowel-bricks` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `furnish.png` | Font Awesome Free 6.5.2 `couch` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `editroom.png` | Font Awesome Free 6.5.2 `pen-ruler` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hire.png` | Font Awesome Free 6.5.2 `user-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `firstmessage.png` | Font Awesome Free 6.5.2 `envelope-open-text` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `info.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jukebox.png` | Font Awesome Free 6.5.2 `record-vinyl` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotateobject.png` | Material Design Icons `rotate-3d-variant` | Pictogrammers | Apache-2.0 |
| `sell.png` | Font Awesome Free 6.5.2 `hand-holding-dollar` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gohome.png` | Font Awesome Free 6.5.2 `house-user` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `adviser.png` | Font Awesome Free 6.5.2 `user-tie` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `adviserhistory.png` | Font Awesome Free 6.5.2 `clock-rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `announcements.png` | Font Awesome Free 6.5.2 `bullhorn` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sounds.png` | Font Awesome Free 6.5.2 `volume-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `music.png` | Font Awesome Free 6.5.2 `music` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `townmap_f4.png`, `casebook_f5.png`, `research_f6.png` | the `map`, `book-medical` and `flask` icons above, in the 30 px area of the F key | Fonticons, Inc. | CC BY 4.0 |
| `speed1.png` to `speed5.png` | bars drawn by `fetch_icons.py`; Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `recall1.png` to `recall0.png`, `store1.png` to `store0.png` | Font Awesome Free 6.5.2 `location-dot` (solid), with a digit (DejaVu Sans Bold) and a plus drawn by `fetch_icons.py` | Fonticons, Inc.; DejaVu fonts team (digits) | CC BY 4.0; Bitstream Vera licence |
| `zoominmore.png`, `zoomoutmore.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus`, `magnifying-glass-minus` (solid), with a second sign drawn by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `resetzoom.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid), with "1:1" in DejaVu Sans Bold | Fonticons, Inc.; DejaVu fonts team (digits) | CC BY 4.0; Bitstream Vera licence |
| `transparent.png`, `toggletransparent.png` | Material Design Icons `wall`, checkered by `fetch_icons.py` | Pictogrammers | Apache-2.0 |
| `toggletransparent.png` (lock) | Font Awesome Free 6.5.2 `lock` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png`, `quickload.png` | Font Awesome Free 6.5.2 `floppy-disk`, `folder-open` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `program.png` (figure) | CorsixTH logo `CorsixTH/Original_Logo.svg`, tag v0.70.2, the green figure as a silhouette | the CorsixTH developers | MIT |
| `program.png` (name) | "Corsix" over "TH" set in Archivo Black by `fetch_icons.py` | Hector Gatti, Omnibus-Type (The Archivo Black Project Authors) | SIL OFL 1.1 |

Material Design Icons are from Templarian/MaterialDesign at commit 2424e74.
