# StepMania 5 overlay: sources

`scripts/generate_app_overlays.py` renders `stepmania.yaml`; `fetch_icons.py`
rebuilds `icons/`. The Etterna and osu! sets import the helpers of this
`fetch_icons.py`, and the Etterna set uses the icons of the keys that are the
same in both games.

| Set | Loads for |
|---|---|
| `stepmania_template` (2 files) | StepMania 5 on Linux, Windows and macOS, under the process names below |

All files named here are in <https://github.com/stepmania/stepmania> at tag
`v5.0.12`.

| Name | Where it comes from |
|---|---|
| `stepmania` | the Linux executable (`SM_NAME_RELEASE` in `src/CMakeLists.txt`) and the `Exec=` line of `stepmania.desktop`. The X11 window class is `StepMania` (`PRODUCT_FAMILY` in `src/archutils/Unix/X11Helper.cpp`), and the macOS and Windows builds are named `StepMania` (`SM_EXE_NAME` in `StepmaniaCore.cmake`); the host compares names in lower case |
| `stepmania.exe`, `stepmania-sse2.exe` | `Program\StepMania.exe` and `Program\StepMania-SSE2.exe` in the Windows installer script `stepmania.nsi`; the shortcut the installer creates starts the SSE2 one |
| `stepmania-sse2` | on Windows the host cuts the process name at the first dot, so `StepMania-SSE2.exe` arrives as `stepmania-sse2` (and `StepMania.exe` as `stepmania`) |

Names not checked on an install. Project OutFox, the closed-source successor,
has other process names and gets no set.

## Shortcut reference

Read 2026-11-14 at tag `v5.0.12` (commit
`45e0787a7457c1b9071522463aa902d59ae3a2ee`):

- `src/InputMapper.cpp`, `g_DefaultKeyMappings`: the menu buttons of every game type.
- `src/GameManager.cpp`, `g_AutoKeyMappings_Dance`: the keys of the game type
  `dance`, which is the default.
- `src/StepMania.cpp`, `HandleGlobalInputs()`: F2, Pause, Alt+F4, Print Screen,
  Alt+Enter.
- `src/ScreenDebugOverlay.cpp`, `ScreenDebugOverlay::Init()` and `Update()`: F3,
  Tab, `` ` ``, Pause, F6 to F8.
- `src/ScreenSyncOverlay.cpp`, `ScreenSyncOverlay::Input()`: F4, F9 to F12.
- `src/ScreenSelectMusic.cpp`, `ScreenSelectMusic::Input()`: the song list chords.

The same files at tag `v5.1.0-b2` (the 5.1 beta) were compared: the key tables
of `InputMapper.cpp`, `GameManager.cpp` and `ScreenSyncOverlay.cpp` are
identical. `ScreenDebugOverlay.cpp` has one more line in the debug menu there
(Reload Preferences, with F3 held); no key drawn here differs. A user who maps a key in the
game (Options, Config Key/Joy Mappings) still sees the default here.

| Key | Source name | Action |
|---|---|---|
| Enter | `GAME_BUTTON_START` | Start |
| / | `GAME_BUTTON_SELECT` | Select |
| Delete, Page Down, Home, End | `GAME_BUTTON_MENULEFT`, `MENURIGHT`, `MENUUP`, `MENUDOWN` (dance) | Menu left, right, up, down |
| - | `GAME_BUTTON_BACK`, second controller | Back for player 2 (the source comment says "laptop keyboards") |
| F1 | `GAME_BUTTON_COIN` | Insert a coin |
| Scroll Lock | `GAME_BUTTON_OPERATOR` | Operator menu (the options) |
| F2 | `HandleGlobalInputs()` | Reload metrics, textures and note skins |
| Shift+F2 | | Reload the metrics only |
| Ctrl+F2 | | Reload the scripts |
| Ctrl+Shift+F2 | | Reload the overlay screens |
| F3 (held) | `holdForDebug1` | Show the debug menu |
| Tab (held) | `holdForFast` | The game runs 4 times faster |
| `` ` `` (held) | `holdForSlow` | The game runs at a quarter of the speed |
| Pause | `toggleMute` | Mute actions on or off |
| F4 | `RevertSyncChanges` | Revert the sync changes (during a song) |
| F6 | `gameplayButton[2]`, `DebugLineAutosync` | Autosync: off, song, machine, tempo (during a song) |
| F7 | `gameplayButton[1]`, `DebugLineAssist` | Assist clap on or off (during a song) |
| Shift+F7 | | Assist metronome on or off (during a song) |
| F8 | `gameplayButton[0]`, `DebugLineAutoplay` | Autoplay (during a song) |
| F9, F10 | `ChangeSongBPM` | Song BPM down, up (during a song) |
| F11, F12 | `ChangeSongOffset` | Song offset down, up (during a song) |
| Shift+F11, Shift+F12 | `ChangeGlobalOffset` | Global offset down, up (during a song) |
| Ctrl+Shift+R | `ReloadFromSongDir()` | Reload the selected song from disk (song list) |
| Print Screen | `SaveScreenshot()` | Screenshot as JPEG |
| Shift+Print Screen | | Screenshot as PNG |
| Alt+Enter | `SetToggleWindowed()` | Toggle full screen (not on macOS, where it is a menu item) |
| Alt+F4 | `SetUserQuit()` | Quit (not on macOS) |

