# Warzone 2100 overlay: sources

`scripts/generate_app_overlays.py` renders `warzone2100.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `warzone2100_template` (1 file) | Warzone 2100: `warzone2100` on Linux, `warzone2100.exe` on Windows, "Warzone 2100" on macOS, `steam_app_1241950` under Proton |

The binary name is the `OUTPUT_NAME` of the `warzone2100` target in
`src/CMakeLists.txt` at tag 4.7.0 (`"Warzone 2100"` for the macOS bundle). The
window names were not checked on an install.

## Shortcut reference

The default key map of Warzone 2100 4.7.0 (the latest 4.x release), from
`initializeKeyFunctions()` in `src/input/keyconfig.cpp` of
<https://github.com/Warzone2100/warzone2100>, tag `4.7.0` (commit 7d3d8e5).
The game lists the same table under Options → Key Mappings, where the user can
change it; this overlay shows the defaults. The game binds the left Ctrl, Shift
and Alt keys.

Every function in that table does the same thing whatever is selected, so the
letter keys are labelled too: they give an order to the selected units
(C, E, F, G, H, I, O, P, Q, R, S, T, U, `,` `.` `/`) or select units by type
(Ctrl, Shift and Alt with a letter). The game builds and trains through the
reticule screens on F1 to F6, not through letter keys.

| Keys | Function |
|---|---|
| F1 to F6 | Manufacture, Research, Build, Design, Intelligence display, Commanders |
| F7, F8 | Quick save, quick load; with Shift: toggle the radar, toggle the console display |
| F9, F10, F11 | Toggle damage bars, take a screenshot, toggle formation speed limiting |
| F12 | View the location of the previous message; with Shift: toggle the sensor display |
| 1 to 0 | Select group; Ctrl assigns the group, Shift adds the selection to it, Alt selects commander N |
| Backspace, Space | Snap the view to north, toggle the tracking camera |
| Ctrl+Up/Down/Left/Right | View north, south, east, west (Left is east and Right is west in the table) |
| Ctrl+`-`, Ctrl+`=`, Ctrl+Backspace | Decrease, increase and reset the game speed |
| `-`, `=` | Zoom the radar out and in (only with the mouse over the radar) |
| Tab | Toggle overlays; with Ctrl: radar terrain, with Shift: ally-enemy radar view (both over the radar) |
| `` ` `` | Toggle the console history; with Ctrl: the team chat history |
| Enter | Send a global message; Ctrl: team message, Shift: team quick chat, Alt: toggle fullscreen |
| M | Show all keyboard mappings |
| B, D | Center the view on the HQ, view unassigned units |
| C, E, F | Hold fire, return fire, fire at will |
| G, H, Shift+H | Guard position, hold position, return to HQ |
| O, I, U | Short, optimum and long range |
| P, Q, R, S, T | Pursue, patrol, return for repair, stop, go to transport |
| Ctrl+R | Return for recycling |
| `,` `.` `/` | Retreat at medium damage, retreat at heavy damage, do or die |
| Alt+H, Alt+S, Alt+T | Drop a beacon, toggle shadows, trap the cursor |
| Ctrl+A, C, D, F, H, S, T, U, V, W, Z | Select all: combat units, cyborgs, heavily damaged units, half-tracks, hovers, units on screen, tracks, every unit, VTOLs, wheels, units with the same components |
| Shift+C, E, G, M, P, R, S, T, V | Select all: combat cyborgs, engineers, land combat units, mechanics, transporters, repair tanks, sensor units, trucks, fully-armed VTOLs |
| Alt+C, D, F, G, J, V | The same selections, only units without a group: combat cyborgs, tracks, half-tracks, land combat units, sensor units, fully-armed VTOLs |

## Left out

- The keypad keys: camera zoom (`+` `-`), rotation and pitch (2, 4, 5, 6, 8),
  the orders menu (0), the next oil derrick (`*`) and the multiplayer menu
  (Enter). The keyboard has no keypad.
- The arrow keys alone (move the camera): the arrows keep their own legends.
- The functions with no default key (the next factory, research
  facility or power generator, the next truck or commander, building rotation,
  global quick chat, "remove from current group").
- The debug functions (`HIDDEN`, in the debug contexts: Ctrl+Y, Ctrl+M,
  Ctrl+E, Ctrl+G, Ctrl+O and others, Alt+A, Alt+K, Alt+L): they work only after
  Shift+Backspace switches the debug key map on, and that switch is left out
  too. Alt+Enter (toggle fullscreen) is also `HIDDEN`, but it works at any
  time, so it is labelled.
