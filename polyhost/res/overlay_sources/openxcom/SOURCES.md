# OpenXcom overlay: sources

`scripts/generate_app_overlays.py` renders `openxcom.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `openxcom_template` (1 file) | OpenXcom, the free engine for UFO: Enemy Unknown (X-COM: UFO Defense) and X-COM: Terror from the Deep: `openxcom` (Linux, macOS, `OpenXcom.exe` on Windows) and `openxcomex` (the Windows executable of OpenXcom Extended) |

`openxcom` is the executable target in `src/CMakeLists.txt`
(`add_executable ( openxcom ...)`) and the `Exec=` line of
`res/linux/openxcom.desktop`. OpenXcom Extended (MeridianOXC/OpenXcom) builds
the same target name from CMake; its Windows downloads name the executable
`OpenXcomEx.exe`, which was not read from a build file. The engine uses SDL
1.2, which names the X11 window class after the executable. Names not checked
on an install.

## Shortcut reference

The default key options in `src/Engine/Options.cpp` (`keyGeo*`, `keyBattle*`,
`keyInv*`, `keyBaseSelect*` and the general keys) of
<https://github.com/OpenXcom/OpenXcom>, branch `master` at commit
`4a4bae5fa2e5a09282928e84943fc84b093e34ff`, read 2026-11-14. The newest release
tag, `v1.0`, is from 2014; the project distributes nightly builds of `master`
since then, so `master` was read. OpenXcom Extended adds keys of its own, which
were not read. A user who changes a key in the options still sees the default.

No default uses a modifier, so only the plain layer is drawn.

The game has two main screens, the Geoscape (the globe) and the Battlescape (a
mission). Where a key has a meaning on both, the Battlescape meaning is drawn:

| Key | Battlescape (drawn) | Geoscape (not drawn) | Option |
|---|---|---|---|
| Page Up / Page Down | View level above / below | | `keyBattleLevelUp`, `keyBattleLevelDown` |
| Home | Centre on the selected unit | | `keyBattleCenterUnit` |
| Tab | Next unit | Country detail on / off (`keyGeoToggleDetail`) | `keyBattleNextUnit` |
| Left Shift | Previous unit | | `keyBattlePrevUnit` |
| \ | Deselect unit | | `keyBattleDeselectUnit` |
| M | Minimap | | `keyBattleMap` |
| L | Personal lighting on / off | | `keyBattlePersonalLighting` |
| 1 to 9, 0 | Centre on visible enemy 1 to 10 | 1 to 6: time speed (5 seconds to 1 day, `keyGeoSpeed1..6`); in a base, 1 to 8: select base 1 to 8 (`keyBaseSelect1..8`) | `keyBattleCenterEnemy1..10` |
| Q / E | Use left hand / right hand | | `keyBattleUseLeftHand`, `keyBattleUseRightHand` |
| I | Inventory | Intercept (`keyGeoIntercept`) | `keyBattleInventory` |
| S | Unit stats | | `keyBattleStats` |
| K | Kneel / stand | | `keyBattleKneel` |
| R | Reload | Radar ranges on / off (`keyGeoToggleRadar`) | `keyBattleReload` |
| F1 | Reserve no time units | | `keyBattleReserveNone` |
| F2 | Reserve time units for a snap shot | | `keyBattleReserveSnap` |
| F3 | Reserve time units for an aimed shot | | `keyBattleReserveAimed` |
| F4 | Reserve time units for an auto shot | | `keyBattleReserveAuto` |
| J | Reserve time units for kneeling | | `keyBattleReserveKneel` |
| Delete | Expend all time units | | `keyBattleZeroTUs` |
| Backspace | End turn | | `keyBattleEndTurn` |
| A | Abort mission | | `keyBattleAbort` |
| Esc | program mark (Esc opens the options on both screens, and cancels a dialog) | | `keyBattleOptions`, `keyGeoOptions`, `keyCancel` |

Keys with no Battlescape meaning, drawn with the meaning they have:

| Key | Meaning | Screen | Option |
|---|---|---|---|
| C | Create inventory template | soldier inventory | `keyInvCreateTemplate` |
| V | Apply inventory template | soldier inventory | `keyInvApplyTemplate` |
| X | Clear inventory | soldier inventory | `keyInvClear` |
| Z | Auto equip | soldier inventory | `keyInvAutoEquip` |
| B | Bases | Geoscape | `keyGeoBases` |
| G | Graphs | Geoscape | `keyGeoGraphs` |
| U | UFOpaedia | Geoscape | `keyGeoUfopedia` |
| F | Funding | Geoscape | `keyGeoFunding` |
| F5 / F9 | Quick save / quick load | every screen | `keyQuickSave`, `keyQuickLoad` |
| F7 | FPS counter | every screen | `keyFps` |
| F12 | Take screenshot | every screen | `keyScreenshot` |

## Left out

- **The arrow keys** (scroll the Battlescape, rotate the globe): the arrows
  keep their own legends.
- **Enter** (`keyOk`, confirm a dialog): only in dialogs.
- **`+` and `-`** (Geoscape zoom, `keyGeoZoomIn`, `keyGeoZoomOut`): the default
  for zoom in is the key that types `+` without Shift (`SDLK_PLUS`), which a
  US layout does not have, so the pair is not drawn.
- **F10** (`keyBattleVoxelView`, save a voxel view image): a developer tool.
- **Mouse buttons**: no keycap.

## Placement

As for the other game sets (`../aoe2/SOURCES.md`, Placement): every icon sits
at the right edge and uses the full height, and the firmware clears 3 px around
it, so a letter legend stays whole. F1, F2, F5, F7, F9 and Left Shift use a
34×40 area and F4 a 30×40 area. On the digits and `\` the icon erases the
shifted symbol, which the game does not use.

All icons are flat 1-bit silhouettes drawn at the size of their key area, so
the generator places them 1:1. The solid shapes fill a smaller box in the
bottom-right corner (`INK` in `fetch_icons.py`). The digits are a filled disc
with the digit of the key cut out (the 0 key is enemy 10). The two hands carry
an L or an R, because the mirrored hands alone look the same at this size. The
reserve keys show what is reserved: one bullet (snap shot), a crosshair (aimed
shot), three bullets (auto shot), and the kneeling figure with an hourglass.
Quick save and quick load are the disk or the folder with a bolt
(`../openmw/fetch_icons.py`, `bolt_icons()`).

ESC shows the game's own icon, an alien head over an X:
`res/linux/icons/openxcom_128x128.png` at the pinned commit, reduced to 40×40
with a box filter; pixels lighter than luma 90 are lit, so the eyes stay dark.
It sits at the right edge beside the ESC legend. Licence reasoning: the source
headers (for example `src/Engine/Options.cpp`) say "either version 3 of the
License, or (at your option) any later version", the README says the project
is licensed under the GPL, and the icon file has no licence of its own, so it
falls under the project's GPL-3.0-or-later, which is this repository's
licence. The games' own art (UFO: Enemy Unknown, Terror from the Deep) is
proprietary and not used.

## Icons

Licence texts for the icon licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0

Where each icon file comes from. The icon table gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`
- Material Design Icons (`mdi:<name>`): `https://raw.githubusercontent.com/Templarian/MaterialDesign/2424e748e0cc63ab7b9c095a099b9fe239b737c0/svg/<name>.svg`
- GPL-3.0-or-later: https://www.gnu.org/licenses/gpl-3.0.html

