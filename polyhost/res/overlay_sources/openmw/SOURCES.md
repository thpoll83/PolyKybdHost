# OpenMW overlay: sources

`scripts/generate_app_overlays.py` renders `openmw.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `openmw_template` (1 file) | OpenMW, the free engine for The Elder Scrolls III: Morrowind: `openmw` (Linux, `openmw.exe` on Windows, the OpenMW app on macOS) and `org.openmw.openmw` (the Flathub app id) |

`openmw` is the executable target in `apps/openmw/CMakeLists.txt`
(`openmw_add_executable(openmw ...)`). The window title is "OpenMW"
(`SDL_CreateWindow("OpenMW", ...)` in `apps/openmw/engine.cpp`). The launcher
(`openmw-launcher`), the content editor (`openmw-cs`) and the other tools are
different processes and get no set. The Flathub id was not read from the
source. Names not checked on an install.

## Shortcut reference

The default key table in `BindingsManager::loadKeyDefaults()`,
`apps/openmw/mwinput/bindingsmanager.cpp` of <https://github.com/OpenMW/openmw>
(the mirror of <https://gitlab.com/OpenMW/openmw>), release tag
`openmw-0.51.0` (commit `f4bec41444214a7903bebd178389ca22ca13f646`), read
2026-11-14. The table binds SDL scancodes, so the keys are positions on the
keyboard. A user who changes a key in the game still sees the default.

Run is Left Shift and sneak is Left Ctrl. Both are held while the character
moves, so the run icon is drawn on Left Shift itself, with and without Shift
held, the sneak icon on Left Ctrl in the same way, and the movement keys, jump
and activate are drawn on the Shift and Ctrl layers as well. The copies are the
same images.

| Key | Action | Action id |
|---|---|---|
| W / A / S / D | Move forward / left / backward / right | `A_MoveForward`, `A_MoveLeft`, `A_MoveBackward`, `A_MoveRight` |
| E | Jump | `A_Jump` |
| Space | Activate | `A_Activate` |
| Left Shift | Run | `A_Run` |
| Left Ctrl | Sneak | `A_Sneak` |
| Caps Lock | Always run on / off | `A_AlwaysRun` |
| Q | Auto move | `A_AutoMove` |
| F | Ready weapon | `A_ToggleWeapon` |
| R | Ready spell | `A_ToggleSpell` |
| [ / ] | Previous / next weapon | `A_CycleWeaponLeft`, `A_CycleWeaponRight` |
| - / = | Previous / next spell | `A_CycleSpellLeft`, `A_CycleSpellRight` |
| 1 to 9, 0 | Quick key 1 to 10 | `A_QuickKey1` .. `A_QuickKey10` |
| F1 | Quick keys menu | `A_QuickKeysMenu` |
| J | Journal | `A_Journal` |
| T | Rest | `A_Rest` |
| Tab | First / third person | `A_TogglePOV` |
| ` | Console | `A_Console` |
| F2 | Post-processing HUD | `A_TogglePostProcessorHUD` |
| F10 | Debug window | `A_ToggleDebug` |
| F11 | HUD on / off | `A_ToggleHUD` |
| F12 | Take screenshot | `A_Screenshot` |
| F5 | Quick save | `A_QuickSave` |
| F9 | Quick load | `A_QuickLoad` |
| Esc | program mark (Esc opens the game menu) | `A_GameMenu` |

## Left out

- **F3 and F4**: the same file reserves them (a user cannot bind them), but
  the default table gives them no action. What they do was not read.
- **The keypad** (4, 6, 8, 2 look around): no keycap cell.
- **Mouse buttons and the wheel** (`A_Use`, `A_Inventory`, `A_ZoomIn`,
  `A_ZoomOut`): no keycap.
- **Ctrl+Shift** (run and sneak held together): the movement copies are not
  repeated on that layer.
- Morrowind mods written in Lua can add their own keys; they are not part of
  the engine's table.

