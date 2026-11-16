# Path of Exile 1 and 2 overlays: sources

`scripts/generate_app_overlays.py` renders `poe.yaml` and `poe2.yaml`;
`fetch_icons.py` rebuilds `icons/` for both.

| Set | Loads for |
|---|---|
| `poe_template` (1 file) | Path of Exile: `PathOfExile.exe`, `PathOfExile_x64.exe`, `PathOfExileSteam.exe`, `PathOfExile_x64Steam.exe`, `PathOfExile_KG.exe`, `PathOfExile_x64_KG.exe`; `steam_app_238960` under Proton |
| `poe2_template` (1 file) | Path of Exile 2: the same executables with a window title that starts with "Path of Exile 2"; `steam_app_2694490` under Proton |

The executable names are from SCSKiller (`GameFiles.cs`) and WingmanReloaded
(`lib/GLOBALS.ahk`). Both games use the same names; navali-creations/hinekora
(`poe_process.rs`) tells them apart by window title, and so does the mapping
(`titles-match`). Without a title (macOS, some Wayland setups) the first
game's set loads. None of the names or titles was checked on an install.

## Shortcut reference

Grinding Gear Games publishes no key list. The keys are the defaults of the
`[ACTION_KEYS]` section of the game's config file:

- Path of Exile: the value most of 26 different player
  `production_Config.ini` files on GitHub agree on, for each action (all 47
  keys of the set match the majority). Example:
  <https://github.com/jakeuj/poe_production_Config/blob/HEAD/production_Config.ini>
- Path of Exile 2: three player `poe2_production_Config.ini` files, which
  agree on all 42 keys:
  <https://github.com/jakeuj/poe_production_Config/blob/HEAD/poe2_production_Config.ini>,
  <https://github.com/cedws/dotfiles-esports-cafe/blob/HEAD/Documents/My%20Games/Path%20of%20Exile%202/poe2_production_Config.ini>,
  <https://github.com/kutan16/my-documents-saved-game-files/blob/HEAD/My%20Games/Path%20of%20Exile%202/poe2_production_Config.ini>

Read 2026-11-15. The action names are the file's; the labels are read from
them.

## The player's bindings

`[ACTION_KEYS]` has one line per action, `action=<VK>` or
`action=<VK> <modifier>`: a Windows virtual-key code (0 or empty: unbound;
1, 2, 4 to 6: mouse buttons) and 1 for Shift or 2 for Ctrl. The value for Alt
is not known for sure (awakened-poe-trade reads 3, WhatsARoute 4), so a line
with any other modifier is left out. `game_assets/poe_keys.py` reads
`Documents\My Games\Path of Exile\production_Config.ini` (also
`garena_tw_production_Config.ini`, OneDrive, Wine, the Proton prefix and the
macOS `~/Library/Application Support/Path of Exile/Preferences`), and
`game_assets/poe2_keys.py` reads `Documents\My Games\Path of Exile 2\poe2_production_Config.ini`.
Path of Exile 2 has a second set, `[WASD_ACTION_KEYS]`, which
`user_input_mode=wasd` in `[GENERAL]` selects; the reader then uses it, so
the skill icons move to Q E R T F. The game writes every action it knows, but
the actions change with each league, so an action missing from the file keeps
its default key. Format and folders from SnosMe/awakened-poe-trade
(`GameConfig.ts`), Kvan7/Exiled-Exchange-2 and ParogDev/WhatsARoute
(`GameKeys.cs`). Not checked on an install.

A key moved between the plain and the Ctrl layer is fine: both are in the one
overlay file.

## Keys: Path of Exile

