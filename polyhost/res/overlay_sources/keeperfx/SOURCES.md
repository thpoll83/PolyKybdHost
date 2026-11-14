# KeeperFX overlay: sources

`scripts/generate_app_overlays.py` renders `keeperfx.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `keeperfx_template` (1 file) | KeeperFX, the open source engine for Dungeon Keeper: `keeperfx` and `keeperfx.exe`, and the logging build `keeperfx_hvlog` (`keeperfx_hvlog.exe`) |

`keeperfx` and `keeperfx_hvlog` are the two executable targets in
`CMakeLists.txt` (`add_executable(keeperfx ...)`,
`add_executable(keeperfx_hvlog ...)`). No Flatpak id or macOS bundle was found
in the files read. Names not checked on an install.

## Shortcut reference

`src/front_input.c` of <https://github.com/dkfans/keeperfx>, release tag
`v1.4.0`, read 2026-11-14: the default key table `game_key_settings[]` and the
keys the file reads directly (`is_key_pressed(KC_...)`). The player changes the
table's keys in the game's options; this overlay shows the defaults.

| Key | Plain | Shift | Ctrl | Alt |
|---|---|---|---|---|
| W S A D | Move the camera (the arrow keys too) | | | W: workshop. S: scavenger room. A: annoyed creature |
| Delete | Rotate the camera clockwise | | | |
| Page Down | Rotate the camera counterclockwise | Tilt the camera down | | |
| Page Up | | Tilt the camera up | | |
| Insert | | Reset the camera tilt | | |
| Home, End | Zoom in, out | | | |
| T | Go to the treasure room | Training room | Temple | Torture chamber |
| L | Library | Lair | | |
| G | Graveyard | Guard post | | |
| B | Barracks | Bridge | | |
| H | Dungeon heart | Hatchery | | |
| P | Pause | Prison | Portal | |
| F | Go to a fight | | | Toggle hero health flowers |
| Q | Query a creature while held | | | |
| Backspace | Undo pickup | | | |
| M | Map | Record the screen | | |
| C | | Screenshot | | |
| X, Z | Ascend, descend (possessed creature) | | | X: exit the game |
| R | | | | Switch screen resolution |
| ; | Teleport to the last work room (possessed creature) | | | |
| / | Teleport to the call to arms (possessed creature) | | | |
| , | Teleport to the default place (possessed creature) | | | |
| 1 to 5 | Panel tabs: information, rooms, spells, traps and doors, creatures | Go to bookmark 1 to 5 | Store bookmark 1 to 5 | |
| Enter | Write a message | | | |
| Space | Finish the level (after the level is won) | | | |
| Tab | | | Toggle the interface | |
| F8 | Toggle tooltips | | | |
| ` | Toggle console | | | |
| = - | | | Frame skip up, down | |
| F1 to F8 | | | Send quick message 1 to 8 | |