- Pause: the game has a pause function, but the key map gives it no key.
- ESC (in-game options): it shows the program mark.

## Placement

As for Warcraft III (`../warcraft3/SOURCES.md`): every icon sits at the right
edge and uses the full height, and the firmware clears 3 px around it, so a
letter legend stays whole. The F-key areas use AoE2's measured legend widths:
F1 to F3 and F5 to F9 34×40, F4 30×40. F10 to F12 are 40×40 and cover the right
part of the legend, as in Warcraft III. The control groups and the commanders
are 48×40, drawn 1:1, 5 px from the right edge. Shift+H (return to HQ) is
46×40: the HQ with an arrow pointing into it from the left.

Most keys were picked in the icon picker (`picker.yaml`, see
`tools/ICON_PICKER.md`) from Warzone's own art, dithered with the settings
picked there (next section). The other icons are flat 1-bit silhouettes. Solid shapes (save, load, the chat
bubbles, the skull, the broken heart, the screen, the speed and playback
buttons, shadows, the mouse) fill a 30×30 or 34×34 box, so they do not
outweigh the outline icons.

- The control groups show one Warzone unit per digit (the ten of the C&C set:
  scavenger infantry, trike, pulse laser tank, half-track, heavy cannon tank,
  sensor, rail gun tank, howitzer, rocket array, helicopter). The game does not
  tie a group to a unit type; the pictures only tell the digits apart. Ctrl
  adds a plus, Shift a plus in a ring, as in Warcraft III. Alt+digit (select
  commander N) shows the command turret tank, as F6.
- The Alt selections ("without group") add a struck-through ring in the
  bottom-right corner to the Shift or Ctrl icon of the same units.
- `-` and `=` (radar zoom) are the radar of Shift+F7 with a minus or a plus.
- Backspace and Ctrl+arrows show the compass letter in a ring.

ESC shows WARZONE over a larger 2100 in Orbitron Black (SIL OFL 1.1, the `wght`
900 instance of `ofl/orbitron/Orbitron[wght].ttf` from google/fonts at commit
e7db6ca), drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25). The game's logo is not used.

## The game's own art

Warzone 2100's data is GPL-2.0-or-later (`COPYING.README` in its repository),
except the files listed in its `COPYING.NONGPL`. The host is GPL-3.0-or-later
and can take the GPL files. `fetch_icons.py` fetches everything from pinned
commits: the interface images from Warzone2100/warzone2100 at
`e115b6379c1b831d12980f00f877c1e72e599c68` (`data/base/images/intfac/`), the models from the same
commit and their textures from Warzone2100/data-texpages at
`009ec2f652a6230d8315cc3db4eadb5690f18fbd`.

- Interface images (`intfac:` in `pictures.yaml`): the reticule buttons for F1
  to F5 and the unit order buttons. Which button belongs to which order is
  from `src/intorder.cpp` (for example `range3` is optimum range, `repair3` do
  or die).
- Units (`model:`): body, propulsion and turret assembled as the game does,
  drawn by `../cnc_remastered/wz_units.py`; `wz_models.py` lists them.
  `prm[lr]whl1.pie` (CC BY-SA 3.0) is not used; the plain `prmwhl1.pie` is GPL.
- ⚠️ **The weapon texture `page-17-droid-weapons.png` is CC BY-SA 3.0**
  (Mysteryem, 2009; `COPYING.NONGPL` of Warzone2100/data-texpages). It colours
  the turrets of the rendered units, here and in the C&C set. Whether it may
  ship in a GPL-3.0-or-later program (through CC BY-SA 4.0, which CC declared
  one-way compatible with GPLv3) is the maintainer's call; drawing the turrets
  untextured removes it.

`pictures.yaml` and `rasterize.yaml` are written by `tools/apply_icon_picks.py`
from the picks; `fetch_icons.py` renders them with `game_assets/picture.py`,
the picker page's own renderer, and the palette `icon_picker_sources.Warzone2100`
builds from the `palette_from` list of `picker.yaml`. Changing that list changes
every picked interface image.

## Icons

Licence texts for the icon and font licences named in this file:

