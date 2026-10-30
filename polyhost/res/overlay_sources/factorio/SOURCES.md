# Factorio overlay: sources

`scripts/generate_app_overlays.py` renders `factorio.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `factorio_template` (2 files) | Factorio 2.0 on Windows (`factorio.exe`) and Linux (the native `factorio`; `factorio.exe` under Wine; `steam_app_427520` under Proton) |
| `factorio_template_mac` (3 files) | Factorio 2.0 on macOS (`factorio.app`, reported as `factorio`) |

None of the app names was checked on an install. Factorio has a native Linux
build, so the Proton name is unlikely to occur.

## Shortcut reference

The default PC controls on the Factorio Wiki page "Controls"
(<https://wiki.factorio.com/Controls>; <https://wiki.factorio.com/Keyboard_bindings>
redirects there), read 2026-10-30 from the page's wikitext
(`index.php?title=Controls&action=raw`, last edited 2026-03-05). The page
describes Factorio 2.0 and Space Age (flip, rail layer, spidertron remote,
surfaces). A user who rebinds a control in Settings > Controls still sees the
default here.

### macOS

The Factorio modding API documents a COMMAND modifier that "is loaded as
CONTROL on Windows and Linux"
(<https://lua-api.factorio.com/latest/prototypes/CustomInputPrototype.html>,
`key_sequence`, read 2026-10-30), so a control can default to Cmd on macOS and
Ctrl elsewhere. The wiki does not say which built-in controls do this. Two
sources name the same five:

- <https://factoriocheatsheet.com/> → Tips → Common shortcuts ("Table only lists
  different macOS shortcuts", read 2026-10-30 with headless Chromium): Cut, Copy,
  Paste, Undo and Redo are Cmd+X, Cmd+C, Cmd+V, Cmd+Z and Cmd+Y on macOS.
- A Factorio forum moderator on macOS: "shift-Cmd-Z (on Mac that's redo)"
  (<https://forums.factorio.com/viewtopic.php?t=69903>, 2020-11-26).

Those five (and Shift+Redo) use `CMDCTRL` and are drawn on Cmd in the macOS
set. Every other binding is the same on every platform. Ctrl+F (focus search)
and Ctrl+Shift+F4 stay on Ctrl in the macOS set; neither source covers them, so
this is not checked. Alt is Option on a Mac keyboard and uses the same layer.

## Keys

| Key | Action |
|---|---|
| W A S D | Move up, left, down, right |
| E | Open character screen |
| Q | Pipette tool / clear cursor |
| R, Shift+R | Rotate, reverse rotate |
| H, V | Flip horizontal, flip vertical |
| F | Pick up items on the ground |
| Z | Drop item |
| G | Toggle rail layer (with a rail planner) |
| C | Next weapon |
| Space, Shift+Space | Shoot enemy, shoot selected |
| Enter | Enter / leave vehicle |
| \` | Toggle chat (and Lua console) |
| 1 to 0 | Quickbar shortcut 1 to 10 |
| Shift+1 to Shift+0 | Select quickbar 1 to 10 |
| X | Rotate active quickbars |
| Tab, M | Toggle world map |
| T | Technology screen |
| P | Production statistics |
| L | Logistic networks |
| B | Blueprint library |
| O | Train overview |
| F1, F2, F3 | Character logistics, character info, character crafting |
| Alt+Left, Alt+Right | Back, forward (last opened window) |
| J, K | Connect train, disconnect train |
| Ctrl+C, Ctrl+X, Ctrl+V | Copy, cut, paste (area tools) |
| Ctrl+Z, Ctrl+Y, Ctrl+Shift+Z | Undo, redo, redo |
| Ctrl+F | Focus search |
| Alt+T | Artillery targeting remote |
| Alt+B, Alt+D, Alt+U | New blueprint, new deconstruction planner, new upgrade planner |
| Alt+C, Alt+R, Alt+G | Copper, red, green wire connection mode |
| Alt+Y | Discharge defense remote |
| Alt+A | Spidertron remote |
| Alt+E, Alt+L, Alt+F | Toggle exoskeleton, personal logistics requests, personal roboport |
| Pause | Pause game |
| F4, F5 | Debug settings, basic debug |
| F9, Shift+F9 | Reset zoom level, zoom level 2x |
| F10 | Next player in a replay |
| Ctrl+Shift+F4 | Toggle GUI visibility |

Where one key has a second action in another context, the overlay shows the
first and this is the other: E also confirms a window; Q is pipette when an
entity is selected and clear cursor when the cursor holds an item (one icon,
the pipette); Tab also confirms a message.

## Left out

- Mouse bindings (build, mine, transfer, zoom, Alt+click Factoriopedia): no
  keycap cell.
- Alt alone (Alt-mode) and Shift alone (activate tooltip): modifier keys. No
  overlay set draws on a modifier key.
- Up and Down (select previous / next surface, remote view only), Ctrl+arrows
  (move the blueprint absolute grid) and Shift+arrows (move blueprint entities):
  they act only in remote view or with a blueprint in the cursor, and the arrow
  legend already shows the direction.
- Backspace (select previous mod): the mods screen only.
- Numpad keys (tile area size, editor game speed, UI scale): no keycap cell.
- Ctrl+F3, Ctrl+F5 to Ctrl+F8 (atlas, GUI debug, style view, shadows, glows),
  Ctrl+Shift+E, Ctrl+Shift+F (prototype GUIs) and Ctrl+Shift+F11 (`/editor`):
  tools for GUI and mod development.
- Controls the wiki lists as "Not set" (secondary quickbar shortcuts, new
  blueprint book, music track keys).

## Placement

As for Age of Empires II (`../aoe2/SOURCES.md` → Placement) and Warcraft III:
every icon sits at the right edge and uses the full height, and the firmware
clears 3 px around the icon's ink, so a letter legend stays whole. F1 and F2
use 34×40 and F4 30×40, the areas AoE2 measured to keep those legends whole.
F5 uses 30×40 like F4; its legend was not measured. F10 is 40×40 and covers the
right part of its legend, as in Warcraft III. On the digits the icon erases the
shifted symbol, which the game does not use.

The icons are flat 1-bit silhouettes, as in the AoE2 and Warcraft III sets.
The solid or wide icons (the chat bubble, the knapsack, the box, the train,
Pause and the movement arrows; `INK` in `fetch_icons.py`) are drawn in a
smaller box inside their area so they do not outweigh the outline icons. V is the
horizontal flip icon turned by 90 degrees.

The drawn icons, all 40×40 and placed 1:1 because their size equals the area:

- 1 to 0: a square quickbar slot with the number inside (0 is slot 10).
- Shift+1 to Shift+0: the number over a row of four small slots (a quickbar).
- Alt+C, Alt+R, Alt+G: the cable glyph over CU, RED or GRN. The three wire
  modes differ only by colour, which a 1-bit keycap cannot show.
- Shift+F9: the magnifier with 2x in the lens.

The text is Liberation Sans Bold. `fetch_icons.py` loads a font only when it
draws a missing PNG; a committed PNG is kept as it is.

Ctrl+C, Ctrl+X, Ctrl+V, Ctrl+Z, Ctrl+Y and Ctrl+F (Cmd on macOS for the first
five) name shared concepts, so the generator draws them with the shared
renderer, the same picture every app uses for that action.

ESC shows FACTORIO in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). Simple
Icons has no Factorio logo, and the game's logo art is not used. A pixel is
lit from grey 90 of 255.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `inventory.png` | game-icons.net `lorc/knapsack` | lorc | CC BY 3.0 |
| `pipette.png` | game-icons.net `lorc/eyedropper` | lorc | CC BY 3.0 |
| `pickup.png` | game-icons.net `lorc/grab` | lorc | CC BY 3.0 |
| `raillayer.png` | game-icons.net `delapouite/rail-road` | delapouite | CC BY 3.0 |
| `weapon.png` | game-icons.net `john-colburn/pistol-gun` | John Colburn | CC BY 3.0 |
| `shoot.png` | game-icons.net `delapouite/crosshair` | delapouite | CC BY 3.0 |
| `shootselected.png` | game-icons.net `sbed/targeted` | sbed | CC BY 3.0 |
| `vehicle.png` | game-icons.net `delapouite/car-door` | delapouite | CC BY 3.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `technology.png` | game-icons.net `lorc/round-bottom-flask` | lorc | CC BY 3.0 |
| `logistics.png` | game-icons.net `delapouite/cardboard-box-closed` | delapouite | CC BY 3.0 |
| `crafting.png` | game-icons.net `lorc/gear-hammer` | lorc | CC BY 3.0 |
| `artillery.png` | game-icons.net `lorc/cannon` | lorc | CC BY 3.0 |
| `newdecon.png` | game-icons.net `lorc/wrecking-ball` | lorc | CC BY 3.0 |
| `newupgrade.png` | game-icons.net `delapouite/upgrade` | delapouite | CC BY 3.0 |
| `discharge.png` | game-icons.net `lorc/lightning-shield` | lorc | CC BY 3.0 |
| `spidertron.png` | game-icons.net `carl-olsen/spider-alt` | Carl Olsen | CC BY 3.0 |
| `exoskeleton.png` | game-icons.net `delapouite/leg-armor` | delapouite | CC BY 3.0 |
| `roboport.png` | game-icons.net `delapouite/delivery-drone` | delapouite | CC BY 3.0 |
| `up.png`, `left.png`, `down.png`, `right.png` | Material Symbols `north`, `west`, `south`, `east` | Google | Apache-2.0 |
| `rotate.png`, `rotateback.png` | Material Symbols `rotate_right`, `rotate_left` | Google | Apache-2.0 |
| `fliph.png`, `flipv.png` | Material Symbols `flip` (`flipv` turned by 90 degrees) | Google | Apache-2.0 |
| `drop.png` | Material Symbols `place_item` | Google | Apache-2.0 |
| `quickbars.png` | Material Symbols `swap_vert` | Google | Apache-2.0 |
| `map.png` | Material Symbols `map` | Google | Apache-2.0 |
| `production.png` | Material Symbols `bar_chart` | Google | Apache-2.0 |
| `networks.png` | Material Symbols `hub` | Google | Apache-2.0 |
| `library.png` | Material Symbols `library_books` | Google | Apache-2.0 |
| `trains.png` | Material Symbols `train` | Google | Apache-2.0 |
| `character.png` | Material Symbols `person` | Google | Apache-2.0 |
| `back.png`, `forward.png` | Material Symbols `arrow_back`, `arrow_forward` | Google | Apache-2.0 |
| `newblueprint.png` | Material Symbols `architecture` | Google | Apache-2.0 |
| `connect.png`, `disconnect.png` | Material Symbols `link`, `link_off` | Google | Apache-2.0 |
| `pause.png` | Material Symbols `pause` | Google | Apache-2.0 |
| `debugsettings.png` | Material Symbols `bug_report` | Google | Apache-2.0 |
| `basicdebug.png` | Material Symbols `analytics` | Google | Apache-2.0 |
| `resetzoom.png` | Material Symbols `youtube_searched_for` | Google | Apache-2.0 |
| `replaynext.png` | Material Symbols `switch_account` | Google | Apache-2.0 |
| `hidegui.png` | Material Symbols `visibility_off` | Google | Apache-2.0 |
| `wirecopper.png`, `wirered.png`, `wiregreen.png` | Material Symbols `cable` + text drawn by `fetch_icons.py` (Liberation Sans Bold) | Google | Apache-2.0 |
| `zoom2x.png` | Material Symbols `search` + text drawn by `fetch_icons.py` (Liberation Sans Bold) | Google | Apache-2.0 |
| `slot0.png` … `slot9.png`, `bar0.png` … `bar9.png` | drawn by `fetch_icons.py` (Liberation Sans Bold) | — | this repo (GPL-3.0-or-later) |
| `program.png` | drawn by `fetch_icons.py` in Bebas Neue | font: Dharma Type | font: SIL OFL 1.1 |

## Art from the user's game files

When a Factorio install is on the machine, the host draws 21 keys of this
overlay from the game's own icons instead. The shipped files above stay the
fallback and are the only art in the repository. Wube's images are never
shipped: the host reads them from the user's install, writes the patched copy
to the user's cache directory, and sends it only to the keyboard.

⚠️ The reader was not run against a real Factorio install. The paths below are
from Wube's public prototype definitions, and the tests use synthetic PNG files
laid out the same way. Neither the look of the real icons at 40 px nor the
install folders were checked.

The mapping entry and its macOS sub-entry opt in with
`game_assets: factorio/factorio.yaml`. The `game_assets:` block at the end of
`factorio.yaml` names the reader (`factorio`) and the file each key reads.
Nothing is read until the overlay is first sent.

| Keys | From the game | File (under the data folder) |
|---|---|---|
| B, P, O, Tab and M, L, T | the buttons at the top right of the screen that open the same panels (blueprint library, production, trains, map, logistic networks, technology) | `core/graphics/side-menu-buttons.png`, 64 px rows 0, 1, 4, 7, 9 and 11 |
| Alt+B, Alt+D, Alt+U, Alt+T, Alt+Y, Alt+A, Alt+E, Alt+F | the shortcut bar buttons of the same controls | `base/graphics/icons/shortcut-toolbar/mip/` `new-blueprint`, `new-deconstruction-planner`, `new-upgrade-planner`, `artillery-targeting-remote`, `discharge-defense-remote`, `new-rts-tool`, `toggle-exoskeleton`, `toggle-personal-roboport`, each `-x56.png` (`-x32.png` before 2.0.18) |
| C | the pistol item | `base/graphics/icons/pistol.png` |
| Enter | the car item | `base/graphics/icons/car.png` |
| G | the rail item | `base/graphics/icons/rail.png` |
| F1, Alt+L | the logistic robot item | `base/graphics/icons/logistic-robot.png` |
| F2 | the character icon | `core/graphics/icons/entity/character.png` |

How the paths were checked: each one is the `icon` or `filename` of the
prototype named in the table, read from
[wube/factorio-data](https://github.com/wube/factorio-data) on 2026-10-30 at
commit `acf5a342afcb66c066b9d88d202e8622112da117` (version 2.1.24) and at the
tags `2.0.10` and `2.0.77`:

- `base/prototypes/shortcuts.lua`: the shortcuts `give-blueprint`,
  `give-deconstruction-planner`, `give-upgrade-planner`,
  `give-artillery-targeting-remote`, `give-discharge-defense-remote`,
  `give-spidertron-remote`, `toggle-equipment-movement-bonus` and
  `toggle-personal-roboport`. Each names the control it triggers
  (`associated_control_input`). The files are `-x56.png` in 2.0.77 and 2.1.24
  and `-x32.png` in 2.0.10; the changelog of 2.0.18 says "Updated shortcut
  icons and increased their size to 56px". The reader reads the first of the
  two that exists.
- `base/prototypes/item.lua`: the items `pistol`, `car`, `rail` and
  `logistic-robot`, unchanged from 2.0.10 to 2.1.24.
- `core/prototypes/utility-sprites.lua`: `side_menu_blueprint_library_icon`,
  `side_menu_production_icon`, `side_menu_train_icon`, `side_menu_map_icon`,
  `side_menu_logistic_networks_icon` and `side_menu_technology_icon`
  (`make_side_menu_button(row)`: 64 px, `y = row * 64`), and the default
  character modifier icon (`core/graphics/icons/entity/character.png`, 64 px).
  The same in 2.0.10 and 2.1.24.

The repository has no images, and none were downloaded.

Factorio 2.0 stores an icon with its smaller copies to the right of it (a
64 px icon is 64 + 32 + 16 + 8 = 120 px wide; the 2.0.7 changelog: "Mipmap
count will be inferred from icon_size and actual dimensions of the source
image"). The reader reads only the first square of the file, or the square in
the given row of a sheet.

Drawing (`mode` in the recipe): the GUI symbols (the side-menu buttons, the
shortcut icons and the character) are drawn as `silhouette`, the shape of the
symbol. A symbol that turns out to have parts of different brightness, or no
transparent background, is drawn as `threshold` instead so its inner lines are
kept. The item icons are drawn as `threshold`: the outline lit and the parts
lighter than mid-grey lit. Rendered on synthetic coloured icons (a pistol, a
car, a blueprint sheet and a robot, flat and shaded with noise) at 40 px,
`threshold` kept the shapes and `dither` turned the bodies into a dot pattern,
so no key uses `dither`.

Keys that keep the shipped art: the wire modes Alt+C, Alt+R and Alt+G (the
game's three wire icons are told apart by colour: the items carry
`color_hint` "C", "R" and "G", and a 1-bit keycap cannot show colour; the
shipped icons add CU, RED and GRN), and every key with no game icon of the same
action (movement, rotate, flip, pick up, drop, shoot, chat, quickbar slots,
inventory, crafting, train connect, pause, debug and zoom).

The reader looks for a folder with `base/info.json`, `core/info.json` and
`base/graphics/icons/` in this order:

1. the folder in the `game_factorio_data_dir` setting, when set: the data
   folder itself, the install folder above it, or `factorio.app`;
2. the data folder of the install the running game's executable is in
   (`bin/x64/factorio`, so two levels up; under Proton the game's working
   folder). macOS gives no executable folder, so a Mac skips this step;
3. `steamapps/common/Factorio/data` (macOS:
   `steamapps/common/Factorio/factorio.app/Contents/data`) in each Steam
   library;
4. `Factorio\data` under Program Files on Windows, `~/factorio/data` (the
   Linux archive unpacked in the home folder), and
   `/Applications/factorio.app/Contents/data` or
   `~/Applications/factorio.app/Contents/data` on macOS.

None of these folders was checked on an install.

| Setting | Default | Meaning |
|---|---|---|
| `game_assets_enabled` | `true` | `false` always sends the shipped files |
| `game_factorio_data_dir` | empty | the Factorio data folder; empty searches as above |

Copies are cached by the size and time of `base/info.json` and
`core/info.json` (a game update rewrites both), the shipped overlay, the spec
and `RENDER_VERSION`.
