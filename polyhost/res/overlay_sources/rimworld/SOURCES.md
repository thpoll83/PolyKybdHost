# RimWorld overlay: sources

`scripts/generate_app_overlays.py` renders `rimworld.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `rimworld_template` (1 file) | RimWorld (Steam app 294100) on Windows, Linux and macOS: `RimWorldWin64.exe`, `RimWorldLinux`, `RimWorld` / `RimWorldMac`, and `steam_app_294100` under Proton |

The game reads the same Unity key codes on every OS and its defaults use no
Ctrl or Cmd shortcut, so there is no macOS set. The app names were not checked
on an install.

## Shortcut reference

The defaults are the key bindings in the game's own data files, which every
install has as XML text (read 2026-10-30):

- `Data/Core/Defs/Misc/KeyBindings/KeyBindings.xml`: each `KeyBindingDef` has a
  `defaultKeyCodeA` (and some a `defaultKeyCodeB`). Read from the public mirror
  <https://github.com/Adelphea/GuildForge_Mobile/blob/HEAD/data/rimworld_data/Core/Defs/Misc/KeyBindings/KeyBindings.xml>
  (sha256 `fb84d9f2…c84ea9`). The game version is not stated there. It has the
  draw-style bindings, and its 59 `defName`s are the same as the list for
  RimWorld 1.7.4981 rev136 in
  <https://github.com/Kon-on/rimworld-modding-skill> (`docs/def-schema.json`).
  An older mirror without the draw-style bindings
  (<https://github.com/AustenXiyue/RimWorldLibrary>,
  `vanilla/Data/Core/Defs/Misc/KeyBindings/KeyBindings.xml`) gives the same keys
  for every binding drawn here.
- `Data/Core/Defs/Misc/MainButtonDefs/MainButtons.xml`: each `MainButtonDef`
  has a `defaultHotKey` (Tab and F1 to F9), from the same mirror (sha256
  `f5acad0b…0c3a3a`). The 1.7 list above also has 10 `defaultHotKey` values.
- Checked against the RimWorld Wiki, <https://rimworldwiki.com/wiki/Controls>
  (last edited 17 September 2025, read 2026-10-30 with headless Chromium).
  Every key it lists (camera, zoom, Space, Tab, F1 to F11, 1 to 4, Q, E, `,`
  and `.`) matches the data. It does not list G, T, Z, R, F, V, C, X, Home or
  End.

A player can change every key under Options, Keyboard configuration. The
overlay shows the defaults.

| Key | Action | Definition |
|---|---|---|
| Space | Pause / resume | `TogglePause` |
| 1, 2, 3 | Speed: normal, fast, super fast | `TimeSpeed_Normal`, `_Fast`, `_Superfast` |
| Home, End | Speed: faster, slower | `TimeSpeed_Faster`, `TimeSpeed_Slower` |
| W, A, S, D | Move the camera up, left, down, right | `MapDolly_Up` … `MapDolly_Right` |
| Page Down, Page Up | Zoom in, zoom out | `MapZoom_In`, `MapZoom_Out` |
| Tab | Architect tab | `MainButtonDef` Architect |
| F1 to F9 | Work, Schedule, Assign, Animals, Wildlife, Research, Quests, World, History tabs | `MainButtonDef` |
| F10 | Take screenshot | `TakeScreenshot` |
| F11 | Screenshot mode (hides the interface) | `ToggleScreenshotMode` |
| `,` `.` | Previous colonist, next colonist | `PreviousColonist`, `NextColonist` |
| G | Room stats display | `ToggleRoomStatsDisplay` |
| T | Beauty display | `ToggleBeautyDisplay` |
| Z | Search the map | `OpenMapSearch` |
| Q, E | Rotate left, rotate right | `Designator_RotateLeft`, `Designator_RotateRight` |
| R | Draft | `Command_ColonistDraft` |
| F | Forbid / allow | `Command_ItemForbid` |
| V | Power on / off | `Command_TogglePower` |
| C | Cancel designation | `Designator_Cancel` |
| X | Deconstruct | `Designator_Deconstruct` |
| Esc | Program mark (in the game: close a window or open the menu) | `Cancel` |

## Left out

- `Misc1` to `Misc12` (B H Y N J U M K I L O P). Every command button of a
  selected pawn or building and every architect designator takes the next free
  one of these keys, so what each does depends on the selection.
- Q and E also select the previous and next draw style
  (`Designator_PreviousDrawStyle`, `Designator_NextDrawStyle`) while an area
  designator is active. The overlay shows rotation, the meaning while placing
  a building.
- `TimeSpeed_Ultrafast` (4): developer mode only (`devModeOnly`). The other
  developer bindings (`` ` `` `;` `/` `'` `[` `]` Insert, keypad +, Tab in the
  debug menu) are left out for the same reason. `Dev_ToggleDebugLog`
  (`` ` ``, "toggle debug log") has no `devModeOnly` flag but is in the
  Development category.
- The arrow keys (the second binding of the camera moves): the arrows keep
  their own legends.
- Enter (`Accept`): confirms a dialog, as in any program.
- Keypad `*` (`SelectNextInCell`): the keypad has no keycap cells.
- Modifier keys alone: Alt (`ShowCellInspector`), Ctrl (`ShowEyedropper`,
  `Designator_ShapeSnap`, `ModifierIncrement_10x`), Shift
  (`ModifierIncrement_100x`, `QueueOrder`). A modifier key has no cell of its
  own.
- Shift with W A S D (move the camera twice as fast, from the wiki page): it is
  not a key binding in the data, and the arrows already show the direction.
- The Factions, Menu, Ideoligion (Ideology) and Mechs (Biotech) tabs: they have
  no default key.
- No multi-key sequences exist in the defaults.

## Placement

As for Age of Empires II (`../aoe2/SOURCES.md`) and Warcraft III: every icon
sits at the right edge and uses the full height, and the firmware clears 3 px
around it, so a letter legend stays whole. The icons are drawn at exactly the
size of their key area, so the generator places them 1:1. F1 to F3 and F5 to F8
are 34×40 and F4 is 30×40, from AoE2's measured legend widths (F2 ends at
x 35, F4 at 37); F1, F3 and F5 to F8 take the F2 size, and F5 to F8 were not
measured.
F9 to F11 are 40×40 as in the Warcraft III set: F10 and F11 cover the right part
of their legend. The digits' shifted symbols are erased by the speed icons.

All icons are flat 1-bit silhouettes. The game-speed icons are drawn by
`fetch_icons.py`: one to three triangles 13×24 px for 1 to 3, two bars of the
same height for pause, and one triangle with a plus (Home) or a minus (End).
`,` and `.` show a person with a small triangle on the left (previous) or the
right (next). The camera moves are one Fluent arrow turned a quarter at a time.
Solid or wide icons (clock, camera, eye, magnifiers, prohibited, power,
dismiss, rotate arrows, globe, flag, sparkle) fill a smaller box in the
bottom-right corner of their area so they do not outweigh the others.

ESC shows RIM over WORLD in Orbitron Bold (SIL OFL 1.1, the `wght` 700
instance of `ofl/orbitron/Orbitron[wght].ttf` from google/fonts at commit
e7db6ca), drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25). RIM is 40 px wide and WORLD 70 px,
4 px apart. Simple Icons has no RimWorld logo, and the game's logo art is not
used. `fetch_icons.py` keeps a committed `program.png` and loads the font only
when it draws a new one.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `architect.png` | game-icons.net `delapouite/brick-wall` | delapouite | CC BY 3.0 |
| `work.png` | game-icons.net `lorc/flat-hammer` | lorc | CC BY 3.0 |
| `schedule.png` | Fluent UI System Icons `Clock` (24 filled) | Microsoft | MIT |
| `assign.png` | game-icons.net `delapouite/t-shirt` | delapouite | CC BY 3.0 |
| `animals.png` | game-icons.net `skoll/pig` | skoll | CC BY 3.0 |
| `wildlife.png` | game-icons.net `caro-asercion/deer` | caro-asercion | CC BY 3.0 |
| `research.png` | game-icons.net `lorc/erlenmeyer` | lorc | CC BY 3.0 |
| `quests.png` | Fluent UI System Icons `Flag` (24 filled) | Microsoft | MIT |
| `world.png` | game-icons.net `delapouite/earth-africa-europe` | delapouite | CC BY 3.0 |
| `history.png` | game-icons.net `lorc/open-book` | lorc | CC BY 3.0 |
| `screenshot.png` | Fluent UI System Icons `Camera` (24 filled) | Microsoft | MIT |
| `screenshotmode.png` | Fluent UI System Icons `Eye Off` (24 filled) | Microsoft | MIT |
| `panup.png`, `panleft.png`, `pandown.png`, `panright.png` | Fluent UI System Icons `Arrow Up` (24 filled), turned | Microsoft | MIT |
| `zoomin.png` | Fluent UI System Icons `Zoom In` (24 filled) | Microsoft | MIT |
| `zoomout.png` | Fluent UI System Icons `Zoom Out` (24 filled) | Microsoft | MIT |
| `rotateleft.png` | Fluent UI System Icons `Arrow Counterclockwise` (24 filled) | Microsoft | MIT |
| `rotateright.png` | Fluent UI System Icons `Arrow Clockwise` (24 filled) | Microsoft | MIT |
| `roomstats.png` | Material Symbols `bed` (outlined, weight 300) | Google | Apache-2.0 |
| `beauty.png` | Fluent UI System Icons `Sparkle` (24 filled) | Microsoft | MIT |
| `search.png` | Fluent UI System Icons `Search` (24 filled) | Microsoft | MIT |
| `draft.png` | game-icons.net `lorc/crossed-sabres` | lorc | CC BY 3.0 |
| `forbid.png` | Fluent UI System Icons `Prohibited` (24 filled) | Microsoft | MIT |
| `power.png` | Fluent UI System Icons `Power` (24 filled) | Microsoft | MIT |
| `cancel.png` | Fluent UI System Icons `Dismiss Circle` (24 filled) | Microsoft | MIT |
| `deconstruct.png` | game-icons.net `quoting/damaged-house` | quoting | CC BY 3.0 |
| `prevcolonist.png`, `nextcolonist.png` | game-icons.net `delapouite/person`, with a triangle drawn by `fetch_icons.py` | delapouite | CC BY 3.0 |
| `speed1.png`, `speed2.png`, `speed3.png`, `pause.png`, `faster.png`, `slower.png` | drawn by `fetch_icons.py` | - | GPL-3.0-or-later (this repository) |
| `program.png` | RIM / WORLD set in Orbitron Bold | Orbitron: Matt McInerney | SIL OFL 1.1 |
