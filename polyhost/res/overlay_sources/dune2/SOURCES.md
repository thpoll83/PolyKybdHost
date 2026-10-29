# Dune II overlays: sources

`fetch_icons.py` rebuilds `icons/`, and `scripts/generate_app_overlays.py`
renders both sets.

| Set | Loads for |
|---|---|
| `dune_legacy_template` | Dune Legacy, the open-source remake (`dunelegacy`, window title "Dune Legacy") |
| `dune2_template` | OpenDUNE (`opendune`, window title "OpenDUNE - v0.9"), and DOSBox while it runs DUNE2.EXE |

The names come from the projects' sources, not from an install. DOSBox runs
any DOS program, so its entry gives an overlay only for a title with the word
`DUNE2` (DOSBox 0.74: `... Program:    DUNE2`; DOSBox-X: `DOSBox-X <version>:
DUNE2 - ...`) or `DUNE2.EXE` (DOSBox Staging: `DUNE2.EXE - 3000 cycles/ms`). The
titles are read off each DOSBox's source; they were not seen.

## Shortcut reference

**Dune Legacy**: `handleKeyInput()` in `src/Game.cpp` of
<https://sourceforge.net/p/dunelegacy/code> (591b9e1, v0.99.5). A digit
selects a group (a second press centres the view on it), Ctrl creates it (a
plus) and Shift adds it to the selection (a plus in a square); 0 deselects
all, Ctrl+0 removes the selection from every group. The letter orders do not
change with the selection: A attack, M move, C capture, D carryall drop, H
harvester return, R repair, U upgrade, P place, O ornithopters, G next
construction yard, F next factory. Also − and = game speed, Space pause, T
game clock, F1 to F3 zoom level, F4 to F6 skip 10 s, 30 s, 2 min (single
player), F10 sound, F11 music, F12 frame rate, Enter chat, Alt+Enter full
screen, Print Screen and Ctrl+P screenshot. Esc opens the menu: it shows the
ESC mark.

