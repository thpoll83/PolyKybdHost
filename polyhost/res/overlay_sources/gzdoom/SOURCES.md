# GZDoom and UZDoom overlays: sources

`scripts/generate_app_overlays.py` renders `gzdoom.yaml` and `uzdoom.yaml`;
`fetch_icons.py` rebuilds `icons/`. `fetch_icons.py` also holds the icon
catalogue and the helpers the Chocolate Doom and Quake sets use
(`../chocolate_doom`, `../quake`).

| Set | Loads for |
|---|---|
| `gzdoom_template` (1 file) | GZDoom: `gzdoom` on Linux and macOS, `gzdoom.exe` on Windows, `org.zdoom.GZDoom` as a Flatpak |
| `uzdoom_template` (1 file) | UZDoom: `uzdoom` on Linux and macOS, `uzdoom.exe` on Windows, `org.zdoom.UZDoom` as a Flatpak |

`gzdoom` is the value of `ZDOOM_EXE_NAME` in the top-level `CMakeLists.txt` of
GZDoom g4.14.2 (`set( ZDOOM_EXE_NAME "gzdoom" ...)`), and `uzdoom` the same
variable in UZDoom 5.0.3. `org.zdoom.UZDoom` is `APPID` in UZDoom's
`src/version.h`. `org.zdoom.GZDoom` is the Flathub application id; it is not in
the GZDoom source. The names were not checked on an install.

## Shortcut reference

GZDoom: <https://github.com/ZDoom/gzdoom>, release tag `g4.14.2` (commit
`99aa489d09015a95bb78df2b30ede29f328cc874`), read 2026-11-14:

- `wadsrc/static/engine/commonbinds.txt`: the bindings every layout has.
- `wadsrc/static/engine/defbinds.txt`: the default layout (W A S D). The other
  two layouts, `origbinds.txt` (the original Doom keys) and `leftbinds.txt`
  (keypad), are used only when the player selects them.
- The tag has no Doom-specific `defbinds.txt`. The game filters
  `wadsrc/static/filter/game-heretic`, `game-hexen` and `game-strife` add keys
  for those games only.

UZDoom: <https://github.com/UZDoom/UZDoom>, release tag `5.0.3` (commit
`7910df7102033fd7754a317f3254f24101135926`), the same two files, read
2026-11-14. Compared with GZDoom g4.14.2, the keyboard bindings differ in three
lines: UZDoom adds `r +reload` and `ctrl +crouch`, and F11 runs `bumplight`
instead of `bumpgamma`. Ctrl has no overlay cell. So `uzdoom.yaml` is
`gzdoom.yaml` plus R, with another label on F11.

No default binding uses a modifier, so only the plain layer is drawn. A player's
own bindings (the `[Doom.Bindings]` section of the configuration file) change
the keys; the overlay shows the defaults.

The keys are drawn for Doom and Doom II. Heretic, Hexen, Strife and many mods
use other weapons in the same slots.

