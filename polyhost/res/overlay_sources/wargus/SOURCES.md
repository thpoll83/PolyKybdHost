# Wargus overlay: sources

`scripts/generate_app_overlays.py` renders `wargus.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `wargus_template` (2 files) | Wargus (Warcraft II on the Stratagus engine): `stratagus`, `stratagus.exe`, `wargus`, `wargus.exe`, only while the window title contains "Wargus" |

The binary names are the CMake targets `stratagus` (Wargus/stratagus
`CMakeLists.txt`) and `wargus` (Wargus/wargus `CMakeLists.txt`). The `wargus`
launcher starts the engine (`gameheaders/stratagus-game-launcher.h`: `execvp` on
Linux, `CreateProcess` on Windows), so the game window belongs to `stratagus`.
The engine names its window after `SetFullGameName(wargus.Name)` in
`scripts/stratagus.lua`, which is "Wargus" in every shipped translation. The
engine also runs other games (Stargus, War1gus), so the mapping entry requires
that title. The names and the title were not checked on an install. No Flatpak
or Snap ID was found in either repository.

## Shortcut reference

The default bindings in the source of the latest releases, both tagged v3.3.2
(2022-08-10):

- Stratagus v3.3.2 (Wargus/stratagus, commit
  c57ec097b3563de34ef05c84e6b152f5ab5eaea3): `src/ui/interface.cpp`,
  `CommandKey()`, `CommandKey_Group()`, `CommandKey_MapPosition()` and
  `HandleKeyModifiersDown()` (Print Screen).
- Wargus v3.3.2 (Wargus/wargus, commit 420efb4256574ca2afb995ea3badfea542c416ac):
  `scripts/commands.lua`, `HandleIngameCommandKey()`, which the engine calls for
  every key its own `CommandKey()` does not handle. The keystroke list in
  `scripts/menus/help.lua` was compared with both and differs in the places
  listed under "Left out". The group keys are `0123456789` (`GroupKeys` in
  `scripts/stratagus.lua`, the same as the engine default).

A key without Ctrl, Alt or GUI first goes to the button panel
(`HandleKeyDown()`); the global function applies only when no button of the
current selection uses that key. The Wargus buttons use letters, so the digits,
F-keys, Space, Tab, `=`, `-`, `.`, Backspace and Enter keep their global
meaning.

Labelled:

| Keys | Action | Source |
|---|---|---|
| 1 to 0 | Select group | `CommandKey_Group()` |
| Ctrl+digit | Create group | `CommandKey_Group()` |
| Shift+digit | Add the group's units to the selection | `CommandKey_Group()` |
| Ctrl+Shift+digit | Add the selection to the group | `CommandKey_Group()` |
| `.`, Ctrl+I, Alt+I | Select the next idle worker | `CommandKey()` |
| Space | Go to the last event | `CommandKey()` |
| Ctrl+C, Alt+C | Center on the selection | `CommandKey()` |
| Ctrl+T, Alt+T | Track the selected unit on / off | `CommandKey()` |
| F2 to F4 | Go to map position 1 to 3 | `CommandKey_MapPosition()` |
| Shift+F2 to Shift+F4 | Store map position 1 to 3 | `CommandKey_MapPosition()` |
| Ctrl+B, Alt+B | Big map on / off | `CommandKey()` |
| Alt+V, Ctrl+V | Next / previous viewport layout | `CommandKey()` |
| Tab | Minimap terrain on / off | `CommandKey()` |
| `=` and Shift+`=` (`+`) | Game speed faster | `CommandKey()` |
| `-` | Game speed slower | `CommandKey()` |
| Pause, Ctrl+P, Alt+P | Pause | `CommandKey()` |
| Ctrl+F, Alt+F | Full screen on / off | `CommandKey()` |
| Ctrl+G, Alt+G | Grab mouse on / off | `CommandKey()` |
| Ctrl+M | Music on / off | `CommandKey()` |
| Ctrl+S | Sound on / off | `CommandKey()` |
| Ctrl+E | Messages on / off | `CommandKey()` |
| Print Screen | Screenshot | `HandleKeyModifiersDown()` |
| Enter | Write a message | `CommandKey()` |
| F1, Ctrl+H, Alt+H | Help menu | `commands.lua` |
| F5 | Game options | `commands.lua` |
| F6 | Speed options | `commands.lua` |
| F7 | Sound options | `commands.lua` |
| F8 | Preferences | `commands.lua` |
| F9 | Diplomacy | `commands.lua` |
| F10, Backspace | Game menu | `commands.lua` |
| F11 | Save game | `commands.lua` |
| F12, Alt+L | Load game | `commands.lua` |
| Ctrl+R, Alt+R | Restart scenario | `commands.lua` |
| Ctrl+Q, Alt+Q | Quit to the main menu | `commands.lua` |
| Ctrl+X, Alt+X | Exit the game | `commands.lua` |

## Left out

- The letter keys alone. They train, build and give orders through the button
  panel, and what each does depends on the selection. Plain C centers on the
  selection only when no button uses C, so only Ctrl+C and Alt+C are labelled.
- Alt+M (game menu) and Alt+S (save game). `commands.lua` and the help list name
  them, but the engine's `CommandKey()` handles every M and S key itself (Ctrl:
  music, sound; otherwise nothing) and never passes them to the script. F10 and
  F11 work.
- Alt+digit (select only the group's units that a drag box does not select,
  `NON_SELECTABLE_BY_RECTANGLE_ONLY`), Alt+Shift+digit (select the whole group,
  the same as the digit alone) and pressing a digit twice (center on the group).
  The help list calls Alt+digit "add to alternate group"; the code does not do
  that.
- `` ` `` (select nothing): the call is commented out in `CommandKey()`.
- Alt+F10 (debug menu): only in debug builds.
- The keypad `+`, `-` and `*` (default speed): the keyboard has no keypad.
- Arrow keys (scroll the map): the arrows keep their own legends.
- There is no fast-forward key. Fast forward is the `ffw <cycle>` chat command
  in a replay.

