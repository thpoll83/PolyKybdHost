# FreeCol overlay: sources

`scripts/generate_app_overlays.py` renders `freecol.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `freecol_template` (2 files) | FreeCol: the names `freecol` (`freecol.exe` on Windows), `net-sf-freecol-FreeCol` and `org.freecol.FreeCol`, and a `java` or `javaw` process whose window title starts with "FreeCol" and a version number |

How the names were found:

- FreeCol is a Java program (`Main-Class` `net.sf.freecol.FreeCol` in
  `build.xml`). Started with `java -jar FreeCol.jar`, or through the `freecol`
  script that `packaging/common/freecol.desktop` starts, the process is `java`
  (or `javaw` on Windows), the name that JetBrains IDEs, Minecraft, Ghidra,
  DBeaver and Unciv also have. Those entries in `overlay-mapping.poly.yaml`
  tell the programs apart by window title, so the FreeCol set is a
  `titles-startswith` branch of the existing `java` and `javaw` entries.
- The window title is "FreeCol " and the version: `getFrameName()` in
  `src/net/sf/freecol/client/gui/FreeColFrame.java` returns
  `"FreeCol " + FreeCol.getVersion()`. The branch asks for a digit after the
  name, so an IDE window of a project named FreeCol ("FreeCol – Foo.java") is
  not matched.
- `freecol.exe` is the Windows launcher that `build.xml` packs into the
  installer (`<fileset ... includes="freecol.exe"/>`). Whether the game then
  runs inside `freecol.exe` or in a `javaw.exe` it starts was not checked; both
  are routed.
- `net-sf-freecol-FreeCol` is the window class Java gives a Swing program on
  X11 (the main class with dots replaced), as for Ghidra's `ghidra-Ghidra`.
- `org.freecol.FreeCol` is the Flathub id. It is not in the repository.

Names not checked on an install.

## Shortcut reference

The `*.accelerator` entries of `data/strings/FreeColMessages.properties` of
<https://github.com/FreeCol/freecol>, release tag `v1.2.0` (commit
`1690a5f3a1ba40f72e68ce3ae0a88818f9cfa3d8`), read 2026-11-14. `FreeColAction`
(`src/net/sf/freecol/client/gui/action/FreeColAction.java`) reads
`<action id>.accelerator` from that file and passes it to
`KeyStroke.getKeyStroke()`. A user changes the keys in Preferences, Keyboard
accelerators; this overlay shows the defaults.

The entries name the Control key ("control C") on every system, so macOS uses
the same set.

| Key | Action |
|---|---|
| B | Build colony |
| F | Fortify |
| S | Sentry |
| W | Wait |
| Space | Skip unit |
| D | Disband unit |
| Z | Clear orders |
| H | Go to (`gotoAction`) |
| G | Go to tile |
| O | Execute go to orders |
| R | Build road |
| P | Plow |
| C | Clear forest |
| L | Load |
| U | Unload |
| A | Assign trade route |
| N | Rename |
| Tab | Next unit on tile (`changeAction`; in a colony tile: enter colony, on a carrier: select carrier) |
| Ctrl+A | Ranged attack |
| Home, Page Up, End, Page Down | Move north-west, north-east, south-west, south-east (the secondary accelerators of `moveAction`) |
| Enter | End turn |
| E | Europe |
| T | Trade routes |
| Ctrl+C | Center |
| Ctrl+T | Chat |
| Ctrl+B | Display borders |
| Ctrl+G | Display grid |
| Ctrl+F | Find settlement |
| Ctrl+M | Map controls |
| Shift+T | Show tile |
| Ctrl+Shift+V | Toggle view mode |
| + (Shift+=) | Zoom in ("typed +") |
| - | Zoom out ("typed -") |
| Ctrl+- | Zoom out the mini-map |
| Alt+Enter | Toggle windowed mode |
| Ctrl+N | New game |
| Ctrl+O | Open |
| Ctrl+S | Save |
| Ctrl+X | Save and exit |
| Ctrl+Q | Quit |
| Ctrl+P | Preferences |
| Ctrl+R | Reconnect |
| F1 | Religious advisor |
| F2 | Labour advisor |
| F3 | Colony advisor |
| F4 | Foreign affairs advisor |
| F5 | Indian advisor |
| F6 | Continental Congress |
| F7 | Military advisor |
| F8 | Naval advisor |
| F9 | Trade advisor |
| F11 | Turn report |
| F12 | Requirements |
| Shift+F1 | Cargo report |
| Shift+F2 | Exploration report |
| Shift+F3 | History report |
| Shift+F4 | Production report |
| Shift+F5 | Education report |
| Shift+F9 | Show difficulty level |
| Shift+F11 | Show game options |
| Shift+F12 | Show map generator options |

"typed +" is the character `+`. On a US layout that is Shift+`=`, and the
overlay draws it there. On a layout with `+` on another key the icon is on the
wrong key.

## Left out

- The arrow keys (move north, south, west, east): they keep their own legends.
  The keypad keys (the primary move accelerators, and the secondary mini-map
  zoom keys) have no cell.
- Ctrl+PLUS (zoom in the mini-map): Java's `VK_PLUS` is a key that a US layout
  does not have, so on that layout only the keypad accelerator works.
- `continueAction`: its accelerator entry is empty.
- Actions without an accelerator entry (about, colopedia, declare independence,
  retire, high scores, the map editor actions and others).

## Placement

As for Freeciv (`../freeciv/SOURCES.md`): every icon sits at the right edge and
uses the full height, and the firmware clears 3 px around it, so a letter legend
stays whole. F1 to F3 and F8 are 34x40 and F4 to F7 30x40, the widths the AoE2
set measured to keep those legends whole. F9 to F12 are 40x40.

Icons shared with the Freeciv set: build colony (build city), fortify, sentry,
go to, road, plow (cultivate), load, unload, disband, clear orders, center,
chat, borders, grid, find settlement, turn report (messages) and next unit on
tile (unit selection). With the Civilization IV set: wait, religion, military
(crossed swords), Continental Congress (civics), exploration. The diagonal
move arrows are the ones of the VCMI set.

The mini-map zoom is the magnifier with "MAP" above it (`TEXT_ICONS`, drawn by
`wesnoth.text_icons()`).

Layers: plain, Ctrl, Alt (Alt+Enter), Shift, and Ctrl+Shift in the second
file.

## ESC mark

ESC shows "FreeCol" in IM Fell English SC (SIL OFL 1.1,
`ofl/imfellenglishsc/IMFeENsc28P.ttf` from google/fonts at commit e7db6ca),
drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25). A pixel is lit from grey 70 of
255; at 100 the thin strokes of the letters break.

The game's icon is not used. The source code is GPL-2.0-or-later (the header
of `src/net/sf/freecol/FreeCol.java`), which is compatible with this
repository's GPL-3.0-or-later. But the README says that the art is partly GPL
v2 and partly CC BY 4.0, "refer to the README file in the same directory as
the included content", and that per-directory note was not read for the icon.
The icon is also a coloured drawing that does not read at 1 bit in 72x40.

Font file: <https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/imfellenglishsc/IMFeENsc28P.ttf>

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/
- Bitstream Vera licence: https://dejavu-fonts.github.io/License.html

Where each icon file comes from. The table below gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`, which
`fetch_icons.py` fetches through.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`
- Material Design Icons (`mdi:<name>`): `https://raw.githubusercontent.com/Templarian/MaterialDesign/2424e748e0cc63ab7b9c095a099b9fe239b737c0/svg/<name>.svg`

