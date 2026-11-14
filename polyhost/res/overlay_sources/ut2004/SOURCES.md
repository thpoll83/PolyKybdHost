# Unreal Tournament 2004 overlay: sources

`scripts/generate_app_overlays.py` renders `ut2004.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `ut2004_template` (1 file) | Unreal Tournament 2004: `UT2004.exe` on Windows (`ut2004`), the Linux installer's `ut2004-bin` and `ut2004-bin-linux-amd64`, `steam_app_13230` under Proton, `Unreal Tournament 2004` (assumed) on macOS |

None of the names was checked on an install.

## Keys

The default bindings in `System/DefUser.ini` of the UT2004 3369 install, the
`[Engine.Input]` section (read 2026-11-14; the maintainer's `User.ini` was
identical). Each binding in `ut2004.yaml` names its command as that file
writes it.

1 to 9 run `SwitchWeapon 1` to `SwitchWeapon 9`, 0 runs `SwitchWeapon 0` and
Q `SwitchWeapon 10`. Each selects the weapon whose `InventoryGroup` is that
number. The groups were read from the stock weapon classes in
`System/XWeapons.u`:

| Key | Group | Weapon (class) |
|---|---|---|
| 1 | 1 | Shield Gun (`ShieldGun`; sets no group, so it keeps the default 1) |
| 2 | 2 | Assault Rifle (`AssaultRifle`) |
| 3 | 3 | Bio-Rifle (`BioRifle`) |
| 4 | 4 | Shock Rifle (`ShockRifle`) |
| 5 | 5 | Link Gun (`LinkGun`) |
| 6 | 6 | Minigun (`Minigun`) |
| 7 | 7 | Flak Cannon (`FlakCannon`) |
| 8 | 8 | Rocket Launcher (`RocketLauncher`) |
| 9 | 9 | Lightning Gun (`SniperRifle`) |
| 0 | 0 | Redeemer (`Redeemer`), Ion Painter (`Painter`) |
| Q | 10 | Translocator (`Translauncher`) |

The Onslaught weapons share slots with these: the Mine Layer is in group 3,
the Grenade Launcher in 7 and the AVRiL in 8 (`System/Onslaught.u`).

| Key | Command | Action |
|---|---|---|
| B, G | `SwitchToLastWeapon`, `SwitchToBestWeapon` | Last weapon, best weapon |
| \\ | `ThrowWeapon` | Throw weapon |
| / | `NextWeapon` | Next weapon |
| [, ] | `InventoryPrevious`, `InventoryNext` | Previous and next item |
| Space, Backspace | `Jump` | Jump |
| C | `Duck` | Crouch |
| E, U, Enter | `Use` | Use |
| J, K, L, ; | `Taunt pthrust`, `Taunt asssmack`, `Taunt throatcut`, `Taunt gesture_point` | Taunts |
| M, N | `BasePath 0`, `BasePath 1` | Show the path to a base (which team each number means was not checked) |
| T, R | `Talk`, `TeamTalk` | Say, team say |
| Tab | `Type` | Console line |
| F | `VoiceTalk` | Voice chat while held |
| I, O, P | `ToggleTeamChat`, `ToggleLocalChat`, `TogglePublicChat` | Voice chat channel: team, local, public |
| V, X | `SpeechMenuToggle`, `ShowVoteMenu` | Speech menu, vote menu |
| F1 to F4 | `ShowScores`, `InGameChat`, `ShowStats`, `ToggleBehindView` | Scores, in-game chat, stats, third-person view |
| F6 | `Stat Net` | Network stats |
| F9, F11, F12 | `shot`, `MusicMenu`, `ToggleRadarMap` | Screenshot, music menu, radar map |
| \` | `ConsoleToggle` | Console |
| =, - | `GrowHUD`, `ShrinkHUD` | Larger and smaller HUD |
| Pause | `Pause` | Pause |

## Keys the player rebound

With the game's files on the machine, the `ut2004` reader also reads
`System/User.ini`, the player's own bindings, and moves each icon to the keys
the player bound its command to (`build.remap`). A command bound to several
keys gets the icon on each. A default key the player gave to another command,
or to nothing, comes out blank. ESC keeps the program mark. The game rewrites
`User.ini` when the settings are saved, so a rebind shows on the next overlay
send after that.

## Left out

- W, A, S, D, the arrows, `,` and `.`, Numpad 7 to 9 (move and strafe), Z and
  `'` (strafe), Caps Lock, Delete, Page Down and End (look): the legend is
  enough.
- Ctrl (`Jump`) and Shift (`Duck`): modifier keys, which the overlay does not
  draw.
