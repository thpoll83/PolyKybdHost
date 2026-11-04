# Civilization IV overlays: sources

`scripts/generate_app_overlays.py` renders `civ4_bts.yaml` and
`civ4_classic.yaml`; `fetch_icons.py` rebuilds `icons/`; `gen_classic.py`
writes `civ4_classic.yaml` from `civ4_bts.yaml`.

| Set | Loads for |
|---|---|
| `civ4_bts_template` (2 files, 76 keys) | Beyond the Sword: `civ4beyondsword` on Windows, `civ4beyondsword.exe` under Wine, `steam_app_8800` under Proton |
| `civ4_classic_template` (2 files, 69 keys) | The base game and Warlords: `civilization4` and `civ4warlords` on Windows, `civilization4.exe` and `civ4warlords.exe` under Wine, `steam_app_3900` and `steam_app_3990` under Proton |

The executable names `Civilization4.exe`, `Civ4Warlords.exe` and
`Civ4BeyondSword.exe` are from the Lutris installer for the GOG edition
(<https://lutris.net/games/install/11366/view>, read 2026-11-04), which starts
each game by that file. The Steam app ids are from SteamDB and the Steam store
(3900 the base game, 3990 Warlords, 8800 Beyond the Sword). The Windows matcher
drops `.exe`; Wine keeps it in the WM_CLASS. **Unverified**: none of these
names was checked on an install, and it was not checked that Proton reports
`steam_app_<id>` for these three games.

## Shortcut reference

The game defines its hotkeys in XML: `<HotKey>`, `<bCtrlDown>`, `<bAltDown>`,
`<bShiftDown>` and `<iHotKeyPriority>` on each action, and a second key in
`<HotKeyAlt>`. The files were read from **f1rpo/Civ4CE**
(<https://github.com/f1rpo/Civ4CE>), a change history of the game built by
extracting the official installers and patches in order (its `readme.txt`).
Commit `019c035905cc935dd57cc47a151f430de2a7b52d` ("Update to v3.19") holds
Beyond the Sword 3.19, Warlords 2.13 and the base game 1.74, the final
official versions. The hotkey files are the same at the branch head
`ba64c3545b479887739ad0ff78605b51b6fa57f9`, and no unofficial patch merged into
that branch changed them (`git log` of each file lists only official updates).

| File (Beyond the Sword) | Keys drawn |
|---|---|
| `BtS/Assets/XML/Units/CIV4ControlInfos.xml` | F1 to F12, Shift+F7, Alt+F1, Shift+F5, Shift+F8, Ctrl+E, Shift+D, Enter, Shift+Enter, W, Space (end turn), C, Ctrl+C, Ctrl+H, Insert, Home, End, `.`, `,`, `/`, `\`, Ctrl+`\`, Ctrl+A, Ctrl+T, Ctrl+B, Ctrl+Y, Ctrl+R, Alt+U, Alt+O, Alt+F, Ctrl+Alt+F, Alt+Shift+F, Ctrl+Left, Ctrl+Right, Ctrl+S, Ctrl+Alt+S, Ctrl+L, Ctrl+O, Alt+Q, Ctrl+W, Ctrl+Shift+H, Alt+D, Alt+Shift+D, Alt+S, Tab, Shift+Tab, Ctrl+Tab |
| `BtS/Assets/XML/Units/CIV4MissionInfos.xml` | Space (skip the unit's turn) |
| `Civ4/Assets/XML/Units/CIV4CommandInfos.xml` (Beyond the Sword has no copy and loads the base game's) | U, Shift+U, Delete, Backspace, Shift+Backspace |
| `BtS/Assets/XML/Units/CIV4AutomateInfos.xml` | A, E, Ctrl+Shift+C |
| `BtS/Assets/XML/Interface/CIV4InterfaceModeInfos.xml` | G, Ctrl+G, Alt+G, Shift+A |
| `BtS/Assets/XML/Units/CIV4BuildInfos.xml` | M, T, Q, O, Ctrl+F, Shift+F |

The labels follow the English text of each action's `<Description>`, from
the game's `Assets/XML/Text/*.xml`. Four labels follow the game's own code
instead (`doControl()` in `BtS/CvGameCoreDLL/CvGameInterface.cpp` at the same
commit), because the text names something else:

- Ctrl+H (`CONTROL_SELECT_HEALTHY`) shows the Hall of Fame text, but the code
  selects the units on the tile that are hurt (`isHurt()`): "Select the
  wounded units on the tile".
- `\` (`CONTROL_LASTUNIT`, text "Cycle Units (Backwards)") selects the unit
  that was selected last: "Select the last selected unit".
- W (`CONTROL_CYCLEUNIT_ALT`, text "Cycle Units (Alt)") runs the same code as
  Enter's next unit, so the current unit waits: "Next unit (wait)".
- Insert (`CONTROL_SELECTCITY`, text "Select City") selects the city the
  camera looks at: "Select the city in view".

A user who edits these files, or plays a mod that does, still sees the
defaults here.

Space, Enter and Backspace each have two actions in the XML, picked by
`iHotKeyPriority`. Both actions of a key mean the same thing, so the key is
drawn once: Space skips the unit's turn, or ends the turn when no unit waits
(`MISSION_SKIP`, `CONTROL_ENDTURN_ALT`); Enter ends the turn, or selects the
next unit (`CONTROL_ENDTURN`, `CONTROL_CYCLEUNIT`); Backspace cancels the last
order, or stops automation (`COMMAND_CANCEL`, `COMMAND_STOP_AUTOMATION`).

### The base game and Warlords

Warlords ships its own `CIV4MissionInfos.xml`, `CIV4ControlInfos.xml` and
`CIV4BuildInfos.xml` (`Warlords/Assets/XML/Units/`); the base game's files are
in `Civ4/Assets/XML/`. Every hotkey in them is also in Beyond the Sword with
the same action, except these, which `civ4_bts.yaml` marks `classic: false` so
that `gen_classic.py` leaves them out of the classic set:

| Key | Beyond the Sword | Warlords | Base game |
|---|---|---|---|
| Shift+F7 | Corporation advisor | none | none |
| Ctrl+E | Espionage screen | none | none |
| Alt+F1 | Grant independence to colonies | none | none |
| Alt+U | Enemy unit display on / off | none | none |
| Shift+F | Preserve the forest | none | none |
| Ctrl+H | Select the wounded units on the tile | Select the wounded units on the tile | Hall of Fame |
| Ctrl+Shift+H | Hall of Fame | Hall of Fame | none |

Ctrl+H and Ctrl+Shift+H differ between the base game and Warlords, and the
classic set serves both, so it draws neither.

### Checked against

The CivFanatics shortcut list (<https://www.civfanatics.com/?p=672>, read
2026-11-04) agrees with the XML for every drawn key, with one difference: it
gives the World Builder as Alt+W; the XML gives Ctrl+W, and the overlay draws
Ctrl+W.

## Left out

**Keys whose action depends on the selected unit or the terrain.** The XML
gives each of these keys to two or more actions of different units, so the
keycap cannot show one meaning:

| Key | Actions in the Beyond the Sword XML |
|---|---|
| B | Build city (settler), bombard, ranged attack, air bomb |
| F | Fortify (military units), sleep (other units), wake the unit, build fishing boats (work boat) |
| S | Sentry, sabotage, air strike, scrub fallout (worker) |
| P | Ping the map, sea patrol (ships), paradrop |
| R | Build a road or a railroad (worker), recon (aircraft), spread religion automatically (missionary) |
| I | Build a farm (irrigate, worker), intercept (fighters) |
| L | Build a lumbermill (worker), load |
| H | Fortify until healed, build a camp (worker) |
| N | Build a trade network (automated, worker), nuke |
| K | Build a workshop (worker), kill a nearby spy |
| Shift+P | Pillage, blockade (ships), build a plantation or a pasture (worker) |
| Shift+W | Build a windmill, watermill, well or winery (worker, by terrain and resource), whaling boats (work boat) |
| Alt+C | Select all units, remove jungle or chop down a forest (worker) |
| Alt+R | Route to (worker), rebase (aircraft) |

The base game and Warlords give K, P and some others to fewer actions (P is
only "Ping the map" there), but the classic set draws the same keys as the
Beyond the Sword set.

**Other keys:**

- **D (destroy production) and Shift+S (steal plans).** Spy missions of the
  base game and Warlords. No unit in Beyond the Sword's `CIV4UnitInfos.xml` has
  `bDestroy` or `bStealPlans`, so the keys do nothing there. In the classic set
  they are left out so that both sets draw the same keys.
- **Z (grip mode).** `INTERFACEMODE_GRIP` has `bVisible` 0 and no help text, so
  what it does is not documented.
- **The numpad keys** (`<HotKeyAlt>` on Skip, Sleep, Fortify, Centre, End turn
  and others): the keyboard has no numpad.
- **Esc** (close the screen, open the menu): it shows the program mark.
- **Keys the XML does not list.** The CivFanatics list also names Page Up and
  Page Down (zoom), Pause, Print Screen, Ctrl+M (music), Alt+I and Ctrl+I
  (interface), Shift+Left and Shift+Right (turn the camera), Ctrl+digit
  (groups) and Scroll Lock (voice chat). The game's engine handles them, and
  they were not checked against the game, so they are not drawn.
- **Debug keys.** `CvEventManager.onKbdEvent()` passes keys to the debug tools
  only when cheats are on.

**Colonization** (`Colonization.exe`) has no set. Its XML gives other actions
to the F-keys (F2 Europe, F3 Revolution, F6 Founding Fathers, F7 Continental
Congress; branch `col` of the same repository, commit
`a47ee9c0765f599dc60a3676b0c8885a5eb3d751`,
`Col/Assets/XML/Units/CIV4ControlInfos.xml`).

## Placement

As for OpenTTD (`../openttd/SOURCES.md`): every icon sits at the right edge
and uses the full height, and the firmware clears 3 px around it, so a letter
legend stays whole. The F-key areas use the legend widths AoE2 measured: F1,
F2, F3 and F8 34×40, F4 30×40; F5 to F7 are 30×40 like F4 (not measured), F9
to F12 40×40, which covers the right part of the F10 to F12 legends. Tab uses
30×40, as in the Command & Conquer set. The other keys use 40×40; on `,` `.`
`/` and `\` the icon erases the shifted symbol, which the game does not use.

All icons are flat 1-bit silhouettes, drawn at their key area so the
generator places each 1:1. Solid icons fill a smaller box than the key area
(`INK` in `fetch_icons.py`) so they do not outweigh the outline icons.

Composed icons (`BADGED` and `TWICE` in `fetch_icons.py`):

- Ctrl+G and Alt+G (go to with the units of the same type, with all units):
  the map pin with `=` or `ALL` at the top right. Shift+U (unload all) and
  Shift+Backspace (cancel all orders) are the U and Backspace icons with `ALL`.
  The text is DejaVu Sans Bold (Bitstream Vera licence, the copy bundled with
  matplotlib 3.9.2), as in the OpenTTD set.
- Shift+F5 and Shift+F8 (quick save, quick load): the floppy disk or the open
  folder with a lightning bolt.
- Home and End (next and previous city), `.` and `,` (next and previous unit on
  the tile): a city or a person with a triangle pointing right or left.
- Ctrl+Alt+S (save game, group): the floppy disk twice.

ESC shows the text CIV IV in Cinzel Bold by Natanael Gama (SIL OFL 1.1, the
Bold instance of `ofl/cinzel/Cinzel[wght].ttf` from google/fonts at commit
e7db6ca), at the largest size that fits 70×30 px, centred on the whole cell
and drawn without the ESC legend (`program_icon_legend: false`, protocol v25).
No Firaxis logo art is used.

## Game art: not used

Civilization IV's art (buttons, logo, leader heads) is owned by Firaxis Games
and Take-Two Interactive and is not licensed for redistribution, so none of it
is used.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Font Awesome Free 6.5.2, solid style (CC BY 4.0, Fonticons, Inc.), unless a
row says game-icons.net (CC BY 3.0, credit to the author named).

| File | Source | Author | Licence |
|---|---|---|---|
| `domestic.png` | Font Awesome `city` | Fonticons, Inc. | CC BY 4.0 |
| `financial.png` | Font Awesome `coins` | Fonticons, Inc. | CC BY 4.0 |
| `civics.png` | Font Awesome `landmark` | Fonticons, Inc. | CC BY 4.0 |
| `foreign.png` | Font Awesome `handshake-simple` | Fonticons, Inc. | CC BY 4.0 |
| `military.png` | game-icons.net `lorc/crossed-swords` | Lorc | CC BY 3.0 |
| `technology.png` | Font Awesome `flask` | Fonticons, Inc. | CC BY 4.0 |
| `religion.png` | Font Awesome `place-of-worship` | Fonticons, Inc. | CC BY 4.0 |
| `corporation.png` | Font Awesome `briefcase` | Fonticons, Inc. | CC BY 4.0 |
| `victory.png` | Font Awesome `trophy` | Fonticons, Inc. | CC BY 4.0 |
| `info.png` | Font Awesome `chart-column` | Fonticons, Inc. | CC BY 4.0 |
| `capital.png` | Font Awesome `star` | Fonticons, Inc. | CC BY 4.0 |
| `globe.png` | Font Awesome `earth-americas` | Fonticons, Inc. | CC BY 4.0 |
| `civilopedia.png` | Font Awesome `book-open` | Fonticons, Inc. | CC BY 4.0 |
| `freecolony.png` | Font Awesome `flag` | Fonticons, Inc. | CC BY 4.0 |
| `skip.png` | Font Awesome `forward-step` | Fonticons, Inc. | CC BY 4.0 |
| `endturn.png` | Font Awesome `hourglass-end` | Fonticons, Inc. | CC BY 4.0 |
| `forceendturn.png` | Font Awesome `forward-fast` | Fonticons, Inc. | CC BY 4.0 |
| `wait.png` | Font Awesome `clock` | Fonticons, Inc. | CC BY 4.0 |
| `goto.png`, `gototype.png`, `gotoall.png` | Font Awesome `location-dot` | Fonticons, Inc. | CC BY 4.0 |
| `automate.png` | Font Awesome `robot` | Fonticons, Inc. | CC BY 4.0 |
| `automoves.png` | Font Awesome `circle-play` | Fonticons, Inc. | CC BY 4.0 |
| `airlift.png` | Font Awesome `plane` | Fonticons, Inc. | CC BY 4.0 |
| `explore.png` | Font Awesome `compass` | Fonticons, Inc. | CC BY 4.0 |
| `improvecity.png` | Font Awesome `person-digging` | Fonticons, Inc. | CC BY 4.0 |
| `mine.png` | game-icons.net `lorc/mining` | Lorc | CC BY 3.0 |
| `cottage.png` | Font Awesome `house-chimney` | Fonticons, Inc. | CC BY 4.0 |
| `quarry.png` | Font Awesome `cubes-stacked` | Fonticons, Inc. | CC BY 4.0 |
| `fort.png` | Font Awesome `chess-rook` | Fonticons, Inc. | CC BY 4.0 |
| `preserve.png` | Font Awesome `tree` | Fonticons, Inc. | CC BY 4.0 |
| `offshore.png` | game-icons.net `delapouite/oil-rig` | Delapouite | CC BY 3.0 |
| `unload.png`, `unloadall.png` | Font Awesome `person-walking-arrow-right` | Fonticons, Inc. | CC BY 4.0 |
| `delete.png` | Font Awesome `trash-can` | Fonticons, Inc. | CC BY 4.0 |
| `cancel.png`, `cancelall.png` | Font Awesome `ban` | Fonticons, Inc. | CC BY 4.0 |
| `centre.png` | Font Awesome `crosshairs` | Fonticons, Inc. | CC BY 4.0 |
| `selecttype.png` | Font Awesome `people-group` | Fonticons, Inc. | CC BY 4.0 |
| `selectwounded.png` | Font Awesome `heart-pulse` | Fonticons, Inc. | CC BY 4.0 |
| `selectcity.png` | Font Awesome `house-flag` | Fonticons, Inc. | CC BY 4.0 |
| `nextcity.png`, `prevcity.png` | Font Awesome `city` | Fonticons, Inc. | CC BY 4.0 |
| `nextunit.png`, `prevunit.png` | Font Awesome `person` | Fonticons, Inc. | CC BY 4.0 |
| `cycleworkers.png` | Font Awesome `helmet-safety` | Fonticons, Inc. | CC BY 4.0 |
| `lastunit.png` | Font Awesome `backward-step` | Fonticons, Inc. | CC BY 4.0 |
| `grid.png` | Font Awesome `table-cells` | Fonticons, Inc. | CC BY 4.0 |
| `baremap.png` | Font Awesome `map` | Fonticons, Inc. | CC BY 4.0 |
| `yields.png` | game-icons.net `lorc/wheat` | Lorc | CC BY 3.0 |
| `resources.png` | Font Awesome `gem` | Fonticons, Inc. | CC BY 4.0 |
| `enemyunits.png` | Font Awesome `eye` | Fonticons, Inc. | CC BY 4.0 |
| `ortho.png` | Font Awesome `cube` | Fonticons, Inc. | CC BY 4.0 |
| `topdown.png` | Font Awesome `arrows-down-to-line` | Fonticons, Inc. | CC BY 4.0 |
| `flying.png` | Font Awesome `paper-plane` | Fonticons, Inc. | CC BY 4.0 |
| `mousefly.png` | Font Awesome `computer-mouse` | Fonticons, Inc. | CC BY 4.0 |
| `flymodes.png` | Font Awesome `video` | Fonticons, Inc. | CC BY 4.0 |
| `rotleft.png` | Font Awesome `rotate-left` | Fonticons, Inc. | CC BY 4.0 |
| `rotright.png` | Font Awesome `rotate-right` | Fonticons, Inc. | CC BY 4.0 |
| `save.png`, `savegroup.png` | Font Awesome `floppy-disk` | Fonticons, Inc. | CC BY 4.0 |
| `quicksave.png` | Font Awesome `floppy-disk` and `bolt` | Fonticons, Inc. | CC BY 4.0 |
| `load.png` | Font Awesome `folder-open` | Fonticons, Inc. | CC BY 4.0 |
| `quickload.png` | Font Awesome `folder-open` and `bolt` | Fonticons, Inc. | CC BY 4.0 |
| `options.png` | Font Awesome `gear` | Fonticons, Inc. | CC BY 4.0 |
| `retire.png` | Font Awesome `door-open` | Fonticons, Inc. | CC BY 4.0 |
| `worldbuilder.png` | Font Awesome `mountain-sun` | Fonticons, Inc. | CC BY 4.0 |
| `halloffame.png` | Font Awesome `medal` | Fonticons, Inc. | CC BY 4.0 |
| `espionage.png` | Font Awesome `user-secret` | Fonticons, Inc. | CC BY 4.0 |
| `diplomacy.png` | Font Awesome `user-tie` | Fonticons, Inc. | CC BY 4.0 |
| `details.png` | Font Awesome `id-card` | Fonticons, Inc. | CC BY 4.0 |
| `gamedetails.png` | Font Awesome `circle-info` | Fonticons, Inc. | CC BY 4.0 |
| `sign.png` | Font Awesome `signs-post` | Fonticons, Inc. | CC BY 4.0 |
| `chatteam.png` | Font Awesome `comment` | Fonticons, Inc. | CC BY 4.0 |
| `chatall.png` | Font Awesome `bullhorn` | Fonticons, Inc. | CC BY 4.0 |
| `eventlog.png` | Font Awesome `list` | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | CIV IV in Cinzel Bold | Natanael Gama (The Cinzel Project Authors) | SIL OFL 1.1 |

The files starting with `_` are the downloaded sources that `fetch_icons.py`
turns into the composed icons above.
