# SuperTuxKart overlay: sources

`scripts/generate_app_overlays.py` renders `supertuxkart.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `supertuxkart_template` (1 file) | SuperTuxKart: `supertuxkart` on Linux and macOS, `supertuxkart.exe` on Windows, `net.supertuxkart.SuperTuxKart` as a Flatpak |

`supertuxkart` is the executable target in `CMakeLists.txt`
(`add_executable(supertuxkart ...)`, also the `MACOSX_BUNDLE` target) and the
`Exec=` and `StartupWMClass=` lines of `data/supertuxkart.desktop`. The Flatpak
id is the `<id>` in `data/net.supertuxkart.SuperTuxKart.metainfo.xml`. Names not
checked on an install.

## Shortcut reference

<https://github.com/supertuxkart/stk-code>, release tag `1.5` (commit
`1fb491f507216c5d181ccd85f29ff08eca003827`), read 2026-11-14:

- `src/input/keyboard_config.cpp`, `KeyboardConfig::setDefaultBinds()`: the
  default keys of the first keyboard player. In 1.5 the function is in this
  file, not in `src/config/device_config.cpp`.
- `src/input/input_manager.cpp`, `InputManager::handleStaticAction()`: keys the
  player cannot change.

A player changes the driving keys in Options > Controls; this overlay shows the
defaults.

| Key | Action | Source |
|---|---|---|
| Up | Accelerate (`PA_ACCEL`) | default binds |
| Down | Brake and reverse (`PA_BRAKE`) | default binds |
| Left, Right | Steer (`PA_STEER_LEFT`, `PA_STEER_RIGHT`) | default binds |
| N | Nitro (`PA_NITRO`) | default binds |
| V | Skid (`PA_DRIFT`) | default binds |
| Space | Use the power-up (`PA_FIRE`) | default binds |
| B | Look back (`PA_LOOK_BACK`) | default binds |
| Backspace | Rescue: put the kart back on the track (`PA_RESCUE`) | default binds |
| Print Screen | Take a screenshot | fixed |
| Ctrl+Print Screen | Start or stop video recording | fixed |
| F11 | Save a replay of this race | fixed |
| Ctrl+F11 | Save the race history | fixed |
| F12 | Show or hide the FPS display | fixed |
| Ctrl+F12 | Show or hide the power-up of each kart above it | fixed |
| Shift+F12 | Show or hide the soccer player list | fixed |

In the menus the arrow keys move the selection and Enter and Space select
(`PA_MENU_*`). The overlay shows the race meaning.

## Left out

- Escape (pause the race, back in the menus): the key shows the program mark.
- Alt and the left Windows key with Print Screen, F11 and F12. The game sets the
  same flag for Ctrl, Alt and the left Windows key (`control_is_pressed`), so
  they act like Ctrl. Only the Ctrl layer is drawn.
- Shift+F11 (write the render targets to files): a tool for developers.
- 1 to 9 in profile mode: only in `DEBUG` builds.
- The keys of the artist debug mode (`Debug::handleStaticAction`): the mode is
  off by default.
- Enter and Tab in the menus, and the text keys of the chat field.
- Keyboard configurations a player adds for a second player: they have no
  defaults of their own in the source read.

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge and
uses the full height (40×40), and the firmware clears 3 px around it, so a
letter legend stays whole. F11, F12, Backspace and Print Screen are 40×40 too
and cover the right end of their legends.

All icons are flat 1-bit silhouettes. The solid shapes (power-up, screenshot,
video, replay, rescue) fill a smaller box in the bottom-right corner so they do
not outweigh the outline icons (`INK` in `fetch_icons.py`).

ESC shows "Super" over "TuxKart" in Racing Sans One (SIL OFL 1.1,
`ofl/racingsansone/RacingSansOne-Regular.ttf` from google/fonts at commit
e7db6ca), both lines at the largest one size at which each fits 70 px wide and
both, 2 px apart, fit 38 px high, drawn over the whole cell without the ESC
legend (`program_icon_legend: false`, protocol v25).

The game's own logo is not used. The code is GPL-3.0-or-later, but `COPYING`
says the data files (textures, models and other art) have a mixture of
licences, including CC BY-SA, and names a `licenses.txt` per data directory.
The logo's licence was not traced to one of the allowed licences, so the name is
set in a font.

## Icons

Licence texts for the icon and font licences named in this file:

- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Material Design Icons are from Templarian/MaterialDesign at commit 2424e74.

| File | Source | Author | Licence |
|---|---|---|---|
| `accelerate.png` | Material Design Icons `speedometer` | Pictogrammers | Apache-2.0 |
| `brake.png` | Material Design Icons `car-brake-alert` | Pictogrammers | Apache-2.0 |
| `steerleft.png` | Material Design Icons `arrow-left-top-bold` | Pictogrammers | Apache-2.0 |
| `steerright.png` | Material Design Icons `arrow-right-top-bold` | Pictogrammers | Apache-2.0 |
| `nitro.png` | Material Design Icons `rocket-launch` | Pictogrammers | Apache-2.0 |
| `skid.png` | Material Design Icons `car-traction-control` | Pictogrammers | Apache-2.0 |
| `fire.png` | Font Awesome Free 6.5.2 `gift` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lookback.png` | Material Design Icons `eye-arrow-left` | Pictogrammers | Apache-2.0 |
| `rescue.png` | Font Awesome Free 6.5.2 `life-ring` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `recordvideo.png` | Font Awesome Free 6.5.2 `video` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `savereplay.png` | Font Awesome Free 6.5.2 `film` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `savehistory.png` | Font Awesome Free 6.5.2 `clock-rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fps.png` | Material Design Icons `counter` | Pictogrammers | Apache-2.0 |
| `kartpowerups.png` | Material Design Icons `go-kart` | Pictogrammers | Apache-2.0 |
| `soccerplayers.png` | Material Design Icons `soccer` | Pictogrammers | Apache-2.0 |
| `program.png` | "Super" over "TuxKart" set in Racing Sans One by `fetch_icons.py` | Impallari Type (font) | SIL OFL 1.1 |
