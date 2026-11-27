# World of Warcraft and Final Fantasy XIV overlays: sources

`scripts/generate_app_overlays.py` renders `wow.yaml` and `ffxiv.yaml`;
`fetch_icons.py` rebuilds `icons/` for both. Each spec lists its keys and the
keys it leaves out.

| Set | Loads for |
|---|---|
| `wow_template` (2 files) | World of Warcraft, retail: `Wow.exe` (Windows, in `_retail_`), the `World of Warcraft` app (macOS) |
| `ffxiv_template` (2 files) | Final Fantasy XIV: `ffxiv_dx11.exe` (Windows, and inside the macOS app's Wine wrapper); `steam_app_39210` under Proton |

The second file of each set (`.combo`) holds the keys with two modifiers
(Ctrl+Shift+Tab, Ctrl+Shift+End, Alt+Shift+L ...).

The WoW names are from Blizzard's support pages and forum posts; the macOS
app name is from forum posts only. The FFXIV macOS detail is from a process
listing in a Square Enix forum post and the Lodestone Mac download page
(<https://na.finalfantasyxiv.com/mac/download/>). None of the names was
checked on an install. The WoW Classic clients (`WowClassic.exe`) have other
default keys and get no set.

## Shortcut reference

### World of Warcraft

The client's own defaults: `WTF/DefaultBindings.wtf` in the game's CASC
storage (FileDataID 841796, named in the wowdev/wow-listfile), build
12.1.5.70961, downloaded from the wago.tools CASC API
(`https://wago.tools/api/casc/841796?download&version=12.1.5.70961`) on
2026-11-27. The file is Blizzard's and is not committed. Each line is
`bind <KEY> <COMMAND>`; the specs' `command:` values are its command names.

`Interface/AddOns/Blizzard_FrameXML/Bindings_Standard.xml` in
Gethe/wow-ui-source (live branch) names the actions and marks the debug ones
(`debug="true" hidden="true"`), which the spec leaves out.

### Final Fantasy XIV

The official Game Manual, "Keyboard Controls", updated 2026-04-28:
<https://na.finalfantasyxiv.com/game_manual/operation/>, read 2026-11-27.

Not in the manual, so **unconfirmed**:

- Hotbar 1 on 1 to 0, - and =: ggrecon and Icy Veins player guides.
- Shift+1 to Shift+3 (switch to hotbar 1 to 3) and Shift+Up / Shift+Down
  (cycle hotbars): <https://ffxiv.consolegameswiki.com/wiki/Controls> only.

A screenshot of the game's Keybind page should confirm these.

## The player's bindings

The overlays draw the default keys only.

- World of Warcraft writes `WTF/Account/<ACCOUNT>/bindings-cache.wtf` (and one
  per character under `<Realm>/<Character>/`). It holds only the player's
  changes from the defaults (a removed default is `bind <KEY> NONE`), so a
  reader would apply it on top of `DefaultBindings.wtf`. The game also syncs
  the bindings to Blizzard's servers by default (`synchronizeBindings`), so
  the file on disk can be out of date.
- Final Fantasy XIV writes `Documents/My Games/FINAL FANTASY XIV - A Realm
  Reborn/FFXIV_CHR<id>/KEYBIND.DAT`. Its header (file type `0x00650003`, then
  the size minus 32) and the XOR with `0x73` of the data are described by
  EmperorArthur/FFXIV_Settings and the libxivdat crate; the records are not.

## Placement

As for Counter-Strike 2: every icon sits at the right edge of its key and uses
the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F-key icons use 34x40 (the area AoE2 measured for
F-key legends). Every icon is drawn at exactly its area by `game_set.py`, so
the generator places it 1:1.

Numbered slots (action buttons, bonus and stance bar, party members, party
pets, bags, hotbar sets) carry their number in the icon, so no two actions
share a picture (`tests/res/f2p_overlays_distinct_test.py`).

ESC shows each logo's words in Cinzel at weight 900, thickened by a 2 px
stroke (of 8 per keycap pixel): WORLD OF over WARCRAFT, and FINAL FANTASY
over XIV. They are drawn by `wordmark()` in `fetch_icons.py`, cover the whole
cell and are drawn without the ESC legend (`program_icon_legend: false`).
Blizzard's and Square Enix's logo art is proprietary and is not used or
committed.

## Icons

Each icon is drawn at keycap size by `fetch_icons.py` from the source named here.

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png` | Material Symbols [`arrow_upward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_upward) | Google | Apache-2.0 |
| `back.png` | Material Symbols [`arrow_downward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_downward) | Google | Apache-2.0 |
| `strafeleft.png` | Material Symbols [`arrow_back`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_back) | Google | Apache-2.0 |
| `straferight.png` | Material Symbols [`arrow_forward`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_forward) | Google | Apache-2.0 |
| `turnleft.png` | Material Symbols [`rotate_left`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:rotate_left) | Google | Apache-2.0 |
| `turnright.png` | Material Symbols [`rotate_right`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:rotate_right) | Google | Apache-2.0 |
| `jump.png` | game-icons.net [`delapouite/jump-across`](https://game-icons.net/1x1/delapouite/jump-across.html) | Delapouite | CC BY 3.0 |
| `descend.png` | Material Symbols [`south`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:south) | Google | Apache-2.0 |
| `autorun.png` | Material Symbols [`directions_run`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:directions_run) | Google | Apache-2.0 |
| `sit.png` | Material Symbols [`chair`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:chair) | Google | Apache-2.0 |
| `sheathe.png` | game-icons.net [`lorc/broadsword`](https://game-icons.net/1x1/lorc/broadsword.html) | Lorc | CC BY 3.0 |
| `pitchup.png` | Material Symbols [`flight_takeoff`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flight_takeoff) | Google | Apache-2.0 |
| `pitchdown.png` | Material Symbols [`flight_land`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flight_land) | Google | Apache-2.0 |
| `targetenemy.png` | Material Symbols [`my_location`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:my_location) | Google | Apache-2.0 |
| `prevenemy.png` | Material Symbols [`location_searching`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:location_searching) | Google | Apache-2.0 |
| `targetfriend.png` | Material Symbols [`person_search`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:person_search) | Google | Apache-2.0 |
| `prevfriend.png` | Material Symbols [`person_pin`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:person_pin) | Google | Apache-2.0 |
| `targetself.png` | Material Symbols [`person`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:person) | Google | Apache-2.0 |
| `party1.png`, `party2.png`, `party3.png`, `party4.png`, `party5.png`, `party6.png`, `party7.png`, `party8.png` | game-icons.net [`delapouite/person`](https://game-icons.net/1x1/delapouite/person.html) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Delapouite | CC BY 3.0 |
| `targetpet.png` | Material Symbols [`pets`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:pets) | Google | Apache-2.0 |
| `partypet1.png`, `partypet2.png`, `partypet3.png`, `partypet4.png` | Material Symbols [`cruelty_free`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:cruelty_free) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `interact.png` | Material Symbols [`touch_app`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:touch_app) | Google | Apache-2.0 |
| `ping.png` | game-icons.net [`delapouite/position-marker`](https://game-icons.net/1x1/delapouite/position-marker.html) | Delapouite | CC BY 3.0 |
| `nameplates.png` | Material Symbols [`label`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:label) | Google | Apache-2.0 |
| `friendplates.png` | Material Symbols [`label_important`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:label_important) | Google | Apache-2.0 |
| `allplates.png` | Material Symbols [`new_label`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:new_label) | Google | Apache-2.0 |
| `petattack.png` | game-icons.net [`lorc/claw-slashes`](https://game-icons.net/1x1/lorc/claw-slashes.html) | Lorc | CC BY 3.0 |
| `facetarget.png` | Material Symbols [`center_focus_strong`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:center_focus_strong) | Google | Apache-2.0 |
| `focustarget.png` | Material Symbols [`filter_center_focus`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:filter_center_focus) | Google | Apache-2.0 |
| `targetfocus.png` | Material Symbols [`adjust`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:adjust) | Google | Apache-2.0 |
| `nearestenemy.png` | Material Symbols [`point_scan`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:point_scan) | Google | Apache-2.0 |
| `nearestnpc.png` | Material Symbols [`person_pin_circle`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:person_pin_circle) | Google | Apache-2.0 |
| `targetoftarget.png` | Material Symbols [`double_arrow`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:double_arrow) | Google | Apache-2.0 |
| `attacker.png` | Material Symbols [`warning`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:warning) | Google | Apache-2.0 |
| `targetfilter.png` | Material Symbols [`filter_alt`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:filter_alt) | Google | Apache-2.0 |
| `action1.png`, `action2.png`, `action3.png`, `action4.png`, `action5.png`, `action6.png`, `action7.png`, `action8.png`, `action9.png`, `action10.png`, `action11.png`, `action12.png` | Material Symbols [`check_box_outline_blank`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:check_box_outline_blank) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `bonus1.png`, `bonus2.png`, `bonus3.png`, `bonus4.png`, `bonus5.png`, `bonus6.png`, `bonus7.png`, `bonus8.png`, `bonus9.png`, `bonus10.png` | Material Symbols [`star`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:star) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `stance1.png`, `stance2.png`, `stance3.png`, `stance4.png`, `stance5.png`, `stance6.png`, `stance7.png`, `stance8.png`, `stance9.png`, `stance10.png` | Material Symbols [`self_improvement`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:self_improvement) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `hotbarset1.png`, `hotbarset2.png`, `hotbarset3.png` | Material Symbols [`view_agenda`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:view_agenda) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `hotbarup.png` | Material Symbols [`keyboard_double_arrow_up`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:keyboard_double_arrow_up) | Google | Apache-2.0 |
| `hotbardown.png` | Material Symbols [`keyboard_double_arrow_down`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:keyboard_double_arrow_down) | Google | Apache-2.0 |
| `allbags.png` | Material Symbols [`inventory_2`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:inventory_2) | Google | Apache-2.0 |
| `backpack.png` | Material Symbols [`backpack`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:backpack) | Google | Apache-2.0 |
| `bag1.png`, `bag2.png`, `bag3.png`, `bag4.png` | Material Symbols [`shopping_bag`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:shopping_bag) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `character.png` | Material Symbols [`badge`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:badge) | Google | Apache-2.0 |
| `itemcompare.png` | Material Symbols [`compare_arrows`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:compare_arrows) | Google | Apache-2.0 |
| `spellbook.png` | Material Symbols [`auto_stories`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:auto_stories) | Google | Apache-2.0 |
| `petbook.png` | Material Symbols [`book_5`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:book_5) | Google | Apache-2.0 |
| `collections.png` | Material Symbols [`collections_bookmark`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:collections_bookmark) | Google | Apache-2.0 |
| `talents.png` | Material Symbols [`hub`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:hub) | Google | Apache-2.0 |
| `pvp.png` | Material Symbols [`swords`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:swords) | Google | Apache-2.0 |
| `reputation.png` | Material Symbols [`handshake`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:handshake) | Google | Apache-2.0 |
| `professions.png` | Material Symbols [`construction`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:construction) | Google | Apache-2.0 |
| `social.png` | game-icons.net [`delapouite/three-friends`](https://game-icons.net/1x1/delapouite/three-friends.html) | Delapouite | CC BY 3.0 |
| `guild.png` | game-icons.net [`lorc/checked-shield`](https://game-icons.net/1x1/lorc/checked-shield.html) | Lorc | CC BY 3.0 |
| `adventureguide.png` | Material Symbols [`menu_book`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:menu_book) | Google | Apache-2.0 |
| `groupfinder.png` | Material Symbols [`group_add`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:group_add) | Google | Apache-2.0 |
| `dungeons.png` | Material Symbols [`castle`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:castle) | Google | Apache-2.0 |
| `achievements.png` | game-icons.net [`delapouite/trophy-cup`](https://game-icons.net/1x1/delapouite/trophy-cup.html) | Delapouite | CC BY 3.0 |
| `statistics.png` | Material Symbols [`leaderboard`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:leaderboard) | Google | Apache-2.0 |
| `questlog.png` | Material Symbols [`history_edu`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:history_edu) | Google | Apache-2.0 |
| `worldmap.png` | Material Symbols [`map`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:map) | Google | Apache-2.0 |
| `minimap.png` | Material Symbols [`explore`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:explore) | Google | Apache-2.0 |
| `housing.png` | Material Symbols [`cottage`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:cottage) | Google | Apache-2.0 |
| `housingeditor.png` | Material Symbols [`architecture`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:architecture) | Google | Apache-2.0 |
| `equipment.png` | Material Symbols [`checkroom`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:checkroom) | Google | Apache-2.0 |
| `chatchannels.png` | Material Symbols [`forum`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:forum) | Google | Apache-2.0 |
| `channelpullout.png` | Material Symbols [`open_in_new`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:open_in_new) | Google | Apache-2.0 |
| `scoreboard.png` | Material Symbols [`scoreboard`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:scoreboard) | Google | Apache-2.0 |
| `currency.png` | Material Symbols [`payments`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:payments) | Google | Apache-2.0 |
| `armoury.png` | Material Symbols [`shield`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:shield) | Google | Apache-2.0 |
| `saddlebag.png` | Material Symbols [`luggage`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:luggage) | Google | Apache-2.0 |
| `linkshells.png` | Material Symbols [`lan`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:lan) | Google | Apache-2.0 |
| `signs.png` | Material Symbols [`flag`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flag) | Google | Apache-2.0 |
| `waymarks.png` | Material Symbols [`pin_drop`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:pin_drop) | Google | Apache-2.0 |
| `orchestrion.png` | Material Symbols [`music_note`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:music_note) | Google | Apache-2.0 |
| `timers.png` | Material Symbols [`timer`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:timer) | Google | Apache-2.0 |
| `charconfig.png` | Material Symbols [`manage_accounts`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:manage_accounts) | Google | Apache-2.0 |
| `sysconfig.png` | Material Symbols [`settings`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:settings) | Google | Apache-2.0 |
| `craftlog.png` | Material Symbols [`handyman`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:handyman) | Google | Apache-2.0 |
| `gatherlog.png` | Material Symbols [`forest`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:forest) | Google | Apache-2.0 |
| `huntlog.png` | Material Symbols [`cruelty_free`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:cruelty_free) | Google | Apache-2.0 |
| `fishlog.png` | Material Symbols [`phishing`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:phishing) | Google | Apache-2.0 |
| `fishguide.png` | Material Symbols [`set_meal`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:set_meal) | Google | Apache-2.0 |
| `chat.png` | Material Symbols [`chat`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:chat) | Google | Apache-2.0 |
| `slash.png` | Material Symbols [`terminal`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:terminal) | Google | Apache-2.0 |
| `reply.png` | Material Symbols [`reply`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:reply) | Google | Apache-2.0 |
| `replyback.png` | Material Symbols [`reply_all`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:reply_all) | Google | Apache-2.0 |
| `chatup.png` | Material Symbols [`expand_less`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:expand_less) | Google | Apache-2.0 |
| `chatdown.png` | Material Symbols [`expand_more`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:expand_more) | Google | Apache-2.0 |
| `chatbottom.png` | Material Symbols [`low_priority`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:low_priority) | Google | Apache-2.0 |
| `logup.png` | Material Symbols [`keyboard_double_arrow_up`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:keyboard_double_arrow_up) | Google | Apache-2.0 |
| `logdown.png` | Material Symbols [`keyboard_double_arrow_down`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:keyboard_double_arrow_down) | Google | Apache-2.0 |
| `logbottom.png` | Material Symbols [`vertical_align_bottom`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:vertical_align_bottom) | Google | Apache-2.0 |
| `say.png` | Material Symbols [`chat_bubble`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:chat_bubble) | Google | Apache-2.0 |
| `shout.png` | Material Symbols [`campaign`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:campaign) | Google | Apache-2.0 |
| `partychat.png` | Material Symbols [`group`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:group) | Google | Apache-2.0 |
| `yell.png` | Material Symbols [`record_voice_over`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:record_voice_over) | Google | Apache-2.0 |
| `fcchat.png` | game-icons.net [`lorc/checked-shield`](https://game-icons.net/1x1/lorc/checked-shield.html) | Lorc | CC BY 3.0 |
| `pvpchat.png` | Material Symbols [`swords`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:swords) | Google | Apache-2.0 |
| `alliancechat.png` | Material Symbols [`diversity_3`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:diversity_3) | Google | Apache-2.0 |
| `novicechat.png` | Material Symbols [`eco`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:eco) | Google | Apache-2.0 |
| `lschat.png` | Material Symbols [`link`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:link) | Google | Apache-2.0 |
| `lschatback.png` | Material Symbols [`link_off`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:link_off) | Google | Apache-2.0 |
| `cwlschat.png` | Material Symbols [`public`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:public) | Google | Apache-2.0 |
| `cwlschatback.png` | Material Symbols [`public_off`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:public_off) | Google | Apache-2.0 |
| `camup.png` | Material Symbols [`expand_less`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:expand_less) | Google | Apache-2.0 |
| `camdown.png` | Material Symbols [`expand_more`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:expand_more) | Google | Apache-2.0 |
| `camleft.png` | Material Symbols [`chevron_left`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:chevron_left) | Google | Apache-2.0 |
| `camright.png` | Material Symbols [`chevron_right`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:chevron_right) | Google | Apache-2.0 |
| `tiltup.png` | Material Symbols [`arrow_circle_up`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_circle_up) | Google | Apache-2.0 |
| `tiltdown.png` | Material Symbols [`arrow_circle_down`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:arrow_circle_down) | Google | Apache-2.0 |
| `zoomin.png` | Material Symbols [`zoom_in`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:zoom_in) | Google | Apache-2.0 |
| `zoomout.png` | Material Symbols [`zoom_out`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:zoom_out) | Google | Apache-2.0 |
| `changecamera.png` | Material Symbols [`switch_video`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:switch_video) | Google | Apache-2.0 |
| `returncamera.png` | Material Symbols [`history`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:history) | Google | Apache-2.0 |
| `savecamera.png` | Material Symbols [`bookmark_add`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:bookmark_add) | Google | Apache-2.0 |
| `defaultcamera.png` | Material Symbols [`settings_backup_restore`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:settings_backup_restore) | Google | Apache-2.0 |
| `flipcamera.png` | Material Symbols [`flip_camera_android`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flip_camera_android) | Google | Apache-2.0 |
| `facecamera.png` | Material Symbols [`face`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:face) | Google | Apache-2.0 |
| `screenshot.png` | Material Symbols [`screenshot_monitor`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:screenshot_monitor) | Google | Apache-2.0 |
| `toggleui.png` | Material Symbols [`visibility_off`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:visibility_off) | Google | Apache-2.0 |
| `fps.png` | Material Symbols [`monitoring`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:monitoring) | Google | Apache-2.0 |
| `music.png` | Material Symbols [`music_off`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:music_off) | Google | Apache-2.0 |
| `sound.png` | Material Symbols [`volume_off`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:volume_off) | Google | Apache-2.0 |
| `volup.png` | Material Symbols [`volume_up`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:volume_up) | Google | Apache-2.0 |
| `voldown.png` | Material Symbols [`volume_down`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:volume_down) | Google | Apache-2.0 |
| `nextview.png` | Material Symbols [`videocam`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:videocam) | Google | Apache-2.0 |
| `prevview.png` | Material Symbols [`switch_video`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:switch_video) | Google | Apache-2.0 |
| `windowsize.png` | Material Symbols [`fullscreen`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:fullscreen) | Google | Apache-2.0 |
| `wow.png` | WORLD OF / WARCRAFT with a 2 px stroke, drawn by `wordmark()` in `fetch_icons.py`, in Cinzel ([`ofl/cinzel/Cinzel[wght].ttf`](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf), weight 900) | font: Natanael Gama | font: SIL OFL 1.1 |
| `ffxiv.png` | FINAL FANTASY / XIV with a 2 px stroke, drawn by `wordmark()` in `fetch_icons.py`, in Cinzel ([`ofl/cinzel/Cinzel[wght].ttf`](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf), weight 900) | font: Natanael Gama | font: SIL OFL 1.1 |
