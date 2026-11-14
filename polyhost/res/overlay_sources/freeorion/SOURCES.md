# FreeOrion overlay: sources

`scripts/generate_app_overlays.py` renders `freeorion.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `freeorion_template` (2 files) | the FreeOrion client: `freeorion` on Linux, `FreeOrion.exe` on Windows, the `FreeOrion` app on macOS, `org.freeorion.FreeOrion` as a Flatpak |

`freeorion` is the client's executable target in `CMakeLists.txt`
(`add_executable(freeorion "")`, with `OUTPUT_NAME FreeOrion` on Windows and
macOS) and the `Exec=` line of `packaging/org.freeorion.FreeOrion.desktop`,
whose file name is the Flatpak id. The server (`freeoriond`) and the AI client
(`freeorionca`) have no window. Names not checked on an install.

## Shortcut reference

The hotkeys the client registers with `Hotkey::AddHotkey` in `UI/MapWnd.cpp`
(the map screen), `client/human/GGHumanClientApp.cpp` (full screen, quit) and
`UI/CUIControls.cpp` (autocomplete) of
<https://github.com/freeorion/freeorion>, release tag `v0.5.1.2` (commit
`1d4211edeab19cf5f5096cda7c9f54e7b3b3dbf7`), read 2026-11-14. The list was
compared with the `HOTKEY_` entries of `default/stringtables/en.txt`: every
entry that a registration uses is in the table below or under "Left out". A
user changes the keys in Options, Keyboard shortcuts; this overlay shows the
defaults.

| Key | Hotkey | Name in the source |
|---|---|---|
| Ctrl+Enter | End turn | `ui.turn.end` |
| Ctrl+N | Situation report | `ui.map.sitrep` |
| Ctrl+R | Research | `ui.research` |
| Ctrl+P | Production | `ui.production` |
| Ctrl+I | Government | `ui.government` |
| Ctrl+D | Ship design | `ui.design` |
| Ctrl+O | Objects list | `ui.map.objects` |
| Ctrl+E | Empires | `ui.map.empires` |
| Alt+T | Messages | `ui.map.messages` |
| F1 | Pedia | `ui.pedia` |
| F10 | Game menu | `ui.gamemenu` |
| Ctrl+Z | Zoom in | `ui.zoom.in` |
| Ctrl+X | Zoom out | `ui.zoom.out` |
| Ctrl+H | Zoom to home system | `ui.map.system.zoom.home` |
| Ctrl+comma, Ctrl+period | Zoom to previous, next system | `ui.map.system.zoom.prev`, `.next` |
| Ctrl+Shift+comma, Ctrl+Shift+period | Zoom to previous, next owned system | `ui.map.system.owned.zoom.prev`, `.next` |
| Ctrl+F, Ctrl+G | Zoom to previous, next fleet | `ui.map.fleet.zoom.prev`, `.next` |
| Alt+F, Alt+G | Zoom to previous, next idle fleet | `ui.map.fleet.idle.zoom.prev`, `.next` |
| Ctrl+Up, Down, Left, Right | Pan the map | `ui.pan.up`, `.down`, `.left`, `.right` |
| Alt+L | Toggle map scale line | `ui.map.scale.legend` |
| Alt+C | Toggle map scale circle | `ui.map.scale.circle` |
| Alt+Enter | Toggle full screen | `video.fullscreen` |
| Ctrl+C | Copy (text fields) | `ui.copy` |
| Ctrl+V | Paste (text fields) | `ui.paste` |
| Ctrl+A | Select all (text fields) | `ui.select.all` |

Two keys have a second hotkey in the table. The map screen meaning is drawn:

| Key | Drawn | Also registered (not drawn) |
|---|---|---|
| Ctrl+X | Zoom out | Cut, in a text field (`ui.cut`) |
| Ctrl+D | Ship design | Deselect, in a text field (`ui.select.none`) |

The game registers the Ctrl key on every system. Whether the macOS build
reports Command for it was not checked, so there is one set.

## Left out

- Escape (Return to map, `ui.map.open`): Esc has the program mark.
- Tab (Autocomplete, `ui.autocomplete`): works only in the chat text field.
- Ctrl+keypad plus and Ctrl+keypad minus (zoom, `ui.zoom.in.alt`,
  `ui.zoom.out.alt`): the keypad has no cell.
- Hotkeys registered without a key: Graphs (`ui.map.graphs`), Exit (`exit`),
  Quit (`quit`).
- `ui.focus.prev` and `ui.focus.next`: commented out in the source.

## Placement

As for Freeciv (`../freeciv/SOURCES.md`): every icon sits at the right edge and
uses the full height, and the firmware clears 3 px around it, so a letter legend
stays whole. F1 is 34x40, the width the AoE2 set measured to keep that legend
whole.

The "previous" and "next" keys show what they go to (a sun for a system, a
ringed planet for an owned system, a rocket for a fleet, an anchor for an idle
fleet) in a 30x26 box, with an arrow to the left or right above it
(`arrow_icons()`).

End turn, research, zoom, full screen and Pedia use the icons the Freeciv and
Civilization IV sets use for the same actions.

Layers: plain (F1, F10), Ctrl, Alt, and Ctrl+Shift in the second file.

## ESC mark

ESC shows "FREE" over "ORION" in Orbitron Bold (SIL OFL 1.1,
`ofl/orbitron/Orbitron[wght].ttf` from google/fonts at commit e7db6ca, weight
700), drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25).

The game's logo is not used: `default/COPYING` puts the art under CC BY-SA
3.0, and the source code under GPL version 2 without "or any later version".
Neither is compatible with this repository's GPL-3.0-or-later.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Where each icon file comes from. The table below gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`, which
`fetch_icons.py` fetches through.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`

| File | Source | Author | Licence |
|---|---|---|---|
| `endturn.png` | Font Awesome Free 6.5.2 `hourglass-end` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sitrep.png` | Font Awesome Free 6.5.2 `clipboard-list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `research.png` | Font Awesome Free 6.5.2 `flask` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `production.png` | Font Awesome Free 6.5.2 `industry` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `government.png` | Font Awesome Free 6.5.2 `landmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `design.png` | Font Awesome Free 6.5.2 `pen-ruler` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `objects.png` | Font Awesome Free 6.5.2 `list-ul` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `empires.png` | Font Awesome Free 6.5.2 `flag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `messages.png` | Font Awesome Free 6.5.2 `comments` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pedia.png` | Font Awesome Free 6.5.2 `book-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `menu.png` | Font Awesome Free 6.5.2 `bars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `homesystem.png` | Font Awesome Free 6.5.2 `house` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `panup.png` | Font Awesome Free 6.5.2 `arrow-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pandown.png` | Font Awesome Free 6.5.2 `arrow-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `panleft.png` | Font Awesome Free 6.5.2 `arrow-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `panright.png` | Font Awesome Free 6.5.2 `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scaleline.png` | Font Awesome Free 6.5.2 `ruler-horizontal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scalecircle.png` | Font Awesome Free 6.5.2 `compass-drafting` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `copy.png` | Font Awesome Free 6.5.2 `copy` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `paste.png` | Font Awesome Free 6.5.2 `paste` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `selectall.png` | Font Awesome Free 6.5.2 `check-double` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `system_prev.png`, `system_next.png` | Font Awesome Free 6.5.2 `sun` with `arrow-left` or `arrow-right` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `ownedsystem_prev.png`, `ownedsystem_next.png` | game-icons.net `lorc/ringed-planet` with Font Awesome Free 6.5.2 `arrow-left` or `arrow-right`, composed by `fetch_icons.py` | lorc (planet); Fonticons, Inc. (arrow) | CC BY 3.0; CC BY 4.0 |
| `fleet_prev.png`, `fleet_next.png` | Font Awesome Free 6.5.2 `rocket` with `arrow-left` or `arrow-right` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `idlefleet_prev.png`, `idlefleet_next.png` | Font Awesome Free 6.5.2 `anchor` with `arrow-left` or `arrow-right` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "FREE" over "ORION" set in Orbitron Bold by `fetch_icons.py` | The Orbitron Project Authors (font) | SIL OFL 1.1 |
