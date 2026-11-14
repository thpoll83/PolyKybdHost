# Etterna overlay: sources

`scripts/generate_app_overlays.py` renders `etterna.yaml`; `fetch_icons.py`
rebuilds `icons/` with the helpers of `../stepmania/fetch_icons.py`.

| Set | Loads for |
|---|---|
| `etterna_template` (2 files) | Etterna on Linux, Windows and macOS: `etterna` and `etterna.exe` |

`Etterna` is the executable target in `CMakeLists.txt` (`add_executable(Etterna)`,
`RUNTIME_OUTPUT_NAME_RELEASE "Etterna"`) of
<https://github.com/etternagame/etterna> at tag `v0.75.1`; Windows adds `.exe`
and macOS builds it as an app bundle (`CMake/Helpers/CMakeMacOS.cmake`). The
host compares names in lower case, and on Windows it cuts the name at the first
dot, so `Etterna.exe` arrives as `etterna`. Names not checked on an install.

## Why Etterna has its own set

Etterna is a fork of StepMania 5, and many of its keys are the same; those use
the StepMania icons (`SHARED` in `fetch_icons.py`). A player sees these differences in the defaults, so one
set for both games would be wrong on these keys:

| Key | StepMania 5.0.12 | Etterna 0.75.1 |
|---|---|---|
| Z, X, `,`, `.` | not mapped | the four columns |
| `` ` `` | hold: quarter speed | restart the song (and hold: quarter speed) |
| F9, F10 | song BPM down, up | F9: title display on the song list; F10 not mapped |
| Scroll Lock | operator menu | operator menu only with Ctrl |
| F1, - | insert coin, back for player 2 | not handled |
| Delete, Page Down, Home, End | menu directions | not mapped |
| Ctrl+F, M, G, O, P, A, S, Q, Ctrl+Shift+P | Ctrl+letter jumps to that letter on the song list | song list functions (below) |

## Shortcut reference

Read 2026-11-14 at tag `v0.75.1` (commit
`2d706147cc4bcf95a8ceb24dc4f4129be207f803`):

- `src/Etterna/Singletons/InputMapper.cpp`, `g_DefaultKeyMappings`: the menu
  buttons and the restart button of every game type.
- `src/Etterna/Singletons/GameManager.cpp`, `g_AutoKeyMappings_Dance`: the
  columns of the game type `dance` (4 keys), which is the default.
- `src/Etterna/Globals/StepMania.cpp`, `HandleGlobalInputs()`: Ctrl+Scroll Lock,
  F2, Pause, Alt+F4, Print Screen, Alt+Enter.
- `src/Etterna/Screen/Others/ScreenSelectMusic.cpp`, `ScreenSelectMusic::Input()`:
  F9 and the song list chords.
- `src/Etterna/Screen/Gameplay/ScreenGameplay.cpp` (restart) and
  `ScreenGameplayPractice.cpp` (Ctrl+Shift+R).
- `src/Etterna/Screen/Others/ScreenSyncOverlay.cpp`: F4, F11, F12.
- `src/Etterna/Screen/Others/ScreenDebugOverlay.cpp` with the key names in
  `[ScreenDebugOverlay]` of `Themes/_fallback/metrics.ini`: F3, Tab, `` ` ``,
  Pause, F6 to F8.

A user who maps a key in the game still sees the default here.