- GPL-2.0: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
- CC BY-SA 3.0: https://creativecommons.org/licenses/by-sa/3.0/
- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quickload.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `damagebars.png` | Font Awesome Free 6.5.2 `bars-progress` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `formationspeed.png` | game-icons.net `delapouite/speedometer` | delapouite | CC BY 3.0 |
| `lastmessage.png` | game-icons.net `lorc/ringing-bell` | lorc | CC BY 3.0 |
| `radar.png`, `_radar.png`, `_radar40.png`, `radarzoomin.png`, `radarzoomout.png` | game-icons.net `lorc/radar-sweep`, with a mark drawn by `fetch_icons.py` | lorc | CC BY 3.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sensordisplay.png` | Font Awesome Free 6.5.2 `satellite-dish` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `trackcamera.png` | Font Awesome Free 6.5.2 `video` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `overlays.png` | Font Awesome Free 6.5.2 `layer-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `consolehistory.png` | Font Awesome Free 6.5.2 `clock-rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `teamchathistory.png` | Font Awesome Free 6.5.2 `comments` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `slowdown.png` | Font Awesome Free 6.5.2 `backward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `speedup.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `normalspeed.png` | Font Awesome Free 6.5.2 `play` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `radarterrain.png` | Font Awesome Free 6.5.2 `mountain` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `radarallies.png` | Font Awesome Free 6.5.2 `people-arrows` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `shadows.png` | Font Awesome Free 6.5.2 `circle-half-stroke` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `trapcursor.png` | Font Awesome Free 6.5.2 `computer-mouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mappings.png` | Font Awesome Free 6.5.2 `keyboard` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `centrehq.png` | Font Awesome Free 6.5.2 `building-flag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `unassigned.png` | Font Awesome Free 6.5.2 `person-circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `guard.png` | Font Awesome Free 6.5.2 `shield-halved` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `patrol.png` | Font Awesome Free 6.5.2 `arrow-right-arrow-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `stop.png` | Font Awesome Free 6.5.2 `hand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `transport.png` | Font Awesome Free 6.5.2 `plane-arrival` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `recycle.png` | Font Awesome Free 6.5.2 `recycle` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `beacon.png` | Font Awesome Free 6.5.2 `location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cyborgs.png` | game-icons.net `delapouite/cyborg-face` | delapouite | CC BY 3.0 |
| `combatcyborgs.png`, `combatcyborgs_nogroup.png` | game-icons.net `delapouite/battle-mech`, with a mark drawn by `fetch_icons.py` | delapouite | CC BY 3.0 |
| `engineers.png` | Font Awesome Free 6.5.2 `helmet-safety` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mechanics.png` | Font Awesome Free 6.5.2 `screwdriver-wrench` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `damaged.png` | Font Awesome Free 6.5.2 `heart-crack` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `onscreen.png` | Font Awesome Free 6.5.2 `display` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `everyunit.png` | Font Awesome Free 6.5.2 `earth-europe` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `samecomponents.png` | Font Awesome Free 6.5.2 `clone` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `teamchat.png` | game-icons.net `lorc/conversation` | lorc | CC BY 3.0 |
| `quickchat.png` | Font Awesome Free 6.5.2 `comment-dots` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `north.png`, `south.png`, `east.png`, `west.png` | a ring and a DejaVu Sans Bold letter, drawn by `fetch_icons.py` (the font from matplotlib, commit a254b68) | DejaVu fonts | Bitstream Vera licence (free) |
| `program.png` | WARZONE and 2100 in Orbitron Black, drawn by `fetch_icons.py` | Matt McInerney (Orbitron) | SIL OFL 1.1 |

Picked in the icon picker (`pictures.yaml`, `rasterize.yaml`):

