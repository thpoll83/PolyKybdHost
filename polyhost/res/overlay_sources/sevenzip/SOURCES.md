# 7-Zip File Manager overlay -- sources & provenance

Reproducible record for the 7-Zip File Manager keycap overlays. Re-run

```bash
python polyhost/res/overlay_sources/sevenzip/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/sevenzip/bindings.yaml --preview /tmp/sevenzip_preview
```

to rebuild; both steps are deterministic given the committed `icons/` and
`bindings.yaml`, and a re-run must leave every PNG byte-identical.

## Shortcuts

Shortcuts come from **7-Zip's own manual** ("Shortcut Keys"), so this is the
documented set rather than a third-party summary:

- https://sevenzip.osdn.jp/chm/main/shortcuts.htm  (the 7-Zip HTML help)
- https://7-zip.org/  (project home; the same help ships in the installer)

⚠️ **7-Zip is an F-KEY app in the Norton Commander tradition** -- `F2` rename,
`F5` copy, `F6` move, `F7` new folder, `F9` second panel -- so most of this
overlay lands in the NO-MODIFIER layer. That is unusual and it is the point:
those keys do nothing in most apps and everything here.

⚠️ `Ctrl+PgDn` (open the archive as a folder) shared the Eye glyph with `F3`
(view file) until the preview showed it. Descending into an archive and viewing
a file read-only are different acts; it is Fluent's `Folder Zip` now.

## Icons

Every icon is either **Microsoft Fluent UI System Icons** (MIT, the house style
across all PolyKybd overlays) or drawn in `fetch_icons.py`. MIT and our own art
are both compatible with this repo's **GPL-3.0-or-later**.

Drawn here: the program mark only.

⚠️ **The program mark is never the app's real logo**, and for most of this batch
it is not in this folder at all. Measured against both catalogs, none of these
apps has a brand mark in Simple Icons or mdi -- Microsoft does not license its
logos and mdi does not draw them -- so the ESC cell takes a **curated generic**
from `polyhost/res/app_icons.yaml` (a palette for Paint, scissors for Snipping
Tool, a zipped folder for 7-Zip). It says what the app IS rather than naming a
brand, which is the mark's whole job.

⚠️ A baked `program_icon:` would WIN over that: `send_overlays_mru` defers a
synthetic source on any (modifier, keycode) a template already drew. So a mark
here and a generic in the catalog are mutually exclusive, and the trade is that
a baked mark always draws while a fetched one needs `shortcut_icon_auto_fetch`
(default on) and one successful download.

| icon | art | licence |
|---|---|---|
| `rename.png` | Fluent `Rename` | MIT |
| `view.png` | Fluent `Eye` | MIT |
| `edit.png` | Fluent `Text Edit Style` | MIT |
| `copyto.png` | Fluent `Copy` | MIT |
| `moveto.png` | Fluent `Arrow Forward` | MIT |
| `newfolder.png` | Fluent `Folder Add` | MIT |
| `twopanel.png` | Fluent `Split Vertical` | MIT |
| `switchpanel.png` | Fluent `Arrow Swap` | MIT |
| `parent.png` | Fluent `Folder Arrow Up` | MIT |
| `root.png` | Fluent `Home` | MIT |
| `newfile.png` | Fluent `Document Add` | MIT |
| `comment.png` | Fluent `Comment Note` | MIT |
| `copyname.png` | Fluent `Clipboard Letter` | MIT |
| `refresh.png` | Fluent `Arrow Sync` | MIT |
| `largeicons.png` | Fluent `Grid` | MIT |
| `smallicons.png` | Fluent `Apps List` | MIT |
| `listview.png` | Fluent `Text Bullet List Square` | MIT |
| `details.png` | Fluent `Document Table` | MIT |
| `sortname.png` | Fluent `Text Sort Ascending` | MIT |
| `sorttype.png` | Fluent `Filter` | MIT |
| `sortdate.png` | Fluent `Calendar` | MIT |
| `sortsize.png` | Fluent `Data Bar Vertical` | MIT |
| `unsorted.png` | Fluent `Arrow Sort` | MIT |
| `openfolder.png` | Fluent `Folder Zip` | MIT |
| `props.png` | Fluent `Info` | MIT |
| `addrleft.png` | Fluent `Panel Left` | MIT |
| `addrright.png` | Fluent `Panel Right` | MIT |
| `history.png` | Fluent `History` | MIT |
| `otherpanel.png` | Fluent `Arrow Export Up` | MIT |

29 of 29 are Fluent (MIT, some with a digit composited over); the rest are drawn.

## Verifying

The preview (`--preview`, `overlay_preview.png`) reads the **rendered** overlay
back and shows every populated key in its real 72x40 cell. That is the only
check that catches a cell which drew nothing -- see
`tests/res/overlay_cells_test.py`, which now pins it for every app at once.
