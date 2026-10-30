# OpenTTD overlay: sources

`scripts/generate_app_overlays.py` renders `openttd.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `openttd_template` (2 files) | OpenTTD: `openttd` on Linux, `openttd.exe` on Windows, `org.openttd.openttd` (Flathub), `steam_app_1536610` (Steam under Proton) |

The binary name is from the game's `CMakeLists.txt` (`BINARY_NAME` defaults to
`openttd`, and it is the `OUTPUT_NAME` of the `openttd` target). The Flathub
and Steam names were not checked on an install.

## Shortcut reference

The default hotkeys of OpenTTD **15.3**, the latest release on 2026-10-30
(tag `15.3`, commit `14ec60f248547d4d062a1160f0fc26d742319888`,
<https://github.com/OpenTTD/OpenTTD/tree/15.3>), read from the `Hotkey(...)`
tables in its source:

| File | Hotkey list | Keys drawn |
|---|---|---|
| `src/toolbar_gui.cpp` | `maintoolbar` | F1 to F12, Shift+F1 to Shift+F12, Pause, `=` and `-` (and with Shift), M, L, V, Ctrl+S, Ctrl+P, Ctrl+D, Ctrl+Alt+C |
| `src/main_gui.cpp` | `global` (the main window) | Ctrl+Q, Ctrl+W, Ctrl+R, `` ` ``, Z, X, Ctrl+X, Delete (alone, with Shift, with Ctrl), Space, Enter (alone, with Shift, with Ctrl, with Ctrl+Shift), Ctrl+1 to Ctrl+9, Ctrl+Shift+1 to Ctrl+Shift+8 |
| `src/terraform_gui.cpp` | `terraform` | Q, W, E (marked `WKC_GLOBAL_HOTKEY`) |
| `src/rail_gui.cpp` | `railtoolbar` | A (marked `WKC_GLOBAL_HOTKEY`) |

A user's `hotkeys.cfg` changes these; the overlay shows the defaults.

The keyboard is offered to the windows from the front to the back, and the main
toolbar last (`HandleKeypress()` in `src/window.cpp`). A letter marked
`WKC_GLOBAL_HOTKEY` is checked only after no open window took it
(`HandleGlobalHotkeys()` in `src/hotkeys.cpp`); it opens its toolbar and selects
the tool.

## Left out

- **The construction toolbars' keys** (rail, road, tram, docks, airport,
  landscaping: digits 1 to 9 and the letters S, B, T, R, C, U, I, O, P). They
  work only while that toolbar is open. A mapping entry can switch overlays on
  the window title, but OpenTTD's title is always `OpenTTD <version>`
  (`VideoDriver::GetCaption()` in `src/video/video_driver.cpp`), so it cannot
  tell when a toolbar is open.
- **C (centre on the cursor), T (chat) and D (dynamite).** They are global, but
  an open window that binds the same letter takes the key first: C converts
  rail or road and T builds a tunnel while a rail or road toolbar is open, and
  D skips an order while an order window is open.
- **The scenario editor's F4 to F12** (`scenedit_maintoolbar`): they differ
  from the game's, and the window title does not tell the editor from a game.
- **Esc** (cancel the tool being placed): it shows the program mark.
- **Ctrl+B, Ctrl+I, Ctrl+O** (bounding boxes, dirty blocks, widget outlines):
  developer aids. **Alt+0, Alt+1, Alt+2** exist only in debug builds.
- **Cmd+Q and Cmd+W** (`WKC_META`): the macOS spellings of Ctrl+Q and Ctrl+W.
  On Windows and Linux the same key is the Windows key, which the desktop takes.
- **Numpad `+` and `-`** (zoom): the keyboard has no numpad.

## Placement

As for Warcraft III (`../warcraft3/SOURCES.md`): every icon sits at the right
edge and uses the full height, and the firmware clears 3 px around it, so a
letter legend stays whole. The F-key areas use the legend widths AoE2 measured:
F1, F2, F3 and F8 34×40, F4 30×40; F5 to F7 are 30×40 like F4 (not measured),
F9 to F12 40×40, which covers the right part of the F10 to F12 legends, as on
Warcraft III. An icon used on two keys with different areas is drawn twice, so
the generator places each 1:1 (`NARROW` in `fetch_icons.py`).

