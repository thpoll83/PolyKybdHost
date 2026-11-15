# VCMI overlay: sources

`scripts/generate_app_overlays.py` renders `vcmi.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `vcmi_template` (1 file) | VCMI, the free engine for Heroes of Might and Magic III: `vcmiclient` on Linux and macOS, `VCMI_client.exe` on Windows, `eu.vcmi.VCMI` as a Flatpak |

`vcmiclient` is the executable target in `clientapp/CMakeLists.txt`
(`add_executable(vcmiclient ...)`) and the `Exec=` line of
`clientapp/icons/vcmiclient.desktop`. On Windows the same file sets
`OUTPUT_NAME "VCMI_client"`. The Flatpak id is the `<id>` in
`launcher/eu.vcmi.VCMI.metainfo.xml`. The launcher (`vcmilauncher`,
`VCMI_launcher.exe`) is a Qt program without these keys and gets no overlay.
The window title is the version string (`SDL_CreateWindow(GameConstants::VCMI_VERSION ...)`
in `client/renderSDL/ScreenHandler.cpp`). Names not checked on an install. The
engine uses SDL2, which reports the Flatpak id as the Wayland app id; that was
not measured.

## Shortcut reference

The `keyboard` table in `config/keyBindingsConfig.json` of
<https://github.com/vcmi/vcmi>, release tag `1.7.5` (commit
`6901839ae9760dfcd1d5ff2c4aa4ef6968fee752`), read 2026-11-14. The file was named
`config/shortcutsConfig.json` in older releases. The adventure-map handler that
uses the keys is `client/adventureMap/AdventureMapShortcuts.cpp`. A user changes
the keys in the launcher or in the game's settings; this overlay shows the
defaults.

A shortcut written with a modifier ("Ctrl+H") is used only while that modifier
is held, so the Ctrl, Alt and Shift chords are on their own layers.

| Key | Adventure map | Other screens (not drawn) |
|---|---|---|
| E | End turn | lobby: extra options; town: hero exchange |
| H | Next hero | town: open hero; kingdom overview: heroes tab; main menu: high scores, hot seat |
| Ctrl+H | First hero | town: open visiting hero |
| T | Next town | battle: quick spell panel; town: tavern; hero: tight formation; kingdom overview: towns tab |
| Ctrl+T | First town | |
| N | Next hero or town (`adventureNextObject`) | battle: spell shortcut 11; main menu: new game |
| M | Move hero along its path | battle: spell shortcut 12; town: marketplace; market: maximum amount; recruitment: maximum |
| Z | Put hero to sleep | battle: toggle the turn queue |
| W | Wake hero | battle: wait |
| C | Cast spell (opens the spell book) | battle: cast spell (the same icon fits both); hero: commander |
| D | Dig for the grail | battle: defend; hero: dismiss |
| Space | Visit the object under the hero | battle: defend, next unit in tactics; town: swap armies; market: deal |
| Enter | Open the selected hero or town | dialogs: accept |
| F5 | Track hero | |
| Home, Page Up, End, Page Down | Move hero north-west, north-east, south-west, south-east | lists: first, page up, last, page down; recruitment: minimum, maximum |
| Ctrl+Page Up, Ctrl+Page Down | Move the hero or town up or down in the list | |
| Ctrl+Home, Ctrl+End | Move the hero or town to the top or bottom of the list | |
| Delete | Dismiss hero (`listHeroDismiss`) | |
| V | View world | battle: open hovered unit; lobby: random town versus |
| 1, 2, 4 | View world at 1x, 2x, 4x (while the world view is open) | battle: spell shortcuts 1, 2, 4; hero: load costume; dialogs: select entry |
| U | Switch between surface and underground | recruitment: upgrade |
| K | Kingdom overview | |
| P | Puzzle map | |
| I | Scenario information | battle: open active unit; lobby: invite players |
| Q | Quest log | battle: end auto combat; exchange: swap armies and artifacts; main menu: quit |
| G | Thieves' guild | battle: creature spell; town: mage guild, thieves' guild |
| J | Statistics | main menu: join game |
| B | Marketplace | town: town hall; hero: backpack, tactics; main menu: back |
| F6 | Toggle map grid | |
| Backspace | Reset zoom | text fields: delete character |
| Ctrl+F | Search for a map object | |
| Alt+F | Continue the search | |
| F1 | Open the wiki | |
| O | Options (`adventureGameOptions` and `globalOptions`) | |
| S | Save game | battle: surrender; hero: split army; main menu: single player |
| L | Load game | hero: loose formation; main menu: load game |
| F8 | Quick save | |
| F9 | Quick load | |
| R | Restart game | battle: retreat; town: recruitment; lobby: random map |
| Ctrl+N | New game | |
| Ctrl+M | Main menu | |
| Ctrl+Q | Quit | |
| Ctrl+Tab | Online lobby (`mainMenuLobby`) | |
| Tab | Game console (`gameActivateConsole`) | dialogs: move focus; recruitment: switch level |
| F3 | Screenshot | |
| F4 | Toggle full screen | |

Keys with no adventure-map meaning, drawn with the meaning they have:

| Key | Meaning | Screen |
|---|---|---|
| A | Auto combat | battle (also market: sacrifice all; recruitment: upgrade all; spell book: adventure tab) |
| F | Town fort | town (also battle: creature spell; lobby: flip coin) |
| Shift+H | Open the garrisoned hero | town |
| F10 | Swap armies | hero exchange |
| F11 | Swap artifacts | hero exchange |
| Shift+F11 | Swap backpack artifacts | hero exchange |
| Ctrl+F11 | Swap equipped artifacts | hero exchange |

## Left out

- The arrow keys (move the hero north, south, west, east; scroll lists): they
  keep their own legends. The keypad keys (move hero, zoom in and out) have no
  cell, so zoom in and zoom out have no drawable default key.
- 3, 5 to 9 and 0: battle spell shortcuts and hero costumes only; no
  adventure-map meaning, and each depends on what the player stored.
- Ctrl+0 to Ctrl+9 (save hero costume): only in the hero window.
- X (lobby: battle mode), the period (high scores: statistics) and Y: no
  meaning in a running game, or not bound.
- Escape (cancel, leave the world view): Esc has the program mark.
- Shortcuts with an empty default (`adventureReplayTurn`, the map list sorting
  and size filters, the spectator keys and others).
- The controller table (`joystickAxes`, `joystickButtons`).

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge
and uses the full height, and the firmware clears 3 px around it, so a letter
legend stays whole. F1, F3 and F8 are 34x40 and F4 to F6 30x40, the widths the
AoE2 set measured to keep those legends whole. F9 to F11 are 40x40.

The actions that fheroes2 also has use the icon of the fheroes2 set: end turn,
next hero, next town, move hero, sleep, cast spell, dig, visit object (fheroes2:
default action), open hero or town, view world, kingdom, puzzle, scenario
information, options, new game, save, load, quit, full screen and swap armies.
F8 and F9 are the save and load icons at 26 px with a bolt above the left edge,
as F2 in the fheroes2 set (`bolt_icons()`).

"First hero" and "First town" are the next-hero and next-town icons with "1st"
above them. The world view scales are a map with "x1", "x2", "x4", and reset
zoom is the magnifier with "1:1" (`TEXT_ICONS`, drawn by
`wesnoth.text_icons()`).

## ESC mark

ESC shows "VCMI" in Cinzel Bold (SIL OFL 1.1, `ofl/cinzel/Cinzel[wght].ttf` from
google/fonts at commit e7db6ca, weight 700), drawn over the whole cell without
the ESC legend (`program_icon_legend: false`, protocol v25).

The project's logo is not used. The source code is GPL-2.0-or-later (the
header of each source file, for example `client/GameEngine.cpp`), which is
compatible with this repository's GPL-3.0-or-later. The icon files in
`clientapp/icons/` have no licence note of their own, and the icon is a
painted, shaded drawing that does not read at 1 bit in 72x40. The game's art
(units, towns, interface) comes from the original Heroes of Might and Magic
III data files, which are proprietary and not used.

Font file: <https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf>

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/
- Bitstream Vera licence: https://dejavu-fonts.github.io/License.html

Where each icon file comes from. The table below gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`, which
`fetch_icons.py` fetches through.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`
- Material Design Icons (`mdi:<name>`): `https://raw.githubusercontent.com/Templarian/MaterialDesign/2424e748e0cc63ab7b9c095a099b9fe239b737c0/svg/<name>.svg`

