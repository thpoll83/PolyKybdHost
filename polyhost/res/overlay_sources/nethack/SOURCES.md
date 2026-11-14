# NetHack overlay: sources

`scripts/generate_app_overlays.py` renders `nethack.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `nethack_template` (2 files) | NetHack. A terminal whose title has `nethack` at the command position (the tty and curses interfaces). A window of the process `nethack` (the Qt and X11 interfaces on Linux and macOS, when they are built into the main binary), `NetHackW.exe` (the Windows graphical interface) or `NetHack.exe` |

`nethack` is `GAME` in `sys/unix/Makefile.top`. `NetHack.exe` (console) and
`NetHackW.exe` (graphical) are the targets `NHTARGET` and `NHWTARGETS` in
`sys/windows/GNUmakefile`. Names not checked on an install. Distribution
packages that give a graphical build another binary name are not covered: no
such name is in the NetHack source.

The tty and curses interfaces run in a terminal and write no window title, so
the host sees the game only when the shell or the terminal puts the running
command into the title (`polyhost/res/overlay-mapping.md`, "An editor seen
only in the window title"). The `nethack` route in `&editor_titles` of the
mapping file requires `nethack` at the command position, as the `htop` route
does. A game on a public server over SSH or telnet (`ssh nethack@example.org`)
is not recognised. `NetHack.exe` started by a double click on Windows runs in a
console window whose process is the console host; its title was not measured,
so that case is probably not recognised.

## Shortcut reference

The command table `extcmdlist[]` in `src/cmd.c` of
<https://github.com/NetHack/NetHack>, release tag `NetHack-5.0.0_Released`
(commit `16ff59115315917b93185d026aeefea06db9b0f4`), with the bindings added in
`commands_init()` (`M-O`, `M-2`) and the direction keys set in
`reset_commands()`; all of the table was read. `doc/Guidebook.txt` of the same
tag gives the meaning of the direction and prefix keys. Read 2026-11-14.

Most installed copies are still 3.6.x, so the table was compared with
`src/cmd.c` of `NetHack-3.6.7_Released` (commit
`ed600d9f0f3c37677418f0150f59363ca641f3dc`). **Only a key that means the same
in both releases is drawn.** The keys that differ are under "Left out". A
user's `BIND` lines in the options file change the keys; this overlay shows the
defaults, with the `number_pad` option off (the default).

The game reads characters. A lower-case letter, an upper-case letter and
Ctrl+letter are three commands, drawn on the plain, Shift and Ctrl layers. The
symbol commands on the Shift layer (`@` on Shift+2, `<` on Shift+,) follow the
US layout. `M-x` in the game's documentation is Meta+x: Alt+x on Windows, and
in a terminal Alt+x only when the terminal sets the eighth bit, or sends Escape
first and the game's `altmeta` option is on (off by default). Those commands
are on the Alt layer (`M-a`) and the Alt+Shift layer (`M-A`); where Alt does
not reach the game they do nothing, and the same commands can be typed after
`#`.

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
| . | `.` | Rest one move | `wait.png` |
| S | `s` | Search for traps and secret doors | `search.png` |
| A | `a` | Apply (use) a tool | `apply.png` |
| C | `c` | Close a door | `closedoor.png` |
| D | `d` | Drop an item | `drop.png` |
| E | `e` | Eat something | `eat.png` |
| F | `f` | Fire ammunition from the quiver | `fire.png` |
| I | `i` | Show the inventory | `inventory.png` |
| O | `o` | Open a door | `opendoor.png` |
| P | `p` | Pay the shopping bill | `pay.png` |
| Q | `q` | Quaff (drink) something | `quaff.png` |
| R | `r` | Read a scroll or spellbook | `read.png` |
| T | `t` | Throw something | `throw.png` |
| W | `w` | Wield a weapon | `wield.png` |
| X | `x` | Swap the wielded and the secondary weapon | `swapweapons.png` |
| Z | `z` | Zap a wand | `zap.png` |
| , | `,` | Pick up things here | `pickup.png` |
| / | `/` | Show what a symbol means | `whatis.png` |
| ; | `;` | Show what a map symbol is | `glance.png` |
| \ | `\` | Show the discovered object types | `known.png` |
| ` | ``` | Show the discovered types of one class | `knownclass.png` |
| Shift+H | `H` | Rush west | `rush_w.png` |
| Shift+J | `J` | Rush south | `rush_s.png` |
| Shift+K | `K` | Rush north | `rush_n.png` |
| Shift+L | `L` | Rush east | `rush_e.png` |
| Shift+Y | `Y` | Rush north-west | `rush_nw.png` |
| Shift+U | `U` | Rush north-east | `rush_ne.png` |
| Shift+B | `B` | Rush south-west | `rush_sw.png` |
| Shift+N | `N` | Rush south-east | `rush_se.png` |
| Shift+A | `A` | Take off all armor | `takeoffall.png` |
| Shift+C | `C` | Name a monster, an object or an object type | `call.png` |
| Shift+D | `D` | Drop specific item types | `droptype.png` |
| Shift+E | `E` | Engrave writing on the floor | `engrave.png` |
| Shift+F | `F` | Prefix: fight in a direction | `fight.png` |
| Shift+I | `I` | Show the inventory of one item class | `inventtype.png` |
| Shift+O | `O` | Show the option settings | `options.png` |
| Shift+P | `P` | Put on an accessory | `puton.png` |
| Shift+Q | `Q` | Select ammunition for the quiver | `quiver.png` |
| Shift+R | `R` | Remove an accessory | `remove.png` |
| Shift+S | `S` | Save the game and exit | `save.png` |
| Shift+T | `T` | Take off one piece of armor | `takeoff.png` |
| Shift+W | `W` | Wear a piece of armor | `wear.png` |
| Shift+X | `X` | Toggle two-weapon combat | `twoweapon.png` |
| Shift+Z | `Z` | Cast a spell | `cast.png` |
| Shift+, | `<` | Go up a staircase | `upstairs.png` |
| Shift+. | `>` | Go down a staircase | `downstairs.png` |
| Shift+/ | `?` | Show the help menu | `help.png` |
| Shift+; | `:` | Look at what is here | `lookhere.png` |
| Shift+1 | `!` | Escape to a shell | `shell.png` |
| Shift+2 | `@` | Toggle the autopickup option | `autopickup.png` |
| Shift+3 | `#` | Type an extended command | `extended.png` |
| Shift+6 | `^` | Describe an adjacent trap | `showtrap.png` |
| Shift+7 | `&` | Tell what a key does | `whatdoes.png` |
| Shift+8 | `*` | Show all equipment in use | `seeall.png` |
| Shift+- | `_` | Travel to a place on the map | `travel.png` |
| Ctrl+H | `^H` | Run west | `run_w.png` |
| Ctrl+J | `^J` | Run south | `run_s.png` |
| Ctrl+K | `^K` | Run north | `run_n.png` |
| Ctrl+L | `^L` | Run east | `run_e.png` |
| Ctrl+Y | `^Y` | Run north-west | `run_nw.png` |
| Ctrl+U | `^U` | Run north-east | `run_ne.png` |
| Ctrl+B | `^B` | Run south-west | `run_sw.png` |
| Ctrl+N | `^N` | Run south-east | `run_se.png` |
| Ctrl+A | `^A` | Do the previous command again | `repeat.png` |
| Ctrl+D | `^D` | Kick something | `kick.png` |
| Ctrl+O | `^O` | Dungeon overview | `overview.png` |
| Ctrl+P | `^P` | Show the previous messages | `messages.png` |
| Ctrl+R | `^R` | Redraw the screen | `redraw.png` |
| Ctrl+T | `^T` | Teleport | `teleport.png` |
| Ctrl+X | `^X` | Show your attributes | `attributes.png` |
| Ctrl+Z | `^Z` | Suspend the game | `suspend.png` |
| Alt+A | `M-a` | Adjust inventory letters | `adjust.png` |
| Alt+C | `M-c` | Talk to someone | `chat.png` |
| Alt+D | `M-d` | Dip an object into something | `dip.png` |
| Alt+E | `M-e` | Advance or check skills | `enhance.png` |
| Alt+F | `M-f` | Force a lock | `force.png` |
| Alt+I | `M-i` | Invoke an object's special power | `invoke.png` |
| Alt+J | `M-j` | Jump to another place | `jump.png` |
| Alt+L | `M-l` | Loot a box on the floor | `loot.png` |
| Alt+M | `M-m` | Use a monster's special ability | `monster.png` |
| Alt+O | `M-o` | Offer a sacrifice | `offer.png` |
| Alt+P | `M-p` | Pray | `pray.png` |
| Alt+R | `M-r` | Rub a lamp or a stone | `rub.png` |
| Alt+S | `M-s` | Sit down | `sit.png` |
| Alt+T | `M-t` | Turn undead | `turn.png` |
| Alt+U | `M-u` | Untrap something | `untrap.png` |
| Alt+V | `M-v` | Show the version and build options | `version.png` |
| Alt+W | `M-w` | Wipe off your face | `wipe.png` |
| Alt+2 | `M-2` | Toggle two-weapon combat | `twoweapon.png` |
| Alt+Shift+A | `M-A` | Name the current level | `annotate.png` |
| Alt+Shift+C | `M-C` | List the conducts kept | `conduct.png` |
| Alt+Shift+O | `M-O` | Dungeon overview | `overview.png` |
| Alt+Shift+R | `M-R` | Mount or dismount a steed | `ride.png` |
| Alt+Shift+T | `M-T` | Empty a container | `tip.png` |
| Alt+Shift+/ | `M-/` | List all extended commands | `extendedlist.png` |

