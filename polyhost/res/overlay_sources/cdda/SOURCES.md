# Cataclysm: Dark Days Ahead overlay: sources

`scripts/generate_app_overlays.py` renders `cdda.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `cdda_template` (1 file) | Cataclysm: Dark Days Ahead. Tiles build: `cataclysm-tiles` on Linux, `cataclysm-tiles.exe` on Windows, `org.cataclysmdda.CataclysmDDA` as a Flatpak, "Cataclysm" on macOS. Curses build: a terminal whose title has `cataclysm` at the command position |

`cataclysm` is `TARGET_NAME` in the `Makefile` and `cataclysm-tiles` is
`TILES_TARGET_NAME` (with `.exe` for a Windows target). `cataclysm-tiles` is
also the `Exec=` line of `data/xdg/org.cataclysmdda.CataclysmDDA.desktop`, and
the Flatpak id is the `<id>` of the `.appdata.xml` beside it. The macOS bundle
is `Cataclysm.app` (`APPTARGETDIR` in the `Makefile`, `CFBundleName` in
`build-data/osx/Info.plist`). Names not checked on an install.

The curses build runs in a terminal and writes no window title (`set_title()`
in `src/ncurses_def.cpp` is empty), so the host sees it only when the shell or
the terminal puts the running command into the title
(`polyhost/res/overlay-mapping.md`, "An editor seen only in the window title").
The `cataclysm` route in `&editor_titles` of the mapping file requires
`cataclysm` at the command position, as the `htop` route does. The launcher
script `cataclysm-launcher` is a different word and is not matched.

## Shortcut reference

The default bindings in `data/raw/keybindings.json` of
<https://github.com/CleverRaven/Cataclysm-DDA>, stable tag
`cdda-0.I-2026-09-19-2324` (commit `7b2efa5cea38e4d4d97dd0e63b28b9148623da59`),
read 2026-11-14. Every entry of the `DEFAULTMODE` category (the main game
screen, 121 entries) and of the category without a name (the keys every screen
shares, 86 entries) was read. The game's keybindings menu changes the keys;
this overlay shows the defaults.

The game tells a lower-case from an upper-case letter, so the plain and the
Shift layer are drawn. No `DEFAULTMODE` entry has a Ctrl or Alt binding. For a
symbol the file gives both the character and the US-layout chord (`&` and
Shift+7), so the Shift layer follows the US layout. "Game key" is the
character in the file.

| Key | Game key | Action | Icon |
|---|---|---|---|
| H | `h` | Move west | `move_w.png` |
| J | `j` | Move south | `move_s.png` |
| K | `k` | Move north | `move_n.png` |
| L | `l` | Move east | `move_e.png` |
| Y | `y` | Move north-west | `move_nw.png` |
| U | `u` | Move north-east | `move_ne.png` |
| B | `b` | Move south-west | `move_sw.png` |
| N | `n` | Move south-east | `move_se.png` |
| 1 | `1` | Move south-west | `move_sw.png` |
| 2 | `2` | Move south | `move_s.png` |
| 3 | `3` | Move south-east | `move_se.png` |
| 4 | `4` | Move west | `move_w.png` |
| 6 | `6` | Move east | `move_e.png` |
| 7 | `7` | Move north-west | `move_nw.png` |
| 8 | `8` | Move north | `move_n.png` |
| 9 | `9` | Move north-east | `move_ne.png` |
| 5 | `5` | Wait one turn | `pause.png` |
| . | `.` | Wait one turn | `pause.png` |
| Tab | `Tab` | Attack the nearest enemy | `autoattack.png` |
| O | `o` | Open a door | `opendoor.png` |
| C | `c` | Close a door | `closedoor.png` |
| S | `s` | Smash nearby terrain | `smash.png` |
| E | `e` | Examine nearby terrain or furniture | `examine.png` |
| G | `g` | Pick up items | `pickup.png` |
| X | `x` | Look around | `look.png` |
| ; | `;` | Look around | `look.png` |
| \ | `\` | Haul items along the ground | `haul.png` |
| ' | `'` | Ignore the nearby enemy | `ignoreenemy.png` |
| M | `m` | View the map | `map.png` |
| I | `i` | Open the inventory | `inventory.png` |
| / | `/` | Advanced inventory manager | `advinv.png` |
| = | `=` | Swap inventory letters | `organize.png` |
| A | `a` | Use an item | `apply.png` |
| W | `w` | Wield an item | `wield.png` |
| V | `v` | Insert an item into a container | `insert.png` |
| T | `t` | Throw an item | `throw.png` |
| F | `f` | Fire the wielded item | `fire.png` |
| R | `r` | Reload an item | `reload.png` |
| D | `d` | Drop an item | `drop.png` |
| F3 | `F3` | Select the default ammunition | `defaultammo.png` |
| - | `-` | Craft the last recipe again | `recraft.png` |
| P | `p` | View or activate bionics | `bionics.png` |
| [ | `[` | View or activate mutations | `mutations.png` |
| ] | `]` | Supernatural abilities | `spells.png` |
| Enter | `Enter` | Action menu | `actionmenu.png` |
| 0 | `0` | View the help | `help.png` |
| Z | `z` | Zoom in | `zoomin.png` |
| Shift+G | `G` | Grab something nearby | `grab.png` |
| Shift+O | `O` | Zone activities | `zoneactivity.png` |
| Shift+B | `B` | Butcher | `butcher.png` |
| Shift+C | `C` | Talk to a character | `chat.png` |
| Shift+X | `X` | Peek around a corner | `peek.png` |
| Shift+V | `V` | List the items and monsters around | `listitems.png` |
| Shift+Y | `Y` | Zones manager | `zones.png` |
| Shift+I | `I` | Compare two items | `compare.png` |
| Shift+A | `A` | Use the wielded item | `applywielded.png` |
| Shift+W | `W` | Wear an item | `wear.png` |
| Shift+T | `T` | Take off a worn item | `takeoff.png` |
| Shift+E | `E` | Eat, drink or take a medicine | `eat.png` |
| Shift+R | `R` | Read a book | `read.png` |
| Shift+U | `U` | Unload an item | `unload.png` |
| Shift+F | `F` | Change the attack mode of the wielded item | `firemode.png` |
| Shift+D | `D` | Drop an item on an adjacent tile | `dropadjacent.png` |
| Shift+N | `N` | View the medical screen | `medical.png` |
| Shift+S | `S` | Save the game and quit | `save.png` |
| Shift+M | `M` | View missions | `missions.png` |
| Shift+P | `P` | View the message log | `messages.png` |
| Shift+Z | `Z` | Zoom out | `zoomout.png` |
| Shift+1 | `!` | Toggle safe mode | `safemode.png` |
| Shift+2 | `@` | View the player information | `playerinfo.png` |
| Shift+3 | `#` | View factions | `factions.png` |
| Shift+4 | `$` | Sleep | `sleep.png` |
| Shift+5 | `%` | Item action menu | `itemactions.png` |
| Shift+6 | `^` | Control a vehicle | `vehicle.png` |
| Shift+7 | `&` | Craft items | `craft.png` |
| Shift+8 | `*` | Construct terrain | `construct.png` |
| Shift+9 | `(` | Disassemble items | `disassemble.png` |
| Shift+0 | `)` | Diary, achievements and scores | `diary.png` |
| Shift+- | `_` | Select a martial arts style | `martialarts.png` |
| Shift+= | `+` | Sort the worn armor | `sortarmor.png` |
| Shift+[ | `{` | View the body status | `bodystatus.png` |
| Shift+\ | <code>&#124;</code> | Wait for a chosen time | `wait.png` |
| Shift+' | `"` | Movement mode menu | `movemode.png` |
| Shift+` | `~` | Add the enemy to the safe mode whitelist | `whitelist.png` |
| Shift+, | `<` | Go up | `upstairs.png` |
| Shift+. | `>` | Go down | `downstairs.png` |
| Shift+/ | `?` | Keybindings menu | `keybindings.png` |

The same icon on two keys means the same command: `x` and `;` look around, `.`
and `5` wait, a vi key and a digit move in the same direction.

Other meanings of drawn keys (not drawn). The main screen's meaning is drawn;
the menus and the other screens use the same letters for their own commands:

| Key | Main screen (drawn) | Other screens |
|---|---|---|
| `h` `j` `k` `l` `y` `u` `b` `n` and the digits | Move | every list and map: move the cursor or pan |
| `0` | View the help | map screens: centre on the character |
| `g` | Pick up | overmap: go to the destination |
| `c` | Close a door | overmap: centre on the destination |
| `f`, `r`, `/` | Fire, reload, advanced inventory | lists: filter, reset the filter, search |
| `e` | Examine | lists: extended description |
| `;` | Look around | inventory: category mode |
| `W`, `T` | Wear, take off | overmap: choose the destination, travel |
| `S` | Save and quit | character creation: trait variant |
| `@`, `$`, `*` | Player information, sleep, construct | character creation: gender, outfit, profession name |
| `<`, `>` | Go up, go down | lists: scroll the description |
| Tab | Attack the nearest enemy | menus: next tab |

## Left out

- The arrow keys, Page Up and Page Down (move, go up, go down): they keep
  their own legends. Home and End are bound only in lists.
- The keypad (move, wait, help, the craft and inventory keys): the keypad has
  no cell.
- Shift+H, J, K, L ("wide move"): used only by the map editor and list
  screens.
- `q` and Space: they close a menu; on the main screen they do nothing.
- F5 (toggle navigation with the keypad digits) and F2 (text input from a
  file): act only in a menu or a text field.
- Ctrl+C, D, T, Y, R (debug toggles of the dialogue window) and Ctrl+U, Ctrl+V
  (text input).
- The `DEFAULTMODE` commands with no default key (quick save, toggle run,
  pick up all, and about 60 more): nothing to draw.
- The inventory, advanced inventory, overmap, crafting, vehicle and targeting
  categories: their keys depend on the screen.

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge
and uses the full height, and the firmware clears 3 px around it, so a letter
legend stays whole. On a digit or symbol key the shifted symbol of the legend
is erased. F3 is 34×40.

All icons are flat 1-bit silhouettes drawn at their key area, so the generator
places them 1:1. A command that is another command with a change has that
command's icon at 31×31 with a small glyph in the top-left corner: a plus or
minus (wear and take off, unload), a turning arrow (reload, craft again), a
bolt (attack the nearest enemy without choosing a target). The movement arrows
are drawn by the helpers in `../dcss/fetch_icons.py`.

## ESC mark

ESC shows "Cataclysm" over "DDA" in Creepster (SIL OFL 1.1,
`ofl/creepster/Creepster-Regular.ttf` from google/fonts at commit e7db6ca),
both lines at the largest one size at which each fits 70 px wide and both, 2 px
apart, fit 38 px high, drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25). A pixel is lit from grey 100 of
255.

The game's own art is not used. `LICENSE.txt` puts the game under CC BY-SA 3.0
Unported, which is not compatible with this repository's GPL-3.0-or-later, and
that covers the application icon in `data/xdg/` and `build-data/`.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Where each icon file comes from. The icon table gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`

Material Design Icons are from <https://pictogrammers.com/library/mdi/>
(Templarian/MaterialDesign at commit 2424e74).

| File | Source | Author | Licence |
|---|---|---|---|
| `pause.png` | Font Awesome Free 6.5.2 `hourglass-half` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `opendoor.png` | Font Awesome Free 6.5.2 `door-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closedoor.png` | Font Awesome Free 6.5.2 `door-closed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `smash.png` | Font Awesome Free 6.5.2 `hammer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `examine.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `advinv.png` | Font Awesome Free 6.5.2 `boxes-stacked` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pickup.png` | Material Design Icons `tray-arrow-up` | Pictogrammers | Apache-2.0 |
| `haul.png` | Font Awesome Free 6.5.2 `dolly` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `look.png` | Font Awesome Free 6.5.2 `eye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `inventory.png` | Material Design Icons `bag-personal` | Pictogrammers | Apache-2.0 |
| `organize.png` | Font Awesome Free 6.5.2 `arrow-down-a-z` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `apply.png` | Font Awesome Free 6.5.2 `hand-pointer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `wield.png` | Material Design Icons `knife-military` | Pictogrammers | Apache-2.0 |
| `insert.png` | Font Awesome Free 6.5.2 `arrow-right-to-bracket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `throw.png` | game-icons.net `lorc/thrown-daggers` | lorc | CC BY 3.0 |
| `fire.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `defaultammo.png` | Material Design Icons `ammunition` | Pictogrammers | Apache-2.0 |
| `drop.png` | Material Design Icons `tray-arrow-down` | Pictogrammers | Apache-2.0 |
| `bionics.png` | Font Awesome Free 6.5.2 `microchip` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mutations.png` | Font Awesome Free 6.5.2 `dna` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `recraft.png` | Font Awesome Free 6.5.2 `screwdriver-wrench` (solid) with Font Awesome `rotate-right` in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `ignoreenemy.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `map.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reload.png` | Material Design Icons `ammunition` with Font Awesome `rotate-right` in the corner, composed by `fetch_icons.py` | Pictogrammers; Fonticons, Inc. | Apache-2.0; CC BY 4.0 |
| `actionmenu.png` | Font Awesome Free 6.5.2 `bars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autoattack.png` | Material Design Icons `sword-cross` with Font Awesome `bolt` in the corner, composed by `fetch_icons.py` | Pictogrammers; Fonticons, Inc. | Apache-2.0; CC BY 4.0 |
| `spells.png` | Font Awesome Free 6.5.2 `wand-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `grab.png` | Font Awesome Free 6.5.2 `hand-back-fist` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoneactivity.png` | Font Awesome Free 6.5.2 `person-digging` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `butcher.png` | game-icons.net `lorc/meat-cleaver` | lorc | CC BY 3.0 |
| `chat.png` | Font Awesome Free 6.5.2 `comments` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `peek.png` | Font Awesome Free 6.5.2 `user-secret` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `listitems.png` | Font Awesome Free 6.5.2 `list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zones.png` | Font Awesome Free 6.5.2 `vector-square` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `compare.png` | Font Awesome Free 6.5.2 `scale-balanced` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `applywielded.png` | Font Awesome Free 6.5.2 `hand-fist` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `wear.png` | Font Awesome Free 6.5.2 `shirt` (solid) with a plus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `takeoff.png` | Font Awesome Free 6.5.2 `shirt` (solid) with a minus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `eat.png` | Font Awesome Free 6.5.2 `utensils` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `read.png` | Font Awesome Free 6.5.2 `book-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `martialarts.png` | Material Design Icons `karate` | Pictogrammers | Apache-2.0 |
| `unload.png` | Material Design Icons `ammunition` with a minus in the corner, composed by `fetch_icons.py` | Pictogrammers | Apache-2.0 |
| `firemode.png` | Font Awesome Free 6.5.2 `sliders` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `dropadjacent.png` | Material Design Icons `subdirectory-arrow-right` | Pictogrammers | Apache-2.0 |
| `medical.png` | Font Awesome Free 6.5.2 `kit-medical` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `bodystatus.png` | Font Awesome Free 6.5.2 `heart-pulse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sortarmor.png` | Font Awesome Free 6.5.2 `layer-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `wait.png` | Font Awesome Free 6.5.2 `clock` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `craft.png` | Font Awesome Free 6.5.2 `screwdriver-wrench` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `construct.png` | Font Awesome Free 6.5.2 `trowel-bricks` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `disassemble.png` | Material Design Icons `puzzle-remove` | Pictogrammers | Apache-2.0 |
| `sleep.png` | Font Awesome Free 6.5.2 `bed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `vehicle.png` | Material Design Icons `steering` | Pictogrammers | Apache-2.0 |
| `safemode.png` | Font Awesome Free 6.5.2 `triangle-exclamation` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `whitelist.png` | Font Awesome Free 6.5.2 `user-check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `playerinfo.png` | Font Awesome Free 6.5.2 `id-card` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `missions.png` | Font Awesome Free 6.5.2 `flag-checkered` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `factions.png` | Font Awesome Free 6.5.2 `people-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `messages.png` | Font Awesome Free 6.5.2 `message` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `itemactions.png` | Font Awesome Free 6.5.2 `rectangle-list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `movemode.png` | Font Awesome Free 6.5.2 `person-walking` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `diary.png` | Font Awesome Free 6.5.2 `trophy` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `keybindings.png` | Font Awesome Free 6.5.2 `keyboard` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `upstairs.png` | Material Design Icons `stairs-up` | Pictogrammers | Apache-2.0 |
| `downstairs.png` | Material Design Icons `stairs-down` | Pictogrammers | Apache-2.0 |
| `move_<direction>.png` (8) | an arrow, drawn by `fetch_icons.py` | this repository | GPL-3.0-or-later |
| `program.png` | "Cataclysm" over "DDA" set in Creepster by `fetch_icons.py` | Font Diner, Inc (font) | SIL OFL 1.1 |
