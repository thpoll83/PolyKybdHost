# Microsoft Paint overlay -- sources & provenance

Reproducible record for the Microsoft Paint keycap overlays. Re-run

```bash
python polyhost/res/overlay_sources/mspaint/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/mspaint/bindings.yaml --preview /tmp/mspaint_preview
```

to rebuild; both steps are deterministic given the committed `icons/` and
`bindings.yaml`, and a re-run must leave every PNG byte-identical.

## Shortcuts

⚠️ **Paint is closed source and Microsoft publishes no per-app shortcut list.**
The general *Keyboard shortcuts in Windows* support page has no Paint section
(checked), and the `keyboard-shortcuts-in-apps` URL that used to carry one is a
404. So the rule applied here is the one the Notepad overlay uses: **wire only
what two independent references agree on**, and leave a single-source claim out
rather than inventing a meaning. A wrong icon is worse than a missing one,
because the user believes it.

References:
- https://www.computerhope.com/shortcut/paint.htm
- https://winaero.com/the-full-list-of-keyboard-shortcut-for-microsoft-paint/
- https://www.makeuseof.com/microsoft-paint-keyboard-shortcuts/

⚠️ **Windows 11's Paint is a rewritten app** (layers, background removal), so a
list written for Windows 10 can be right about `Ctrl+S` and wrong about a menu
that no longer exists. The 21 wired bindings are the ones that are stable across
both: file, clipboard, the text-tool run, view toggles and zoom.

Not wired, deliberately: the arrow keys (nudge the selection one pixel) and
`Del`, which have no cell in the overlay grid; and the tool-select keys, which
Paint does not have -- that row is paint.net's, not Paint's.

## Icons

Every icon is either **Microsoft Fluent UI System Icons** (MIT, the house style
across all PolyKybd overlays) or drawn in `fetch_icons.py`. MIT and our own art
are both compatible with this repo's **GPL-3.0-or-later**.

Drawn here: the program mark only.

⚠️ **The program mark is never the app's real logo.** Every one of these logos is
proprietary trademark art, so the ESC cell carries a licence-clean substitute --
usually the shared letter tile (`../program_marks.py`). It exists to say *which
overlay set is loaded*, not to identify the vendor.

| icon | art | licence |
|---|---|---|
| `new.png` | Fluent `Document Add` | MIT |
| `open.png` | Fluent `Folder Open` | MIT |
| `save.png` | Fluent `Save` | MIT |
| `print.png` | Fluent `Print` | MIT |
| `undo.png` | Fluent `Arrow Undo` | MIT |
| `redo.png` | Fluent `Arrow Redo` | MIT |
| `cut.png` | Fluent `Cut` | MIT |
| `copy.png` | Fluent `Copy` | MIT |
| `paste.png` | Fluent `Clipboard Paste` | MIT |
| `selectall.png` | Fluent `Select All On` | MIT |
| `imageprops.png` | Fluent `Image` | MIT |
| `resize.png` | Fluent `Resize Image` | MIT |
| `bold.png` | Fluent `Text Bold` | MIT |
| `italic.png` | Fluent `Text Italic` | MIT |
| `underline.png` | Fluent `Text Underline` | MIT |
| `grid.png` | Fluent `Grid` | MIT |
| `ruler.png` | Fluent `Ruler` | MIT |
| `zoomin.png` | Fluent `Zoom In` | MIT |
| `zoomout.png` | Fluent `Zoom Out` | MIT |
| `fullscreen.png` | Fluent `Full Screen Maximize` | MIT |
| `saveas.png` | Fluent `Save Edit` | MIT |
| `mspaint.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |

21 of 22 are Fluent (MIT, some with a digit composited over); the rest are drawn.

## Verifying

The preview (`--preview`, `overlay_preview.png`) reads the **rendered** overlay
back and shows every populated key in its real 72x40 cell. That is the only
check that catches a cell which drew nothing -- see
`tests/res/overlay_cells_test.py`, which now pins it for every app at once.
