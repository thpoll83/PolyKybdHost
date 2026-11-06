# Counter-Strike 2 overlay: sources

`scripts/generate_app_overlays.py` renders `cs2.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `cs2_template` (1 file) | Counter-Strike 2: `cs2.exe` on Windows (`cs2`), the native `cs2` binary on Linux, `steam_app_730` under Proton |

Windows reports the process name without `.exe`, so `cs2` matches both
platforms. The game has a native Linux build, so Proton is unlikely;
`steam_app_730` (Steam app 730) is the window class Proton gives it, as for
the other Steam games here. The game does not run on macOS. None of the names
was checked on an install.

## Shortcut reference

The default bindings Valve ships in `game/csgo/cfg/user_keys_default.vcfg`,
as mirrored by SteamDatabase:
<https://github.com/SteamDatabase/GameTracking-CS2/blob/cce7bf1f190144c1c08fb0fe75fd3c9514f2637f/game/csgo/cfg/user_keys_default.vcfg>
(read 2026-11-05). The commands map to the weapon slots as in CS:GO:
`slot1`..`slot5` primary, pistol, knife, grenades, bomb; `slot6`..`slot10`
HE grenade, flashbang, smoke, decoy, molotov or incendiary; `slot12`
healthshot. A user who rebinds a key in the game still sees the default here.

## Keys

| Key | Command | Action |
|---|---|---|
| 1 to 5 | `slot1`..`slot5` | Primary weapon, pistol, knife, grenades, bomb |
| 6 to 9, 0 | `slot6`..`slot10` | HE grenade, flashbang, smoke, decoy, molotov / incendiary |
| X | `slot12` | Healthshot |
| Q | `lastinv` | Last weapon |
| Space | `+jump` | Jump |
| E | `+use` | Use |
| R | `+reload` | Reload |
| F | `+lookatweapon` | Inspect weapon |
| G | `drop` | Drop weapon |
| H | `switchhands` | Switch hands |
| B | `buymenu` | Buy menu |
| F3, F4 | `autobuy`, `rebuy` | Autobuy, rebuy |
| Delete | `sellbackall` | Sell back all |
| C, V | `+radialradio`, `+radialradio2` | Radio wheel 1 and 2 |
| Z | `radio` | Radio commands |
| T | `+spray_menu` | Graffiti |
| U, Y | `messagemode2`, `messagemode` | Team chat, all chat |
| Tab | `+showscores` | Scoreboard |
| I | `show_loadout_toggle` | Loadout |
| M | `teammenu` | Choose team |
| \` | `toggleconsole` | Console |
| F5 | `jpeg` | Screenshot |
| F10 | `cs_quit_prompt` | Quit |

## Left out

- W, A, S, D (move), Ctrl (crouch), Shift (walk): the letter legend is enough
  for movement, and the modifier keys have no overlay cell.
- `,` and `.` (`buyammo1`, `buyammo2`): CS2 sells no separate ammunition, and
  it was not checked that the commands do anything.
- F6 and F7 (`save quick`, `load quick`): they do nothing in a match.
- Esc (`cancelselect`): ESC has the program mark.
- K: the default file binds no key to voice chat; voice is on mouse button 4
  (`+voicerecord`), and the map is not on M (M is `teammenu`). Mouse bindings
  have no keycap cell.

## Placement

As for League of Legends: every icon sits at the right edge and uses the full
height, and the firmware clears 3 px around the icon's ink, so a letter legend
stays whole. F3, F4 and F5 use 34×40 and F10 30×40 (the areas AoE2 measured for
F-key legends; F10 was not measured). The solid or wide icons (`INK` in
`fetch_icons.py`) are drawn in a smaller box inside their area. Every icon is
drawn at exactly its area, so the generator places it 1:1.

C and V show the walkie-talkie with the wheel number 1 or 2 (DejaVu Sans Bold)
in the top-left corner of the icon area.

ESC shows CS2 in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). Valve's
logo art is proprietary and is not used.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `primary.png` | game-icons.net `skoll/ak47` | Skoll | CC BY 3.0 |
| `secondary.png` | game-icons.net `john-colburn/pistol-gun` | John Colburn | CC BY 3.0 |
| `knife.png` | game-icons.net `lorc/bowie-knife` | lorc | CC BY 3.0 |
| `grenade.png` | game-icons.net `lorc/grenade` | lorc | CC BY 3.0 |
| `bomb.png` | game-icons.net `delapouite/dynamite` | delapouite | CC BY 3.0 |
| `hegrenade.png` | game-icons.net `lorc/mine-explosion` | lorc | CC BY 3.0 |
| `flashbang.png` | game-icons.net `lorc/flash-grenade` | lorc | CC BY 3.0 |
| `smoke.png` | game-icons.net `lorc/smoking-orb` | lorc | CC BY 3.0 |
| `molotov.png` | game-icons.net `lorc/fire-bomb` | lorc | CC BY 3.0 |
| `healthshot.png` | game-icons.net `lorc/syringe` | lorc | CC BY 3.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `buymenu.png` | game-icons.net `delapouite/shopping-cart` | delapouite | CC BY 3.0 |
| `radio1.png`, `radio2.png` | game-icons.net `delapouite/walkie-talkie` + a digit drawn by `fetch_icons.py` (DejaVu Sans Bold) | delapouite | CC BY 3.0 |
| `spray.png` | game-icons.net `lorc/spray` | lorc | CC BY 3.0 |
| `loadout.png` | game-icons.net `delapouite/backpack` | delapouite | CC BY 3.0 |
| `decoy.png`, `lastweapon.png` | Material Symbols `volume_up`, `history` | Google | Apache-2.0 |
| `use.png`, `reload.png`, `inspect.png` | Material Symbols `touch_app`, `autorenew`, `visibility` | Google | Apache-2.0 |
| `drop.png`, `switchhands.png` | Material Symbols `place_item`, `swap_horiz` | Google | Apache-2.0 |
| `autobuy.png`, `rebuy.png`, `sellback.png` | Material Symbols `shopping_cart_checkout`, `replay`, `sell` | Google | Apache-2.0 |
| `radiomenu.png`, `teamchat.png`, `allchat.png` | Material Symbols `campaign`, `chat`, `public` | Google | Apache-2.0 |
| `scoreboard.png`, `teammenu.png`, `console.png` | Material Symbols `scoreboard`, `groups`, `terminal` | Google | Apache-2.0 |
| `screenshot.png`, `quit.png` | Material Symbols `screenshot_monitor`, `logout` | Google | Apache-2.0 |
| `program.png` | drawn by `fetch_icons.py` in Bebas Neue | font: Dharma Type | font: SIL OFL 1.1 |
