# Chocolate Doom, Crispy Doom, DSDA-Doom and Woof! overlays: sources

`scripts/generate_app_overlays.py` renders the four specs in this folder;
`fetch_icons.py` rebuilds the shared `icons/`. The icon catalogue and the
drawing code are in `../gzdoom/fetch_icons.py`.

| Set | Spec | Loads for |
|---|---|---|
| `chocolate_doom_template` (1 file) | `chocolate_doom.yaml` | Chocolate Doom: `chocolate-doom`, `chocolate-doom.exe`, `org.chocolate_doom.Doom` |
| `crispy_doom_template` (1 file) | `crispy_doom.yaml` | Crispy Doom: `crispy-doom`, `crispy-doom.exe`, `io.github.fabiangreffrath.Doom` |
| `dsda_doom_template` (1 file) | `dsda_doom.yaml` | DSDA-Doom: `dsda-doom`, `dsda-doom.exe` |
| `woof_template` (1 file) | `woof.yaml` | Woof!: `woof`, `woof.exe`, `io.github.fabiangreffrath.woof` |

How the names were found (not checked on an install):

- Chocolate Doom and Crispy Doom: the Doom executable is
  `"${PROGRAM_PREFIX}doom"` in `src/CMakeLists.txt`, and `PROGRAM_PREFIX` is the
  lower-case project name without " Doom" plus a hyphen (`CMakeLists.txt`,
  `configure.ac`): `chocolate-doom` and `crispy-doom`. The third name is
  `PACKAGE_RDNS` from `configure.ac` (`org.chocolate_doom`,
  `io.github.fabiangreffrath`) with `.Doom`, the name the desktop file
  `src/Doom.desktop.in` is installed under. The Heretic, Hexen and Strife
  executables of both ports (`chocolate-heretic` and so on) are not matched:
  their keys differ.
- DSDA-Doom: `AddGameExecutable(dsda-doom ...)` in `prboom2/src/CMakeLists.txt`
  and `StartupWMClass=dsda-doom` in `prboom2/ICONS/dsda-doom.desktop`.
- Woof!: `add_executable(woof ...)` in `src/CMakeLists.txt` and the desktop file
  `data/io.github.fabiangreffrath.woof.desktop`.

The four ports do not share one spec because their defaults differ on drawn
keys: Chocolate Doom moves with the arrow keys and strafes with `,` and `.`;
Crispy Doom adds W A S D; DSDA-Doom moves with W A S D and turns with E and Q;
Woof! moves with W A S D and the arrow keys and does not bind `,` and `.`.

No default binding uses a modifier, so every set has only the plain layer. A
player's own configuration changes the keys; the overlays show the defaults.

## Shortcut reference

All four files were read on 2026-11-14.

| Port | Repository | Release tag (commit) | File |
|---|---|---|---|
| Chocolate Doom | <https://github.com/chocolate-doom/chocolate-doom> | `chocolate-doom-3.1.1` (`410d96855b5df5410ff591a90efeafa889119224`) | `src/m_controls.c`: the initial values of the `key_*` variables. `src/m_config.c` binds them to the configuration file |
| Crispy Doom | <https://github.com/fabiangreffrath/crispy-doom> | `crispy-doom-7.2` (`fdeabe4c23a833534b70aa84a22f1685aae7125d`) | `src/m_controls.c` |
| DSDA-Doom | <https://github.com/kraflab/dsda-doom> | `v0.30.1` (`8ed581ad5c868b4dba1c39eb21d29e4ddbed9fad`) | `prboom2/src/m_misc.c`: `input_defs[]`. `prboom2/src/dsda/input.c` and `configuration.c` hold no defaults |
| Woof! | <https://github.com/fabiangreffrath/woof> | `woof_16.0.0` (`4553f9a739d8979a69907c9dab384678902522fa`) | `src/m_input.c`: `default_inputs[]` and `M_InputPredefined()` |

Drawn keys per port. An empty cell means the port does not bind the key, or
binds it to something that is not drawn (see "Left out").

