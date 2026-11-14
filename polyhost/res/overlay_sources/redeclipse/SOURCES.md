# Red Eclipse overlay: sources

`scripts/generate_app_overlays.py` renders `redeclipse.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `redeclipse_template` (1 file) | Red Eclipse on Linux, Windows and macOS, under the process names below |

All files named here are in <https://github.com/redeclipse/base> at tag `v2.0.0`.

| Name | Where it comes from |
|---|---|
| `redeclipse_linux`, `redeclipse.exe`, `redeclipse_universal`, `redeclipse_bsd` | the binary the start script `redeclipse.sh` runs: `redeclipse` plus the suffix it selects for Linux, Windows, macOS and FreeBSD (`redeclipse.bat` on Windows). `src/Makefile` builds the same names (`APPCLIENT` plus `BIN_SUFFIX`) |
| `redeclipse_osx`, `redeclipse_windows.exe`, `redeclipse_native` | `add_executable(redeclipse${BIN_SUFFIX} ...)` in `src/CMakeLists.txt` |
| `redeclipse` | `Exec=@APPNAME@` in `src/install/nix/redeclipse.desktop.am`, with `APPNAME=redeclipse` in `src/Makefile`. `redeclipse.exe` also matches it on Windows |
| `net.redeclipse.RedEclipse` | the Flathub application id; not found in the source |

Names not checked on an install.

## Shortcut reference

The default `bind` lines in `config/setup.cfg`, commit
`4117baee090baa71b0116599c415998aff9839c3` (2019-12-19), read 2026-11-14. The
weapon behind each `weapon N` is the N-th entry of the weapon enum in
`src/game/weapons.h`. `config/keymap.cfg` only names the keys. A user who
rebinds a key in the game still sees the default here.

No default binding uses a modifier chord, so only the plain layer is drawn.

| Key | Command | Action |
|---|---|---|
| W, S, A, D | `forward`, `backward`, `left`, `right` | Move forward, back, strafe left, right |
| Space | `jump` | Jump |
| Q | `special` | Special move |
| 1, 2, 3 | `weapon 0`, `1`, `2` | Claw, pistol, sword |
| 4, 5, 6 | `weapon 3`, `4`, `5` | Shotgun, SMG, flamer |
| 7, 8, 9 | `weapon 6`, `7`, `8` | Plasma, zapper, rifle |
| 0, -, = | `weapon 9`, `10`, `11` | Grenade, mine, rocket |
| [ | `universaldelta 1` | The same as mouse button 4 (wheel up): in a match `weapon -1 1`, change the weapon by one step. While the weapon zooms, it changes the zoom |
| ] | `universaldelta -1` | The same as mouse button 5 (wheel down): one step the other way |
| R | `reload` | Reload |
| Z | `drop` | Drop the weapon |
| E | `use` | Use |
| F | `affinity` | Drop the flag or the bomb |
| K | `suicide` | Suicide |
| T, Enter | `chat` | Chat |
| Y | `teamchat` | Team chat |
| \`, / | `command` | Command line (opens the input with a `/`) |
| Tab | `showscores` | Scoreboard |
| M | `uiopen bindmap` | Key bindings |
| Pause | `gamepaused` | Pause |
| Insert, Delete | `addbot`, `delbot` | Add a bot, remove a bot |
| Home | `spectate 1` | Spectate |
| End | `spectate 0` | Leave spectating |
| , and F6 | `uiopen profile` | Profile |
| . and F7 | `uiopen team` | Team |
| F1 | `uiopen help` | Help |
| F2 | `edittoggle` | Map editor |
| F3 | `uiopen maps` | Maps |
| F4 | `uiopen votes` | Votes |
| F5 | `uiopen servers` | Servers |
| F8 | `toggleconsole` | Console |
| F9 | `thirdpersonswitch` | Third person view |
| F11 | `screenshot` | Screenshot |

The actions of Q ("special") and F ("affinity") are named after the commands;
the release's `config/` files do not describe them. Red Eclipse uses "affinity"
for the flag and the bomb. Not checked in the game.

## Other meanings (not drawn)

| Key | While spectating (`specbind`) | While waiting to respawn (`waitbind`) | In the map editor (`editbind`) |
|---|---|---|---|
| E | join the match (`spectate 0`) | | |
| R, Space | change the spectator mode | R: change the wait mode | |
| Home | change the spectator mode | | |
| End | | change the wait mode | |
| F1 to F9, 1 to 0, and most letters | | | editor commands |

## Left out

- F10 (`takescreenshot`): the command is not defined in `config/` or the
  engine files read at this tag, so what it does was not confirmed. F11
  (`screenshot`) is drawn.
- End is bound twice (`suicide`, then `spectate 0`). The second `bind` replaces
  the first, so End shows "leave spectating".
- Left Shift (`crouch`) and left Ctrl (`walk`): the modifier keys have no
  overlay cell.
- The arrow keys (the same four movement commands as W, A, S, D): the arrows
  keep their own legends.
- The keypad (chat, volume, sound on and off): keypad keys have no cell.
- The mouse buttons and the wheel.
- The map editor keys (`editbind`): another mode of the same
  process, which the host cannot detect.

## Placement

As for Xonotic (`../xonotic/SOURCES.md`): every icon sits at the right edge and
uses the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F1 to F9 use 34×40 and F11 30×40. The solid or wide
icons (`INK` in `fetch_icons.py`) are drawn in a smaller box inside their area.
Every icon is drawn at exactly its area, so the generator places it 1:1.

Two keys show the same picture only where they run the same command: T and
Enter, `` ` `` and /, `,` and F6, `.` and F7.

