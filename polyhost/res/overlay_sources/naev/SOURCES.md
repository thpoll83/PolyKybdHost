# Naev overlay: sources

`scripts/generate_app_overlays.py` renders `naev.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `naev_template` (1 file) | Naev: `naev` on Linux and macOS, `naev.exe` on Windows, `org.naev.Naev` as a Flatpak |

`naev` is the executable target in `meson.build` (`executable('naev', ...)`),
the `Exec=` line of `org.naev.Naev.desktop` and the `CFBundleExecutable` of
`extras/macos/Info.plist.in`; `org.naev.Naev` is the `<id>` in
`org.naev.Naev.metainfo.xml`. Names not checked on an install.

## Shortcut reference

`input_setDefault()` in `src/input.c` of <https://github.com/naev/naev>, release
tag `v0.13.5` (commit `7ead32f231bf448af45f4d8d6b121d50894bdec2`), read
2026-11-14. The action names are those of `keybind_info` in the same file. The
function has two layouts. `src/conf.c` calls `input_setDefault( 1 )`, the WASD
layout, for a new configuration, so that layout is drawn. A player changes the
keys in the options menu; this overlay shows the defaults.

| Key | Action |
|---|---|
| W | Accelerate |
| A, D | Turn left, turn right |
| S | Reverse |
| Q | Face target |
| F | Stealth |
| Space | Fire primary weapon |
| Left Shift | Fire secondary weapon |
| 1 to 9, 0 | Weapon set 1 to 9 and 0 |
| T | Target nearest |
| R | Target nearest hostile |
| C | Clear target |
| End | Escorts: attack my target |
| Insert | Escorts: hold formation |
| Delete | Escorts: return to the hangars |
| Home | Escorts: clear commands |
| P | Target space object ("spob") |
| L | Approach, or land |
| H | Target jump point |
| J | Initiate jump |
| M | Star map |
| Tab | Overlay map |
| Y | Hail target |
| U | Scan target |
| Page Up, Page Down | Scroll the log |
| I | Information menu |
| Pause | Pause |
| ` | Toggle speed |
| F11 | Screenshot |
| F2 | Lua console |
| Ctrl+E, Ctrl+Q | Target next, target previous |
| Ctrl+J | Autonavigation on |
| Ctrl+X | Mouse flight |
| Ctrl+S | Active cooldown |
| Ctrl+Y | Autohail |

The source binds W, A, D, S, T, R, C, Space, Tab, U, the digits and the escort
keys with `NMOD_ANY`: they act with any modifier held. They are drawn on the
plain layer only. The other plain keys are bound with `NMOD_NONE`.

## Left out

- The arrow-key layout (`input_setDefault( 0 )`): not the default of a new
  configuration. With it the arrows fly the ship and T, N, R and Backspace
  choose targets.
- Keypad `+`, `-` (zoom) and `*` (screenshot): the keypad has no cell. F11
  takes the screenshot too and is drawn.
- Ctrl+V (paste): it acts in text fields.
- "Target Next Hostile", "Target Previous Hostile", "Target Next Escort" and
  "Target Previous Escort": no default key in the WASD layout.
- Escape (small menu): the ESC key shows the program mark.

## Placement

As for Age of Empires II and fheroes2 (`../aoe2/SOURCES.md`): every icon sits
at the right edge and uses the full height, and the firmware clears 3 px around
it, so a letter legend stays whole. F2 is 34×40 and F11 is 21×40, the widths
AoE2 measured to keep those legends whole. The digit icons erase the shifted
symbol of their key.

All icons are flat 1-bit silhouettes drawn at their key area. The solid shapes
listed in `INK` in `fetch_icons.py` fill a smaller box in the bottom-right
corner so they do not outweigh the outline icons.

The weapon set keys are composed by `weapon_sets()`: the game-icons.net ray gun
at the bottom of the area with the set number (DejaVu Sans Bold, 14 px) in the
top-right corner.

ESC shows "NAEV" in Quantico Bold (SIL OFL 1.1,
`ofl/quantico/Quantico-Bold.ttf` from google/fonts at commit e7db6ca) at the
largest size at which it fits 70 px wide, drawn over the whole cell without the
ESC legend (`program_icon_legend: false`, protocol v25).

The game's own logo (`extras/logos/naev.png`) is not used. The repository's
`LICENSE` file puts the source code under GPL-3.0 and "all other files" under
CC BY-SA 4.0, unless `gfx/ARTWORK_LICENSE.yaml` says otherwise for a file under
`gfx/`. The logo is not under `gfx/`, so it is CC BY-SA 4.0, which is not
compatible with this repository's GPL-3.0-or-later.

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
| `accel.png` | Font Awesome Free 6.5.2 `rocket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `turnleft.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `turnright.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reverse.png` | Font Awesome Free 6.5.2 `arrow-turn-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `face.png` | Font Awesome Free 6.5.2 `location-arrow` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `stealth.png` | Font Awesome Free 6.5.2 `user-secret` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mousefly.png` | Font Awesome Free 6.5.2 `computer-mouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cooldown.png` | Font Awesome Free 6.5.2 `snowflake` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `primary.png` | game-icons.net `lorc/ray-gun` | lorc | CC BY 3.0 |
| `secondary.png` | game-icons.net `lorc/rocket` | lorc | CC BY 3.0 |
| `targetnearest.png` | Material Design Icons `target` | Pictogrammers | Apache-2.0 |
| `targethostile.png` | Material Design Icons `skull-scan` | Pictogrammers | Apache-2.0 |
| `targetclear.png` | Material Design Icons `crosshairs-off` | Pictogrammers | Apache-2.0 |
| `targetnext.png` | Font Awesome Free 6.5.2 `forward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `targetprev.png` | Font Awesome Free 6.5.2 `backward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `escortattack.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `escorthold.png` | Font Awesome Free 6.5.2 `anchor` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `escortreturn.png` | Font Awesome Free 6.5.2 `house` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `escortclear.png` | Font Awesome Free 6.5.2 `eraser` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `targetspob.png` | game-icons.net `lorc/ringed-planet` | lorc | CC BY 3.0 |
| `approach.png` | Font Awesome Free 6.5.2 `plane-arrival` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `targetjump.png` | game-icons.net `delapouite/star-gate` | delapouite | CC BY 3.0 |
| `jump.png` | game-icons.net `lorc/vortex` | lorc | CC BY 3.0 |
| `autonav.png` | Font Awesome Free 6.5.2 `route` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `starmap.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `overlaymap.png` | Font Awesome Free 6.5.2 `map-location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hail.png` | Font Awesome Free 6.5.2 `comments` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autohail.png` | Font Awesome Free 6.5.2 `phone-volume` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scan.png` | game-icons.net `lorc/radar-sweep` | lorc | CC BY 3.0 |
| `logup.png` | Font Awesome Free 6.5.2 `angles-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `logdown.png` | Font Awesome Free 6.5.2 `angles-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `info.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `speed.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `weapset0.png` to `weapset9.png` | game-icons.net `lorc/ray-gun` with the set number, composed by `fetch_icons.py` | lorc | CC BY 3.0 |
| `program.png` | "NAEV" set in Quantico Bold by `fetch_icons.py` | MADType (font) | SIL OFL 1.1 |
