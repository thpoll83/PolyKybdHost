# OpenRCT2 overlay: sources

`scripts/generate_app_overlays.py` renders `openrct2.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `openrct2_template` (2 files) | OpenRCT2: `openrct2` on Linux, `openrct2.exe` on Windows, `OpenRCT2` on macOS, and the Flatpak `io.openrct2.OpenRCT2` |

The binary names are from the build files of v0.5.6: `add_executable(openrct2 …)`
in `src/openrct2-ui/CMakeLists.txt`, `OUTPUT_NAME "OpenRCT2"` for the macOS
bundle in the same file, `<TargetName>openrct2</TargetName>` in
`src/openrct2-win/openrct2-win.vcxproj`, and `app-id: io.openrct2.OpenRCT2`
with `command: openrct2` in the Flathub manifest
(<https://github.com/flathub/io.openrct2.OpenRCT2>). The names the window
handler reports were not checked on an install. The window title is
"OpenRCT2".

## Shortcut reference

The default shortcuts registered in `ShortcutManager::registerDefaultShortcuts()`,
`src/openrct2-ui/input/Shortcuts.cpp`, OpenRCT2 tag `v0.5.6` (commit
82b309798a83346b7f9fc61a53847f4323deb19d), the latest release on 2026-10-30.
The labels are the English names from `data/language/en-GB.txt` at the same tag
(string ids from `src/openrct2/localisation/StringIds.h` and
`src/openrct2-ui/UiStringIds.h`).

OpenRCT2 binds by key character (`SDL_GetKeyFromName` in
`src/openrct2-ui/input/ShortcutInput.cpp`), so on a layout other than US
English the `-`, `=`, `/` and `` ` `` shortcuts are on whichever key types that
character. A user's own bindings (`shortcuts.json`) are not read.

| Key | Action |
|---|---|
| F1 / F2 / F3 / F4 / F5 | Adjust land / Adjust water / Build scenery / Build paths / Build new ride |
| B | Clear scenery |
| Z | Rotate construction object |
| F / D / R / P / G / S / M | Financial information / Research information / Rides list / Park information / Guest list / Staff list / Recent messages |
| Tab | Show map |
| C | Send message (multiplayer chat) |
| Shift+/ | Open keyboard shortcuts window |
| Ctrl+T | Open transparency options |
| Ctrl+Alt+C | Open cheats window |
| `` ` `` | Console |
| 1 / 2 | Underground view / Transparent water |
| 3 / 4 / 5 / 6 | See-through rides / See-through scenery / Invisible supports / Hide guests |
| 7 | Gridlines |
| 8 / 9 / 0 | Height marks on land / on ride tracks / on paths |
| H / V | Hide base land / Hide vertical land |
| I | Highlight path issues |
| Page Up / Page Down | Zoom view out / Zoom view in |
| Enter / Shift+Enter | Rotate view clockwise / anti-clockwise |
| Alt+Enter | Toggle windowed mode |
| Pause | Pause game |
| `-` / `=` | Reduce / Increase game speed |
| Backspace / Shift+Backspace | Close top-most window / Close all floating windows |
| Ctrl+S / Ctrl+Shift+S | Screenshot / Giant screenshot |
| Ctrl+L | Load game |
| Ctrl+F10 | Save game |

None of these changes meaning with the selection, so every default on a key
with a cell is labelled.

## Left out

- The ride construction keys (turn, slope, bank, chain lift, build, demolish,
  previous and next track). They act only while the ride construction window
  is open, and all twelve are on the numeric keypad (`NUMPAD 0` to `NUMPAD 9`,
  `NUMPAD +`, `NUMPAD -`). They do not collide with the global shortcuts, but
  the keypad has no overlay cell.
- Escape (Cancel construction mode): ESC shows the program mark.
- The arrow keys (scroll the map): the arrows keep their own legends.
- The shortcuts that have no default key (options, mute, tile inspector,
  scale factor, the other see-through toggles, and the debug shortcuts except
  the console).

## Placement

As for Age of Empires II and Warcraft III (`../aoe2/SOURCES.md`): every icon
sits at the right edge and uses the full height, and the firmware clears 3 px
around it, so a letter legend stays whole. F1 and F2 use 34×40 and F4 and F5
30×40, the widths AoE2 measured to keep those legends whole; F5 was not
measured and is given F4's width. On the digits, `-`, `=` and `` ` `` the icon
erases the shifted symbol.

