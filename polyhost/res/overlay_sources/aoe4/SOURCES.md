# Age of Empires IV overlays: sources

`scripts/generate_app_overlays.py` renders `aoe4.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `aoe4_template` (2 files: `.mods.png`, `.combo.mods.png`) | Age of Empires IV and its Anniversary Edition: `reliccardinal` on Windows, `steam_app_1466860` under Proton |

The game runs on Windows only; there is no macOS version. Steam's launch
configuration for app 1466860 names `RelicCardinal.exe` for the default branch
(read through <https://api.steamcmd.net/v1/info/1466860> on 2026-10-30). The
Microsoft Store copy is assumed to use the same name, and `steam_app_1466860`
under Proton follows the AoE2 Definitive Edition entry, which was measured.
Those two names were not checked on an install.

## Shortcut reference

The game has two hotkey layouts: **Grid Keys**, the default on a fresh install,
and **Fully Remappable**, which starts as a copy of Grid Keys. The overlay uses
the Grid Keys defaults. A key the user rebinds in the game keeps its default
icon here.

- <https://support.ageofempires.com/hc/en-us/articles/7473968190356-Fully-Remappable-Keys>
  (Age of Empires support, read 2026-10-30): names Grid Keys as the default
  layout and links the two pages below as "the default hotkeys".
- <https://news.xbox.com/en-us/2021/10/22/age-of-empires-iv-hotkeys-revealed/>
  (Xbox Wire, 2021-10-22, read 2026-10-30): the full table of global keys, in
  two columns, "Hotkey Default" and "Secondary Hotkey". Every binding here is
  from the first column.
- <https://www.ageofempires.com/news/aoeiv-shortcuts-revealed/>
  (ageofempires.com, 2021-10-22, read 2026-10-30): a short list and the
  "Age of Empires IV Hotkeys" sheet, with the Grid build keys (Q, W, E, R
  select an age; Q W E R / A S D F / Z X C build).

The Age of Empires wiki page <https://ageofempires.fandom.com/wiki/Hotkey> has
no Age of Empires IV section (read 2026-10-30), so no wiki source was used.
None of the official pages names a "Classic" hotkey layout; the patch notes
quoted on that wiki use "Classic" only for a command-queue mode.

Where the two official pages differ:

- `.`: the sheet says "Select idle villagers", the Xbox Wire table "Cycle
  through idle economy" (villagers, trade carts, fishing ships, trade ships,
  officials). The label follows the table.
- Backspace: the sheet says "Center your camera", the table "Reset camera"
  (the first press resets the rotation, the second the zoom). The label
  follows the table.
- Shift+digit: the table's text was being changed when it was published. Its
  name reads "[Shift]: Add Group To Selection", then "Changing this to
  '[Shift]: Add Selected Units to Group'", and its description is "Add
  selected units to group". The overlay uses the description.

Control groups: 1 to 0 select a group, Ctrl+digit sets it, Shift+digit adds the
selection. The select and set icons are AoE2's (one unit per digit, drawn
twice); the game does not tie a group number to a unit type.

| Key | Action | Icon |
|---|---|---|
| 1 … 0 | Select group | `group<N>.png` (AoE2) |
| Ctrl+1 … 0 | Set group | `groupnew<N>.png` (AoE2) |
| Shift+1 … 0 | Add the selection to the group | `groupadd<N>.png` |
| F1 | Select all military production buildings | `milbuildings.png` |
| F2 | Select all economy buildings | `ecobuildings.png` |
| F3 | Select all research buildings | `techbuildings.png` |
| F4 | Select all landmarks, wonders and capital Town Centers | `landmarks.png` |
| H | Cycle through Town Centers | `towncenter.png` (AoE2) |
| Ctrl+H | Focus on the capital Town Center | `capital.png` |
| `.` | Cycle through idle economy units | `idlevillager.png` (AoE2) |
| Ctrl+`.` | Select all idle villagers | `allidlevillagers.png` |
| `,` | Cycle through idle military units | `idlemilitary.png` (AoE2) |
| Ctrl+`,` | Select all idle military units | `allidlemilitary.png` |
| `'` | Cycle through monks | `monks.png` |
| `/` | Cycle through scouts | `scouts.png` |
| Ctrl+A | Select all units on screen | `selectscreen.png` |
| Ctrl+Shift+A | Select all units | `allunits.png` |
| Ctrl+Shift+V | Select all villagers | `allvillagers.png` |
| Ctrl+Shift+C | Select all military units | `allmilitary.png` |
| Ctrl+Shift+R | Return all villagers to work (from Seek Shelter) | `backtowork.png` |
| Ctrl+F, W, G, S | Cycle through villagers gathering food, wood, gold, stone | `gatherfood/wood/gold/stone.png` |
| Tab | Cycle through selected units | `subgroup.png` (Warcraft III) |
| Ctrl+Tab | Cycle through selected units, reverse | `subgroupback.png` |
| Delete (hold) | Delete unit or building | `delete.png` |
| F5 | Focus on selected units | `focus.png` |
| Home | Follow selected unit | `follow.png` |
| Backspace | Reset camera | `resetcamera.png` |
| `[` / `]` | Rotate camera 45° counter-clockwise / clockwise | `rotateleft.png` / `rotateright.png` (Warcraft III) |
| Space | Focus on last event | `lastevent.png` (Warcraft III) |
| Enter | Team chat | `chatallies.png` (Warcraft III) |
| Shift+Enter | Global chat | `chatall.png` (Warcraft III) |
| Page Up / Page Down | Scroll chat messages, older / newer | `chatback.png` / `chatfwd.png` (AoE2) |
| F6 | Players and tribute panel | `tribute.png` |
| Insert | Toggle team or unique player colours | `allycolours.png` (AoE2) |
| Ctrl+E | Notify ping (then left click) | `flare.png` (AoE2) |
| Ctrl+R | Attack ping (then left click) | `pingattack.png` |
| Ctrl+T | Defend ping (then left click) | `pingdefend.png` |
| F8 / F9 | Quick save / quick load (single player) | `save.png` / `load.png` (Warcraft III) |
| F10 | Game menu | `gamemenu.png` (Warcraft III) |
| F11 | Toggle game time display | `gametime.png` (AoE2) |
| Pause | Pause simulation (single player) | `pause.png` (AoE2) |
| Esc | Cancel, deselect, game menu (not remappable) | the ESC mark |