| Key | Source name | Action |
|---|---|---|
| Z, X, `,`, `.` | `DANCE_BUTTON_LEFT`, `DOWN`, `UP`, `RIGHT` | Columns 1 to 4 |
| Enter | `GAME_BUTTON_START` | Start |
| / | `GAME_BUTTON_SELECT` | Select |
| Ctrl+Scroll Lock | `GAME_BUTTON_OPERATOR` with Ctrl | Operator menu (the options) |
| `` ` `` (held) | `GAME_BUTTON_RESTART` | Restart the song |
| F4 | `RevertSyncChanges` | Revert the sync changes (during a song) |
| F6 | `GameplayButton2`, `DebugLineAutosync` | Autosync: off, song, machine (during a song) |
| F7, Shift+F7 | `GameplayButton1`, `DebugLineAssist` | Assist clap, assist metronome (during a song) |
| F8 | `GameplayButton0`, `DebugLineAutoplay` | Autoplay (during a song) |
| F11, F12 | `ChangeSongOffset` | Song offset down, up (during a song) |
| Shift+F11, Shift+F12 | `ChangeGlobalOffset` | Global offset down, up (during a song) |
| F9 | `m_bShowNativeLanguage` | Song list: titles transliterated or in the native script |
| Ctrl+F | `ToggleCurrentFavorite()` | Song list: favorite on or off |
| Ctrl+M | `ToggleCurrentPermamirror()` | Song list: always mirror this chart, on or off |
| Ctrl+G | `GoalFromCurrentChart()` | Song list: add a goal for this chart |
| Ctrl+O | `TogglePracticeMode()` | Song list: practice mode on or off |
| Ctrl+P | `SM_BackFromNamePlaylist` | Song list: name a new playlist |
| Ctrl+A | `AddCurrentChartToActivePlaylist()` | Song list: add the chart to the active playlist |
| Ctrl+S | `SaveProfile()` | Song list: save the profile |
| Ctrl+Q | `DifferentialReload()` | Song list: load new songs from disk |
| Ctrl+Shift+R | `ReloadCurrentSong()` | Reload the selected song from disk (song list and practice mode) |
| Ctrl+Shift+P | `ReloadCurrentPack()` | Song list: reload the selected pack from disk |
| F2, Shift+F2, Ctrl+F2, Ctrl+Shift+F2 | `HandleGlobalInputs()` | Reload metrics and textures; metrics only; scripts; overlay screens |
| F3 (held) | `HoldForDebug1` | Show the debug menu |
| Tab (held) | `HoldForFast` | The game runs 4 times faster |
| Pause | `ToggleMute` | Mute actions on or off |
| Print Screen, Shift+Print Screen | `SaveScreenshot()` | Screenshot as JPEG, as PNG |
| Alt+Enter | `SetToggleWindowed()` | Toggle full screen (not on macOS) |
| Alt+F4 | `SetUserQuit()` | Quit (not on macOS) |

## Other meanings (not drawn)

| Key | Other meaning |
|---|---|
| `` ` `` | held anywhere: the game runs at a quarter of the speed (`HoldForSlow`) |
| Pause | also sends `ToggleConsoleDisplay` to the theme |
| F5 to F8 | while F3 is held: the pages of the debug menu |
| Z, X, `,`, `.` | other game types map other keys; `solo` uses Z X C M `,` `.` |

## Left out

- `=` and `-` (`GAME_BUTTON_EFFECT_UP`, `EFFECT_DOWN`): the engine passes them to
  the theme, and the bundled themes use them differently. In
  `Themes/Rebirth/metrics.ini` they step through the scores, and with Select
  held they change the music rate.
- The keys that only a theme's scripts define (the tabs and search of the
  bundled themes): not in the engine, and different per theme.
- The arrow keys (menu directions): the arrows keep their own legends.
- The keypad (second controller): keypad keys have no cell.
- F1 (`GAME_BUTTON_COIN`): mapped, but `HandleGlobalInputs()` no longer handles
  it.
- F3 held with 1 to 0 and Q to D (the lines of the debug menu): F3 is not a
  modifier with a layer of its own.
- Alt held with F11 and F12 (the same change in steps 20 times smaller).
- Ctrl+Backspace on the song list (delete the song): it needs the preference
  `AllowSongDeletion`, which is off by default (`PrefsManager.cpp`).
- Ctrl+Shift+O (`CachePackForRanking()`) and Ctrl+T (the difficulty calculator's
  test list): functions for development.
- The macOS variants: Cmd+Q, F13 and Cmd+F12 (screenshot).

## Placement

