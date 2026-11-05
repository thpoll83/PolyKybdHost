# Freeciv and Civilization overlays: sources

`scripts/generate_app_overlays.py` renders the six specs in this folder;
`fetch_icons.py` rebuilds `icons/`. `freeciv.yaml` is the only spec written by
hand. `gen_variants.py` writes the other five from it, and
`tests/res/freeciv_spec_test.py` checks that the committed variants equal its
output.

| Set | Spec | Loads for |
|---|---|---|
| `freeciv_template` (2 files) | `freeciv.yaml` | Freeciv 3.2 GTK clients: `freeciv-gtk3.22`, `freeciv-gtk4` |
| `freeciv_qt_template` (2 files) | `freeciv_qt.yaml` | Freeciv 3.2 Qt client: `freeciv-qt` |
| `freeciv_sdl_template` (2 files) | `freeciv_sdl.yaml` | Freeciv 3.2 SDL clients: `freeciv-sdl2`, `freeciv-sdl3` |
| `freeciv21_template` (2 files) | `freeciv21.yaml` | Freeciv21 3.1: `freeciv21-client` |
| `civ2_template` (1 file) | `civ2.yaml` | Civilization II: `civ2.exe` |
| `civ1_template` (1 file) | `civ1.yaml` | Civilization I (DOS) in DOSBox |

## App names

None of the names was checked on an install. They come from the build files:

- Freeciv: the `executable()` names in `meson.build` (tag `R3_2_6`):
  `freeciv-gtk3.22`, `freeciv-gtk4`, `freeciv-qt`, `freeciv-sdl2`,
  `freeciv-sdl3`. The desktop file ids in the same file are
  `org.freeciv.gtk322`, `org.freeciv.gtk4`, `org.freeciv.qt`,
  `org.freeciv.sdl2` and `org.freeciv.sdl3`; a Wayland session or Flathub
  reports these.
- Freeciv21: the CMake target `freeciv21-client` (`client/CMakeLists.txt`) and
  the desktop file `net.longturn.freeciv21.desktop`
  (`cmake/FreecivInstall.cmake`), commit `63c3509f` (tag `v3.1.3`).
- Civilization II: `civ2.exe`. This name is not taken from a source and is
  **unverified**.
- Civilization I runs in DOSBox; see "Civilization I in DOSBox" below.

How the handler sees these names (`polyhost/handler/active_window.py`):

- Windows cuts the process name at the **first** dot. `freeciv-gtk3.22.exe`
  arrives as `freeciv-gtk3`, so the mapping lists `freeciv-gtk3`. Freeciv 3.0
  had a GTK 3.0 client with that name; it uses the same keys, but that was not
  checked.
- Linux X11 reports `ps -o comm=`, which the kernel cuts to 15 characters.
  `freeciv21-client` (16 characters) arrives as `freeciv21-clien`, so the
  mapping lists that too. The other names are 15 characters or shorter.
- A window forwarded from Windows is tried by its whole lower-cased name first
  (`remote_window.py`), so the mapping also lists the `.exe` names.
- The multiplayer launchers (`freeciv-mp-gtk4`, `freeciv-mp-qt`, ...), the
  server and the ruleset tools have no entry, so they get no game keys.
  `tests/handler/active_window_test.py` checks this.

## Shortcut reference

### Freeciv 3.2 GTK clients (`freeciv.yaml`)

