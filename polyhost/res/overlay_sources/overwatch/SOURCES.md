# Overwatch 2 overlay: sources

`scripts/generate_app_overlays.py` renders `overwatch.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `overwatch_template` (1 file) | Overwatch 2: `Overwatch.exe` (in `_retail_`) on Windows, `steam_app_2357570` under Proton |

`Overwatch Launcher.exe` starts the game and exits; it gets no set. The name
is from Blizzard forum threads. None of the names was checked on an install.

## Shortcut reference

Blizzard's support pages need a Battle.net login and could not be read. The
keys are those two independent key lists agree on:

- Shacknews, <https://www.shacknews.com/article/132531/pc-keybindings-controls-overwatch-2>
- TutorialTactic, <https://tutorialtactic.com/blog/overwatch-2016-shortcuts/>

G (ping) is from several ping guides (gameskinny, videogamer,
windowscentral), not from these two lists. Read 2026-11-15. A screenshot of
the game's Controls page should confirm this before anyone relies on it.

## Default keys only

Overwatch keeps the key bindings on Blizzard's servers with the account
(Bill Warnecke, Overwatch developer:
<https://outof.games/devtracker/overwatch/reddit/r-overwatch/439>).
`Documents\Overwatch\Settings\Settings_v0.ini` holds only the settings of
the computer. The overlay therefore always shows the defaults.

## Keys

| Key | Action |
|---|---|
| W | Move forward |
| A | Move left |
| S | Move back |
| D | Move right |
| Q | Ultimate |
| E | Ability 2 |
| R | Reload |
| V | Quick melee |
| F | Interact |
| 1 | Weapon 1 |
| 2 | Weapon 2 |
| Space | Jump |
| G | Ping |
| C | Communication wheel |
| X | Need healing |
| Z | Ultimate status |
| Y | Spray |
| \` | Push to talk |
| M | Mute microphone |
| Enter | Text chat |
| Tab | Scoreboard |
| H | Change hero |
| N | Endorse players |
| P | Social |
| F9 | Capture highlight |
| Print Screen | Screenshot |

## Left out

- Shift (ability 1), Ctrl (crouch) and Alt (perks): modifier keys, no cell.
- Fire, secondary fire and the ping wheel: on the mouse.
- The keys only one source lists: T (spray), O (social), F1 (hero
  information or spectate), Backspace (reply), L (custom game lobby) and the
  Ctrl+Shift display keys.
- Esc: ESC has the program mark.

## Placement

As for Counter-Strike 2: every icon sits at the right edge of its key and uses
the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F-key icons use 34x40 (the area AoE2 measured for
F-key legends). The solid or wide icons (`INK` in `fetch_icons.py`) are drawn
in a smaller box inside their area. Every icon is drawn at exactly its area by
`game_set.py`, so the generator places it 1:1.

ESC shows a 1-bit emblem drawn by `program()` in `fetch_icons.py` to resemble
the Overwatch emblem: a ring whose top arc is cut off at 10:30 and 1:30, and
two prongs near the centre that splay out into the lower ring. It is 39 px
across, centred on the whole cell and drawn without the ESC legend
(`program_icon_legend: false`, protocol v25). It was compared by eye with the
game's site icon (Google's favicon service for overwatch.blizzard.com);
Blizzard's logo art is proprietary and is not used or committed.

1 and 2 show the gun with the weapon number, so the two keys differ.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `ultimate.png` | game-icons.net `lorc/burning-meteor` | lorc | CC BY 3.0 |
| `ability2.png` | game-icons.net `lorc/magic-palm` | lorc | CC BY 3.0 |
| `melee.png` | game-icons.net `lorc/punch` | lorc | CC BY 3.0 |
| `weapon1.png`, `weapon2.png` | game-icons.net `john-colburn/pistol-gun` + the number drawn by `game_set.py` (DejaVu Sans Bold) | John Colburn | CC BY 3.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `ping.png` | game-icons.net `delapouite/position-marker` | delapouite | CC BY 3.0 |
| `comms.png` | game-icons.net `delapouite/walkie-talkie` | delapouite | CC BY 3.0 |
| `spray.png` | game-icons.net `lorc/spray` | lorc | CC BY 3.0 |
| `endorse.png` | game-icons.net `delapouite/thumb-up` | delapouite | CC BY 3.0 |
| `social.png` | game-icons.net `delapouite/three-friends` | delapouite | CC BY 3.0 |
| `highlight.png` | game-icons.net `delapouite/film-projector` | delapouite | CC BY 3.0 |
| `forward.png`, `left.png`, `back.png` | Material Symbols `arrow_upward`, `arrow_back`, `arrow_downward` | Google | Apache-2.0 |
| `right.png`, `reload.png`, `interact.png` | Material Symbols `arrow_forward`, `autorenew`, `touch_app` | Google | Apache-2.0 |
| `healing.png`, `ultstatus.png`, `pushtotalk.png` | Material Symbols `medical_services`, `percent`, `mic` | Google | Apache-2.0 |
| `mute.png`, `chat.png`, `scoreboard.png` | Material Symbols `mic_off`, `chat`, `scoreboard` | Google | Apache-2.0 |
| `heroselect.png`, `screenshot.png` | Material Symbols `switch_account`, `screenshot_monitor` | Google | Apache-2.0 |
| `program.png` | drawn by `fetch_icons.py` (geometric shapes, no source art) | - | - |
