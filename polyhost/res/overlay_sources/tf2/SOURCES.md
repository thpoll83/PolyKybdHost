# Team Fortress 2 overlay: sources

`scripts/generate_app_overlays.py` renders `tf2.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `tf2_template` (1 file) | Team Fortress 2: `tf_win64.exe` on Windows, `tf_linux64` on Linux, `steam_app_440` under Proton |

The process names are from the Windows and Linux depot manifests in
SteamDatabase/GameTracking-TF2 (`manifest_232251.txt`, `manifest_232253.txt`).
The game has a native Linux build, so Proton is unlikely. None of the names
was checked on an install.

## Shortcut reference

The default bindings Valve ships in `tf/cfg/config_default.cfg`, as mirrored
by SteamDatabase:
<https://raw.githubusercontent.com/SteamDatabase/GameTracking-TF2/910657b9c6fa06cad10855c66d6c3054153ce94e/tf/cfg/config_default.cfg>
(read 2026-11-15). The file binds E twice; the second line (`voicemenu 0 0`,
call for Medic) is the one the game keeps.

## The player's binds

The game writes `tf/cfg/config.cfg` in its install folder when it exits:
`unbindall`, then a `bind "<key>" "<command>"` line for every bound key (the
engine strings `unbindall\n` and `bind "%s" "%s"\n` in
`bin/linux64/engine_strings.txt`). `game_assets/tf2_keys.py` reads that file
from every Steam library, and `build.remap` moves each icon to the key the
player bound its command to. The file lists every bind, so a command with no
line is unbound and its icon is removed. A key bound to several commands with
`;` counts for each of them. Not checked on an install.

## Keys

| Key | Command | Action |
|---|---|---|
| 1 | `slot1` | Primary weapon |
| 2 | `slot2` | Secondary weapon |
| 3 | `slot3` | Melee weapon |
| 4 | `slot4` | Slot 4 (PDA) |
| 5 | `slot5` | Slot 5 (PDA 2) |
| Q | `lastinv` | Last weapon |
| Space | `+jump` | Jump |
| R | `+reload` | Reload |
| F | `+inspect` | Inspect weapon |
| G | `+taunt` | Taunt |
| H | `+use_action_slot_item` | Action item |
| L | `dropitem` | Drop intelligence |
| B | `lastdisguise` | Last disguise |
| - | `disguiseteam` | Disguise team |
| Z | `voice_menu_1` | Voice menu 1 |
| X | `voice_menu_2` | Voice menu 2 |
| C | `voice_menu_3` | Voice menu 3 |
| E | `voicemenu 0 0` | Call for Medic |
| T | `impulse 201` | Spray |
| Y | `say` | All chat |
| U | `say_team` | Team chat |
| P | `say_party` | Party chat |
| V | `+voicerecord` | Voice chat |
| Tab | `+showscores` | Scoreboard |
| . | `changeteam` | Change team |
| , | `changeclass` | Change class |
| M | `open_charinfo_direct` | Loadout |
| N | `open_charinfo_backpack` | Backpack |
| I | `showmapinfo` | Map info |
| J | `cl_trigger_first_notification` | Accept notification |
| K | `cl_decline_first_notification` | Decline notification |
| \` | `toggleconsole` | Console |
| F1 | `+showroundinfo` | Round info |
| F2 | `show_quest_log` | Contracts |
| F5 | `screenshot` | Screenshot |
| F6 | `save_replay` | Save replay |
| F7 | `abuse_report_queue` | Report player |
| F10 | `quit prompt` | Quit |
| Pause | `pause` | Pause |

## Left out

- W, A, S, D (move), Ctrl (`+duck`), Alt (`+strafe`): the letter legend is
  enough for movement, and the modifier keys have no overlay cell.
- 6 to 9 and 0 (`slot6` to `slot10`): they only pick menu entries.
- `'` and `/` (`+moveup`, `+movedown`: swim up and down), Page Up, Page Down,
  End and Insert (`+lookup`, `+lookdown`, `centerview`, `+klook`): keyboard
  look and swim keys few players use.
- F12 (`replay_togglereplaytips`): replay editor tips.
- Esc (`escape`): ESC has the program mark.

## Placement

As for Counter-Strike 2: every icon sits at the right edge of its key and uses
the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F-key icons use 34x40 (the area AoE2 measured for
F-key legends). The solid or wide icons (`INK` in `fetch_icons.py`) are drawn
in a smaller box inside their area. Every icon is drawn at exactly its area by
`game_set.py`, so the generator places it 1:1.

ESC shows TF2 in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). Valve's
logo art is proprietary and is not used.

Z, X and C show the walkie-talkie with the voice menu number 1, 2 or 3 (DejaVu
Sans Bold) in the top-left corner of the icon area.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `primary.png` | game-icons.net `lorc/rocket` | lorc | CC BY 3.0 |
| `secondary.png` | game-icons.net `john-colburn/pistol-gun` | John Colburn | CC BY 3.0 |
| `melee.png` | game-icons.net `sbed/wrench` | sbed | CC BY 3.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `dropitem.png` | game-icons.net `delapouite/briefcase` | delapouite | CC BY 3.0 |
| `disguise.png` | game-icons.net `lorc/domino-mask` | lorc | CC BY 3.0 |
| `voice1.png`, `voice2.png`, `voice3.png` | game-icons.net `delapouite/walkie-talkie` + the number drawn by `game_set.py` (DejaVu Sans Bold) | delapouite | CC BY 3.0 |
| `spray.png` | game-icons.net `lorc/spray` | lorc | CC BY 3.0 |
| `partychat.png` | game-icons.net `delapouite/three-friends` | delapouite | CC BY 3.0 |
| `pda.png`, `lastweapon.png`, `reload.png` | Material Symbols `tablet_android`, `history`, `autorenew` | Google | Apache-2.0 |
| `inspect.png`, `taunt.png`, `actionitem.png` | Material Symbols `visibility`, `celebration`, `redeem` | Google | Apache-2.0 |
| `disguiseteam.png`, `medic.png`, `allchat.png` | Material Symbols `swap_horiz`, `medical_services`, `public` | Google | Apache-2.0 |
| `teamchat.png`, `voice.png`, `scoreboard.png` | Material Symbols `chat`, `mic`, `scoreboard` | Google | Apache-2.0 |
| `changeteam.png`, `changeclass.png`, `loadout.png` | Material Symbols `sync_alt`, `switch_account`, `checkroom` | Google | Apache-2.0 |
| `backpack.png`, `mapinfo.png`, `accept.png` | Material Symbols `backpack`, `map`, `check` | Google | Apache-2.0 |
| `decline.png`, `console.png`, `roundinfo.png` | Material Symbols `close`, `terminal`, `info` | Google | Apache-2.0 |
| `contracts.png`, `screenshot.png`, `savereplay.png` | Material Symbols `assignment`, `screenshot_monitor`, `video_file` | Google | Apache-2.0 |
| `report.png`, `quit.png`, `pause.png` | Material Symbols `report`, `logout`, `pause` | Google | Apache-2.0 |
| `program.png` | drawn by `game_set.py` in Bebas Neue | font: Dharma Type | font: SIL OFL 1.1 |
