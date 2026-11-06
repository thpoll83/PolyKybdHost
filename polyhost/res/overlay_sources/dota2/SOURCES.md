# Dota 2 overlay: sources

`scripts/generate_app_overlays.py` renders `dota2.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `dota2_template` (1 file) | Dota 2: `dota2.exe` on Windows (`dota2`), the native `dota2` binary on Linux, `steam_app_570` under Proton |

Windows reports the process name without `.exe`, so `dota2` matches both
platforms. The game has a native Linux build, so Proton is unlikely;
`steam_app_570` (Steam app 570) is the window class Proton gives it, as for
the other Steam games here. Valve dropped the macOS build, so there is no macOS
name. None of the names was checked on an install.

## Shortcut reference

The "Arrow (Default)" template on the Dota 2 Wiki page "Hotkeys"
(<https://dota2.fandom.com/wiki/Hotkeys>, revision 2196318 of 2022-12-19, read
2026-11-05 from the page's wikitext through the MediaWiki API). The game
starts with this template. The game's own default key file in
SteamDatabase/GameTracking-Dota2 (`game/dota/cfg/user_keys_default.vcfg`)
binds only the console, so it is not the source. A user who picks another
template (WASD, Legacy and others) or rebinds a key still sees the default
here. The same keys apply on Linux.

## Keys

| Key | Action |
|---|---|
| Z, X, C, V, B, N | Item slot 1 to 6 (top row Z X C, bottom row V B N) |
| F1 | Select hero |
| A | Attack move |
| H | Hold position |
| S | Stop (cancel current action) |
| M | Move |
| O | Learn ability |
| U | Talents |
| J | Glyph of Fortification |
| P | Scan |
| Tab | Next unit |
| 1 to 9 | Select control group 1 to 9 |
| Ctrl+1 to Ctrl+9 | Assign control group 1 to 9 |
| F2, F3 | Select courier, courier: deliver items |
| F4 | Open shop |
| F5, F8 | Purchase quickbuy, purchase sticky item |
| \` | Scoreboard |
| F9 | Pause |
| F6 | Screenshot |
| \\ | Console |
| I | Showcase view |
| Enter, Shift+Enter | Team chat, all chat |
| G | Voice chat (team) |
| Y | Chat wheel |

## Left out

- Q, W, E, D, F, R (abilities 1 to 5 and the ultimate) and their Alt
  (autocast) variants: what they do depends on the hero.
- 0: the wiki's table for groups 7 and up names a key "10", which is not a key,
  so group 10's key was not confirmed.
- Shift+1 to Shift+9 (add to a control group): the plain digit already shows
  the group.
- The arrow keys (move the camera): the legend already shows the direction.
- The TP scroll slot and the neutral item slot: the wiki revision predates
  them, and their default keys were not confirmed from another source.
- Esc: ESC has the program mark.
- Spectator and replay keys: they act only while spectating, and on the same
  letters they would show in every match.
- Mouse bindings (camera grip and others): no keycap cell.

## Placement

As for League of Legends: every icon sits at the right edge and uses the full
height, and the firmware clears 3 px around the icon's ink, so a letter legend
stays whole. F1 to F9 use 34×40, the area AoE2 measured for F-key legends (F6
and F8 were not measured). The solid or wide icons (`INK` in `fetch_icons.py`)
are drawn in a smaller box inside their area. Every icon is drawn at exactly
its area, so the generator places it 1:1.

The drawn icons:

- Z X C V B N: the inventory as two rows of three slots, with the slot of that
  key filled (the drawing of the League of Legends item slots).
- 1 to 9 and Ctrl+1 to Ctrl+9: the Material Symbols `groups` or `group_add`
  glyph with the group number (DejaVu Sans Bold) above it.

ESC shows DOTA 2 in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). Valve's
logo art is proprietary and is not used.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `attack.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `move.png` | game-icons.net `delapouite/walk` | delapouite | CC BY 3.0 |
| `glyph.png` | game-icons.net `lorc/stone-tower` | lorc | CC BY 3.0 |
| `scan.png` | game-icons.net `lorc/radar-sweep` | lorc | CC BY 3.0 |
| `courier.png` | game-icons.net `delapouite/horse-head` | delapouite | CC BY 3.0 |
| `shop.png` | game-icons.net `delapouite/shop` | delapouite | CC BY 3.0 |
| `hero.png`, `hold.png`, `stop.png` | Material Symbols `person`, `pan_tool`, `block` | Google | Apache-2.0 |
| `learn.png`, `talents.png`, `nextunit.png` | Material Symbols `upgrade`, `account_tree`, `skip_next` | Google | Apache-2.0 |
| `deliver.png`, `quickbuy.png`, `sticky.png` | Material Symbols `local_shipping`, `shopping_cart`, `push_pin` | Google | Apache-2.0 |
| `scoreboard.png`, `pause.png`, `screenshot.png` | Material Symbols `scoreboard`, `pause`, `screenshot_monitor` | Google | Apache-2.0 |
| `console.png`, `showcase.png` | Material Symbols `terminal`, `zoom_in` | Google | Apache-2.0 |
| `teamchat.png`, `allchat.png`, `voice.png`, `chatwheel.png` | Material Symbols `chat`, `public`, `mic`, `forum` | Google | Apache-2.0 |
| `group1.png` … `group9.png` | Material Symbols `groups` + a digit drawn by `fetch_icons.py` (DejaVu Sans Bold) | Google | Apache-2.0 |
| `groupadd1.png` … `groupadd9.png` | Material Symbols `group_add` + a digit drawn by `fetch_icons.py` (DejaVu Sans Bold) | Google | Apache-2.0 |
| `item_z.png` … `item_n.png` | drawn by `fetch_icons.py` | — | this repo (GPL-3.0-or-later) |
| `program.png` | drawn by `fetch_icons.py` in Bebas Neue | font: Dharma Type | font: SIL OFL 1.1 |
