# FlightGear overlay: sources

`scripts/generate_app_overlays.py` renders `flightgear.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `flightgear_template` (1 file) | FlightGear: `fgfs` on Linux, `fgfs.exe` on Windows, `FlightGear` on macOS, `org.flightgear.FlightGear` as a Flatpak |

`fgfs` is the executable target in `src/Main/CMakeLists.txt`
(`add_executable(fgfs WIN32 MACOSX_BUNDLE ...)`) and the `Exec=` line of
`package/org.flightgear.FlightGear.desktop.in`. On macOS
`CMakeModules/SetupFGFSBundle.cmake` sets `OUTPUT_NAME "FlightGear"`. The
Flatpak id is the `id` of the Flathub manifest
(`flathub/org.flightgear.FlightGear`). The source is
<https://gitlab.com/flightgear/flightgear>, tag `2024.1.7`. Names not checked
on an install.

## Shortcut reference

`keyboard.xml` of <https://gitlab.com/flightgear/fgdata>, release tag
`2024.1.7` (commit `74b24bfc89c4b5c98f7414d71a4f5fcac7764b9e`), read
2026-11-14. `defaults.xml` includes this file as the keyboard configuration.
FlightGear and fgdata are developed on GitLab; `FlightGear/fgdata` is not
readable on GitHub.

**The overlay shows the global defaults only.** An aircraft's own
configuration adds keys and replaces global ones (for example the keys of
`Input/Keyboard/carrier-bindings.xml`, which carrier aircraft include). The
host cannot know which aircraft is loaded, so a key can do something else in a
given aircraft.

FlightGear binds characters, not keys: `g` (gear up) and `G` (gear down) are
two bindings, and so are `[` and `{`. The overlay puts a capital letter and a
shifted symbol on the Shift layer, as a US layout types them. On another
layout the symbols are on other keys.

The digits are bound as characters too, so the digit row acts like the keypad
with Num Lock on. The "look" directions that `keyboard.xml` gives for Shift
with a digit apply to the keypad only: Shift with a digit of the digit row
types `!`, `@`, `#` or `$`, which select an engine.

### Plain layer

| Key | Action |
|---|---|
| Left, Right, 4, 6 | Aileron left, right (or adjust the autopilot heading) |
| Up, 8 | Elevator down (or decrease the autopilot altitude) |
| Down, 2 | Elevator up (or increase the autopilot altitude) |
| Page Up, 9 | Increase throttle (or the autopilot auto-throttle) |
| Page Down, 3 | Decrease throttle |
| Home, 7 | Elevator trim up |
| End, 1 | Elevator trim down |
| Insert, 0 | Rudder left |
| Enter | Rudder right |
| 5 | Centre aileron, elevator and rudder |
| B | Apply all brakes |
| , and . | Left brake, right brake |
| G | Gear up |
| [ and ] | Decrease, increase flaps |
| J, K | Decrease, increase spoilers |
| L | Toggle tail-wheel lock |
| S | Starter on the selected engines |
| M | Mixture richer |
| N | Propeller finer |
| P | Pause the simulator |
| A | Increase the simulation speed |
| T | Warp time forwards |
| V | Next view |
| X | Zoom in (decrease the field of view) |
| Z | Increase visibility |
| C | Toggle the 3D or 2D cockpit |
| H | HUD master switch |
| I | Normal HUD |
| Tab | Cycle the mouse mode |
| Space | Push to talk (FGCom) |
| ' | ATC dialog |
| - | Chat menu |
| / | Property browser |
| F3 | Capture the screen |
| F6 | Toggle the autopilot heading mode |
| F10 | Toggle the menubar |
| F11 | Autopilot dialog |
| F12 | Radio settings dialog |

### Shift layer

| Key (character) | Action |
|---|---|
| Shift+1 to 4 (`!` `@` `#` `$`) | Select the first to fourth engine |
| Shift+` (`~`) | Select all engines |
| Shift+[ and ] (`{` `}`) | Decrease, increase magneto on the selected engines |
| Shift+M | Mixture leaner |
| Shift+N | Propeller coarser |
| Shift+B | Toggle the parking brake |
| Shift+G | Gear down |
| Shift+A | Decrease the simulation speed |
| Shift+T | Warp time backwards |
| Shift+V | Previous view |
| Shift+X | Zoom out (increase the field of view) |
| Shift+Z | Decrease visibility |
| Shift+H | Cycle the HUD brightness |
| Shift+I | Alternative HUD types |
| Shift+P | Toggle the 2D panel |
| Shift+S | Swap panels |
| Shift+/ (`?`) | Help dialog |
| Shift+; (`:`) | Start a multikey command |
| Shift+= (`+`) | ATC or instructor repeats the last message |
| Shift+- (`_`) | Compose chat |
| Shift+Left, Right, Up, Down | Look left, right, forward, back |
| Shift+Home, Page Up, End, Page Down | Look front left, front right, back left, back right |
| Shift+F1, F2 | Load, save a flight recorder tape |
| Shift+F3 | Load a panel |
| Shift+F5, F6, F7, F8 | Scroll the 2D panel down, up, left, right |
| Shift+F10 | Toggle full screen |

### Ctrl and Alt layers

| Key | Action |
|---|---|
| Ctrl+A | Autopilot altitude lock |
| Ctrl+G | Autopilot glide slope lock |
| Ctrl+H | Autopilot heading lock |
| Ctrl+N | Autopilot NAV1 lock |
| Ctrl+P | Pitch hold |
| Ctrl+S | Auto-throttle lock |
| Ctrl+T | Autopilot terrain lock |
| Ctrl+W | Autopilot wing leveler |
| Ctrl+B | Toggle the speedbrake |
| Ctrl+U | Add 1000 ft of emergency altitude (marked "Cheat" in the file) |
| Ctrl+R | Instant replay |
| Ctrl+M | Map dialog (`<mod-ctrl>` of key 13; Ctrl+Enter sends the same) |
| Ctrl+C | Toggle the clickable panel hotspots |
| Ctrl+V | Initial view (view 0) |
| Ctrl+X | Reset the zoom |
| Ctrl+Z | Reset the visibility |
| Ctrl+1, Ctrl+7 | Elevator trim down fast, up fast |
| Ctrl+4, Ctrl+6 | Aileron trim left, right |
| Ctrl+5 | Clear all trims |
| Ctrl+F3 | Capture a cube map (`screenshot.make_cubemap()`; the file has no description) |
| Alt+F3 | Capture a panorama (`screenshot.make_panorama()`; no description) |
| Alt+C | Toggle tooltips for animated objects |
| Alt+2 | Toggle auto-coordination |

## Left out

- Escape (quit dialog) and Shift+Escape (reset FlightGear): the key shows the
  program mark on every layer.
- Keypad 5 and the keypad digits with Shift (look directions): the keypad has no
  cell.
- Shift+Space: the same push to talk as Space.
- Ctrl+Enter (map dialog): drawn on Ctrl+M, which sends the same character.
- The second key of a multikey command (`Input/Keyboard/multikey.xml`, started
  with `:`): the keyboard has no layer for a key sequence.
- `Input/Keyboard/carrier-bindings.xml` (catapult, launch bar, hook, wing fold on
  C, L, O, F): only aircraft that include the file have these keys.
- Every key an aircraft defines.

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge and
uses the full height (40×40), and the firmware clears 3 px around it, so a
letter legend stays whole. On the digit keys the icon erases the shifted
symbol. F1 to F8 use 34×40; F10, F11 and F12 use 40×40 and cover the right end of
their legends.

All icons are flat 1-bit silhouettes. Solid shapes fill a smaller box in the
bottom-right corner (`INK` in `fetch_icons.py`).

Cockpit terms that have no clear pictogram are set as text in Press Start 2P at
8 px, where every pixel of the font is exact (`TEXT`, `SIGNED` and `STACKED` in
`fetch_icons.py`): the autopilot locks (`AP` over `ALT`, `HDG`, `NAV1`, ...),
a term above a plus or minus sign drawn by the script (`FLAP`, `SPOIL`, `MIX`,
`PROP`, `MAG`, `VIS`), and a term under a pictogram (`TAIL` under a lock,
`START` under a flash, `LOAD` and `SAVE` under a cassette). `PANL` is short for
panel: five letters do not fit the 34 px of F3.

Composed by `fetch_icons.py`: the brake symbol with `L` or `R`, the tyre with an
arrow (gear up, down), the engine with its number, the eye with `0` (initial
view) or with an arrow (the eight look directions).

Two keys that do the same thing (Left and 4, Page Up and 9, ...) show the same
icon.

## ESC mark

ESC shows FlightGear's own application icon,
`package/FlightGear_app_icon.svg` of <https://gitlab.com/flightgear/flightgear>
at commit `7241807173248abd838e2ab11337fbc5b2ae20b0` (tag `2024.1.7`). The icon
is a rounded tile, 128 units wide in its own drawing, with a band of 16 unit
yellow and black squares and a blue F on white. `program()` renders it, lights
the yellow squares and the F, and reduces the tile to 40×40, where a square is
exactly 5 px. It is placed at the right edge and the ESC legend stays.

Licence: the file has no licence statement of its own (its metadata names
`flightgear.org` as creator and rights holder), so the project's licence
applies. FlightGear's source files say "either version 2 of the License, or (at
your option) any later version" (for example the header of
`src/Main/bootstrap.cxx`), which is compatible with this repository's
GPL-3.0-or-later.

## Icons

Licence texts for the icon and font licences named in this file:

- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/
- GPL-2.0-or-later: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html

Material Design Icons (author: Pictogrammers, Apache-2.0) are from
Templarian/MaterialDesign at commit 2424e74. Font Awesome Free 6.5.2 solid
icons are by Fonticons, Inc. (CC BY 4.0). Text is Press Start 2P by CodeMan38
(SIL OFL 1.1, `ofl/pressstart2p/PressStart2P-Regular.ttf` from google/fonts at
commit e7db6ca). The letters L and R and the digits of the composed icons are
DejaVu Sans Bold (Bitstream Vera licence; the copy bundled with matplotlib
v3.9.2, pinned commit).

| File | Source | Author | Licence |
|---|---|---|---|
| `aileronleft.png`, `aileronright.png` | Material Design Icons `rotate-left`, `rotate-right` | Pictogrammers | Apache-2.0 |
| `elevatorup.png`, `elevatordown.png` | Material Design Icons `airplane-takeoff`, `airplane-landing` | Pictogrammers | Apache-2.0 |
| `rudderleft.png`, `rudderright.png` | Material Design Icons `arrow-left-top-bold`, `arrow-right-top-bold` | Pictogrammers | Apache-2.0 |
| `center.png` | Font Awesome Free 6.5.2 `arrows-to-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `throttleup.png`, `throttledown.png` | Material Design Icons `speedometer`, `speedometer-slow` | Pictogrammers | Apache-2.0 |
| `trimup.png`, `trimdown.png` | Material Design Icons `arrow-up-drop-circle-outline`, `arrow-down-drop-circle-outline` | Pictogrammers | Apache-2.0 |
| `trimupfast.png`, `trimdownfast.png` | Material Design Icons `chevron-triple-up`, `chevron-triple-down` | Pictogrammers | Apache-2.0 |
| `ailerontrimleft.png`, `ailerontrimright.png` | Material Design Icons `arrow-left-drop-circle-outline`, `arrow-right-drop-circle-outline` | Pictogrammers | Apache-2.0 |
| `autocoordination.png` | Material Design Icons `link-variant` | Pictogrammers | Apache-2.0 |
| `allbrakes.png`, `parkingbrake.png` | Material Design Icons `car-brake-alert`, `car-brake-parking` | Pictogrammers | Apache-2.0 |
| `leftbrake.png`, `rightbrake.png` | Material Design Icons `car-brake-alert`, with L or R | Pictogrammers; the letters Bitstream | Apache-2.0; the letters Bitstream Vera |
| `gearup.png`, `geardown.png` | Material Design Icons `tire` with `arrow-up-bold`, `arrow-down-bold` | Pictogrammers | Apache-2.0 |
| `engine1.png` to `engine4.png` | Material Design Icons `engine`, with the number | Pictogrammers; the digits Bitstream | Apache-2.0; the digits Bitstream Vera |
| `allengines.png` | Material Design Icons `engine`, text `ALL` | Pictogrammers; CodeMan38 (font) | Apache-2.0; SIL OFL 1.1 |
| `starter.png` | Material Design Icons `flash`, text `START` | Pictogrammers; CodeMan38 (font) | Apache-2.0; SIL OFL 1.1 |
| `tailwheellock.png` | Material Design Icons `lock`, text `TAIL` | Pictogrammers; CodeMan38 (font) | Apache-2.0; SIL OFL 1.1 |
| `cleartrims.png`, `visibilityreset.png` | Material Design Icons `restore`, text `TRIM`, `VIS` | Pictogrammers; CodeMan38 (font) | Apache-2.0; SIL OFL 1.1 |
| `hudbrightness.png` | Material Design Icons `brightness-6`, text `HUD` | Pictogrammers; CodeMan38 (font) | Apache-2.0; SIL OFL 1.1 |
| `atcrepeat.png` | Material Design Icons `repeat`, text `ATC` | Pictogrammers; CodeMan38 (font) | Apache-2.0; SIL OFL 1.1 |
| `loadtape.png`, `savetape.png` | Material Design Icons `cassette`, text `LOAD`, `SAVE` | Pictogrammers; CodeMan38 (font) | Apache-2.0; SIL OFL 1.1 |
| `loadpanel.png` | Material Design Icons `folder-open`, text `PANL` | Pictogrammers; CodeMan38 (font) | Apache-2.0; SIL OFL 1.1 |
| `flapsup.png`, `flapsdown.png`, `spoilersless.png`, `spoilersmore.png`, `mixtureleaner.png`, `mixturericher.png`, `propcoarser.png`, `propfiner.png`, `magnetoless.png`, `magnetomore.png`, `visibilityless.png`, `visibilitymore.png` | text in Press Start 2P above a sign drawn by `fetch_icons.py` | CodeMan38 (font) | SIL OFL 1.1 |
| `apaltitude.png`, `apglideslope.png`, `apheading.png`, `apnav1.png`, `appitch.png`, `apterrain.png`, `apwing.png`, `autothrottle.png`, `speedbrake.png`, `cheataltitude.png`, `headingmode.png`, `hud.png`, `hudnormal.png`, `hudalternative.png` | text in Press Start 2P | CodeMan38 (font) | SIL OFL 1.1 |
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `speedup.png`, `slowdown.png` | Material Design Icons `fast-forward`, `rewind` | Pictogrammers | Apache-2.0 |
| `warpforward.png`, `warpback.png` | Material Design Icons `clock-fast`, `history` | Pictogrammers | Apache-2.0 |
| `replay.png` | Material Design Icons `replay` | Pictogrammers | Apache-2.0 |
| `map.png` | Material Design Icons `map` | Pictogrammers | Apache-2.0 |
| `mousemode.png` | Material Design Icons `mouse` | Pictogrammers | Apache-2.0 |
| `hotspots.png` | Material Design Icons `cursor-default-click` | Pictogrammers | Apache-2.0 |
| `tooltips.png` | Material Design Icons `tooltip-text` | Pictogrammers | Apache-2.0 |
| `propertybrowser.png` | Material Design Icons `file-tree` | Pictogrammers | Apache-2.0 |
| `help.png` | Material Design Icons `help-circle` | Pictogrammers | Apache-2.0 |
| `multikey.png` | Material Design Icons `keyboard` | Pictogrammers | Apache-2.0 |
| `ptt.png` | Material Design Icons `microphone` | Pictogrammers | Apache-2.0 |
| `atc.png` | Material Design Icons `radio-tower` | Pictogrammers | Apache-2.0 |
| `chatmenu.png`, `composechat.png` | Material Design Icons `forum`, `message-text` | Pictogrammers | Apache-2.0 |
| `nextview.png`, `prevview.png` | Material Design Icons `eye-arrow-right`, `eye-arrow-left` | Pictogrammers | Apache-2.0 |
| `initialview.png` | Material Design Icons `eye`, with 0 | Pictogrammers; the digit Bitstream | Apache-2.0; the digit Bitstream Vera |
| `lookleft.png`, `lookright.png`, `lookforward.png`, `lookback.png`, `lookfrontleft.png`, `lookfrontright.png`, `lookbackleft.png`, `lookbackright.png` | Material Design Icons `eye` with `arrow-left-thick`, `arrow-right-thick`, `arrow-up-thick`, `arrow-down-thick`, `arrow-top-left-thick`, `arrow-top-right-thick`, `arrow-bottom-left-thick`, `arrow-bottom-right-thick` | Pictogrammers | Apache-2.0 |
| `zoomin.png`, `zoomout.png`, `zoomreset.png` | Material Design Icons `magnify-plus`, `magnify-minus`, `magnify-scan` | Pictogrammers | Apache-2.0 |
| `cockpit.png` | Material Design Icons `video-3d` | Pictogrammers | Apache-2.0 |
| `panel.png`, `swappanels.png` | Material Design Icons `view-dashboard`, `swap-horizontal-bold` | Pictogrammers | Apache-2.0 |
| `panelup.png`, `paneldown.png`, `panelleft.png`, `panelright.png` | Material Design Icons `pan-up`, `pan-down`, `pan-left`, `pan-right` | Pictogrammers | Apache-2.0 |
| `screenshot.png`, `cubemap.png`, `panorama.png` | Material Design Icons `camera`, `cube-outline`, `panorama-variant` | Pictogrammers | Apache-2.0 |
| `menubar.png`, `fullscreen.png` | Material Design Icons `menu`, `fullscreen` | Pictogrammers | Apache-2.0 |
| `autopilotdialog.png` | Material Design Icons `airplane-cog` | Pictogrammers | Apache-2.0 |
| `radiodialog.png` | Material Design Icons `radio-handheld` | Pictogrammers | Apache-2.0 |
| `program.png` | FlightGear `package/FlightGear_app_icon.svg`, reduced to 40×40 at 1 bit by `fetch_icons.py` | The FlightGear project | GPL-2.0-or-later |