The same icon on two keys means the same command: `X` and `M-2` toggle
two-weapon combat, Ctrl+O and `M-O` show the dungeon overview.

Shift with a direction key "rushes": go until something stops you (the arrow
that ends at a bar). Ctrl with a direction key "runs": go until something
interesting is seen (the double chevron). Ctrl+H is also Backspace and Ctrl+J
is also Enter for the terminal; the game reads both as directions.

Other meanings of drawn keys (not drawn):

| Key | Command prompt (drawn) | Elsewhere |
|---|---|---|
| letters | commands | item prompts and menus: choose the item with that letter |
| `h` `j` `k` `l` `y` `u` `b` `n` | Move | direction prompts and the cursor of `;` and `_`: point |
| `.` `,` `;` `:` | Rest, pick up, glance, look here | position prompts: select; menus: select all, select page |
| `<` `>` | Stairs | menus: first and last page; position prompts: jump to a staircase |
| `?` | Help | prompts: list the choices |
| `F` | Prefix: fight in a direction | needs a direction key after it |

## Left out

Keys that differ between 5.0.0 and 3.6.7:

- `v`: chronicle (journal of events) in 5.0.0, short version in 3.6.7.
- `V`: short version in 5.0.0, game history in 3.6.7.
- `N`: not bound in 5.0.0, name (call) in 3.6.7. `M-n` and `M-N`: name in
  5.0.0 only.
