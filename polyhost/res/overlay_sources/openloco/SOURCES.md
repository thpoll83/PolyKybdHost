# OpenLoco overlay: sources

`scripts/generate_app_overlays.py` renders `openloco.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `openloco_template` (1 file) | OpenLoco, the open source engine for Chris Sawyer's Locomotion: `OpenLoco` on Linux and macOS, `OpenLoco.exe` on Windows (both lowercase to `openloco`) |

The binary name is from the build files of v26.09:
`set_target_properties(App PROPERTIES OUTPUT_NAME OpenLoco)` in
`src/App/CMakeLists.txt`, and `Exec=OpenLoco %u` in
`distribution/linux/openloco.desktop`. The desktop file has no
`StartupWMClass=`, and the repository has no Flatpak manifest, so no Flatpak id
is mapped. Names not checked on an install.

## Shortcut reference

The default shortcuts registered in `Shortcuts::initialize()`,
`src/OpenLoco/src/Input/Shortcuts.cpp`, <https://github.com/OpenLoco/OpenLoco>,
tag `v26.09` (commit ec72a7d5dd8a4dd1c101948e5f4a6edcdb6b46cb), the latest
release on 2026-11-14, read the same day. Each `ShortcutManager::add()` call
ends with the default key as text ("Left Shift+Backspace"); the labels are the
shortcut names of the `StringIds::shortcut_*` in the same calls. A user's
`shortcuts.yml` changes the keys; this overlay shows the defaults.

| Key | Shortcut (`Shortcuts.cpp`) |
|---|---|
| L | Adjust land |
| W | Adjust water |
| P | Plant trees |
| X | Bulldoze area |
| T | Build tracks |
| R | Build roads |
| A | Build airports |
| D | Build ship ports |
| N | Build new vehicles |
| Z | Rotate construction object |
| V | Show vehicles list |
| S | Show stations list |
| U | Show towns list |
| I | Show industries list |
| C | Show companies list |
| Q | Show company information |
| M | Show map |
| F | Show finances |
| Tab | Show announcements list |
| Space | Toggle last announcement |
| F1 | Send message |
| F10 | Debug window |
| 1 | Underground view toggle |
| 2 to 7 | See-through tracks, roads, trees, buildings, bridges, scenery |
| 8, 9 | Height marks on land, on tracks |
| 0 | Direction arrows on tracks |
| Page Up, Page Down | Zoom view out, zoom view in |
| Enter | Rotate view |
| Pause | Pause or unpause the game |
| Backspace | Close top-most window |
| Shift+Backspace | Close all floating windows |
| Ctrl+S | Screenshot |

No shortcut changes its meaning with the selection. The defaults name the left
Shift and the left Ctrl key; the keyboard has one layer for each modifier, so
the icons also show while the right key is held.

## Left out

- Escape (Cancel construction mode): ESC shows the program mark.
- The shortcuts with an empty default key: the options and jukebox windows, the
  nine track construction shortcuts (previous and next tab, track piece and
  slope, build, remove, select position) and the three game speeds.
- The arrow keys (scroll the map): the arrows keep their own legends.

## Placement

As for OpenRCT2 (`../openrct2/SOURCES.md`), which has almost the same default
keys: every icon sits at the right edge and uses the full height, and the
firmware clears 3 px around it, so a letter legend stays whole. F1 is 34×40.
S is 30×40 because the station icon is the OpenTTD one, drawn at that size.

All icons are flat 1-bit silhouettes. The same action has the same icon source
as in the OpenRCT2 set (adjust land and water, rotate construction object,
underground view, the height marks, zoom, rotate view, pause, the two
close-window keys, screenshot, map, finances, messages, send message) and the
OpenTTD set (plant trees, build tracks, roads, airports and docks, the town,
station, industry and company lists, the news message on Space). The solid
shapes fill a smaller box in the bottom-right corner (`INK` in
`fetch_icons.py`).

Composed in `fetch_icons.py`:

- 3 to 6 (see-through roads, trees, buildings, bridges): the shape as a 2 px
  outline. 2 and 7 (tracks, scenery): every second pixel of the shape, because
  the rails and the fence are too thin for an outline.
- 8 and 9 (height marks): a ruler on the left and the shape at 28 px on the
  right, as in the OpenRCT2 set.
- 0 (direction arrows): the track at 28×26 px with an arrow above it.
- N (Build new vehicles): the train of V (vehicles list) with a plus, as the
  OpenRCT2 set draws Build new ride.
- T (Build tracks): the railway track turned upright, as in the OpenTTD set.
- S: a train under a roof, drawn by the OpenTTD set's `station()`.

ESC shows "Open" over "Loco" in Archivo Black (SIL OFL 1.1,
`ofl/archivoblack/ArchivoBlack-Regular.ttf` from google/fonts at commit
e7db6ca), both lines at the largest one size at which each fits 70 px wide and
both, 2 px apart, fit 38 px high, drawn over the whole cell without the ESC
legend (`program_icon_legend: false`, protocol v25).

OpenLoco's own logo, `src/Resources/src/logo/icon_x256.png`, could be used by
licence: the repository's `LICENSE` is MIT and the logo has no other licence.
It was tried and is not used. The logo is a shaded front view of a steam
locomotive in a diamond; dithered or cut at a threshold into 40×40 px at 1 bit
it reads as a clock face, not as a locomotive.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `land.png` | Font Awesome Free 6.5.2 `mountain` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `water.png` | Font Awesome Free 6.5.2 `water` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `trees.png` | Font Awesome Free 6.5.2 `seedling` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `bulldoze.png` | Material Design Icons `bulldozer` | Pictogrammers | Apache-2.0 |
| `buildroads.png` | Font Awesome Free 6.5.2 `road` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `airports.png` | Font Awesome Free 6.5.2 `plane-departure` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `ports.png` | Font Awesome Free 6.5.2 `anchor` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotateobject.png` | Material Design Icons `rotate-3d-variant` | Pictogrammers | Apache-2.0 |
| `vehicles.png` | Font Awesome Free 6.5.2 `train` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `towns.png` | Font Awesome Free 6.5.2 `city` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `industries.png` | Font Awesome Free 6.5.2 `industry` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `companies.png` | Font Awesome Free 6.5.2 `building` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `company.png` | Font Awesome Free 6.5.2 `id-card` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `map.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `finances.png` | Font Awesome Free 6.5.2 `sack-dollar` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `announcements.png` | Font Awesome Free 6.5.2 `envelope` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lastannouncement.png` | Font Awesome Free 6.5.2 `newspaper` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | Font Awesome Free 6.5.2 `comment` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `debug.png` | Font Awesome Free 6.5.2 `bug` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `underground.png` | Material Design Icons `tunnel` | Pictogrammers | Apache-2.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotateview.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closetop.png` | Font Awesome Free 6.5.2 `rectangle-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `closeall.png` | Material Design Icons `close-box-multiple` | Pictogrammers | Apache-2.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `buildtracks.png` | game-icons.net `delapouite/railway`, turned by `fetch_icons.py` | delapouite | CC BY 3.0 |
| `stations.png` | Font Awesome Free 6.5.2 `train-subway` (solid), with a roof drawn by the OpenTTD set's `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `newvehicles.png` | Font Awesome Free 6.5.2 `train` (solid), with a plus drawn by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `seetracks.png`, `heighttrack.png`, `dirarrows.png` | game-icons.net `delapouite/rail-road`, composed by `fetch_icons.py` | delapouite | CC BY 3.0 |
| `dirarrows.png` (arrow) | Font Awesome Free 6.5.2 `right-long` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `seeroads.png` | Font Awesome Free 6.5.2 `road` (solid), as an outline | Fonticons, Inc. | CC BY 4.0 |
| `seetrees.png` | Font Awesome Free 6.5.2 `tree` (solid), as an outline | Fonticons, Inc. | CC BY 4.0 |
| `seebuildings.png` | Font Awesome Free 6.5.2 `house` (solid), as an outline | Fonticons, Inc. | CC BY 4.0 |
| `seebridges.png` | Font Awesome Free 6.5.2 `bridge` (solid), as an outline | Fonticons, Inc. | CC BY 4.0 |
| `seescenery.png` | Material Design Icons `fence`, every second pixel | Pictogrammers | Apache-2.0 |
| `heightland.png` | Font Awesome Free 6.5.2 `mountain` (solid), with a ruler drawn by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | "Open" over "Loco" set in Archivo Black by the Simutrans set's `text_mark()` | Hector Gatti, Omnibus-Type (The Archivo Black Project Authors) | SIL OFL 1.1 |

Material Design Icons are from Templarian/MaterialDesign at commit 2424e74.