All icons are flat 1-bit silhouettes. Solid icons fill a smaller box than
40×40 (`INK` in `fetch_icons.py`) so they do not outweigh the outline icons.
The transparency keys (Ctrl+digit) show the object as an outline with every
second pixel lit inside; the invisibility keys (Ctrl+Shift+digit) show it with
a bar through it. The objects follow `TransparencyOption` in
`src/transparency.h`: signs, trees, houses, industries, company buildings,
bridges, transmitters and lighthouses, catenary, loading indicators (Ctrl+9
only; it has no invisibility key).

Q (lower land) and W (raise land) are drawn by `terrain()`: ground with a pit
or a hill, and an arrow. A (autorail) is the railway track turned 45 degrees;
Shift+F7 (build railway) is the same track upright. F7 (station list) is a
train under a drawn roof. Ctrl+P and Ctrl+D (screenshots at the closest and the
default zoom) are the camera with a plus or `1:1` over it, the `1:1` set in
DejaVu Sans Bold (Bitstream Vera licence, the copy bundled with matplotlib
3.9.2). Shift+Delete (close all windows, sticky ones too) is the closed window
twice.

ESC shows "Open" over a larger "TTD" in Alfa Slab One by JM Solé (SIL OFL 1.1,
`ofl/alfaslabone/AlfaSlabOne-Regular.ttf` from google/fonts at commit
e7db6ca), drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25).

## Game art: not used

OpenTTD's own icon (`media/openttd.*` in the game's repository) is GPL-2.0
like the game, and the OpenGFX base graphics are GPL-2.0 as well ("version 2
as published by the Free Software Foundation", OpenGFX `README.md`, master
bdea551). Neither says "or later". This host is GPL-3.0-or-later, and GPL-2.0
only is not compatible with it, so neither is used. They would become an
option only with a GPL-3.0 grant from their authors.

## Icons

Font Awesome Free 6.5.2, solid style (CC BY 4.0, Fonticons, Inc.), unless a
row says otherwise.

