# GarageBand overlay — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `garageband_template_mac` (4 files) | GarageBand on macOS |

GarageBand is a macOS app, so every binding is `only: [macos]` and no Windows
set is written; the mapping entry's top-level overlay is the macOS set, as for
Safari. App name: "GarageBand" (the bundle name). Not checked on an install.
On macOS the host also reads every menu shortcut of the focused app, and those
fill each key this set leaves free.

## Shortcut reference

Apple, GarageBand User Guide for Mac, "Main window shortcuts in GarageBand on
Mac", <https://support.apple.com/guide/garageband/gbnd58362a62/mac>, read
2026-11-12 (the page's tables: Projects, Tracks, Transports, Modes, Windows,
Editing). Command is GUI, Option is ALT, Control is CTRL. Apple's "Delete" is the
key labelled delete on a Mac keyboard (Backspace), and "Return" is Enter.

### Left out

- Numeric keypad keys (no cell): Enter (play), 0 (stop), * (record).
- Scrolling with fn or Page Up/Down/Home/End, the locator moves by a cycle
  length (Option-Shift-Command-Period/Comma), Tab and Shift-Tab (focus),
  Option-Command-Delete (cut the Arrangement Marker).
- Shift-Command-Period/Comma appear twice on the page ("Move the cycle range" and
  "Move locators"); they are drawn once.
- The macOS window keys: Command-H, Option-Command-H, Command-M,
  Option-Command-M, Control-Command-M.
- Esc: the ESC key shows the program mark, which the host draws.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>: `nextpatch`,
  `prevpatch` (Arrow Next / Previous), `library` (Library).
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: every `ms:`
  entry in `fetch_icons.py`.
- Byte-identical copies of the icons another DAW set draws for the same
  action (`BORROW` in `fetch_icons.py`), from `../ableton`, `../reaper`,
  `../flstudio`, `../protools`, `../soundcraft` and `../cubase`. Their sources
  and licences are in those folders' `SOURCES.md`.
- New, Open, Save, Save as, Close, Quit, Undo, Redo, Cut, Copy, Paste, Select
  all, Delete, Help, Zoom in and Zoom out are drawn by the shared concept
  renderer.

**ESC mark.** None is baked in. GarageBand is proprietary Apple software, so
the host draws the mark for the running app (the icon from its bundle first,
then the icon catalogs; neither Simple Icons nor Material Design Icons has a
GarageBand mark).