| Key | Chocolate Doom 3.1.1 | Crispy Doom 7.2 | DSDA-Doom 0.30.1 | Woof! 16.0.0 |
|---|---|---|---|---|
| Up, Down | forward, backward | forward, backward | | forward, backward |
| Left, Right | turn left, right | turn left, right | | turn left, right |
| W, S | | forward, backward (`key_alt_up`, `key_alt_down`) | forward, backward | forward, backward |
| A, D | | strafe left, right (`key_alt_strafeleft`, `key_alt_straferight`) | strafe left, right | strafe left, right |
| `,` and `.` | strafe left, right | strafe left, right | | |
| E, Q | | | turn left, turn right | |
| / | | | turn 180 degrees | turn 180 degrees |
| Space | use | use | use | use |
| Caps Lock | | toggle always run | toggle always run | toggle always run |
| \\ | | | toggle mouse look | |
| 1 to 7 | fist and chainsaw, pistol, shotgun and super shotgun, chaingun, rocket launcher, plasma rifle, BFG 9000 | the same | the same | the same |
| 8 | chainsaw | chainsaw | chainsaw | chainsaw |
| 9 | | | super shotgun | super shotgun |
| 0 | automap: show whole map | automap: show whole map | toggle between the two best weapons | toggle between the two best weapons |
| Tab | automap | automap | automap | automap |
| F, G, M, C | automap: follow, grid, set mark, clear marks | the same | the same | the same |
| O, R | | automap: overlay, rotate | automap: overlay, rotate | automap: overlay, rotate |
| H | | | automap: highlight by tag | |
| F1, F2, F3 | help, save, load | the same | the same | the same |
| F4 | sound volume | sound volume | sound volume | sound volume |
| F5 | toggle graphic detail | toggle graphic detail | cycle HUD | cycle HUD |
| F6, F9 | quick save, quick load | the same | the same | the same |
| F7, F8, F10, F11 | end game, toggle messages, quit, gamma correction | the same | the same | the same |
| F12 | view the next player | the same | the same | the same |
| -, = | screen size down, up | the same | the same | the same |
| Pause | pause | pause | pause | pause |
| T | chat (multiplayer) | chat (multiplayer) | | chat (multiplayer) |
| Home, Page Down, Page Up | | | restart level, next level, previous level | |
| Insert, End | | | demo: skip ahead, skip to the end of the level | |

DSDA-Doom's table binds `input_turnleft` to E and `input_turnright` to Q, so
the key on the right turns left. The overlay follows the source.

Other meanings of drawn keys, not drawn:

| Key | Other meaning |
|---|---|
| -, = | automap: zoom out, zoom in |
| arrow keys | automap: pan (follow mode off); menus: move the selection |
| 0 (DSDA-Doom, Woof!) | automap: show the whole map |
| F1 (Woof!) | multiplayer: netgame statistics |
| G, R (Woof!) | chat to player 1 and player 4 while the chat key T is used in a multiplayer game |
| W, S, A, D, E, Q, F, G, H, T, 1 to 9, Space, Delete, arrow keys (DSDA-Doom) | the same letters drive the demo "build mode", which no key enables by default |

## Left out

- Right Ctrl (fire), Right Alt (strafe; jump in DSDA-Doom), Right Shift (run;
  use artifact in DSDA-Doom): modifier keys have no overlay cell.
- The mouse and gamepad bindings, and keys without an overlay cell (DSDA-Doom: `*`
  screenshot, keypad 0 walk camera; Crispy Doom: keypad `+` demo speed).
- `,` and `.` in DSDA-Doom (fly up, fly down) and Chocolate Doom's Page Up,
  Insert, Home, Page Down, Delete, End, `[`, `]`, Enter, Backspace (fly, look,
  inventory): Heretic, Hexen and Strife only.
- Chocolate Doom and Crispy Doom: Y and N (answer a menu question), Enter
  (repeat the last message), Q (stop a demo recording), and the chat destination
  keys G, I, B, R of a multiplayer game.
- Woof!: Enter (message review) and the chat destination keys G, I, B, R.
- The menu navigation keys (arrow keys, Enter, Backspace, Escape, Delete).
- Every action that has no default key (next and previous weapon on the
  keyboard, the cheat keys, rewind, and so on).

## Placement

As for the GZDoom set (`../gzdoom/SOURCES.md`): every icon is a flat 1-bit
silhouette at the right edge, drawn at its key area so the generator places it
1:1. F1 to F9 are 34×40, F10 to F12 30×40, every other key 40×40. The strokes of
the shotgun, the super shotgun and the chainsaw are grown by 1 px.

The weapon keys show generic weapon shapes from game-icons.net. No id Software
artwork (sprites, status bar, logo) is used.

## ESC marks

Each mark is drawn by `fetch_icons.py` from the port's own icon at the release
commit: the icon is box-filtered to fit 40×40 and cut at one grey level
(`MARKS`).

