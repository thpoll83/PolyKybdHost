# VLC media player overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table, and
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Loads for |
|---|---|
| `vlc_template` (2 files) | Windows (`vlc.exe`) and Linux (`vlc`) |
| `vlc_template_mac` (4 files) | macOS ("VLC") |

App names: the VLC 3.0.20 Ubuntu package, run under Xvfb on 2026-10-22, runs
as `vlc`, with WM_CLASS `vlc` and the window title "VLC media player". The
Windows and macOS names were not checked on an install.

## Shortcut references

VLC 3.0.x source code, branch `3.0.x` of <https://github.com/videolan/vlc>,
read 2026-10-22:

- `src/libvlc-module.c`: the default hotkey table, one block for macOS and one
  for Windows and Linux. These keys act in the video window.
- `modules/gui/qt/menus.cpp`: the menu keys of the Qt interface (Windows and
  Linux).
- `modules/gui/macosx/UI/MainMenu.xib` and `VLCMainMenu.m`: the macOS menu
  keys. `VLCMainMenu.m` replaces 15 of the menu keys at start with the hotkey
  values (quit, stop, previous, next, the short jumps, volume, mute, full
  screen, snapshot, shuffle and the three zoom sizes); the set shows those
  values.

Windows and Linux share one key table, except that Linux also binds the media
keys, which have no overlay cell.

## Single keys

The single-key hotkeys of `src/libvlc-module.c` act in the main window and the
video window, so the set draws them (the `ROWS +=` block in `gen_specs.py`).
The icon is drawn beside the key's own letter, which stays readable.

| Platform | Keys |
|---|---|
| Windows, Linux | F, `-`, `=`, `]`, `[`, N, P, S, T, E, R, L, M, B, K, J, V, H, G, A, C, O, D, I, Z, W, X; Shift+R, M, O, B, P, N, A, V, H, J, K, S, D, Z, X |
| macOS | T, E, L, G, F, S, J, H, A, C, O, D, I, Z, X; Shift+L, A, S, H, J, K, D, Z, X |

The macOS table moves some keys: L is the audio track, S the subtitle track,
G and F the audio delay, J and H the subtitle delay, and Shift+L the loop.

## Left out

- Space (play / pause), Esc, Enter, the arrows alone, Page Up and Page Down
  (360° field of view), and the media keys: they have no overlay cell, or they
  only navigate.
- `+` (faster) on Windows and Linux: which key types `+` depends on the
  layout. `-` (slower) and `=` (normal speed) are drawn.
- F1..F10 alone (play bookmark): on Windows and Linux F1 is also Help in the
  menu, so the plain F keys are not drawn on any platform. Ctrl+F1..F10
  (Cmd+F1..F8 on macOS), set bookmark, are drawn; bookmark 10 shows "0".
- Ctrl+1..9 (open a recent file): the list changes with use.
- Ctrl+Shift+W (VLM configuration, only in builds with VLM) and Ctrl+Shift+S
  (skins, only in the skins interface).
- Alt+V (previous subtitle track): Alt+V also opens the Video menu.
- Mouse-wheel keys (subtitle text size).
- macOS: Cmd+R (the menu gives it to both Open Capture Device and Repeat Item),
  the hotkey Cmd+Shift+R for Record (the menu gives it to Reveal in Finder; the
  menu's Record is Cmd+Option+R), the hotkey Cmd+0 for subtitle size (the menu
  gives it to Half Size), Option+letter crop and scale keys, Cmd+Q, Cmd+H,
  Cmd+M, Cmd+W and Cmd+Shift+Z (system keys).

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- `subdelayup`, `subdelaydown`, `audiodelayup`, `audiodelaydown`: Material
  `subtitles` or `music_note` with `arrow_upward` or `arrow_downward`, composed
  by `delay_icons()` in `fetch_icons.py`.
- `setbm0..setbm9.png`: Fluent `Bookmark` with a digit, from
  `../number_badge.py`.
- Quit, Settings, Bookmarks, Find and Help are drawn by the shared concept
  renderer.
- ESC: the VLC cone from Simple Icons (CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
