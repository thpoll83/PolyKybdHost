# Command & Conquer Remastered Collection overlay: sources

`scripts/generate_app_overlays.py` renders `cnc_remastered.yaml`; `fetch_icons.py`
rebuilds `icons/` (it calls `wz_units.py` for the control groups).

| Set | Loads for |
|---|---|
| `cnc_remastered_template` (1 file) | The Steam release (app 1213210): `ClientG.exe` on Windows, `steam_app_1213210` under Proton |

The app names were not checked on an install. Steam starts the launcher,
`ClientLauncherG.exe`; it starts `ClientG.exe`, the game window the overlay
matches. `steam_app_1213210` is the window class Proton gives every Steam game,
as for Age of Empires II (`steam_app_813780`).

## Shortcut reference

The keys are the Remastered Collection defaults. Tiberian Dawn and Red Alert
share them.

- [defkey.com: Command & Conquer Remastered Collection controls](https://defkey.com/cc-remastered-collection-shortcuts)
  lists every bound key: groups, Tab, Space, H, W/E/R/T, A, Ctrl+A, G, S, X,
  Q (Red Alert only), F1 to F4 and Ctrl+F1 to Ctrl+F4, Alt+Enter.
- The Steam guide [C&C Remastered Basic Tips & Tricks](https://steamcommunity.com/sharedfiles/filedetails/?id=2142348365)
  by Momo lists the same groups, Tab, Space, H, W/E/R/T, A, Ctrl+A, G, S and X.
- The game's GPL source ([electronicarts/CnC_Remastered_Collection](https://github.com/electronicarts/CnC_Remastered_Collection),
  `REDALERT/OPTIONS.CPP`) confirms X, S, G and Q (`KeyQueueMove1`).

Both lists are fan-written. Neither names which tab W, E, R and T select.
The labels follow the sidebar order (structures, infantry, vehicles, special
weapons) and were not checked in the game.

## Left out

- Mouse shortcuts (Ctrl+click force attack, Alt+click force move, Ctrl+Alt+click
  guard a target): they have no key.
- Letters whose action depends on the selection or the game.

## Placement

The firmware draws the legend first, clears 3 px around the overlay's ink, and
then draws the overlay (`copy_overlay_to_buffer()` in the firmware's
`poly_keymap.c`).

| Keys | Area |
|---|---|
| Letters, Space | 40×40 at the right edge |
| Tab, F1 to F4, Alt+Enter | 30×40 at the right edge |
| Digits (control groups) | 48×40 drawn 1:1, 5 px from the right edge (`margin: 5`) |
| ESC | the whole 72×40 cell, without the legend |

On a digit key the firmware draws the Shift symbol (`!`, `@`, `#` ...) in the
top middle. `wz_units.py` puts each unit at the top of its area, so the unit
covers most of that symbol; parts of `@`, `&` and `)` stay visible on 2, 7
and 0. The Ctrl plus for "create group" is in the lower-right corner. On the
bookmark keys the plus is in the upper-right corner, clear of the bookmark's
notch.

ESC shows COMMAND / & / CONQUER, set in Black Ops One and laid out like the
game's title: the second M and the Q are 10 px against 8 px, centred on the
other letters, and a 1 px rule runs on each side of the `&`. The game's own
logo is not used. ESC is drawn without its legend (`program_icon_legend:
false`), which needs firmware with protocol v25. Older firmware draws the mark
over the legend with the 3 px clearance.

## Units (control groups)

The units are 3D models from [Warzone 2100](https://github.com/Warzone2100/warzone2100),
GPL-2.0-or-later (its `COPYING.README`), with textures from
[Warzone2100/data-texpages](https://github.com/Warzone2100/data-texpages)
(same licence). `wz_units.py` fetches them from pinned commits (`WZ_SHA`,
`TEX_SHA`), assembles body, propulsion and weapon as the game does, renders
them with an orthographic camera and a top-front light, and Floyd-Steinberg
dithers the result with a lit 1 px outline.

| Key | Unit | Camera (yaw, pitch) |
|---|---|---|
| 1 | 12 scavenger soldiers (`exbloke`) | 60°, 20° |
| 2 | scavenger trike (`extrike`) | 120°, 25° |
| 3 | pulse laser, medium tracks | 60°, 10° |
| 4 | machine gun, half-tracks | 60°, 25° |
| 5 | heavy cannon, heavy tracks | 60°, 25° |
| 6 | sensor, wheels | 120°, 25° |
| 7 | rail gun, heavy tracks | 20°, 20° |
| 8 | howitzer, heavy tracks | 240°, 20° |
| 9 | rocket array, medium tracks | 120°, 25° |
| 0 | scavenger helicopter (`scavchop`) with the medium rotor | 70°, 65° |

`groupnew<N>.png` adds a 13 px plus with 3 px of black cleared around it.

## Key icons

`fetch_icons.py` renders each SVG at 256 px, then gives it a raised-plate
shading and the same dither and outline as the units, at its exact key area.

| File | Icon | Source and licence |
|---|---|---|
| `tabstructures.png` | factory | [Material Design Icons](https://pictogrammers.com/library/mdi/), Apache-2.0 |
| `tabinfantry.png` | [barracks](https://game-icons.net/1x1/delapouite/barracks.html), mirrored | game-icons.net, Delapouite, CC BY 3.0 |
| `tabvehicles.png` | [battle-tank](https://game-icons.net/1x1/lorc/battle-tank.html) | game-icons.net, Lorc, CC BY 3.0 |
| `tabsuper.png` | [mushroom-cloud](https://game-icons.net/1x1/lorc/mushroom-cloud.html) | game-icons.net, Lorc, CC BY 3.0 |
| `stop.png` | hand | Font Awesome Free 6.5.2, CC BY 4.0 |
| `scatter.png` | arrows-up-down-left-right | Font Awesome Free 6.5.2, CC BY 4.0 |
| `guard.png` | shield-halved | Font Awesome Free 6.5.2, CC BY 4.0 |
| `queuedmove.png` | route | Font Awesome Free 6.5.2, CC BY 4.0 |
| `selectscreen.png` | crosshairs | Font Awesome Free 6.5.2, CC BY 4.0 |
| `selectall.png` | earth-americas | Font Awesome Free 6.5.2, CC BY 4.0 |
| `conyard.png` | helmet-safety | Font Awesome Free 6.5.2, CC BY 4.0 |
| `lastevent.png` | satellite-dish | Font Awesome Free 6.5.2, CC BY 4.0 |
| `bookmark*.png` | bookmark | Font Awesome Free 6.5.2, CC BY 4.0 |
| `graphics.png` | gem | Font Awesome Free 6.5.2, CC BY 4.0 |
| `fullscreen.png` | expand | Font Awesome Free 6.5.2, CC BY 4.0 |

`bookmark<N>.png` cuts the digit out of the bookmark in DejaVu Sans Bold
(Bitstream Vera licence), 11 px high, with a lit 1 px rim. `bookmarkset<N>.png`
adds the plus.

## Fonts

| Font | Used for | Licence |
|---|---|---|
| [Black Ops One](https://github.com/google/fonts/tree/main/ofl/blackopsone) | the ESC mark | SIL OFL 1.1 |
| DejaVu Sans Bold, the copy bundled with matplotlib v3.9.2 (pinned commit) | the bookmark digits | Bitstream Vera |

## Art from the user's game files

When the classic Tiberian Dawn files are on the machine, the host draws 31 keys
of this overlay from the game's own sprites instead
(`polyhost/services/game_assets/cnc_classic.py`). The shipped file above stays
the fallback and is the only C&C art in the repository. EA's sprites are never
shipped: the host reads them from the user's install, writes the patched copy
to the user's cache directory, and sends it only to the keyboard.

| Keys | From the game |
|---|---|
| 1 to 0, Ctrl+1 to Ctrl+0 | map sprites of the chosen faction, with the same plus |
| W, E, R, H, Tab | building sprites |
| S, X, G, A, Q, T | mouse cursors (only when `CCLOCAL.MIX` is present) |

The host looks for `CONQUER.MIX` and `TEMPERAT.MIX` (any case) under
`Data/CNCDATA/TIBERIAN_DAWN/` of a Steam or EA app install of the Remastered
Collection. That path was not checked on an install. The 1995 freeware
release has the same files; point the host at its folder with the setting
below.

| Setting | Default | Meaning |
|---|---|---|
| `game_assets_enabled` | `true` | `false` always sends the shipped file |
| `game_cnc_data_dir` | empty | a folder with the MIX files; empty searches the installs |
| `game_cnc_faction` | `gdi` | `gdi` or `nod` |

`polyctl settings set game_cnc_faction nod` switches the faction; the copy is
rebuilt on a background thread and cached by game file size and time, faction
and `RENDER_VERSION`.
