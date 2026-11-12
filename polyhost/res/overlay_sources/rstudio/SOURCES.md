# RStudio overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table;
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Loads for |
|---|---|
| `rstudio_template` (3 files), `_mac` (4 files) | the RStudio desktop app on Windows, Linux and macOS |

App names: the RStudio 2026.10.0+233 Linux package (`rstudio-latest-amd64.deb`
for Ubuntu 22.04, run under Xvfb on 2026-10-22) runs as `rstudio`, with
WM_CLASS `rstudio` / `Rstudio`. Windows (`rstudio.exe`) and macOS ("RStudio")
were not checked on an install. RStudio Server in a browser is not routed.

## Shortcut reference

Posit, RStudio User Guide, "Keyboard Shortcuts" (release 2026.10.0),
<https://docs.posit.co/ide/user/ide/reference/shortcuts.html>, read 2026-10-22
with headless Chromium. Its "Windows & Linux" and "Mac" columns; where a row
gives a desktop and a browser variant, the set uses the desktop key.

### Left out

- Browser-only variants (the Chrome and Firefox rows), the RStudio Server menu
  keys (Alt+Shift+letter), and desktop keys the system owns (Ctrl+Q / Cmd+Q).
- Find next and Find previous on Windows/Linux: the page gives F3 / Shift+F3 on
  Windows and Ctrl+G / Ctrl+Shift+G on Linux, and the two share one set. macOS
  has ⌘G / ⇧⌘G.
- Ctrl+Up / Cmd+Up (popup command history): the editing table gives the same
  key "Jump to start", so it is not drawn.
- Keys with no overlay cell or that act only in one dialog: Tab, Shift+Tab, Esc,
  Enter, Space, the plain and Shift+arrow keys, Home, End, Page Up/Down, F6.
- The accessibility keys (Alt+Shift+/, Alt+Shift+1, Alt+Shift+2, Alt+Shift+[,
  Alt+Shift+Y) and the help-topic keys (Alt+Shift+F2/F3).
- The second key of a pair: Ctrl+F11/F12 (tabs, the set draws Ctrl+Alt+Left/
  Right), Ctrl+Shift+PageUp/PageDown (plots), Ctrl+Shift+F11/F12 (first and
  last tab), Ctrl+` (console focus), Ctrl+Space (completion).
- The Mac-only Emacs-style editing keys (Ctrl+K,
  Ctrl+U, Ctrl+Y, Ctrl+T).

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- `zoom1..9.png` (Ctrl+Shift+1..9, zoom a pane): Material `fullscreen` with a
  digit, from `../number_badge.py`.
- `assign.png` and `pipe.png`: the operators `<-` and `|>`, drawn in DejaVu Sans
  Mono Bold (Bitstream Vera licence) by `fetch_icons.py`.
- Open, Save, Close, Undo, Redo, Cut, Copy, Paste, Select all and Find are drawn
  by the shared concept renderer.
- ESC: the RStudio logo from Simple Icons (`rstudioide`, CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
