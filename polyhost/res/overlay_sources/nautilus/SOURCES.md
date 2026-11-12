# GNOME Files (Nautilus) overlay sources

## Shortcuts

Nautilus 46.4 (the version Ubuntu 24.04 ships), read from its source at tag
`gnome-46` of https://github.com/GNOME/nautilus (mirror of gitlab.gnome.org/GNOME/nautilus):

- `src/resources/gtk/help-overlay.ui`: the shortcuts window (Ctrl+?).
- `src/nautilus-application.c`: Ctrl+N, F1, Ctrl+Q, Ctrl+, (app actions).
- `src/nautilus-window.c`: tab, navigation, location and reload accelerators.
- `src/nautilus-files-view.c`: per-view bindings (F2, Del, Shift+Del, Ctrl+I,
  Alt+Enter, Ctrl+M, Ctrl+Shift+M, Ctrl+Enter, Shift+Enter, Ctrl+Alt+O, zoom,
  Ctrl+H, Ctrl+S, Ctrl+Shift+N, Ctrl+V).

Left out: Alt+0..8 (open tab N, the digit is already the key legend) and `~`
(location bar at home), whose physical key depends on the layout. Ctrl+? is
drawn on Ctrl+Shift+/, its US position.

## Icons

| file | source | licence |
|---|---|---|
| `nautilus.png` (ESC program mark) | `data/icons/hicolor/symbolic/apps/org.gnome.Nautilus-symbolic.svg`, GNOME/nautilus `gnome-46` | GPL-3.0-or-later (Nautilus) |
| `listview.png`, `gridview.png` | Material Symbols `view_list`, `grid_view` | Apache-2.0 |
| every other `icons/*.png` | Microsoft Fluent UI System Icons, folder named in `fetch_icons.py` | MIT |

Copy, Cut, Paste, Undo, Redo, Select all and Reload are drawn by the shared
concept renderer and have no file here.

The full-colour `org.gnome.Nautilus.svg` (CC-BY-SA 4.0) was not used: its
gradient shading smears at 1 bit and 40 px, while the symbolic icon is drawn
for one colour.
