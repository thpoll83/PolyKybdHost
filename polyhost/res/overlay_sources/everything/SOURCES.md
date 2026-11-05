# Everything (voidtools) overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/everything/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/everything/everything.yaml --preview /tmp/everything_preview
```

Both steps are deterministic. A second run leaves every PNG byte-identical.

## Shortcuts

voidtools' own list: "Keyboard Shortcuts" in the Everything support pages,
<https://www.voidtools.com/support/everything/keyboard_shortcuts/> (read
2026-11-05). The page has three groups: search edit, result list, and global
(any Everything search window). The overlay draws 71 keys plus the ESC mark.

Notes on the keys that are drawn:

- `Ctrl++` and `Ctrl+Alt++` are drawn on the `=` key, the `+` key of a US
  layout. In the result list `Ctrl++` also adjusts the column widths; the
  overlay shows the global meaning, "Increase text size".
- `F3`, `Ctrl+F` and `Alt+D` all focus the search box and use one icon.
- `Ctrl+H`, `Ctrl+Shift+H`, `Alt+Up` and `Alt+Down` all show the search
  history and use one icon.

Left out:

- `Esc` (close the window): the ESC cell holds the program mark.
- Keys that only move the cursor or the selection: arrow keys, `Page Up`,
  `Page Down`, `Home`, `End` with or without `Shift` and `Ctrl`,
  `Ctrl+Left/Right` (scroll one page), `Space`, `Ctrl+Space`, `Backspace` and
  letters (the jump-to text), `Enter` (open) and `Ctrl+Backspace` in the
  search box.
- Hotkeys the user sets in Options. Everything has no default global hotkey.

## Icons

| file | art | licence |
|---|---|---|
| `rename.png` | Fluent `Rename` | MIT |
| `reload.png` | Fluent `Arrow Sync` | MIT |
| `props.png` | Fluent `Document Settings` | MIT |
| `switchfocus.png` | Fluent `Arrow Swap` | MIT |
| `contextmenu.png` | Fluent `Navigation` | MIT |
| `deleteperm.png` | Fluent `Delete Dismiss` | MIT |
| `copypath.png` | Fluent `Clipboard Letter` | MIT |
| `openpath.png` | Fluent `Folder Open` | MIT |
| `readinfo.png` | Fluent `Document Search` | MIT |
| `sortname.png` | Fluent `Text Sort Ascending` | MIT |
| `sortpath.png` | Fluent `Folder` | MIT |
| `sortsize.png` | Fluent `Data Bar Vertical` | MIT |
| `sortext.png` | Fluent `Document` | MIT |
| `sorttype.png` | Fluent `Shapes` | MIT |
| `sortmod.png` | Fluent `Calendar Edit` | MIT |
| `sortcreated.png` | Fluent `Calendar Add` | MIT |
| `sortattr.png` | Fluent `Tag` | MIT |
| `sortchanged.png` | Fluent `Calendar Clock` | MIT |
| `matchcase.png` | Material Symbols `match_case` | Apache-2.0 |
| `matchword.png` | Material Symbols `match_word` | Apache-2.0 |
| `regex.png` | Material Symbols `regular_expression` | Apache-2.0 |
| `matchpath.png` | Fluent `Folder Search` | MIT |
| `search.png` | Fluent `Search` | MIT |
| `newwindow.png` | Fluent `Window New` | MIT |
| `filelist.png` | Fluent `Document Bullet List` | MIT |
| `options.png` | Fluent `Settings` | MIT |
| `exit.png` | Fluent `Power` | MIT |
| `export.png` | Fluent `Document Arrow Right` | MIT |
| `ontop.png` | Fluent `Pin` | MIT |
| `bookmark.png` | Fluent `Bookmark Add` | MIT |
| `bookmarks.png` | Fluent `Bookmark Multiple` | MIT |
| `filters.png` | Fluent `Filter` | MIT |
| `history.png` | Fluent `History` | MIT |
| `home.png` | Fluent `Home` | MIT |
| `back.png` | Fluent `Arrow Left` | MIT |
| `forward.png` | Fluent `Arrow Right` | MIT |
| `fullscreen.png` | Fluent `Full Screen Maximize` | MIT |
| `preview.png` | Fluent `Panel Right` | MIT |
| `autosize.png` | Fluent `Arrow Autofit Content` | MIT |
| `details.png` | Fluent `Document Table` | MIT |
| `textbigger.png` | Fluent `Font Increase` | MIT |
| `textsmaller.png` | Fluent `Font Decrease` | MIT |
| `textreset.png` | Fluent `Text Font Size` | MIT |
| `thumbbigger.png` | Fluent `Arrow Maximize` | MIT |
| `thumbsmaller.png` | Fluent `Arrow Minimize` | MIT |
| `nextwindow.png` | Fluent `Arrow Next` | MIT |
| `prevwindow.png` | Fluent `Arrow Previous` | MIT |
| `debug.png` | Fluent `Bug` | MIT |
| `about.png` | Fluent `Info` | MIT |
| `size512.png`, `size640.png`, `size768.png` | drawn in `fetch_icons.py` (Liberation Sans Bold, SIL OFL 1.1) | this repo |
| `thumbxl.png`, `thumbl.png`, `thumbm.png` | drawn in `fetch_icons.py` | this repo |
| `diacritics.png` | drawn in `fetch_icons.py` | this repo |
| `progmark.png` | drawn "E" tile, `program_marks.letter_mark` | this repo |

Fluent: Microsoft Fluent UI System Icons,
<https://github.com/microsoft/fluentui-system-icons> (MIT). Material Symbols:
<https://fonts.google.com/icons> (Apache-2.0). Both are compatible with this
repository's GPL-3.0-or-later.

Help, Delete, Select all, Copy, Cut, Paste and Close are drawn by the shared
concept renderer (no file in `icons/`).

## ESC mark

The Everything logo (a magnifying glass) is voidtools' artwork, distributed
only inside the freeware program, with no licence that allows redistributing
it. It is not in Simple Icons. The mark is therefore a drawn letter tile with
"E". It is a committed asset; `fetch_icons.py` does not redraw it once it
exists.

## Process name

Both downloads on <https://www.voidtools.com/downloads/> ship the program as
`Everything.exe` (`Everything-1.4.1.1032.x64.zip` and
`Everything-1.5.0.1424b.x64.en-US.zip`, read 2026-11-05). The mapping key is
`everything`. It was not checked against a running install.
