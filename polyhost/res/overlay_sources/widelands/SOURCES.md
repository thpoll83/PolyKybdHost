# Widelands overlay: sources

`scripts/generate_app_overlays.py` renders `widelands.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `widelands_template` (1 file) | Widelands: `widelands` on Linux and macOS, `widelands.exe` on Windows, `org.widelands.Widelands` as a Flatpak |

`widelands` is the binary target in `src/CMakeLists.txt`
(`wl_binary(widelands ...)`), and `xdg/org.widelands.Widelands.desktop` has
`Exec=widelands` and `StartupWMClass=widelands`. The Flatpak id is the name of
that desktop file. Names not checked on an install.

## Shortcut reference

The default shortcut table (`KeyboardShortcut` to `KeyboardShortcutInfo`) in
`src/wlapplication_options.cc` of <https://github.com/widelands/widelands>,
release tag `v1.3.1`, read 2026-11-14. The player changes the keys in the
game's options; this overlay shows the defaults. The entries with the scope
`kGame` or `kGlobal` are drawn. `kDefaultCtrlModifier` is Ctrl.

| Key | Plain | Ctrl | Shift |
|---|---|---|---|
| Space | Toggle building spaces | | |
| M | Toggle minimap | | |
| C | Toggle census | | |
| S | Toggle status labels | Save | |
| L | Toggle soldier levels | Load | |
| U | Toggle buildings visibility | | |
| W | Toggle overlapping workareas | | |
| A | General statistics | | |
| P | Ware statistics | | |
| B | Building statistics | | |
| I | Stock inventory | | |
| X | Soldier statistics | | |
| E | Seafaring statistics | | |
| T | Objectives | | |
| D | Diplomacy | | |
| N | Messages | | |
| V | Toggle quick navigation | | |
| Q | | Exit | |
| R | | Restart scenario or replay | |
| O | | Sound options | |
| F | | Toggle fullscreen | |
| 1 to 9 | Go to landmark 1 to 9 | Set landmark 1 to 9 | |
| 0 | | Reset zoom | |
| - | | Zoom out | |
| , . | Jump to the previous, next location | | |
| Home | Scroll to the starting field | | |
| Page Up | Increase game speed by 1× | by 10× | by 0.25× |
| Page Down | Decrease game speed by 1× | by 10× | by 0.25× |
| Enter | Chat | | |
| F1 | Encyclopedia | | |
| F2 | Tooltip accessibility mode key | | |
| F8 | Pinned note | | |
| F9 | Change music | | |
| F11 | Screenshot | | |

The same keys have other functions outside a running game, not drawn:

| Where | Keys |
|---|---|
| Main menu | N new game, L load game, R watch replay, T tutorials, H campaigns, S single player, M multiplayer, E editor, O options, A add-ons and others (scope `kMainMenu`) |
| Map editor | T tools menu, H tool history, G grid, Z oceans, O immovables, A animals, R resources, V height heat map, 1 to 0 tool size, Shift+letter tools, Ctrl+N, R, U, O, Z, Y (scope `kEditor`) |

## Left out

- Ctrl++ (zoom in): the default is `SDLK_PLUS`. A US layout has no key that
  sends that key code without Shift (the `=` key sends `SDLK_EQUALS`); the
  keypad plus is mapped to it and has no cell.
- The keys of single windows: G (go to the location of a message) and Alt+0 to
  Alt+6 (message filters) in the messages window; J, F, O, Shift+O and Shift+0
  to Shift+7 in the seafaring statistics window.
- Delete (delete the selected item of a list), Ctrl+X, C, V, A (text fields),
  the Menu key.
- Ctrl+Shift+Space (debug console) and Ctrl+Shift+Backspace (cheat mode):
  developer tools.
- Pause (pause; Shift+Pause resets the game speed): no cell.
- The fast-place shortcuts (`FP(...)`): no default key (`SDLK_UNKNOWN`).
- The arrow keys (scroll the map) keep their own legends.

## Placement

As for 0 A.D. and fheroes2: every icon sits at the right edge and uses the full
height, and the firmware clears 3 px around it, so a letter legend stays whole.
All icons are flat 1-bit silhouettes drawn at their key area, so the generator
places them 1:1. The solid shapes fill a smaller box (`INK` in
`fetch_icons.py`). The landmarks are a location pin with the number cut out;
Ctrl (set) moves the pin up and left and adds a plus. The six game speed keys
show the forward arrows over the step (+1×, −1×, +¼×, −¼×, +10×, −10×) in
DejaVu Sans Bold.

ESC shows the game's own logo, `data/images/logos/wl-ico-128.png` at tag
`v1.3.1`, 40×40 at the right edge beside the ESC legend. Licence reasoning: the
source files of Widelands say "either version 2 of the License, or (at your
option) any later version" (the header of `src/wlapplication_options.cc`), and
`COPYING` is the GPL version 2 text. The logo file has no licence of its own in
the files read, so it falls under the project's licence, GPL-2.0-or-later,
which is compatible with this repository's GPL-3.0-or-later. The logo is a
green W behind a red L; as one silhouette the letters merge at 1 bit, so
`program()` splits them by colour and clears the W 1 px around the L. The
committed `program.png` is kept on a re-run.

## Icons

Licence texts for the licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/

Where each icon file comes from. The icon table gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`
- GPL-2.0-or-later: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html

