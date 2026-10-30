# DevilutionX overlay: sources

`scripts/generate_app_overlays.py` renders `devilutionx.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `devilutionx_template` (1 file) | DevilutionX, the open-source engine for Diablo and Hellfire: `devilutionx` on Linux and macOS, `devilutionx.exe` on Windows, the Flatpak `org.diasurgical.DevilutionX` |

Hellfire runs in the same program (`devilutionx --hellfire`) with the same keys.

## Process names and window title

From the DevilutionX 1.5.5 source, not checked on an install:

- `CMakeLists.txt`: `set(BIN_TARGET devilutionx)`, so the program is
  `devilutionx` (`devilutionx.exe` on Windows). The macOS bundle is
  `devilutionx.app` with the display name `DevilutionX`.
- `Packaging/nix/devilutionx.metainfo.xml`: the Flatpak id is
  `org.diasurgical.DevilutionX`.
- `Source/init.cpp`: `SpawnWindow(PROJECT_NAME)`, and `project(DevilutionX …)`
  in `CMakeLists.txt`, so the window title is `DevilutionX`, not `DIABLO`.

## Shortcut reference

The default key bindings of DevilutionX 1.5.5 (the latest release, tag `1.5.5`,
commit `7223eeac9e8274fbf665b4de86fda26d3b22c52f`) in
<https://github.com/diasurgical/devilutionX>:

- `InitKeymapActions()` in `Source/diablo.cpp`: every `Keymapper.AddAction()`
  with its default key. A user's `diablo.ini` (`[Keymapping]`) can change these.
- `PressKey()` in `Source/diablo.cpp`: the keys handled in the code, not through
  the keymapper: Escape (game menu), Enter (chat line), Alt+Enter (full screen),
  `+`/`=` and `-` (automap zoom, only while the automap is shown).
- The four default quick messages: `QuickMessages[]` in `Source/diablo.cpp`.

| Key | Action (source name) |
|---|---|
| 1 to 8 | Belt item 1 to 8 (`BeltItem{}`) |
| F5 to F8 | Quick spell 1 to 4 (`QuickSpell{}`); with the speedbook open, the key assigns the spell under the cursor |
| S | Speedbook (`DisplaySpells`) |
| B | Spellbook (`SpellBook`) |
| I | Inventory (`Inventory`) |
| C | Character (`Character`) |
| Q | Quest log (`QuestLog`) |
| Tab | Toggle automap (`Toggle Automap`) |
| Space | Hide info screens (`Hide Info Screens`) |
| L | Chat log (`ChatLog`) |
| V | Game info (`GameInfo`) |
| F1 | Help (`Help`) |
| Z | Zoom (`Zoom`) |
| `=` and `-` | Automap zoom in and out (`PressKey()`) |
| F and G | Increase and decrease gamma (`IncreaseGamma`, `DecreaseGamma`) |
| Left Alt (hold) | Item highlighting (`Item Highlighting`) |
| Right Ctrl | Toggle item highlighting (`Toggle Item Highlighting`) |
| Print Screen | Screenshot (`Screenshot`) |
| P and Pause | Pause game (`Pause Game`, `Pause Game (Alternate)`) |
| F2 | Quick save (`QuickSave`, single player only) |
| F3 | Quick load (`QuickLoad`, single player only) |
| Enter | Chat (`PressKey()`) |
| Alt+Enter | Full screen on / off (`PressKey()`) |
| F9 to F12 | Quick message 1 to 4 (`QuickMessage{}`): "I need help! Come Here!", "Follow me.", "Here's something for you.", "Now you DIE!" |
| Escape | Game menu (`PressKey()`); the key shows the ESC mark |

The keymapper compares the key only (`KeymapperOptions::KeyPressed()` in
`Source/options.cpp`) and ignores Shift, Ctrl and Alt, so a key does the same
with a modifier held. The overlay labels the unmodified layer only, plus Alt+Enter
and Left Alt on the Alt layer (Left Alt is the item-highlighting key, so the Alt
layer shows while it is held).

## Left out

- Quick spells 5 to 12, Use health potion, Use mana potion, Stop hero and Quit
  game: these actions have no default key (`SDLK_UNKNOWN`).
- The arrow keys, Page Up and Page Down: they scroll the store, the quest log,
  the help screen, the chat log, the automap or the stash, depending on what is
  open.
- The mouse buttons and the Shift+click and Ctrl+wheel actions.
- `Debug toggle` (X): debug builds only.

## Placement

As for Warcraft III (`../warcraft3/SOURCES.md`): every icon sits at the right
edge and uses the full height, and the firmware clears 3 px around it, so a
letter legend stays whole. F1, F2, F3 and F5 to F8 use 34×40, the area that
keeps their legend whole; F9 to F12 use 40×40 and, as in the Warcraft III set,
cover the right part of the F10 to F12 legends. On the digits the icon erases
the shifted symbol, which the game does not use.

All icons are flat 1-bit silhouettes, as in the Warcraft III set. The solid
Font Awesome icons fill a smaller box (30×30 or 34×34, `INK` in
`fetch_icons.py`) so they do not outweigh the outline icons. The belt keys
share one flask and F5 to F8 share one spell icon, because what a slot holds
depends on the player. F9 to F12 show the default quick messages: a raised hand
(help), a footprint (follow me), a present (something for you) and a skull (now
you die). F and G show a sun with a plus or a minus (`gamma_icons()`). Left Alt
and Right Ctrl both show the item labels icon.

ESC shows "Devilution" over a large "X" in New Rocker (SIL OFL 1.1,
`ofl/newrocker/NewRocker-Regular.ttf` from google/fonts at commit e7db6ca),
drawn over the whole cell without the ESC legend (`program_icon_legend: false`,
protocol v25). The DevilutionX logo and the Diablo art are not used: the game
art is Blizzard's, and the DevilutionX repository is under the Sustainable Use
License, not a free licence.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `belt.png` | game-icons.net `lorc/round-bottom-flask` | lorc | CC BY 3.0 |
| `quickspell.png` | game-icons.net `lorc/fire-ray` | lorc | CC BY 3.0 |
| `speedbook.png` | game-icons.net `lorc/magic-palm` | lorc | CC BY 3.0 |
| `spellbook.png` | game-icons.net `lorc/book-aura` | lorc | CC BY 3.0 |
| `inventory.png` | game-icons.net `lorc/knapsack` | lorc | CC BY 3.0 |
| `character.png` | game-icons.net `delapouite/skills` | delapouite | CC BY 3.0 |
| `questlog.png` | game-icons.net `lorc/scroll-unfurled` | lorc | CC BY 3.0 |
| `automap.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closepanels.png` | Font Awesome Free 6.5.2 `rectangle-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chatlog.png` | game-icons.net `delapouite/notebook` | delapouite | CC BY 3.0 |
| `gameinfo.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoom.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapzoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapzoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gammaup.png`, `gammadown.png` | Font Awesome Free 6.5.2 `sun` (solid), with a plus or a minus drawn by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `highlight.png` | Font Awesome Free 6.5.2 `tags` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `msghelp.png` | Font Awesome Free 6.5.2 `hand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `msgfollow.png` | game-icons.net `lorc/footprint` | lorc | CC BY 3.0 |
| `msggift.png` | game-icons.net `delapouite/present` | delapouite | CC BY 3.0 |
| `msgdie.png` | game-icons.net `lorc/skull-crossed-bones` | lorc | CC BY 3.0 |
| `program.png` | "Devilution X" set in New Rocker | Impallari Type | SIL OFL 1.1 |
