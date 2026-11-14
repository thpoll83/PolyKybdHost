# Julius and Augustus (Caesar III engines) overlays: sources

`scripts/generate_app_overlays.py` renders `julius.yaml` and `augustus.yaml`;
`fetch_icons.py` rebuilds `icons/` for both.

| Set | Loads for |
|---|---|
| `julius_template` (1 file) | Julius, the open source engine for Caesar III: `julius` on Linux and macOS, `julius.exe` on Windows, `com.github.bvschaik.julius` as a Flatpak |
| `augustus_template` (1 file) | Augustus, the fork of Julius with gameplay changes: `augustus` on Linux and macOS, `augustus.exe` on Windows, `com.github.keriew.augustus` as a Flatpak |

The names are from the build files of Julius v1.8.0 and Augustus v4.0.0:
`set(SHORT_NAME julius)` / `set(SHORT_NAME augustus)` with
`add_executable(${SHORT_NAME} ...)` in `CMakeLists.txt`, the `Exec=` line of
`res/julius.desktop` / `res/augustus.desktop`, and the `<id>` of
`res/julius.metainfo.xml` / `res/augustus.metainfo.xml`. The macOS bundles are
named `Julius` and `Augustus` (`USER_FRIENDLY_NAME`). Names not checked on an
install. The original Caesar III executable (`c3.exe`) has other keys and gets
no set.

## Shortcut reference

The default hotkeys set in `init_defaults()` of `src/core/hotkey_config.c`:

- Julius: <https://github.com/bvschaik/julius>, tag `v1.8.0` (commit
  127b5ddb4a80d6fc6b11b19fe8d8c22db2459c78), read 2026-11-14.
- Augustus: <https://github.com/Keriew/augustus>, tag `v4.0.0` (commit
  3edf0f889c977a63117c555d4ef3d0891d797664), read 2026-11-14.

The two tables differ: Augustus has every default of Julius and adds R, Q, X,
Shift+F12 and three mouse bindings. So the folder has two specs, and the keys
both engines share have the same icon. A user's hotkey configuration changes
the keys; the overlays show the defaults.

The letter keys and `[` `]` `-` `=` are set with `set_layout_mapping()`, which
looks the key up by the character it types on the current layout. The overlay
draws them on the US positions.

| Key | Action (`hotkey_config.c`) | Julius | Augustus |
|---|---|---|---|
| P | `HOTKEY_TOGGLE_PAUSE` | yes | yes |
| [ and Page Down | `HOTKEY_DECREASE_GAME_SPEED` | yes | yes |
| ] and Page Up | `HOTKEY_INCREASE_GAME_SPEED` | yes | yes |
| Space | `HOTKEY_TOGGLE_OVERLAY`: show or hide the current overlay | yes | yes |
| L | `HOTKEY_CYCLE_LEGION` | yes | yes |
| Home, End | `HOTKEY_ROTATE_MAP_LEFT`, `HOTKEY_ROTATE_MAP_RIGHT` | yes | yes |
| 1 to 0 | advisors: labor, military, imperial, ratings, trade, population, health, education, entertainment, religion | yes | yes |
| - | `HOTKEY_SHOW_ADVISOR_FINANCIAL` | yes | yes |
| = | `HOTKEY_SHOW_ADVISOR_CHIEF` | yes | yes |
| W, F, D, C, T | overlays: water, fire, damage, crime, problems | yes | yes |
| Ctrl+O, Ctrl+S | `HOTKEY_LOAD_FILE`, `HOTKEY_SAVE_FILE` | yes | yes |
| F1 to F4 | `HOTKEY_GO_TO_BOOKMARK_1` to `_4` | yes | yes |
| Ctrl+F1 to F4, Alt+F1 to F4 | `HOTKEY_SET_BOOKMARK_1` to `_4` | yes | yes |
| F5 | `HOTKEY_CENTER_WINDOW` | yes | yes |
| F6, Alt+Enter | `HOTKEY_TOGGLE_FULLSCREEN` | yes | yes |
| F7, F8, F9 | `HOTKEY_RESIZE_TO_640`, `_800`, `_1024` | yes | yes |
| F12, Alt+F12 | `HOTKEY_SAVE_SCREENSHOT` | yes | yes |
| Ctrl+F12 | `HOTKEY_SAVE_CITY_SCREENSHOT` | yes | yes |
| R | `HOTKEY_ROTATE_BUILDING` | | yes |
| Q | `HOTKEY_BUILD_CLONE`: build a copy of the building under the cursor | | yes |
| X | `HOTKEY_MOTHBALL_TOGGLE` | | yes |
| Shift+F12 | `HOTKEY_SAVE_MINIMAP_SCREENSHOT` | | yes |

The source comments mark Alt+F1 to Alt+F4 and Alt+F12 as "mac specific"
(Ctrl+F1 does not reach the game on macOS), but the table sets them on every
OS, so they are drawn on every OS.

No key changes its meaning with the selection.

## Left out

- The arrow keys (scroll the map): the arrows keep their own legends.
- The keypad digits (the advisors again): the keypad has no cell.
- Ctrl+A (`HOTKEY_EDITOR_TOGGLE_BATTLE_INFO`): a map editor key.
- Augustus: mouse wheel up and down (zoom in and out) and the middle mouse
  button (reset zoom) are not keys.
- The hotkey actions without a default key (the build menu actions in
  Augustus, for example).

## Placement