## ESC mark

ESC shows RED over ECLIPSE in Bebas Neue (SIL OFL 1.1,
`ofl/bebasneue/BebasNeue-Regular.ttf` from google/fonts at commit e7db6ca),
centred on the whole cell and drawn without the ESC legend
(`program_icon_legend: false`, protocol v25).

The game's own logo is not used. `doc/license.txt` puts the source code under
the zlib licence and says of the content: "In the absence of an explicit
license, content is considered to be covered by the CC-BY-SA license, either
version 4.0 or (at your option) any later version". The logo and
`src/redeclipse.ico` are content with no licence of their own, and
`doc/trademark.txt` adds a mark policy. CC BY-SA 4.0 art cannot be shipped
under GPL-3.0-or-later, the licence of this repository.

## Icons

Licence texts:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `special.png` | game-icons.net `lorc/sprint` | lorc | CC BY 3.0 |
| `claw.png` | game-icons.net `lorc/claw-slashes` | lorc | CC BY 3.0 |
| `pistol.png` | game-icons.net `john-colburn/pistol-gun` | John Colburn | CC BY 3.0 |
| `sword.png` | game-icons.net `lorc/broadsword` | lorc | CC BY 3.0 |
| `shotgun.png` | game-icons.net `delapouite/sawed-off-shotgun` | delapouite | CC BY 3.0 |
| `smg.png` | game-icons.net `delapouite/uzi` | delapouite | CC BY 3.0 |
| `flamer.png` | game-icons.net `carl-olsen/flame` | Carl Olsen | CC BY 3.0 |
| `plasma.png` | game-icons.net `lorc/plasma-bolt` | lorc | CC BY 3.0 |
| `zapper.png` | game-icons.net `sbed/electric` | sbed | CC BY 3.0 |
| `rifle.png` | game-icons.net `skoll/lee-enfield` | Skoll | CC BY 3.0 |
| `grenade.png` | game-icons.net `lorc/grenade` | lorc | CC BY 3.0 |
| `mine.png` | game-icons.net `lorc/land-mine` | lorc | CC BY 3.0 |
| `rocket.png` | game-icons.net `lorc/rocket` | lorc | CC BY 3.0 |
| `affinity.png` | game-icons.net `lorc/flying-flag` | lorc | CC BY 3.0 |
| `forward.png`, `back.png`, `left.png`, `right.png` | Material Symbols `arrow_upward`, `arrow_downward`, `arrow_back`, `arrow_forward` | Google | Apache-2.0 |
| `weaponup.png`, `weapondown.png` | Material Symbols `keyboard_double_arrow_up`, `keyboard_double_arrow_down` | Google | Apache-2.0 |
| `reload.png`, `drop.png`, `use.png`, `suicide.png` | Material Symbols `autorenew`, `place_item`, `touch_app`, `skull` | Google | Apache-2.0 |
| `chat.png`, `teamchat.png`, `command.png` | Material Symbols `public`, `chat`, `terminal` | Google | Apache-2.0 |
| `scoreboard.png`, `bindmap.png`, `pause.png` | Material Symbols `scoreboard`, `keyboard`, `pause` | Google | Apache-2.0 |
| `addbot.png`, `delbot.png`, `spectate.png`, `play.png` | Material Symbols `person_add`, `person_remove`, `visibility`, `sports_esports` | Google | Apache-2.0 |
| `help.png`, `edit.png`, `maps.png`, `votes.png`, `servers.png` | Material Symbols `help`, `edit`, `map`, `how_to_vote`, `dns` | Google | Apache-2.0 |
| `profile.png`, `profile_f.png`, `team.png`, `team_f.png` | Material Symbols `account_circle`, `groups` | Google | Apache-2.0 |
| `console.png`, `thirdperson.png`, `screenshot.png` | Material Symbols `article`, `cameraswitch`, `screenshot_monitor` | Google | Apache-2.0 |
| `program.png` | drawn by `fetch_icons.py` in Bebas Neue | font: Dharma Type | font: SIL OFL 1.1 |