All icons are flat 1-bit silhouettes, drawn at their key area. Save, Load,
Chat and Messages fill a 34×34 box; Zoom in, Zoom out and Screenshot 30×30;
Pause 26×30; the two speed arrows 34×26. Composed icons:

- 3, 4 and 6 (see-through rides, scenery, guests): the shape as a 2 px outline.
  5 (invisible supports): the pillar with every second pixel lit, because its
  parts are too thin for an outline.
- 8, 9 and 0 (height marks): a ruler (a 2 px bar with a tick every 4 px) on
  the left and the land, track or path shape in a 28×28 box.
- F5 (Build new ride): the ferris wheel of R (rides list) with the plus of the
  AoE2 control groups.
- H and V: an isometric block of land. H (hide base land) draws the top face
  dotted and the side faces solid; V (hide vertical land) draws the top face
  solid and the side faces dotted.

ESC shows "Open" over "RCT2" in Fredoka Bold (SIL OFL 1.1, the Bold instance
of `ofl/fredoka/Fredoka[wdth,wght].ttf` from google/fonts at commit e7db6ca),
drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25).

## Game art

No art from the game is used. OpenRCT2's own logo (`resources/logo/` in the
repository) is distributed in the GPL-3.0 repository and could be an option
for the ESC mark; its licence was not checked file by file. The game graphics
come from the user's RollerCoaster Tycoon 2 files, which are proprietary, and
OpenRCT2 does not ship them.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `land.png`, `_land.png` (in `heightland.png`) | Font Awesome Free 6.5.2 `mountain` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `water.png` | Font Awesome Free 6.5.2 `water` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scenery.png`, `_scenery.png` (in `seescenery.png`) | Font Awesome Free 6.5.2 `tree` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `paths.png`, `_paths.png` (in `heightpaths.png`) | Font Awesome Free 6.5.2 `shoe-prints` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clearscenery.png` | game-icons.net `lorc/wood-axe` | lorc | CC BY 3.0 |
| `rotateobject.png` | Material Design Icons `rotate-3d-variant` | Pictogrammers | Apache-2.0 |
| `finances.png` | Font Awesome Free 6.5.2 `sack-dollar` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `research.png` | Font Awesome Free 6.5.2 `flask` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rides.png`, `_rides.png` (in `newride.png`, `seerides.png`) | Material Design Icons `ferris-wheel` | Pictogrammers | Apache-2.0 |
| `park.png` | game-icons.net `delapouite/park-bench` | delapouite | CC BY 3.0 |
| `guests.png`, `_guests.png` (in `seeguests.png`) | Font Awesome Free 6.5.2 `users` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `staff.png` | Font Awesome Free 6.5.2 `helmet-safety` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `messages.png` | Font Awesome Free 6.5.2 `envelope` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `map.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | Font Awesome Free 6.5.2 `comment` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `shortcuts.png` | Font Awesome Free 6.5.2 `keyboard` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `transparency.png` | Material Design Icons `circle-opacity` | Pictogrammers | Apache-2.0 |
| `cheats.png` | Font Awesome Free 6.5.2 `wand-magic-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `underground.png` | Material Design Icons `tunnel` | Pictogrammers | Apache-2.0 |
| `transparentwater.png` | Material Design Icons `water-opacity` | Pictogrammers | Apache-2.0 |
| `_supports.png` (in `seesupports.png`) | Material Design Icons `pillar` | Pictogrammers | Apache-2.0 |
| `gridlines.png` | Material Design Icons `grid` | Pictogrammers | Apache-2.0 |
| `_track.png` (in `heighttrack.png`) | game-icons.net `delapouite/rail-road` | delapouite | CC BY 3.0 |
| `pathissues.png` | Font Awesome Free 6.5.2 `triangle-exclamation` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotatecw.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotateccw.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `windowed.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `slower.png` | Font Awesome Free 6.5.2 `backward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `faster.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closetop.png` | Font Awesome Free 6.5.2 `rectangle-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closeall.png` | Material Design Icons `close-box-multiple` | Pictogrammers | Apache-2.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `giantscreenshot.png` | Font Awesome Free 6.5.2 `panorama` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hidebase.png`, `hidevertical.png` | drawn by `fetch_icons.py` | | |
| `program.png` | Fredoka Bold, google/fonts commit e7db6ca | Milena Brandão, Hafontia (The Fredoka Project Authors) | SIL OFL 1.1 |

Material Design Icons are from Templarian/MaterialDesign at commit 2424e74.
