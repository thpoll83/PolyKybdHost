# Quake source ports overlay: sources

`scripts/generate_app_overlays.py` renders `quake.yaml`; `fetch_icons.py`
rebuilds `icons/`. The icon catalogue and the drawing code are in
`../gzdoom/fetch_icons.py`.

| Set | Loads for |
|---|---|
| `quake_template` (1 file) | Ironwail (`ironwail`, `ironwail.exe`), vkQuake (`vkquake`, `vkquake.exe`) and QuakeSpasm (`quakespasm`, `quakespasm.exe`) |

`ironwail` is `DEFAULT_TARGET` in `Quake/Makefile` and the `add_executable()`
target in `CMakeLists.txt` of Ironwail v0.8.2. `vkquake` is `DEFAULT_TARGET` in
`Quake/Makefile` and the project name in `meson.build` of vkQuake 1.37.0.
`quakespasm` is `DEFAULT_TARGET` in `Quake/Makefile` of QuakeSpasm 0.97.0. The
names were not checked on an install. Flatpak application ids are not matched,
because none of the three source trees names one.

## Shortcut reference

A Quake engine reads its default bindings from `default.cfg` in the game data.
Each of the three ports ships its own `default.cfg` in a pak file that the
engine adds to its search path beside the game's paks (`COM_AddEnginePak()` in
Ironwail's `Quake/common.c`). This overlay takes the port's file as the one in
effect; the search order was not checked on an install, and a mod with its own
`default.cfg` can replace it. Read on 2026-11-14:

| Port | Repository | Release tag (commit) | File |
|---|---|---|---|
| Ironwail | <https://github.com/andrei-drexler/ironwail> | `v0.8.2` (`1eabd0df21130e55d94496c7af177e2dcbed75df`) | `default.cfg` inside `Quake/ironwail.pak` (the pak's SHA-256 is `be6a546c1b267837d5b6558e9349b1df302a825587b994309b1c955a561292a1`) |
| vkQuake | <https://github.com/Novum/vkQuake> | `1.37.0` (`749b4fd43fe8b8554b34163dc9469c4a08a4def1`) | `Misc/vq_pak/default.cfg` |
| QuakeSpasm | <https://github.com/sezero/quakespasm> | `quakespasm-0.97.0` (`e8795a79273f2823661727265d0617106e282bea`) | `Misc/qs_pak/default.cfg` |

The `bind` lines of the three files are the same, with one exception: Ironwail
also binds Print Screen to `screenshot`. The files differ in the `zoom_in` alias
that F11 runs (`togglezoom` in Ironwail and vkQuake, a series of `fov` commands
in QuakeSpasm) and in default cvars. So one spec serves the three ports.
`Quake/keys.c` of the three ports sets no binding of its own: `Key_SetBinding()`
is called only by the `bind` and `unbind` commands and the key menu.

id Software's original `default.cfg` is part of the game data (`pak0.pak`),
which is not in <https://github.com/id-Software/Quake> (read at commit
`bf4ac424ce754894ac8f1dae6a3981954bc9852d`): that repository's `readme.txt`
says the data files keep their original licence. The original file could not
be read from a source repository and was not used here.

No default binding uses a modifier, so only the plain layer is drawn. A player's
`config.cfg` changes the keys; the overlay shows the defaults.

| Key | Command | Drawn as |
|---|---|---|
| W, Up | `+forward` | move forward |
| S, Down | `+back` | move backward |
| A, `,` | `+moveleft` | strafe left |
| D, `.` | `+moveright` | strafe right |
| Left, Right | `+left`, `+right` | turn left, turn right |
| Space | `+jump` | jump |
| E, C | `+moveup`, `+movedown` | swim up, swim down |
| Page Down, Delete, End | `+lookup`, `+lookdown`, `centerview` | look up, look down, centre view |
| \\ | `+mlook` | mouse look |
| Insert | `+klook` | keyboard look |
| 1 to 8 | `impulse 1` to `impulse 8` | axe, shotgun, double-barrelled shotgun, nailgun, super nailgun, grenade launcher, rocket launcher, thunderbolt |
| / | `impulse 10` | next weapon |
| F1 to F5 | `help`, `menu_save`, `menu_load`, `menu_options`, `menu_multiplayer` | help, save, load, options, multiplayer |
| F6, F9 | `save quick`, `load quick` | quick save, quick load |
| F10, F11, F12 | `quit`, `zoom_in`, `screenshot` | quit, zoom, screenshot |
| Tab | `+showscores` | show scores |
| -, = | `sizedown`, `sizeup` | screen size down, up |
| Pause | `pause` | pause |
| T | `messagemode` | chat |
| ` | `toggleconsole` | console |

The impulse numbers select the weapons of Quake itself. A mission pack or mod
can give them other weapons.

## Left out

- 0 (`impulse 0`): it selects nothing.
- Shift (`+speed`), Ctrl (`+attack`), Alt (`+strafe`): modifier keys have no
  overlay cell.
- Print Screen (`screenshot`): only Ironwail binds it.
- `~` and `+`: the shifted forms of the drawn keys ` and =, bound to the same
  commands.
