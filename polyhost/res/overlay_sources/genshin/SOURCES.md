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

ESC shows the wordmark GENSHIN over IMPACT in Marcellus, a serif close to the
logo's lettering, thickened by a 3 px stroke (of 8 per keycap pixel) so every
stem stays lit. It is drawn by `program()` in `fetch_icons.py`
(Marcellus: SIL OFL 1.1, `ofl/marcellus/Marcellus-Regular.ttf` from google/fonts at commit e7db6ca). It covers
the whole cell and is drawn without the ESC legend (`program_icon_legend:
false`, protocol v25). It was compared by eye with the game's logo; HoYoverse's
logo art is proprietary and is not used or committed.

1 to 4 show a person with the party member number, and Alt+1 to 4 the burst
with that number, so no two actions share a picture.

## Icons

Each icon is drawn at keycap size by `fetch_icons.py` from the source named here.

| File | Source | Author | Licence |
|---|---|---|---|
| `skill.png` | game-icons.net [`lorc/wind-slap`](https://game-icons.net/1x1/lorc/wind-slap.html) | Lorc | CC BY 3.0 |
| `burst.png`, `burst1.png`, `burst2.png`, `burst3.png`, `burst4.png` | game-icons.net [`lorc/star-swirl`](https://game-icons.net/1x1/lorc/star-swirl.html) (the numbered copies + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py`) | Lorc | CC BY 3.0 |
| `aim.png` | Material Symbols [`my_location`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:my_location) | Google | Apache-2.0 |
| `member1.png`, `member2.png`, `member3.png`, `member4.png` | game-icons.net [`delapouite/person`](https://game-icons.net/1x1/delapouite/person.html) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Delapouite | CC BY 3.0 |
| `jump.png` | game-icons.net [`delapouite/jump-across`](https://game-icons.net/1x1/delapouite/jump-across.html) | Delapouite | CC BY 3.0 |
| `interact.png` | Material Symbols [`touch_app`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:touch_app) | Google | Apache-2.0 |
| `gadget.png` | game-icons.net [`lorc/gear-hammer`](https://game-icons.net/1x1/lorc/gear-hammer.html) | Lorc | CC BY 3.0 |
| `special.png` | Material Symbols [`bolt`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:bolt) | Google | Apache-2.0 |
| `drop.png` | Material Symbols [`south`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:south) | Google | Apache-2.0 |
| `navigate.png` | game-icons.net [`delapouite/position-marker`](https://game-icons.net/1x1/delapouite/position-marker.html) | Delapouite | CC BY 3.0 |
| `abandon.png` | Material Symbols [`flag`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:flag) | Google | Apache-2.0 |
| `bag.png` | game-icons.net [`delapouite/backpack`](https://game-icons.net/1x1/delapouite/backpack.html) | Delapouite | CC BY 3.0 |
| `character.png` | Material Symbols [`badge`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:badge) | Google | Apache-2.0 |
| `map.png` | Material Symbols [`map`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:map) | Google | Apache-2.0 |
| `quests.png` | game-icons.net [`lorc/scroll-unfurled`](https://game-icons.net/1x1/lorc/scroll-unfurled.html) | Lorc | CC BY 3.0 |
| `party.png` | game-icons.net [`delapouite/three-friends`](https://game-icons.net/1x1/delapouite/three-friends.html) | Delapouite | CC BY 3.0 |
| `friends.png` | game-icons.net [`delapouite/shaking-hands`](https://game-icons.net/1x1/delapouite/shaking-hands.html) | Delapouite | CC BY 3.0 |
| `notification.png` | Material Symbols [`notifications`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:notifications) | Google | Apache-2.0 |
| `tutorial.png` | Material Symbols [`school`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:school) | Google | Apache-2.0 |
| `chat.png` | Material Symbols [`chat`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:chat) | Google | Apache-2.0 |
| `wheel.png` | Material Symbols [`donut_large`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:donut_large) | Google | Apache-2.0 |
| `handbook.png` | game-icons.net [`lorc/book-cover`](https://game-icons.net/1x1/lorc/book-cover.html) | Lorc | CC BY 3.0 |
| `coop.png` | game-icons.net [`delapouite/team-upgrade`](https://game-icons.net/1x1/delapouite/team-upgrade.html) | Delapouite | CC BY 3.0 |
| `wish.png` | Material Symbols [`auto_awesome`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:auto_awesome) | Google | Apache-2.0 |
| `battlepass.png` | game-icons.net [`delapouite/ticket`](https://game-icons.net/1x1/delapouite/ticket.html) | Delapouite | CC BY 3.0 |
| `events.png` | game-icons.net [`delapouite/calendar`](https://game-icons.net/1x1/delapouite/calendar.html) | Delapouite | CC BY 3.0 |
| `teapot.png` | game-icons.net [`delapouite/house`](https://game-icons.net/1x1/delapouite/house.html) | Delapouite | CC BY 3.0 |
| `program.png` | GENSHIN / IMPACT with a 3 px stroke, drawn by `program()` in `fetch_icons.py`, in Marcellus ([`ofl/marcellus/Marcellus-Regular.ttf`](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/marcellus/Marcellus-Regular.ttf)) | font: Astigmatic | font: SIL OFL 1.1 |
