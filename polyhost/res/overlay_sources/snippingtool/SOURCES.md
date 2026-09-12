# Snipping Tool overlay -- sources & provenance

Reproducible record for the Snipping Tool keycap overlays. Re-run

```bash
python polyhost/res/overlay_sources/snippingtool/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/snippingtool/bindings.yaml --preview /tmp/snippingtool_preview
```

to rebuild; both steps are deterministic given the committed `icons/` and
`bindings.yaml`, and a re-run must leave every PNG byte-identical.

## Shortcuts

⚠️ **This overlay is small by nature, not by omission.** The shortcut everyone
knows -- `Win+Shift+S` -- is a GUI/Win-key combination, and the overlay format
has **no channel for those at all** (the generator drops them). What is wired is
the set that works INSIDE the app window once it is open.

References:
- https://www.cloudspress.com/9-snipping-tool-keyboard-shortcuts-in-windows-10-11/
- https://www.xp-pen.com/blog/snipping-tool-shortcut.html

`Alt+M` (choose a snipping mode) and `Alt+N` (new snip in the last mode) are the
two that are genuinely worth a keycap -- both are app-only and neither is
guessable.

## Icons

Every icon is either **Microsoft Fluent UI System Icons** (MIT, the house style
across all PolyKybd overlays) or drawn in `fetch_icons.py`. MIT and our own art
are both compatible with this repo's **GPL-3.0-or-later**.

Drawn here: nothing (program mark only).

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
| `newsnip.png` | Fluent `Cut` | MIT |
| `save.png` | Fluent `Save` | MIT |
| `copy.png` | Fluent `Copy` | MIT |
| `print.png` | Fluent `Print` | MIT |
| `undo.png` | Fluent `Arrow Undo` | MIT |
| `redo.png` | Fluent `Arrow Redo` | MIT |
| `selectall.png` | Fluent `Select All On` | MIT |
| `mode.png` | Fluent `Crop Interim` | MIT |
| `samemode.png` | Fluent `Arrow Sync Circle` | MIT |

9 of 9 are Fluent (MIT, some with a digit composited over); the rest are drawn.

## Verifying

The preview (`--preview`, `overlay_preview.png`) reads the **rendered** overlay
back and shows every populated key in its real 72x40 cell. That is the only
check that catches a cell which drew nothing -- see
`tests/res/overlay_cells_test.py`, which now pins it for every app at once.