| Key | Command | Drawn as |
|---|---|---|
| W, S | `+forward`, `+back` | move forward, move backward |
| A, D | `+moveleft`, `+moveright` | strafe left, strafe right |
| Space | `+jump` | jump |
| X | `crouch` | toggle crouch |
| E | `+use` | use |
| R (UZDoom only) | `+reload` | reload weapon |
| Caps Lock | `toggle cl_run` | toggle always run |
| Page Down, Delete, End | `+lookup`, `+lookdown`, `centerview` | look up, look down, centre view |
| 1 to 7 | `slot 1` to `slot 7` | fist and chainsaw, pistol, shotgun and super shotgun, chaingun, rocket launcher, plasma rifle, BFG 9000 |
| Tab | `togglemap` | automap |
| F1 to F5 | `menu_help`, `menu_save`, `menu_load`, `menu_options`, `menu_display` | help, save, load, options, display options |
| F6, F9 | `quicksave`, `quickload` | quick save, quick load |
| F7, F8, F10 | `menu_endgame`, `togglemessages`, `menu_quit` | end game, toggle messages, quit |
| F11 | `bumpgamma` (GZDoom), `bumplight` (UZDoom) | gamma correction, light level |
| F12 | `spynext` | view the next player |
| -, = | `sizedown`, `sizeup` | screen size down, up |
| Pause, Print Screen | `pause`, `screenshot` | pause, screenshot |
| T, \\ | `messagemode`, `+showscores` | chat, show scores |
| ` | `toggleconsole` | console |

Keys that do nothing in the game view, drawn with the meaning they have while
the automap is open (`mapbind` lines):

| Key | Command | Drawn as |
|---|---|---|
| F | `am_togglefollow` | follow the player |
| G | `am_togglegrid` | grid |
| P | `am_toggletexture` | textured automap |
| M | `am_setmark` | set a mark |
| C | `am_clearmarks` | clear the marks |
| 0 | `am_gobig` | show the whole map (in the game view 0 is `slot 0`, which is empty in Doom) |

Other automap meanings, not drawn: - and = zoom the map (drawn: screen size),
the arrow keys pan it.

## Left out

- 8, 9 (`slot 8`, `slot 9`): empty in Doom and Doom II.
- [, ], Enter (`invprev`, `invnext`, `invuse`): Doom has no inventory. They act
  in Heretic, Hexen, Strife and mods.
- Page Up, Insert, Home (`+moveup`, `+movedown`, `land`): they act only while the
  player can fly, which Doom has no item for.
- Shift (`+speed`) and, in UZDoom, Ctrl (`+crouch`): modifier keys have no
  overlay cell.
- The mouse buttons and wheel, and the gamepad bindings.
- The Heretic, Hexen and Strife keys from the game filters.

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge
and uses the full height, and the firmware clears 3 px around it, so a letter
legend stays whole. F1 to F9 are 34×40 and F10 to F12 30×40.

All icons are flat 1-bit silhouettes drawn at their key area, so the generator
places them 1:1. The solid Font Awesome and Material Design shapes fill a
smaller box (32×32 in a 40×40 area) so they do not outweigh the game-icons.net
drawings (`_box()` and `INK` in `fetch_icons.py`). The shotgun's strokes are
grown by 1 px (`BOLD`), because the drawing is too thin at this size. F6 and F9
are the floppy disk and the folder at 26 px with a bolt above the left edge, cut
out by a 2 px gap (`_composed()`).

The weapon keys show generic weapon shapes from game-icons.net. No id Software
artwork (sprites, status bar, logo) is used.

## ESC marks

GZDoom: the letters "GZ" from GZDoom's own icon, `src/win32/icon1.ico` at the
release commit (256 px frame). `fetch_icons.py` crops the frame to the letters
(x 34 to 226, y 62 to 172), box-filters the crop to 40×23 and lights the pixels
brighter than grey 105. The icon file has no licence of its own, so the
project's licence applies: GZDoom's README says "Licensed under the GPL v3" and
`docs/licenses/README.TXT` says the Doom source "has been relicensed under the
GPL v3 for GZDoom". GPL-3.0 is compatible with this repository's
GPL-3.0-or-later.

UZDoom: "UZ" over "Doom" set in Black Ops One (SIL OFL 1.1,
`ofl/blackopsone/BlackOpsOne-Regular.ttf` from google/fonts at commit e7db6ca),
drawn over the whole cell without the ESC legend (`program_icon_legend: false`,
protocol v25). UZDoom's README says its icon is licensed under Creative Commons
BY-SA 4.0, which this repository does not accept, so the icon is not used.

## Icons

Licence texts for the licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- GPL-3.0: https://www.gnu.org/licenses/gpl-3.0.html
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Where each icon file comes from. The icon table gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`
- Material Design Icons (`mdi:<name>`): `https://raw.githubusercontent.com/Templarian/MaterialDesign/2424e748e0cc63ab7b9c095a099b9fe239b737c0/svg/<name>.svg`

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png` | Font Awesome Free 6.5.2 `arrow-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `back.png` | Font Awesome Free 6.5.2 `arrow-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `strafeleft.png` | Font Awesome Free 6.5.2 `arrow-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `straferight.png` | Font Awesome Free 6.5.2 `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `crouch.png` | Material Design Icons `arrow-collapse-down` | Pictogrammers | Apache-2.0 |
| `use.png` | Font Awesome Free 6.5.2 `hand-pointer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reload.png` | Font Awesome Free 6.5.2 `arrows-rotate` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autorun.png` | Font Awesome Free 6.5.2 `person-running` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lookup.png` | Font Awesome Free 6.5.2 `angles-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lookdown.png` | Font Awesome Free 6.5.2 `angles-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `centerview.png` | Font Awesome Free 6.5.2 `arrows-to-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fist.png` | game-icons.net `lorc/fist` | lorc | CC BY 3.0 |
| `pistol.png` | game-icons.net `john-colburn/pistol-gun` | John Colburn | CC BY 3.0 |
| `shotgun.png` | game-icons.net `skoll/winchester-rifle`, strokes grown by 1 px | skoll | CC BY 3.0 |
| `chaingun.png` | game-icons.net `lorc/minigun` | lorc | CC BY 3.0 |
| `rocket.png` | game-icons.net `lorc/rocket` | lorc | CC BY 3.0 |
| `plasma.png` | game-icons.net `lorc/ray-gun` | lorc | CC BY 3.0 |
| `bfg.png` | game-icons.net `lorc/bolter-gun` | lorc | CC BY 3.0 |
| `map.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapfollow.png` | Font Awesome Free 6.5.2 `location-crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapgrid.png` | Font Awesome Free 6.5.2 `table-cells` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `maptexture.png` | Font Awesome Free 6.5.2 `image` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapmark.png` | Font Awesome Free 6.5.2 `location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapclear.png` | Font Awesome Free 6.5.2 `eraser` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapmaxzoom.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `display.png` | Font Awesome Free 6.5.2 `display` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quickload.png` | Font Awesome Free 6.5.2 `folder-open` and `bolt` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `endgame.png` | Font Awesome Free 6.5.2 `circle-stop` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `messages.png` | Font Awesome Free 6.5.2 `comment-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gamma.png` | Font Awesome Free 6.5.2 `sun` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `spy.png` | Font Awesome Free 6.5.2 `eye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sizedown.png` | Font Awesome Free 6.5.2 `down-left-and-up-right-to-center` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sizeup.png` | Font Awesome Free 6.5.2 `up-right-and-down-left-from-center` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | Font Awesome Free 6.5.2 `comment-dots` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scores.png` | Font Awesome Free 6.5.2 `ranking-star` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | the "GZ" of GZDoom's icon, `src/win32/icon1.ico` at g4.14.2, cut to 1 bit by `fetch_icons.py` | ZDoom + GZDoom teams | GPL-3.0 |
| `program_uzdoom.png` | "UZ" over "Doom" set in Black Ops One by `fetch_icons.py` | James Grieshaber, Eben Sorkin (font) | SIL OFL 1.1 |