| File | Source | Author | Licence |
|---|---|---|---|
| `buildhelp.png` | Font Awesome Free 6.5.2 `trowel-bricks` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `minimap.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `census.png` | Font Awesome Free 6.5.2 `tags` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `statuslabels.png` | Font Awesome Free 6.5.2 `bars-progress` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `soldierlevels.png` | Font Awesome Free 6.5.2 `medal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `buildings.png` | Font Awesome Free 6.5.2 `building` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `workareas.png` | Font Awesome Free 6.5.2 `bullseye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `statsgeneral.png` | Font Awesome Free 6.5.2 `chart-line` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `statswares.png` | Font Awesome Free 6.5.2 `chart-column` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `statsbuildings.png` | Font Awesome Free 6.5.2 `city` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `stock.png` | Font Awesome Free 6.5.2 `boxes-stacked` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `statssoldiers.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `seafaring.png` | Font Awesome Free 6.5.2 `ship` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `objectives.png` | Font Awesome Free 6.5.2 `list-check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `diplomacy.png` | game-icons.net `delapouite/shaking-hands` | delapouite | CC BY 3.0 |
| `messages.png` | Font Awesome Free 6.5.2 `envelope` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `encyclopedia.png` | Font Awesome Free 6.5.2 `book-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pinnednote.png` | Font Awesome Free 6.5.2 `thumbtack` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `starthq.png` | Font Awesome Free 6.5.2 `house-flag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicknav.png` | Font Awesome Free 6.5.2 `location-arrow` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `locationnext.png` | Font Awesome Free 6.5.2 `forward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `locationprev.png` | Font Awesome Free 6.5.2 `backward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomreset.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `exit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `restart.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `soundoptions.png` | Font Awesome Free 6.5.2 `volume-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `music.png` | Font Awesome Free 6.5.2 `music` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tooltipmode.png` | Font Awesome Free 6.5.2 `universal-access` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `speedup.png`, `speeddown.png`, `speedupslow.png`, `speeddownslow.png`, `speedupfast.png`, `speeddownfast.png` | Font Awesome Free 6.5.2 `forward` (solid) over the step in DejaVu Sans Bold, composed by `fetch_icons.py` | Fonticons, Inc. (icon); DejaVu fonts, Bitstream Vera licence (text) | CC BY 4.0 |
| `landmark1.png` to `landmark9.png`, `landmarkset1.png` to `landmarkset9.png` | Font Awesome Free 6.5.2 `location-dot` (solid) with the number in DejaVu Sans Bold cut out | Fonticons, Inc. (icon); DejaVu fonts, Bitstream Vera licence (digits) | CC BY 4.0 |
| `program.png` | Widelands logo `data/images/logos/wl-ico-128.png` (tag v1.3.1), reduced to 1 bit by `fetch_icons.py` | Widelands Development Team | GPL-2.0-or-later |
