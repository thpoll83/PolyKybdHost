# Oolite overlay: sources

`scripts/generate_app_overlays.py` renders `oolite.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `oolite_template` (2 files) | Oolite: `oolite` on Linux and macOS, `oolite.exe` on Windows, `space.oolite.Oolite` as a Flatpak |

`oolite` is `OBJC_PROGRAM_NAME` in `GNUmakefile` and the `StartupWMClass=` of
`installers/FreeDesktop/space.oolite.Oolite.desktop`; the Flatpak id is the
name of that file and of `installers/flatpak/space.oolite.Oolite.yaml`. The
desktop file starts the game through `run_oolite.sh`. Names not checked on an
install.

## Shortcut reference

The `"default"` layout of `Resources/Config/keyconfig2.plist` of
<https://github.com/OoliteProject/oolite>, release tag `1.92.1` (commit
`088f9b3aa27b8849da3489000120fee9b9135237`), read 2026-11-14. The file has 15
more layouts for other keyboard languages (`gbr`, `deu`, `fra` and so on); they
move the punctuation keys and are not drawn. In the file `mod1` is Ctrl
(`isCtrlDown` in `src/Core/Entities/PlayerEntityControls.m`) and a key with
`shift = true` names the shifted character: `_` is Shift+`-`, `*` is Shift+8,
`^` is Shift+6, `|` is Shift+`\`, `:` is Shift+`;`, `+` is Shift+`=`. A player
changes the keys on the game options screen; this overlay shows the defaults.

| Key | In flight | Other meanings (not drawn) |
|---|---|---|
| Left, Right | Roll left, roll right | charts: previous and next system; market: sell and buy one |
| Up, Down | Pitch forward, pitch back | menus: move the selection |
| `,` `.` | Yaw left, yaw right | external view: rotate |
| W, S | Increase, decrease speed | S while docking: docking music |
| I | Inject fuel | charts: system information |
| J | Jump drive | |
| H | Hyperspace | |
| G | Galactic hyperspace | |
| C | Docking computer | |
| Shift+C | Fast docking | |
| Shift+L | Request docking clearance | |
| Shift+M | Mouse control (roll) | |
| Ctrl+Shift+M | Mouse control (yaw) | |
| A | Fire lasers | |
| Shift+`-` | Weapons online or offline | |
| M | Launch missile | |
| Y | Next missile | |
| T | Target missile | |
| U | Unarm missile | |
| Shift+T | Target incoming missile | |
| R | Ident system | |
| Shift+`=`, `-` | Next target, previous target | |
| E | ECM | |
| N | Activate primed equipment | |
| B | Mode of primed equipment | |
| Shift+N, Ctrl+Shift+N | Prime next, previous equipment | |
| 0 | Fast equipment activation A | |
| Tab | Fast equipment activation B | |
| Shift+D | Dump cargo | |
| Shift+R | Rotate cargo | |
| 1 to 4 | Forward, aft, port, starboard view | docked: launch, game options, equip ship, interfaces |
| F1 to F4 | The same views as 1 to 4 | docked: launch, game options, equip ship, interfaces (drawn, see below) |
| 5 or F5 | Status screen | |
| 6 or F6 | Chart screens | |
| 7 or F7 | System data | |
| 8 or F8 | Market screen | |
| V | External view | |
| L, K | Wider, narrower field of view | |
| Z, Shift+Z | Scanner zoom, unzoom | |
| `\`, Shift+`\` | Next, previous compass mode | |
| `;`, Ctrl+`;` | Next, previous content of the selected display (MFD) | |
| Shift+`;`, Ctrl+Shift+`;` | Select the next, previous display (MFD) | |
| Shift+6, Ctrl+Shift+6 | Advanced navigation array: next, previous | |
| O | Toggle HUD | |
| F9 | Toggle bloom | |
| `` ` `` | Comms log | |
| P | Pause | |
| Shift+8 | Snapshot | |
| Shift+F | Show frame rate | |

Each of the keys 1 to 4 and F1 to F4 has two meanings: a view in flight, and a
screen or the launch while docked. Both keys of a pair do the same thing. The
digits show the flight meaning and the F keys show the docked meaning, so that
both are on the keyboard. This is a choice, not a rule of the game.

