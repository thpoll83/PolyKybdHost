# Age of Empires II overlays: sources

`scripts/generate_app_overlays.py` renders `aoe2_hd.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `aoe2_hd_template` (1 file) | The Conquerors (`age2_x1.exe`), The Age of Kings (`empires2.exe`), HD Edition (`AoK HD.exe`), on Windows and under Wine |

The app names were not checked on an install.

## Shortcut reference

The HD Edition default hotkey sheet from aoe2hdozclan.com, sent by the
maintainer on 2026-10-22. It lists the same defaults as the CD version.

## Left out

- The letter keys alone, except H (Go to Town Center). They build, train and
  give unit commands, and what each does depends on the selection.
- Numpad `-` and `+` (game speed): the keyboard has no numpad.
- Ctrl+1 to Ctrl+0 and 1 to 0 (control groups): not on the sheet.

## Placement

Keys with a one-letter legend use a 40×40 icon on the right of the keycap. The
legend ends at x 22 and the icon starts at x 32. The function keys, Home,
Backspace, Enter, `,` and `.` keep the app sets' 36×32 size, because their
legends are wider.

## Icons

All icons are from [game-icons.net](https://game-icons.net), licensed
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Each one is credited
to its author below. `fetch_icons.py` renders the SVG at 128 px; the generator
scales it to the keycap.

| File | Icon | Author |
|---|---|---|
| `idlevillager.png` | [farmer](https://game-icons.net/1x1/delapouite/farmer.html) | Delapouite |
| `idlemilitary.png` | [crossed-swords](https://game-icons.net/1x1/lorc/crossed-swords.html) | Lorc |
| `towncenter.png` | [village](https://game-icons.net/1x1/delapouite/village.html) | Delapouite |
| `notification.png` | [ringing-bell](https://game-icons.net/1x1/lorc/ringing-bell.html) | Lorc |
| `previousview.png` | [anticlockwise-rotation](https://game-icons.net/1x1/delapouite/anticlockwise-rotation.html) | Delapouite |
| `mill.png` | [windmill](https://game-icons.net/1x1/delapouite/windmill.html) | Delapouite |
| `barracks.png` | [barracks](https://game-icons.net/1x1/delapouite/barracks.html) | Delapouite |
| `archeryrange.png` | [bow-arrow](https://game-icons.net/1x1/delapouite/bow-arrow.html) | Delapouite |
| `stable.png` | [stable](https://game-icons.net/1x1/delapouite/stable.html) | Delapouite |
| `blacksmith.png` | [anvil](https://game-icons.net/1x1/lorc/anvil.html) | Lorc |
| `market.png` | [shop](https://game-icons.net/1x1/delapouite/shop.html) | Delapouite |
| `monastery.png` | [church](https://game-icons.net/1x1/delapouite/church.html) | Delapouite |
| `castle.png` | [castle](https://game-icons.net/1x1/delapouite/castle.html) | Delapouite |
| `siegeworkshop.png` | [catapult](https://game-icons.net/1x1/heavenly-dog/catapult.html) | HeavenlyDog |
| `dock.png` | [anchor](https://game-icons.net/1x1/lorc/anchor.html) | Lorc |
| `lumbercamp.png` | [axe-in-log](https://game-icons.net/1x1/delapouite/axe-in-log.html) | Delapouite |
| `miningcamp.png` | [mine-wagon](https://game-icons.net/1x1/delapouite/mine-wagon.html) | Delapouite |
| `university.png` | [graduate-cap](https://game-icons.net/1x1/delapouite/graduate-cap.html) | Delapouite |
| `techtree.png` | [family-tree](https://game-icons.net/1x1/delapouite/family-tree.html) | Delapouite |
| `pause.png` | [pause-button](https://game-icons.net/1x1/guard13007/pause-button.html) | Guard13007 |
| `statistics.png` | [histogram](https://game-icons.net/1x1/delapouite/histogram.html) | Delapouite |
| `savechapter.png` | [quill-ink](https://game-icons.net/1x1/lorc/quill-ink.html) | Lorc |
| `gametime.png` | [sands-of-time](https://game-icons.net/1x1/lorc/sands-of-time.html) | Lorc |
| `savegame.png` | [save](https://game-icons.net/1x1/delapouite/save.html) | Delapouite |
| `diplomacy.png` | [shaking-hands](https://game-icons.net/1x1/delapouite/shaking-hands.html) | Delapouite |
| `flare.png` | [position-marker](https://game-icons.net/1x1/delapouite/position-marker.html) | Delapouite |
| `objectives.png` | [checklist](https://game-icons.net/1x1/delapouite/checklist.html) | Delapouite |
| `chat.png` | [conversation](https://game-icons.net/1x1/lorc/conversation.html) | Lorc |
| `sendchat.png` | [chat-bubble](https://game-icons.net/1x1/delapouite/chat-bubble.html) | Delapouite |
