# Simutrans overlay: sources

`scripts/generate_app_overlays.py` renders `simutrans.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `simutrans_template` (1 file) | Simutrans with the pak64 pakset: `simutrans` on Linux and macOS, `simutrans.exe` on Windows, `com.simutrans.Simutrans` as a Flatpak |

`simutrans` is the executable target in `CMakeLists.txt`
(`add_executable(simutrans MACOSX_BUNDLE)`), the `Exec=` line of
`src/linux/simutrans.desktop` and the `<binary>` of
`src/linux/com.simutrans.Simutrans.metainfo.xml.in`, whose `<id>` is the
Flatpak id. `src/Windows/simres.rc` names the Windows file `SIMUTRANS.EXE`. All
four files are from <https://github.com/simutrans/simutrans> at tag `125.0.1`.
Names not checked on an install. The desktop file has no `StartupWMClass=`, so
the name a Wayland or X11 session reports was not measured.

The host cannot see which pakset is loaded: the process name is the same for
all of them. The set shows the pak64 keys for every pakset.

## Shortcut reference

Simutrans has no key table in the engine. Every pakset assigns its tool keys in
its own `config/menuconf.tab`, and the engine adds a few fixed keys.

- Tool keys: `pak64/config/menuconf.tab` of the Simutrans pakset repository,
  revision 2234,
  <https://svn.code.sf.net/p/simutrans/code/!svn/bc/2234/pak64/config/menuconf.tab>,
  read 2026-11-14. pak64 is the pakset the Simutrans installers offer first.
  The GitHub mirror `simutrans/simutrans` holds the engine only, so the pakset
  file was read from the project's Subversion server.
- Fixed keys: `interaction_t::interactive_event()` in
  `src/simutrans/siminteraction.cc`, <https://github.com/simutrans/simutrans>,
  tag `125.0.1` (commit 40bbb12894793cc7c6ae5c93f31a16e7e7707627), read
  2026-11-14.
- How a key string is read: `str_to_key()` in `src/simutrans/tool/simmenu.cc`
  at the same tag. The tool names are from the comments in `menuconf.tab` and
  the `get_tooltip()` texts in `src/simutrans/tool/simtool.h` and
  `simtool-dialogs.h`.

**Other paksets differ.** pak128, pak128.Britain, pak128.German, pak192.comic
and the others ship their own `menuconf.tab` with other keys and other
toolbars. This set is right for pak64 only.

The engine compares the character a key types, not the key. In `menuconf.tab`
`a` is the A key, `A` is Shift+A and `^A` is Ctrl+A. The characters
`>` `<` `!` `#` `%` `"` `?` `+` are drawn on the Shift layer of the keys that
type them on a US layout (Shift+. Shift+, Shift+1 Shift+3 Shift+5 Shift+'
Shift+/ Shift+=). On another layout these eight are on other keys.