## Left out

- Escape (launch escape pod): the ESC key shows the program mark.
- Home, End, Page Up and Page Down (chart and system-data screens), Shift+`/`
  (chart highlight, market filter) and `/` (market sorter): they act on one
  screen only.
- The keypad keys (menu arrows, next and previous target, snapshot, market
  sorter): the keypad has no cell.
- The debug keys (`key_debug_*` and `key_dump_*`: D, B, C, X, S, N, 0 and
  Shift+H) and the expansion manager keys (F, I, X): developer and manager
  screens.
- Shift+arrows in the external view (pan), Shift+Left and Shift+Right on the
  market screen (sell and buy all): they act on one screen only.
- The 15 language layouts other than `"default"`.

## Placement

As for Age of Empires II and fheroes2 (`../aoe2/SOURCES.md`): every icon sits
at the right edge and uses the full height, and the firmware clears 3 px around
it, so a letter legend stays whole. F1 to F3 and F5 to F9 are 34×40 and F4 is
30×40, the widths AoE2 measured to keep those legends whole. The digit icons
erase the shifted symbol of their key.

All icons are flat 1-bit silhouettes drawn at their key area. The solid shapes
listed in `INK` in `fetch_icons.py` fill a smaller box in the bottom-right
corner so they do not outweigh the outline icons. The four screens that have a
digit and an F key are drawn twice, once per key area (`F_COPIES`).

Keys that step through a list are composed by `stepped()`: the list's icon at
the bottom of the area and a Font Awesome `right-long` or `left-long` arrow in
the top-right corner. The mouse yaw key has the `left-right` arrow. The two
fast-activation keys are the Font Awesome `bolt` with the letter A or B (DejaVu
Sans Bold, 14 px), composed by `lettered()`.

ESC shows "Oolite" in Righteous (SIL OFL 1.1,
`ofl/righteous/Righteous-Regular.ttf` from google/fonts at commit e7db6ca) at
the largest size at which it fits 70 px wide, drawn over the whole cell without
the ESC legend (`program_icon_legend: false`, protocol v25).

The game's own icon (`installers/win32/Oolite.ico`, a winged emblem with an
"OOLITE" banner) could be used: `LICENSE.md` puts the work under GPL-2.0 "or
(at your option) any later version" and offers the artwork under CC BY-NC-SA
3.0 as a second choice, so the GPL applies. At 40 px and 1 bit the wings stay
as a silhouette and the banner text cannot be read (tested at six thresholds).
The name is drawn instead, because it can be read.

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
- DejaVu fonts licence (the letters A and B): https://dejavu-fonts.github.io/License.html

