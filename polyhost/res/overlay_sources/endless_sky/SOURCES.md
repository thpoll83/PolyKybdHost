# Endless Sky overlay: sources

`scripts/generate_app_overlays.py` renders `endless_sky.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `endless_sky_template` (1 file) | Endless Sky: `endless-sky` on Linux, `Endless Sky.exe` on Windows, `Endless Sky` on macOS, `io.github.endless_sky.endless_sky` as a Flatpak |

The names come from `CMakeLists.txt` (`OUTPUT_NAME "endless-sky"` on Linux,
`"Endless Sky"` on Windows and macOS) and from
`io.github.endless_sky.endless_sky.desktop` (`Exec=endless-sky`; the file name
is the Flatpak id). The window title is "Endless Sky" (`SDL_CreateWindow()` in
`source/GameWindow.cpp`). Names not checked on an install.

## Shortcut reference

The default key file `keys.txt` of <https://github.com/endless-sky/endless-sky>,
release tag `v0.11.4` (commit `406661ebc4920816d02ac66e7e89e18554cfe0c8`), read
2026-11-14. It lists every command of `source/Command.cpp` with its SDL key
code. Three more groups of keys are not in the key file, because the game reads
them directly:

- `-` and `=` (zoom) and the digits (fleet groups): `MainPanel::KeyDown()` in
  `source/MainPanel.cpp`. `Engine::Step()` in `source/Engine.cpp` stores the
  selected ships as the group with Ctrl and adds the group to the selection
  with Shift.
- Shift with a command key: `Engine::HandleKeyboardInputs()` in
  `source/Engine.cpp` (Shift+Reverse stops the ship, Shift+Jump is the fleet
  jump) and `source/AI.cpp` (the other Shift rows below).

A player changes the keys in the preferences panel; this overlay shows the
defaults.

| Key | Action | With Shift |
|---|---|---|
| Up | Forward thrust | |
| Left, Right | Turn left, turn right | |
| Down | Reverse | Stop the ship |
| E | Auto steer | |
| A | Fire afterburner | |
| C | Toggle cloaking device | |
| Left Alt (hold) | Mouse turning | |
| Tab | Fire primary weapon | |
| Q | Fire secondary weapon | |
| W | Select secondary weapon | |
| N | Select next ship | Select next escort |
| R | Select nearest hostile ship | Select the nearest ship, friendly ones too |
| V | Select nearest asteroid | |
| B | Board selected ship | Board an escort (to repair it) |
| T | Talk to selected ship | |
| S | Scan selected ship | |
| L | Land on planet or station | |
| J | Hyperspace jump | Fleet jump (wait for the escorts) |
| D | Deploy or recall fighters | Deploy all fighters, damaged ones too |
| F | Fleet: fight my target | |
| Y | Fleet: toggle hold fire | |
| G | Fleet: gather around me | Fleet: next formation |
| H | Fleet: hold position | |
| U | Fleet: toggle ammo usage | |
| Z | Fleet: harvest flotsam | |
| 0 to 9 | Select fleet group | Add the group to the selection. With Ctrl: store the selected ships as the group |
| M | View star map | |
| I | View player info | |
| / | View message log | |
| F1 | Show help | |
| P | Pause | |
| Caps Lock | Toggle fast-forward | |
| F3 | Toggle performance info | |
| F11 | Toggle fullscreen | |
| = and - | Zoom the view in and out | |

The keys act in flight. On a planet and in the map and info panels the letters
choose panel buttons (for example D for "Depart"), which depend on the panel,
so the flight meaning is drawn.

## Left out

- "Toggle turret tracking", "Turret aim override (hold)" and "Fleet: Scan my
  target": commands with no key in `keys.txt`.
- The keypad `+` and `-` (zoom): the keypad has no cell.
- Shift, Ctrl and Alt with a mouse click or drag (select escorts): modifiers
  with the mouse, not a key.
- The panel buttons on a planet, in the shop, map and info panels: they depend
  on the panel.

## Placement

As for Age of Empires II and fheroes2 (`../aoe2/SOURCES.md`): every icon sits
at the right edge and uses the full height, and the firmware clears 3 px around
it, so a letter legend stays whole. F1 and F3 are 34×40 and F11 is 21×40, the
widths AoE2 measured to keep those legends whole. The digit icons erase the
shifted symbol of their key.

All icons are flat 1-bit silhouettes drawn at their key area. The solid shapes
listed in `INK` in `fetch_icons.py` fill a smaller box in the bottom-right
corner so they do not outweigh the outline icons.

The fleet group keys are composed by `groups()`: the Font Awesome
`shuttle-space` at the bottom of the area with the group number (DejaVu Sans
Bold, 14 px) in the top-right corner. The Shift copies add a plus in the
top-left corner. The Ctrl copies show the Font Awesome `flag` in place of the
ship.

ESC shows "Endless" over "Sky" in Russo One (SIL OFL 1.1,
`ofl/russoone/RussoOne-Regular.ttf` from google/fonts at commit e7db6ca), both
lines at the largest one size at which each fits 70 px wide and both, 2 px
apart, fit 38 px high, drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25).

The game's own icon (`icons/endless-sky.iconset/`) falls under the `Files: *`
entry of the repository's `copyright` file, GPL-3.0-or-later, so the licence
would allow it. It is a shaded picture of a ship, and at 40 px and 1 bit it is
a shape nobody can recognise (tested at six thresholds, light pixels lit and
dark pixels lit). So the name is drawn instead. The art under `images/` is
CC BY-SA 4.0 and is not used.

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
- DejaVu fonts licence (the digits): https://dejavu-fonts.github.io/License.html

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png` | Font Awesome Free 6.5.2 `rocket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `turnleft.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `turnright.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reverse.png` | Font Awesome Free 6.5.2 `arrow-turn-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autosteer.png` | Material Design Icons `steering` | Pictogrammers | Apache-2.0 |
| `afterburner.png` | Font Awesome Free 6.5.2 `fire` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cloak.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mouseturn.png` | Font Awesome Free 6.5.2 `computer-mouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `stop.png` | Font Awesome Free 6.5.2 `circle-stop` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `primary.png` | game-icons.net `lorc/ray-gun` | lorc | CC BY 3.0 |
| `secondary.png` | game-icons.net `lorc/rocket` | lorc | CC BY 3.0 |
| `selectsecondary.png` | Font Awesome Free 6.5.2 `list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `nextship.png` | Material Design Icons `target` | Pictogrammers | Apache-2.0 |
| `nearesthostile.png` | Material Design Icons `skull-scan` | Pictogrammers | Apache-2.0 |
| `nearestasteroid.png` | Font Awesome Free 6.5.2 `meteor` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `nextescort.png` | Font Awesome Free 6.5.2 `shield-halved` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `nearestany.png` | Material Design Icons `crosshairs-gps` | Pictogrammers | Apache-2.0 |
| `board.png` | Font Awesome Free 6.5.2 `right-to-bracket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `repair.png` | Font Awesome Free 6.5.2 `screwdriver-wrench` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hail.png` | Font Awesome Free 6.5.2 `comments` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scan.png` | game-icons.net `lorc/radar-sweep` | lorc | CC BY 3.0 |
| `land.png` | Font Awesome Free 6.5.2 `plane-arrival` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jump.png` | game-icons.net `lorc/vortex` | lorc | CC BY 3.0 |
| `fleetjump.png` | game-icons.net `lorc/star-swirl` | lorc | CC BY 3.0 |
| `deploy.png` | Font Awesome Free 6.5.2 `jet-fighter-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `forcedeploy.png` | game-icons.net `delapouite/jet-fighter` | delapouite | CC BY 3.0 |
| `fight.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `holdfire.png` | Font Awesome Free 6.5.2 `ban` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gather.png` | Font Awesome Free 6.5.2 `arrows-to-circle` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `formation.png` | Material Design Icons `dots-triangle` | Pictogrammers | Apache-2.0 |
| `holdposition.png` | Font Awesome Free 6.5.2 `anchor` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ammo.png` | game-icons.net `lorc/bullets` | lorc | CC BY 3.0 |
| `harvest.png` | Font Awesome Free 6.5.2 `box-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `map.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `info.png` | Font Awesome Free 6.5.2 `id-card` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `messagelog.png` | Font Awesome Free 6.5.2 `scroll` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fastforward.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `performance.png` | Font Awesome Free 6.5.2 `gauge-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `group0.png` to `group9.png`, `groupadd0.png` to `groupadd9.png` | Font Awesome Free 6.5.2 `shuttle-space` (solid) with the group number, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `groupset0.png` to `groupset9.png` | Font Awesome Free 6.5.2 `flag` (solid) with the group number, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "Endless" over "Sky" set in Russo One by `fetch_icons.py` | Jovanny Lemonad (font) | SIL OFL 1.1 |