| Key | `menuconf.tab` entry | Action |
|---|---|---|
| A | `general_tool[0]`, `a` | Query tool |
| R | `general_tool[1]`, `r` | Remove tool |
| U | `general_tool[2]`, `u` | Raise land |
| D | `general_tool[3]`, `d` | Lower land |
| B | `general_tool[7]`, `b` | Remove block reservation |
| G | `general_tool[8]`, `g` | Build transformer station |
| H | `general_tool[27]`, `h` | Build headquarters |
| T | `toolbar[3][13]` `general_tool[14]`, `t` | Build the default railway track |
| S | `toolbar[6][10]` `general_tool[14]`, `s` | Build the default road |
| L | `toolbar[9][14]` `general_tool[14]`, `l` | Build the default power line |
| E | `toolbar[3][14]` `general_tool[18]`, `e` | Build overhead lines over a track |
| Z | `toolbar[0][32]` `toolbar[LAST_USED]`, `z` | Last used tools |
| Shift+M | `general_tool[6]`, `M` | Place a label (marker) |
| Shift+C | `general_tool[9]`, `C` | Found a city |
| Ctrl+K | `general_tool[35]`, `^K` | Buy a house |
| P | `simple_tool[0]`, `p` | Pause |
| Ctrl+P | `toolbar[10][28]` `simple_tool[0]`, `^p` | Pause |
| . | `toolbar[0][30]` `simple_tool[7]` `+1`, `.` | Increase game speed |
| , | `toolbar[0][31]` `simple_tool[7]` `-1`, `COMMA` | Reduce game speed |
| Shift+W | `simple_tool[1]`, `W` | Fast forward |
| C | `simple_tool[2]`, `c` | Screenshot |
| Ctrl+Z | `simple_tool[4]`, `^Z` | Undo the last way |
| Shift+P | `simple_tool[5]`, `P` | Switch player |
| Ctrl+Q | `simple_tool[17]`, `^Q` | Quit |
| Shift+. | `simple_tool[8]`, `>` | Zoom in |
| Shift+, | `simple_tool[9]`, `<` | Zoom out |
| Shift+R | `simple_tool[16]`, `R` | Rotate the map by 90 degrees |
| Shift+U | `simple_tool[15]`, `U` | Underground view |
| Ctrl+U | `toolbar[1][16]` `simple_tool[15]` `K`, `^U` | Sliced underground view |
| Shift+= | `toolbar[1][17]` `simple_tool[15]` `I`, `+` | Sliced view one level up |
| - | `toolbar[1][18]` `simple_tool[15]` `D`, `-` | Sliced view one level down |
| Shift+3 | `simple_tool[12]`, `#` | Show grid |
| Shift+1 | `simple_tool[11]`, `!` | Show station names |
| Shift+5 | `simple_tool[13]`, `%` | Hide trees |
| Shift+' | `simple_tool[14]`, `"` | Hide buildings |
| V | `simple_tool[10]`, `v` | Show station coverage |
| Shift+O | `simple_tool[34]`, `O` | Show owner colours |
| Ctrl+B | `simple_tool[33]`, `^b` | Show block reservations |
| / | `simple_tool[20]`, `/` | Vehicle tooltips |
| ] | `simple_tool[43]`, `]` | Highlight single ways |
| Shift+/ | `dialog_tool[0]`, `?` | Help |
| Shift+Q | `dialog_tool[1]`, `Q` | Options |
| M | `dialog_tool[2]`, `m` | Map |
| W | `dialog_tool[3]`, `w` | Line management |
| Shift+B | `dialog_tool[4]`, `B` | Messages |
| F | `dialog_tool[5]`, `f` | Finances |
| K | `dialog_tool[6]`, `k` | Player list |
| Shift+J | `dialog_tool[11]`, `J` | Jump to a map position |
| N | `dialog_tool[28]`, `n` | Game information |
| F6 | `dialog_tool[31]`, `F6` | Scenario information |
| F7 | `dialog_tool[38]`, `F7` | Way builder |
| Ctrl+O | `dialog_tool[12]`, `^O` | Load game |
| Ctrl+S | `dialog_tool[13]`, `^S` | Save game |
| Shift+H | `dialog_tool[14]`, `H` | Station list |
| Shift+V | `dialog_tool[15]`, `V` | Convoy list |
| Shift+T | `dialog_tool[16]`, `T` | Town list |
| Shift+G | `dialog_tool[17]`, `G` | Goods list |
| Shift+F | `dialog_tool[18]`, `F` | Factory list |
| Shift+A | `dialog_tool[19]`, `A` | Attraction list |
| Ctrl+D | `dialog_tool[32]`, `^d` | Depot list |
| Ctrl+E | `dialog_tool[33]`, `^e` | Vehicle list |
| Ctrl+M | `toolbar[11][9]` `dialog_tool[25]`, `^M` | Label list |
| F1 | fixed in `siminteraction.cc` | Help (for the top window, if it has a help page) |
| Backspace | fixed in `siminteraction.cc` | Close all windows |
| Delete | fixed in `siminteraction.cc` | Close the top window |