| File | Source | Author | Licence |
|---|---|---|---|
| `rollleft.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rollright.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pitchforward.png` | Font Awesome Free 6.5.2 `angles-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pitchback.png` | Font Awesome Free 6.5.2 `angles-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `yawleft.png` | Font Awesome Free 6.5.2 `arrow-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `yawright.png` | Font Awesome Free 6.5.2 `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `speedup.png` | Material Design Icons `speedometer` | Pictogrammers | Apache-2.0 |
| `speeddown.png` | Material Design Icons `speedometer-slow` | Pictogrammers | Apache-2.0 |
| `injectfuel.png` | Font Awesome Free 6.5.2 `fire` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jumpdrive.png` | Font Awesome Free 6.5.2 `forward-fast` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hyperspace.png` | game-icons.net `lorc/vortex` | lorc | CC BY 3.0 |
| `galactic.png` | game-icons.net `lorc/star-swirl` | lorc | CC BY 3.0 |
| `autopilot.png` | Font Awesome Free 6.5.2 `robot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fastdock.png` | Font Awesome Free 6.5.2 `plane-arrival` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clearance.png` | Material Design Icons `airport` | Pictogrammers | Apache-2.0 |
| `mouseroll.png` | Font Awesome Free 6.5.2 `computer-mouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lasers.png` | game-icons.net `lorc/ray-gun` | lorc | CC BY 3.0 |
| `weaponsonline.png` | Font Awesome Free 6.5.2 `toggle-on` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `missile.png` | game-icons.net `lorc/rocket` | lorc | CC BY 3.0 |
| `nextmissile.png` | Font Awesome Free 6.5.2 `repeat` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `targetmissile.png` | Font Awesome Free 6.5.2 `location-crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `unarmmissile.png` | Material Design Icons `crosshairs-off` | Pictogrammers | Apache-2.0 |
| `targetincoming.png` | Font Awesome Free 6.5.2 `triangle-exclamation` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ident.png` | Font Awesome Free 6.5.2 `tag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ecm.png` | Font Awesome Free 6.5.2 `tower-broadcast` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `activate.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `equipmode.png` | Font Awesome Free 6.5.2 `sliders` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `dumpcargo.png` | Font Awesome Free 6.5.2 `arrow-up-from-bracket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotatecargo.png` | Font Awesome Free 6.5.2 `boxes-stacked` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `viewforward.png` | Material Design Icons `arrow-up-bold-box-outline` | Pictogrammers | Apache-2.0 |
| `viewaft.png` | Material Design Icons `arrow-down-bold-box-outline` | Pictogrammers | Apache-2.0 |
| `viewport.png` | Material Design Icons `arrow-left-bold-box-outline` | Pictogrammers | Apache-2.0 |
| `viewstarboard.png` | Material Design Icons `arrow-right-bold-box-outline` | Pictogrammers | Apache-2.0 |
| `customview.png` | Font Awesome Free 6.5.2 `video` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fovwider.png` | Material Design Icons `angle-obtuse` | Pictogrammers | Apache-2.0 |
| `fovnarrower.png` | Material Design Icons `angle-acute` | Pictogrammers | Apache-2.0 |
| `scannerzoom.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scannerunzoom.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hud.png` | Material Design Icons `monitor-dashboard` | Pictogrammers | Apache-2.0 |
| `bloom.png` | Font Awesome Free 6.5.2 `sun` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `launch.png` | Font Awesome Free 6.5.2 `plane-departure` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `equipship.png` | Font Awesome Free 6.5.2 `wrench` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `interfaces.png` | Font Awesome Free 6.5.2 `list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `status.png` | Font Awesome Free 6.5.2 `clipboard-list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `charts.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `systemdata.png` | game-icons.net `lorc/ringed-planet` | lorc | CC BY 3.0 |
| `market.png` | Font Awesome Free 6.5.2 `scale-balanced` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `commslog.png` | Font Awesome Free 6.5.2 `comments` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `snapshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fps.png` | Font Awesome Free 6.5.2 `gauge-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fstatus.png`, `fcharts.png`, `fsystemdata.png`, `fmarket.png` | the sources of `status.png`, `charts.png`, `systemdata.png` and `market.png`, drawn at the F-key area | Fonticons, Inc.; lorc (`fsystemdata.png`) | CC BY 4.0; CC BY 3.0 (`fsystemdata.png`) |
| `targetnext.png`, `targetprev.png` | Material Design Icons `target` with a Font Awesome Free 6.5.2 `right-long` or `left-long` arrow, composed by `fetch_icons.py` | Pictogrammers; Fonticons, Inc. | Apache-2.0; CC BY 4.0 |
| `compassnext.png`, `compassprev.png` | Font Awesome Free 6.5.2 `compass` with a `right-long` or `left-long` arrow, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `mfdcyclenext.png`, `mfdcycleprev.png` | Font Awesome Free 6.5.2 `display` with an arrow, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `mfdswitchnext.png`, `mfdswitchprev.png` | Font Awesome Free 6.5.2 `table-columns` with an arrow, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `primenext.png`, `primeprev.png` | Font Awesome Free 6.5.2 `plug` with an arrow, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `navnext.png`, `navprev.png` | Font Awesome Free 6.5.2 `route` with an arrow, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `mouseyaw.png` | Font Awesome Free 6.5.2 `computer-mouse` with a `left-right` arrow, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `fasta.png`, `fastb.png` | Font Awesome Free 6.5.2 `bolt` with the letter A or B, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "Oolite" set in Righteous by `fetch_icons.py` | Astigmatic (font) | SIL OFL 1.1 |
