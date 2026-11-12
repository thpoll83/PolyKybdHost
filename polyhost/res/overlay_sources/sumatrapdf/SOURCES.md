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

59 keys with a modifier or a function key: file (Ctrl+N/O/W/S/P/D/Q, Ctrl+Shift+S/N, F2), navigation (Ctrl+G,
Alt+Left/Right, Ctrl+Up/Down, Ctrl+Shift+Left/Right, Ctrl+F, F3, Shift+F3,
Ctrl+B), view and zoom (Ctrl+6/7/8, Ctrl+Shift+- / +, Ctrl+0/1/2/3, Ctrl+Y,
Ctrl+L and F5 presentation, Ctrl+Shift+L and F11 full screen, F12, Shift+F12,
F8, F9, F7), edit (Ctrl+A/C/Z, Ctrl+Shift+Z), Ctrl+K command palette, F1 manual
and the tab keys (Ctrl+Tab, Ctrl+Shift+Tab, Ctrl+Page Down/Up, Alt+1..8, Alt+9).
Ctrl+Tab and Ctrl+Shift+Tab are Smart Tab Switch: with three or more tabs they go
in most-recently-used order, so they show a history icon, not the tab-strip arrows
of Ctrl+Page Down/Up.
Ctrl+Shift++ (rotate right) is drawn on the `=` key, where the `+` sits.

23 single keys and Shift+letter keys, from the page's Navigation, Viewing state,
Actions and Annotations sections. They act while the document has focus, which
is the normal state: J / K scroll down / up, H / L scroll left / right, N / P
next / previous page, G go to page, B flip page in book mode, Z cycle zoom, C
continuous / single page, F full screen, I page info and Shift+I invert colors
(3.6+; 3.5.2 and earlier swap them), M cursor position, R reload, Q close tab, `/`
find, `[` / `]` rotate left / right, A highlight and U underline the selection,
and Shift+A / Shift+U the same with Edit PDF mode on. The firmware draws the icon
beside the letter legend, so the legend stays readable. The page lists "j / k"
as "Scroll up / down"; the set follows the vi meaning (J down, K up), which was
not checked in the app.

## Left out

- W and `.` (white and black screen): they act only in presentation mode.
- The command-palette prefix characters (`>`, `@`, `#`, `$`, `%`, `&`, `=`): they
  are typed into the palette, not pressed in the document.
- `+` and `-` alone (zoom): the key that types `+` depends on the layout.
- The numeric-keypad `/` and `*` (rotate): the keyboard has no keypad.
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