| File | Source | Author | Licence |
|---|---|---|---|
| `buildcolony.png` | Font Awesome Free 6.5.2 `building-flag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fortify.png` | Font Awesome Free 6.5.2 `shield-halved` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sentry.png` | Font Awesome Free 6.5.2 `eye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `wait.png` | Font Awesome Free 6.5.2 `clock` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `skip.png` | Font Awesome Free 6.5.2 `forward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `disband.png` | Font Awesome Free 6.5.2 `user-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clearorders.png` | Font Awesome Free 6.5.2 `eraser` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `goto.png` | Font Awesome Free 6.5.2 `route` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gototile.png` | Font Awesome Free 6.5.2 `location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `executegoto.png` | Font Awesome Free 6.5.2 `play` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `road.png` | Font Awesome Free 6.5.2 `road` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `plow.png` | Font Awesome Free 6.5.2 `tractor` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clearforest.png` | game-icons.net `lorc/wood-axe` | lorc | CC BY 3.0 |
| `load.png` | Font Awesome Free 6.5.2 `right-to-bracket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `unload.png` | Font Awesome Free 6.5.2 `right-from-bracket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `assigntraderoute.png` | Font Awesome Free 6.5.2 `signs-post` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rename.png` | Font Awesome Free 6.5.2 `pen` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `nextontile.png` | Font Awesome Free 6.5.2 `layer-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rangedattack.png` | game-icons.net `lorc/cannon` | lorc | CC BY 3.0 |
| `moveNW.png` | Material Design Icons `arrow-top-left-thick` | Pictogrammers | Apache-2.0 |
| `moveNE.png` | Material Design Icons `arrow-top-right-thick` | Pictogrammers | Apache-2.0 |
| `moveSW.png` | Material Design Icons `arrow-bottom-left-thick` | Pictogrammers | Apache-2.0 |
| `moveSE.png` | Material Design Icons `arrow-bottom-right-thick` | Pictogrammers | Apache-2.0 |
| `endturn.png` | Font Awesome Free 6.5.2 `hourglass-end` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `europe.png` | Font Awesome Free 6.5.2 `earth-europe` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `traderoutes.png` | Font Awesome Free 6.5.2 `money-bill-transfer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `center.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | Font Awesome Free 6.5.2 `comment` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `borders.png` | Font Awesome Free 6.5.2 `vector-square` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `grid.png` | Font Awesome Free 6.5.2 `table-cells` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `findsettlement.png` | Font Awesome Free 6.5.2 `magnifying-glass-location` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapcontrols.png` | Font Awesome Free 6.5.2 `arrows-up-down-left-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `showtile.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `viewmode.png` | Font Awesome Free 6.5.2 `arrow-pointer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `newgame.png` | Font Awesome Free 6.5.2 `file-circle-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `open.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `saveandquit.png` | Font Awesome Free 6.5.2 `door-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `preferences.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `reconnect.png` | Font Awesome Free 6.5.2 `plug` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `religion.png` | Font Awesome Free 6.5.2 `place-of-worship` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `labour.png` | Font Awesome Free 6.5.2 `person-digging` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `colonies.png` | Font Awesome Free 6.5.2 `city` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `foreign.png` | Font Awesome Free 6.5.2 `handshake-simple` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `indian.png` | game-icons.net `delapouite/tipi` | delapouite | CC BY 3.0 |
| `congress.png` | Font Awesome Free 6.5.2 `landmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `military.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `naval.png` | Font Awesome Free 6.5.2 `ship` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `trade.png` | Font Awesome Free 6.5.2 `coins` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `turnreport.png` | Font Awesome Free 6.5.2 `envelope` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `requirements.png` | Font Awesome Free 6.5.2 `list-check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cargo.png` | Font Awesome Free 6.5.2 `boxes-stacked` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `exploration.png` | Font Awesome Free 6.5.2 `compass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `history.png` | Font Awesome Free 6.5.2 `scroll` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `production.png` | Font Awesome Free 6.5.2 `industry` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `education.png` | Font Awesome Free 6.5.2 `graduation-cap` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `difficulty.png` | Font Awesome Free 6.5.2 `gauge-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gameoptions.png` | Font Awesome Free 6.5.2 `sliders` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapoptions.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `minimapzoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid), with "MAP" in DejaVu Sans Bold, composed by `fetch_icons.py` | Fonticons, Inc. (icon), DejaVu fonts authors (text) | CC BY 4.0; Bitstream Vera licence |
| `program.png` | "FreeCol" set in IM Fell English SC by `fetch_icons.py` | Igino Marini (font) | SIL OFL 1.1 |
