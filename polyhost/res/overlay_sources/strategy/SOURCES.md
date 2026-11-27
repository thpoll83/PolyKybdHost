# Paradox grand-strategy overlays: sources

`scripts/generate_app_overlays.py` renders `eu4.yaml`, `eu5.yaml`, `ck3.yaml`,
`hoi4.yaml`, `stellaris.yaml` and `vic3.yaml`; `fetch_icons.py` rebuilds
`icons/` for all six. Each spec lists its keys and the keys it leaves out.

| Set | Game | Loads for | Steam app |
|---|---|---|---|
| `eu4_template` | Europa Universalis IV | `eu4` (Windows, Linux, macOS) | 236850 |
| `eu5_template` | Europa Universalis V | `binaries/eu5.exe` (Windows only on Steam) | 3450310 |
| `ck3_template` | Crusader Kings III | `binaries/ck3` | 1158310 |
| `hoi4_template` | Hearts of Iron IV | `hoi4` | 394360 |
| `stellaris_template` | Stellaris | `stellaris` | 281990 |
| `vic3_template` | Victoria 3 | `binaries/victoria3` | 529340 |

The executable names are from `launcher-settings.json` copies and modding tools
(pdx-tools `src/pdx-assets/src/lib.rs`, IronyModManager `Constants.cs`,
ParadoxGameConverters CK3toEU5). None was checked on an install.

## Shortcut reference

Read 2026-11-27. The game files were read from public mirrors; none is committed.

| Game | Source | Grade |
|---|---|---|
| CK3 1.21.0.3 | `game/gui/shortcuts.shortcuts` in jesec/ck3-mod-base @ e529e00 | game file |
| Victoria 3 1.15 | `game/input_profile/default.profile` and `gui/shortcuts.shortcuts` in jink47787/Historical_MP_Series_Vic3 (commit f8e3ee6c, "update 1.15") | game file |
| EU5 | `loading_screen/input_profile/default.profile` in HLJSXK/eu5-modding-base @ 33e60f14 (files collected 2026-10-13); panel names from `in_game/gui/panels/left_panel/left_panel.gui` | game file |
| EU4 1.36.2 | `interface/*.gui` in AlejandroGiner/eu4 @ aea8b49. Pause, speed, capital, chat and screenshot keys: <https://eu4.paradoxwikis.com/Controls> (verified 1.24) | game file, engine keys wiki |
| HOI4 1.20 | The value most of 40 mod copies of `interface/topbar.gui` and of `interface/mapmodes_interface.gui` agree on (Kaiserreich 1.20.1, Millennium Dawn); engine keys from <https://hoi4.paradoxwikis.com/Hotkeys> | mod copies + wiki |
| Stellaris 4.x | Map modes from `common/map_modes/00_map_modes.txt` (3.10 and 3.12 copies); outliner, search, home, chat and help from `interface/outliner.gui` and `interface/main_bottom.gui` (all mod copies agree); the rest from <https://stellaris.paradoxwikis.com/Hotkeys> | game file + wiki |

Notes on single keys:

- EU4 `+` (faster) is drawn on the = key, where `+` is on a US layout.
- EU4's Q to P are map-mode slots whose content the player sets, so their icons
  carry the slot number.
- HOI4 Ctrl+Q (faction) is in 22 of the 40 copies, all from newer versions.
- CK3 1.21 moved Court from F5 to F6 and put Trade on F5.

## The player's bindings

The overlays draw the default keys only. CK3, EU4, HOI4 and Stellaris have no
in-game rebinding. Victoria 3 and EU5 can rebind in Settings > Input bindings
and store physical key positions (USB HID scancodes, the usage IDs QMK uses).
Where they save the player's profile is not confirmed yet (one secondary source
gives `Documents/Paradox Interactive/Victoria 3/input_profiles/default.profile`).

## Placement

As for Counter-Strike 2: every icon sits at the right edge of its key and uses
the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F-key icons use 34x40 (the area AoE2 measured for
F-key legends). Every icon is drawn at exactly its area by `game_set.py`, so
the generator places it 1:1.

