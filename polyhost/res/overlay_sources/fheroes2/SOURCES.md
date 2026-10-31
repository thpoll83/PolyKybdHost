# fheroes2 overlay: sources

`scripts/generate_app_overlays.py` renders `fheroes2.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `fheroes2_template` (1 file) | fheroes2, the free engine for Heroes of Might and Magic II: `fheroes2` on Linux and macOS, `fheroes2.exe` on Windows, `io.github.ihhub.Fheroes2` as a Flatpak |

`fheroes2` is the executable target in `src/fheroes2/CMakeLists.txt`
(`add_executable(fheroes2 ...)`) and the `Exec=` line of
`script/packaging/common/fheroes2.desktop`; the Flatpak id is the `<id>` in
`script/packaging/common/fheroes2.metainfo.xml`. The window title is
"fheroes2 engine, version: X" (`GetCaption()` in `src/fheroes2/game/fheroes2.cpp`).
The names were not checked on an install. The engine uses SDL2, which reports
the Flatpak id as the Wayland app id; that was not measured.

## Shortcut reference

The default hotkey table in `src/fheroes2/game/game_hotkeys.cpp` of
<https://github.com/ihhub/fheroes2>, release tag `1.1.17` (commit
`2685c2188b541660f1ce261b554c3e92f79b1775`, 2026-06-30), read 2026-10-30. The
adventure-map handler that uses the keys is `src/fheroes2/game/game_startgame.cpp`.
A user's `fheroes2.key` file changes the keys; this overlay shows the defaults.

The game ignores Shift, Ctrl and Alt when it matches a hotkey
(`Game::HotKeyPressEvent()` compares only the key), and no default binding uses
a modifier. So only the plain layer is drawn.

| Key | Adventure map | Other screens (not drawn) |
|---|---|---|
| E | End turn | |
| H | Next hero | main menu: high scores |
| T | Next town | battle: turn order display; town: thieves' guild |
| M | Start hero movement | town: marketplace, buy all in the well |
| Z | Put hero to sleep | |
| C | Cast spell | battle: cast spell (the same icon fits both) |
| D | Dig for artifact | army: dismiss hero or troop |
| Space | Default action | battle: skip turn |
| Enter | Open the focused hero or town | dialogs: OK |
| V | View world | |
| K | Kingdom summary | |
| P | Puzzle map | |
| I | Scenario information | |
| A | Adventure options | battle: auto combat |
| O | System options | battle: battle options |
| F | File options | |
| N | New game | town: shipyard |
| S | Save game | battle: surrender; town: mage guild |
| L | Load game | |
| Q | Quit | battle: quick combat |
| F2 | Quick save | |

Keys with no adventure-map meaning, drawn with the meaning they have:

| Key | Meaning | Category in the table |
|---|---|---|
| R | Retreat from battle | battle (also town: tavern) |
| W | Town well | town |
| B | Town construction screen | town (also main menu: battle-only game) |
| U | Upgrade troop | army (also editor: undo) |
| X | Exchange all troops | army (also main menu: extra large maps) |
| F4 | Toggle full screen | every screen |
| F10 | Toggle text support mode | every screen |

## Left out

- 1 to 5. On the adventure map they show or hide the control panel, radar,
  buttons, status and icons, but only while the "hide interface" option is on
  (off by default; `EventSwitchShowRadar()` and its siblings in
  `src/fheroes2/gui/interface_events.cpp`). In a town 1 to 6 open the dwellings.
  Neither meaning dominates, so the digits stay blank.
- G, J, Y: not bound.
- The arrow keys (scroll the map) and the keypad (move the hero): the arrows
  keep their own legends, and the keypad has no cell.
- Left Shift held (switch to the hero under the cursor) and the Shift, Ctrl and
  Alt clicks that split or join army stacks: modifiers with a mouse click, not a
  key.
- F5, F6 and F8 (random map tools, transfer control to the AI) and the
  backquote (developer mode): only in `WITH_DEBUG` builds.
- The main menu, campaign and map editor keys.

## Placement

As for Age of Empires II and Warcraft III (`../aoe2/SOURCES.md`): every icon
sits at the right edge and uses the full height, and the firmware clears 3 px
around it, so a letter legend stays whole. F2 is 34×40 and F4 30×40, the widths
AoE2 measured to keep those legends whole. F10 is 40×40 and covers the right
part of its legend, as Warcraft III's F10 does.

All icons are flat 1-bit silhouettes. The solid shapes (save, load, file
options, puzzle, scenario information, adventure options, default action,
upgrade, kingdom) fill a smaller box in the bottom-right corner so they do not
outweigh the outline icons (`INK` in `fetch_icons.py`). F2 is the floppy disk at
26 px with a bolt above its left edge, cut out of the disk by a 2 px gap
(`quicksave()`).

ESC shows the name "fheroes2" in Pirata One (SIL OFL 1.1,
`ofl/pirataone/PirataOne-Regular.ttf` from google/fonts at commit e7db6ca), at
the largest size that fits 70×38 px, drawn over the whole cell without the ESC
legend (`program_icon_legend: false`, protocol v25). A pixel is lit from grey 80
of 255; at 120 the thin joins of the "r" and "s" break.

The engine's own icon, `src/resources/fheroes2.png` and `fheroes2.ico` in the
same repository, is distributed with GPL-2.0 source and could be used as the
ESC mark instead. It is not used here. The game's art (units, buildings,
interface) comes from the original Heroes of Might and Magic II data files,
which are proprietary and not used.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `endturn.png` | Font Awesome Free 6.5.2 `hourglass-end` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `nexthero.png` | game-icons.net `lorc/visored-helm` | lorc | CC BY 3.0 |
| `nexttown.png` | game-icons.net `delapouite/castle` | delapouite | CC BY 3.0 |
| `movehero.png` | Font Awesome Free 6.5.2 `person-walking-arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sleephero.png` | Font Awesome Free 6.5.2 `bed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `castspell.png` | Font Awesome Free 6.5.2 `wand-magic-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `dig.png` | game-icons.net `lorc/spade` | lorc | CC BY 3.0 |
| `defaultaction.png` | Font Awesome Free 6.5.2 `circle-play` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `openfocus.png` | Font Awesome Free 6.5.2 `up-right-from-square` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `viewworld.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `kingdom.png` | Font Awesome Free 6.5.2 `crown` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `puzzle.png` | Font Awesome Free 6.5.2 `puzzle-piece` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scenarioinfo.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `adventureoptions.png` | Font Awesome Free 6.5.2 `compass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `systemoptions.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fileoptions.png` | Font Awesome Free 6.5.2 `file-lines` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `newgame.png` | Font Awesome Free 6.5.2 `file-circle-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `retreat.png` | Font Awesome Free 6.5.2 `person-running` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `well.png` | Font Awesome Free 6.5.2 `bucket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `build.png` | Font Awesome Free 6.5.2 `hammer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `upgrade.png` | Font Awesome Free 6.5.2 `circle-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `swaparmies.png` | Font Awesome Free 6.5.2 `right-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `textmode.png` | Font Awesome Free 6.5.2 `font` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "fheroes2" set in Pirata One by `fetch_icons.py` | Rodrigo Fuenzalida, Nicolas Massi (font) | SIL OFL 1.1 |