- `|` (scroll the permanent inventory), Ctrl+`_` (travel again), Delete
  (terrain), `M-g` (genocided), `M-V` (vanquished) and `M-X` (explore mode):
  5.0.0 only.
- `M-q` (quit): 3.6.7 only.

Other keys:

- `g`, `G` and `m`: prefixes whose effect depends on the next key (`g` rush,
  `G` run, `m` move without fighting or picking up, or ask for a menu). The
  Shift and Ctrl direction keys do the same as `g` and `G` in one key.
- The digits: a count before a command (`number_pad` off).
- The arrow keys: the terminal interfaces read them as the `h` `j` `k` `l`
  directions; they keep their own legends. The keypad has no cell.
- Ctrl+E, F, G, I, V, W: wizard (debug) mode only.
- Ctrl+C (interrupt) and Ctrl+[ (Escape).
- Space: rests only when the `rest_on_space` option is on (off by default).
- `M-?` is drawn on Alt+Shift+/ (US layout); the Guidebook says it is "not
  supported by all platforms".
- The menu, text-prompt and position-prompt keys: they depend on the prompt.

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge
and uses the full height, and the firmware clears 3 px around it, so a letter
legend stays whole. On a digit or symbol key the shifted symbol of the legend
is erased.

All icons are flat 1-bit silhouettes drawn at their key area, so the generator
places them 1:1. A command that is another command with a change has that
command's icon at 31×31 with a small glyph in the top-left corner: a plus or
minus (put on and remove, wear and take off, untrap), two arrows (swap
weapons). The direction keys are drawn by the helpers in
`../dcss/fetch_icons.py`.

## ESC mark

ESC shows "Net" over "Hack" in VT323 (SIL OFL 1.1,
`ofl/vt323/VT323-Regular.ttf` from google/fonts at commit e7db6ca), a font
after the glyphs of a DEC VT320 terminal. Both lines are at the largest one
size at which each fits 70 px wide and both fit 38 px high, drawn over the
whole cell without the ESC legend (`program_icon_legend: false`, protocol
v25). A pixel is lit from grey 110 of 255.

The game's own art (the tile sets in `win/share/`, the Windows icon) is not
used. NetHack is under the NetHack General Public License (`dat/license`), a
copyleft licence based on the BISON General Public License of 1988. It is not
the GNU GPL and has no "any later version" clause, so its files cannot be
distributed under this repository's GPL-3.0-or-later.

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
| `apply.png` | Material Design Icons `pickaxe` | Pictogrammers | Apache-2.0 |
| `closedoor.png` | Font Awesome Free 6.5.2 `door-closed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `drop.png` | Material Design Icons `tray-arrow-down` | Pictogrammers | Apache-2.0 |
| `eat.png` | Font Awesome Free 6.5.2 `utensils` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fire.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `inventory.png` | Material Design Icons `bag-personal` | Pictogrammers | Apache-2.0 |
| `opendoor.png` | Font Awesome Free 6.5.2 `door-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pay.png` | Font Awesome Free 6.5.2 `coins` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quaff.png` | Font Awesome Free 6.5.2 `flask` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `read.png` | Font Awesome Free 6.5.2 `scroll` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `search.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `throw.png` | game-icons.net `lorc/thrown-daggers` | lorc | CC BY 3.0 |
| `wield.png` | Material Design Icons `sword` | Pictogrammers | Apache-2.0 |
| `swapweapons.png` | Material Design Icons `sword` with Font Awesome `right-left` in the corner, composed by `fetch_icons.py` | Pictogrammers; Fonticons, Inc. | Apache-2.0; CC BY 4.0 |
| `zap.png` | game-icons.net `lorc/crystal-wand` | lorc | CC BY 3.0 |
| `pickup.png` | Material Design Icons `tray-arrow-up` | Pictogrammers | Apache-2.0 |
| `wait.png` | Font Awesome Free 6.5.2 `hourglass-half` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `whatis.png` | Font Awesome Free 6.5.2 `question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `glance.png` | Font Awesome Free 6.5.2 `eye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `known.png` | Font Awesome Free 6.5.2 `clipboard-list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `knownclass.png` | Font Awesome Free 6.5.2 `list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `takeoffall.png` | Material Design Icons `hanger` | Pictogrammers | Apache-2.0 |
| `call.png` | Font Awesome Free 6.5.2 `tag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `droptype.png` | Material Design Icons `download-multiple` | Pictogrammers | Apache-2.0 |
| `engrave.png` | Font Awesome Free 6.5.2 `pen-nib` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fight.png` | Font Awesome Free 6.5.2 `hand-fist` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `inventtype.png` | Font Awesome Free 6.5.2 `filter` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `puton.png` | Font Awesome Free 6.5.2 `ring` (solid) with a plus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quiver.png` | Material Design Icons `bow-arrow` | Pictogrammers | Apache-2.0 |
| `remove.png` | Font Awesome Free 6.5.2 `ring` (solid) with a minus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `takeoff.png` | Font Awesome Free 6.5.2 `shirt` (solid) with a minus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `wear.png` | Font Awesome Free 6.5.2 `shirt` (solid) with a plus in the corner, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `twoweapon.png` | Material Design Icons `sword-cross` | Pictogrammers | Apache-2.0 |
| `cast.png` | Font Awesome Free 6.5.2 `wand-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `upstairs.png` | Material Design Icons `stairs-up` | Pictogrammers | Apache-2.0 |
| `downstairs.png` | Material Design Icons `stairs-down` | Pictogrammers | Apache-2.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autopickup.png` | Font Awesome Free 6.5.2 `magnet` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `extended.png` | Material Design Icons `form-textbox` | Pictogrammers | Apache-2.0 |
| `whatdoes.png` | Font Awesome Free 6.5.2 `keyboard` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `seeall.png` | Material Design Icons `shield-sword` | Pictogrammers | Apache-2.0 |
| `shell.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `showtrap.png` | game-icons.net `lorc/wolf-trap` | lorc | CC BY 3.0 |
| `travel.png` | Font Awesome Free 6.5.2 `route` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lookhere.png` | Material Design Icons `map-marker-question` | Pictogrammers | Apache-2.0 |
| `repeat.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `kick.png` | Material Design Icons `karate` | Pictogrammers | Apache-2.0 |
| `overview.png` | Font Awesome Free 6.5.2 `sitemap` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `messages.png` | Font Awesome Free 6.5.2 `message` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `redraw.png` | Font Awesome Free 6.5.2 `arrows-rotate` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `teleport.png` | game-icons.net `lorc/teleport` | lorc | CC BY 3.0 |
| `attributes.png` | Font Awesome Free 6.5.2 `id-card` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `suspend.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `adjust.png` | Font Awesome Free 6.5.2 `arrow-down-a-z` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | Font Awesome Free 6.5.2 `comments` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `dip.png` | Font Awesome Free 6.5.2 `fill-drip` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `enhance.png` | Font Awesome Free 6.5.2 `ranking-star` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `force.png` | Font Awesome Free 6.5.2 `lock-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `invoke.png` | Font Awesome Free 6.5.2 `hand-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `loot.png` | Material Design Icons `treasure-chest` | Pictogrammers | Apache-2.0 |
| `monster.png` | Font Awesome Free 6.5.2 `dragon` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `offer.png` | game-icons.net `lorc/fire-bowl` | lorc | CC BY 3.0 |
| `pray.png` | Font Awesome Free 6.5.2 `hands-praying` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rub.png` | game-icons.net `lorc/magic-lamp` | lorc | CC BY 3.0 |
| `sit.png` | Font Awesome Free 6.5.2 `chair` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `turn.png` | Font Awesome Free 6.5.2 `ghost` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `untrap.png` | game-icons.net `lorc/wolf-trap` with a minus in the corner, composed by `fetch_icons.py` | lorc | CC BY 3.0 |
| `version.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `wipe.png` | Font Awesome Free 6.5.2 `soap` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `extendedlist.png` | Font Awesome Free 6.5.2 `rectangle-list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `annotate.png` | Font Awesome Free 6.5.2 `thumbtack` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `conduct.png` | Font Awesome Free 6.5.2 `medal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ride.png` | Font Awesome Free 6.5.2 `horse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tip.png` | Material Design Icons `package-down` | Pictogrammers | Apache-2.0 |
| `move_<direction>.png` (8) | an arrow, drawn by `fetch_icons.py` | this repository | GPL-3.0-or-later |
| `rush_<direction>.png` (8) | an arrow that ends at a bar, drawn by `fetch_icons.py` | this repository | GPL-3.0-or-later |
| `run_<direction>.png` (8) | a double chevron, drawn by `fetch_icons.py` | this repository | GPL-3.0-or-later |
| `program.png` | "Net" over "Hack" set in VT323 by `fetch_icons.py` | The VT323 Project Authors (font) | SIL OFL 1.1 |
