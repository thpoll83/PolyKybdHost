# Xonotic overlay: sources

`scripts/generate_app_overlays.py` renders `xonotic.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `xonotic_template` (1 file) | Xonotic on Linux, Windows and macOS, under the process names below |

| Name | Where it comes from |
|---|---|
| `xonotic-linux64-sdl`, `xonotic-linux64-glx`, `xonotic.exe`, `xonotic-x86.exe`, `xonotic-wgl.exe`, `xonotic-x86-wgl.exe`, `xonotic-osx-sdl-bin` | the release archive layout in `misc/tools/all/release.subr` of <https://github.com/xonotic/xonotic>, tag `xonotic-v0.8.6` |
| `xonotic-linux-sdl`, `xonotic-linux-glx` | the same file (the names the start scripts are built from) |
| `xonotic-x64.exe`, `xonotic-sdl.exe`, `xonotic-x64-sdl.exe` | the same file at tag `xonotic-v0.7.0`; later releases renamed them |
| `xonotic-sdl`, `xonotic-glx` | the `Exec=` lines of `misc/logos/xonotic.desktop` and `misc/logos/xonotic-glx.desktop`, which distribution packages install |
| `xonotic` | a short name some packages use; not found in the source |
| `org.xonotic.Xonotic` | the Flathub application id; not found in the source |

A build from source produces `xonotic-local-sdl` (`CLIENT` in the `Makefile`);
it is not in the list. Names not checked on an install.

## Shortcut reference

The default bindings in `binds-xonotic.cfg` of
<https://github.com/xonotic/xonotic-data.pk3dir>, tag `xonotic-v0.8.6` (commit
`45df581bba67832b61e5041f4b7d87cf59c80657`), read 2026-11-14. The aliases the
bindings call are in `commands.cfg` and `xonotic-client.cfg` of the same tag.
The weapon in each weapon group is the weapon with that `impulse` and the
`WEP_FLAG_NORMAL` flag in `qcsrc/common/weapons/weapon/*.qh`. A user who
rebinds a key in the game still sees the default here.

No default binding uses a modifier chord, so only the plain layer is drawn.

| Key | Command | Action | Other weapons in the group (not drawn) |
|---|---|---|---|
| W, S, A, D | `+forward`, `+back`, `+moveleft`, `+moveright` | Move forward, back, strafe left, right | |
| Space | `+jump` | Jump | |
| 1 | `weapon_group_1` | Blaster | Tuba |
| 2 | `weapon_group_2` | Shotgun | Shockwave |
| 3 | `weapon_group_3` | Machine gun | Arc |
| 4 | `weapon_group_4` | Mortar | Mine layer |
| 5 | `weapon_group_5` | Electro | |
| 6 | `weapon_group_6` | Crylink | HLAC |
| 7 | `weapon_group_7` | Vortex | Vaporizer, Rifle |
| 8 | `weapon_group_8` | Hagar | Seeker |
| 9 | `weapon_group_9` | Devastator | Fireball |
| 0 | `weapon_group_0` (`impulse 14`) | Cycle the superweapons | |
| Q | `weaplast` | Last weapon | |
| R | `reload` | Reload | |
| G, Backspace | `dropweapon` | Drop weapon | |
| E | `+hook` | Grappling hook | |
| F | `+use` | Use (drop the flag or key, leave a vehicle) | |
| V | `+button8` | Drag object (sandbox) | |
| K | `kill` | Kill yourself | |
| T, Enter | `messagemode` | Chat | |
| Y, Z | `messagemode2` | Team chat | |
| U | `+con_chat_maximize` | Chat history | |
| B, F8 | `quickmenu` | Quick menu | |
| Tab | `+showscores` | Scoreboard | |
| M | `+hud_panel_radar_maximized` | Enlarge radar | |
| I | `+show_info` | Server info | |
| \` | `toggleconsole` | Console | |
| Pause | `pause` | Pause | |
| F1, F2 | `vyes`, `vno` | Vote yes, vote no | |
| F3 | `spec` | Spectate | |
| F4 | `ready` | Ready | |
| F5 | `team_selection_show` | Team selection | |
| F6 | `team_auto` | Join the team the server selects | |
| F7 | `menu_showsandboxtools` | Sandbox tools | |
| F8 | `quickmenu` | Quick menu | |
| F9 | `cl_cmd hud minigame` | Minigames | |
| F10 | `menu_showquitdialog` | Quit | |
| F12 | `screenshot` | Screenshot | |

## Left out

- Shift (`+crouch`): the modifier keys have no overlay cell.
- The arrow keys (the same four movement commands as W, A, S, D): the arrows
  keep their own legends.
- `~` (`toggleconsole`): the same physical key as `` ` ``, which is drawn.
- Esc (`togglemenu`): ESC has the program mark.
- The keypad (`messagemode`, `messagemode2` and the 14 team messages,
  `+userbind 1` to `+userbind 18`): keypad keys have no cell.
- The mouse buttons, the wheel and the gamepad buttons.
- F11: not bound.

## Placement

As for Counter-Strike 2 (`../cs2/SOURCES.md`): every icon sits at the right
edge and uses the full height, and the firmware clears 3 px around the icon's
ink, so a letter legend stays whole. F1 to F9 use 34×40 and F10 and F12 30×40.
The solid or wide icons (`INK` in `fetch_icons.py`) are drawn in a smaller box
inside their area. Every icon is drawn at exactly its area, so the generator
places it 1:1.

Two keys show the same picture only where they run the same command: T and
Enter, Y and Z, G and Backspace, B and F8.

## ESC mark

ESC shows Xonotic's own icon, `misc/logos/xonotic_icon.svg` of
<https://github.com/xonotic/xonotic> at tag `xonotic-v0.8.6`, 40×40 in the
centre of the cell and drawn without the ESC legend
(`program_icon_legend: false`, protocol v25). `program()` in `fetch_icons.py`
lights the bird's head (the red and orange pixels) as one shape and the ring
(the blue pixels) as a second one, with 1 px cleared round the head.

Licence: the `COPYING` file of that repository says "All source files (as
defined by the respective license) in scope of this document are under the GPL
version 3 or any later version, at your choice", and its scope is the official
releases and the Team Xonotic branches of the repositories. The SVG has no
licence of its own, so it is GPL-3.0-or-later, the licence of this repository.

## Icons

Licence texts:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- GPL-3.0-or-later: https://www.gnu.org/licenses/gpl-3.0.html

| File | Source | Author | Licence |
|---|---|---|---|
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `blaster.png` | game-icons.net `lorc/ray-gun` | lorc | CC BY 3.0 |
| `shotgun.png` | game-icons.net `delapouite/sawed-off-shotgun` | delapouite | CC BY 3.0 |
| `machinegun.png` | game-icons.net `delapouite/uzi` | delapouite | CC BY 3.0 |
| `mortar.png` | game-icons.net `lorc/grenade` | lorc | CC BY 3.0 |
| `electro.png` | game-icons.net `sbed/electric` | sbed | CC BY 3.0 |
| `crylink.png` | game-icons.net `lorc/crystal-shine` | lorc | CC BY 3.0 |
| `vortex.png` | game-icons.net `lorc/vortex` | lorc | CC BY 3.0 |
| `hagar.png` | game-icons.net `lorc/missile-swarm` | lorc | CC BY 3.0 |
| `devastator.png` | game-icons.net `lorc/rocket` | lorc | CC BY 3.0 |
| `superweapon.png` | game-icons.net `lorc/star-swirl` | lorc | CC BY 3.0 |
| `hook.png` | game-icons.net `lorc/meat-hook` | lorc | CC BY 3.0 |
| `forward.png`, `back.png`, `left.png`, `right.png` | Material Symbols `arrow_upward`, `arrow_downward`, `arrow_back`, `arrow_forward` | Google | Apache-2.0 |
| `lastweapon.png`, `reload.png`, `drop.png` | Material Symbols `history`, `autorenew`, `place_item` | Google | Apache-2.0 |
| `use.png`, `drag.png`, `kill.png` | Material Symbols `touch_app`, `drag_pan`, `skull` | Google | Apache-2.0 |
| `chat.png`, `teamchat.png`, `chathistory.png` | Material Symbols `public`, `chat`, `forum` | Google | Apache-2.0 |
| `quickmenu.png`, `quickmenu_f.png` | Material Symbols `menu` | Google | Apache-2.0 |
| `scoreboard.png`, `radar.png`, `info.png`, `console.png`, `pause.png` | Material Symbols `scoreboard`, `radar`, `info`, `terminal`, `pause` | Google | Apache-2.0 |
| `voteyes.png`, `voteno.png`, `spectate.png`, `ready.png` | Material Symbols `thumb_up`, `thumb_down`, `visibility`, `check_circle` | Google | Apache-2.0 |
| `teamselect.png`, `autojoin.png`, `sandbox.png`, `minigames.png` | Material Symbols `groups`, `group_add`, `deployed_code`, `casino` | Google | Apache-2.0 |
| `quit.png`, `screenshot.png` | Material Symbols `logout`, `screenshot_monitor` | Google | Apache-2.0 |
| `program.png` | Xonotic `misc/logos/xonotic_icon.svg`, reduced to two flat shapes by `fetch_icons.py` | Team Xonotic | GPL-3.0-or-later |