Numbered keys (speed 1-5, EU5 control groups, EU4 map-mode slots) carry their
number in the icon, so no two actions share a picture
(`tests/res/f2p_overlays_distinct_test.py`).

ESC shows each game's name in Cinzel, a serif close to the Paradox logos'
capitals. The marks are drawn by `mark()` in `fetch_icons.py`, cover the whole
cell and are drawn without the ESC legend (`program_icon_legend: false`). No
Paradox logo art is used or committed.

## Icons

Each icon is drawn at keycap size by `fetch_icons.py` from the source named here.

| File | Source | Author | Licence |
|---|---|---|---|
| `pause.png` | Material Symbols [`pause`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:pause) | Google | Apache-2.0 |
| `pauseonly.png` | Material Symbols [`pause_circle`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:pause_circle) | Google | Apache-2.0 |
| `unpause.png` | Material Symbols [`play_arrow`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:play_arrow) | Google | Apache-2.0 |
| `faster.png` | Material Symbols [`fast_forward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:fast_forward) | Google | Apache-2.0 |
| `slower.png` | Material Symbols [`fast_rewind`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:fast_rewind) | Google | Apache-2.0 |
| `nextday.png` | Material Symbols [`skip_next`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:skip_next) | Google | Apache-2.0 |
| `speed1.png`, `speed2.png`, `speed3.png`, `speed4.png`, `speed5.png` | Material Symbols [`speed`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:speed) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `group0.png`, `group1.png`, `group2.png`, `group3.png`, `group4.png`, `group5.png`, `group6.png`, `group7.png`, `group8.png`, `group9.png` | Material Symbols [`group_work`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:group_work) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `mapslot1.png`, `mapslot2.png`, `mapslot3.png`, `mapslot4.png`, `mapslot5.png`, `mapslot6.png`, `mapslot7.png`, `mapslot8.png`, `mapslot9.png`, `mapslot10.png` | Material Symbols [`map`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:map) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `panup.png` | Material Symbols [`arrow_upward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_upward) | Google | Apache-2.0 |
| `pandown.png` | Material Symbols [`arrow_downward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_downward) | Google | Apache-2.0 |
| `panleft.png` | Material Symbols [`arrow_back`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_back) | Google | Apache-2.0 |
| `panright.png` | Material Symbols [`arrow_forward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_forward) | Google | Apache-2.0 |
| `zoomin.png` | Material Symbols [`zoom_in`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:zoom_in) | Google | Apache-2.0 |
| `zoomout.png` | Material Symbols [`zoom_out`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:zoom_out) | Google | Apache-2.0 |
| `maxzoom.png` | Material Symbols [`zoom_out_map`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:zoom_out_map) | Google | Apache-2.0 |
| `scrollup.png` | Material Symbols [`keyboard_double_arrow_up`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:keyboard_double_arrow_up) | Google | Apache-2.0 |
| `scrolldown.png` | Material Symbols [`keyboard_double_arrow_down`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:keyboard_double_arrow_down) | Google | Apache-2.0 |
| `capital.png` | Material Symbols [`home_pin`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:home_pin) | Google | Apache-2.0 |
| `focus.png` | Material Symbols [`center_focus_strong`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:center_focus_strong) | Google | Apache-2.0 |
| `rotation.png` | Material Symbols [`3d_rotation`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:3d_rotation) | Google | Apache-2.0 |
| `cycle.png` | Material Symbols [`autorenew`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:autorenew) | Google | Apache-2.0 |
| `back.png` | Material Symbols [`arrow_back_ios`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_back_ios) | Google | Apache-2.0 |
| `forward.png` | Material Symbols [`arrow_forward_ios`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_forward_ios) | Google | Apache-2.0 |
| `find.png` | Material Symbols [`search`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:search) | Google | Apache-2.0 |
| `findtitle.png` | Material Symbols [`manage_search`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:manage_search) | Google | Apache-2.0 |
| `charfinder.png` | Material Symbols [`person_search`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:person_search) | Google | Apache-2.0 |
| `searchfocus.png` | Material Symbols [`pageview`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:pageview) | Google | Apache-2.0 |
| `ledger.png` | Material Symbols [`table_chart`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:table_chart) | Google | Apache-2.0 |
| `encyclopedia.png` | Material Symbols [`menu_book`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:menu_book) | Google | Apache-2.0 |
| `outliner.png` | Material Symbols [`list`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:list) | Google | Apache-2.0 |
| `chat.png` | Material Symbols [`chat`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:chat) | Google | Apache-2.0 |
| `help.png` | Material Symbols [`help`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:help) | Google | Apache-2.0 |
| `mapmenu.png` | Material Symbols [`layers`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:layers) | Google | Apache-2.0 |
| `confirm.png` | Material Symbols [`check`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:check) | Google | Apache-2.0 |
| `decline.png` | Material Symbols [`close`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:close) | Google | Apache-2.0 |
| `undo.png` | Material Symbols [`undo`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:undo) | Google | Apache-2.0 |
| `redo.png` | Material Symbols [`redo`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:redo) | Google | Apache-2.0 |
| `alerts.png` | Material Symbols [`notifications`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:notifications) | Google | Apache-2.0 |
| `journal.png` | Material Symbols [`import_contacts`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:import_contacts) | Google | Apache-2.0 |
| `situation.png` | Material Symbols [`report`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:report) | Google | Apache-2.0 |
| `actionlist.png` | Material Symbols [`pending_actions`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:pending_actions) | Google | Apache-2.0 |
| `macro.png` | Material Symbols [`view_module`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:view_module) | Google | Apache-2.0 |
| `screenshot.png` | Material Symbols [`screenshot_monitor`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:screenshot_monitor) | Google | Apache-2.0 |
| `mapshot.png` | Material Symbols [`panorama`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:panorama) | Google | Apache-2.0 |
| `hidegui.png` | Material Symbols [`visibility_off`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:visibility_off) | Google | Apache-2.0 |
| `lockcam.png` | Material Symbols [`lock`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:lock) | Google | Apache-2.0 |
| `country.png` | Material Symbols [`flag`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flag) | Google | Apache-2.0 |
| `court.png` | game-icons.net [`delapouite/throne-king`](https://game-icons.net/1x1/delapouite/throne-king.html) | Delapouite | CC BY 3.0 |
| `royalcourt.png` | Material Symbols [`workspace_premium`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:workspace_premium) | Google | Apache-2.0 |
| `government.png` | Material Symbols [`account_balance`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:account_balance) | Google | Apache-2.0 |
| `diplomacy.png` | Material Symbols [`handshake`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:handshake) | Google | Apache-2.0 |
| `economy.png` | Material Symbols [`payments`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:payments) | Google | Apache-2.0 |
| `trade.png` | Material Symbols [`currency_exchange`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:currency_exchange) | Google | Apache-2.0 |
| `logistics.png` | Material Symbols [`local_shipping`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:local_shipping) | Google | Apache-2.0 |
| `technology.png` | Material Symbols [`science`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:science) | Google | Apache-2.0 |
| `ideas.png` | Material Symbols [`lightbulb`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:lightbulb) | Google | Apache-2.0 |
| `missions.png` | Material Symbols [`task_alt`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:task_alt) | Google | Apache-2.0 |
| `decisions.png` | Material Symbols [`gavel`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:gavel) | Google | Apache-2.0 |
| `stability.png` | Material Symbols [`balance`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:balance) | Google | Apache-2.0 |
| `religion.png` | Material Symbols [`church`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:church) | Google | Apache-2.0 |
| `military.png` | Material Symbols [`swords`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:swords) | Google | Apache-2.0 |
| `subjects.png` | Material Symbols [`account_tree`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:account_tree) | Google | Apache-2.0 |
| `estates.png` | Material Symbols [`groups`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:groups) | Google | Apache-2.0 |
| `age.png` | Material Symbols [`hourglass_top`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:hourglass_top) | Google | Apache-2.0 |
| `greatpowers.png` | Material Symbols [`star_rate`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:star_rate) | Google | Apache-2.0 |
| `production.png` | Material Symbols [`factory`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:factory) | Google | Apache-2.0 |
| `society.png` | Material Symbols [`diversity_3`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:diversity_3) | Google | Apache-2.0 |
| `geography.png` | Material Symbols [`public`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:public) | Google | Apache-2.0 |
| `content.png` | Material Symbols [`article`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:article) | Google | Apache-2.0 |
| `character.png` | Material Symbols [`person`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:person) | Google | Apache-2.0 |
| `realm.png` | Material Symbols [`castle`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:castle) | Google | Apache-2.0 |
| `council.png` | Material Symbols [`group`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:group) | Google | Apache-2.0 |
| `intrigue.png` | game-icons.net [`lorc/cloak-dagger`](https://game-icons.net/1x1/lorc/cloak-dagger.html) | Lorc | CC BY 3.0 |
| `factions.png` | Material Symbols [`campaign`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:campaign) | Google | Apache-2.0 |
| `openholding.png` | Material Symbols [`location_city`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:location_city) | Google | Apache-2.0 |
| `domicile.png` | Material Symbols [`house`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:house) | Google | Apache-2.0 |
| `culture.png` | Material Symbols [`palette`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:palette) | Google | Apache-2.0 |
| `activities.png` | Material Symbols [`hiking`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:hiking) | Google | Apache-2.0 |
| `warview.png` | Material Symbols [`military_tech`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:military_tech) | Google | Apache-2.0 |
| `faction.png` | Material Symbols [`diversity_1`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:diversity_1) | Google | Apache-2.0 |
| `intel.png` | Material Symbols [`radar`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:radar) | Google | Apache-2.0 |
| `market.png` | Material Symbols [`storefront`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:storefront) | Google | Apache-2.0 |
| `construction.png` | Material Symbols [`construction`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:construction) | Google | Apache-2.0 |
| `recruit.png` | Material Symbols [`engineering`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:engineering) | Google | Apache-2.0 |
| `navy.png` | Material Symbols [`anchor`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:anchor) | Google | Apache-2.0 |
| `air.png` | Material Symbols [`flight`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flight) | Google | Apache-2.0 |
| `budget.png` | Material Symbols [`savings`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:savings) | Google | Apache-2.0 |
| `buildings.png` | Material Symbols [`apartment`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:apartment) | Google | Apache-2.0 |
| `powerbloc.png` | Material Symbols [`hub`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:hub) | Google | Apache-2.0 |
| `companies.png` | Material Symbols [`domain`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:domain) | Google | Apache-2.0 |
| `population.png` | Material Symbols [`person_pin`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:person_pin) | Google | Apache-2.0 |
| `queuepause.png` | Material Symbols [`pending`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:pending) | Google | Apache-2.0 |
| `map_realms.png` | Material Symbols [`flag_circle`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flag_circle) | Google | Apache-2.0 |
| `map_religions.png` | Material Symbols [`temple_buddhist`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:temple_buddhist) | Google | Apache-2.0 |
| `map_cultures.png` | Material Symbols [`language`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:language) | Google | Apache-2.0 |
| `map_houses.png` | Material Symbols [`family_restroom`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:family_restroom) | Google | Apache-2.0 |
| `map_duchies.png` | Material Symbols [`shield`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:shield) | Google | Apache-2.0 |
| `map_kingdoms.png` | Material Symbols [`crown`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:crown) | Google | Apache-2.0 |
| `map_empires.png` | Material Symbols [`fort`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:fort) | Google | Apache-2.0 |
| `map_hegemonies.png` | Material Symbols [`travel_explore`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:travel_explore) | Google | Apache-2.0 |
| `map_plagues.png` | Material Symbols [`coronavirus`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:coronavirus) | Google | Apache-2.0 |
| `map_legends.png` | Material Symbols [`auto_stories`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:auto_stories) | Google | Apache-2.0 |
| `map_default.png` | Material Symbols [`public_off`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:public_off) | Google | Apache-2.0 |
| `map_naval.png` | Material Symbols [`sailing`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:sailing) | Google | Apache-2.0 |
| `map_air.png` | Material Symbols [`cloud`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:cloud) | Google | Apache-2.0 |
| `map_supply.png` | Material Symbols [`inventory_2`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:inventory_2) | Google | Apache-2.0 |
| `map_terrain.png` | Material Symbols [`landscape`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:landscape) | Google | Apache-2.0 |
| `map_resistance.png` | Material Symbols [`local_police`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:local_police) | Google | Apache-2.0 |
| `map_compliance.png` | Material Symbols [`policy`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:policy) | Google | Apache-2.0 |
| `map_resource.png` | Material Symbols [`energy_savings_leaf`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:energy_savings_leaf) | Google | Apache-2.0 |
| `map_infrastructure.png` | Material Symbols [`route`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:route) | Google | Apache-2.0 |
| `map_factions.png` | Material Symbols [`flag_2`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flag_2) | Google | Apache-2.0 |
| `map_counters.png` | Material Symbols [`badge`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:badge) | Google | Apache-2.0 |
| `map_colours.png` | Material Symbols [`brightness_6`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:brightness_6) | Google | Apache-2.0 |
| `map_battleplans.png` | Material Symbols [`timeline`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:timeline) | Google | Apache-2.0 |
| `map_daynight.png` | Material Symbols [`nightlight`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:nightlight) | Google | Apache-2.0 |
| `map_empire.png` | Material Symbols [`flag_circle`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flag_circle) | Google | Apache-2.0 |
| `map_diplomatic.png` | Material Symbols [`waving_hand`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:waving_hand) | Google | Apache-2.0 |
| `map_opinion.png` | Material Symbols [`thumbs_up_down`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:thumbs_up_down) | Google | Apache-2.0 |
| `map_attitude.png` | Material Symbols [`psychology`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:psychology) | Google | Apache-2.0 |
| `map_neighbor.png` | Material Symbols [`scatter_plot`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:scatter_plot) | Google | Apache-2.0 |
| `map_intel.png` | Material Symbols [`visibility`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:visibility) | Google | Apache-2.0 |
| `galaxy.png` | Material Symbols [`travel_explore`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:travel_explore) | Google | Apache-2.0 |
| `lens_production.png` | Material Symbols [`precision_manufacturing`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:precision_manufacturing) | Google | Apache-2.0 |
| `lens_political.png` | Material Symbols [`how_to_vote`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:how_to_vote) | Google | Apache-2.0 |
| `lens_diplomatic.png` | Material Symbols [`waving_hand`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:waving_hand) | Google | Apache-2.0 |
| `lens_military.png` | Material Symbols [`military_tech`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:military_tech) | Google | Apache-2.0 |
| `lens_trade.png` | Material Symbols [`sailing`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:sailing) | Google | Apache-2.0 |
| `eu4.png` | EUROPA IV / UNIVERSALIS, weight 900, 2 px stroke, drawn by `mark()` in `fetch_icons.py`, in [Cinzel](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf) | font: Natanael Gama | font: SIL OFL 1.1 |
| `eu5.png` | EUROPA V / UNIVERSALIS, weight 900, 2 px stroke, drawn by `mark()` in `fetch_icons.py`, in [Cinzel](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf) | font: Natanael Gama | font: SIL OFL 1.1 |
| `ck3.png` | CRUSADER / KINGS III, weight 900, 2 px stroke, drawn by `mark()` in `fetch_icons.py`, in [Cinzel](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf) | font: Natanael Gama | font: SIL OFL 1.1 |
| `hoi4.png` | HEARTS OF / IRON IV, weight 900, 2 px stroke, drawn by `mark()` in `fetch_icons.py`, in [Cinzel](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf) | font: Natanael Gama | font: SIL OFL 1.1 |
| `stellaris.png` | STELLARIS, weight 900, 2 px stroke, drawn by `mark()` in `fetch_icons.py`, in [Cinzel](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf) | font: Natanael Gama | font: SIL OFL 1.1 |
| `vic3.png` | VICTORIA / III, weight 900, 2 px stroke, drawn by `mark()` in `fetch_icons.py`, in [Cinzel](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf) | font: Natanael Gama | font: SIL OFL 1.1 |