| Port | Icon file | Cut | Licence reasoning |
|---|---|---|---|
| Chocolate Doom | `data/doom.png` (a chocolate bar with a "D") | pixels darker than 140 lit | `data/README` says the icon "may be used under the GNU GPL, so the copyright status of the icon is the same as that of the rest of the project". The source headers say "either version 2 of the License, or (at your option) any later version", so GPL-2.0-or-later |
| DSDA-Doom | `prboom2/ICONS/dsda-doom.png` (a goose) | pixels brighter than 90 lit | The file has no licence of its own, so the project's applies: the source headers say "either version 2 of the License, or (at your option) any later version". The README credits the design to Mal (129thVisplane) |
| Woof! | `data/woof.png` (a "D" beside a dog's head) | pixels brighter than 90 lit | Woof!'s README lists `data/woof.png` as © 2020-2026 Julia Nechaevskaya, CC BY 3.0 |
| Crispy Doom | not used | | `data/doom.png` is a textured "D" in the shape of the Doom logo's letter. The Doom logo is id Software's, so the mark is "Crispy" over "Doom" set in Black Ops One (SIL OFL 1.1, `ofl/blackopsone/BlackOpsOne-Regular.ttf` from google/fonts at commit e7db6ca), drawn over the whole cell without the ESC legend (`program_icon_legend: false`, protocol v25) |

## Icons

Licence texts for the licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- GPL-2.0-or-later: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png` | Font Awesome Free 6.5.2 `arrow-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `back.png` | Font Awesome Free 6.5.2 `arrow-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `strafeleft.png` | Font Awesome Free 6.5.2 `arrow-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `straferight.png` | Font Awesome Free 6.5.2 `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `turnleft.png` | Font Awesome Free 6.5.2 `reply` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `turnright.png` | Font Awesome Free 6.5.2 `share` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reverse.png` | Material Design Icons `arrow-u-down-left-bold` | Pictogrammers | Apache-2.0 |
| `use.png` | Font Awesome Free 6.5.2 `hand-pointer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autorun.png` | Font Awesome Free 6.5.2 `person-running` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mouselook.png` | Font Awesome Free 6.5.2 `computer-mouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fist.png` | game-icons.net `lorc/fist` | lorc | CC BY 3.0 |
| `pistol.png` | game-icons.net `john-colburn/pistol-gun` | John Colburn | CC BY 3.0 |
| `shotgun.png` | game-icons.net `skoll/winchester-rifle`, strokes grown by 1 px | skoll | CC BY 3.0 |
| `supershotgun.png` | game-icons.net `delapouite/sawed-off-shotgun`, strokes grown by 1 px | delapouite | CC BY 3.0 |
| `chaingun.png` | game-icons.net `lorc/minigun` | lorc | CC BY 3.0 |
| `rocket.png` | game-icons.net `lorc/rocket` | lorc | CC BY 3.0 |
| `plasma.png` | game-icons.net `lorc/ray-gun` | lorc | CC BY 3.0 |
| `bfg.png` | game-icons.net `lorc/bolter-gun` | lorc | CC BY 3.0 |
| `chainsaw.png` | game-icons.net `delapouite/chainsaw`, strokes grown by 1 px | delapouite | CC BY 3.0 |
| `weapontoggle.png` | Font Awesome Free 6.5.2 `repeat` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `map.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapfollow.png` | Font Awesome Free 6.5.2 `location-crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapgrid.png` | Font Awesome Free 6.5.2 `table-cells` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapmark.png` | Font Awesome Free 6.5.2 `location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapclear.png` | Font Awesome Free 6.5.2 `eraser` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapmaxzoom.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `maprotate.png` | Font Awesome Free 6.5.2 `compass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapoverlay.png` | Font Awesome Free 6.5.2 `layer-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `maptag.png` | Font Awesome Free 6.5.2 `tag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `volume.png` | Font Awesome Free 6.5.2 `volume-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `detail.png` | Material Design Icons `quality-high` | Pictogrammers | Apache-2.0 |
| `hud.png` | Font Awesome Free 6.5.2 `gauge-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
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
| `chat.png` | Font Awesome Free 6.5.2 `comment-dots` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `restart.png` | Font Awesome Free 6.5.2 `arrow-rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `nextlevel.png` | Font Awesome Free 6.5.2 `forward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `prevlevel.png` | Font Awesome Free 6.5.2 `backward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `demoskip.png` | Font Awesome Free 6.5.2 `forward-fast` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `demoend.png` | Font Awesome Free 6.5.2 `flag-checkered` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | Chocolate Doom's icon, `data/doom.png` at chocolate-doom-3.1.1, cut to 1 bit by `fetch_icons.py` | Chocolate Doom authors | GPL-2.0-or-later |
| `program_dsda.png` | DSDA-Doom's icon, `prboom2/ICONS/dsda-doom.png` at v0.30.1, cut to 1 bit by `fetch_icons.py` | Mal (129thVisplane) | GPL-2.0-or-later |
| `program_woof.png` | Woof!'s icon, `data/woof.png` at woof_16.0.0, cut to 1 bit by `fetch_icons.py` | Julia Nechaevskaya | CC BY 3.0 |
| `program_crispy.png` | "Crispy" over "Doom" set in Black Ops One by `fetch_icons.py` | James Grieshaber, Eben Sorkin (font) | SIL OFL 1.1 |