| File | Source | Author | Licence |
|---|---|---|---|
| `levelup.png`, `leveldown.png` | Material Design Icons `stairs-up`, `stairs-down` | Pictogrammers | Apache-2.0 |
| `centerunit.png` | Font Awesome Free 6.5.2 `location-crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `nextunit.png`, `prevunit.png` | Material Design Icons `account-arrow-right`, `account-arrow-left` | Pictogrammers | Apache-2.0 |
| `deselect.png` | Material Design Icons `account-off` | Pictogrammers | Apache-2.0 |
| `minimap.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lighting.png` | Font Awesome Free 6.5.2 `lightbulb` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `enemy1.png` .. `enemy10.png` | Font Awesome Free 6.5.2 `circle` (solid), numbered by `fetch_icons.py` (digits in DejaVu Sans Bold) | Fonticons, Inc. | CC BY 4.0 |
| `lefthand.png`, `righthand.png` | Material Design Icons `hand-back-left`, `hand-back-right`, with a letter added by `fetch_icons.py` | Pictogrammers | Apache-2.0 |
| `inventory.png` | game-icons.net `lorc/knapsack` | lorc | CC BY 3.0 |
| `stats.png` | Font Awesome Free 6.5.2 `id-card` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `kneel.png` | Font Awesome Free 6.5.2 `person-praying` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reload.png` | game-icons.net `delapouite/machine-gun-magazine` | delapouite | CC BY 3.0 |
| `reservenone.png` | Font Awesome Free 6.5.2 `ban` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reservesnap.png` | Material Design Icons `bullet` | Pictogrammers | Apache-2.0 |
| `reserveaimed.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reserveauto.png` | Material Design Icons `ammunition` | Pictogrammers | Apache-2.0 |
| `reservekneel.png` | Font Awesome Free 6.5.2 `person-praying` and `hourglass-half` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `zerotus.png` | Font Awesome Free 6.5.2 `battery-empty` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `endturn.png` | Font Awesome Free 6.5.2 `hourglass-end` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `abort.png` | Material Design Icons `exit-run` | Pictogrammers | Apache-2.0 |
| `savetemplate.png`, `applytemplate.png` | Font Awesome Free 6.5.2 `file-export`, `file-import` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clearinventory.png` | Font Awesome Free 6.5.2 `trash-can` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autoequip.png` | Font Awesome Free 6.5.2 `shirt` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `bases.png` | Font Awesome Free 6.5.2 `warehouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `graphs.png` | Font Awesome Free 6.5.2 `chart-line` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ufopaedia.png` | Font Awesome Free 6.5.2 `book` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `funding.png` | Font Awesome Free 6.5.2 `sack-dollar` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` and `bolt` (solid), composed by `../openmw/fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `quickload.png` | Font Awesome Free 6.5.2 `folder-open` and `bolt` (solid), composed by `../openmw/fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `fps.png` | Font Awesome Free 6.5.2 `gauge-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | `res/linux/icons/openxcom_128x128.png` of OpenXcom/OpenXcom at commit 4a4bae5, reduced to 1 bit by `fetch_icons.py` | the OpenXcom developers | GPL-3.0-or-later |