No key changes its meaning with the selection: a tool key picks the tool and a
window key opens the window, whatever is open.

## Left out

- Escape (close the top window, like Delete): ESC shows the program mark.
- The arrow keys (scroll the map): the arrows keep their own legends. The
  keypad keys that scroll have no cell.
- Ctrl+W (`toolbar[2][13]`, `general_tool[39]` with parameter 0: the climate
  tool set to the water climate). It is a map editor tool with eight climates
  and a key for one of them only.
- `general_tool[11]` (plant a tree): its key field is a single space, which
  `simmenu.cc` skips, so it has no key.
- Every other key opens the keyboard help (`keys.txt`) in the engine; that is
  not drawn.
- F12 on a Steam build is left to Steam for its screenshot (`STEAM_BUILT` in
  `siminteraction.cc`); pak64 binds nothing to it.

## Placement

As for OpenTTD (`../openttd/SOURCES.md`): every icon sits at the right edge and
uses the full height, and the firmware clears 3 px around it, so a letter
legend stays whole. F1 is 34×40, F6 and F7 are 30×40, the widths of the OpenTTD
set. Shift+H is 30×40 because the station icon is the OpenTTD one, drawn at
that size.

All icons are flat 1-bit silhouettes. The same action has the same icon source
as in the OpenTTD and OpenRCT2 sets: pause, zoom, screenshot, quit, save, load,
map, finances, the town, station and industry lists, raise and lower land,
build railway and road, the game speed arrows, rotate, underground view, grid,
messages and the two close-window keys. The solid shapes fill a smaller box in
the bottom-right corner so they do not outweigh the outline icons (`INK` in
`fetch_icons.py`).

Composed in `fetch_icons.py`:

- U and D (raise and lower land): ground with a hill or a pit and an arrow, the
  shapes of the OpenTTD set (`terrain()`).
- T: the railway track turned upright (`upright_rail()`).
- Shift+H: a train under a roof, drawn by the OpenTTD set's `station()`.
- Shift+C: the city of the town list, moved up and left, with a plus in the
  corner.
- Shift+5 and Shift+': the tree and the house with a bar from corner to corner,
  as the OpenTTD set draws its invisibility keys.
- B: the signal of Ctrl+B with the same bar.
- Shift+= and -: the layers of Ctrl+U at 26 px with an arrow up or down at the
  left.

ESC shows "Simu" over "trans" in Russo One (SIL OFL 1.1,
`ofl/russoone/RussoOne-Regular.ttf` from google/fonts at commit e7db6ca), both
lines at the largest one size at which each fits 70 px wide and both, 2 px
apart, fit 38 px high, drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25).