The table binds frame skip to the keypad plus and minus with Ctrl;
`is_game_key_pressed()` also accepts Ctrl+= and Ctrl+- ("hardcoded alternative
keys"), and those are drawn.

Other meanings, not drawn:

| Key | Other meaning |
|---|---|
| 1 to 0 | with a creature possessed: use ability 1 to 10 |
| Q | with a creature possessed: previous ability (E: next ability) |
| F | with a creature possessed: teleport to a fight |
| Alt+T | also "disable packet mode" (`Gkey_DisablePacketMode`), which acts only while a recorded game plays |

## Left out

- E (`ToggleMessage`): its dungeon view use was not found in the file read;
  with a creature possessed it selects the next ability.
- Left Shift (speed while moving the camera, creature control, best room
  size), Left Ctrl (rotate, square room) and Left Alt (sell a trap): modifiers.
- Keypad plus and minus (minimap zoom) and the other keypad keys: no cell.
- The arrow keys (move the camera) keep their own legends.
- F12, Shift+Enter and keypad Enter (cheat menus), Ctrl+F9 to F11 (land view),
  Alt+D (debug report), `.` (frame step in a debug mode): developer and cheat
  keys, hidden in the game's own key list (`BMV_Hidden`) or behind a debug flag.
- X and Z are drawn from their name in the table (`Ascend`, `Descend`); the
  code that reads them is not in `src/front_input.c` and was not read.

## Placement

As for 0 A.D. and fheroes2: every icon sits at the right edge and uses the full
height, and the firmware clears 3 px around it, so a letter legend stays whole.
All icons are flat 1-bit silhouettes drawn at their key area, so the generator
places them 1:1. The solid shapes fill a smaller box (`INK` in
`fetch_icons.py`). The bookmarks are a location pin with the number cut out;
Ctrl (store) moves the pin up and left and adds a plus. The quick messages are
a speech bubble with the number cut out.

ESC shows "Keeper" over "FX" in Almendra Bold (SIL OFL 1.1,
`ofl/almendra/Almendra-Bold.ttf` from google/fonts at commit e7db6ca), both
lines at the largest one size that fits 70×38 px, drawn over the whole cell
without the ESC legend (`program_icon_legend: false`, protocol v25).

The engine's source files say "either version 2 of the License, or (at your
option) any later version" (the header of `src/front_input.c`), so its own
files would be compatible. Its icon (`res/keeperfx_icon*.png`) is not used: it
shows Dungeon Keeper artwork, and the game's art comes from the original
Dungeon Keeper data, which is proprietary. Room and creature pictures are
therefore taken from the icon sets, not from the game.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `moveup.png` | Font Awesome Free 6.5.2 `arrow-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `movedown.png` | Font Awesome Free 6.5.2 `arrow-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `moveleft.png` | Font Awesome Free 6.5.2 `arrow-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `moveright.png` | Font Awesome Free 6.5.2 `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotatecw.png` | Font Awesome Free 6.5.2 `arrow-rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotateccw.png` | Font Awesome Free 6.5.2 `arrow-rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tiltup.png` | Font Awesome Free 6.5.2 `angle-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tiltdown.png` | Font Awesome Free 6.5.2 `angle-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tiltreset.png` | Font Awesome Free 6.5.2 `compass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `treasure.png` | Font Awesome Free 6.5.2 `coins` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `library.png` | Font Awesome Free 6.5.2 `book` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lair.png` | Font Awesome Free 6.5.2 `bed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `prison.png` | Font Awesome Free 6.5.2 `dungeon` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `torture.png` | Font Awesome Free 6.5.2 `handcuffs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `training.png` | Font Awesome Free 6.5.2 `dumbbell` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `heart.png` | Font Awesome Free 6.5.2 `heart` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `workshop.png` | game-icons.net `lorc/anvil` | lorc | CC BY 3.0 |
| `scavenger.png` | Font Awesome Free 6.5.2 `eye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `temple.png` | Font Awesome Free 6.5.2 `place-of-worship` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `graveyard.png` | Font Awesome Free 6.5.2 `cross` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `barracks.png` | game-icons.net `delapouite/barracks` | delapouite | CC BY 3.0 |
| `hatchery.png` | game-icons.net `delapouite/chicken` | delapouite | CC BY 3.0 |
| `guardpost.png` | Font Awesome Free 6.5.2 `flag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `bridge.png` | Font Awesome Free 6.5.2 `bridge` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `portal.png` | Font Awesome Free 6.5.2 `door-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fight.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `annoyed.png` | Font Awesome Free 6.5.2 `face-angry` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tabinfo.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tabrooms.png` | Font Awesome Free 6.5.2 `table-cells-large` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tabspells.png` | Font Awesome Free 6.5.2 `wand-magic-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tabworkshop.png` | Font Awesome Free 6.5.2 `door-closed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tabcreatures.png` | Font Awesome Free 6.5.2 `spider` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `query.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `undopickup.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ascend.png` | Font Awesome Free 6.5.2 `angles-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `descend.png` | Font Awesome Free 6.5.2 `angles-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `teleportwork.png` | Font Awesome Free 6.5.2 `briefcase` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `teleportarms.png` | Font Awesome Free 6.5.2 `bullhorn` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `teleportlair.png` | Font Awesome Free 6.5.2 `house` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `map.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `finishlevel.png` | Font Awesome Free 6.5.2 `flag-checkered` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tooltips.png` | Font Awesome Free 6.5.2 `comment-dots` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `togglegui.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `record.png` | Font Awesome Free 6.5.2 `video` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `resolution.png` | Font Awesome Free 6.5.2 `display` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `healthflowers.png` | Font Awesome Free 6.5.2 `heart-pulse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `exit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `frameskipup.png`, `frameskipdown.png` | Font Awesome Free 6.5.2 `forward` (solid) with a plus or a minus, composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `bookmark1.png` to `bookmark5.png`, `bookmarkset1.png` to `bookmarkset5.png` | Font Awesome Free 6.5.2 `location-dot` (solid) with the number in DejaVu Sans Bold cut out | Fonticons, Inc. (icon); DejaVu fonts, Bitstream Vera licence (digits) | CC BY 4.0 |
| `message1.png` to `message8.png` | Font Awesome Free 6.5.2 `comment` (solid) with the number in DejaVu Sans Bold cut out | Fonticons, Inc. (icon); DejaVu fonts, Bitstream Vera licence (digits) | CC BY 4.0 |
| `program.png` | "Keeper" over "FX" set in Almendra Bold by `fetch_icons.py` | Ana Sanfelippo (font) | SIL OFL 1.1 |
