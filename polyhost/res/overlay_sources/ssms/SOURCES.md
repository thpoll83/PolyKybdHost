# SQL Server Management Studio overlay sources

`bindings.yaml` generates one artwork set, `ssms_template.*`, for SQL Server
Management Studio (SSMS) on Windows. SSMS exists only for Windows, so there is
no macOS or Linux set. 66 keys plus the ESC mark, on two tiers (`.mods`,
`.combo.mods`).

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/ssms/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/ssms/bindings.yaml --preview /tmp/ssms_preview
```

## Process name

The mapping entry is `ssms`. The executable is `Ssms.exe` in SSMS 18 to 20 and
`SSMS.exe` in SSMS 21 and later; the Windows window handler strips `.exe` and
lowercases, so both are `ssms`. The name was not checked on an install.

## Shortcut source

Microsoft Learn, "SQL Server Management Studio Keyboard Shortcuts" (default
keyboard scheme):
<https://learn.microsoft.com/ssms/sql-server-management-studio-keyboard-shortcuts>
(`ms.date: 10/30/2025`, page source
`MicrosoftDocs/data-tools/main/ssms/sql-server-management-studio-keyboard-shortcuts.md`),
read on 2026-11-05. Every drawn chord appears on that page.

- **F5** is Execute in the query editor. In Activity Monitor and Replication
  Monitor the same key is Refresh; the overlay draws the query editor meaning.
- **F6** toggles between the query editor and the results pane. In Object
  Explorer Details and Activity Monitor it moves between panes, which the same
  icon also describes.
- **Alt+F1, Ctrl+1, Ctrl+2** run `sp_help`, `sp_who` and `sp_lock`. They are the
  default Query Shortcuts (Tools > Options > Environment > Keyboard > Query
  Shortcuts), so a user who changed that page sees the wrong icon.
- **Ctrl+R** (show or hide the results pane) is on the page. One user reports on
  Microsoft Q&A that it and Ctrl+E did nothing after installing SSMS 21.1
  (<https://learn.microsoft.com/answers/a/1539969>). It is drawn because the
  current page lists it.

## Icons

- **Fetched (48)**: Microsoft Fluent UI System Icons (MIT,
  github.com/microsoft/fluentui-system-icons) or Google Material Symbols
  (Apache-2.0, fonts.google.com/icons). Each binding's `source:` and
  `fetch_icons.py` name the glyph. Both licences are compatible with this repo's
  GPL-3.0-or-later.
- **Shared with `../visualstudio`**: where SSMS has the same command as Visual
  Studio (new project, add new item, Solution Explorer, Properties, Output,
  next document, save all, navigate backward/forward, replace in files,
  clipboard ring, open line above/below, move line down, rename), the glyph is
  the same Fluent or Material glyph that `../visualstudio/fetch_icons.py` uses.
  The results pane and pane toggle use the glyphs of `../dbeaver` (Panel Bottom,
  `swap_vert`).
- **Shared concepts** (drawn by the shared renderer, no icon file): New (Ctrl+Alt+N,
  new file), Open, Save, Print, Close, Fullscreen, Undo, Redo, Cut, Copy, Paste,
  Select all, Go to, Find, Replace, Find next, Help.
- **ESC mark (`ssms.png`)**: drawn in `fetch_icons.draw_mark()`, a database
  cylinder, white on transparent. Microsoft's SSMS icon is proprietary and may
  not be redistributed, so the set ships this substitute. It is a committed
  asset: `fetch_icons.py` draws it only when the file is missing, so a hand
  edit is kept.

## Deliberately not drawn

- **Two-stroke chords** cannot be drawn on one keycap, as in `../visualstudio`:
  Ctrl+K, Ctrl+C / Ctrl+K, Ctrl+U (comment / uncomment), Ctrl+K, Ctrl+K and the
  other Ctrl+K bookmark chords, Ctrl+K, Ctrl+X / Ctrl+K, Ctrl+S / Ctrl+K, Ctrl+B
  (snippets), Ctrl+K, Ctrl+\\ (delete whitespace), Ctrl+K, Ctrl+W (Bookmarks
  window), Ctrl+K, Ctrl+A (swap anchor), Ctrl+M, Ctrl+M / Ctrl+M, Ctrl+L /
  Ctrl+M, Ctrl+P (outlining), Ctrl+B, Ctrl+I (IntelliSense on/off),
  Ctrl+\\, Ctrl+T (Task List) and Ctrl+\\, Ctrl+E (Error List). The page lists
  no single-stroke comment shortcut.
- **Ctrl+E (execute)** is not on the current page. The SQL Server 2012 version
  of the page lists it only in the SQL Server 2008 R2 keyboard scheme
  (<https://learn.microsoft.com/previous-versions/sql/sql-server-2012/ms174205(v=sql.110)>),
  and a Microsoft Q&A report says it does not work in SSMS 21.1. F5 is drawn.
- **Alt+Break** (cancel the query) is on the Pause/Break key, which has no
  keycap cell.
- Left out to keep the set to commands a user acts on: cursor movement and
  text selection with the arrow keys, Home, End and Page Up/Down; Shift+F3
  (find previous, no matching shared concept); Ctrl+= (select to the previous
  location); Ctrl+Up/Down (scroll); Ctrl+Backspace / Ctrl+Delete (delete word);
  Shift+Alt+A (add existing item); Ctrl+J (list members); Shift+F10 (context
  menu); Ctrl+Alt+Down, Alt+F7, Alt+F6, Ctrl+F6 (window navigators);
  Shift+Esc (close tool window); Alt+F4 (exit); Ctrl+F2 (dropdown bar);
  Ctrl+Alt+F1 and Ctrl+Alt+F2 (Help Library Manager, Resource Center); the
  browser window's Alt+Left/Right; and the Query Designer pane toggles
  (Ctrl+1, Ctrl+2, Ctrl+3 in the Query Designer only, where Ctrl+1 and Ctrl+2
  are the query editor's `sp_who` and `sp_lock`).