| Key | Command | Action |
|---|---|---|
| Q | `use_bound_skill4` | Skill 4 |
| W | `use_bound_skill5` | Skill 5 |
| E | `use_bound_skill6` | Skill 6 |
| R | `use_bound_skill7` | Skill 7 |
| T | `use_bound_skill8` | Skill 8 |
| Ctrl+Q | `use_bound_skill9` | Skill 9 |
| Ctrl+W | `use_bound_skill10` | Skill 10 |
| Ctrl+E | `use_bound_skill11` | Skill 11 |
| Ctrl+R | `use_bound_skill12` | Skill 12 |
| Ctrl+T | `use_bound_skill13` | Skill 13 |
| 1 | `use_flask_in_slot1` | Flask 1 |
| 2 | `use_flask_in_slot2` | Flask 2 |
| 3 | `use_flask_in_slot3` | Flask 3 |
| 4 | `use_flask_in_slot4` | Flask 4 |
| 5 | `use_flask_in_slot5` | Flask 5 |
| 6 | `use_temporary_skill1` | Temporary skill 1 |
| 7 | `use_temporary_skill2` | Temporary skill 2 |
| I | `open_inventory_panel` | Inventory |
| C | `open_character_panel` | Character |
| P | `open_passive_skills_panel` | Passive skill tree |
| H | `open_challenges_panel` | Challenges |
| L | `open_ladder_panel` | Ladder |
| K | `open_cosmetics_inventory` | Cosmetics |
| N | `open_mtx_stash` | Microtransaction stash |
| M | `open_microtransaction_panel` | Shop |
| O | `open_options` | Options |
| V | `generic_league_key` | League mechanic |
| ' | `generic_league_panel_key` | League panel |
| G | `open_atlas_screen` | Atlas |
| Ctrl+G | `open_atlas_passives_screen` | Atlas passive tree |
| U | `open_world_panel` | World |
| S | `open_social_panel` | Social |
| Y | `open_pantheon_panel` | Pantheon |
| B | `open_events_panel` | Events |
| ; | `open_guidebook_panel` | Guidebook |
| / | `open_market_browser_panel` | Trade market |
| Space | `close_panels` | Close panels |
| Tab | `open_map` | Overlay map |
| Enter | `chat` | Chat |
| Page Up | `zoom_in` | Zoom in |
| Page Down | `zoom_out` | Zoom out |
| F1 | `performance_overlay` | Performance overlay |
| F8 | `take_screenshot` | Screenshot |
| Z | `highlight_toggle` | Toggle item labels |
| X | `weapon_swap` | Weapon swap |
| D | `detonate_mines` | Detonate mines |
| F | `enable_key_pickup` | Pick up |

## Keys: Path of Exile 2

