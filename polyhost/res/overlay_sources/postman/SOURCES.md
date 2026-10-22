# Postman overlays — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `postman_template` (2 files), `_mac` (3 files) | `Postman.exe` on Windows, `postman` on Linux, "Postman" on macOS |

App names: the Linux build 12.33.3 (`linux_64` tarball, run under Xvfb on
2026-10-22) shows its window from a process named `postman` (the launcher is
`Postman`), with WM_CLASS `postman` / `Postman` and the title "Postman API
Platform". The Windows and macOS names were not checked on an install.

## Shortcut reference

Postman's docs page "Shortcuts"
(<https://learning.postman.com/docs/getting-started/installation/settings/shortcut-settings>,
read 2026-10-22) describes the Shortcuts tab in Settings but no longer lists the
keys. The keys therefore come from the app itself, version 12.33.3:

- the default shortcut table in `resources/app/js/scratchpad/scratchpad.js`
  (entries `{name, label, shortcut, keyLabel, keyLabelDarwin}`; `mod+` is Ctrl
  on Windows/Linux and Cmd on macOS);
- the menu accelerators in `resources/app/main.js` (`CmdOrCtrl+…`), which add
  the console (Ctrl+Alt+C), the sidebars (Ctrl+Alt+\, Ctrl+Alt+S), the
  workbench (Ctrl+Alt+M), reset layout (Ctrl+Alt+R), close window
  (Ctrl+Shift+W) and the developer tools.

Users can change the keys in Settings -> Shortcuts; the set shows the defaults.

### Choices

- Ctrl+F is listed for "Search Sidebar" and for "Search Console"; it is drawn
  as Find.
- Next and previous tab: Windows/Linux get Ctrl+Tab and Ctrl+Shift+Tab, macOS
  ⇧⌘] and ⇧⌘[. The app accepts both forms on every platform; ⌘Tab belongs to
  macOS.

### Left out

- Keys without a modifier or a cell: Enter, Esc, Tab, Space, the arrow keys,
  Delete (delete item), Shift+arrows (multi-select).
- Ctrl+Shift+L, a second Request URL key that the web app uses.
- Cut, Copy, Paste, Undo, Redo and Paste as plain text: the standard editing
  keys.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- `tab1..tab8.png`: Fluent `Tab` with a digit, from `../number_badge.py`.
- Save, Find, New, Settings, Zoom in and Zoom out are drawn by the shared concept
  renderer.
- ESC: the Postman mark from Simple Icons (CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
