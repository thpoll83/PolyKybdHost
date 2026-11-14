# Beyond All Reason overlay: sources

`scripts/generate_app_overlays.py` renders `beyond_all_reason.yaml`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `beyond_all_reason_template` (2 files) | Beyond All Reason: the engine process `spring` on Linux and `spring.exe` on Windows, the launcher `Beyond-All-Reason` (`Beyond-All-Reason.exe`), and `info.beyondallreason.bar` as a Flatpak |

The game runs in the Recoil engine, whose binary keeps the name `spring`
(`spring.exe`). The launcher is a separate program named `Beyond-All-Reason`.
The names come from the task description of this set and from the install paths
in the game's `README.md`; the Flatpak id is the Flathub id as remembered, not
read from a file. Names not checked on an install. Other games on the Recoil or
Spring engine (Zero-K uses its own keys) run in a process of the same name and
get this set too; the host cannot tell them apart by process name.

## Shortcut reference

The "Grid" profile in `common/configs/keybind_defaults.json` of
<https://github.com/beyond-all-reason/Beyond-All-Reason>, commit
`d90b8ad8e4ec8bf7b6774a998ac0607a3e8231f1` (the head of `master`), read
2026-11-14. The repository has no release tags; the game is distributed as a
rolling release. "Grid" is the first of the four shipped profiles (Grid, Grid
60 %, Legacy, Legacy 60 %) and the default.

At this commit 66 actions are no longer in that file (`movedToWidgets`): each
widget declares their default keys in its own `manifest.json`. Two manifests
were read: `luaui/Widgets/camera_fov_changer/manifest.json` (Ctrl+P, Ctrl+O)
and `luaui/Widgets/gui_pip/manifest.json`. The manifests of the squad, factory
preset and select-loop actions were not found by path, so those keys are not
in this set (see "Left out").

The profile names keys by scancode (`sc_a`), so a key is the same physical key
on every layout. `Any+` in the profile means "with any modifier".

