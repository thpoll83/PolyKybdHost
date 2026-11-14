# Unvanquished overlay: sources

`scripts/generate_app_overlays.py` renders `unvanquished.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `unvanquished_template` (1 file) | Unvanquished on Linux, Windows and macOS, under the process names below |

| Name | Where it comes from |
|---|---|
| `daemon`, `daemon.exe` | the client executable of the Daemon engine: `CLIENT_EXECUTABLE_NAME` in `CMakeLists.txt` of <https://github.com/DaemonEngine/Daemon>, tag `v0.56.2` |
| `daemon-vulkan` | the same variable in a build with the Vulkan renderer |
| `unvanquished` | the launcher script `dist/scripts/unvanquished` and the `Exec=` line of `debian/net.unvanquished.Unvanquished.desktop`. The script starts `daemon` with `exec`, so the process is `daemon` |
| `net.unvanquished.Unvanquished` | the name of that desktop file, used as the Flatpak application id |

`daemon` is a general word. A window of another program whose process is
named `daemon` would load this set too; no such program is known. Other games
built on the Daemon engine would use the same process name. Names not checked
on an install.

## Shortcut reference

The default bindings in `pkg/unvanquished_src.dpkdir/presets/input/wasd.cfg` of
<https://github.com/Unvanquished/Unvanquished>, release tag `v0.56.2`, read
2026-11-14. `pkg/unvanquished_src.dpkdir/default.cfg` of the same tag holds one
line, `preset presets/input/wasd.cfg`. The file binds letters by position
(`hw:w`), so the icons are on the same physical keys on every keyboard layout.
A user who rebinds a key in the game still sees the default here.

`modcase SHIFT a b` runs `a` while Shift is held and `b` otherwise. Two keys
use it, so the Shift layer has two keys.

| Key | Command | Action |
|---|---|---|
| W, S, A, D | `+forward`, `+back`, `+moveleft`, `+moveright` | Move forward, back, strafe left, right |
| Space | `+moveUp` | Jump |
| Delete | `centerview` | Centre the view |
| Q | `+activate` | Use: humans open the armoury, aliens evolve |
| E | `+deconstruct` | Deconstruct a building |
| C | `+taunt` | Taunt |
| V | `vsayMenu` | Voice message menu |
| B | `beaconMenu` | Beacon menu |
| N | `botTacticMenu` | Bot tactic menu |
| T, Enter | `message_public` | Public chat |
| Y, Shift+Enter | `message_team` | Team chat |
| U | `message_admin` | Admin chat |
| Backspace | `follow` | Follow a player (spectators) |
| Home, End | `followprev`, `follownext` | Follow the previous, the next player |
| P, Pause | `pause` | Pause |
| \` | `toggleConsole` | Console |
| Tab | `+scores` | Scoreboard |
| F1, F2 | `vote yes`, `vote no` | Vote yes, vote no |
| F3, F4 | `teamVote yes`, `teamVote no` | Team vote yes, team vote no |
| F11 | `screenshotJPEG` | Screenshot as JPEG |
| Shift+F11 | `screenshotPNG` | Screenshot as PNG |

## Keys bound for one team (not drawn)

The file binds these keys with `teambind`, for one team only. The host cannot
detect the player's team, so they stay blank.

| Key | Humans | Aliens | Spectators |
|---|---|---|---|
| 1 | `itemtoggle blaster`: switch to the blaster and back | not bound | not bound |
| F | `itemact medkit`: use the medkit | not bound | not bound |
| G | `itemact grenade`: throw a grenade | not bound | not bound |
| R | `reload` | not bound | not bound |
| Shift | `+sprint` | not bound | not bound |
| Ctrl | `+moveDown`: crouch | `+moveDown`: walk on walls | `+moveDown`: move down |

Q is bound with `teambind` for humans and for aliens to the same command,
`+activate`, so it is drawn.

## Left out

- Ctrl, Shift and Alt (`+speed`, walk slowly): the modifier keys have no
  overlay cell.
- The arrow keys (`+lookup`, `+lookdown`, `+left`, `+right`: turn the view):
  the arrows keep their own legends.
- The keypad (look and turn keys): keypad keys have no cell.
- The mouse buttons and the wheel.
- The 2 to 0 keys and every other key: not bound.

## Placement

As for Xonotic (`../xonotic/SOURCES.md`): every icon sits at the right edge and
uses the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F1 to F4 use 34×40 and F11 30×40. The solid or wide
icons (`INK` in `fetch_icons.py`) are drawn in a smaller box inside their area.
Every icon is drawn at exactly its area, so the generator places it 1:1.

F3 and F4 show the thumb of F1 and F2 at 28×28 with a T (DejaVu Sans Bold,
12 px) in the top-left corner of the icon area.

Two keys show the same picture only where they run the same command (T and
Enter, P and Pause) or the same action in another file format (F11 and
Shift+F11).

## ESC mark

ESC shows UNVAN over QUISHED in Bebas Neue (SIL OFL 1.1,
`ofl/bebasneue/BebasNeue-Regular.ttf` from google/fonts at commit e7db6ca),
centred on the whole cell and drawn without the ESC legend
(`program_icon_legend: false`, protocol v25). The name on one line fits only
at 15 px, where the letters touch, so it is split.

The game's own logo is not used. `COPYING.txt` of the repository says "The
media is licensed under the CREATIVE COMMONS ATTRIBUTION-SHAREALIKE 2.5
LICENSE", and the logo files (`dist/icons/`,
`pkg/unvanquished_src.dpkdir/ui/assets/logos/`) are media. CC BY-SA 2.5 is not
compatible with GPL-3.0-or-later, the licence of this repository.

## Icons

Licence texts:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Where each icon file comes from. The icon table gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`.

- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`

| File | Source | Author | Licence |
|---|---|---|---|
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `deconstruct.png` | game-icons.net `lorc/wrecking-ball` | lorc | CC BY 3.0 |
| `taunt.png` | game-icons.net `lorc/shouting` | lorc | CC BY 3.0 |
| `vsay.png` | game-icons.net `delapouite/megaphone` | delapouite | CC BY 3.0 |
| `beacon.png` | game-icons.net `delapouite/lighthouse` | delapouite | CC BY 3.0 |
| `forward.png`, `back.png`, `left.png`, `right.png` | Material Symbols `arrow_upward`, `arrow_downward`, `arrow_back`, `arrow_forward` | Google | Apache-2.0 |
| `centerview.png`, `activate.png`, `bottactic.png` | Material Symbols `center_focus_strong`, `touch_app`, `smart_toy` | Google | Apache-2.0 |
| `chat.png`, `teamchat.png`, `adminchat.png` | Material Symbols `public`, `chat`, `shield_person` | Google | Apache-2.0 |
| `follow.png`, `followprev.png`, `follownext.png` | Material Symbols `videocam`, `skip_previous`, `skip_next` | Google | Apache-2.0 |
| `pause.png`, `console.png`, `scoreboard.png`, `screenshot.png` | Material Symbols `pause`, `terminal`, `scoreboard`, `screenshot_monitor` | Google | Apache-2.0 |
| `voteyes.png`, `voteno.png` | Material Symbols `thumb_up`, `thumb_down` | Google | Apache-2.0 |
| `teamvoteyes.png`, `teamvoteno.png` | Material Symbols `thumb_up`, `thumb_down` + a T drawn by `fetch_icons.py` (DejaVu Sans Bold) | Google | Apache-2.0 |
| `program.png` | drawn by `fetch_icons.py` in Bebas Neue | font: Dharma Type | font: SIL OFL 1.1 |