- F5, F7, F8 and F10 (`ToggleFreeCam`, `ToggleFreeCamSwivel`, `NextStats`,
  `Cancel`), Y (`writetolog`): debugging and logging commands.
- Esc (`ShowMenu`): ESC has the program mark.
- Mouse and joystick bindings: no keycap cell.

## Placement

The weapon keys use a 48×40 area at the right edge, so the digit legend at
the left stays whole. The shipped icons fill the 40×40 box at the right of
that area; the pictures read from the game are fitted to the whole area.
F1 to F6 use 34×40, the F-key area of the Warcraft III and AoE2 sets. The
solid icons (`INK` in `fetch_icons.py`) are drawn in a smaller box. Crouch is
a figure crouched over a floor line, drawn by `fetch_icons.py`: the kneeling
figure on game-icons.net read as praying, and a squatting figure without the
floor as a creeper (maintainer, 2026-11-14).

ESC shows UT2004 in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). Epic's
logo art is not used.

## Drawn from the game

With the game on the machine, the ten weapon keys are redrawn from the
player's own files by the `ut2004` reader
(`polyhost/services/game_assets/unreal2/`): the weapon bar picture of each
class, at the `IconCoords` the class declares on `HUDContent.Generic.HUD`
(`Textures/HudContent.utx`, a 512×512 DXT5 texture). The picture is dithered
inside a lit outline, after 1 px is taken off its edge to drop the dark glow
the game draws round each weapon (maintainer's choice from a comparison of
0, 1 and 2 px, 2026-11-14). The `game_assets:` block in `ut2004.yaml` names
the classes; nothing read from the game is committed.

Run on the UT2004 3369 files, all ten keys were drawn. The pictures are 3D
renders; dithered at 48×40 they read as guns of different shapes, not as the
weapon's details.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `shieldgun.png` | game-icons.net `lorc/bolt-shield` | Lorc | CC BY 3.0 |
| `assaultrifle.png` | game-icons.net `skoll/mp5` | Skoll | CC BY 3.0 |
| `biorifle.png` | game-icons.net `lorc/goo-spurt` | Lorc | CC BY 3.0 |
| `shockrifle.png` | game-icons.net `lorc/laser-precision` | Lorc | CC BY 3.0 |
| `linkgun.png` | game-icons.net `lorc/linked-rings` | Lorc | CC BY 3.0 |
| `minigun.png` | game-icons.net `lorc/bullets` | Lorc | CC BY 3.0 |
| `flakcannon.png` | game-icons.net `lorc/striking-diamonds` | Lorc | CC BY 3.0 |
| `rocketlauncher.png` | game-icons.net `lorc/missile-swarm` | Lorc | CC BY 3.0 |
| `lightninggun.png` | game-icons.net `lorc/lightning-tear` | Lorc | CC BY 3.0 |
| `superweapon.png` | game-icons.net `lorc/mushroom-cloud` | Lorc | CC BY 3.0 |
| `translocator.png` | game-icons.net `lorc/teleport` | Lorc | CC BY 3.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | Delapouite | CC BY 3.0 |
| `speechmenu.png` | game-icons.net `delapouite/megaphone` | Delapouite | CC BY 3.0 |
| `crouch.png` | drawn by `fetch_icons.py` (`crouch()`) | - | - |
| `lastweapon.png`, `bestweapon.png`, `throwweapon.png`, `nextweapon.png`, `invprev.png`, `invnext.png`, `use.png`, `taunt.png`, `basepath.png`, `talk.png`, `teamtalk.png`, `type.png`, `voicetalk.png`, `voiceteam.png`, `voicelocal.png`, `voicepublic.png`, `vote.png`, `ingamechat.png`, `scores.png`, `stats.png`, `behindview.png`, `netstats.png`, `screenshot.png`, `music.png`, `radar.png`, `console.png`, `growhud.png`, `shrinkhud.png`, `pause.png` | Material Symbols `history`, `star`, `place_item`, `skip_next`, `chevron_left`, `chevron_right`, `touch_app`, `mood`, `route`, `chat`, `forum`, `keyboard`, `mic`, `groups`, `near_me`, `public`, `how_to_vote`, `chat_bubble`, `scoreboard`, `bar_chart`, `3p`, `network_check`, `screenshot_monitor`, `music_note`, `radar`, `terminal`, `zoom_out_map`, `zoom_in_map`, `pause` | Google | Apache-2.0 |
| `program.png` | UT2004 set in Bebas Neue | Dharma Type | SIL OFL 1.1 |

game-icons.net: <https://game-icons.net>, CC BY 3.0
(<https://creativecommons.org/licenses/by/3.0/>).
