# Unciv overlay: sources

`scripts/generate_app_overlays.py` renders `unciv.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `unciv_template` (1 file) | Unciv: the process `Unciv` (`Unciv.exe` on Windows), the Flatpak id `io.github.yairm210.unciv`, and a `java` or `javaw` process whose window title starts with "Unciv" |

How the names were found:

- `desktop/build.gradle.kts` packages the game with packr and
  `--executable Unciv`, so the Windows, Linux and macOS downloads start a
  program named `Unciv` (`Unciv.exe`).
- The Linux package script `desktop/linuxFilesForJar/Unciv.sh` runs
  `java -jar /usr/share/Unciv/Unciv.jar`, and a user can start the jar the same
  way on any system. The process is then `java` (or `javaw` on Windows), the
  name that JetBrains IDEs, Minecraft, Ghidra and DBeaver also have. Those
  entries in `overlay-mapping.poly.yaml` tell the programs apart by window
  title, so the Unciv set is a `titles-startswith` branch of the existing
  `java` and `javaw` entries.
- The window title is "Unciv": `config.setTitle("Unciv")` in
  `desktop/src/com/unciv/app/desktop/DesktopLauncher.kt`.
- `io.github.yairm210.unciv` is the Flathub id. It is not in the repository.

Names not checked on an install. On Linux with X11 the host can report the
window class instead of the process; libGDX sets it from the window title, so
it is expected to be "Unciv" too. That was not measured.

## Shortcut reference

The default key of each `KeyboardBinding` in
`core/src/com/unciv/ui/components/input/KeyboardBinding.kt` of
<https://github.com/yairm210/Unciv>, release tag `5.0.0` (commit
`63ec54738e13d4a97dcd32f4ccd1886824857346`), read 2026-11-14. A binding without
a key in the table uses the first letter of its name (`NextTurn` is N,
`EmpireOverview` is E), from the `init` block of the same file. A binding
marked `KeyCharAndCode.UNKNOWN` has no default key. A user changes the keys in
Options, Keys; this overlay shows the defaults.

`KeyCharAndCode.ctrl()` is the Control key on every system, so macOS uses the
same set.

World screen (category `WorldScreen`):

| Key | Binding |
|---|---|
| N, Space | Next turn (`NextTurn`, `NextTurnAlternate`) |
| Tab | Menu |
| E | Empire overview |
| comma, period | Previous and next idle unit (`PrevIdleButton`, `NextIdleButton`) |
| Home | View capital city |
| backquote | Developer console |
| F1 | Civilopedia |
| F2, F3, F4 | Empire overview: trades, units, politics |
| F5 | Social policies |
| F6 | Technology tree |
| F7 | Empire overview: notifications |
| F8 | Victory status |
| F9, F10 | Empire overview: stats, resources |
| F11, F12 | Quick save, quick load |
| Ctrl+A | Start AutoPlay |
| Ctrl+M | Music player |
| Ctrl+O | Options |
| Ctrl+S, Ctrl+L | Save game, load game |
| Ctrl+R | Toggle resource display |
| Ctrl+Y | Toggle yield display |
| Ctrl+Q | Quit game |
| Ctrl+N | New game |
| Ctrl+Z | Undo |
| Ctrl+U | Toggle UI |

Map panning (category `MapPanning`): W, A, S, D pan up, left, down, right.

Unit actions (category `UnitActions`). Several actions share a key, because a
unit has only some of them. The first one is drawn:

| Key | Drawn | Other actions on the key (not drawn) |
|---|---|---|
| C | Found city | Connect road |
| M | Automate | Stop automation, Stop movement |
| F | Fortify (label "Fortify or sleep") | Sleep |
| H | Fortify until healed | Sleep until healed, Remove heresy |
| X | Explore | Stop exploration |
| O | Promote | |
| U | Upgrade | |
| K | Transform | |
| P | Pillage | Paradrop |
| T | Set up | |
| I | Construct improvement | Create |
| R | Repair | |
| G | Great person action (one icon for all) | Hurry research, Hurry wonder, Hurry construction, Conduct trade mission, Found a religion, Enhance a religion, Spread religion, Trigger unique, Add in capital |
| Z | Skip turn | |
| J | Show unit destination | |
| Y | Swap units | |
| Delete | Disband unit | |
| Page Down, Page Up | Show more actions, back |

Other screens use the same keys with another meaning (not drawn): the city
screen (B buy, T buy tile, U, L, W, N, O construction lists, S, C, G, P, R, D
detail panels, Ctrl+F, P, G, S, C, D focus, Ctrl+R reset citizens, Ctrl+A avoid
growth), the Civilopedia (one letter per category), the main menu (N, L, E, D,
S, O), the AutoPlay menu (T, M, C, E), the next-turn menu (N, M) and popups
(Y confirm, N cancel, Ctrl+A upgrade all).

## Left out

- The semicolon (`Cycle`): the action it starts was not found in the files
  read, so no icon was chosen for it.
- A (`AirSweep`): A pans the map left, which is drawn.
- The arrow keys (pan the map): they keep their own legends. The keypad plus
  and minus (zoom): the keypad has no cell.
- Escape (`DeselectOrQuit`, `QuitMainMenu`): Esc has the program mark.
- Bindings without a default key: AutoPlay menu, Diplomacy, Espionage, the
  three other display toggles, Gift unit, Faith focus.
- The city screen, Civilopedia, main menu, AutoPlay menu, next-turn menu and
  popup keys.

## Placement

As for Freeciv (`../freeciv/SOURCES.md`): every icon sits at the right edge and
uses the full height, and the firmware clears 3 px around it, so a letter legend
stays whole. F1 to F3 and F8 are 34x40 and F4 to F7 30x40, the widths the AoE2
set measured to keep those legends whole. F9 to F12 are 40x40.

Icons shared with the Civilization IV set (`../civ4/`): Civilopedia, units
(crossed swords), social policies (civics), technology, victory, capital, next
turn, found city, fortify, heal, automate, explore, pillage, AutoPlay
(automate moves). With the Freeciv set: upgrade, statistics, yield display
(city output), politics (nations). F11 and F12 are the save and load icons with
a bolt, as in the VCMI set (`vcmi.bolt_icons()`).

N and Space show the same icon because they do the same thing.

## ESC mark

ESC shows "UNCIV" in Cinzel Bold (SIL OFL 1.1, `ofl/cinzel/Cinzel[wght].ttf`
from google/fonts at commit e7db6ca, weight 700), drawn over the whole cell
without the ESC legend (`program_icon_legend: false`, protocol v25).

The game's icon is not used. Unciv is under the Mozilla Public License 2.0
(`LICENSE`). MPL-2.0 is not in the list of licences this repository takes art
from, so the text mark is used instead.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Where each icon file comes from. The table below gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`, which
`fetch_icons.py` fetches through.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`

| File | Source | Author | Licence |
|---|---|---|---|
| `nextturn.png` | Font Awesome Free 6.5.2 `hourglass-end` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `menu.png` | Font Awesome Free 6.5.2 `bars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `empire.png` | Font Awesome Free 6.5.2 `city` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `idleprev.png` | Font Awesome Free 6.5.2 `backward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `idlenext.png` | Font Awesome Free 6.5.2 `forward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `capital.png` | Font Awesome Free 6.5.2 `star` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `panup.png` | Font Awesome Free 6.5.2 `arrow-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `panleft.png` | Font Awesome Free 6.5.2 `arrow-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pandown.png` | Font Awesome Free 6.5.2 `arrow-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `panright.png` | Font Awesome Free 6.5.2 `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `civilopedia.png` | Font Awesome Free 6.5.2 `book-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `trades.png` | Font Awesome Free 6.5.2 `handshake` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `units.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `politics.png` | Font Awesome Free 6.5.2 `flag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `policies.png` | Font Awesome Free 6.5.2 `landmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `technology.png` | Font Awesome Free 6.5.2 `flask` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `notifications.png` | Font Awesome Free 6.5.2 `bell` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `victory.png` | Font Awesome Free 6.5.2 `trophy` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `stats.png` | Font Awesome Free 6.5.2 `chart-column` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `resources.png` | Font Awesome Free 6.5.2 `cubes` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autoplay.png` | Font Awesome Free 6.5.2 `circle-play` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `music.png` | Font Awesome Free 6.5.2 `music` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `resourceicons.png` | Font Awesome Free 6.5.2 `gem` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `yieldicons.png` | Font Awesome Free 6.5.2 `wheat-awn` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `newgame.png` | Font Awesome Free 6.5.2 `file-circle-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `undo.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `toggleui.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `foundcity.png` | Font Awesome Free 6.5.2 `building-flag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `automate.png` | Font Awesome Free 6.5.2 `robot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fortify.png` | Font Awesome Free 6.5.2 `shield-halved` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `heal.png` | Font Awesome Free 6.5.2 `shield-heart` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `explore.png` | Font Awesome Free 6.5.2 `compass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `promote.png` | Font Awesome Free 6.5.2 `medal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `upgrade.png` | Font Awesome Free 6.5.2 `circle-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `transform.png` | Font Awesome Free 6.5.2 `shuffle` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pillage.png` | Font Awesome Free 6.5.2 `fire` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `setup.png` | game-icons.net `lorc/cannon` | lorc | CC BY 3.0 |
| `improve.png` | Font Awesome Free 6.5.2 `person-digging` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `repair.png` | Font Awesome Free 6.5.2 `screwdriver-wrench` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `greatperson.png` | Font Awesome Free 6.5.2 `user-graduate` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `disband.png` | Font Awesome Free 6.5.2 `trash-can` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `skip.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `destination.png` | Font Awesome Free 6.5.2 `location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `swapunits.png` | Font Awesome Free 6.5.2 `right-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `moreactions.png` | Font Awesome Free 6.5.2 `ellipsis` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lessactions.png` | Font Awesome Free 6.5.2 `reply` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quickload.png` | Font Awesome Free 6.5.2 `folder-open` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "UNCIV" set in Cinzel Bold by `fetch_icons.py` | The Cinzel Project Authors (font) | SIL OFL 1.1 |
