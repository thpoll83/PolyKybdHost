# League of Legends overlay: sources

`scripts/generate_app_overlays.py` renders `lol.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `lol_template` (1 file) | The League of Legends game window: `League of Legends.exe` on Windows (`league of legends`), the `LeagueOfLegends.app` bundle on macOS (`leagueoflegends`) |

The lobby client (`LeagueClient`, `LeagueClientUx`) is a different process and
gets no overlay. The Windows name is the game executable in
`Riot Games/League of Legends/Game/`. The macOS bundle name is from player
reports of the launcher's own log
(<https://gist.github.com/kdembler/181fc7b7c3e4be27ed936152940cf341>, 2021 to
2024), which spell it `LeagueOfLegends.app`; the lookup is lowercased, so both
spellings match. None of the names was checked on an install. The game does not
run on Linux, so there is no Linux name.

## Shortcut reference

The Click-to-Move defaults on the League of Legends Wiki page "Controls and
Hotkeys/Click to Move"
(<https://wiki.leagueoflegends.com/en-us/Controls_and_Hotkeys/Click_to_Move>),
read 2026-11-05 from the page's wikitext (`?action=raw`), with the camera
section of the parent page
(<https://wiki.leagueoflegends.com/en-us/Controls_and_Hotkeys>). The game also
has a WASD movement scheme (since V25.24) that moves several bindings; the
overlay shows the Click-to-Move defaults. A user who rebinds a key in
Settings > Hotkeys still sees the default here. The same keys apply on macOS.

## Keys

| Key | Action |
|---|---|
| Ctrl+Q, Ctrl+W, Ctrl+E, Ctrl+R | Level up ability 1 to 4 |
| 1, 2, 3, 5, 6, 7 | Item slot 1 to 6 |
| 4 | Trinket |
| B | Recall |
| \` | Target champions only |
| A, X | Attack move |
| J | Hold position |
| S | Stop |
| Space | Center camera on champion |
| Y | Toggle camera lock |
| F1, F2 to F5 | Select self, select ally 1 to 4 |
| Ctrl+F | Toggle FPS display |
| F9 | Toggle mouse screen lock |
| F12 | Screenshot |
| Alt+Enter | Toggle fullscreen |
| Alt+M | Toggle minimap camera drag |
| G | Alert ping |
| H | Enemy vision ping |
| Ctrl+1 to Ctrl+6 | Joke, taunt, dance, laugh, toggle, mastery emote |
| U, I | Fist bump, "my bad" |
| T | Emote wheel |
| Enter, Shift+Enter | Open chat, open all chat |
| Z | Chat history |
| , | Toggle microphone |
| Tab, O | Scoreboard (hold), scoreboard (toggle) |
| \\ | System menu |
| C, Ctrl+C | Advanced player stats, toggle basic player stats |
| P | Open shop |
| Ctrl+L | Focus shop search |
| Ctrl+Tab | Switch shop tabs |

## Left out

- Q, W, E, R (abilities), D, F (summoner spells), V (role quest active) and
  Shift+F1 to Shift+F6 (champion interactions): what they do depends on the
  champion. Their Shift (quick cast) and Alt (self cast) variants are left out
  for the same reason.
- Shift+1 to Shift+7 and Alt+1 to Alt+7 (quick cast and self cast an item):
  the plain digit already shows the slot.
- The arrow keys (scroll the camera): the legend already shows the direction.
- Esc (system menu): ESC has the program mark; `\` has the second system menu
  binding.
- Practice Tool keys (Shift+T, Shift+Y and others): they act only in a Practice
  Tool session, and on the Shift layer they would show in every game.
- Mouse bindings (move, attack move click, pings with Alt or Ctrl+click): no
  keycap cell.

## Placement

As for Factorio and Age of Empires II: every icon sits at the right edge and
uses the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F1 to F5 and F9 use 34×40 and F12 30×40, the areas
AoE2 measured to keep those legends whole (F9 and F12 were not measured).

The icons are flat 1-bit silhouettes. The solid or wide icons (chat bubbles,
the globe, the pings, the faces; `INK` in `fetch_icons.py`) are drawn in a
smaller box inside their area.

The drawn icons, placed 1:1 because their size equals the area:

- 1, 2, 3, 5, 6, 7: the inventory as two rows of three slots, with the slot of
  that key filled. 1 2 3 are the top row and 5 6 7 the bottom row, as in the
  game's item bar.
- F2 to F5: the person glyph with the ally number 1 to 4 (Liberation Sans Bold).

ESC shows LEAGUE in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). Riot's logo
art is proprietary and is not used.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `trinket.png` | game-icons.net `lorc/lantern-flame` | lorc | CC BY 3.0 |
| `champonly.png` | game-icons.net `sbed/targeted` | sbed | CC BY 3.0 |
| `attackmove.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `taunt.png` | game-icons.net `lorc/shouting` | lorc | CC BY 3.0 |
| `fistbump.png` | game-icons.net `lorc/fist` | lorc | CC BY 3.0 |
| `shop.png` | game-icons.net `delapouite/shop` | delapouite | CC BY 3.0 |
| `levelup.png` | Material Symbols `upgrade` | Google | Apache-2.0 |
| `recall.png` | Material Symbols `home` | Google | Apache-2.0 |
| `hold.png`, `stop.png` | Material Symbols `pan_tool`, `block` | Google | Apache-2.0 |
| `centre.png`, `camlock.png` | Material Symbols `center_focus_strong`, `lock` | Google | Apache-2.0 |
| `self.png` | Material Symbols `person` | Google | Apache-2.0 |
| `mouselock.png`, `screenshot.png`, `fullscreen.png` | Material Symbols `mouse`, `screenshot_monitor`, `fullscreen` | Google | Apache-2.0 |
| `minimapdrag.png`, `fps.png` | Material Symbols `map`, `speed` | Google | Apache-2.0 |
| `ping.png`, `visionping.png` | Material Symbols `error`, `visibility` | Google | Apache-2.0 |
| `joke.png`, `dance.png`, `laugh.png` | Material Symbols `theater_comedy`, `music_note`, `sentiment_very_satisfied` | Google | Apache-2.0 |
| `emotetoggle.png`, `mastery.png` | Material Symbols `toggle_on`, `military_tech` | Google | Apache-2.0 |
| `mybad.png`, `emotewheel.png` | Material Symbols `sentiment_dissatisfied`, `add_reaction` | Google | Apache-2.0 |
| `chat.png`, `allchat.png`, `chathistory.png`, `mic.png` | Material Symbols `chat`, `public`, `history`, `mic` | Google | Apache-2.0 |
| `scoreboard.png`, `menu.png` | Material Symbols `scoreboard`, `menu` | Google | Apache-2.0 |
| `stats.png`, `basicstats.png` | Material Symbols `query_stats`, `bar_chart` | Google | Apache-2.0 |
| `shopsearch.png`, `shoptabs.png` | Material Symbols `search`, `tab` | Google | Apache-2.0 |
| `ally1.png` … `ally4.png` | Material Symbols `person` + a digit drawn by `fetch_icons.py` (Liberation Sans Bold) | Google | Apache-2.0 |
| `item1.png` … `item7.png` (no `item4`) | drawn by `fetch_icons.py` | — | this repo (GPL-3.0-or-later) |
| `program.png` | drawn by `fetch_icons.py` in Bebas Neue | font: Dharma Type | font: SIL OFL 1.1 |
