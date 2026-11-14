# The Battle for Wesnoth overlay: sources

`scripts/generate_app_overlays.py` renders `wesnoth.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `wesnoth_template` (2 files) | The Battle for Wesnoth on Windows and Linux: `wesnoth`, `wesnoth.exe`, `org.wesnoth.Wesnoth` as a Flatpak |
| `wesnoth_template_mac` (3 files) | the same names on macOS, and the app name "The Battle for Wesnoth" |

`wesnoth` is the executable target in `src/CMakeLists.txt`
(`add_executable(wesnoth ...)`) and the command in the `Exec=` line of
`packaging/org.wesnoth.Wesnoth.desktop`; the Flatpak id is the `<id>` in
`packaging/org.wesnoth.Wesnoth.appdata.xml`. The macOS app name was not found in
the source and is the name of the application as the project distributes it.
Names not checked on an install.

## Shortcut reference

The default hotkey table `data/core/hotkeys.cfg` of
<https://github.com/wesnoth/wesnoth>, release tag `1.18.8` (commit
`9f54f6a4f65b0d942a70436372e7cf28c4ba14d0`), read 2026-11-14. The scope and the
category of each command (game, editor, title screen, debug) are from
`src/hotkey/hotkey_command.cpp` at the same tag. A user changes the keys in
Preferences, Hotkeys; this overlay shows the defaults.

Most commands use the macro `IF_APPLE_CMD_ELSE_CTRL`: Ctrl on Windows and
Linux, Cmd on macOS. They are written `CMDCTRL` in `wesnoth.yaml`, so the
generator writes a second set for macOS. "Cmd/Ctrl" in the table means that
macro.

| Key | Command (game screen) |
|---|---|
| N | Next unit (`cycle`) |
| Shift+N | Previous unit (`cycleback`) |
| Space | End unit turn |
| Shift+Space | Hold position |
| T | Continue interrupted move |
| L | Scroll to leader |
| D | Unit description |
| Cmd/Ctrl+N | Rename unit |
| Cmd/Ctrl+R | Recruit |
| Alt+R | Recall |
| Cmd/Ctrl+Alt+R | Repeat recruit |
| Cmd/Ctrl+V | Show enemy moves |
| Cmd/Ctrl+B | Best possible enemy moves |
| Alt+U | Unit list |
| Ctrl+Space (macOS: Alt+Space) | End turn |
| U | Undo |
| R | Redo |
| Cmd/Ctrl+S | Save game |
| Cmd/Ctrl+O | Load game |
| Cmd/Ctrl+W | Quit to title screen (`quit`) |
| Ctrl+Q (no key on macOS) | Quit to desktop |
| Ctrl+P (macOS: Cmd+comma) | Preferences |
| F1 | Help |
| Cmd/Ctrl+J | Objectives |
| S | Statistics |
| Alt+S | Status table |
| Cmd/Ctrl+Shift+A | Achievements |
| Ctrl+Shift+S | Surrender game |
| Cmd/Ctrl+A | Toggle accelerated speed |
| Cmd/Ctrl+F | Toggle full screen |
| Cmd/Ctrl+Alt+M | Mute |
| Alt+Shift+S | Map screenshot |
| : (Shift+semicolon) | Enter user command |
| / | Search |
| = | Zoom in |
| - | Zoom out |
| 0 | Default zoom |
| Cmd/Ctrl+G | Toggle grid |
| Cmd/Ctrl+E | Toggle ellipses |
| Cmd/Ctrl+T | Terrain description |
| Alt+L | Set label |
| Cmd/Ctrl+L | Set team label |
| Cmd/Ctrl+C | Clear labels |
| Shift+S | Update shroud now |
| M | Speak |
| Alt+M | Speak to all |
| Cmd/Ctrl+M | Speak to ally |
| Alt+C | Chat log |
| Cmd/Ctrl+X | Clear messages |
| P | Planning mode |
| Y | Execute planned action |
| Ctrl+Y (Ctrl on macOS too) | Execute all planned actions |
| H | Delete planned action |
| Page Up | Move planned action up |
| Page Down | Move planned action down |
| I | Suppose dead |

The table's key for the user command is the character `:`. On a US layout that
is Shift+semicolon, and the overlay draws it there. On a layout with `:` on
another key the icon is on the wrong key.

The table's zoom-in keys are `=` and `+`; `+` is Shift+`=` on a US layout and
is not drawn a second time.

Several of these keys have another meaning in the map editor and on the title
screen (not drawn):

| Key | Editor | Title screen |
|---|---|---|
| N | Next tool | |
| S | Select tool | |
| P | Paint tool | |
| T | Update transitions | |
| I | Draw terrain codes | |
| Space | | Credits |
| L | | Language |
| M | | Multiplayer |
| Cmd/Ctrl+S | Save map | |
| Cmd/Ctrl+O | Load map | |
| Cmd/Ctrl+M | New map | |
| Cmd/Ctrl+A | Select all | |
| Cmd/Ctrl+C, X, V | Copy, cut, paste | |
| Cmd/Ctrl+R | Rotate clipboard clockwise | |
| Alt+R | Resize map | |
| Alt+S | Save all maps | |
| Alt+C | Create mask | |
| Cmd/Ctrl+Shift+S | Save map as | |

## Left out

- F (Run formula), Shift+C (Create unit), Shift+U (Change side), Shift+K (Kill
  unit) and the backquote (Lua console): category `HKCAT_DEBUG` in
  `hotkey_command.cpp`; they work only in debug mode.
- The arrow keys (scroll the map): they keep their own legends.
- F10 (Show helptip): it shows the help text of the widget under the mouse, so
  its result depends on the screen.
- F5 (Reload WML) and the arrow keys for the tips: title screen only.
- The map editor keys (1 to 5, A, B, F, O, X, Cmd/Ctrl+Z, Cmd/Ctrl+D,
  Cmd/Ctrl+I and the Alt and Shift editor chords) and the title screen keys
  (A, C, E, K).
- Mouse bindings (select, deselect, touch).

## Placement

As for Freeciv (`../freeciv/SOURCES.md`): every icon sits at the right edge and
uses the full height, and the firmware clears 3 px around it, so a letter legend
stays whole. F1 is 34x40, the width the AoE2 set measured to keep that legend
whole. Font Awesome and Material Design icons fill a 34x34 box and
game-icons.net drawings a 38x38 box; `INK` in `fetch_icons.py` lists the icons
with their own box.

The default zoom icon is the magnifier with "1:1" above it, as in the Freeciv
set.

Layers: the Windows and Linux set uses the plain, Ctrl, Alt and Shift layers
and Ctrl+Shift, Ctrl+Alt and Alt+Shift. The macOS set uses the plain, Ctrl
(Ctrl+Y only), Alt, Shift, Alt+Shift, Cmd, Cmd+Shift, Cmd+Alt and Ctrl+Shift
layers.

## ESC mark

ESC shows "Wesnoth" in Almendra Bold (SIL OFL 1.1,
`ofl/almendra/Almendra-Bold.ttf` from google/fonts at commit e7db6ca), at the
largest size at which it fits 70 px wide, drawn over the whole cell without
the ESC legend (`program_icon_legend: false`, protocol v25).

The game's logo is not used. The source code is GPL-2.0-or-later (the file
`copyright` in the repository), which would be compatible with this
repository's GPL-3.0-or-later. But the README says that new art contributions
are CC BY-SA 4.0, and the logo files have no licence note of their own, so
their licence is not clear. The logo is also a painted shield with a script
wordmark, which does not read at 1 bit in 72x40.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/
- Bitstream Vera licence: https://dejavu-fonts.github.io/License.html

| File | Source | Author | Licence |
|---|---|---|---|
| `nextunit.png` | Font Awesome Free 6.5.2 `forward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `prevunit.png` | Font Awesome Free 6.5.2 `backward-step` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `endunitturn.png` | Font Awesome Free 6.5.2 `check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `holdposition.png` | Font Awesome Free 6.5.2 `hand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `continuemove.png` | Font Awesome Free 6.5.2 `person-walking-arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `leader.png` | Font Awesome Free 6.5.2 `crown` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `describeunit.png` | Font Awesome Free 6.5.2 `id-card` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `renameunit.png` | Font Awesome Free 6.5.2 `user-pen` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `recruit.png` | Font Awesome Free 6.5.2 `user-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `recall.png` | Font Awesome Free 6.5.2 `user-clock` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `repeatrecruit.png` | Font Awesome Free 6.5.2 `repeat` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `enemymoves.png` | Font Awesome Free 6.5.2 `shoe-prints` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `bestenemymoves.png` | Font Awesome Free 6.5.2 `chess-knight` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `unitlist.png` | Font Awesome Free 6.5.2 `people-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `endturn.png` | Font Awesome Free 6.5.2 `hourglass-end` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `undo.png` | Font Awesome Free 6.5.2 `rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `redo.png` | Font Awesome Free 6.5.2 `rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome Free 6.5.2 `right-from-bracket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quitdesktop.png` | Font Awesome Free 6.5.2 `power-off` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `preferences.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `help.png` | Font Awesome Free 6.5.2 `circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `objectives.png` | Font Awesome Free 6.5.2 `list-check` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `statistics.png` | Font Awesome Free 6.5.2 `chart-column` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `statustable.png` | Font Awesome Free 6.5.2 `table-list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `achievements.png` | Font Awesome Free 6.5.2 `trophy` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `surrender.png` | Font Awesome Free 6.5.2 `flag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `accelerated.png` | Font Awesome Free 6.5.2 `forward-fast` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mute.png` | Font Awesome Free 6.5.2 `volume-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `command.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `search.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `grid.png` | Material Design Icons `hexagon-multiple` | Pictogrammers | Apache-2.0 |
| `ellipses.png` | Font Awesome Free 6.5.2 `ring` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `describeterrain.png` | Font Awesome Free 6.5.2 `mountain-sun` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `label.png` | Font Awesome Free 6.5.2 `tag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `teamlabel.png` | Font Awesome Free 6.5.2 `user-tag` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clearlabels.png` | Font Awesome Free 6.5.2 `text-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `updateshroud.png` | Font Awesome Free 6.5.2 `binoculars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | Font Awesome Free 6.5.2 `comment` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chatall.png` | Font Awesome Free 6.5.2 `comments` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chatally.png` | Font Awesome Free 6.5.2 `walkie-talkie` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chatlog.png` | Font Awesome Free 6.5.2 `rectangle-list` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `clearmessages.png` | Font Awesome Free 6.5.2 `comment-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `planning.png` | Font Awesome Free 6.5.2 `pen-ruler` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `planexecute.png` | Font Awesome Free 6.5.2 `play` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `planexecuteall.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `plandelete.png` | Font Awesome Free 6.5.2 `eraser` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `planup.png` | Font Awesome Free 6.5.2 `angles-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `plandown.png` | Font Awesome Free 6.5.2 `angles-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `supposedead.png` | Font Awesome Free 6.5.2 `skull` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomdefault.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid), with "1:1" in DejaVu Sans Bold, composed by `fetch_icons.py` | Fonticons, Inc. (icon), DejaVu fonts authors (text) | CC BY 4.0; Bitstream Vera licence |
| `program.png` | "Wesnoth" set in Almendra Bold by `fetch_icons.py` | Ana Sanfelippo (font) | SIL OFL 1.1 |