## Left out

- The letter keys alone, except H. In the Grid layout they select an age's
  buildings, build, train and give unit commands, and what each does depends
  on the selection. Shift with a production key (queue five units) is left out
  for the same reason.
- Y (open the secondary panel of the selected unit): it acts only on a
  selection, and the panel's content depends on it.
- The arrow keys (pan the camera): the arrows keep their own legends.
- Alt with the mouse (rotate the camera), and the mouse actions.
- The "Secondary Hotkey" column of the Xbox Wire table. As published it binds
  Ctrl+K to two actions (select all units on screen, villagers gathering stone)
  and Ctrl+F to the tribute panel although Ctrl+F is the food key in the first
  column, so it cannot be the set the game ships as written.
- The observer and replay keys (Ctrl+U, Ctrl+C, Ctrl+F, `-`, `=`, Ctrl+`[`,
  Ctrl+`]`): they act only when watching a game, and Ctrl+F is the food key in
  a game you play.

## Placement

As for Age of Empires II (`../aoe2/SOURCES.md`): every icon sits at the right
edge and uses the full height, and the firmware clears 3 px around it, so a
letter legend stays whole. F1, F2, F3, F5 and F6 use 34×40 and F4 30×40, the
legend widths AoE2 and Warcraft III measured. The control groups are 48×40,
drawn 1:1, 5 px from the right edge.

An icon copied from the AoE2 or Warcraft III set is bound with the same area as
there, so its cell is byte-identical to that set's and the keyboard stores it
once. This was checked cell by cell against the generated templates of both
sets. For that reason F8, F9 and F10 keep Warcraft III's 40×40 area (Save and
Load fill a 34×34 box in it, which keeps the F8 and F9 legends whole; the menu
icon covers the right part of the F10 legend, as in Warcraft III), and F11
keeps AoE2's 21×40.

The new icons are flat 1-bit silhouettes drawn at their key area, as in the
Warcraft III set. Follow, Reset camera and Delete are solid shapes and fill a
34×34 box. The composites:

