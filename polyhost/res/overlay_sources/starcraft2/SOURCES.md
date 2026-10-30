# StarCraft II overlay: sources

`scripts/generate_app_overlays.py` renders `starcraft2.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `starcraft2_template` (primary and combo file) | StarCraft II: `SC2_x64.exe` and `SC2.exe` on Windows (`sc2_x64`, `sc2`), the same names with `.exe` under Wine, `sc2` and `starcraft ii` on macOS |

None of the app names was checked on an install. The Windows names are those of
the game client in `StarCraft II\Versions\Base<N>\`; `StarCraft II.exe` is the
launcher. The macOS names are assumed. StarCraft II is not on Steam, so there
is no `steam_app_*` name under Proton; under Wine or Lutris the window class is
the `.exe` name.

## Shortcut reference

The default "Standard" hotkey profile, from two pages:

- the StarCraft wiki on Fandom, page "Hotkey", section "StarCraft II"
  (<https://starcraft.fandom.com/wiki/Hotkey>), read 2026-10-30 through the
  MediaWiki API (`api.php?action=parse&page=Hotkey&prop=wikitext`), because the
  page itself answers 403 to scripts;
- Liquipedia, "Hotkeys" (<https://liquipedia.net/starcraft2/Hotkeys>), read
  2026-10-30 as the Internet Archive copy of 2026-03-06
  (`web.archive.org/web/20260306073412/...`), because Liquipedia answered a
  captcha to headless Chromium and 429 to its API.

No public default hotkey file was found to compare with: the session could not
use GitHub search. The game's own files were not read.

| Key | Action | Source |
|---|---|---|
| 1 to 0 | select control group | both |
| Ctrl+1 to 0 | create control group | both |
| Shift+1 to 0 | add the selection to the group | both |
| Alt+1 to 0 | create the group and take the units out of their other groups | both |
| Shift+Alt+1 to 0 | add to the group and take the units out of their other groups | Fandom |
| F1 | select idle worker | both |
| F2 | select army | both |
| Backspace | go to (cycle) bases | both |
| Space | go to the last alert | both |
| Tab, Shift+Tab | next, previous subgroup | Fandom |
| F5 to F8 | go to camera location 1 to 4 | both |
| Ctrl+F5 to F8 | save camera location 1 to 4 | both |
| Page Down, Page Up | zoom in, zoom out | Fandom (Liquipedia: "adjust view") |
| End | zoom toggle | Fandom |
| Home | default camera view | Fandom |
| Insert, Delete | rotate the camera clockwise, counterclockwise | Fandom |
| Ctrl+F, Ctrl+Shift+F | follow the selected unit (while held), follow it | Fandom |
| Enter | chat | Fandom |
| Shift+Enter, Ctrl+Enter, Ctrl+Alt+Enter | chat to all, to allies, to one player | Fandom |
| \` | voice chat | Fandom |
| ' \ [ ] | show all, own, allied, enemy health bars | Fandom |
| Alt+G | ping the minimap | both |
| Alt+F | alliance colours | both |
| Alt+T | minimap terrain on / off | both |
| Ctrl+Alt+F | frame rate display | both |
| Pause | pause the game | Fandom |
| Ctrl+Q | quick save (campaign) | Fandom |
| Ctrl+M, Ctrl+S | music, sound on / off | Fandom |
| Print Screen | screenshot | Fandom |
| Alt+Enter | full screen / window | Fandom |
| F9, F10, F11, F12 | achievements, game menu, message log, help | both |
| Alt+F11 | social menu | Fandom |
| Ctrl+F12 | team resources | Fandom |

A user who changes the hotkeys in the game keeps these defaults on the keys.

## Left out

- The letter keys alone, and letters with Shift. They train, build and cast,
  and what each does depends on the selection.
- W (select all warp gates, or "warp-in units" on Liquipedia): it is a
  Protoss-only key and a letter, which a command card can use.
- F3 to F8 "select hero": Fandom lists them for campaigns and custom maps, where
  F5 to F8 are the camera keys of a normal game. The camera keys are drawn.
- Shift+F5 to F8 (camera locations 5 to 8): Fandom says Shift adds four more
  locations; Liquipedia says locations 5 to 8 have no key until the player sets
  one. The two pages disagree, so the keys stay blank.
- The arrow keys (scroll the view): the arrows keep their own legends.
- The keypad keys (game speed, item slots): they have no keycap display.
- The replay and observer keys (P, F, B, Ctrl+E, Ctrl+T, A, D, M and more):
  they replace the game keys only in a replay or as an observer.
- The AI commands (Alt+C, Alt+A, Alt+S, Alt+D, Alt+E, Alt+B, Alt+X): only in
  games with an allied computer player.
- `/` (also opens the chat): Enter is drawn.

## Placement

As for Age of Empires II and Warcraft III (`../aoe2/SOURCES.md`,
`../warcraft3/SOURCES.md`): every icon sits at the right edge and uses the full
height, and the firmware clears 3 px around it, so a letter legend stays whole.
F1, F2 and F5 to F8 use 34×40, the other keys 40×40. The control groups are
48×40, drawn 1:1, 5 px from the right edge.

The control groups show one unit each, from a neutral science-fiction set:
1 space suit, 2 walker, 3 tank, 4 jet fighter, 5 spaceship, 6 beetle, 7 hydra,
8 UFO, 9 alien, 0 drill. The game does not tie a group number to a unit type;
the icons only suggest a habit. A mark in the bottom-right corner shows the
modifier, with the same marks the StarCraft reader draws
(`polyhost/services/game_assets/dither.py`): a plus for Ctrl (create), a plus
in a ring for Shift (add), a plus in a square for Alt (create and steal), a plus
cut out of a filled disc for Shift+Alt (add and steal).

F5 to F8 show a film camera with the number cut out of its body; Ctrl adds a
plus at the top right. The health-bar keys show a bar over the word ALL, OWN,
ALLY or ENEMY, all in Liberation Sans Bold at one size. Ctrl+F and Ctrl+Shift+F
both show the crosshairs; they are on different modifier layers.

ESC shows STARCRAFT over a large II in Teko SemiBold (SIL OFL 1.1, the
SemiBold instance of `ofl/teko/Teko[wght].ttf` from google/fonts at commit
e7db6ca), drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25). Teko was chosen from eight OFL
faces rendered at keycap size, because it is narrow enough for an 11 px cap
height. The game's logo art is not used.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `idleworker.png` | game-icons.net `delapouite/miner` | delapouite | CC BY 3.0 |
| `army.png` | Font Awesome Free 6.5.2 `person-military-rifle` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `bases.png` | Font Awesome Free 6.5.2 `industry` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lastalert.png` | Font Awesome Free 6.5.2 `triangle-exclamation` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `subgroupnext.png` | Font Awesome Free 6.5.2 `forward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `subgroupprev.png` | Font Awesome Free 6.5.2 `backward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `camera1.png` to `camera4.png`, `cameraset1.png` to `cameraset4.png` | Font Awesome Free 6.5.2 `video` (solid), the number in DejaVu Sans Bold (the copy bundled with matplotlib v3.9.2, Bitstream Vera licence) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomtoggle.png` | Material Design Icons `magnify-expand` (pinned commit 2424e74) | Pictogrammers | Apache-2.0 |
| `camdefault.png` | Material Design Icons `image-filter-center-focus` (pinned commit 2424e74) | Pictogrammers | Apache-2.0 |
| `rotatecw.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotateccw.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `follow.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `chatall.png` | game-icons.net `delapouite/megaphone` | delapouite | CC BY 3.0 |
| `chatallies.png` | game-icons.net `lorc/conversation` | lorc | CC BY 3.0 |
| `chatplayer.png` | Font Awesome Free 6.5.2 `user` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `voice.png` | Font Awesome Free 6.5.2 `microphone` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hpall.png`, `hpown.png`, `hpallies.png`, `hpenemies.png` | drawn by `fetch_icons.py`; the words in Liberation Sans Bold | - | SIL OFL 1.1 (font) |
| `ping.png` | Material Design Icons `map-marker-radius` (pinned commit 2424e74) | Pictogrammers | Apache-2.0 |
| `alliancecolours.png` | Font Awesome Free 6.5.2 `palette` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `terrain.png` | Font Awesome Free 6.5.2 `mountain` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fps.png` | Font Awesome Free 6.5.2 `gauge-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `music.png` | Font Awesome Free 6.5.2 `music` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sound.png` | Font Awesome Free 6.5.2 `volume-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `achievements.png` | Font Awesome Free 6.5.2 `trophy` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gamemenu.png` | Font Awesome Free 6.5.2 `bars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `messagelog.png` | game-icons.net `delapouite/notebook` | delapouite | CC BY 3.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `social.png` | Font Awesome Free 6.5.2 `user-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `resources.png` | Font Awesome Free 6.5.2 `gem` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | drawn by `fetch_icons.py` in Teko SemiBold | - | SIL OFL 1.1 (font) |
| `group1.png` and its marked copies (`groupnew1`, `groupadd1`, `groupsteal1`, `groupaddsteal1`) | game-icons.net `lorc/space-suit` | lorc | CC BY 3.0 |
| `group2.png` and its marked copies | game-icons.net `delapouite/walking-turret` | delapouite | CC BY 3.0 |
| `group3.png` and its marked copies | game-icons.net `lorc/tank` | lorc | CC BY 3.0 |
| `group4.png` and its marked copies | game-icons.net `delapouite/jet-fighter` | delapouite | CC BY 3.0 |
| `group5.png` and its marked copies | game-icons.net `delapouite/spaceship` | delapouite | CC BY 3.0 |
| `group6.png` and its marked copies | game-icons.net `lorc/scarab-beetle` | lorc | CC BY 3.0 |
| `group7.png` and its marked copies | game-icons.net `lorc/hydra` | lorc | CC BY 3.0 |
| `group8.png` and its marked copies | game-icons.net `delapouite/ufo` | delapouite | CC BY 3.0 |
| `group9.png` and its marked copies | game-icons.net `lorc/alien-skull` | lorc | CC BY 3.0 |
| `group0.png` and its marked copies | game-icons.net `delapouite/drill` | delapouite | CC BY 3.0 |

The files whose name starts with `_` are the unscaled renders `fetch_icons.py`
draws the keys from.

## Art from the user's StarCraft files

When StarCraft 1.16.1 (with or without Brood War) is on the machine, the host
draws the control groups, F1 and Backspace from the game's own unit
wireframes, for the race chosen in the settings. The shipped file above stays
the fallback and is the only art in the repository. Blizzard's graphics are
never shipped: the host reads them from the user's install, writes the patched
copy to the user's cache directory, and sends it only to the keyboard.

⚠️ **The reader was not run against real StarCraft files.** It was written from
the format descriptions below and tested only with small archives and sprites
the tests build themselves. Which wireframe frame belongs to which unit, and
how the frames look at keycap size, are not checked.

The mapping entry opts in with `game_assets: starcraft2/starcraft2.yaml`. The
`game_assets:` block at the end of `starcraft2.yaml` names the reader
(`starcraft`) and the unit on each key per race.

| Keys | From the game |
|---|---|
| 1 to 0 with no modifier, Ctrl, Shift, Alt and Shift+Alt | the unit's wireframe, with the same marks as the shipped set |
| F1 | the race's worker (SCV, Probe, Drone) |
| Backspace | the race's town hall (Command Center, Nexus, Hatchery) |

| Race | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 0 |
|---|---|---|---|---|---|---|---|---|---|---|
| Terran | Marine 0 | Firebat 32 | Medic 34 | Ghost 1 | Vulture 2 | Siege Tank 5 | Goliath 3 | Wraith 8 | Battlecruiser 12 | SCV 7 |
| Protoss | Zealot 65 | Dragoon 66 | High Templar 67 | Dark Templar 61 | Archon 68 | Reaver 83 | Corsair 60 | Scout 70 | Carrier 72 | Probe 64 |
| Zerg | Zergling 37 | Hydralisk 38 | Lurker 103 | Ultralisk 39 | Mutalisk 43 | Guardian 44 | Queen 45 | Defiler 46 | Overlord 42 | Drone 41 |

The numbers are unit ids, checked against BWAPI's `UnitType` enum
(<https://github.com/bwapi/bwapi/blob/master/bwapi/include/BWAPI/UnitType.h>,
read 2026-10-30; Command Center 106, Nexus 154 and Hatchery 131 as well). The
reader takes frame `id` of `unit\wirefram\wirefram.grp`, as the modding tools
describe it; that the frame number equals the unit id was not checked on the
game's files. `{cmdicon: n}` (frame n of `unit\cmdbtns\cmdicons.grp`) is
supported but not used.

The pixels are palette indices. The reader turns them into grey with the
palette `tileset\badlands.wpe` (256 entries of red, green, blue and an unused
byte, as OpenBW reads `Tileset/<name>.wpe`), then dithers the inside and lights
the outline with `dither.keycap`, as the C&C reader does. The status panel
colours a wireframe with its own remapping, so the badlands greys are only an
approximation; `flat: true` on a recipe lights every opaque pixel instead.

The reader looks for `StarDat.mpq` (any case), with `BrooDat.mpq` and
`patch_rt.mpq` when present, in this order:

1. the folder in the `game_sc1_data_dir` setting, when set;
2. the folder of the running StarCraft II executable, and a `StarCraft` folder
   beside any of its four nearest parents (`Program Files (x86)\StarCraft`
   next to `Program Files (x86)\StarCraft II\Versions\Base<N>`);
3. `StarCraft` in `%PROGRAMFILES(X86)%` and `%PROGRAMFILES%`, in
   `/Applications` and `~/Applications`, and in `Program Files (x86)` and
   `Program Files` of `$WINEPREFIX` and `~/.wine`.

A file is read from `patch_rt.mpq` first, then `BrooDat.mpq`, then
`StarDat.mpq`, so the Brood War units come from the Brood War archive.

StarCraft: Remastered keeps its files in CASC storage, which the reader does
not open. A folder with `.build.info` or `Data/data` is named in the log once
("keeps its files in CASC"), and the shipped overlay is used. The 2017 free
release (1.18) is reported to use CASC as well; that was not checked. The MPQ
files are in installs of 1.16.1 and earlier.

| Setting | Default | Meaning |
|---|---|---|
| `game_assets_enabled` | `true` | `false` always sends the shipped file |
| `game_sc1_data_dir` | empty | a folder with the MPQ files; empty searches as above |
| `game_sc1_race` | `terran` | `terran`, `protoss` or `zerg` |

The last two are the reader's own settings
(`polyhost/services/game_assets/starcraft/__init__.py`).

### File formats

- MPQ format version 1 (`mpq.py`): the header (at 0 or a multiple of 512),
  the hash and block tables decrypted with the standard MPQ crypt table, the
  file key from the name without its folder (with the FIX_KEY adjustment by
  block offset and size), sector offset tables, single-unit files, and the
  compressions PKWARE DCL implode (both the old IMPLODE flag and mask 0x08),
  zlib (0x02) and bzip2 (0x10). Huffman and ADPCM compress only sound and are
  refused. Written from the StormLib documentation and "Inside MoPaQ"; the
  tests check the two published table keys (0xC3AF3770, 0xEC83B3A3).
- PKWARE DCL explode (`explode.py`): a port of `blast.c` 1.3 by Mark Adler from
  zlib's `contrib/blast` (zlib licence, compatible with GPL-3.0-or-later; the
  notice is kept in the file header). It is checked against the test vector in
  `blast.c`'s comment, `00 04 82 24 25 8f 80 7f` → `AIAIAIAIAIAIA`, and against
  a test-only encoder for the coded-literal path.
- GRP sprites (`grp.py`): frame count and largest size, an 8-byte entry per
  frame (offsets, size, line table), and per row a run-length code (0x80
  transparent run, 0x40 repeat, else literal). Written from the descriptions
  on the Staredit Network wiki and in the PyMS and OpenBW sources.
