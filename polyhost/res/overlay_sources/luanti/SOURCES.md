# Luanti overlay: sources

`scripts/generate_app_overlays.py` renders `luanti.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `luanti_template` (1 file) | Luanti, the voxel game engine that was named Minetest up to 5.9: `luanti` (Linux, macOS, and `luanti.exe` on Windows), `minetest` (releases up to 5.9), and the app ids `org.luanti.luanti` and `net.minetest.minetest` |

`luanti` is the CMake project name (`project(luanti)` in `CMakeLists.txt`),
which names the executable and the macOS bundle (`${PROJECT_NAME}.app`).
`misc/org.luanti.luanti.desktop` has `Exec=luanti` and `StartupWMClass=luanti`;
the desktop file name is the app id. `minetest` and `net.minetest.minetest` are
the names of the releases before the rename (5.9.1 and older). Names not
checked on an install.

## Shortcut reference

The `keymap_*` defaults in `src/defaultsettings.cpp` of
<https://github.com/luanti-org/luanti>, release tag `5.18.0` (commit
`e8f12bf1b93245cfc479ea21787beb1ec472cce9`), read 2026-11-14. The file stores
each key as an SDL scancode with the key name in a comment; both were read. A
user who changes a key in the game still sees the default.

Luanti is an engine: the game that runs in it (Minetest Game, VoxeLibre, and
others) decides what an item does, but the keys below belong to the engine and
are the same in every game.

Sneak is Left Shift and is held while the player moves. So the sneak icon is
drawn on Left Shift itself, with and without Shift held, and the movement keys,
Space and the hotbar digits are drawn on the Shift layer as well. The copies
are the same images.

| Key | Action | Setting |
|---|---|---|
| W / A / S / D | Walk forward / strafe left / walk backward / strafe right | `keymap_forward`, `keymap_left`, `keymap_backward`, `keymap_right` |
| Space | Jump | `keymap_jump` |
| Left Shift | Sneak | `keymap_sneak` |
| E | Aux1 | `keymap_aux1` |
| K | Fly mode on / off | `keymap_freemove` |
| J | Fast mode on / off | `keymap_fastmove` |
| H | Noclip mode on / off | `keymap_noclip` |
| 1 to 9, 0 | Hotbar slot 1 to 10 | `keymap_slot1` .. `keymap_slot10` |
| N / B | Next / previous hotbar item | `keymap_hotbar_next`, `keymap_hotbar_previous` |
| I | Inventory | `keymap_inventory` |
| Q | Drop item | `keymap_drop` |
| T | Open chat | `keymap_chat` |
| / | Open command | `keymap_cmd` |
| . | Local command | `keymap_cmd_local` |
| F10 | Large chat console | `keymap_console` |
| F2 | Chat on / off | `keymap_toggle_chat` |
| Z | Zoom | `keymap_zoom` |
| V | Minimap mode | `keymap_minimap` |
| C | Camera mode | `keymap_camera_mode` |
| = | View range up (the comment in the file names the key `+`; scancode 46 is the `=` `+` key) | `keymap_increase_viewing_range_min` |
| - | View range down | `keymap_decrease_viewing_range_min` |
| F1 | HUD on / off | `keymap_toggle_hud` |
| F3 | Fog on / off | `keymap_toggle_fog` |
| M | Mute | `keymap_mute` |
| F5 | Debug info | `keymap_toggle_debug` |
| F6 | Profiler | `keymap_toggle_profiler` |
| F11 | Toggle fullscreen | `keymap_fullscreen` |
| F12 | Take screenshot | `keymap_screenshot` |
| Esc | program mark (Esc opens the pause menu) | |

Aux1 has no fixed effect: with fast mode on it makes the player run, in a
liquid or on a ladder it moves the player down, and a game can read it for its
own use. The key shows its name, as the game's key list does.

## Left out

- **F4** (`keymap_toggle_update_camera`) and **Home, End, Page Up, Page Down**
  (`keymap_quicktune_*`): bound only in debug builds (`#ifndef NDEBUG`).