The game's own logo is not used. `LICENSE.txt` at tag `125.0.1` puts the source
code, documentation and images under the Artistic License 1.0, which is not on
this repository's list of licences compatible with GPL-3.0-or-later. The pakset
graphics have their own licence (`pak64/licence.txt`) and are not used either.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `query.png` | Font Awesome Free 6.5.2 `arrow-pointer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `remove.png` | Material Design Icons `bulldozer` | Pictogrammers | Apache-2.0 |
| `showblocks.png` | Material Design Icons `traffic-light` | Pictogrammers | Apache-2.0 |
| `transformer.png` | Font Awesome Free 6.5.2 `plug-circle-bolt` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `headquarters.png` | Font Awesome Free 6.5.2 `building` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `buildroad.png` | Font Awesome Free 6.5.2 `road` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `electrify.png` | Font Awesome Free 6.5.2 `bolt` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `powerline.png` | Material Design Icons `transmission-tower` | Pictogrammers | Apache-2.0 |
| `marker.png` | Font Awesome Free 6.5.2 `signs-post` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `buyhouse.png` | Font Awesome Free 6.5.2 `house-circle-check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lastused.png` | Font Awesome Free 6.5.2 `clock-rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `faster.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `slower.png` | Font Awesome Free 6.5.2 `backward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fastforward.png` | Font Awesome Free 6.5.2 `forward-fast` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `undo.png` | Font Awesome Free 6.5.2 `arrow-rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `switchplayer.png` | Font Awesome Free 6.5.2 `people-arrows` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotatemap.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `underground.png` | Material Design Icons `tunnel` | Pictogrammers | Apache-2.0 |
| `sliced.png` | Font Awesome Free 6.5.2 `layer-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `grid.png` | Material Design Icons `grid` | Pictogrammers | Apache-2.0 |
| `names.png` | Font Awesome Free 6.5.2 `tag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `coverage.png` | Material Design Icons `map-marker-radius` | Pictogrammers | Apache-2.0 |
| `owner.png` | Font Awesome Free 6.5.2 `flag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tooltips.png` | Material Design Icons `tooltip-text` | Pictogrammers | Apache-2.0 |
| `singleways.png` | Font Awesome Free 6.5.2 `highlighter` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jump.png` | Font Awesome Free 6.5.2 `location-crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closetop.png` | Font Awesome Free 6.5.2 `rectangle-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closeall.png` | Material Design Icons `close-box-multiple` | Pictogrammers | Apache-2.0 |
| `minimap.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lines.png` | Font Awesome Free 6.5.2 `route` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `finances.png` | Font Awesome Free 6.5.2 `sack-dollar` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `players.png` | Font Awesome Free 6.5.2 `users` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `messages.png` | Font Awesome Free 6.5.2 `envelope` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gameinfo.png` | Font Awesome Free 6.5.2 `circle-info` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scenarioinfo.png` | Font Awesome Free 6.5.2 `list-check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `waybuilder.png` | Material Design Icons `map-marker-path` | Pictogrammers | Apache-2.0 |
| `convoys.png` | Font Awesome Free 6.5.2 `train` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `towns.png` | Font Awesome Free 6.5.2 `city` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `goods.png` | Font Awesome Free 6.5.2 `boxes-stacked` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `factories.png` | Font Awesome Free 6.5.2 `industry` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `attractions.png` | Font Awesome Free 6.5.2 `landmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `depots.png` | Font Awesome Free 6.5.2 `warehouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `vehicles.png` | Font Awesome Free 6.5.2 `truck` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `labels.png` | Font Awesome Free 6.5.2 `tags` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help_f1.png` | Font Awesome Free 6.5.2 `circle-question` (solid), in the 34 px area of F1 | Fonticons, Inc. | CC BY 4.0 |
| `buildrail.png` | game-icons.net `delapouite/railway`, turned by `fetch_icons.py` | delapouite | CC BY 3.0 |
| `stations.png` | Font Awesome Free 6.5.2 `train-subway` (solid), with a roof drawn by the OpenTTD set's `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `foundcity.png` | Font Awesome Free 6.5.2 `city` (solid), with a plus drawn by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `hidetrees.png` | Font Awesome Free 6.5.2 `tree` (solid), struck through by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `hidehouses.png` | Font Awesome Free 6.5.2 `house` (solid), struck through by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `clearblock.png` | Material Design Icons `traffic-light`, struck through by `fetch_icons.py` | Pictogrammers | Apache-2.0 |
| `sliceup.png`, `slicedown.png` | Font Awesome Free 6.5.2 `layer-group` (solid), with an arrow drawn by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `raise.png`, `lower.png` | drawn by `fetch_icons.py` | | |
| `program.png` | "Simu" over "trans" set in Russo One by `fetch_icons.py` | Jovanny Lemonad (font) | SIL OFL 1.1 |

Material Design Icons are from Templarian/MaterialDesign at commit 2424e74.