## Other meanings (not drawn)

| Key | Other meaning |
|---|---|
| F9 | on the song list: show the titles transliterated or in the native script |
| Pause | also sends `ToggleConsoleDisplay` to the theme |
| F5 to F8 | while F3 is held: the pages of the debug menu |
| Delete, Page Down, Home, End | only the game type `dance` maps them; other game types use other keys |

## Left out

- The arrow keys: the four dance panels of player 1 and the menu directions.
  The arrows keep their own legends.
- The keypad (player 2: panels, menu directions, Start, Select): keypad keys
  have no cell.
- F3 held with 1 to 0 and Q to D (the lines of the debug menu): F3 is not a
  modifier with a layer of its own.
- Alt held with F9 to F12 (the same changes in steps 20 times smaller): the
  same action as the key without Alt.
- Ctrl+A to Ctrl+Z on the song list (jump to the section of that letter): 26
  keys with the same picture.
- Ctrl+Backspace on the song list (delete the song): it needs the preference
  `AllowSongDeletion`, which is off by default (`src/PrefsManager.cpp`).
- The step editor keys (`src/ScreenEdit.cpp`): another mode of the same
  process, which the host cannot detect.
- The keys of the other game types (pump, kb7, beat, techno and so on).
- The macOS variants: Cmd+Q, F13 and Cmd+F12 (screenshot).

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge
and uses the full height, and the firmware clears 3 px around the icon's ink,
so a letter legend stays whole. F1 to F9 use 34×40 and F10 to F12 30×40. The
solid or wide icons (`INK` in `fetch_icons.py`) are drawn in a smaller box
inside their area. Every icon is drawn at exactly its area, so the generator
places it 1:1.

The BPM and offset keys show a gauge (BPM), a clock (song offset) or a globe
(global offset) with a minus or a plus in the top-left corner (`badged()`).

## ESC mark

ESC shows STEP over MANIA in Bungee (SIL OFL 1.1), centred on the whole cell
and drawn without the ESC legend (`program_icon_legend: false`, protocol v25).

The game's own logo is not used. `README.md` puts "our source code" under the
MIT licence and the bundled songs under a CC non-commercial licence;
`Docs/Licenses.txt` covers the code and the bundled libraries. Neither names a
licence for the logo and the theme graphics, so their licence is unclear.

## Icons

Licence texts:

- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Where each icon file comes from. The icon table gives the name to put in the
URL.

- Material Symbols (`ms:<name>`), outlined style at weight 300: `https://raw.githubusercontent.com/google/material-design-icons/10ecc14790612ca8fd164e3f4ffe9c16fc50d5b7/symbols/web/<name>/materialsymbolsoutlined/<name>_wght300_24px.svg` (`RAW` in `../material_symbols.py`; the URL names commit `10ecc14` of google/material-design-icons)
- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`
- Bungee (ESC mark): `https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/bungee/Bungee-Regular.ttf`

| File | Source | Author | Licence |
|---|---|---|---|
| `start.png`, `select.png`, `operator.png`, `back2.png` | Material Symbols `play_circle`, `menu`, `settings`, `undo` | Google | Apache-2.0 |
| `menuleft.png`, `menuright.png`, `menuup.png`, `menudown.png` | Material Symbols `arrow_back`, `arrow_forward`, `arrow_upward`, `arrow_downward` | Google | Apache-2.0 |
| `reload.png`, `reloadmetrics.png`, `reloadscripts.png`, `reloadoverlays.png` | Material Symbols `refresh`, `description`, `code`, `layers` | Google | Apache-2.0 |
| `debug.png`, `fast.png`, `slow.png`, `mute.png` | Material Symbols `bug_report`, `fast_forward`, `slow_motion_video`, `volume_off` | Google | Apache-2.0 |
| `revertsync.png`, `autosync.png`, `autoplay.png` | Material Symbols `history`, `sync`, `smart_toy` | Google | Apache-2.0 |
| `bpmdown.png`, `bpmup.png` | Material Symbols `speed`, with a minus or a plus drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `offsetdown.png`, `offsetup.png` | Material Symbols `schedule`, with a minus or a plus drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `globaldown.png`, `globalup.png` | Material Symbols `public`, with a minus or a plus drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `screenshot.png`, `screenshotraw.png`, `fullscreen.png`, `quit.png`, `reloadsong.png` | Material Symbols `photo_camera`, `high_quality`, `fullscreen`, `power_settings_new`, `audio_file` | Google | Apache-2.0 |
| `coin.png`, `assist.png` | Font Awesome Free 6.5.2 `coins`, `hands-clapping` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `metronome.png` | game-icons.net `delapouite/metronome` | delapouite | CC BY 3.0 |
| `program.png` | drawn by `fetch_icons.py` in Bungee | font: David Jonathan Ross | font: SIL OFL 1.1 |