- **R** (`keymap_rangeselect`, unlimited view range): bound only on a device
  with a touch screen (`has_touch`).
- **Not bound by default:** `keymap_autoforward`, `keymap_pitchmove`,
  `keymap_cinematic`, `keymap_increase_volume`, `keymap_decrease_volume`,
  `keymap_toggle_block_bounds`, `keymap_close_world`, `keymap_slot11` to
  `keymap_slot32`, and `keymap_pause` (a gamepad button only).
- **Mouse buttons** (`keymap_dig`, `keymap_place`) and the gamepad bindings: no
  keycap.

## Placement

As for the Minecraft sets (`../minecraft/SOURCES.md`, Placement): every icon
sits at the right edge and uses the full height, and the firmware clears 3 px
around it, so a letter legend stays whole. F1, F2, F5, F6 and Left Shift use a
34×40 area. On the digits and on `/`, `.`, `=` and `-` the icon erases the
shifted symbol, which the game does not use.

Every key icon is drawn 1-bit on a grid of 2 px squares (`BLOCK`), at the size
of its key area, so the generator places it 1:1. The icons for actions that
Minecraft also has (movement, jump, sneak, inventory, drop, chat, command, HUD,
debug, camera mode, fullscreen, screenshot, the hotbar slots) are made by the
Minecraft script's own tables and functions, so they are the same pictures.
Slot 10 on the 0 key is the same slot with "10" at 3x. View range up and down
are a landscape over a plus or a minus, drawn on the half grid.

ESC shows LUANTI in Monocraft (SIL OFL 1.1, `dist/Monocraft-ttf/Monocraft.ttf`
from IdreesInc/Monocraft at commit e498bf7), each 5×7 letter 2x across and 3x
down, drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25). The game's own logo
(`misc/luanti.svg`, `misc/luanti-icon.ico`) is CC BY-SA 3.0 according to
`LICENSE.txt` of the release. CC BY-SA is not compatible with this
repository's GPL-3.0-or-later, so the logo is not used.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png`, `left.png`, `back.png`, `right.png` | Font Awesome Free 6.5.2 `arrow-up`, `arrow-left`, `arrow-down`, `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `sneak.png` | drawn by `../minecraft/fetch_icons.py` (`SNEAK`): a player in the sneak pose, pixel by pixel | (this repo) | |
| `sprint.png` (fast mode) | Font Awesome Free 6.5.2 `person-running` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fly.png` | Font Awesome Free 6.5.2 `dove` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `noclip.png` | Font Awesome Free 6.5.2 `ghost` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `aux1.png` | drawn by `fetch_icons.py`; letters in Monocraft | Idrees Hassan | SIL OFL 1.1 |
| `slot1.png` .. `slot10.png` | drawn by `../minecraft/fetch_icons.py` and `fetch_icons.py`; digits in Monocraft | Idrees Hassan | SIL OFL 1.1 |
| `hotbarnext.png`, `hotbarprev.png` | Font Awesome Free 6.5.2 `angles-right`, `angles-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `inventory.png` | game-icons.net `delapouite/cardboard-box-closed` | delapouite | CC BY 3.0 |
| `drop.png` | drawn by `../minecraft/fetch_icons.py`: a square pixel block over a down arrow | (this repo) | |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `command.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `localcommand.png` | Font Awesome Free 6.5.2 `laptop-code` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `comments` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `togglechat.png` | Font Awesome Free 6.5.2 `comment-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoom.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `minimap.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `perspective.png` | Font Awesome Free 6.5.2 `street-view` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rangeup.png`, `rangedown.png` | Font Awesome Free 6.5.2 `mountain-sun` (solid) over a drawn plus or minus, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `hidehud.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fog.png` | Font Awesome Free 6.5.2 `smog` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mute.png` | Font Awesome Free 6.5.2 `volume-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `debug.png` | Font Awesome Free 6.5.2 `bug` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `profiler.png` | Font Awesome Free 6.5.2 `chart-line` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | LUANTI set in Monocraft by `fetch_icons.py` | Idrees Hassan (font) | SIL OFL 1.1 |