**The original game and OpenDUNE**: there are no control groups. Each command
button answers to the first letter of its name (`src/gui/widget_draw.c` of
<https://github.com/OpenDUNE/OpenDUNE>, ebea79a), so a letter means the
command of that name on what is selected: A attack, M move, R retreat
(units), return (harvester) or repair (buildings), G guard, H harvest, S stop
(harvester, MCV) or sabotage (saboteur), D deploy (MCV) or destruct
(devastator), B build it, P place it, U upgrade. F1 opens the mentat, F2 the
options, Tab and Shift+Tab select the next and previous unit. The labels name
each meaning; the icons show the most common one.

## Left out

- Dune Legacy: Alt+Tab (minimise), the arrow keys (scroll), Shift+Print
  Screen (periodic screenshots).
- The original game: F3 (the picture of the selected object, a mouse button),
  the factory window's 1 to 4, keypad 8 / 2 and = / − (only in that window),
  and the localized letters of other languages (French L, E; German U).

## Icons

All flat icons are silhouettes, shaded and dithered like the OpenRA set.

| File | Source | Author | Licence |
|---|---|---|---|
| `group*.png`, `groupnew*.png`, `groupcombine*.png`, `attackmove.png`, `stop.png`, `guard.png`, `repair.png`, `deploy.png`, `harvesters.png`, `tabupgrade.png`, `conyard.png`, `cycleproduction.png`, `zoomreset.png`, `screenshot.png`, `teamchat.png` | copied from `../openra/icons/` | see `../openra/SOURCES.md` | |
| `deselect.png` | Font Awesome Free 6.5.2 `xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ungroup.png` | Font Awesome Free 6.5.2 `link-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `move.png` | Font Awesome Free 6.5.2 `location-arrow` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `capture.png` | Font Awesome Free 6.5.2 `flag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `drop.png` | Font Awesome Free 6.5.2 `parachute-box` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `place.png` | Font Awesome Free 6.5.2 `trowel-bricks` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ornithopters.png` | game-icons.net `lorc/dragonfly` | lorc | CC BY 3.0 |
| `slower.png` | Font Awesome Free 6.5.2 `backward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `faster.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clock.png` | Font Awesome Free 6.5.2 `clock` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `skip.png` | Font Awesome Free 6.5.2 `forward-fast` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sound.png` | Font Awesome Free 6.5.2 `volume-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `music.png` | Font Awesome Free 6.5.2 `music` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fps.png` | Font Awesome Free 6.5.2 `gauge-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `retreat.png` | Font Awesome Free 6.5.2 `person-running` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `build.png` | Font Awesome Free 6.5.2 `hammer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mentat.png` | game-icons.net `lorc/brain` | lorc | CC BY 3.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `nextunit.png` | Font Awesome Free 6.5.2 `forward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `prevunit.png` | Font Awesome Free 6.5.2 `backward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoom1.png` to `zoom3.png` | `zoomreset.png` with the level in its lens, drawn by `fetch_icons.py` | | CC BY 4.0 |
| `program_legacy.png`, `program_dune2.png` | DUNE over LEGACY or II in Black Ops One | James Grieshaber | SIL OFL 1.1 |

## Keys drawn from the game files

When the original DUNE.PAK is on the machine, the host draws these keys from
the game's own build portraits (the `westwood_d2` reader in
`polyhost/services/game_assets`). The shipped files above stay the fallback
and are the only art in the repository; the game's pictures are never shipped.

| Set | Keys |
|---|---|
| Dune Legacy | 1 to 9 with no modifier, Ctrl and Shift; H (harvester), O (ornithopter), D (carryall) |
| Original | H (harvester), D (MCV) |

| Group | Atreides | Harkonnen | Ordos |
|---|---|---|---|
| 1 | light infantry | light infantry | light infantry |
| 2 | troopers | troopers | troopers |
| 3 | trike | trike | trike |
| 4 | quad | quad | quad |
| 5 | combat tank | combat tank | combat tank |
| 6 | siege tank | siege tank | siege tank |
| 7 | rocket launcher | rocket launcher | rocket launcher |
| 8 | sonic tank | devastator | deviator |
| 9 | ornithopter | ornithopter | ornithopter |

The pictures are the 32x24 build portraits in SHAPES.SHP, the ones the game
shows in its sidebar. The reader cuts away each portrait's 1 px frame and its
one-colour background and draws the unit in three levels (unlit, a 50 %
checker, lit) inside a lit outline. Two portraits use error diffusion
instead (`style:` in the recipe): the combat tank with lighter mid-tones
(`lighter`) and the devastator with a stronger contrast stretch (`stretch`). The portrait numbers are those
of Dune Legacy's `src/FileClasses/GFXManager.cpp` (72 siege tank to 91
troopers). The Dune II 1.0 demo has the same portraits and unit sprites at
the same numbers, so the reader reads 1.0 and 1.07 files alike; the numbers
were checked against the demo, not against 1.07 files. The reader can also
draw the smaller map sprites (`{unit: ..., face: ...}`), pixel for pixel.

The reader looks for DUNE.PAK (any case) in this order:

1. the folder in the `game_dune2_data_dir` setting, when set (DOSBox users
   set it: DOSBox's own folder is not the game's);
2. the folder of the running game's executable, and its `data` subfolder
   (OpenDUNE's default);
3. Dune Legacy's data folders: `%APPDATA%\DuneLegacy\data`,
   `~/.config/DuneLegacy/data`, `~/Library/Application Support/Dune
   Legacy/data`, `/usr/share/dunelegacy` and `/usr/local/share/dunelegacy`
   (and `DuneLegacy`); and OpenDUNE's `~/Library/Application
   Support/OpenDUNE/data`.

| Setting | Default | Meaning |
|---|---|---|
| `game_dune2_data_dir` | empty | a folder with DUNE.PAK; empty searches as above |
| `game_dune2_house` | `atreides` | `atreides`, `harkonnen` or `ordos` |
