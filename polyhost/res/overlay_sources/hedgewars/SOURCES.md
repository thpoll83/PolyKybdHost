# Hedgewars overlay: sources

`scripts/generate_app_overlays.py` renders `hedgewars.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `hedgewars_template` (1 file) | Hedgewars: the engine `hwengine` (`hwengine.exe` on Windows), the frontend `hedgewars` (`hedgewars.exe`), `org.hedgewars.Hedgewars` as a Flatpak |

A match runs in the engine, a separate program that the frontend starts:
`add_executable(hwengine hwengine.pas)` in `hedgewars/CMakeLists.txt`. The
frontend (menus, team and scheme editors) is `add_executable(hedgewars ...)` in
`QTfrontend/CMakeLists.txt` and the `Exec=` line of
`share/hedgewars/Data/misc/hedgewars.desktop`. The Flatpak id is the `app-id` of
the Flathub manifest (`flathub/org.hedgewars.Hedgewars`, `command: hedgewars`).
The frontend is in the mapping so the keys are shown before a match starts; the
keys act only in the engine. Names not checked on an install.

## Shortcut reference

<https://github.com/hedgewars/hw> (the GitHub mirror of the project's Mercurial
repository), commit `1629043bb4e7529aae3c63aaab2a6b4f2ab9f419` of `master`
(`project(hedgewars VERSION 1.1.0)`, a development version), read 2026-11-14:

- `hedgewars/uInputHandler.pas`, `InitDefaultBinds`: the default key of each
  command, and the Ctrl+W check in `ProcessKey`. In this version
  `SetDefaultBinds` only copies the table that `InitDefaultBinds` fills.
- `QTfrontend/binds.cpp`: the name of each command and the "precise + key"
  combinations.
- `hedgewars/uCommandHandlers.pas`: what a command does while "precise" is held.

No release tag was read. The mirror has tags up to `0.9.23-alpha` only; the
tags of the 1.0 releases are in the Mercurial repository, which was not
reachable (HTTP 401). The key table was therefore not compared with release
1.0.3.

A player changes the keys in the frontend (Settings > Controls, and per team);
this overlay shows the defaults.

"Precise" is the left Shift key by default (`left_shift`, `+precise`). The
game's "precise + key" combinations are drawn on the Shift layer.

| Key | Action (command) |
|---|---|
| Up, Down | Aim up, aim down (`+up`, `+down`) |
| Left, Right | Walk (`+left`, `+right`) |
| Enter | Long jump (`ljump`) |
| Backspace | High jump (`hjump`); pressed twice: backwards jump |
| Tab | Switch hedgehog (`switch`) |
| Shift+Tab | Switch hedgehog backwards |
| Space | Attack: use the selected weapon or utility (`+attack`) |
| F1 to F10 | Select from weapon slot 1 to 10 (`slot 1` ... `slot :`) |
| 1 to 5 | Set the timer of a bomb to 1 to 5 seconds (`timer 1` ... `timer 5`) |
| N | Change the timer (`timer_u`) |
| Shift+1 to 5, Shift+N | Set or change the bounciness instead of the timer |
| H | Automatic camera on or off, find the active hedgehog (`findhh`) |
| T | Chat (`chat`) |
| U | Clan chat (`chat team`) |
| ` | Chat history (`history`) |
| P | Pause / auto skip (`pause`) |
| Y | Confirmation (`confirm`) |
| Ctrl+W | Close the game (`forcequit`); Cmd+W on macOS |
| 9, 0 | Volume down, volume up (`+voldown`, `+volup`) |
| 8 | Mute audio (`mute`) |
| F12 | Toggle full screen (`fullscr`) |
| C | Take a screenshot (`capture`) |
| Shift+C | Save the map as an image |
| F | Speed up a replay (`+speedup`) |
| R | Record video (`record`) |
| M | Show the mission information (`+mission`) |
| O | Show object information (`gearinfo`) |
| Delete | Toggle the team bars (`rotmask`) |
| Home | Toggle the hedgehog tags (`rottags`) |
| Shift+Home | Change the hedgehog tag types |

## Left out

- Escape (`quit`): the key shows the program mark.
- Keypad 8, 4, 6 and 2 (move the cursor or camera): the keypad has no cell.
- The mouse: left button (place, target), right button (ammo menu), wheel
  (zoom), middle button (reset zoom).
- Combinations of three keys: Tab+Home (hedgehog tag translucency) and
  Shift+Tab+Delete (hide the heads-up display). Tab is not a modifier layer.
- Shift with the arrow keys (stand still on slippery land, turn without
  walking) and with 9 and 0 (the volume commands read the "precise" state): the
  plain meaning stays.
- "Unselect weapon" (`setweap ~`): no default key.
- Cmd+W on macOS: the overlay has one set for every OS and shows Ctrl+W.

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge and
uses the full height (40×40), and the firmware clears 3 px around it, so a
letter legend stays whole. On the digit keys the icon erases the shifted
symbol. F1 to F10 all use 30×40, the width that keeps the F4 legend whole, so
the ten slot icons are equal.