| File | Source | Author | Licence |
|---|---|---|---|
| `endturn.png` | Font Awesome Free 6.5.2 `hourglass-end` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `nexthero.png` | game-icons.net `lorc/visored-helm` | lorc | CC BY 3.0 |
| `nexttown.png` | game-icons.net `delapouite/castle` | delapouite | CC BY 3.0 |
| `movehero.png` | Font Awesome Free 6.5.2 `person-walking-arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sleephero.png` | Font Awesome Free 6.5.2 `bed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `castspell.png` | Font Awesome Free 6.5.2 `wand-magic-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `dig.png` | game-icons.net `lorc/spade` | lorc | CC BY 3.0 |
| `visitobject.png` | Font Awesome Free 6.5.2 `circle-play` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `openselected.png` | Font Awesome Free 6.5.2 `up-right-from-square` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `wakehero.png` | Font Awesome Free 6.5.2 `bell` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `nextobject.png` | Font Awesome Free 6.5.2 `forward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `trackhero.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `moveNW.png` | Material Design Icons `arrow-top-left-thick` | Pictogrammers | Apache-2.0 |
| `moveNE.png` | Material Design Icons `arrow-top-right-thick` | Pictogrammers | Apache-2.0 |
| `moveSW.png` | Material Design Icons `arrow-bottom-left-thick` | Pictogrammers | Apache-2.0 |
| `moveSE.png` | Material Design Icons `arrow-bottom-right-thick` | Pictogrammers | Apache-2.0 |
| `listup.png` | Font Awesome Free 6.5.2 `arrow-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `listdown.png` | Font Awesome Free 6.5.2 `arrow-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `listtop.png` | Font Awesome Free 6.5.2 `arrows-up-to-line` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `listbottom.png` | Font Awesome Free 6.5.2 `arrows-down-to-line` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `dismiss.png` | Font Awesome Free 6.5.2 `user-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `viewworld.png` | game-icons.net `lorc/treasure-map` | lorc | CC BY 3.0 |
| `kingdom.png` | Font Awesome Free 6.5.2 `crown` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `puzzle.png` | Font Awesome Free 6.5.2 `puzzle-piece` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scenarioinfo.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `newgame.png` | Font Awesome Free 6.5.2 `file-circle-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `marketplace.png` | Font Awesome Free 6.5.2 `store` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `questlog.png` | Font Awesome Free 6.5.2 `scroll` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `thievesguild.png` | Font Awesome Free 6.5.2 `user-secret` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `statistics.png` | Font Awesome Free 6.5.2 `chart-column` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `maplevel.png` | Font Awesome Free 6.5.2 `stairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `grid.png` | Font Awesome Free 6.5.2 `table-cells` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `restart.png` | Font Awesome Free 6.5.2 `rotate` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mainmenu.png` | Font Awesome Free 6.5.2 `bars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lobby.png` | Font Awesome Free 6.5.2 `globe` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `search.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `searchnext.png` | Font Awesome Free 6.5.2 `magnifying-glass-arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `wiki.png` | Font Awesome Free 6.5.2 `book-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autocombat.png` | Font Awesome Free 6.5.2 `robot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fort.png` | Font Awesome Free 6.5.2 `chess-rook` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `garrisonhero.png` | Font Awesome Free 6.5.2 `person-shelter` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `swaparmies.png` | Font Awesome Free 6.5.2 `right-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `swapartifacts.png` | Font Awesome Free 6.5.2 `gem` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `swapbackpack.png` | Font Awesome Free 6.5.2 `suitcase` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `swapequipped.png` | Font Awesome Free 6.5.2 `shirt` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `firsthero.png` | game-icons.net `lorc/visored-helm`, with "1st" in DejaVu Sans Bold, composed by `fetch_icons.py` | lorc (icon), DejaVu fonts authors (text) | CC BY 3.0; Bitstream Vera licence |
| `firsttown.png` | game-icons.net `delapouite/castle`, with "1st" in DejaVu Sans Bold, composed by `fetch_icons.py` | delapouite (icon), DejaVu fonts authors (text) | CC BY 3.0; Bitstream Vera licence |
| `world1.png` | Font Awesome Free 6.5.2 `map` (solid), with "x1" in DejaVu Sans Bold, composed by `fetch_icons.py` | Fonticons, Inc. (icon), DejaVu fonts authors (text) | CC BY 4.0; Bitstream Vera licence |
| `world2.png` | Font Awesome Free 6.5.2 `map` (solid), with "x2" in DejaVu Sans Bold, composed by `fetch_icons.py` | Fonticons, Inc. (icon), DejaVu fonts authors (text) | CC BY 4.0; Bitstream Vera licence |
| `world4.png` | Font Awesome Free 6.5.2 `map` (solid), with "x4" in DejaVu Sans Bold, composed by `fetch_icons.py` | Fonticons, Inc. (icon), DejaVu fonts authors (text) | CC BY 4.0; Bitstream Vera licence |
| `zoomreset.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid), with "1:1" in DejaVu Sans Bold, composed by `fetch_icons.py` | Fonticons, Inc. (icon), DejaVu fonts authors (text) | CC BY 4.0; Bitstream Vera licence |
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quickload.png` | Font Awesome Free 6.5.2 `folder-open` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "VCMI" set in Cinzel Bold by `fetch_icons.py` | The Cinzel Project Authors (font) | SIL OFL 1.1 |
