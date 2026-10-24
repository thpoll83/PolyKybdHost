# Age of Empires II overlays: sources

`scripts/generate_app_overlays.py` renders `aoe2_hd.yaml` and `aoe2_de.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `aoe2_hd_template` (1 file) | The Conquerors (`age2_x1.exe`), The Age of Kings (`empires2.exe`), HD Edition (`AoK HD.exe`), on Windows and under Wine |
| `aoe2_de_template` (1 file) | The Definitive Edition: `aoe2de_s` on Windows, `steam_app_813780` under Proton |

The Definitive Edition reports `AoE2DE_s.exe` (`aoe2de_s`) on Windows and
`steam_app_813780` under Proton on KDE Plasma (Steam app 813780), both measured
2026-10-23. Until it has its own key list it uses the HD keys: `gen_de.py`
writes `aoe2_de.yaml` from `aoe2_hd.yaml` and changes only the name, the app
names, the output file and the ESC mark. The other app names were not checked
on an install.

## Shortcut reference

The HD Edition default hotkey sheet printed by <https://www.aoe2hdozclan.com>,
sent as an image by the maintainer on 2026-10-22. The sheet has no URL of its
own; the site is the one it names. The CD version is assumed to use the same
defaults; that was not checked.

Control groups (1 to 0 select a group, Ctrl+1 to Ctrl+0 create one) are not
on the sheet. They are AoE2's standard keys, added at the maintainer's request.
Each digit has its own unit, drawn twice as a group, so the groups are easy to
tell apart: 1 spearmen, 2 archers, 3 cavalry, 4 vikings, 5 knights, 6 catapults,
7 siege towers, 8 elephants, 9 longships, 0 villagers. The game does not tie a
group number to a unit type; the icons only suggest a habit.

## Left out

- The letter keys alone, except H (Go to Town Center). They build, train and
  give unit commands, and what each does depends on the selection.
- Numpad `-` and `+` (game speed): the keyboard has no numpad.

## Placement

The firmware draws the legend first, clears 3 px around the overlay's ink, and
then draws the overlay, so the icon takes priority over the legend
(`copy_overlay_to_buffer()` in the firmware's `poly_keymap.c`).

Every icon sits at the right edge and uses the full height. Where a narrower
area keeps the key's own legend whole without making the icon too small, the
key uses it, measured with the firmware fonts (`tools/oled_preview.py`) and the
3 px clearance:

| Keys | Legend ends at x | Area |
|---|---|---|
| Letters, `,` `.`, F3, F9, Home, Enter, Page Up, Page Down | 22 to 36 | 40×40 |
| Digits (control groups) | 22 to 36 (the shifted symbol, which the group erases) | 48×40 drawn 1:1, 5 px from the right edge (`margin: 5`) |
| F2 | 35 | 34×40 |
| F4 | 37 | 30×40 |
| F11 | 47 | 21×40 |
| F12 | 51 | 40×40, 5 px from the right edge (`margin: 5`); the icon erases the `12` |
| Backspace | 44 | 40×40; the icon erases the right end of the ⌫ |

On `,` and `.` the icon erases most of the shifted `<` and `>` (x 36–48),
which a game does not use. The villager on `.` sits 5 px further left
(`margin: 5`, x 32–60), so it erases all of the `>`. `fetch_icons.py` trims six icons to their drawn area
(the villager, F2, F4, F11, F12 and Backspace) so they fill their area.

ESC shows a mark drawn pixel by pixel at 72×40 by `program_mark.py`: a large
serif "II" in the light pattern of a dimmed browser mark (every second pixel in
x and y), with "Age", a smaller "— of —" and "Empires" in italic serif over it.
The dashes and the f's crossbar are drawn as single pixels, because the font's
strokes are thinner than a pixel at 10 px. `program_de.png` adds a small "D"
and "E" for the Definitive Edition. The font is Liberation Serif (SIL OFL 1.1);
without it, `program_mark.py` keeps the committed PNGs. The game's own logo is
not free to use.

The mark fills the whole keycap, so ESC is drawn without its legend
(`program_icon_legend: false`): the keyboard clears the cell before it draws the
mark. That needs firmware with protocol v25 (cmd 44). Older firmware draws the
mark over the legend with the 3 px clearance, and parts of the ⎋ legend stay
visible around it.

## Icons

All shortcut icons are from [game-icons.net](https://game-icons.net), licensed
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Each one is credited
to its author below. `fetch_icons.py` renders the SVG at 128 px; the generator
scales it to the keycap.

| File | Icon | Author |
|---|---|---|
| `idlevillager.png` | [farmer](https://game-icons.net/1x1/delapouite/farmer.html) | Delapouite |
| `idlemilitary.png` | [crossed-swords](https://game-icons.net/1x1/lorc/crossed-swords.html) | Lorc |
| `towncenter.png` | [village](https://game-icons.net/1x1/delapouite/village.html) | Delapouite |
| `notification.png` | [ringing-bell](https://game-icons.net/1x1/lorc/ringing-bell.html) | Lorc |
| `previousview.png` | [back-forth](https://game-icons.net/1x1/lorc/back-forth.html) | Lorc |
| `mill.png` | [windmill](https://game-icons.net/1x1/delapouite/windmill.html) | Delapouite |
| `barracks.png` | [medieval-barracks](https://game-icons.net/1x1/delapouite/medieval-barracks.html) | Delapouite |
| `archeryrange.png` | [bow-arrow](https://game-icons.net/1x1/delapouite/bow-arrow.html) | Delapouite |
| `stable.png` | [stable](https://game-icons.net/1x1/delapouite/stable.html) | Delapouite |
| `blacksmith.png` | [anvil](https://game-icons.net/1x1/lorc/anvil.html) | Lorc |
| `market.png` | [two-coins](https://game-icons.net/1x1/delapouite/two-coins.html) | Delapouite |
| `monastery.png` | [church](https://game-icons.net/1x1/delapouite/church.html) | Delapouite |
| `castle.png` | [castle](https://game-icons.net/1x1/delapouite/castle.html) | Delapouite |
| `siegeworkshop.png` | [catapult](https://game-icons.net/1x1/heavenly-dog/catapult.html) | HeavenlyDog |
| `dock.png` | [anchor](https://game-icons.net/1x1/lorc/anchor.html) | Lorc |
| `lumbercamp.png` | [axe-in-log](https://game-icons.net/1x1/delapouite/axe-in-log.html) | Delapouite |
| `miningcamp.png` | [mining](https://game-icons.net/1x1/lorc/mining.html) | Lorc |
| `university.png` | [graduate-cap](https://game-icons.net/1x1/delapouite/graduate-cap.html) | Delapouite |
| `techtree.png` | [family-tree](https://game-icons.net/1x1/delapouite/family-tree.html) | Delapouite |
| `pause.png` | [pause-button](https://game-icons.net/1x1/guard13007/pause-button.html) | Guard13007 |
| `statistics.png` | [histogram](https://game-icons.net/1x1/delapouite/histogram.html) | Delapouite |
| `gametime.png` | [sands-of-time](https://game-icons.net/1x1/lorc/sands-of-time.html) | Lorc |
| `savegame.png` | [save](https://game-icons.net/1x1/delapouite/save.html) | Delapouite |
| `diplomacy.png` | [shaking-hands](https://game-icons.net/1x1/delapouite/shaking-hands.html) | Delapouite |
| `flare.png` | [position-marker](https://game-icons.net/1x1/delapouite/position-marker.html) | Delapouite |
| `objectives.png` | [checklist](https://game-icons.net/1x1/delapouite/checklist.html) | Delapouite |
| `chat.png` | [conversation](https://game-icons.net/1x1/lorc/conversation.html) | Lorc |
| `sendchat.png` | [chat-bubble](https://game-icons.net/1x1/delapouite/chat-bubble.html) | Delapouite |
| `allycolours.png` | [palette](https://game-icons.net/1x1/delapouite/palette.html) | Delapouite |
| `mapcombat.png` | [sword-clash](https://game-icons.net/1x1/lorc/sword-clash.html) | Lorc |
| `mapeco.png` | [wheat](https://game-icons.net/1x1/lorc/wheat.html) | Lorc |
| `mapnormal.png` | [mountains](https://game-icons.net/1x1/lorc/mountains.html) | Lorc |
| `_unit1.png` | [spartan](https://game-icons.net/1x1/lorc/spartan.html) | Lorc |
| `_unit2.png` | [bowman](https://game-icons.net/1x1/lorc/bowman.html) | Lorc |
| `_unit3.png` | [cavalry](https://game-icons.net/1x1/delapouite/cavalry.html) | Delapouite |
| `_unit4.png` | [viking-head](https://game-icons.net/1x1/delapouite/viking-head.html) | Delapouite |
| `_unit5.png` | [visored-helm](https://game-icons.net/1x1/lorc/visored-helm.html) | Lorc |
| `_unit6.png` | [catapult](https://game-icons.net/1x1/heavenly-dog/catapult.html) | HeavenlyDog |
| `_unit7.png` | [siege-tower](https://game-icons.net/1x1/delapouite/siege-tower.html) | Delapouite |
| `_unit8.png` | [elephant](https://game-icons.net/1x1/delapouite/elephant.html) | Delapouite |
| `_unit9.png` | [drakkar](https://game-icons.net/1x1/delapouite/drakkar.html) | Delapouite |
| `_unit0.png` | [farmer](https://game-icons.net/1x1/delapouite/farmer.html) | Delapouite |
| `_conversation.png` | [conversation](https://game-icons.net/1x1/lorc/conversation.html) | Lorc |
| `_arrow.png` | [plain-arrow](https://game-icons.net/1x1/delapouite/plain-arrow.html) | Delapouite |
| `_quill.png` | [quill-ink](https://game-icons.net/1x1/lorc/quill-ink.html) | Lorc |

`fetch_icons.py` composes files from these parts: `chatback.png` and
`chatfwd.png` from `_conversation.png` and `_arrow.png` (the arrow turned up
for back), and `savechapter.png` from `_quill.png` and the up arrow, as on the
save icon.

`group<N>.png` draws `_unit<N>.png` twice at keycap scale: a back copy, and a
front copy 40 % of its width to the right and 6 px lower, with 3 px of black
cleared around the front copy so the two stay apart. `groupnew<N>.png` adds a
13 px plus in the lower-right corner with the same 3 px clearance. Both are
48×40 1-bit images, so the generator places them without scaling and the 3 px
seam survives.