| Key | Plain | Ctrl | Alt | Other |
|---|---|---|---|---|
| A | Attack | Area attack | | Ctrl+Alt: switch chat to allies |
| B | (left out) | Self-destruct | Place blueprint | |
| D | Manual fire (D-gun) or manual launch | | | |
| E | Reclaim | Select all units | | |
| F | Fight | | Force start (also sends the vote `!cv forcestart`) | |
| G | Stop, stop production | Toggle factory guard | Factory queue mode | |
| H | Patrol | | | |
| I | Unit statistics | Game information | | |
| J | Load units | | | |
| K | Cloak | | | |
| L | Fire state (1, 2 or 3 presses choose the state) | | | |
| ; | Move state (1, 2 or 3 presses) | | | |
| M | Restore terrain | | | |
| N | Skip the current command | Cancel the last queued command | | |
| O | Guard | Decrease the field of view | Flip the camera | |
| P | Gather and wait | Increase the field of view | | |
| Q | Select the units of the selected types in view | Keep half of the selection | Keep the damaged mobile units (under 60 % health) | |
| R | Repair | Select all idle transports | | |
| S | Set target | Cancel target | Set target, units only | Ctrl+Alt: switch chat to spectators |
| T | Repeat (1 press on, 2 presses off) | | Create blueprint | |
| U | Unload units | | | |
| W | Resurrect, capture (the one the unit has) | Select the units of the selected types on the map | | |
| X | (left out) | | Decrease build spacing | |
| Y | Wait | Select the waiting units in view | Delete blueprint | |
| Z | (left out) | | Increase build spacing | |
| [ ] | Rotate the building to place | | Previous, next blueprint | |
| , . | (left out) | | Decrease, increase attack range | |
| ` | Draw on the map (2 presses: label) | Remove the selection from its group | Remove the unit type from its auto group | |
| Tab | Select the commander and go to it | Select one idle builder | | Shift: add the commander to the selection |
| Enter | Chat | | | |
| Backspace | Mute sound | | | |
| = - | Volume up, down | | Game speed up, down | |
| F1 to F4 | Go to camera anchor 1 to 4 | Set camera anchor 1 to 4 | | |
| F5 | Go to the last message position | | | |
| F6 | Show the path map | | | |
| F7 | Show the metal map | Hide the interface | | |
| F8 | Show the height map | | | |
| F10 | Options | | | |
| F11 | Widget list | | | |
| F12 | Screenshot | | | |
| Page Up, Page Down | Move the camera up, down | | | |
| 0 to 9 | Select group | Set group | Add the unit type to the auto group | Shift: add the group to the selection. Ctrl+Shift: add the selection to the group. Ctrl+Alt: toggle the group in the selection |

The profile binds Shift+key to the same order for 21 order keys (A, D, E, F, G,
H, J, K, L, ;, M, O, P, R, S, T, U, W, Y, [ and ]); with Shift the order is
added to the queue. The Shift layer shows the same icon on those keys, so the
keys do not go blank while Shift is held. As a spectator the digits 1 to 9 show
a team (`specteam`); the player meaning is drawn.

## Left out

- Z, X, C, V without a modifier: they choose a build category with a builder
  selected and a unit with a factory selected (`gridmenu_category`,
  `gridmenu_key`). Q W E R, A S D F and Z X C V also choose a cell of the build
  grid once a category is open. The order meaning of those keys is drawn.
- B: next page of the build grid, on/off and trajectory toggle, by selection.
- `,` and `.` without a modifier (`cycleselected prev` / `next`; `.` also
  `gridmenu_cycle_builder`): what they do was not verified from the source.
- Space: the profile uses it as a modifier (`fakeMeta`: select idle units in
  the box, split a build line, insert a command). The keyboard has no Space
  layer.
- Shift+Alt+digit (load auto group preset): the five group marks are used by
  the other layers, and no further mark was distinct at 13 px.
- Alt+T is bound twice: `blueprint_create` in the profile and `pip1_track` in
  the picture-in-picture manifest. The profile's meaning is drawn. Meta+Tab and
  Meta+Ctrl+Tab (picture-in-picture) need the Space modifier.
- The 61 other actions whose default keys are in widget manifests that were
  not found (squads, factory presets, select loop).
- Esc (clear the selection; Shift+Esc quit menu, Ctrl+Shift+Esc quit,
  Alt+Shift+Esc reload): the ESC key shows the program mark.
- The arrow keys (move the camera) keep their own legends. Pause and the
  keypad camera keys have no cell.
- The text-edit keys of the chat line (Home, End, Ctrl+V and others).

## Placement

As for 0 A.D. and StarCraft II: every icon sits at the right edge and uses the
full height, and the firmware clears 3 px around it, so a letter legend stays
whole. F1 to F9 icons are 34 px wide and F10 to F12 icons 30 px wide. All icons
are flat 1-bit silhouettes drawn at their key area, so the generator places
them 1:1. The solid shapes fill a smaller box (`INK` in `fetch_icons.py`).

The control groups follow the StarCraft II set: one unit picture per digit, 48×40,
5 px from the right edge, with a mark in the corner per modifier from
`polyhost/services/game_assets/dither.py`: a plus (Ctrl, set), a plus in a ring
(Shift, add the group to the selection), a plus in a box (Ctrl+Shift, add the
selection to the group), a plus cut out of a disc (Ctrl+Alt, toggle) and a ring
with four ticks (Alt, auto group). The game does not tie a group number to a
unit type; the pictures only tell the keys apart.

The camera anchors are a location pin with the number cut out of its head, as
the camera positions of the 0 A.D. set; Ctrl (set) moves the pin up and left
and adds a plus.

ESC shows BAR in Audiowide (SIL OFL 1.1, `ofl/audiowide/Audiowide-Regular.ttf`
from google/fonts at commit e7db6ca), at the largest size that fits 70×38 px,
drawn over the whole cell without the ESC legend (`program_icon_legend: false`,
protocol v25).

The game's own logo and icons are not used. `LICENSE.md` of the game puts the
code under GPL v2 and the art under other terms: `license_icons.txt` says
"all rights reserved (CC BY NC ND)" for the icons, the models and textures are
CC BY-NC-ND 4.0 or CC BY-SA 4.0, and other artwork is "all rights reserved"
unless a folder says otherwise. None of these is compatible with
GPL-3.0-or-later.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Where each icon file comes from. The icon table gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`