| File | Source | Author | Licence |
|---|---|---|---|
| `pause.png` | Font Awesome `pause` | Fonticons, Inc. | CC BY 4.0 |
| `settings.png` | Font Awesome `gear` | Fonticons, Inc. | CC BY 4.0 |
| `saveload.png` | Font Awesome `floppy-disk` | Fonticons, Inc. | CC BY 4.0 |
| `smallmap.png`, `smallmap_f4.png` | Font Awesome `map` | Fonticons, Inc. | CC BY 4.0 |
| `towns.png` | Font Awesome `city` | Fonticons, Inc. | CC BY 4.0 |
| `subsidies.png` | Font Awesome `hand-holding-dollar` | Fonticons, Inc. | CC BY 4.0 |
| `stations.png` | Font Awesome `train-subway`, with a roof drawn by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `finances.png` | Font Awesome `sack-dollar` | Fonticons, Inc. | CC BY 4.0 |
| `companies.png` | Font Awesome `building` | Fonticons, Inc. | CC BY 4.0 |
| `graphs.png` | Font Awesome `chart-line` | Fonticons, Inc. | CC BY 4.0 |
| `league.png` | Font Awesome `trophy` | Fonticons, Inc. | CC BY 4.0 |
| `industries.png` | Font Awesome `industry` | Fonticons, Inc. | CC BY 4.0 |
| `trainlist.png` | Font Awesome `train` | Fonticons, Inc. | CC BY 4.0 |
| `roadvehlist.png` | Font Awesome `bus` | Fonticons, Inc. | CC BY 4.0 |
| `shiplist.png` | Font Awesome `ship` | Fonticons, Inc. | CC BY 4.0 |
| `aircraftlist.png` | Font Awesome `plane` | Fonticons, Inc. | CC BY 4.0 |
| `buildrail.png`, `autorail.png` | game-icons.net `delapouite/railway`, turned by `fetch_icons.py` | delapouite | CC BY 3.0 |
| `buildroad.png` | Font Awesome `road` | Fonticons, Inc. | CC BY 4.0 |
| `builddocks.png` | Font Awesome `anchor` | Fonticons, Inc. | CC BY 4.0 |
| `buildairport.png` | Font Awesome `plane-departure` | Fonticons, Inc. | CC BY 4.0 |
| `buildtrees.png` | Font Awesome `seedling` | Fonticons, Inc. | CC BY 4.0 |
| `music.png` | Font Awesome `music` | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png`, `zoomin_f5.png` | Font Awesome `magnifying-glass-plus` | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png`, `zoomout_f6.png` | Font Awesome `magnifying-glass-minus` | Fonticons, Inc. | CC BY 4.0 |
| `centerzoom.png` | Font Awesome `magnifying-glass-location` | Fonticons, Inc. | CC BY 4.0 |
| `viewport.png` | Font Awesome `window-restore` | Fonticons, Inc. | CC BY 4.0 |
| `transparency.png` | Font Awesome `ghost` | Fonticons, Inc. | CC BY 4.0 |
| `transparencybar.png` | Font Awesome `sliders` | Fonticons, Inc. | CC BY 4.0 |
| `refresh.png` | Font Awesome `arrows-rotate` | Fonticons, Inc. | CC BY 4.0 |
| `landscaping.png` | Font Awesome `mountain-sun` | Fonticons, Inc. | CC BY 4.0 |
| `lower.png`, `raise.png` | drawn by `fetch_icons.py` | | |
| `level.png` | Font Awesome `arrows-down-to-line` | Fonticons, Inc. | CC BY 4.0 |
| `closewindows.png`, `closeall.png` | Font Awesome `rectangle-xmark` | Fonticons, Inc. | CC BY 4.0 |
| `closenews.png` | Font Awesome `newspaper` | Fonticons, Inc. | CC BY 4.0 |
| `deletenews.png` | Font Awesome `trash-can` | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome `terminal` | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png`, `screenshotzoom.png`, `screenshotdefault.png` | Font Awesome `camera` | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome `power-off` | Fonticons, Inc. | CC BY 4.0 |
| `abandon.png` | Font Awesome `door-open` | Fonticons, Inc. | CC BY 4.0 |
| `cheats.png` | Font Awesome `wand-magic-sparkles` | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | Font Awesome `comment` | Fonticons, Inc. | CC BY 4.0 |
| `chatall.png` | Font Awesome `bullhorn` | Fonticons, Inc. | CC BY 4.0 |
| `chatcompany.png` | Font Awesome `comments` | Fonticons, Inc. | CC BY 4.0 |
| `chatserver.png` | Font Awesome `server` | Fonticons, Inc. | CC BY 4.0 |
| `transp1.png`, `invis1.png` | Font Awesome `signs-post` | Fonticons, Inc. | CC BY 4.0 |
| `transp2.png`, `invis2.png` | Font Awesome `tree` | Fonticons, Inc. | CC BY 4.0 |
| `transp3.png`, `invis3.png` | Font Awesome `house` | Fonticons, Inc. | CC BY 4.0 |
| `transp4.png`, `invis4.png` | Font Awesome `industry` | Fonticons, Inc. | CC BY 4.0 |
| `transp5.png`, `invis5.png` | Font Awesome `warehouse` | Fonticons, Inc. | CC BY 4.0 |
| `transp6.png`, `invis6.png` | Font Awesome `bridge` | Fonticons, Inc. | CC BY 4.0 |
| `transp7.png`, `invis7.png` | Font Awesome `tower-broadcast` | Fonticons, Inc. | CC BY 4.0 |
| `transp8.png`, `invis8.png` | Font Awesome `bolt` | Fonticons, Inc. | CC BY 4.0 |
| `transp9.png` | Font Awesome `percent` | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "Open" / "TTD" set in Alfa Slab One | JM Solé | SIL OFL 1.1 |

The files starting with `_` are the downloaded sources that `fetch_icons.py`
turns into the files above.
