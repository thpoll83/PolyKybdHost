# OBS Studio overlays — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Keys | Loads for |
|---|---|---|
| `obs_template` (2 files) | 23 | `obs64.exe` on Windows |
| `obs_template_linux` (2 files) | 24 | `obs` or `com.obsproject.studio` on Linux |
| `obs_template_mac` (3 files) | 26 | "OBS" or "OBS Studio" on macOS |

App names come from the OBS source, not from an install:

- Windows and Linux: `OUTPUT_NAME "$<IF:$<PLATFORM_ID:Windows>,obs64,obs>"` in
  `frontend/CMakeLists.txt`. The Linux desktop file
  `frontend/cmake/linux/com.obsproject.Studio.desktop` has `Exec=obs` and
  `StartupWMClass=obs`. The Flatpak app id is `com.obsproject.Studio`.
- macOS: `cmake/macos/helpers.cmake` builds `OBS.app` with `PRODUCT_NAME OBS`
  and `CFBundleDisplayName "OBS Studio"`. Which of the two the window handler
  reports was not checked, so both are mapping keys.

## Shortcut reference

OBS Studio is GPL-2.0-or-later (<https://github.com/obsproject/obs-studio>,
`master` branch, read 2026-11-05).

OBS hotkeys (start and stop recording or streaming, switch scene, mute a
source, Studio Mode transition) have no default key. The user assigns them in
Settings > Hotkeys, and `frontend/widgets/OBSBasic_Hotkeys.cpp` loads only
saved bindings. So the set draws only the keys OBS sets itself:

- `frontend/forms/OBSBasic.ui`: Copy (Ctrl+C), Paste (Reference) (Ctrl+V),
  Fullscreen Interface (F11), Remove (Del) on the scene and source lists, and
  the Edit > Transform and Edit > Order menus: Edit Transform (Ctrl+E), Copy
  Transform (Ctrl+Shift+C), Paste Transform (Ctrl+Shift+V), Fit to screen
  (Ctrl+F), Stretch to screen (Ctrl+S), Reset Transform (Ctrl+R), Center to
  screen (Ctrl+D), Move Up / Down / to Top / to Bottom (Ctrl+Up / Down / Home /
  End).
- `frontend/widgets/OBSBasic.cpp`, `OBSBasic::OBSInit`: Undo (Ctrl+Z), Redo
  (Ctrl+Shift+Z and Ctrl+Y), Rename (F2, Return on macOS), Remove also on
  Backspace on macOS, Exit (Ctrl+Q, Linux only), and the preview nudge keys
  (arrows 1 px, Shift+arrows 10 px).

Qt spells the Cmd key "Ctrl" on macOS, so every Ctrl key is `CMDCTRL`. On macOS
OBS deletes its Exit action and gives Settings the preferences menu role, so
Qt's application menu provides Quit (Cmd+Q) and Settings (Cmd+,).

The menu labels are the English strings in `frontend/data/locale/en-US.ini`.

### Choices

- Ctrl+S and Ctrl+F are Stretch to screen and Fit to screen. They do not save
  or search.
- Ctrl+C, Ctrl+V, Del and Ctrl+Up/Down also copy, paste, remove and move
  filters in the Filters window (`frontend/dialogs/OBSBasicFilters.cpp`,
  `frontend/forms/OBSBasicFilters.ui`). The keys show the main-window action.
- The Shift+arrow keys nudge the selected source by 10 px while the preview
  has focus.

### Left out

- Plain arrow keys (nudge 1 px): the key legend is already an arrow, so an
  arrow icon adds nothing.
- Esc (leave a fullscreen projector, `frontend/widgets/OBSProjector.cpp`): the
  ESC cell shows the program mark.
- Space (hold to pan the preview, `frontend/widgets/OBSBasicPreview.cpp`): only
  with a fixed preview scale, and it is a hold, not a command.
- All OBS hotkeys: no default key (see above).

## Icons

| File | Source | Licence |
|---|---|---|
| `undo`, `redo`, `copysource`, `pasteref`, `remove`, `rename`, `copytransform`, `pastetransform`, `resettransform`, `stretchscreen`, `moveup`, `movedown`, `movetop`, `movebottom`, `fullscreen`, `settings`, `quit` | Microsoft Fluent UI System Icons (<https://github.com/microsoft/fluentui-system-icons>), names in `fetch_icons.py` | MIT |
| `edittransform`, `fitscreen`, `centerscreen`, `nudgeleft`, `nudgeright`, `nudgeup`, `nudgedown` | Material Symbols (<https://github.com/google/material-design-icons>) | Apache-2.0 |
| `obs.png` (ESC mark) | Simple Icons `obsstudio` (<https://github.com/simple-icons/simple-icons>) | CC0-1.0 artwork; trademark used nominatively to name the app |
