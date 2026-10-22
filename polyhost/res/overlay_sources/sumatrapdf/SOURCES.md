# SumatraPDF overlay — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `sumatrapdf_template` (2 files) | `SumatraPDF.exe` on Windows (installer and portable builds) |

SumatraPDF runs only on Windows, so there is no macOS or Linux set. The app name
was not checked on an install.

## Shortcut reference

SumatraPDF documentation, "Keyboard shortcuts",
<https://www.sumatrapdfreader.org/docs/Keyboard-shortcuts>, read 2026-10-22 with
headless Chromium. The page lists the default keys by menu and notes the version
that added some of them (F7 keyboard text selection 3.7+, undo/redo 3.7+). Users
can rebind keys in the advanced settings; the set shows the defaults.

59 keys: file (Ctrl+N/O/W/S/P/D/Q, Ctrl+Shift+S/N, F2), navigation (Ctrl+G,
Alt+Left/Right, Ctrl+Up/Down, Ctrl+Shift+Left/Right, Ctrl+F, F3, Shift+F3,
Ctrl+B), view and zoom (Ctrl+6/7/8, Ctrl+Shift+- / +, Ctrl+0/1/2/3, Ctrl+Y,
Ctrl+L and F5 presentation, Ctrl+Shift+L and F11 full screen, F12, Shift+F12,
F8, F9, F7), edit (Ctrl+A/C/Z, Ctrl+Shift+Z), Ctrl+K command palette, F1 manual
and the tab keys (Ctrl+Tab, Ctrl+Shift+Tab, Ctrl+Page Down/Up, Alt+1..8, Alt+9).
Ctrl+Shift++ (rotate right) is drawn on the `=` key, where the `+` sits.

## Left out

- Single letters and Shift+letter keys (j, k, h, l, n, p, g, b, z, c, i, m, r,
  q, a, u, w, `.`, Shift+I, Shift+A, Shift+U) and the command-palette prefix
  characters (`>`, `@`, `#`, `$`, `%`, `&`, `=`): they would replace the letter
  legends, and they act only while the page has focus.
- Plain `[` / `]` and the numeric-keypad `/` and `*` (rotate): no modifier.
- Keys with no overlay cell: the arrows alone, Page Up/Down, Home, End, Space,
  Shift+Space, Esc, Delete.
- Ctrl+F4 and Alt+F4 (close; Ctrl+W is drawn), Shift+F11 (a second
  presentation key), F6 (focus between bookmarks and page), Ctrl+X (cut an
  annotation; acts only on the annotation under the mouse).

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- `tab1.png`..`tab9.png`: borrowed unchanged from `../winscp/icons` (Fluent
  `Tab` with a digit).
- Open, Print, Find, Select all, Copy, Undo and Redo are drawn by the shared
  concept renderer.
- ESC: the generic program mark (the OS icon of SumatraPDF.exe).