- `allidlevillagers`, `allidlemilitary`, `allvillagers`, `allmilitary`,
  `allunits`: the word IDLE or ALL (Liberation Sans Bold, cap height 9 px) over
  the villager, the crossed swords or a group of people, at 40×40. IDLE marks
  "all idle" on Ctrl, ALL marks "all" on Ctrl+Shift.
- `capital.png`: the village of H with a crown over its top-left corner.
- `pingattack.png`, `pingdefend.png`: the map marker of the notify ping with a
  sword or a shield in its lower right, 2 px clear around it.
- `selectscreen.png`: a group of people inside the four corners of a screen.
- `subgroupback.png`: Tab's cycle arrows mirrored.
- `groupadd<N>.png`: AoE2's group picture with Warcraft III's ringed plus
  (`_with_ring_plus()`), 48×40.

ESC shows AoE2's mark with "IV" in place of "II": "Age", "— of —" and
"Empires" in italic serif over a dotted IV (`program()`, using
`../aoe2/program_mark.py`). The IV is set in Liberation Serif Bold, because
the thin left stroke of the regular V disappears in the dotted pattern. The
fonts are Liberation Serif and Liberation Sans (SIL OFL 1.1, Debian
`fonts-liberation` 1:2.1.5-3). The game's logo art is not used. The mark fills
the whole keycap, so ESC is drawn without its legend
(`program_icon_legend: false`, protocol v25).

`fetch_icons.py` keeps the drawn files (the ESC mark and the composites) when
they exist; `--redraw` draws them again.

## Icons

game-icons.net icons are licensed [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)
and credited to their author; Font Awesome Free 6.5.2 icons (solid) are
licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), by
Fonticons, Inc.

New in this set:

| File | Source | Author | Licence |
|---|---|---|---|
| `milbuildings.png` | game-icons.net `delapouite/medieval-barracks` | Delapouite | CC BY 3.0 |
| `ecobuildings.png` | game-icons.net `delapouite/windmill` | Delapouite | CC BY 3.0 |
| `techbuildings.png` | game-icons.net `lorc/erlenmeyer` | Lorc | CC BY 3.0 |
| `landmarks.png` | game-icons.net `delapouite/greek-temple` | Delapouite | CC BY 3.0 |
| `focus.png` | Font Awesome Free `crosshairs` | Fonticons, Inc. | CC BY 4.0 |
| `tribute.png` | game-icons.net `delapouite/shaking-hands` | Delapouite | CC BY 3.0 |
| `monks.png` | game-icons.net `delapouite/monk-face` | Delapouite | CC BY 3.0 |
| `scouts.png` | game-icons.net `lorc/spyglass` | Lorc | CC BY 3.0 |
| `follow.png` | Font Awesome Free `video` | Fonticons, Inc. | CC BY 4.0 |
| `resetcamera.png` | Font Awesome Free `camera-rotate` | Fonticons, Inc. | CC BY 4.0 |
| `delete.png` | Font Awesome Free `trash-can` | Fonticons, Inc. | CC BY 4.0 |
| `gatherfood.png` | game-icons.net `lorc/wheat` | Lorc | CC BY 3.0 |
| `gatherwood.png` | game-icons.net `delapouite/log` | Delapouite | CC BY 3.0 |
| `gathergold.png` | game-icons.net `willdabeast/gold-bar` | Willdabeast | CC BY 3.0 |
| `gatherstone.png` | game-icons.net `lorc/stone-block` | Lorc | CC BY 3.0 |
| `backtowork.png` | game-icons.net `lorc/hammer-nails` | Lorc | CC BY 3.0 |
| `_village.png` (in `capital.png`) | game-icons.net `delapouite/village` | Delapouite | CC BY 3.0 |
| `_crown.png` (in `capital.png`) | game-icons.net `delapouite/imperial-crown` | Delapouite | CC BY 3.0 |
| `_marker.png` (in the pings) | game-icons.net `delapouite/position-marker` | Delapouite | CC BY 3.0 |
| `_sword.png` (in `pingattack.png`) | game-icons.net `lorc/broadsword` | Lorc | CC BY 3.0 |
| `_shield.png` (in `pingdefend.png`) | game-icons.net `sbed/shield` | Sbed | CC BY 3.0 |
| `_frame.png` (in `selectscreen.png`) | Font Awesome Free `expand` | Fonticons, Inc. | CC BY 4.0 |
| `_people.png` (in `selectscreen.png`, `allunits.png`) | Font Awesome Free `people-group` | Fonticons, Inc. | CC BY 4.0 |
| `_farmer.png` (in `allidlevillagers.png`, `allvillagers.png`) | game-icons.net `delapouite/farmer` | Delapouite | CC BY 3.0 |
| `_swords.png` (in `allidlemilitary.png`, `allmilitary.png`) | game-icons.net `lorc/crossed-swords` | Lorc | CC BY 3.0 |
| `groupadd<N>.png` | AoE2's `group<N>.png` (units credited below) | | CC BY 3.0 |

