# Command & Conquer Generals and Zero Hour overlay: sources

`scripts/generate_app_overlays.py` renders `generals.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `generals_template` (1 file) | Generals and Zero Hour: `Game.dat` (the host reads `game`), with a window title that starts "Command and Conquer" or "Command & Conquer" and names Generals |

Both games run as `Game.dat`. A log of the Steam release (2026-11-14) showed the
titles "Command and Conquer Generals" (the original) and "Command & Conquer
(TM) Generals Zero Hour". `game` is a name other programs may use too, so the
mapping entry is gated on the title. Not checked under Wine or on the EA app
release.

## Keys

The default hotkeys in `Data\English\CommandMap.ini` of `EnglishZH.big`, the
Steam release of Zero Hour (read 2026-11-14). `Data\INI\CommandMap.ini` in
`INIZH.big` is empty: the game keeps the hotkeys per language. The command-card
letters come from the same archive's `generals.csf`, which marks the hotkey with
`&`: `CONTROLBAR:AttackMove` "&Attack Move", `CONTROLBAR:Guard` "&Guard". Each
binding names its CommandMap command, or the csf label of a command-card
button. The original Generals uses the same keys; that was not checked.

| Key | Command | Action |
|---|---|---|
| 1 to 0 | `SELECT_TEAM<n>` | Select group |
| Ctrl+1 to 0 | `CREATE_TEAM<n>` | Create group |
| Shift+1 to 0 | `ADD_TEAM<n>` | Add the selection to the group |
| Alt+1 to 0 | `VIEW_TEAM<n>` | Centre the view on the group |
| F1 to F8 | `VIEW_VIEW<n>` | Go to saved camera view |
| Ctrl+F1 to F8 | `SAVE_VIEW<n>` | Save camera view |
| A | `CONTROLBAR:AttackMove` | Attack move |
| G | `CONTROLBAR:Guard` | Guard |
| S | `STOP` | Stop |
| E | `SELECT_MATCHING_UNITS` | Select matching units |
| X | `SELECT_ALL` | Select all units |
| H | `VIEW_COMMAND_CENTER` | Go to the command center |
| Ctrl+H | `SELECT_HERO` | Select the hero |
| Space | `VIEW_LAST_RADAR_EVENT` | Go to the last radar event |
| Ctrl+F | `CREATE_FORMATION` | Create a formation |
| F9 | `TOGGLE_CONTROL_BAR` | Show or hide the control bar |
| Enter | `CHAT_EVERYONE` | Chat to everyone |
| Backspace | `CHAT_ALLIES` | Chat to allies |
| Tab | `DIPLOMACY` | Diplomacy |
| Ctrl+B | `PLACE_BEACON` | Place a beacon |
| Delete | `DELETE_BEACON` | Delete a beacon |
| Ctrl+C | `ALL_CHEER` | Cheer |
| F12 | `TAKE_SCREENSHOT` | Screenshot |

## Left out

- The letter keys alone, except attack move, guard and stop. They build,
  train and use abilities, and what each does depends on the selection
  (`generals.csf` gives each button its own letter).
- Ctrl+arrow keys (`SELECT_NEXT_UNIT`, `SELECT_PREV_UNIT`, `SELECT_NEXT_WORKER`,
  `SELECT_PREV_WORKER`): the arrow keys keep their legends.
- The keypad camera keys (rotate, zoom, reset): no overlay cell.
- F (`TOGGLE_FAST_FORWARD_REPLAY`): only in a replay.
- Ctrl, Alt and Shift held (force attack, waypoints, prefer selection):
  modifier keys, which the overlay does not draw.
- Ctrl+Alt+Shift+T and Ctrl+Shift+Backspace: a camera debug toggle and a demo
  quit.
- Esc (`OPTIONS`): ESC has the program mark.

## Placement

As in the C&C and OpenRA sets: every icon sits at the right edge and uses the
full height, and the firmware clears 3 px around it, so a letter legend stays
whole. The control groups are 48×40, 5 px from the right edge, the camera views
30×40. Every icon is drawn like the C&C set (relief, dither, lit outline).

ESC shows GENERALS in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). EA's logo
art is not used.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `group<n>.png`, `groupnew<n>.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | as there |
| `groupadd<n>.png`, `groupjump<n>.png` | the C&C group icon with `dither.with_mark` (ring, sight) | - | as the group icon |
| `view<n>.png`, `viewset<n>.png` | the C&C set's `bookmark.png` with the number (DejaVu Sans Bold), and a plus for Ctrl | see `../cnc_remastered/SOURCES.md` | as there |
| `stop.png`, `guard.png`, `lastevent.png`, `selectall.png`, `commandcenter.png` (`conyard.png`) | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | as there |
| `attackmove.png`, `sametype.png`, `beacon.png`, `screenshot.png`, `chatallies.png` (`teamchat.png`), `chatall.png` (`allchat.png`) | copied from `../openra/icons/` | see `../openra/SOURCES.md` | as there |
| `hero.png` | game-icons.net `lorc/medal` | Lorc | CC BY 3.0 |
| `diplomacy.png` | game-icons.net `delapouite/shaking-hands` | Delapouite | CC BY 3.0 |
| `formation.png`, `deletebeacon.png`, `controlbar.png`, `cheer.png` | Font Awesome Free 6.5.2 `table-cells`, `trash-can`, `table-columns`, `face-laugh-beam` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | GENERALS set in Bebas Neue | Dharma Type | SIL OFL 1.1 |
