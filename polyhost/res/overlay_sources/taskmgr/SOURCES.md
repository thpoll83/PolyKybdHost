# Task Manager overlay -- sources & provenance

Reproducible record for the Task Manager keycap overlays. Re-run

```bash
python polyhost/res/overlay_sources/taskmgr/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/taskmgr/bindings.yaml --preview /tmp/taskmgr_preview
```

to rebuild; both steps are deterministic given the committed `icons/` and
`bindings.yaml`, and a re-run must leave every PNG byte-identical.

## Shortcuts

⚠️ **The thinnest overlay in this set, and that is the APP rather than a gap in
the research.** Windows 11's Task Manager has five documented in-app shortcuts.

References:
- https://winaero.com/task-manager-in-windows-11-now-supports-advanced-keyboard-shortcuts/
- https://www.pocket-lint.com/how-to-use-task-manager-in-windows/

⚠️ **`Ctrl+Shift+Esc` is deliberately NOT drawn.** It *opens* Task Manager and
does nothing once you are in it, so an icon for it would be an instruction the
focused window cannot obey -- which is the one thing a keycap overlay must never
show.

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
| `endtask.png` | Fluent `Dismiss Square` | MIT |
| `newtask.png` | Fluent `Add Square` | MIT |
| `efficiency.png` | Fluent `Leaf One` | MIT |
| `nextpage.png` | Fluent `Arrow Right` | MIT |
| `prevpage.png` | Fluent `Arrow Left` | MIT |

5 of 5 are Fluent (MIT, some with a digit composited over); the rest are drawn.

## Verifying

The preview (`--preview`, `overlay_preview.png`) reads the **rendered** overlay
back and shows every populated key in its real 72x40 cell. That is the only
check that catches a cell which drew nothing -- see
`tests/res/overlay_cells_test.py`, which now pins it for every app at once.