Copied from the AoE2 set (`../aoe2/icons/`):

| File | Source | Author | Licence |
|---|---|---|---|
| `towncenter.png` | game-icons.net `delapouite/village` | Delapouite | CC BY 3.0 |
| `idlevillager.png` | game-icons.net `delapouite/farmer` | Delapouite | CC BY 3.0 |
| `idlemilitary.png` | game-icons.net `lorc/crossed-swords` | Lorc | CC BY 3.0 |
| `chatback.png`, `chatfwd.png` | game-icons.net `lorc/conversation` and `delapouite/plain-arrow` | Lorc, Delapouite | CC BY 3.0 |
| `allycolours.png` | game-icons.net `delapouite/palette` | Delapouite | CC BY 3.0 |
| `flare.png` | game-icons.net `delapouite/position-marker` | Delapouite | CC BY 3.0 |
| `gametime.png` | game-icons.net `lorc/sands-of-time` | Lorc | CC BY 3.0 |
| `pause.png` | game-icons.net `guard13007/pause-button` | Guard13007 | CC BY 3.0 |
| `group1.png`, `groupnew1.png` | game-icons.net `lorc/spartan` | Lorc | CC BY 3.0 |
| `group2.png`, `groupnew2.png` | game-icons.net `lorc/bowman` | Lorc | CC BY 3.0 |
| `group3.png`, `groupnew3.png` | game-icons.net `delapouite/cavalry` | Delapouite | CC BY 3.0 |
| `group4.png`, `groupnew4.png` | game-icons.net `delapouite/viking-head` | Delapouite | CC BY 3.0 |
| `group5.png`, `groupnew5.png` | game-icons.net `lorc/visored-helm` | Lorc | CC BY 3.0 |
| `group6.png`, `groupnew6.png` | game-icons.net `heavenly-dog/catapult` | HeavenlyDog | CC BY 3.0 |
| `group7.png`, `groupnew7.png` | game-icons.net `delapouite/siege-tower` | Delapouite | CC BY 3.0 |
| `group8.png`, `groupnew8.png` | game-icons.net `delapouite/elephant` | Delapouite | CC BY 3.0 |
| `group9.png`, `groupnew9.png` | game-icons.net `delapouite/drakkar` | Delapouite | CC BY 3.0 |
| `group0.png`, `groupnew0.png` | game-icons.net `delapouite/farmer` | Delapouite | CC BY 3.0 |

Copied from the Warcraft III set (`../warcraft3/icons/`):

| File | Source | Author | Licence |
|---|---|---|---|
| `lastevent.png` | game-icons.net `lorc/ringing-bell` | Lorc | CC BY 3.0 |
| `subgroup.png` (and `subgroupback.png`) | game-icons.net `lorc/cycle` | Lorc | CC BY 3.0 |
| `chatall.png` | game-icons.net `delapouite/megaphone` | Delapouite | CC BY 3.0 |
| `chatallies.png` | game-icons.net `lorc/conversation` | Lorc | CC BY 3.0 |
| `gamemenu.png` | Font Awesome Free `bars` | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free `floppy-disk` | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free `folder-open` | Fonticons, Inc. | CC BY 4.0 |
| `rotateleft.png`, `rotateright.png` | Font Awesome Free `street-view`, with an arrow drawn by Warcraft III's `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
