# Genshin Impact overlay: sources

`scripts/generate_app_overlays.py` renders `genshin.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `genshin_template` (1 file) | Genshin Impact: `GenshinImpact.exe` (global client), `YuanShen.exe` (Chinese client) |

The launcher (HoYoPlay) is a separate process and gets no set. Under Wine the
window class keeps `.exe`, which the window handler cuts off, so the same
names match. None of the names was checked on an install.

## Shortcut reference

HoYoverse publishes no key list that could be read. The keys are those two
independent key lists agree on:

- keyboardista, <https://keyboardista.pages.dev/en/shortcuts/genshin-pc/>
- simplegameguide (2024-06-06), <https://simplegameguide.co.uk/genshin-impact-controls-pc-ps4>

GameWith (<https://gamewith.net/genshin-impact/article/show/40478>) agrees on
the movement and combat keys. Read 2026-11-15. A screenshot of the game's
Controls page should confirm this before anyone relies on it.

## Default keys only

The game keeps its settings, the controls included, in a binary value under
`HKEY_CURRENT_USER\Software\miHoYo\Genshin Impact` in the Windows registry.
Its layout is not documented, so the overlay always shows the defaults.

## Keys

| Key | Action |
|---|---|
| E | Elemental skill |
| Q | Elemental burst |
| R | Aim mode |
| 1 | Party member 1 |
| 2 | Party member 2 |
| 3 | Party member 3 |
| 4 | Party member 4 |
| Alt+1 | Member 1: burst |
| Alt+2 | Member 2: burst |
| Alt+3 | Member 3: burst |
| Alt+4 | Member 4: burst |
| Space | Jump |
| F | Interact |
| Z | Gadget |
| T | Special action |
| X | Drop from climb |
| V | Quest navigation |
| P | Abandon challenge |
| B | Inventory |
| C | Characters |
| M | Map |
| J | Quests |
| L | Party setup |
| O | Friends |
| Y | Notification details |
| G | Tutorials |
| Enter | Chat |
| Tab | Shortcut wheel |
| F1 | Adventurer Handbook |
| F2 | Co-op |
| F3 | Wish |
| F4 | Battle Pass |
| F5 | Events |
| F7 | Serenitea Pot |

## Left out

- W, A, S, D (move): the letter legend is enough.
- Shift (sprint), Ctrl (walk) and Alt (show the cursor): modifier keys with no
  cell of their own. Alt with 1 to 4 is drawn: it switches to that member and
  casts the burst.
- 5 (a fifth party member), U (environment notes), F6: the sources disagree
  or do not say when the key applies.
- Esc (Paimon menu): ESC has the program mark.

## Placement

As for Counter-Strike 2: every icon sits at the right edge of its key and uses
the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F-key icons use 34x40 (the area AoE2 measured for
F-key legends). The solid or wide icons (`INK` in `fetch_icons.py`) are drawn
in a smaller box inside their area. Every icon is drawn at exactly its area by
`game_set.py`, so the generator places it 1:1.

ESC shows GENSHIN in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). HoYoverse's
logo art is proprietary and is not used.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `skill.png` | game-icons.net `lorc/wind-slap` | lorc | CC BY 3.0 |
| `burst.png` | game-icons.net `lorc/star-swirl` | lorc | CC BY 3.0 |
| `member.png` | game-icons.net `delapouite/person` | delapouite | CC BY 3.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `gadget.png` | game-icons.net `lorc/gear-hammer` | lorc | CC BY 3.0 |
| `navigate.png` | game-icons.net `delapouite/position-marker` | delapouite | CC BY 3.0 |
| `bag.png` | game-icons.net `delapouite/backpack` | delapouite | CC BY 3.0 |
| `quests.png` | game-icons.net `lorc/scroll-unfurled` | lorc | CC BY 3.0 |
| `party.png` | game-icons.net `delapouite/three-friends` | delapouite | CC BY 3.0 |
| `friends.png` | game-icons.net `delapouite/shaking-hands` | delapouite | CC BY 3.0 |
| `handbook.png` | game-icons.net `lorc/book-cover` | lorc | CC BY 3.0 |
| `coop.png` | game-icons.net `delapouite/team-upgrade` | delapouite | CC BY 3.0 |
| `battlepass.png` | game-icons.net `delapouite/ticket` | delapouite | CC BY 3.0 |
| `events.png` | game-icons.net `delapouite/calendar` | delapouite | CC BY 3.0 |
| `teapot.png` | game-icons.net `delapouite/house` | delapouite | CC BY 3.0 |
| `aim.png`, `interact.png`, `special.png` | Material Symbols `my_location`, `touch_app`, `bolt` | Google | Apache-2.0 |
| `drop.png`, `abandon.png`, `character.png` | Material Symbols `south`, `flag`, `badge` | Google | Apache-2.0 |
| `map.png`, `notification.png`, `tutorial.png` | Material Symbols `map`, `notifications`, `school` | Google | Apache-2.0 |
| `chat.png`, `wheel.png`, `wish.png` | Material Symbols `chat`, `donut_large`, `auto_awesome` | Google | Apache-2.0 |
| `program.png` | drawn by `game_set.py` in Bebas Neue | font: Dharma Type | font: SIL OFL 1.1 |