| File | Source | Author | Licence |
|---|---|---|---|
| `attack.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `manualfire.png` | Font Awesome Free 6.5.2 `bolt` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reclaim.png` | Font Awesome Free 6.5.2 `recycle` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fight.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `stop.png` | Font Awesome Free 6.5.2 `hand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `patrol.png` | Font Awesome Free 6.5.2 `route` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `loadunits.png` | Font Awesome Free 6.5.2 `arrow-right-to-bracket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `unloadunits.png` | Font Awesome Free 6.5.2 `arrow-right-from-bracket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cloak.png` | Font Awesome Free 6.5.2 `ghost` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `firestate.png` | Font Awesome Free 6.5.2 `gun` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `movestate.png` | Font Awesome Free 6.5.2 `shoe-prints` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `restore.png` | Font Awesome Free 6.5.2 `trowel` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `skipcommand.png` | Font Awesome Free 6.5.2 `forward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `guard.png` | Font Awesome Free 6.5.2 `shield-halved` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gatherwait.png` | Font Awesome Free 6.5.2 `people-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `repair.png` | Font Awesome Free 6.5.2 `wrench` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `settarget.png` | Font Awesome Free 6.5.2 `bullseye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `repeat.png` | Font Awesome Free 6.5.2 `repeat` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `resurrect.png` | Font Awesome Free 6.5.2 `heart-pulse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `wait.png` | Font Awesome Free 6.5.2 `hourglass-half` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `facingccw.png` | Font Awesome Free 6.5.2 `arrow-rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `facingcw.png` | Font Awesome Free 6.5.2 `arrow-rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `areaattack.png` | Font Awesome Free 6.5.2 `burst` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `selfdestruct.png` | Font Awesome Free 6.5.2 `bomb` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `canceltarget.png` | Font Awesome Free 6.5.2 `ban` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cancellast.png` | Font Awesome Free 6.5.2 `delete-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `factoryguard.png` | Font Awesome Free 6.5.2 `industry` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `targetunits.png` | Font Awesome Free 6.5.2 `location-crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `queuemode.png` | Font Awesome Free 6.5.2 `list-ol` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `blueprintplace.png` | Font Awesome Free 6.5.2 `stamp` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `blueprintcreate.png` | Font Awesome Free 6.5.2 `pen-ruler` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `blueprintdelete.png` | Font Awesome Free 6.5.2 `trash-can` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `blueprintprev.png` | Font Awesome Free 6.5.2 `angles-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `blueprintnext.png` | Font Awesome Free 6.5.2 `angles-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sametypeview.png` | Font Awesome Free 6.5.2 `clone` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sametypemap.png` | Font Awesome Free 6.5.2 `map-location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `selectall.png` | Font Awesome Free 6.5.2 `earth-europe` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `selecthalf.png` | Font Awesome Free 6.5.2 `circle-half-stroke` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `idletransports.png` | Font Awesome Free 6.5.2 `helicopter` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `waitingunits.png` | Font Awesome Free 6.5.2 `user-clock` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `damaged.png` | Font Awesome Free 6.5.2 `heart-crack` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `commander.png` | Font Awesome Free 6.5.2 `user-astronaut` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `idlebuilder.png` | Font Awesome Free 6.5.2 `helmet-safety` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `groupunset.png` | Font Awesome Free 6.5.2 `users-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autogroupremove.png` | Font Awesome Free 6.5.2 `user-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `unitstats.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gameinfo.png` | Font Awesome Free 6.5.2 `list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lastmessage.png` | game-icons.net `lorc/ringing-bell` | lorc | CC BY 3.0 |
| `pathmap.png` | Font Awesome Free 6.5.2 `road` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `metalmap.png` | Font Awesome Free 6.5.2 `gem` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `heightmap.png` | Font Awesome Free 6.5.2 `mountain` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hideinterface.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `widgets.png` | Font Awesome Free 6.5.2 `list-check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cameraup.png` | Font Awesome Free 6.5.2 `angles-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cameradown.png` | Font Awesome Free 6.5.2 `angles-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cameraflip.png` | Font Awesome Free 6.5.2 `rotate` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `drawinmap.png` | Font Awesome Free 6.5.2 `pencil` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `allychat.png` | game-icons.net `lorc/conversation` | lorc | CC BY 3.0 |
| `specchat.png` | Font Awesome Free 6.5.2 `binoculars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mute.png` | Font Awesome Free 6.5.2 `volume-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `forcestart.png` | Font Awesome Free 6.5.2 `flag-checkered` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `commanderadd.png` | Font Awesome Free 6.5.2 `user-astronaut` (solid) with a plus, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `volumeup.png`, `volumedown.png` | Font Awesome Free 6.5.2 `volume-low` (solid) with a plus or a minus | Fonticons, Inc. | CC BY 4.0 |
| `speedup.png`, `slowdown.png` | Font Awesome Free 6.5.2 `forward` (solid) with a plus or a minus | Fonticons, Inc. | CC BY 4.0 |
| `spacingup.png`, `spacingdown.png` | Font Awesome Free 6.5.2 `arrows-left-right` (solid) with a plus or a minus | Fonticons, Inc. | CC BY 4.0 |
| `rangeup.png`, `rangedown.png` | Font Awesome Free 6.5.2 `ruler` (solid) with a plus or a minus | Fonticons, Inc. | CC BY 4.0 |
| `fovup.png`, `fovdown.png` | Font Awesome Free 6.5.2 `eye` (solid) with a plus or a minus | Fonticons, Inc. | CC BY 4.0 |
| `anchor1.png` to `anchor4.png`, `anchorset1.png` to `anchorset4.png` | Font Awesome Free 6.5.2 `location-dot` (solid) with the number in DejaVu Sans Bold cut out | Fonticons, Inc. (icon); DejaVu fonts, Bitstream Vera licence (digits) | CC BY 4.0 |
| `group1.png` and its 5 marked copies (`groupset1`, `groupselectadd1`, `groupadd1`, `grouptoggle1`, `autogroup1`) | game-icons.net `delapouite/battle-mech` | delapouite | CC BY 3.0 |
| `group2.png` and its 5 marked copies | game-icons.net `lorc/tank` | lorc | CC BY 3.0 |
| `group3.png` and its 5 marked copies | game-icons.net `delapouite/jet-fighter` | delapouite | CC BY 3.0 |
| `group4.png` and its 5 marked copies | game-icons.net `delapouite/submarine` | delapouite | CC BY 3.0 |
| `group5.png` and its 5 marked copies | game-icons.net `delapouite/spider-bot` | delapouite | CC BY 3.0 |
| `group6.png` and its 5 marked copies | game-icons.net `delapouite/missile-launcher` | delapouite | CC BY 3.0 |
| `group7.png` and its 5 marked copies | game-icons.net `delapouite/helicopter` | delapouite | CC BY 3.0 |
| `group8.png` and its 5 marked copies | game-icons.net `delapouite/walking-turret` | delapouite | CC BY 3.0 |
| `group9.png` and its 5 marked copies | game-icons.net `delapouite/mecha-head` | delapouite | CC BY 3.0 |
| `group0.png` and its 5 marked copies | game-icons.net `delapouite/bulldozer` | delapouite | CC BY 3.0 |
| `program.png` | BAR set in Audiowide by `fetch_icons.py` | Astigmatic (font) | SIL OFL 1.1 |