## Placement

As for Warcraft III (`../warcraft3/SOURCES.md`): every icon sits at the right
edge and uses the full height, and the firmware clears 3 px around it, so a
letter legend stays whole. The F-key areas use the Age of Empires II legend
widths (`../aoe2/SOURCES.md`) as Warcraft III does: F1 to F3 and F5 to F8
34×40, F4 30×40, F9 to F12 40×40 (F10 to F12 cover the right part of the
legend). The control groups are 48×40, drawn 1:1, 5 px from the right edge.

All icons are flat 1-bit silhouettes. Save, Load, Chat and the bell fill a 34×34
box, Help, Music, Screenshot and Pause a 30×30 box, and the speed arrows a 32×32
box, so the solid shapes do not outweigh the outline icons.

The control groups show one Warcraft II unit per digit, drawn once at full
height: 1 footman, 2 archer, 3 ogre, 4 catapult, 5 mage (hat), 6 demolition
squad (dynamite), 7 goblin zeppelin, 8 ship, 9 dragon, 0 peasant (wood axe).
The game does not tie a group number to a unit type; the icons only suggest a
habit. Ctrl adds a plus (create), Ctrl+Shift a plus in a ring (add the selection
to the group, the Warcraft III mark for that action), and Shift a plus inside
the corners of a selection box (add the group to the selection).

The idle-worker key shows a digging worker with "Zz" in DejaVu Sans Bold (the
font the C&C set downloads, Bitstream Vera licence).

ESC shows WAR over GUS in Germania One (SIL OFL 1.1,
`ofl/germaniaone/GermaniaOne-Regular.ttf` from google/fonts at commit e7db6ca),
drawn over the whole cell without the ESC legend (`program_icon_legend: false`,
protocol v25). A pixel is lit from grey 90 of 255.

## Game art

