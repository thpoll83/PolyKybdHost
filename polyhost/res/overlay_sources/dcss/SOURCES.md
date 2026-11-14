# Dungeon Crawl Stone Soup overlay: sources

`scripts/generate_app_overlays.py` renders `dcss.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `dcss_template` (1 file) | Dungeon Crawl Stone Soup. Tiles build: `crawl` or `crawl-tiles` on Linux, `crawl.exe` or `crawl-tiles.exe` on Windows, "Dungeon Crawl Stone Soup - Tiles" on macOS. Console build: a terminal whose title has `crawl` or `crawl-console` at the command position |

`crawl` is `GAME` in `crawl-ref/source/Makefile` (`crawl.exe` for a Windows
target). The Windows packaging rules in the same Makefile rename the two builds
to `crawl-tiles.exe` and `crawl-console.exe`, and Debian installs the tiles
build as `crawl-tiles`. The macOS bundle name is `BUNDLE_NAME` in
`crawl-ref/source/mac/Makefile.app-bundle`. The tiles window title is
"Dungeon Crawl Stone Soup <version>" (`SDLWrapper::init()` in
`windowmanager-sdl.cc`); the routing does not use it. Names not checked on an
install.

The console build runs in a terminal and writes no window title, so the host
sees it only when the shell or the terminal puts the running command into the
title (`polyhost/res/overlay-mapping.md`, "An editor seen only in the window
title"). The `crawl` route in `&editor_titles` of the mapping file requires
`crawl` or `crawl-console` at the command position, as the `htop` route does.
A console build started by a double click on Windows has the full path of the
executable as its title and is not recognised. A game on a public server over
SSH (`ssh crawl.example.org`) is not recognised either. The WebTiles client in
a browser has no route.

## Shortcut reference

The default key table in `crawl-ref/source/cmd-keys.h` of
<https://github.com/crawl/crawl>, release tag `0.34.1` (commit
`1eebc1a2892e1c89776a0d7a10691f8dac8d9796`), read 2026-11-14. The first section
of the table (down to the `CMD_TARGET_` entries) is the main view; all of it
was read. A user's `bindkey` lines in the options file change the keys; this
overlay shows the defaults.

The game reads characters, so a lower-case letter, an upper-case letter and
Ctrl+letter are three commands. The overlay draws them on the plain, Shift and
Ctrl layers. The symbol commands on the Shift layer (`@` on Shift+2, `<` on
Shift+,) follow the US layout; on another layout the symbol is on another key.
"Game key" is the character in `cmd-keys.h`.

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
| Home | `Home` | Move north-west | `move_nw.png` |
| Page Up | `Page Up` | Move north-east | `move_ne.png` |
| End | `End` | Move south-west | `move_sw.png` |
| Page Down | `Page Down` | Move south-east | `move_se.png` |
| S | `s` | Wait one turn | `wait.png` |
| . | `.` | Wait one turn | `wait.png` |
| Delete | `Delete` | Wait one turn | `wait.png` |
| 5 | `5` | Rest and search | `rest.png` |
| O | `o` | Auto-explore | `explore.png` |
| Tab | `Tab` | Fight the nearest monster | `autofight.png` |
| A | `a` | Use an ability | `ability.png` |
| C | `c` | Unequip an item | `unequip.png` |
| D | `d` | Drop an item | `drop.png` |
| E | `e` | Equip an item | `equip.png` |
| F | `f` | Fire the quivered action | `fire.png` |
| G | `g` | Pick up items | `pickup.png` |
| , | `,` | Pick up items | `pickup.png` |
| I | `i` | Show the inventory | `inventory.png` |
| M | `m` | Show skills | `skills.png` |
| P | `p` | Fire at the nearest monster | `autofire.png` |
| Q | `q` | Quaff a potion | `quaff.png` |
| R | `r` | Read a scroll | `read.png` |
| T | `t` | Shout or command allies | `shout.png` |
| V | `v` | Attack with the primary weapon | `attack.png` |
| W | `w` | Wield a weapon | `wield.png` |
| X | `x` | Look around | `look.png` |
| Z | `z` | Cast a spell | `cast.png` |
| 0 | `0` | Repeat a command several times | `repeat.png` |
| Insert | `Insert` | Repeat a command several times | `repeat.png` |
| ` | ``` | Do the previous command again | `again.png` |
| ; | `;` | Examine the items here | `inspectfloor.png` |
| = | `=` | Reassign inventory or spell letters | `adjust.png` |
| ' | `'` | Swap between weapons a and b | `weaponswap.png` |
| [ | `[` | List worn armour | `listarmour.png` |
| ] | `]` | Swap to the previous quiver action | `swapquiver.png` |
| \ | `\` | List known items | `known.png` |
| F1 | `F1` | Game menu | `gamemenu.png` |
| Shift+H | `H` | Run west | `run_w.png` |
| Shift+J | `J` | Run south | `run_s.png` |
| Shift+K | `K` | Run north | `run_n.png` |
| Shift+L | `L` | Run east | `run_e.png` |
| Shift+Y | `Y` | Run north-west | `run_nw.png` |
| Shift+U | `U` | Run north-east | `run_ne.png` |
| Shift+B | `B` | Run south-west | `run_sw.png` |
| Shift+N | `N` | Run south-east | `run_se.png` |
| Shift+A | `A` | Show mutations | `mutations.png` |
| Shift+C | `C` | Close a door | `closedoor.png` |
| Shift+D | `D` | Drop the items picked up last | `droplast.png` |
| Shift+E | `E` | Show experience | `experience.png` |
| Shift+F | `F` | Fire or throw an inventory item | `throw.png` |
| Shift+G | `G` | Travel to another level | `travel.png` |
| Shift+I | `I` | List memorised spells | `spells.png` |
| Shift+M | `M` | Memorise a spell | `memorise.png` |
| Shift+O | `O` | Open a door | `opendoor.png` |
| Shift+P | `P` | Put on jewellery | `puton.png` |
| Shift+Q | `Q` | Choose the quiver action | `quiver.png` |
| Shift+R | `R` | Remove jewellery | `remove.png` |
| Shift+S | `S` | Save the game and exit | `save.png` |
| Shift+T | `T` | Take off armour | `takeoff.png` |
| Shift+V | `V` | Evoke an item | `evoke.png` |
| Shift+W | `W` | Wear armour | `wear.png` |
| Shift+X | `X` | Show the level map | `map.png` |
| Shift+Z | `Z` | Cast a spell without a target check | `forcecast.png` |
| Shift+Tab | `Shift+Tab` | Fire at the nearest monster | `autofire.png` |
| Shift+, | `<` | Go up the stairs | `upstairs.png` |
| Shift+. | `>` | Go down the stairs | `downstairs.png` |
| Shift+1 | `!` | Annotate the level | `annotate.png` |
| Shift+2 | `@` | Show the character status | `status.png` |
| Shift+3 | `#` | Write the character to a file | `dump.png` |
| Shift+4 | `$` | Show the gold | `gold.png` |
| Shift+5 | `%` | Show resistances | `resists.png` |
| Shift+6 | `^` | Show the religion screen | `religion.png` |
| Shift+9 | `(` | Previous quiver action | `quiverprev.png` |
| Shift+0 | `)` | Next quiver action | `quivernext.png` |
| Shift+; | `:` | Add a note to the character file | `note.png` |
| Shift+' | `"` | List worn jewellery | `jewellery.png` |
| Shift+[ | `{` | Inscribe an item | `inscribe.png` |
| Shift+] | `}` | List collected runes | `runes.png` |
| Shift+\ | <code>&#124;</code> | Show only the terrain | `terrain.png` |
| Shift+/ | `?` | List of commands | `help.png` |
| Shift+` | `~` | Game menu | `gamemenu.png` |
| Ctrl+H | `^H` | Attack west without moving | `attack_w.png` |
| Ctrl+J | `^J` | Attack south without moving | `attack_s.png` |
| Ctrl+K | `^K` | Attack north without moving | `attack_n.png` |
| Ctrl+L | `^L` | Attack east without moving | `attack_e.png` |
| Ctrl+Y | `^Y` | Attack north-west without moving | `attack_nw.png` |
| Ctrl+U | `^U` | Attack north-east without moving | `attack_ne.png` |
| Ctrl+B | `^B` | Attack south-west without moving | `attack_sw.png` |
| Ctrl+N | `^N` | Attack south-east without moving | `attack_se.png` |
| Ctrl+A | `^A` | Toggle automatic pickup | `autopickup.png` |
| Ctrl+C | `^C` | Clear the level map | `clearmap.png` |
| Ctrl+D | `^D` | Macro menu | `macromenu.png` |
| Ctrl+E | `^E` | Add a macro | `macroadd.png` |
| Ctrl+F | `^F` | Search the known items | `stashes.png` |
| Ctrl+G | `^G` | Travel to another level | `travel.png` |
| Ctrl+O | `^O` | Dungeon overview | `overview.png` |
| Ctrl+P | `^P` | Show earlier messages | `messages.png` |
| Ctrl+Q | `^Q` | Quit without saving | `quit.png` |
| Ctrl+R | `^R` | Redraw the screen | `redraw.png` |
| Ctrl+S | `^S` | Save and exit without a prompt | `savenow.png` |
| Ctrl+W | `^W` | Set a travel waypoint | `waypoint.png` |
| Ctrl+X | `^X` | List everything in view | `fullview.png` |
| Ctrl+Z | `^Z` | Suspend the game | `suspend.png` |

The same icon on two keys means the same command: `s`, `.` and Delete all
wait, `g` and `,` pick up, `0` and Insert repeat, `G` and Ctrl+G travel, `p`
and Shift+Tab fire at the nearest monster, F1 and `~` open the game menu.

Other meanings of drawn keys (not drawn):

| Key | Main view (drawn) | Other screens |
|---|---|---|
| `x` | Look around | targeting: cancel |
| `v` | Attack with the primary weapon | targeting: describe |
| `.` and `5` | Wait, rest | targeting: select |
| `?` | List of commands | targeting and menus: help for that screen |
| Ctrl+X | List everything in view | targeting: full description |
| Ctrl+C | Clear the level map | targeting: cycle the beam path |
| `:` `!` `@` | Note, annotate, status | targeting: beam and forced-target toggles |
| letters | commands | menus: select the item with that letter |

## Left out

- The arrow keys (move), Shift+arrows (run) and Ctrl+arrows (attack): the
  arrows keep their own legends. Shift and Ctrl with Home, End, Page Up and
  Page Down (run and attack diagonally) are left out with them.
- The keypad (move, `5` rest): the keypad has no cell.
- `-` (edit the player tile): only in the tiles build. `_` (read messages):
  only in the console and WebTiles builds. Ctrl+`=` and Ctrl+`-` (zoom): only
  in the local tiles build.
- `&` (wizard mode) and `+` (explore mode): only in builds with `WIZARD`.
- Ctrl+I: the same character as Tab, drawn on Tab.
- F11 and F12: Android only.
- `1` to `4` and `6` to `9`: not bound in the main view.
- The targeting, level-map, menu and doll-editor sections of the table: their
  keys depend on the screen.

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge
and uses the full height, and the firmware clears 3 px around it, so a letter
legend stays whole. On a digit or symbol key the shifted symbol of the legend
is erased. F1 is 34×40.

All icons are flat 1-bit silhouettes drawn at their key area, so the generator
places them 1:1. A command that is another command with a change has that
command's icon at 31×31 with a small glyph in the top-left corner: a plus or
minus (put on and remove, wear and take off, equip and unequip, add a macro),
a bolt for "without asking" (fight or fire at the nearest monster, cast without
a target check, save without a prompt), two arrows for a swap, a turning arrow
for "the last ones", a triangle for previous and next.

The direction keys are drawn by `fetch_icons.py`: an arrow to move (plain), a
double chevron to run (Shift), and a sword that points in the direction to
attack without moving (Ctrl).

## ESC mark

ESC shows the game's own icon, the cauldron:
`crawl-ref/source/dat/tiles/stone_soup_icon-32x32.png` at tag `0.34.1`, 32×32,
placed 1:1. It is reduced to 1 bit as its black outline (luma below 60) and its
bright parts (luma from 130: the soup, the flames and the ladle); the grey body
of the pot stays dark.

Licence: the repository's `LICENSE` says "either version 2 of the License, or
(at your option) any later version" for the game, and "The majority of Crawl's
tiles and artwork are released under the CC0 license". The icon file has no
licence note of its own in the repository, so it is under one of the two; both
are compatible with this repository's GPL-3.0-or-later. The per-file record at
<https://github.com/crawl/tiles> was not read.

## Icons

Licence texts for the icon licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- GPL-2.0-or-later (the game): https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
- CC0 1.0: https://creativecommons.org/publicdomain/zero/1.0/

Material Design Icons are from <https://pictogrammers.com/library/mdi/>
(Templarian/MaterialDesign at commit 2424e74).

| File | Source | Author | Licence |
|---|---|---|---|
| `wait.png` | Font Awesome Free 6.5.2 `hourglass-half` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rest.png` | Font Awesome Free 6.5.2 `bed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ability.png` | Font Awesome Free 6.5.2 `hand-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `equip.png` | Material Design Icons `shield-sword` with a plus in the corner, composed by `fetch_icons.py` | Pictogrammers | Apache-2.0 |
| `unequip.png` | Material Design Icons `shield-sword` with a minus in the corner, composed by `fetch_icons.py` | Pictogrammers | Apache-2.0 |
| `drop.png` | Material Design Icons `tray-arrow-down` | Pictogrammers | Apache-2.0 |
| `fire.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pickup.png` | Material Design Icons `tray-arrow-up` | Pictogrammers | Apache-2.0 |
| `inventory.png` | Material Design Icons `bag-personal` | Pictogrammers | Apache-2.0 |
| `skills.png` | Font Awesome Free 6.5.2 `chart-simple` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autofire.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) with Font Awesome `bolt` in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `explore.png` | Font Awesome Free 6.5.2 `compass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quaff.png` | Font Awesome Free 6.5.2 `flask` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `read.png` | Font Awesome Free 6.5.2 `scroll` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `shout.png` | Font Awesome Free 6.5.2 `bullhorn` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `attack.png` | Material Design Icons `sword-cross` | Pictogrammers | Apache-2.0 |
| `wield.png` | Material Design Icons `sword` | Pictogrammers | Apache-2.0 |
| `look.png` | Font Awesome Free 6.5.2 `eye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cast.png` | Font Awesome Free 6.5.2 `wand-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `repeat.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `again.png` | Font Awesome Free 6.5.2 `repeat` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `inspectfloor.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `adjust.png` | Font Awesome Free 6.5.2 `arrow-down-a-z` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `weaponswap.png` | Material Design Icons `sword` with Font Awesome `right-left` in the corner, composed by `fetch_icons.py` | Pictogrammers; Fonticons, Inc. | Apache-2.0; CC BY 4.0 |
| `listarmour.png` | Font Awesome Free 6.5.2 `shirt` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `swapquiver.png` | Material Design Icons `bow-arrow` with Font Awesome `right-left` in the corner, composed by `fetch_icons.py` | Pictogrammers; Fonticons, Inc. | Apache-2.0; CC BY 4.0 |
| `known.png` | Font Awesome Free 6.5.2 `clipboard-list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gamemenu.png` | Font Awesome Free 6.5.2 `bars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autofight.png` | Material Design Icons `sword-cross` with Font Awesome `bolt` in the corner, composed by `fetch_icons.py` | Pictogrammers; Fonticons, Inc. | Apache-2.0; CC BY 4.0 |
| `mutations.png` | Font Awesome Free 6.5.2 `dna` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closedoor.png` | Font Awesome Free 6.5.2 `door-closed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `droplast.png` | Material Design Icons `tray-arrow-down` with Font Awesome `rotate-right` in the corner, composed by `fetch_icons.py` | Pictogrammers; Fonticons, Inc. | Apache-2.0; CC BY 4.0 |
| `experience.png` | Font Awesome Free 6.5.2 `ranking-star` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `throw.png` | game-icons.net `lorc/thrown-daggers` | lorc | CC BY 3.0 |
| `travel.png` | Font Awesome Free 6.5.2 `route` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `spells.png` | Font Awesome Free 6.5.2 `book` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `memorise.png` | Font Awesome Free 6.5.2 `brain` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `opendoor.png` | Font Awesome Free 6.5.2 `door-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `puton.png` | Font Awesome Free 6.5.2 `ring` (solid) with a plus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quiver.png` | Material Design Icons `bow-arrow` | Pictogrammers | Apache-2.0 |
| `remove.png` | Font Awesome Free 6.5.2 `ring` (solid) with a minus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `takeoff.png` | Font Awesome Free 6.5.2 `shirt` (solid) with a minus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `evoke.png` | game-icons.net `lorc/crystal-wand` | lorc | CC BY 3.0 |
| `wear.png` | Font Awesome Free 6.5.2 `shirt` (solid) with a plus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `map.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `forcecast.png` | Font Awesome Free 6.5.2 `wand-sparkles` (solid) with Font Awesome `bolt` in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `upstairs.png` | Material Design Icons `stairs-up` | Pictogrammers | Apache-2.0 |
| `downstairs.png` | Material Design Icons `stairs-down` | Pictogrammers | Apache-2.0 |
| `status.png` | Font Awesome Free 6.5.2 `heart-pulse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `resists.png` | Font Awesome Free 6.5.2 `shield-halved` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `note.png` | Font Awesome Free 6.5.2 `pen-to-square` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `terrain.png` | Font Awesome Free 6.5.2 `mountain` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `religion.png` | Font Awesome Free 6.5.2 `place-of-worship` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `dump.png` | Font Awesome Free 6.5.2 `file-export` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `annotate.png` | Font Awesome Free 6.5.2 `thumbtack` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gold.png` | Font Awesome Free 6.5.2 `coins` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jewellery.png` | Material Design Icons `necklace` | Pictogrammers | Apache-2.0 |
| `inscribe.png` | Font Awesome Free 6.5.2 `pen-nib` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quiverprev.png` | Material Design Icons `bow-arrow` with a left triangle in the corner, composed by `fetch_icons.py` | Pictogrammers | Apache-2.0 |
| `quivernext.png` | Material Design Icons `bow-arrow` with a right triangle in the corner, composed by `fetch_icons.py` | Pictogrammers | Apache-2.0 |
| `runes.png` | Font Awesome Free 6.5.2 `gem` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autopickup.png` | Font Awesome Free 6.5.2 `magnet` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clearmap.png` | Font Awesome Free 6.5.2 `eraser` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `macromenu.png` | Font Awesome Free 6.5.2 `keyboard` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `macroadd.png` | Font Awesome Free 6.5.2 `keyboard` (solid) with a plus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `stashes.png` | Material Design Icons `archive-search` | Pictogrammers | Apache-2.0 |
| `overview.png` | Font Awesome Free 6.5.2 `sitemap` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `messages.png` | Font Awesome Free 6.5.2 `message` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `redraw.png` | Font Awesome Free 6.5.2 `arrows-rotate` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `savenow.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) with Font Awesome `bolt` in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `waypoint.png` | Font Awesome Free 6.5.2 `location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullview.png` | Font Awesome Free 6.5.2 `binoculars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `suspend.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `move_<direction>.png` (8) | an arrow, drawn by `fetch_icons.py` | this repository | GPL-3.0-or-later |
| `run_<direction>.png` (8) | a double chevron, drawn by `fetch_icons.py` | this repository | GPL-3.0-or-later |
| `attack_<direction>.png` (8) | Material Design Icons `sword`, turned to point in the direction by `fetch_icons.py` | Pictogrammers | Apache-2.0 |
| `program.png` | `crawl-ref/source/dat/tiles/stone_soup_icon-32x32.png` of crawl/crawl 0.34.1, reduced to 1 bit by `fetch_icons.py` | the Dungeon Crawl Stone Soup team | GPL-2.0-or-later or CC0 1.0 (see "ESC mark") |