All icons are flat 1-bit silhouettes. Solid shapes fill a smaller box in the
bottom-right corner (`INK` in `fetch_icons.py`). Composed by `fetch_icons.py`:

- `aimup.png`, `aimdown.png`: the crosshair at 30 px with an arrow in the
  top-left corner.
- `walkleft.png`: `walkright.png` mirrored.
- `slot1.png` to `slot10.png`: the cartridges with the slot number lit in the
  top-left corner. The weapons in a slot depend on the weapon set, so the icon
  does not show a weapon.
- `timer1.png` to `timer5.png`: the stopwatch, its face filled, with the number
  of seconds cut out of the face.
- `bounce1.png` to `bounce5.png`: the ball at 28 px with the number lit in the
  top-left corner.

ESC shows "Hedge" over "wars" in Lilita One (SIL OFL 1.1,
`ofl/lilitaone/LilitaOne-Regular.ttf` from google/fonts at commit e7db6ca), both
lines at the largest one size at which each fits 70 px wide and both, 1 px
apart, fit 38 px high, drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25).

The game's own logo and art are not used. `README.md` says the source code is
under the GNU General Public Licence version 2 and the images and sounds under
the GNU Free Documentation Licence version 1.2. Neither is on the list of
licences this repository (GPL-3.0-or-later) accepts for art.

## Icons

Licence texts for the icon and font licences named in this file:

- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Where each icon file comes from. The icon table gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`

Material Design Icons are from Templarian/MaterialDesign at commit 2424e74.

| File | Source | Author | Licence |
|---|---|---|---|
| `aimup.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) and Material Design Icons `arrow-up-bold`, composed | Fonticons, Inc.; Pictogrammers | CC BY 4.0; Apache-2.0 |
| `aimdown.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) and Material Design Icons `arrow-down-bold`, composed | Fonticons, Inc.; Pictogrammers | CC BY 4.0; Apache-2.0 |
| `walkleft.png`, `walkright.png` | Font Awesome Free 6.5.2 `person-walking` (solid); left is mirrored | Fonticons, Inc. | CC BY 4.0 |
| `longjump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `highjump.png` | Font Awesome Free 6.5.2 `angles-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `switch.png` | Font Awesome Free 6.5.2 `people-arrows` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `switchback.png` | Material Design Icons `account-arrow-left` | Pictogrammers | Apache-2.0 |
| `attack.png` | Font Awesome Free 6.5.2 `bomb` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `slot1.png` to `slot10.png` | Material Design Icons `ammunition`, number in DejaVu Sans Bold | Pictogrammers; the digits Bitstream | Apache-2.0; the digits Bitstream Vera |
| `timer1.png` to `timer5.png` | Font Awesome Free 6.5.2 `stopwatch` (solid), number in DejaVu Sans Bold | Fonticons, Inc.; the digits Bitstream | CC BY 4.0; the digits Bitstream Vera |
| `changetimer.png` | Material Design Icons `timer-plus` | Pictogrammers | Apache-2.0 |
| `bounce1.png` to `bounce5.png` | Material Design Icons `basketball`, number in DejaVu Sans Bold | Pictogrammers; the digits Bitstream | Apache-2.0; the digits Bitstream Vera |
| `changebounce.png` | Material Design Icons `basketball` | Pictogrammers | Apache-2.0 |
| `findhog.png` | Material Design Icons `account-search` | Pictogrammers | Apache-2.0 |
| `chat.png` | Font Awesome Free 6.5.2 `comment` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clanchat.png` | Font Awesome Free 6.5.2 `comments` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chathistory.png` | Material Design Icons `message-text-clock` | Pictogrammers | Apache-2.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `confirm.png` | Font Awesome Free 6.5.2 `check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closeengine.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `voldown.png` | Font Awesome Free 6.5.2 `volume-low` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `volup.png` | Font Awesome Free 6.5.2 `volume-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mute.png` | Font Awesome Free 6.5.2 `volume-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapimage.png` | Font Awesome Free 6.5.2 `mountain-sun` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `speedup.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `record.png` | Font Awesome Free 6.5.2 `video` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mission.png` | Material Design Icons `clipboard-text` | Pictogrammers | Apache-2.0 |
| `objectinfo.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `teambars.png` | Font Awesome Free 6.5.2 `bars-progress` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hogtags.png` | Material Design Icons `tag-text` | Pictogrammers | Apache-2.0 |
| `tagtypes.png` | Material Design Icons `tag-multiple` | Pictogrammers | Apache-2.0 |
| `program.png` | "Hedge" over "wars" set in Lilita One by `fetch_icons.py` | Juan Montoreano (font) | SIL OFL 1.1 |

The numbers are set in DejaVu Sans Bold (Bitstream Vera licence; the copy
bundled with matplotlib v3.9.2, pinned commit), as in the DevilutionX and
0 A.D. sets.
