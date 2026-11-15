# Mindustry overlay: sources

`scripts/generate_app_overlays.py` renders `mindustry.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `mindustry_template` (2 files) | Mindustry: `mindustry` (the packaged launcher: `Mindustry.exe`, `Mindustry` on Linux, the Mindustry app on macOS), `com.github.anuken.mindustry` (the Flatpak id), and a `java` or `javaw` process whose window title is "Mindustry" |

How the desktop build runs, from `desktop/build.gradle` and `build.gradle` of
the tag below:

- The packaged builds (itch.io, Steam) are made with Packr
  (`--executable appName`, `appName = 'Mindustry'`). The launcher loads the
  bundled Java runtime into its own process, so the process is `Mindustry`.
- The jar from the GitHub release is started with `java -jar Mindustry.jar`,
  so the process is `java` (`javaw` when started by a double click on
  Windows). The mapping's `java` and `javaw` entries serve several programs
  and route by window title; the title is "Mindustry"
  (`title = "Mindustry"` in `desktop/src/mindustry/desktop/DesktopLauncher.java`).
- The Flatpak `com.github.Anuken.Mindustry` (linked from the README) was not
  examined. If it starts the jar, the process is `java`; the app id is listed
  for a platform that reports it.

Names not checked on an install.

## Shortcut reference

The default bindings in `core/src/mindustry/input/Binding.java` of
<https://github.com/Anuken/Mindustry>, tag `v160.7` (commit
`17012d61d9e4c3cbd9820d87e81c24495486ac53`), read 2026-11-14. It was the
highest version tag on that day; whether GitHub lists it as a stable release
or a pre-release was not checked. How the keys act was read in
`core/src/mindustry/input/DesktopInput.java`,
`core/src/mindustry/ui/fragments/PlacementFragment.java` and
`core/src/mindustry/core/Control.java` of the same tag. A user who changes a
key in the game still sees the default.

Left Shift is command mode. With the default setting "hold for command mode"
(`commandmodehold`, on) the mode lasts while the key is held, so its keys are
on the Shift layer: the digits select a control group, and with Left Ctrl held
as well (`create_control_group`) they create one. G and H act only in command
mode; they are drawn on the plain layer too, because they have no other
meaning and a player can switch the setting to a toggle.

| Key | Action | Binding |
|---|---|---|
| W / A / S / D | Move up / left / down / right | `move_y`, `move_x` |
| Left Shift | Command mode (hold) | `command_mode` |
| Left Ctrl | Control a unit or a turret (with a click) | `control` |
| V | Respawn | `respawn` |
| [ / ] | Pick up cargo / drop cargo | `pickupCargo`, `dropCargo` |
| Q | Clear building plans | `clear_building` |
| E | Pause or resume building | `pause_building` |
| R | Rotate the block under the cursor (hold, with the mouse wheel) | `rotateplaced` |
| B | Rebuild region | `rebuild_select` |
| F | Select a region as a schematic | `schematic_select` |
| Z / X | Flip schematic X / Y | `schematic_flip_x`, `schematic_flip_y` |
| T | Schematics menu | `schematic_menu` |
| , / . | Previous / next block category | `category_prev`, `category_next` |
| 1 to 9, 0 | Select block 1 to 10 of the category | `block_select_01` .. `block_select_10` |
| F1 | Block info | `block_info` |
| Shift + 1 to 9, 0 | Select control group 1 to 10 | the same digit keys, in command mode |
| Ctrl + Shift + 1 to 9, 0 | Create control group 1 to 10 | `create_control_group` held |
| G | Select all units (command mode) | `select_all_units` |
| H | Select all unit factories (command mode) | `select_all_unit_factories` |
| P | Ping the map | `ping` |
| Space | Pause | `pause` |
| M | Minimap | `minimap` |
| J | Research (campaign) | `research` |
| N | Planet map (campaign) | `planet_map` |
| C | Menus on / off | `toggle_menus` |
| F5 | Power lines on / off | `toggle_power_lines` |
| F6 | Block status on / off | `toggle_block_status` |
| F11 | Toggle fullscreen | `fullscreen` |
| F12 | Take screenshot | `screenshot` |
| Tab | Player list (multiplayer) | `player_list` |
| Enter | Open chat | `chat` |
| F8 | Console | `console` |
| Esc | program mark (Esc opens the menu) | `menu` |

Keys with a second meaning, which is not drawn:

| Key | Drawn | Other meaning |
|---|---|---|
| Left Shift | Command mode | Boost (`boost`), for a player unit that can boost; the game turns command mode off for such a unit. Also faster camera movement. |
| Left Ctrl | Control a unit | Diagonal placement while a block is placed (`diagonal_placement`); create a control group in command mode (drawn on Ctrl+Shift) |
| 1 to 9, 0 | Select block N | Pressed twice within 0.4 s: the first digit selects the category, the second the block |
| Tab | Player list | Chat mode, while the chat is open (`chat_mode`) |

## Left out

- **Left Alt** (`select_across_screen`): held with G or H in command mode, it
  limits the selection to the screen. Alt+Shift+G and Alt+Shift+H would show
  the same pictures as Shift+G and Shift+H, so they are not drawn.
- **The arrow keys** (`block_select_left/right/up/down`, and the chat history
  while the chat is open): the arrows keep their own legends.
- **Not bound by default:** `select_all_unit_transport`, `cancel_orders`, the
  `unit_stance_*` and `unit_command_*` bindings, `detach_camera`,
  `teleport_cursor`, `skip_wave`, `debug_hitboxes`, `performance_metrics`.
- **Mouse buttons and the wheel** (`select`, `deselect`, `break_block`, `pick`,
  `command_queue`, `mouse_move`, `pan`, `rotate`, `zoom`, `chat_scroll`): no
  keycap.

## Placement

As for the other game sets (`../aoe2/SOURCES.md`, Placement): every icon sits
at the right edge and uses the full height, and the firmware clears 3 px around
it, so a letter legend stays whole. F1, F5, F6, F8, Left Shift and Left Ctrl
use a 34×40 area. On the digits and on `,` `.` `[` `]` the icon erases the
shifted symbol, which the game does not use.

All icons are flat 1-bit silhouettes drawn at the size of their key area, so
the generator places them 1:1. The solid shapes fill a smaller box in the
bottom-right corner (`INK` in `fetch_icons.py`). The digits carry their number:
a filled block with the number cut out (select block 1 to 10), a shield with
the digit of the key cut out (control group; the 0 key is group 10), and a
smaller shield with a plus (create control group).

ESC shows the game's own window icon, `core/assets/icons/icon.png` at the
pinned commit, reduced to 40×40 with a box filter; pixels lighter than luma 130
are lit, which keeps the light tile, the dark octagon of the core and the light
chevron inside it. It sits at the right edge beside the ESC legend. Licence
reasoning: the repository's `LICENSE` is the GNU GPL version 3, the README
names no other licence for the art, and the file has no licence of its own, so
it falls under the project's GPL-3.0. GPL-3.0 is compatible with this
repository's GPL-3.0-or-later. No statement "or any later version" was found;
GPL-3.0-only is compatible as well, because this repository can be
distributed under version 3.

## Icons

Licence texts for the icon licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0

Where each icon file comes from. The icon table gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`
- Material Design Icons (`mdi:<name>`): `https://raw.githubusercontent.com/Templarian/MaterialDesign/2424e748e0cc63ab7b9c095a099b9fe239b737c0/svg/<name>.svg`
- GPL-3.0: https://www.gnu.org/licenses/gpl-3.0.html

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png`, `left.png`, `back.png`, `right.png` | Font Awesome Free 6.5.2 `arrow-up`, `arrow-left`, `arrow-down`, `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `command.png` | game-icons.net `lorc/rally-the-troops` | lorc | CC BY 3.0 |
| `control.png` | Font Awesome Free 6.5.2 `gamepad` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `respawn.png` | Font Awesome Free 6.5.2 `heart-pulse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pickup.png`, `dropcargo.png` | Font Awesome Free 6.5.2 `upload`, `download` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clearbuilding.png` | Font Awesome Free 6.5.2 `eraser` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pausebuilding.png` | Font Awesome Free 6.5.2 `circle-pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotate.png` | Font Awesome Free 6.5.2 `rotate` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rebuild.png` | Font Awesome Free 6.5.2 `hammer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `schematic.png` | Font Awesome Free 6.5.2 `vector-square` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `flipx.png`, `flipy.png` | Material Design Icons `flip-horizontal`, `flip-vertical` | Pictogrammers | Apache-2.0 |
| `schematics.png` | Material Design Icons `floor-plan` | Pictogrammers | Apache-2.0 |
| `categoryprev.png`, `categorynext.png` | Font Awesome Free 6.5.2 `angles-left`, `angles-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `blockinfo.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `block1.png` .. `block10.png` | Font Awesome Free 6.5.2 `square` (solid), numbered by `fetch_icons.py` (digits in DejaVu Sans Bold) | Fonticons, Inc. | CC BY 4.0 |
| `group1.png` .. `group10.png`, `newgroup1.png` .. `newgroup10.png` | Font Awesome Free 6.5.2 `shield` (solid), numbered by `fetch_icons.py`; the plus is drawn | Fonticons, Inc. | CC BY 4.0 |
| `allunits.png` | Font Awesome Free 6.5.2 `robot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `factories.png` | Font Awesome Free 6.5.2 `industry` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ping.png` | Font Awesome Free 6.5.2 `location-crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `minimap.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `research.png` | Font Awesome Free 6.5.2 `sitemap` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `planetmap.png` | Font Awesome Free 6.5.2 `globe` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `togglemenus.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `powerlines.png` | Font Awesome Free 6.5.2 `bolt` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `blockstatus.png` | Font Awesome Free 6.5.2 `traffic-light` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `playerlist.png` | Font Awesome Free 6.5.2 `users` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | `core/assets/icons/icon.png` of Anuken/Mindustry at commit 17012d6, reduced to 1 bit by `fetch_icons.py` | Anuken and the Mindustry contributors | GPL-3.0 |
