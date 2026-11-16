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
| 4 | `slot4` | PDA 1 (build, disguise) |
| 5 | `slot5` | PDA 2 (destroy, watch) |
| Q | `lastinv` | Last weapon |
| W | `+forward` | Move forward |
| A | `+moveleft` | Move left |
| S | `+back` | Move back |
| D | `+moveright` | Move right |
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

- Ctrl (`+duck`), Alt (`+strafe`): the modifier keys have no overlay cell.
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

ESC shows the wordmark TEAM over FORTRESS 2 in Anton, with a round emblem
after TEAM, as the logo has an emblem between its words. It is drawn by
`program()` in `fetch_icons.py`
(Anton: SIL OFL 1.1, `ofl/anton/Anton-Regular.ttf` from google/fonts at commit e7db6ca). It covers
the whole cell and is drawn without the ESC legend (`program_icon_legend:
false`, protocol v25). It was compared by eye with the game's logo; Valve's
logo art is proprietary and is not used or committed.

Z, X and C show the walkie-talkie with the voice menu number 1, 2 or 3, and 4
and 5 the PDA with 1 or 2 (DejaVu Sans Bold), in the top-left corner of the
icon area, so no two actions share a picture.

## Icons

Each icon is drawn at keycap size by `fetch_icons.py` from the source named here.

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png` | Material Symbols [`arrow_upward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_upward) | Google | Apache-2.0 |
| `left.png` | Material Symbols [`arrow_back`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_back) | Google | Apache-2.0 |
| `back.png` | Material Symbols [`arrow_downward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_downward) | Google | Apache-2.0 |
| `right.png` | Material Symbols [`arrow_forward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_forward) | Google | Apache-2.0 |
| `primary.png` | game-icons.net [`lorc/rocket`](https://game-icons.net/1x1/lorc/rocket.html) | Lorc | CC BY 3.0 |
| `secondary.png` | game-icons.net [`john-colburn/pistol-gun`](https://game-icons.net/1x1/john-colburn/pistol-gun.html) | John Colburn | CC BY 3.0 |
| `melee.png` | game-icons.net [`sbed/wrench`](https://game-icons.net/1x1/sbed/wrench.html) | Sbed | CC BY 3.0 |
| `pda1.png`, `pda2.png` | Material Symbols [`tablet_android`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:tablet_android) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `lastweapon.png` | Material Symbols [`history`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:history) | Google | Apache-2.0 |
| `jump.png` | game-icons.net [`delapouite/jump-across`](https://game-icons.net/1x1/delapouite/jump-across.html) | Delapouite | CC BY 3.0 |
| `reload.png` | Material Symbols [`autorenew`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:autorenew) | Google | Apache-2.0 |
| `inspect.png` | Material Symbols [`visibility`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:visibility) | Google | Apache-2.0 |
| `taunt.png` | Material Symbols [`celebration`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:celebration) | Google | Apache-2.0 |
| `actionitem.png` | Material Symbols [`redeem`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:redeem) | Google | Apache-2.0 |
| `dropitem.png` | game-icons.net [`delapouite/briefcase`](https://game-icons.net/1x1/delapouite/briefcase.html) | Delapouite | CC BY 3.0 |
| `disguise.png` | game-icons.net [`lorc/domino-mask`](https://game-icons.net/1x1/lorc/domino-mask.html) | Lorc | CC BY 3.0 |
| `disguiseteam.png` | Material Symbols [`swap_horiz`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:swap_horiz) | Google | Apache-2.0 |
| `voice1.png`, `voice2.png`, `voice3.png` | game-icons.net [`delapouite/walkie-talkie`](https://game-icons.net/1x1/delapouite/walkie-talkie.html) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Delapouite | CC BY 3.0 |
| `medic.png` | Material Symbols [`medical_services`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:medical_services) | Google | Apache-2.0 |
| `spray.png` | game-icons.net [`lorc/spray`](https://game-icons.net/1x1/lorc/spray.html) | Lorc | CC BY 3.0 |
| `allchat.png` | Material Symbols [`public`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:public) | Google | Apache-2.0 |
| `teamchat.png` | Material Symbols [`chat`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:chat) | Google | Apache-2.0 |
| `partychat.png` | game-icons.net [`delapouite/three-friends`](https://game-icons.net/1x1/delapouite/three-friends.html) | Delapouite | CC BY 3.0 |
| `voice.png` | Material Symbols [`mic`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:mic) | Google | Apache-2.0 |
| `scoreboard.png` | Material Symbols [`scoreboard`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:scoreboard) | Google | Apache-2.0 |
| `changeteam.png` | Material Symbols [`flag`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flag) | Google | Apache-2.0 |
| `changeclass.png` | Material Symbols [`switch_account`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:switch_account) | Google | Apache-2.0 |
| `loadout.png` | Material Symbols [`checkroom`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:checkroom) | Google | Apache-2.0 |
| `backpack.png` | Material Symbols [`backpack`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:backpack) | Google | Apache-2.0 |
| `mapinfo.png` | Material Symbols [`map`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:map) | Google | Apache-2.0 |
| `accept.png` | Material Symbols [`check`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:check) | Google | Apache-2.0 |
| `decline.png` | Material Symbols [`close`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:close) | Google | Apache-2.0 |
| `console.png` | Material Symbols [`terminal`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:terminal) | Google | Apache-2.0 |
| `roundinfo.png` | Material Symbols [`info`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:info) | Google | Apache-2.0 |
| `contracts.png` | Material Symbols [`assignment`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:assignment) | Google | Apache-2.0 |
| `screenshot.png` | Material Symbols [`screenshot_monitor`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:screenshot_monitor) | Google | Apache-2.0 |
| `savereplay.png` | Material Symbols [`video_file`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:video_file) | Google | Apache-2.0 |
| `report.png` | Material Symbols [`report`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:report) | Google | Apache-2.0 |
| `quit.png` | Material Symbols [`logout`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:logout) | Google | Apache-2.0 |
| `pause.png` | Material Symbols [`pause`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:pause) | Google | Apache-2.0 |
| `program.png` | TEAM / FORTRESS 2 and a round emblem, drawn by `program()` in `fetch_icons.py`, in Anton ([`ofl/anton/Anton-Regular.ttf`](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/anton/Anton-Regular.ttf)) | font: Vernon Adams | font: SIL OFL 1.1 |