As for StepMania (`../stepmania/SOURCES.md`): every icon sits at the right edge
and uses the full height, F1 to F9 use 34×40 and F11, F12 30×40, and every icon
is drawn at exactly its area, so the generator places it 1:1. The icons on `,`
and `.` cover the shifted symbol of those keys; the firmware clears the legend
within 3 px of the icon.

## ESC mark

ESC shows Etterna's logo, the letter E and the corner cut off it,
38 px high in the centre of the cell, drawn without the ESC legend
(`program_icon_legend: false`, protocol v25). The source is
`Docs/images/etterna-logo-dark.svg` at tag `v0.75.1`; both of its shapes are
lit. `fetch_icons.py` writes `program.png` only when it is missing.

Licence reasoning: the file has no licence of its own, so the project's licence
applies. `LICENSE` is the MIT licence ("Copyright (c) 2016-2023 Etterna"), and
`README.md` says "Etterna uses the MIT License" and "you are free to modify,
sell, distribute, and sublicense this project". MIT is compatible with
GPL-3.0-or-later, the licence of this repository. The mark is used to identify
Etterna; no endorsement is implied.

## Icons

Licence texts:

- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- MIT (Etterna): https://raw.githubusercontent.com/etternagame/etterna/v0.75.1/LICENSE

Where each icon file comes from. The icon table gives the name to put in the
URL.

- Material Symbols (`ms:<name>`), outlined style at weight 300: `https://raw.githubusercontent.com/google/material-design-icons/master/symbols/web/<name>/materialsymbolsoutlined/<name>_wght300_24px.svg` (`RAW` in `../material_symbols.py`; the URL names the `master` branch, not a commit, so a later fetch can return a changed drawing)
- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`
- Etterna's logo (ESC mark): `https://raw.githubusercontent.com/etternagame/etterna/v0.75.1/Docs/images/etterna-logo-dark.svg`

| File | Source | Author | Licence |
|---|---|---|---|
| `colleft.png`, `coldown.png`, `colup.png`, `colright.png` | Font Awesome Free 6.5.2 `circle-left`, `circle-down`, `circle-up`, `circle-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `assist.png` | Font Awesome Free 6.5.2 `hands-clapping` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `metronome.png` | game-icons.net `delapouite/metronome` | delapouite | CC BY 3.0 |
| `start.png`, `select.png`, `operator.png`, `restart.png` | Material Symbols `play_circle`, `menu`, `settings`, `replay` | Google | Apache-2.0 |
| `revertsync.png`, `autosync.png`, `autoplay.png` | Material Symbols `history`, `sync`, `smart_toy` | Google | Apache-2.0 |
| `offsetdown.png`, `offsetup.png` | Material Symbols `schedule`, with a minus or a plus drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `globaldown.png`, `globalup.png` | Material Symbols `public`, with a minus or a plus drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `translit.png`, `favorite.png`, `mirror.png`, `goal.png`, `practice.png` | Material Symbols `translate`, `star`, `flip`, `flag`, `fitness_center` | Google | Apache-2.0 |
| `newplaylist.png`, `addtoplaylist.png`, `saveprofile.png`, `newsongs.png` | Material Symbols `playlist_add`, `queue_music`, `save`, `create_new_folder` | Google | Apache-2.0 |
| `reloadsong.png`, `reloadpack.png` | Material Symbols `audio_file`, `folder_open` | Google | Apache-2.0 |
| `reload.png`, `reloadmetrics.png`, `reloadscripts.png`, `reloadoverlays.png` | Material Symbols `refresh`, `description`, `code`, `layers` | Google | Apache-2.0 |
| `debug.png`, `fast.png`, `mute.png` | Material Symbols `bug_report`, `fast_forward`, `volume_off` | Google | Apache-2.0 |
| `screenshot.png`, `screenshotraw.png`, `fullscreen.png`, `quit.png` | Material Symbols `photo_camera`, `high_quality`, `fullscreen`, `power_settings_new` | Google | Apache-2.0 |
| `program.png` | Etterna's logo, `Docs/images/etterna-logo-dark.svg` | the Etterna team | MIT |
