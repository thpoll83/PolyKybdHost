# Warcraft III overlay: sources

`scripts/generate_app_overlays.py` renders `warcraft3.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `warcraft3_template` (1 file) | Warcraft III classic, 1.26 to 1.31: `war3.exe`, `Warcraft III.exe`, `Frozen Throne.exe`, on Windows and under Wine |

The app names were not checked on an install.

## Shortcut reference

The default hotkeys printed on the back of the Reign of Chaos manual, as listed
on <https://warcraft.wiki.gg/wiki/Warcraft_III:_Hotkeys> (read 2026-10-28). The
Frozen Throne uses the same defaults; that was not checked. A user's
`CustomKeys.txt` changes the letter keys only, which this overlay leaves blank.

Control groups: 1 to 0 select a group, Ctrl+digit creates one, Shift+digit
adds the selection to the active group. Each digit has its own unit, drawn
twice as a group: 1 footman, 2 archer, 3 knight, 4 dwarf, 5 wolf rider,
6 trebuchet, 7 gryphon, 8 wyvern, 9 dragon, 0 peasant. The game does not tie a
group number to a unit type; the icons only suggest a habit.

## Left out

- The letter keys alone. They train, build and cast, and what each does
  depends on the selection.
- F4 to F7. The page lists F1 to F7 as hero keys, but a melee game allows three
  heroes; only campaigns and custom maps reach a fourth.
- Print Screen (screenshot): the key has no overlay cell.
- Arrow keys (scroll the view): the arrows keep their own legends.

## Placement

As for Age of Empires II (`../aoe2/SOURCES.md`): every icon sits at the right
edge and uses the full height, and the firmware clears 3 px around it, so a
letter legend stays whole. The F-key areas use AoE2's measured legend widths:
F1 to F3 and F8 34×40, F9 40×40, F10 to F12 21×40. The control groups are
48×40, drawn 1:1, 5 px from the right edge.

All icons are flat 1-bit silhouettes, as in the AoE2 set. Save, Load, Help and
Chat are solid shapes and fill a 34×34 box instead of 40×40, so they do not
outweigh the outline icons. F1 to F3 stamp the hero number into the helmet. The
control groups are drawn twice, like AoE2's; Ctrl adds a plus, Shift a plus in
a ring.

ESC shows WARCRAFT over a large III in Cinzel Black (SIL OFL 1.1, the `wght`
900 instance of `ofl/cinzel/Cinzel[wght].ttf` from google/fonts at commit
e7db6ca), drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25). The game's logo art is not used.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `hero.png` | game-icons.net `lorc/visored-helm` | lorc | CC BY 3.0 |
| `idleworker.png` | game-icons.net `delapouite/miner` | delapouite | CC BY 3.0 |
| `townhall.png` | game-icons.net `delapouite/castle` | delapouite | CC BY 3.0 |
| `lastevent.png` | game-icons.net `lorc/ringing-bell` | lorc | CC BY 3.0 |
| `subgroup.png` | game-icons.net `lorc/cycle` | lorc | CC BY 3.0 |
| `portrait.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotateleft.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotateright.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `questlog.png` | game-icons.net `lorc/scroll-unfurled` | lorc | CC BY 3.0 |
| `gamemenu.png` | Font Awesome Free 6.5.2 `bars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `allies.png` | game-icons.net `delapouite/shaking-hands` | delapouite | CC BY 3.0 |
| `chatlog.png` | game-icons.net `delapouite/notebook` | delapouite | CC BY 3.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `door-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `music.png` | Font Awesome Free 6.5.2 `music` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sound.png` | Font Awesome Free 6.5.2 `volume-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
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