| File | Source | Author | Licence |
|---|---|---|---|
| `manufacture.png` | Warzone 2100 interface image `image_manufacture_up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `research.png` | Warzone 2100 interface image `image_research_up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `build.png` | Warzone 2100 interface image `image_build_up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `design.png` | Warzone 2100 interface image `image_design_up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `intelligence.png` | Warzone 2100 interface image `image_intelmap_up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `commanders.png` | Warzone 2100 unit: Command turret (`commander`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `group1.png`, `groupnew1.png`, `groupadd1.png` | Warzone 2100 unit: Infantry crowd (12 scavenger soldiers) (`group1`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `group2.png`, `groupnew2.png`, `groupadd2.png` | Warzone 2100 unit: Scavenger trike (`group2`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `group3.png`, `groupnew3.png`, `groupadd3.png` | Warzone 2100 unit: Pulse laser tank (`group3`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `group4.png`, `groupnew4.png`, `groupadd4.png` | Warzone 2100 unit: Half-track, machine gun (`group4`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `group5.png`, `groupnew5.png`, `groupadd5.png` | Warzone 2100 unit: Heavy tank, cannon (`group5`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `group6.png`, `groupnew6.png`, `groupadd6.png` | Warzone 2100 unit: Sensor (`group6`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `group7.png`, `groupnew7.png`, `groupadd7.png` | Warzone 2100 unit: Rail gun tank (`group7`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `group8.png`, `groupnew8.png`, `groupadd8.png` | Warzone 2100 unit: Howitzer (`group8`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `group9.png`, `groupnew9.png`, `groupadd9.png` | Warzone 2100 unit: Rocket array (`group9`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `group0.png`, `groupnew0.png`, `groupadd0.png` | Warzone 2100 unit: Scavenger helicopter (`group0`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `commander.png` | Warzone 2100 unit: Command turret (`commander`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `holdfire.png` | Warzone 2100 interface image `image_ord_holdfireup.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `returnfire.png` | Warzone 2100 interface image `image_ord_retfireup.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `fireatwill.png` | Warzone 2100 interface image `image_ord_fatwillup.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `hold.png` | Warzone 2100 interface image `image_ord_haltup.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `pursue.png` | Warzone 2100 interface image `image_ord_pursueup.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `returnhq.png` | Warzone 2100 interface image `image_ord_gotohqup.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `repair.png` | Warzone 2100 interface image `image_ord_rtrup.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `rangeoptimum.png` | Warzone 2100 interface image `image_ord_range3up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `rangeshort.png` | Warzone 2100 interface image `image_ord_range1up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `rangelong.png` | Warzone 2100 interface image `image_ord_range2up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `retreatmedium.png` | Warzone 2100 interface image `image_ord_repair2up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `retreatheavy.png` | Warzone 2100 interface image `image_ord_repair1up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `doordie.png` | Warzone 2100 interface image `image_ord_repair3up.png`, dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `vtols.png` | Warzone 2100 unit: VTOL, lancer (`vtols`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `hovers.png` | Warzone 2100 unit: Hover, machine gun (`hovers`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `tracks.png`, `tracks_nogroup.png` | Warzone 2100 unit: Tracks, machine gun (`tracks`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `halftracks.png`, `halftracks_nogroup.png` | Warzone 2100 unit: Half-tracks, machine gun (`halftracks`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `wheels.png` | Warzone 2100 unit: Wheels, machine gun (`wheels`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `combat.png` | Warzone 2100 unit: Heavy tank, cannon (`group5`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `landcombat.png`, `landcombat_nogroup.png` | Warzone 2100 unit: Heavy tank, cannon (land combat) (`heavytank`, camera yaw,pitch 45,40), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `transporters.png` | Warzone 2100 unit: Transport (`transporters`, camera yaw,pitch 30,10), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `repairtanks.png` | Warzone 2100 unit: Repair turret (`repairtanks`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `sensors.png`, `sensors_nogroup.png` | Warzone 2100 unit: Sensor turret (`sensors`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `trucks.png` | Warzone 2100 unit: Truck (`trucks`), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later |
| `armedvtols.png`, `armedvtols_nogroup.png` | Warzone 2100 unit: VTOL, lancer (`vtols`, camera yaw,pitch 60,45), dithered as picked | Warzone 2100 developers | GPL-2.0-or-later; weapon texture CC BY-SA 3.0 |
| `guard.png` | `fa:shield-halved`, re-rasterized as picked (credited in the table above) | | |
| `patrol.png` | `fa:arrow-right-arrow-left`, re-rasterized as picked (credited in the table above) | | |
| `recycle.png` | `fa:recycle`, re-rasterized as picked (credited in the table above) | | |
| `transport.png` | `fa:plane-arrival`, re-rasterized as picked (credited in the table above) | | |
| `stop.png` | `fa:hand`, re-rasterized as picked (credited in the table above) | | |
| `cyborgs.png` | `gi:delapouite/cyborg-face`, re-rasterized as picked (credited in the table above) | | |
| `combatcyborgs.png` | `gi:delapouite/battle-mech`, re-rasterized as picked (credited in the table above) | | |