- F7 and F8: not bound.
- The mouse buttons and wheel, and the gamepad bindings.

## Placement

As for the GZDoom set (`../gzdoom/SOURCES.md`): every icon is a flat 1-bit
silhouette at the right edge, drawn at its key area so the generator places it
1:1. F1 to F9 are 34×40, F10 to F12 30×40, every other key 40×40.

Each weapon key has its own shape from game-icons.net. The nailgun is two
crossed nails and the super nailgun a gun with several barrels. The strokes of
the two shotguns are grown by 1 px. E and C show waves with an arrow up or down
above them, and / shows the pistol with an arrow (`_composed()` in
`../gzdoom/fetch_icons.py`).

## ESC mark

"Quake" set in New Rocker (SIL OFL 1.1, `ofl/newrocker/NewRocker-Regular.ttf`
from google/fonts at commit e7db6ca), at the largest size that fits 70×38,
drawn over the whole cell without the ESC legend (`program_icon_legend: false`,
protocol v25). A pixel is lit from grey 110 of 255.

The ports' own icons are not used: one set serves three ports, so no single
port's icon fits, and the icons were not examined for parts taken from the
Quake logo, which is id Software's. The source code of the three ports is
GPL-2.0-or-later (the file headers say "either version 2 of the License, or (at
your option) any later version"), so the licence would allow an icon that is
the port's own work.

## Icons

Licence texts for the licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png` | Font Awesome Free 6.5.2 `arrow-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `back.png` | Font Awesome Free 6.5.2 `arrow-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `strafeleft.png` | Font Awesome Free 6.5.2 `arrow-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `straferight.png` | Font Awesome Free 6.5.2 `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `turnleft.png` | Font Awesome Free 6.5.2 `reply` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `turnright.png` | Font Awesome Free 6.5.2 `share` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `swimup.png` | Font Awesome Free 6.5.2 `water` and `arrow-up` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `swimdown.png` | Font Awesome Free 6.5.2 `water` and `arrow-down` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `lookup.png` | Font Awesome Free 6.5.2 `angles-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lookdown.png` | Font Awesome Free 6.5.2 `angles-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `centerview.png` | Font Awesome Free 6.5.2 `arrows-to-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mouselook.png` | Font Awesome Free 6.5.2 `computer-mouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `keylook.png` | Font Awesome Free 6.5.2 `keyboard` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `axe.png` | game-icons.net `lorc/wood-axe` | lorc | CC BY 3.0 |
| `shotgun.png` | game-icons.net `skoll/winchester-rifle`, strokes grown by 1 px | skoll | CC BY 3.0 |
| `supershotgun.png` | game-icons.net `delapouite/sawed-off-shotgun`, strokes grown by 1 px | delapouite | CC BY 3.0 |
| `nailgun.png` | game-icons.net `lorc/nails` | lorc | CC BY 3.0 |
| `chaingun.png` | game-icons.net `lorc/minigun` | lorc | CC BY 3.0 |
| `grenade.png` | game-icons.net `lorc/grenade` | lorc | CC BY 3.0 |
| `rocket.png` | game-icons.net `lorc/rocket` | lorc | CC BY 3.0 |
| `thunderbolt.png` | game-icons.net `sbed/electric` | sbed | CC BY 3.0 |
| `nextweapon.png` | game-icons.net `john-colburn/pistol-gun` and Font Awesome Free 6.5.2 `arrow-right` (solid), composed by `fetch_icons.py` | John Colburn; Fonticons, Inc. | CC BY 3.0; CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `multiplayer.png` | Font Awesome Free 6.5.2 `users` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quickload.png` | Font Awesome Free 6.5.2 `folder-open` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoom.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scores.png` | Font Awesome Free 6.5.2 `ranking-star` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sizedown.png` | Font Awesome Free 6.5.2 `down-left-and-up-right-to-center` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sizeup.png` | Font Awesome Free 6.5.2 `up-right-and-down-left-from-center` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | Font Awesome Free 6.5.2 `comment-dots` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "Quake" set in New Rocker by `fetch_icons.py` | Impallari Type (font) | SIL OFL 1.1 |