As for OpenTTD and 0 A.D.: every icon sits at the right edge and uses the full
height, and the firmware clears 3 px around it, so a letter legend stays
whole. F1 to F9 are 34×40, the width of the 0 A.D. set's F-key icons. F12 is
40×40 and covers the right part of its legend, as OpenTTD's F12 does.

All icons are flat 1-bit silhouettes. The same action has the same icon source
as in the OpenTTD and OpenRCT2 sets: pause, the game speed arrows, save, load,
rotate, screenshot (and the panorama for the large one), fullscreen, rotate a
building. The solid shapes fill a smaller box in the bottom-right corner
(`INK` in `fetch_icons.py`).

Composed in `fetch_icons.py`:

- F1 to F4 and their Ctrl and Alt layers: the location pin with the bookmark
  number cut out, and for "set" the pin moved up and left with a plus. Drawn by
  the 0 A.D. set's `jump_pins()`, which does the same for its camera positions.
- F7, F8, F9: a window with the width (640, 800, 1024) above it in DejaVu Sans
  Bold.
- Shift+F12 (Augustus): the camera with a map above it.

ESC shows a laurel wreath (game-icons.net `lorc/laurels`) over the engine's
name in Cinzel Decorative Black (SIL OFL 1.1,
`ofl/cinzeldecorative/CinzelDecorative-Black.ttf` from google/fonts at commit
e7db6ca), the name at the largest size that fits 70 px wide, drawn over the
whole cell without the ESC legend (`program_icon_legend: false`, protocol v25).

The engines' own icons (`res/julius.png`, `res/augustus.png` and the `.ico`
files) are not used. Both repositories are under the GNU Affero General Public
License 3.0 (`LICENSE.txt`), which is not on this repository's list of licences
compatible with GPL-3.0-or-later. Augustus' own assets in `res/assets/` have a
separate `LICENSE` file and are not used either. The game's art comes from the
original Caesar III data files, which are proprietary.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/
- Bitstream Vera licence (DejaVu Sans Bold, the digits):
  https://dejavu-fonts.github.io/License.html

`rotatebuilding.png`, `clone.png`, `mothball.png` and `minimapscreenshot.png`
are drawn by `augustus.yaml` only.

| File | Source | Author | Licence |
|---|---|---|---|
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `slower.png` | Font Awesome Free 6.5.2 `backward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `faster.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `overlay.png` | Font Awesome Free 6.5.2 `layer-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `legion.png` | game-icons.net `delapouite/centurion-helmet` | delapouite | CC BY 3.0 |
| `rotateleft.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotateright.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `labor.png` | Font Awesome Free 6.5.2 `person-digging` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `military.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `imperial.png` | game-icons.net `lorc/laurel-crown` | lorc | CC BY 3.0 |
| `ratings.png` | Font Awesome Free 6.5.2 `ranking-star` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `trade.png` | Font Awesome Free 6.5.2 `scale-balanced` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `population.png` | Font Awesome Free 6.5.2 `users` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `health.png` | Font Awesome Free 6.5.2 `staff-snake` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `education.png` | Font Awesome Free 6.5.2 `scroll` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `entertainment.png` | Font Awesome Free 6.5.2 `masks-theater` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `religion.png` | game-icons.net `delapouite/greek-temple` | delapouite | CC BY 3.0 |
| `financial.png` | Font Awesome Free 6.5.2 `coins` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chief.png` | game-icons.net `delapouite/caesar` | delapouite | CC BY 3.0 |
| `water.png` | Font Awesome Free 6.5.2 `droplet` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fire.png` | Font Awesome Free 6.5.2 `fire` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `damage.png` | Font Awesome Free 6.5.2 `house-crack` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `crime.png` | Font Awesome Free 6.5.2 `handcuffs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `problems.png` | Font Awesome Free 6.5.2 `triangle-exclamation` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `centerwindow.png` | Font Awesome Free 6.5.2 `arrows-to-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cityscreenshot.png` | Font Awesome Free 6.5.2 `panorama` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rotatebuilding.png` | Material Design Icons `rotate-3d-variant` | Pictogrammers | Apache-2.0 |
| `clone.png` | Font Awesome Free 6.5.2 `clone` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mothball.png` | Font Awesome Free 6.5.2 `store-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen_f6.png` | Font Awesome Free 6.5.2 `expand` (solid), in the 34 px area of F6 | Fonticons, Inc. | CC BY 4.0 |
| `jump1.png` to `jump4.png`, `jumpset1.png` to `jumpset4.png` | Font Awesome Free 6.5.2 `location-dot` (solid), with a digit (DejaVu Sans Bold) and a plus drawn by the 0 A.D. set's `fetch_icons.py` | Fonticons, Inc.; DejaVu fonts team (digits) | CC BY 4.0; Bitstream Vera licence |
| `resize640.png`, `resize800.png`, `resize1024.png` | Font Awesome Free 6.5.2 `window-maximize` (solid), with the width in DejaVu Sans Bold | Fonticons, Inc.; DejaVu fonts team (digits) | CC BY 4.0; Bitstream Vera licence |
| `minimapscreenshot.png` | Font Awesome Free 6.5.2 `camera` and `map` (solid), composed by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `program_julius.png`, `program_augustus.png` (wreath) | game-icons.net `lorc/laurels` | lorc | CC BY 3.0 |
| `program_julius.png`, `program_augustus.png` (name) | "Julius" and "Augustus" set in Cinzel Decorative Black by `fetch_icons.py` | Natanael Gama (font) | SIL OFL 1.1 |

Material Design Icons are from Templarian/MaterialDesign at commit 2424e74.
