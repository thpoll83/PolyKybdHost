# Warcraft III overlay: sources

`scripts/generate_app_overlays.py` renders `warcraft3.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `warcraft3_template` (1 file) | Warcraft III classic, the MPQ releases up to 1.31: `war3.exe`, `Warcraft III.exe`, `Frozen Throne.exe`, on Windows and under Wine |

The app names were not checked on an install.

## Shortcut reference

The default hotkeys printed on the back of the Reign of Chaos manual, as listed
on <https://warcraft.wiki.gg/wiki/Warcraft_III:_Hotkeys> (read 2026-10-28), and
the game's own files of the German 1.22 install (read 2026-11-14): the help page
`UI\HelpStrings.txt`, the menu `UI\FrameDef\UI\EscMenuMainPanel.fdf`, the
tooltips in `UI\FrameDef\GlobalStrings.fdf` and the command card
`Units\CommandStrings.txt`. The help page added F6 (quick save) and the menu
and tooltip files the Alt keys below.

| Key | Command (the game's name) | Action | Source |
|---|---|---|---|
| F6 | - | Quick save (single player; the help page lists F1 to F7 as hero keys in multiplayer) | help page |
| Alt+G | `MINIMAPSIGNALTOOLTIP` | Minimap signal | tooltip |
| Alt+A | `MINIMAPALLYCOLORTOOLTIP` | Ally colour mode | tooltip |
| Alt+F | `FORMATION_TOOLTIP` | Formation movement on / off | tooltip |
| A, M, S, H, P | `CmdAttack`, `CmdMove`, `CmdStop`, `CmdHoldPos`, `CmdPatrol` | Attack, move, stop, hold position, patrol | command card |
| Alt+O, Alt+S, Alt+L, Alt+H, Alt+Q | `OptionsButton`, `SaveGameButton`, `LoadGameButton`, `HelpButton`, `QuitButton` | Options, save, load, help, quit | menu |

The German files have the same letters as the English defaults here, except
move (B, for Bewegen) and quit (Alt+B, for beenden). M and Alt+Q are the
English letters: Alt+Q is on the manual page; M was not checked on English
files.

## Keys of the installed game

Hotkeys depend on the game's language, and a player can change the
command-card keys with a `CustomKeys.txt` in the install folder. With the
game's files on the machine, the `warcraft3` reader
(`polyhost/services/game_assets/warcraft3/`) reads the key of each binding
that has a `command:`, from the installed language's files and from
`CustomKeys.txt`, and the icon moves there (`build.remap`). On the German
files, Move moves from M to B and Quit from Alt+Q to Alt+B; every other key
stays. A command the reader does not find keeps its default key. The reader
reads no pictures: the painted command-button icons read worse than the
shipped silhouettes (`docs/FUTURE_WORK.md`).

Control groups: 1 to 0 select a group, Ctrl+digit creates one, Shift+digit
adds the selection to the active group. Each digit has its own unit, drawn
once at full height: 1 footman, 2 archer, 3 knight, 4 dwarf, 5 wolf rider,
6 trebuchet, 7 gryphon, 8 wyvern, 9 dragon, 0 peasant. The game does not tie a
group number to a unit type; the icons only suggest a habit.

## Left out

- The letter keys alone, except the five unit commands. They train, build and
  cast, and what each does depends on the selection.
- F4, F5 and F7. The page lists F1 to F7 as hero keys, but a melee game allows
  three heroes; only campaigns and custom maps reach a fourth. F6 shows quick
  save.
- Alt+T and Alt+C in the English game for the minimap terrain and creep
  buttons (Alt+K and Alt+R in German): the English letters were not checked,
  and Alt+C already centres on the portrait unit.
- Arrow keys (scroll the view): the arrows keep their own legends.

## Placement

As for Age of Empires II (`../aoe2/SOURCES.md`): every icon sits at the right
edge and uses the full height, and the firmware clears 3 px around it, so a
letter legend stays whole. The F-key areas use AoE2's measured legend widths:
F1 to F3 and F8 34×40, F9 40×40. F10 to F12 are 40×40 as well, although their
legends end at x 47 to 51 (AoE2 measured 21×40 to keep them whole): at 21 px the
icons could not be read, so they cover the right part of the legend (maintainer's
choice, 2026-10-28). The control groups are 48×40, drawn 1:1, 5 px from the
right edge.

All icons are flat 1-bit silhouettes, as in the AoE2 set. Save, Load, Help and
Chat are solid shapes and fill a 34×34 box instead of 40×40, so they do not
outweigh the outline icons; Zoom in, Zoom out, Music and Screenshot fill a 30×30
box (maintainer's choice). F1 to F3 show three different heroes: a paladin, an
archmage and a lich. Insert and Delete show a person with an arrow round their feet,
pointing left for Insert and right for Delete (`rotate_icons()`). The control groups show one unit each, not two as in AoE2: drawn
twice, the thin units (spear, bow, trebuchet) broke apart (maintainer's choice).
Ctrl adds a plus, Shift a plus in a ring.

ESC shows WARCRAFT over a large III in Cinzel Black (SIL OFL 1.1, the `wght`
900 instance of `ofl/cinzel/Cinzel[wght].ttf` from google/fonts at commit
e7db6ca), drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25). The game's logo art is not used.
A pixel of WARCRAFT is lit from grey 60 of 255 and a pixel of III from 110: at
110 the serifs of WARCRAFT break off, and at 60 those of III join.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `hero1.png` | game-icons.net `lorc/visored-helm` | lorc | CC BY 3.0 |
| `hero2.png` | game-icons.net `delapouite/wizard-face` | delapouite | CC BY 3.0 |
| `hero3.png` | game-icons.net `lorc/crowned-skull` | lorc | CC BY 3.0 |
| `idleworker.png` | game-icons.net `delapouite/miner` | delapouite | CC BY 3.0 |
| `townhall.png` | game-icons.net `delapouite/castle` | delapouite | CC BY 3.0 |
| `lastevent.png` | game-icons.net `lorc/ringing-bell` | lorc | CC BY 3.0 |
| `subgroup.png` | game-icons.net `lorc/cycle` | lorc | CC BY 3.0 |
| `portrait.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotateleft.png`, `rotateright.png` | Font Awesome Free 6.5.2 `street-view` (solid), with an arrow drawn by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `questlog.png` | game-icons.net `lorc/scroll-unfurled` | lorc | CC BY 3.0 |
| `gamemenu.png` | Font Awesome Free 6.5.2 `bars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `allies.png` | game-icons.net `delapouite/shaking-hands` | delapouite | CC BY 3.0 |
| `chatlog.png` | game-icons.net `delapouite/notebook` | delapouite | CC BY 3.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png` | Font Awesome Free 6.5.2 `file-pen` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `signal.png` | Font Awesome Free 6.5.2 `location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `allycolors.png` | Font Awesome Free 6.5.2 `palette` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `formation.png` | Font Awesome Free 6.5.2 `table-cells` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `stop.png` | Font Awesome Free 6.5.2 `hand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `patrol.png` | Font Awesome Free 6.5.2 `right-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `attack.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `move.png` | game-icons.net `lorc/boot-prints` | lorc | CC BY 3.0 |
| `hold.png` | game-icons.net `lorc/checked-shield` | lorc | CC BY 3.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `door-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `music.png` | Font Awesome Free 6.5.2 `music` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sound.png` | Font Awesome Free 6.5.2 `volume-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `chatall.png` | game-icons.net `delapouite/megaphone` | delapouite | CC BY 3.0 |
| `chatallies.png` | game-icons.net `lorc/conversation` | lorc | CC BY 3.0 |
| `group1.png`, `groupnew1.png`, `groupadd1.png` | game-icons.net `lorc/spartan` | lorc | CC BY 3.0 |
| `group2.png`, `groupnew2.png`, `groupadd2.png` | game-icons.net `lorc/bowman` | lorc | CC BY 3.0 |
| `group3.png`, `groupnew3.png`, `groupadd3.png` | game-icons.net `delapouite/horse-head` | delapouite | CC BY 3.0 |
| `group4.png`, `groupnew4.png`, `groupadd4.png` | game-icons.net `delapouite/dwarf-face` | delapouite | CC BY 3.0 |
| `group5.png`, `groupnew5.png`, `groupadd5.png` | game-icons.net `lorc/wolf-head` | lorc | CC BY 3.0 |
| `group6.png`, `groupnew6.png`, `groupadd6.png` | game-icons.net `delapouite/trebuchet` | delapouite | CC BY 3.0 |
| `group7.png`, `groupnew7.png`, `groupadd7.png` | game-icons.net `delapouite/griffin-symbol` | delapouite | CC BY 3.0 |
| `group8.png`, `groupnew8.png`, `groupadd8.png` | game-icons.net `lorc/wyvern` | lorc | CC BY 3.0 |
| `group9.png`, `groupnew9.png`, `groupadd9.png` | game-icons.net `lorc/dragon-head` | lorc | CC BY 3.0 |
| `group0.png`, `groupnew0.png`, `groupadd0.png` | game-icons.net `delapouite/farmer` | delapouite | CC BY 3.0 |
