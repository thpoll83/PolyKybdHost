# Elden Ring, Baldur's Gate 3, Cyberpunk 2077 and Helldivers 2 overlays: sources

`scripts/generate_app_overlays.py` renders `eldenring.yaml`, `bg3.yaml`,
`cyberpunk.yaml` and `helldivers2.yaml`; `fetch_icons.py` rebuilds `icons/` for
all four. Each spec lists its keys and the keys it leaves out.

| Set | Loads for |
|---|---|
| `cyberpunk_template` | Cyberpunk 2077: `Cyberpunk2077.exe`; `steam_app_1091500` under Proton |
| `helldivers2_template` | Helldivers 2: `helldivers2.exe`; `steam_app_553850` under Proton |
| `eldenring_template` | Elden Ring: `eldenring.exe`; `steam_app_1245620` under Proton |
| `bg3_template` | Baldur's Gate 3: `bg3.exe` (Vulkan), `bg3_dx11.exe`, the macOS app `Baldur's Gate 3`; `steam_app_1086940` under Proton |

None of the names was checked on an install. Cyberpunk 2077 also has a macOS
build; its process name is not known, so it gets no set there.

## Shortcut reference

| Game | Source | Grade |
|---|---|---|
| Cyberpunk 2077 | The game's own `r6/config/inputUserMappings.xml`, a 2.x copy in [jackhumbert/cyberpunk2077-input-loader](https://github.com/jackhumbert/cyberpunk2077-input-loader/blob/main/fallback/inputUserMappings.xml) (`fallback/`, commit 2fb5d55). The keys are the `IK_*` ids with an `overridableUI` attribute; the mapping names are the specs' `command:` values. | game file |
| Helldivers 2 | Arrowhead's input help page with the default values, <https://content.thehelldiversgame.com/help/inputs.md> (last modified 2024-05-16). The `Group.Action` names are the specs' `command:` values. The page is older than the vehicles. | developer list |
| Baldur's Gate 3 | <https://bg3.wiki/wiki/Controls> and Shacknews (2023-08-03, <https://www.shacknews.com/article/136508/pc-controller-buttons-baldurs-gate-3>) agree on every drawn key; photo mode F9 from Destructoid, Sportskeeda and bg3.wiki "Photo mode" (Patch 8). The default input data is in the game's `.pak` files; no public copy was found. | **unconfirmed** |
| Elden Ring | Shacknews (2022-02-24, <https://www.shacknews.com/article/128968/elden-ring-controls-and-pc-keybindings>) and Fextralife "Controls" (<https://eldenring.wiki.fextralife.com/Controls>) agree on every drawn key. Fextralife also says a Shadow of the Erdtree update moved jump to Space and dodge to Shift; no patch note confirms it. | **unconfirmed** |

All read 2026-11-27. A screenshot of each game's key-binding page should
confirm the unconfirmed sets.

## The player's bindings

The overlays draw the default keys only.

- Cyberpunk 2077: `%LOCALAPPDATA%\CD Projekt Red\Cyberpunk 2077\UserSettings.json`,
  groups `/key_bindings*`, vars named as the mapping `overridableUI` ids.
- Helldivers 2: `input_settings.config` (Steam `userdata/<id>/553850/remote/`, or
  `%APPDATA%\Arrowhead\Helldivers2\saves\<steamid>_input_settings.config`), Lua-like
  text with overrides only.
- Baldur's Gate 3: `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\PlayerProfiles\Public\inputconfig_p1.json`,
  JSON with overrides only (`{"CameraCenter": ["key:home"]}`). Most of its
  action names are not public.
- Elden Ring: not known; probably inside the binary save `ER0000.sl2`.

## Placement

As for Counter-Strike 2: every icon sits at the right edge of its key and uses
the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F-key icons use 34x40 (the area AoE2 measured for
F-key legends). Every icon is drawn at exactly its area by `game_set.py`, so
the generator places it 1:1.

Numbered slots (Cyberpunk weapon slots, the BG3 hotbar and party members) carry
their number in the icon, so no two actions share a picture
(`tests/res/f2p_overlays_distinct_test.py`).

ESC shows each logo's words in a free font close to its lettering: ELDEN /
RING and BALDUR'S / GATE III in Cinzel, CYBERPUNK / 2077 in Orbitron,
HELLDIVERS / II in Black Ops One. They are drawn by `wordmark()` in
`fetch_icons.py`, cover the whole cell and are drawn without the ESC legend
(`program_icon_legend: false`). The publishers' logo art is proprietary and is
not used or committed.

## Icons

Each icon is drawn at keycap size by `fetch_icons.py` from the source named here.

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png` | Material Symbols [`arrow_upward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_upward) | Google | Apache-2.0 |
| `back.png` | Material Symbols [`arrow_downward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_downward) | Google | Apache-2.0 |
| `left.png` | Material Symbols [`arrow_back`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_back) | Google | Apache-2.0 |
| `right.png` | Material Symbols [`arrow_forward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_forward) | Google | Apache-2.0 |
| `jump.png` | game-icons.net [`delapouite/jump-across`](https://game-icons.net/1x1/delapouite/jump-across.html) | Delapouite | CC BY 3.0 |
| `crouch.png` | game-icons.net [`delapouite/kneeling`](https://game-icons.net/1x1/delapouite/kneeling.html) | Delapouite | CC BY 3.0 |
| `prone.png` | Material Symbols [`airline_seat_flat`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:airline_seat_flat) | Google | Apache-2.0 |
| `dodge.png` | game-icons.net [`lorc/dodging`](https://game-icons.net/1x1/lorc/dodging.html) | Lorc | CC BY 3.0 |
| `walk.png` | Material Symbols [`directions_walk`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:directions_walk) | Google | Apache-2.0 |
| `climb.png` | Material Symbols [`stairs`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:stairs) | Google | Apache-2.0 |
| `sneak.png` | game-icons.net [`lorc/cloak-dagger`](https://game-icons.net/1x1/lorc/cloak-dagger.html) | Lorc | CC BY 3.0 |
| `groupsneak.png` | Material Symbols [`group_off`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:group_off) | Google | Apache-2.0 |
| `interact.png` | Material Symbols [`touch_app`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:touch_app) | Google | Apache-2.0 |
| `reload.png` | Material Symbols [`autorenew`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:autorenew) | Google | Apache-2.0 |
| `melee.png` | game-icons.net [`lorc/punch`](https://game-icons.net/1x1/lorc/punch.html) | Lorc | CC BY 3.0 |
| `heal.png` | Material Symbols [`medical_services`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:medical_services) | Google | Apache-2.0 |
| `stim.png` | game-icons.net [`lorc/syringe`](https://game-icons.net/1x1/lorc/syringe.html) | Lorc | CC BY 3.0 |
| `holster.png` | Material Symbols [`back_hand`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:back_hand) | Google | Apache-2.0 |
| `useitem.png` | game-icons.net [`lorc/drink-me`](https://game-icons.net/1x1/lorc/drink-me.html) | Lorc | CC BY 3.0 |
| `lockon.png` | Material Symbols [`my_location`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:my_location) | Google | Apache-2.0 |
| `grenade.png` | game-icons.net [`lorc/grenade`](https://game-icons.net/1x1/lorc/grenade.html) | Lorc | CC BY 3.0 |
| `throw.png` | game-icons.net [`lorc/thrown-spear`](https://game-icons.net/1x1/lorc/thrown-spear.html) | Lorc | CC BY 3.0 |
| `shove.png` | game-icons.net [`delapouite/push`](https://game-icons.net/1x1/delapouite/push.html) | Delapouite | CC BY 3.0 |
| `weaponset.png` | Material Symbols [`swap_horiz`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:swap_horiz) | Google | Apache-2.0 |
| `dualwield.png` | game-icons.net [`lorc/crossed-swords`](https://game-icons.net/1x1/lorc/crossed-swords.html) | Lorc | CC BY 3.0 |
| `groupmode.png` | Material Symbols [`link`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:link) | Google | Apache-2.0 |
| `drop.png` | Material Symbols [`file_download`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:file_download) | Google | Apache-2.0 |
| `backpack.png` | Material Symbols [`luggage`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:luggage) | Google | Apache-2.0 |
| `scanner.png` | Material Symbols [`center_focus_weak`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:center_focus_weak) | Google | Apache-2.0 |
| `cyberware.png` | Material Symbols [`memory`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:memory) | Google | Apache-2.0 |
| `phone.png` | Material Symbols [`smartphone`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:smartphone) | Google | Apache-2.0 |
| `callvehicle.png` | Material Symbols [`directions_car`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:directions_car) | Google | Apache-2.0 |
| `radio.png` | Material Symbols [`radio`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:radio) | Google | Apache-2.0 |
| `skipscene.png` | Material Symbols [`fast_forward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:fast_forward) | Google | Apache-2.0 |
| `ping.png` | game-icons.net [`delapouite/position-marker`](https://game-icons.net/1x1/delapouite/position-marker.html) | Delapouite | CC BY 3.0 |
| `emote.png` | Material Symbols [`sentiment_satisfied`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:sentiment_satisfied) | Google | Apache-2.0 |
| `talk.png` | Material Symbols [`mic`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:mic) | Google | Apache-2.0 |
| `weapon1.png`, `weapon2.png`, `weapon3.png`, `weapon4.png` | game-icons.net [`john-colburn/pistol-gun`](https://game-icons.net/1x1/john-colburn/pistol-gun.html) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | John Colburn | CC BY 3.0 |
| `primary.png` | game-icons.net [`skoll/ak47`](https://game-icons.net/1x1/skoll/ak47.html) | Skoll | CC BY 3.0 |
| `secondary.png` | game-icons.net [`john-colburn/pistol-gun`](https://game-icons.net/1x1/john-colburn/pistol-gun.html) | John Colburn | CC BY 3.0 |
| `support.png` | game-icons.net [`lorc/rocket`](https://game-icons.net/1x1/lorc/rocket.html) | Lorc | CC BY 3.0 |
| `grenadeslot.png` | game-icons.net [`sbed/grenade`](https://game-icons.net/1x1/sbed/grenade.html) | Sbed | CC BY 3.0 |
| `stratup.png` | Material Symbols [`keyboard_double_arrow_up`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:keyboard_double_arrow_up) | Google | Apache-2.0 |
| `stratdown.png` | Material Symbols [`keyboard_double_arrow_down`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:keyboard_double_arrow_down) | Google | Apache-2.0 |
| `stratleft.png` | Material Symbols [`keyboard_double_arrow_left`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:keyboard_double_arrow_left) | Google | Apache-2.0 |
| `stratright.png` | Material Symbols [`keyboard_double_arrow_right`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:keyboard_double_arrow_right) | Google | Apache-2.0 |
| `switchspell.png` | game-icons.net [`delapouite/spell-book`](https://game-icons.net/1x1/delapouite/spell-book.html) | Delapouite | CC BY 3.0 |
| `switchitem.png` | Material Symbols [`swap_vert`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:swap_vert) | Google | Apache-2.0 |
| `switchright.png` | game-icons.net [`lorc/broadsword`](https://game-icons.net/1x1/lorc/broadsword.html) | Lorc | CC BY 3.0 |
| `switchleft.png` | game-icons.net [`sbed/shield`](https://game-icons.net/1x1/sbed/shield.html) | Sbed | CC BY 3.0 |
| `endturn.png` | Material Symbols [`skip_next`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:skip_next) | Google | Apache-2.0 |
| `turnbased.png` | Material Symbols [`hourglass`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:hourglass) | Google | Apache-2.0 |
| `highlight.png` | Material Symbols [`highlight`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:highlight) | Google | Apache-2.0 |
| `examine.png` | Material Symbols [`info`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:info) | Google | Apache-2.0 |
| `rotleft.png` | Material Symbols [`rotate_left`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:rotate_left) | Google | Apache-2.0 |
| `rotright.png` | Material Symbols [`rotate_right`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:rotate_right) | Google | Apache-2.0 |
| `zoomin.png` | Material Symbols [`zoom_in`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:zoom_in) | Google | Apache-2.0 |
| `zoomout.png` | Material Symbols [`zoom_out`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:zoom_out) | Google | Apache-2.0 |
| `center.png` | Material Symbols [`filter_center_focus`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:filter_center_focus) | Google | Apache-2.0 |
| `tactical.png` | Material Symbols [`landscape`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:landscape) | Google | Apache-2.0 |
| `hotbar1.png`, `hotbar2.png`, `hotbar3.png`, `hotbar4.png`, `hotbar5.png`, `hotbar6.png`, `hotbar7.png`, `hotbar8.png`, `hotbar9.png`, `hotbar10.png`, `hotbar11.png`, `hotbar12.png` | Material Symbols [`check_box_outline_blank`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:check_box_outline_blank) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `member1.png`, `member2.png`, `member3.png`, `member4.png` | game-icons.net [`delapouite/person`](https://game-icons.net/1x1/delapouite/person.html) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Delapouite | CC BY 3.0 |
| `nextchar.png` | Material Symbols [`arrow_right`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_right) | Google | Apache-2.0 |
| `prevchar.png` | Material Symbols [`arrow_left`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_left) | Google | Apache-2.0 |
| `hub.png` | Material Symbols [`apps`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:apps) | Google | Apache-2.0 |
| `map.png` | Material Symbols [`map`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:map) | Google | Apache-2.0 |
| `journal.png` | Material Symbols [`menu_book`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:menu_book) | Google | Apache-2.0 |
| `inventory.png` | Material Symbols [`backpack`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:backpack) | Google | Apache-2.0 |
| `perks.png` | Material Symbols [`hub`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:hub) | Google | Apache-2.0 |
| `character.png` | Material Symbols [`badge`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:badge) | Google | Apache-2.0 |
| `crafting.png` | Material Symbols [`construction`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:construction) | Google | Apache-2.0 |
| `party.png` | Material Symbols [`group`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:group) | Google | Apache-2.0 |
| `spellbook.png` | Material Symbols [`auto_stories`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:auto_stories) | Google | Apache-2.0 |
| `illithid.png` | game-icons.net [`lorc/brain`](https://game-icons.net/1x1/lorc/brain.html) | Lorc | CC BY 3.0 |
| `reactions.png` | Material Symbols [`bolt`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:bolt) | Google | Apache-2.0 |
| `inspiration.png` | Material Symbols [`lightbulb`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:lightbulb) | Google | Apache-2.0 |
| `alchemy.png` | game-icons.net [`lorc/round-bottom-flask`](https://game-icons.net/1x1/lorc/round-bottom-flask.html) | Lorc | CC BY 3.0 |
| `quicksave.png` | Material Symbols [`save`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:save) | Google | Apache-2.0 |
| `quickload.png` | Material Symbols [`restore_page`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:restore_page) | Google | Apache-2.0 |
| `photo.png` | Material Symbols [`photo_camera`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:photo_camera) | Google | Apache-2.0 |
| `hideui.png` | Material Symbols [`visibility_off`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:visibility_off) | Google | Apache-2.0 |
| `eldenring.png` | ELDEN / RING, weight 700, 2 px stroke, drawn by `wordmark()` in `fetch_icons.py`, in [Cinzel](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf) | font: Natanael Gama | font: SIL OFL 1.1 |
| `bg3.png` | BALDUR'S / GATE III, weight 900, 2 px stroke, drawn by `wordmark()` in `fetch_icons.py`, in [Cinzel](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf) | font: Natanael Gama | font: SIL OFL 1.1 |
| `cyberpunk.png` | CYBERPUNK / 2077, weight 900, drawn by `wordmark()` in `fetch_icons.py`, in [Orbitron](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/orbitron/Orbitron%5Bwght%5D.ttf) | font: Matt McInerney | font: SIL OFL 1.1 |
| `helldivers2.png` | HELLDIVERS / II, drawn by `wordmark()` in `fetch_icons.py`, in [Black Ops One](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/blackopsone/BlackOpsOne-Regular.ttf) | font: James Grieshaber, Eben Sorkin | font: SIL OFL 1.1 |