## Placement

As for the other game sets (`../aoe2/SOURCES.md`, Placement): every icon sits
at the right edge and uses the full height, and the firmware clears 3 px around
it, so a letter legend stays whole. F1, F2, F5, F9, Left Shift, Left Ctrl and
Caps Lock use a 34×40 area. On the digits and on `[` `]` `-` `=` and the
backquote the icon erases the shifted symbol, which the game does not use.

All icons are flat 1-bit silhouettes drawn at the size of their key area, so
the generator places them 1:1. The solid shapes fill a smaller box in the
bottom-right corner (`INK` in `fetch_icons.py`). The quick keys are a 36 px
square frame with the number; the 0 key shows 10. Previous and next weapon are
the sword with a solid triangle on its left or right; previous and next spell
are the hand in the same way. Quick save and quick load are the disk or the
folder with a bolt, as fheroes2's quick save.

ESC shows "Open" over "MW" in Cinzel Decorative Bold (SIL OFL 1.1,
`ofl/cinzeldecorative/CinzelDecorative-Bold.ttf` from google/fonts at commit
e7db6ca), each line at the largest size at which it fits 70 px wide, drawn over
the whole cell without the ESC legend (`program_icon_legend: false`, protocol
v25). A pixel is lit from grey 80 of 255.

The project's logo (a moon and star) is not used. `AUTHORS.md` of the release
says the logo was provided to the project by a named person ("for kindly
providing us with the Moon and Star logo, used as the application icon and
project logo") and gives no licence for it; the README names GPLv3 for the
project and separate licences only for the fonts. So the logo's licence is not
clear, and the name is drawn instead. Morrowind's own art is proprietary and
not used.

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
- Material Design Icons (`mdi:<name>`): `https://raw.githubusercontent.com/Templarian/MaterialDesign/2424e748e0cc63ab7b9c095a099b9fe239b737c0/svg/<name>.svg`

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png`, `left.png`, `back.png`, `right.png` | Font Awesome Free 6.5.2 `arrow-up`, `arrow-left`, `arrow-down`, `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `activate.png` | Font Awesome Free 6.5.2 `hand-pointer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `run.png` | Font Awesome Free 6.5.2 `person-running` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sneak.png` | Font Awesome Free 6.5.2 `user-ninja` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `alwaysrun.png` | Material Design Icons `run-fast` | Pictogrammers | Apache-2.0 |
| `automove.png` | Font Awesome Free 6.5.2 `person-walking-arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `weapon.png` | game-icons.net `lorc/broadsword` | lorc | CC BY 3.0 |
| `spell.png` | Font Awesome Free 6.5.2 `hand-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `prevweapon.png`, `nextweapon.png` | game-icons.net `lorc/broadsword` beside Font Awesome Free 6.5.2 `caret-left` or `caret-right`, composed by `fetch_icons.py` | lorc; Fonticons, Inc. | CC BY 3.0; CC BY 4.0 |
| `prevspell.png`, `nextspell.png` | Font Awesome Free 6.5.2 `hand-sparkles` beside `caret-left` or `caret-right`, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quick1.png` .. `quick10.png` | drawn by `fetch_icons.py`: a frame with the number in DejaVu Sans Bold | (this repo) | |
| `quickmenu.png` | Font Awesome Free 6.5.2 `table-cells` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `journal.png` | Font Awesome Free 6.5.2 `book-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rest.png` | Font Awesome Free 6.5.2 `bed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pov.png` | Font Awesome Free 6.5.2 `street-view` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `postprocess.png` | Font Awesome Free 6.5.2 `sliders` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `debug.png` | Font Awesome Free 6.5.2 `bug` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hidehud.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quickload.png` | Font Awesome Free 6.5.2 `folder-open` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "Open" over "MW" set in Cinzel Decorative Bold by `fetch_icons.py` | Natanael Gama (font) | SIL OFL 1.1 |