Freeciv 3.2.6, tag `R3_2_6`, commit
`2c4304c742aa81f1d73a5d604ed83237d57804a1`
(<https://github.com/freeciv/freeciv/tree/R3_2_6>):

| File | Keys drawn |
|---|---|
| `client/gui-gtk-4.0/menu.c` (`menu_entries[]`, lines 574 to 941) | every letter, Ctrl and Ctrl+Shift key, F1 to F9, F11, F12, the battle groups |
| `client/gui-gtk-3.22/menu.c` (`entries_*` tables, lines 296 to 622) | the same keys, checked one by one |
| `client/gui-gtk-4.0/gui_main.c` (`toplevel_key_press_handler`, `key_press_map_canvas`) | Shift+Enter (end turn), `-` (zoom out), `'` (chat line), Shift+Home (center on capital) |
| `client/gui-gtk-3.22/gui_main.c` (the same two functions) | the same four keys |

Only keys that both GTK clients bind in the same way are drawn. Ctrl in the
table is `ACCL_MOD_KEY`, which is Cmd on macOS (`gui_main.h`).

Keys whose result depends on the unit. The key is drawn with its common meaning:

- **B** builds a city, or joins a city. For a unit that cannot do that but can
  help build a wonder (a Caravan), B is *Help wonder*
  (`build_city_callback` in `menu.c`).
- **R** builds a road, and on a tile with a road the next road type (railroad,
  then maglev in the rulesets that have them). For a unit that can establish a
  trade route here (a Caravan), R is *Establish trade route*
  (`build_road_callback`).
- **P** cleans pollution or fallout, whichever the tile has.
- **Shift+F** and **Shift+E** build the ruleset's first and second base type
  (`gui_type_base0`, `gui_type_base1`). The client's menus name them Fortress
  and Airbase, and the rulesets that come with Freeciv 3.2 use those names.
- **Ctrl+Shift+P** opens the policies dialog. A ruleset without policies
  (multipliers) has nothing in it.

### Freeciv 3.2 Qt client (`freeciv_qt.yaml`)

The same tag. `client/gui-qt/shortcuts.cpp` (`default_shortcuts[]`, lines 59
to 178), `client/gui-qt/menu.cpp` (`setShortcut` calls, lines 1001 to 1644)
and `client/gui-qt/mapctrl.cpp` (`map_view::keyPressEvent`). Changes from the
GTK set:

| Key | Qt client | GTK clients |
|---|---|---|
| Z | Delayed go to | Select single unit |
| Shift+Z | Select single unit | (none) |
| Shift+S | Set or unset rally point | Unsentry all on tile |
| Ctrl+Shift+D | Unsentry all on tile | (none) |
| Shift+B, Shift+J, Shift+N | Go and build city, go and join city, go and explode nuclear | (GTK 3.22 only, so not in the GTK set) |
| Ctrl+T | Add or remove city in trade planning | Tax rates |
| Ctrl+F | City full bar | Find city |
| Ctrl+Y | Quick airlift | City outlines |
| Ctrl+E | Advanced unit selection | Editing mode |
| Ctrl+Shift+L | Lock interface | Worklists |
| Shift+H | Minimap | (none) |
| Enter | Chat line | (none) |
| `'`, Shift+Home | (none) | Chat line, center on capital |
| Ctrl+Z, Ctrl+Shift+C, Ctrl+J | Execute delayed orders, clear orders, automatic caravan | (none) |
| Ctrl+Space | Units on the tile under the mouse | (none) |
| Alt+Enter | Fullscreen | (none) |
| Shift+`=`, Ctrl+Backspace | Zoom in (`Qt::Key_Plus`), default zoom | (none) |
| F9, Ctrl+Q, Ctrl+Shift+P, Ctrl+Shift+G, Ctrl+Shift+R, Ctrl+Shift+F | (none) | Messages, quit, policies, revolution, rally point dialog, infrastructure dialog |

Ctrl+F1 is both *Assign battle group 1* (a menu shortcut) and *Popup combat
information* (`SC_POPUP_COMB_INF`). The menu shortcut takes the key first, so
the battle group is drawn. Zoom in is `+`, which is Shift+`=` on a US layout;
that Qt matches the shifted key was **not tried** on a keyboard.

### Freeciv 3.2 SDL2 and SDL3 clients (`freeciv_sdl.yaml`)

The same tag. `client/gui-sdl2/menu.c` (the unit order widgets, lines 405 to
935), `client/gui-sdl2/mapctrl.c` (the widget keys at lines 1501 to 1761 and
`map_event_handler`) and `client/gui-sdl2/gui_main.c`
(`main_key_down_handler`). The `client/gui-sdl3/` files bind the same keys
(compared key by key; only the SDL3 constant names differ).

The unit orders, the reports and the map overlays are those of the GTK set,
with these changes:

- Left out because the SDL clients bind them otherwise: Ctrl+M (shows mines;
  there is no maglev connect order), Ctrl+S (shows resources), Ctrl+Shift+F
  (shows bases), V (shows city output), F1, Shift+Home (the Home key moves
  the unit).
- Left out because the SDL clients do not bind them: Z, Shift+V, Shift+C,
  Shift+X, `-`, `'`, Ctrl+T, Ctrl+Q, Ctrl+E, Ctrl+Shift+P, Ctrl+Shift+L,
  Ctrl+Shift+R and the twelve battle group keys.
- F9 shows or hides the message window. Space is *No orders*. Shift+N is
  *Explode nuclear*.
- The order keys (Ctrl+I among them) are widgets that exist while a unit is
  selected. With no unit selected, Ctrl+I shows irrigation instead
  (`map_event_handler`).

### Freeciv21 (`freeciv21.yaml`)

Freeciv21 3.1.3, tag `v3.1.3`, commit
`63c3509f220021053a813e24fd354439ee520885`
(<https://github.com/longturn/freeciv21/tree/v3.1.3>): `client/shortcuts.cpp`
(`default_shortcuts()`), `client/menu.cpp` and `client/mapctrl.cpp`. Freeciv21
is a fork of the Qt client, so `gen_variants.py` applies the Qt changes first
and then these:

| Key | Freeciv21 3.1.3 |
|---|---|
| Ctrl+M | Minimap (no maglev connect order) |
| Ctrl+W | City output (Ctrl+V is not bound) |
| Ctrl+U | Upgrade unit |
| Shift+U | Unload all from transporter (Shift+T is not bound) |
| P | Clean pollution; for a unit that cannot, paradrop (`slot_clean_pollution`) |
| N | Clean nuclear fallout |
| Ctrl+F1 | Combat information (there are no battle groups) |
| J, Shift+H, F1 to F4 with Shift, Ctrl or Ctrl+Shift | not bound |

Left out because two actions share the key, and Qt then fires neither
("ambiguous shortcut"):

- **Shift+X**: *Auto explore* (`SC_AUTOEXPLORE`) and *Same type everywhere*.
  X alone is not bound.
- **Ctrl+O**: *City growth* and *Convert unit*. Shift+O is not bound.

The editor shortcut Ctrl+Shift+E is not in 3.1.3, so it is not drawn.

### Civilization II (`civ2.yaml`)

The MicroProse manuals on the Internet Archive:

- *Sid Meier's Civilization II - Manual (EN) (1996)*,
  <https://archive.org/details/sid-meiers-civilization-ii-manual>: the table
  of contents (the key list) and the "Reference: Screen by Screen" headings.
- *Civilization 2 Manual*, a printing dated 2000,
  <https://archive.org/details/civilization-2-manual>: the same key list, with
  clean text.

Every drawn key except the function keys is listed the same way in both
printings: B, R, I, M, O, E, F, P, Shift+P, U, G, L, H, S, Shift+D, A, W,
Space, V, Z, X, Ctrl+Z, Shift+Z, Shift+X, T, C, Shift+T, Shift+H, Shift+C,
Shift+R, Ctrl+O, Ctrl+P, Ctrl+E, Ctrl+S, Ctrl+L, Ctrl+R, Ctrl+T, Ctrl+G.

The advisors and reports are F1 to F9, F11 and F12 in the 1996 manual (City
status, Defense minister, Foreign minister, Attitude advisor, Trade advisor,
Science advisor, Wonders of the world, Top 5 cities, Civilization score,
Demographics, Spaceships). The 2000 printing puts them on 1 to 9, `-` and `=`
instead. The overlay draws the 1996 function keys. Whether the later editions
also answer the function keys is **unverified**.

Keys whose result depends on the unit:

- **F** is *Fortify* for a military unit and *Build fortress* for Settlers and
  Engineers. *Fortify* is drawn.
- **P** is *Clean up pollution* for Settlers and Engineers and *Paradrop* for
  Paratroopers. *Clean up pollution* is drawn.
- **B** builds a new city, or joins a city.

### Civilization I (`civ1.yaml`)

Two MicroProse documents and one community copy:

1. *Civilization MS DOS - Technical Supplement* (the IBM key tables),
   <https://archive.org/details/technical-supplement>.
2. The manual: the 1991 printing,
   <https://archive.org/details/civilization-1-manual>, and the 1994
   revision, <https://archive.org/details/civilization-1-manual_202301>.
3. CivFanatics' transcription of the technical supplement,
   <https://www.civfanatics.com/civ1/manual/civ1_man.htm>.

Only keys that at least two of these list are drawn. The CivFanatics page is a
copy of document 1, not an independent source, so the drawn keys fall into two
groups:

- Listed by the supplement **and** the manual: B, C, F, G, H, P, Shift+P, S,
  Shift+D, U, W, Space, F9 and Shift+`/` (find city).
- Listed by the supplement and its CivFanatics copy only: R, I, M, T (units
  on or off), Shift+S (save game), `-` and `=` (luxury and tax rate), F1 to
  F8 and F10.

OpenCiv1 (a C# rewrite from the disassembled game) was not used: its
repository could not be read from this session.

F is *Fortify* for a military unit and *Build fortress* for Settlers. R builds
a road, and a railroad on a road.

## Civilization I in DOSBox

Civilization I runs in DOSBox, which runs any DOS program. The mapping entry
for DOSBox (`dosbox`, `dosbox-staging`, `dosbox-x`, with and without `.exe`)
has no overlay of its own; a `titles-contains` sub-map loads the Civilization
set only when the window title has the word `CIV` or `CIV.EXE`. The match is
on whole words and case-sensitive, so `CIVEDIT`, `COLONIZE` or a path shown as
one word (`C:\CIV\CIV.EXE`) does not match.

The title formats, read from the sources:

- DOSBox 0.74-3, `src/gui/sdlmain.cpp` (`GFX_SetTitle`, SVN tag
  `RELEASE_0_74_3`): `DOSBox 0.74-3, Cpu speed:     3000 cycles, Frameskip  0,
  Program:      CIV`. The program name is right-aligned in 8 characters, without
  the extension.
- DOSBox Staging 0.82.2, `src/gui/titlebar.cpp` (commit `f8c24f87`): the
  program name with its extension first, then ` - ` and the rest
  (`CIV.EXE - 3000 cycles/ms`). With `titlebar = program=path` the title has
  the full path as one word and matches nothing.
- DOSBox-X: `DOSBox-X ...: CIV - ...`. This format is taken from the Dune II
  entry next to it, which records it as read from the DOSBox-X sources; it was
  not read again for this set.

None of the titles was seen on a running DOSBox.

## Left out

All sets:

- **Movement**: the numeric keypad, the arrow keys, Home, End, Page Up, Page
  Down and the digits 1 to 9 move the selected unit; 5 selects the previous
  unit (`key_press_map_canvas` in the GTK clients, `map_view::keyPressEvent`
  in the Qt clients). In Civilization I and II the numeric keypad moves units. The
  keyboard has no numpad, and the other keys would show eight arrows that
  repeat the key legends.
- **Esc** cancels the current action. It shows the program mark.

Freeciv GTK set:

- **Shift+`=`** and **Shift+`.`/`,`**: on a US layout these are `+`, `>` and
  `<`. The GTK 4 client takes Shift+`+` as *sound volume up*, the GTK 3.22
  client as *zoom in*, so the two clients disagree. `<` and `>` are
  *volume down* and *volume up*, and `*` is *Achievements*; where these
  characters are depends on the keyboard layout.
- **Ctrl+`+`** (unit stack size): the same layout problem.
- **Ctrl+F11** (GTK 4) and **Alt+Enter** (GTK 3.22): fullscreen, on different
  keys in the two clients.
- **Shift+B, Shift+J, Shift+N** (go and build city, go and join city, go and
  explode nuclear): only the GTK 3.22 client binds them.
- **Ctrl+Shift+W** (fog of war): only in the editor. **Ctrl+Alt+R** (reload
  the tileset): only in debug builds.
- **Shift+Page Up / Page Down**: scroll the message area; Page Up and Page Down
  alone move the unit.
- **B in the city-buy mode** (buy production in the highlighted cities): a
  temporary mode that the window title does not show.

Qt client and Freeciv21:

- Ctrl+Shift+F5, Ctrl+Shift+F6, Ctrl+Shift+J, Ctrl+Shift+K (reload the theme
  or tileset, load a Lua script): developer aids.

Civilization II:

- **Quit**: Ctrl+Q in the 1996 manual and Ctrl+X in the 2000 printing.
  **Ctrl+X** is also *Max zoom out* in both. The key is not drawn.
- **Ctrl+K** and the Shift+F-key commands: the cheat menu.
- **Enter** ends the turn only with the *Always wait at end of turn* option.

Civilization I:

- **Alt+Q** (quit), **Alt+V** (sound), **Alt+H** (help), **Tab** (map
  cursor), **Alt+letter** (menus): the keys of the keyboard-only interface and
  the menu bar.
- The city screen keys (P, 1 to 8, S, A, C, B in the city display): they work
  only in the city screen, and the window title does not change when it opens.

## Placement

As for OpenTTD (`../openttd/SOURCES.md`): every icon sits at the right edge
and uses the full height, and the firmware clears 3 px around it, so a letter
legend stays whole. The function keys use the legend widths AoE2 measured:
F1, F2, F3 and F8 34×40, F4 to F7 30×40, F9 to F12 40×40. `fetch_icons.py`
draws each icon at exactly its key area, so the generator places it 1:1
(`preview_black.py --check-1to1` reports no cell for any of the six specs).

Font Awesome icons fill a 34×34 box and game-icons.net icons a 38×38 box at
the bottom right of their area, because the solid icons read heavier; a few
icons have their own box (`INK` in `fetch_icons.py`).

Composed icons:

- **Connect orders** (Ctrl+R, Ctrl+L, Ctrl+M, Ctrl+I): the road, train,
  subway train or faucet, with a chain link above it.
- **Go and build city, go and join city** (Qt, Freeciv21): the target with the
  route icon above it.
- **Zoom steps** (Civilization II Ctrl+Z, Shift+Z, Shift+X; Qt and Freeciv21
  Ctrl+Backspace): the magnifier with MAX, 1:1 or MID above it, set in DejaVu
  Sans Bold (Bitstream Vera licence, the copy bundled with matplotlib 3.9.2).
- **Battle groups** (Shift, Ctrl and Ctrl+Shift with F1 to F4): crossed
  sabres with the group number at the top left. Shift (select) has no mark,
  Ctrl (assign) has `=` and Ctrl+Shift (append) has `+` at the top right. The
  sabres are lit from alpha 80 instead of 150, so the thin blades keep their
  width.

## ESC marks

The ESC key shows the name of the game, drawn over the whole 72×40 cell
without the ESC legend (`program_icon_legend: false`, protocol v25): FREECIV,
FREECIV with 21 below it, CIV II and CIV I. The text is set in Cinzel by
Natanael Gama (SIL OFL 1.1, the variable font
`ofl/cinzel/Cinzel[wght].ttf` from google/fonts at commit
`e7db6ca603fd4862010383ff17ffd6cc4ffac1c0`, at weight 700). No logo art of
Freeciv, Freeciv21, MicroProse or Firaxis is used.

## Icons

Licence texts for the licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Font Awesome Free 6.5.2, solid style (CC BY 4.0, Fonticons, Inc.), and
game-icons.net (CC BY 3.0, credit per author). `fetch_icons.py` downloads the
sources into a temporary folder; only the drawn icons are committed.

| File | Source | Author | Licence |
|---|---|---|---|
| `build_city.png` | Font Awesome `building-flag` | Fonticons, Inc. | CC BY 4.0 |
| `road.png` | Font Awesome `road` | Fonticons, Inc. | CC BY 4.0 |
| `irrigate.png` | Font Awesome `faucet-drip` | Fonticons, Inc. | CC BY 4.0 |
| `cultivate.png` | Font Awesome `tractor` | Fonticons, Inc. | CC BY 4.0 |
| `mine.png` | game-icons.net `delapouite/mine-wagon` | delapouite | CC BY 3.0 |
| `plant.png` | Font Awesome `tree` | Fonticons, Inc. | CC BY 4.0 |
| `transform.png` | Font Awesome `mountain-sun` | Fonticons, Inc. | CC BY 4.0 |
| `convert.png` | Font Awesome `arrow-right-arrow-left` | Fonticons, Inc. | CC BY 4.0 |
| `clean.png` | Font Awesome `broom` | Fonticons, Inc. | CC BY 4.0 |
| `pillage.png` | Font Awesome `fire` | Fonticons, Inc. | CC BY 4.0 |
| `fortify.png` | Font Awesome `shield-halved` | Fonticons, Inc. | CC BY 4.0 |
| `fortress.png` | game-icons.net `delapouite/castle` | delapouite | CC BY 3.0 |
| `airbase.png` | Font Awesome `plane-arrival` | Fonticons, Inc. | CC BY 4.0 |
| `sentry.png` | Font Awesome `eye` | Fonticons, Inc. | CC BY 4.0 |
| `unsentry.png` | Font Awesome `bell` | Fonticons, Inc. | CC BY 4.0 |
| `goto.png` | Font Awesome `route` | Fonticons, Inc. | CC BY 4.0 |
| `return_city.png` | Font Awesome `arrow-right-to-city` | Fonticons, Inc. | CC BY 4.0 |
| `goto_city.png` | Font Awesome `map-location-dot` | Fonticons, Inc. | CC BY 4.0 |
| `explore.png` | Font Awesome `compass` | Fonticons, Inc. | CC BY 4.0 |
| `auto_worker.png` | Font Awesome `robot` | Fonticons, Inc. | CC BY 4.0 |
| `patrol.png` | Font Awesome `arrows-left-right` | Fonticons, Inc. | CC BY 4.0 |
| `wait.png` | Font Awesome `hourglass-half` | Fonticons, Inc. | CC BY 4.0 |
| `done.png` | Font Awesome `check` | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome `right-to-bracket` | Fonticons, Inc. | CC BY 4.0 |
| `unload.png` | Font Awesome `right-from-bracket` | Fonticons, Inc. | CC BY 4.0 |
| `unload_all.png` | Font Awesome `truck-ramp-box` | Fonticons, Inc. | CC BY 4.0 |
| `home_city.png` | Font Awesome `house` | Fonticons, Inc. | CC BY 4.0 |
| `upgrade.png` | Font Awesome `circle-up` | Fonticons, Inc. | CC BY 4.0 |
| `disband.png` | Font Awesome `user-xmark` | Fonticons, Inc. | CC BY 4.0 |
| `do_action.png` | Font Awesome `hand-pointer` | Fonticons, Inc. | CC BY 4.0 |
| `paradrop.png` | Font Awesome `parachute-box` | Fonticons, Inc. | CC BY 4.0 |
| `nuke.png` | Font Awesome `bomb` | Fonticons, Inc. | CC BY 4.0 |
| `fallout.png` | Font Awesome `radiation` | Fonticons, Inc. | CC BY 4.0 |
| `select_single.png` | Font Awesome `user` | Fonticons, Inc. | CC BY 4.0 |
| `select_tile.png` | Font Awesome `users` | Fonticons, Inc. | CC BY 4.0 |
| `select_type_tile.png` | Font Awesome `people-group` | Fonticons, Inc. | CC BY 4.0 |
| `select_type_cont.png` | Font Awesome `earth-africa` | Fonticons, Inc. | CC BY 4.0 |
| `select_type_all.png` | Font Awesome `globe` | Fonticons, Inc. | CC BY 4.0 |
| `center.png` | Font Awesome `crosshairs` | Fonticons, Inc. | CC BY 4.0 |
| `capital.png` | Font Awesome `landmark-dome` | Fonticons, Inc. | CC BY 4.0 |
| `end_turn.png` | Font Awesome `forward-step` | Fonticons, Inc. | CC BY 4.0 |
| `zoom_in.png` | Font Awesome `magnifying-glass-plus` | Fonticons, Inc. | CC BY 4.0 |
| `zoom_out.png` | Font Awesome `magnifying-glass-minus` | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | Font Awesome `comment` | Fonticons, Inc. | CC BY 4.0 |
| `map_view.png` | Font Awesome `map` | Fonticons, Inc. | CC BY 4.0 |
| `units_report.png` | Font Awesome `person-military-rifle` | Fonticons, Inc. | CC BY 4.0 |
| `nations.png` | Font Awesome `flag` | Fonticons, Inc. | CC BY 4.0 |
| `cities.png`, `city_status.png` | Font Awesome `city` | Fonticons, Inc. | CC BY 4.0 |
| `economy.png` | Font Awesome `coins` | Fonticons, Inc. | CC BY 4.0 |
| `research.png` | Font Awesome `flask` | Fonticons, Inc. | CC BY 4.0 |
| `wonders.png` | Font Awesome `landmark` | Fonticons, Inc. | CC BY 4.0 |
| `top_cities.png` | Font Awesome `trophy` | Fonticons, Inc. | CC BY 4.0 |
| `messages.png` | Font Awesome `envelope` | Fonticons, Inc. | CC BY 4.0 |
| `demographics.png` | Font Awesome `chart-column` | Fonticons, Inc. | CC BY 4.0 |
| `spaceship.png` | Font Awesome `rocket` | Fonticons, Inc. | CC BY 4.0 |
| `tax.png` | Font Awesome `scale-balanced` | Fonticons, Inc. | CC BY 4.0 |
| `policies.png` | Font Awesome `sliders` | Fonticons, Inc. | CC BY 4.0 |
| `revolution.png` | Font Awesome `hand-fist` | Fonticons, Inc. | CC BY 4.0 |
| `find_city.png` | Font Awesome `magnifying-glass-location` | Fonticons, Inc. | CC BY 4.0 |
| `save.png` | Font Awesome `floppy-disk` | Fonticons, Inc. | CC BY 4.0 |
| `quit.png` | Font Awesome `power-off` | Fonticons, Inc. | CC BY 4.0 |
| `worklists.png` | Font Awesome `list-ol` | Fonticons, Inc. | CC BY 4.0 |
| `rally.png` | Font Awesome `flag-checkered` | Fonticons, Inc. | CC BY 4.0 |
| `infra.png` | Font Awesome `trowel-bricks` | Fonticons, Inc. | CC BY 4.0 |
| `editor.png` | Font Awesome `pen-ruler` | Fonticons, Inc. | CC BY 4.0 |
| `grid.png` | Font Awesome `table-cells` | Fonticons, Inc. | CC BY 4.0 |
| `borders.png` | Font Awesome `vector-square` | Fonticons, Inc. | CC BY 4.0 |
| `city_names.png` | Font Awesome `tag` | Fonticons, Inc. | CC BY 4.0 |
| `city_prod.png` | Font Awesome `industry` | Fonticons, Inc. | CC BY 4.0 |
| `trade_routes.png` | Font Awesome `money-bill-transfer` | Fonticons, Inc. | CC BY 4.0 |
| `outlines.png` | Font Awesome `draw-polygon` | Fonticons, Inc. | CC BY 4.0 |
| `city_output.png` | Font Awesome `wheat-awn` | Fonticons, Inc. | CC BY 4.0 |
| `city_growth.png` | Font Awesome `seedling` | Fonticons, Inc. | CC BY 4.0 |
| `native_tiles.png` | Font Awesome `shoe-prints` | Fonticons, Inc. | CC BY 4.0 |
| `delayed_goto.png` | Font Awesome `clock` | Fonticons, Inc. | CC BY 4.0 |
| `delayed_exec.png` | Font Awesome `play` | Fonticons, Inc. | CC BY 4.0 |
| `clear_orders.png` | Font Awesome `eraser` | Fonticons, Inc. | CC BY 4.0 |
| `trade_plan.png` | Font Awesome `handshake` | Fonticons, Inc. | CC BY 4.0 |
| `auto_caravan.png` | game-icons.net `delapouite/caravan` | delapouite | CC BY 3.0 |
| `quick_airlift.png` | Font Awesome `plane` | Fonticons, Inc. | CC BY 4.0 |
| `lock.png` | Font Awesome `lock` | Fonticons, Inc. | CC BY 4.0 |
| `adv_select.png` | Font Awesome `filter` | Fonticons, Inc. | CC BY 4.0 |
| `fullbar.png` | Font Awesome `bars-progress` | Fonticons, Inc. | CC BY 4.0 |
| `minimap.png` | Font Awesome `image` | Fonticons, Inc. | CC BY 4.0 |
| `units_sel.png` | Font Awesome `layer-group` | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome `expand` | Fonticons, Inc. | CC BY 4.0 |
| `combat_info.png` | Font Awesome `burst` | Fonticons, Inc. | CC BY 4.0 |
| `activate.png` | Font Awesome `circle-play` | Fonticons, Inc. | CC BY 4.0 |
| `throne.png` | game-icons.net `delapouite/throne-king` | delapouite | CC BY 3.0 |
| `load_game.png` | Font Awesome `folder-open` | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome `gear` | Fonticons, Inc. | CC BY 4.0 |
| `graphic_options.png` | Font Awesome `display` | Fonticons, Inc. | CC BY 4.0 |
| `report_options.png` | Font Awesome `table-list` | Fonticons, Inc. | CC BY 4.0 |
| `retire.png` | Font Awesome `person-walking-arrow-right` | Fonticons, Inc. | CC BY 4.0 |
| `council.png` | Font Awesome `users-rectangle` | Fonticons, Inc. | CC BY 4.0 |
| `pieces.png` | Font Awesome `chess-pawn` | Fonticons, Inc. | CC BY 4.0 |
| `hidden_terrain.png` | Font Awesome `eye-slash` | Fonticons, Inc. | CC BY 4.0 |
| `attitude.png` | Font Awesome `face-smile` | Fonticons, Inc. | CC BY 4.0 |
| `score.png` | Font Awesome `ranking-star` | Fonticons, Inc. | CC BY 4.0 |
| `intelligence.png` | Font Awesome `user-secret` | Fonticons, Inc. | CC BY 4.0 |
| `world_map.png` | Font Awesome `earth-americas` | Fonticons, Inc. | CC BY 4.0 |
| `luxury.png` | Font Awesome `champagne-glasses` | Fonticons, Inc. | CC BY 4.0 |
| `connect_road.png` | Font Awesome `road`, with Font Awesome `link` | Fonticons, Inc. | CC BY 4.0 |
| `connect_rail.png` | Font Awesome `train`, with Font Awesome `link` | Fonticons, Inc. | CC BY 4.0 |
| `connect_maglev.png` | Font Awesome `train-subway`, with Font Awesome `link` | Fonticons, Inc. | CC BY 4.0 |
| `connect_irrigation.png` | Font Awesome `faucet-drip`, with Font Awesome `link` | Fonticons, Inc. | CC BY 4.0 |
| `go_build.png` | Font Awesome `building-flag`, with Font Awesome `route` | Fonticons, Inc. | CC BY 4.0 |
| `go_join.png` | Font Awesome `people-roof`, with Font Awesome `route` | Fonticons, Inc. | CC BY 4.0 |
| `zoom_max.png`, `zoom_std.png`, `zoom_mid.png` | Font Awesome `magnifying-glass-plus`, `magnifying-glass`, `magnifying-glass-minus`, with MAX, 1:1, MID in DejaVu Sans Bold | Fonticons, Inc.; font: Bitstream, Inc. | CC BY 4.0; font: Bitstream Vera licence |
| `bg_select1.png` to `bg_select4.png`, `bg_assign1.png` to `bg_assign4.png`, `bg_append1.png` to `bg_append4.png` | game-icons.net `lorc/crossed-sabres`, with the number, `=` and `+` in DejaVu Sans Bold | lorc; font: Bitstream, Inc. | CC BY 3.0; font: Bitstream Vera licence |
| `program_freeciv.png`, `program_freeciv21.png`, `program_civ2.png`, `program_civ1.png` | drawn by `fetch_icons.py` in Cinzel | font: Natanael Gama (The Cinzel Project Authors) | font: SIL OFL 1.1 |
