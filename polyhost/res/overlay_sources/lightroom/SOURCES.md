# Adobe Lightroom Classic overlays — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `lightroom_template` (3 files), `_mac` (4 files) | Lightroom Classic: `Lightroom.exe` on Windows, "Adobe Lightroom Classic" on macOS |

The names were not checked on an install. On Windows, Lightroom Classic
(`C:\Program Files\Adobe\Adobe Lightroom Classic\Lightroom.exe`) and the cloud
app Lightroom (`...\Adobe Lightroom\lightroom.exe`) both report `lightroom`,
and the cloud app has other keys. The mapping entry therefore gates the Windows
set on a window title containing "Lightroom Classic" (Classic's title is
"<catalog> - Adobe Photoshop Lightroom Classic - <module>"). The macOS names
differ ("Adobe Lightroom Classic" and "Adobe Lightroom"), so macOS needs no gate.

## Shortcut reference

Adobe Help, "Keyboard shortcuts" for Lightroom Classic (last updated
2025-10-29),
<https://helpx.adobe.com/lightroom-classic/desktop/introduction-to-lightroom-classic/keyboard-shortcuts.html>,
read 2026-10-22 with headless Chromium (the page refuses an automated browser
without a desktop user agent). It has a Windows and a macOS column. macOS uses
Cmd for Ctrl and Option for Alt, so the spec writes CMDCTRL. The keys that
differ are written twice:

| Action | Windows | macOS |
|---|---|---|
| Open catalog | Ctrl+O | ⌘⇧O |
| Redo | Ctrl+Y or Ctrl+Shift+Z | ⌘⇧Z only |
| HDR merge, panorama merge, Enhance | Ctrl+H, Ctrl+M, Ctrl+Alt+I | ⌃H, ⌃M, ⌃⌥I |

Bare letters and digits are drawn, as in the Photoshop set: Lightroom uses them
for views, tools, flags, ratings and labels, and typing happens in panel fields.

### One meaning per key

Lightroom gives several keys a different meaning per module. The set shows:

| Key | Shown | Other meanings |
|---|---|---|
| J | Show clipping (Develop) | Cycle Grid views (Library) |
| Ctrl+E | Edit in Photoshop | Multi-page view (Book) |
| Ctrl+R | Show in Explorer/Finder | Double page view (Book), Rulers (Print), Reload (Web) |
| Ctrl+J | View options (Library, Develop) | Export PDF slide show, Export web gallery |
| Ctrl+U | Auto tone (Develop) | Zoomed single page (Book) |
| Ctrl+S | Save metadata (Library) | Create saved book, save template settings |
| Ctrl+Shift+C / V | Copy / paste Develop settings | Copy / paste book layout |

### Left out

- Keys with three or more module meanings: S, O, H, `[`, `]`, `\`, Ctrl+N,
  Ctrl+Shift+N, Ctrl+Shift+H, Ctrl+Alt+R.
- Mouse actions (Alt-click, Shift-drag), arrows, Page Up/Down, Home/End, Enter,
  Esc, Spacebar, F5 (module picker), F11, F12, Shift+Tab.
- Ctrl+1..9 (panels), Ctrl+Shift+0..5, the Book, Map, Slideshow, Print and Web
  module keys, the Targeted Adjustment keys (Ctrl+Alt+Shift+T/H/S/L/G/N), Shift
  plus a digit, Alt+1..9 keyword sets, and the macOS-only spelling keys.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- `star1..star5.png` (Fluent `Star` with a digit) and `labelR/Y/G/B.png`
  (Fluent `Tag` with a letter), from `../number_badge.py`.
- Undo, Redo, Select all, Zoom in and Zoom out are drawn by the shared concept
  renderer.
- ESC: a generic "Lr" rectangle from `../rect_mark.py`, at the size of the
  other Adobe marks. Adobe's logo is not used.