No art from the game is used. Warcraft II's graphics are Blizzard's and are not
free; Wargus extracts them from the user's own game files. The Wargus repository
(GPL-2.0) has its own launcher icon (`wargus.png`, `wargus.ico`,
`ico_alt.svg`), which could be an ESC mark if its licence is confirmed; no
separate licence for those files was found, and they are not used.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `speedmenu.png` | Font Awesome Free 6.5.2 `gauge-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `soundmenu.png` | Font Awesome Free 6.5.2 `sliders` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `preferences.png` | Font Awesome Free 6.5.2 `user-gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `diplomacy.png` | Font Awesome Free 6.5.2 `handshake-simple` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gamemenu.png` | Font Awesome Free 6.5.2 `bars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `door-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `exit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `restart.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `recallpos.png` | Font Awesome Free 6.5.2 `map-location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `savepos.png` | Font Awesome Free 6.5.2 `thumbtack` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `recallpos30.png` | Font Awesome Free 6.5.2 `map-location-dot` (solid), drawn 30 px wide for F4 | Fonticons, Inc. | CC BY 4.0 |
| `savepos30.png` | Font Awesome Free 6.5.2 `thumbtack` (solid), drawn 30 px wide for Shift+F4 | Fonticons, Inc. | CC BY 4.0 |
| `lastevent.png` | Font Awesome Free 6.5.2 `bell` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `center.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `track.png` | Font Awesome Free 6.5.2 `video` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `bigmap.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `viewport.png` | Font Awesome Free 6.5.2 `table-columns` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `terrain.png` | Font Awesome Free 6.5.2 `mountain-sun` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `faster.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `slower.png` | Font Awesome Free 6.5.2 `backward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `grabmouse.png` | Font Awesome Free 6.5.2 `computer-mouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `music.png` | Font Awesome Free 6.5.2 `music` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sound.png` | Font Awesome Free 6.5.2 `volume-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `messages.png` | Font Awesome Free 6.5.2 `comment-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | Font Awesome Free 6.5.2 `comment` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `idleworker.png` (from `_worker.png`) | Font Awesome Free 6.5.2 `person-digging` (solid), with "Zz" drawn by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `group1.png`, `groupnew1.png`, `groupjoin1.png`, `groupadd1.png` | game-icons.net `cathelineau/swordman` | cathelineau | CC BY 3.0 |
| `group2.png`, `groupnew2.png`, `groupjoin2.png`, `groupadd2.png` | game-icons.net `delapouite/archer` | delapouite | CC BY 3.0 |
| `group3.png`, `groupnew3.png`, `groupjoin3.png`, `groupadd3.png` | game-icons.net `delapouite/ogre` | delapouite | CC BY 3.0 |
| `group4.png`, `groupnew4.png`, `groupjoin4.png`, `groupadd4.png` | game-icons.net `heavenly-dog/catapult` | heavenly-dog | CC BY 3.0 |
| `group5.png`, `groupnew5.png`, `groupjoin5.png`, `groupadd5.png` | game-icons.net `lorc/pointy-hat` | lorc | CC BY 3.0 |
| `group6.png`, `groupnew6.png`, `groupjoin6.png`, `groupadd6.png` | game-icons.net `delapouite/dynamite` | delapouite | CC BY 3.0 |
| `group7.png`, `groupnew7.png`, `groupjoin7.png`, `groupadd7.png` | game-icons.net `skoll/zeppelin` | skoll | CC BY 3.0 |
| `group8.png`, `groupnew8.png`, `groupjoin8.png`, `groupadd8.png` | game-icons.net `lorc/galleon` | lorc | CC BY 3.0 |
| `group9.png`, `groupnew9.png`, `groupjoin9.png`, `groupadd9.png` | game-icons.net `delapouite/spiked-dragon-head` | delapouite | CC BY 3.0 |
| `group0.png`, `groupnew0.png`, `groupjoin0.png`, `groupadd0.png` | game-icons.net `lorc/wood-axe` | lorc | CC BY 3.0 |
| `program.png` | WAR / GUS set in Germania One | John Vargas Beltrán | SIL OFL 1.1 |