| Key | Command | Action |
|---|---|---|
| Q | `use_bound_skill4` | Skill 4 |
| W | `use_bound_skill5` | Skill 5 |
| E | `use_bound_skill6` | Skill 6 |
| R | `use_bound_skill7` | Skill 7 |
| T | `use_bound_skill8` | Skill 8 |
| Ctrl+Q | `use_bound_skill9` | Skill 9 |
| Ctrl+W | `use_bound_skill10` | Skill 10 |
| Ctrl+E | `use_bound_skill11` | Skill 11 |
| Ctrl+R | `use_bound_skill12` | Skill 12 |
| Ctrl+T | `use_bound_skill13` | Skill 13 |
| 1 | `use_flask_in_slot1` | Life flask |
| 2 | `use_flask_in_slot2` | Mana flask |
| 6 | `use_temporary_skill1` | Temporary skill 1 |
| 7 | `use_temporary_skill2` | Temporary skill 2 |
| Space | `use_dodge_roll` | Dodge roll |
| \` | `direct_minions` | Direct minions |
| I | `open_inventory_panel` | Inventory |
| C | `open_character_panel` | Character |
| P | `open_passive_skills_panel` | Passive skill tree |
| H | `open_challenges_panel` | Challenges |
| L | `open_ladder_panel` | Ladder |
| K | `open_cosmetics_inventory` | Cosmetics |
| N | `open_mtx_stash` | Microtransaction stash |
| M | `open_microtransaction_panel` | Shop |
| O | `open_options` | Options |
| V | `generic_league_key` | League mechanic |
| ' | `generic_league_panel_key` | League panel |
| G | `open_skill_panel` | Skills |
| U | `open_world_panel` | World |
| Ctrl+U | `open_atlas_passives_screen` | Atlas passive tree |
| J | `open_social_panel` | Social |
| / | `open_market_panel` | Trade market |
| Tab | `open_map` | Overlay map |
| Enter | `chat` | Chat |
| Page Up | `zoom_in` | Zoom in |
| Page Down | `zoom_out` | Zoom out |
| F1 | `performance_overlay` | Performance overlay |
| F8 | `take_screenshot` | Screenshot |
| Z | `highlight_toggle` | Toggle item labels |
| X | `weapon_swap` | Weapon swap |
| D | `detonate_mines` | Detonate mines |
| F | `enable_key_pickup` | Pick up |

## Left out

- The mouse buttons (skill slots 1 to 3): no keycap cell.
- Shift (`attack_in_place`), Ctrl (`toggle_skill_bar`,
  `compare_item_descriptions`), Alt (`highlight`): modifier keys, no cell.
- A (`enable_corpse_targeting`), F2 to F4 and F7 (league skills): they change
  with each league.
- Path of Exile 2: B (`open_events_panel`, renamed `open_expedition_panel` in
  newer files) and Y (no Pantheon). Space also closes panels (`close_panels`),
  but the dodge roll is drawn.
- Esc: ESC has the program mark.

## Placement

As for Counter-Strike 2: every icon sits at the right edge of its key and uses
the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F-key icons use 34x40 (the area AoE2 measured for
F-key legends). The solid or wide icons (`INK` in `fetch_icons.py`) are drawn
in a smaller box inside their area. Every icon is drawn at exactly its area by
`game_set.py`, so the generator places it 1:1.

ESC shows a crest drawn by `crest()` in `fetch_icons.py` to resemble the
games' winged logos: EXILE in Bebas Neue (SIL OFL 1.1,
`ofl/bebasneue/BebasNeue-Regular.ttf` from google/fonts at commit e7db6ca)
between three feathers on each side, with an arch above and a point below.
The Path of Exile 2 crest (`program2.png`) adds two horns and three fangs, as
its logo has. Both cover the whole cell and are drawn without the ESC legend
(`program_icon_legend: false`, protocol v25). They were compared by eye with
the logos on the games' Steam pages; Grinding Gear Games' logo art is
proprietary and is not used or committed.

The skill slot keys show a swirl with the slot number (4 to 8 on Q W E R T,
9 to 13 on Ctrl+Q to Ctrl+T, DejaVu Sans Bold) in the top-left corner of the
icon area; the swirl is drawn in 24x24 so a two-digit number stays clear of it.
The flasks (1 to 5) and the temporary skills (6 and 7) carry their slot number
the same way, so no two actions share a picture.
Page Up and Page Down (Zoom in, Zoom out) are drawn by the shared concept
renderer, so their cells are the same bytes as every other zoom key.

## Icons

Each icon is drawn at keycap size by `fetch_icons.py` from the source named here.

| File | Source | Author | Licence |
|---|---|---|---|
| `skill4.png`, `skill5.png`, `skill6.png`, `skill7.png`, `skill8.png`, `skill9.png`, `skill10.png`, `skill11.png`, `skill12.png`, `skill13.png` | game-icons.net [`lorc/magic-swirl`](https://game-icons.net/1x1/lorc/magic-swirl.html) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Lorc | CC BY 3.0 |
| `flask1.png`, `flask2.png`, `flask3.png`, `flask4.png`, `flask5.png` | game-icons.net [`lorc/round-bottom-flask`](https://game-icons.net/1x1/lorc/round-bottom-flask.html) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Lorc | CC BY 3.0 |
| `tempskill1.png`, `tempskill2.png` | game-icons.net [`lorc/hourglass`](https://game-icons.net/1x1/lorc/hourglass.html) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Lorc | CC BY 3.0 |
| `weaponswap.png` | game-icons.net [`lorc/crossed-swords`](https://game-icons.net/1x1/lorc/crossed-swords.html) | Lorc | CC BY 3.0 |
| `dodge.png` | game-icons.net [`lorc/dodging`](https://game-icons.net/1x1/lorc/dodging.html) | Lorc | CC BY 3.0 |
| `mines.png` | game-icons.net [`lorc/land-mine`](https://game-icons.net/1x1/lorc/land-mine.html) | Lorc | CC BY 3.0 |
| `minions.png` | Material Symbols [`pets`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:pets) | Google | Apache-2.0 |
| `pickup.png` | game-icons.net [`lorc/hand`](https://game-icons.net/1x1/lorc/hand.html) | Lorc | CC BY 3.0 |
| `labels.png` | Material Symbols [`label`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:label) | Google | Apache-2.0 |
| `inventory.png` | Material Symbols [`backpack`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:backpack) | Google | Apache-2.0 |
| `character.png` | Material Symbols [`badge`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:badge) | Google | Apache-2.0 |
| `skills.png` | game-icons.net [`delapouite/spell-book`](https://game-icons.net/1x1/delapouite/spell-book.html) | Delapouite | CC BY 3.0 |
| `passives.png` | Material Symbols [`hub`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:hub) | Google | Apache-2.0 |
| `atlas.png` | game-icons.net [`lorc/world`](https://game-icons.net/1x1/lorc/world.html) | Lorc | CC BY 3.0 |
| `atlaspassives.png` | Material Symbols [`account_tree`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:account_tree) | Google | Apache-2.0 |
| `world.png` | Material Symbols [`explore`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:explore) | Google | Apache-2.0 |
| `social.png` | game-icons.net [`delapouite/three-friends`](https://game-icons.net/1x1/delapouite/three-friends.html) | Delapouite | CC BY 3.0 |
| `ladder.png` | Material Symbols [`leaderboard`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:leaderboard) | Google | Apache-2.0 |
| `challenges.png` | game-icons.net [`delapouite/trophy-cup`](https://game-icons.net/1x1/delapouite/trophy-cup.html) | Delapouite | CC BY 3.0 |
| `pantheon.png` | game-icons.net [`delapouite/greek-temple`](https://game-icons.net/1x1/delapouite/greek-temple.html) | Delapouite | CC BY 3.0 |
| `cosmetics.png` | game-icons.net [`delapouite/t-shirt`](https://game-icons.net/1x1/delapouite/t-shirt.html) | Delapouite | CC BY 3.0 |
| `mtxstash.png` | Material Symbols [`inventory_2`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:inventory_2) | Google | Apache-2.0 |
| `shop.png` | game-icons.net [`delapouite/shop`](https://game-icons.net/1x1/delapouite/shop.html) | Delapouite | CC BY 3.0 |
| `events.png` | game-icons.net [`delapouite/calendar`](https://game-icons.net/1x1/delapouite/calendar.html) | Delapouite | CC BY 3.0 |
| `options.png` | Material Symbols [`settings`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:settings) | Google | Apache-2.0 |
| `guidebook.png` | Material Symbols [`menu_book`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:menu_book) | Google | Apache-2.0 |
| `market.png` | Material Symbols [`currency_exchange`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:currency_exchange) | Google | Apache-2.0 |
| `league.png` | Material Symbols [`auto_awesome`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:auto_awesome) | Google | Apache-2.0 |
| `leaguepanel.png` | Material Symbols [`dashboard`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:dashboard) | Google | Apache-2.0 |
| `map.png` | Material Symbols [`map`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:map) | Google | Apache-2.0 |
| `close.png` | Material Symbols [`close`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:close) | Google | Apache-2.0 |
| `chat.png` | Material Symbols [`chat`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:chat) | Google | Apache-2.0 |
| `zoomin.png` | Material Symbols [`zoom_in`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:zoom_in) | Google | Apache-2.0 |
| `zoomout.png` | Material Symbols [`zoom_out`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:zoom_out) | Google | Apache-2.0 |
| `performance.png` | Material Symbols [`monitoring`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:monitoring) | Google | Apache-2.0 |
| `screenshot.png` | Material Symbols [`screenshot_monitor`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:screenshot_monitor) | Google | Apache-2.0 |
| `program.png` | winged crest around EXILE, drawn by `crest()` in `fetch_icons.py`, in Bebas Neue ([`ofl/bebasneue/BebasNeue-Regular.ttf`](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/bebasneue/BebasNeue-Regular.ttf)) | font: Dharma Type | font: SIL OFL 1.1 |
| `program2.png` | the crest with horns and fangs, drawn by `crest()` in `fetch_icons.py`, in Bebas Neue ([`ofl/bebasneue/BebasNeue-Regular.ttf`](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/bebasneue/BebasNeue-Regular.ttf)) | font: Dharma Type | font: SIL OFL 1.1 |
