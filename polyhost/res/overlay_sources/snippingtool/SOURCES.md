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

### Three more Alt keys, added 2026-09-14

Reported from the field, then checked. Each drawn one has **two independent
references**, the same bar the `notepad` overlay uses:

| key | action | sources |
|---|---|---|
| `Alt+D` | Delay the capture | [xp-pen](https://www.xp-pen.com/blog/snipping-tool-shortcut.html), [allthings.how](https://allthings.how/how-to-use-windows-11-snipping-tool/) |
| `Alt+B` | Ballpoint pen | [allthings.how](https://allthings.how/how-to-use-windows-11-snipping-tool/) + search corroboration |
| `Alt+H` | Highlighter | as above |

⚠️ `Alt+B` and `Alt+H` only do anything **once a capture exists** -- they are the
editor's annotation tools, not capture controls. They are drawn anyway: a keycap
that shows what a key will do in the state you are about to be in is the point of
the displays, and the overlay format has no way to express "only while editing".

### ⚠️ Alt+A, Alt+P and Alt+K are NOT drawn

They were reported in the same message and **no reference names any of the
three** -- not Microsoft's docs, not the four shortcut sites checked. There is
therefore no action to put on the keycap, and this repo's rule is explicit: *if a
requested key has no default in that app, flag it -- don't invent a meaning.*

This is a gap waiting on evidence, not a decision. The way to settle it is the
app itself:

```
python tools/shortcut_probe.py --focused --json snip.json
```

with Snipping Tool focused and a capture on screen. That reads `AccessKey` and
`AcceleratorKey` off the live UI Automation tree — first-party and exact, and
strictly better than any of the references above.

## Icons

Every icon is either **Microsoft Fluent UI System Icons** (MIT, the house style
across all PolyKybd overlays) or drawn in `fetch_icons.py`. MIT and our own art
are both compatible with this repo's **GPL-3.0-or-later**.

Drawn here: nothing (program mark only).

⚠️ **The program mark here is not the app's real logo, and that is a fact about
THIS app rather than a rule.** The sentence used to read *"the program mark is
never the app's real logo"*, which was written for a mixed batch and inherited
by every overlay in it -- including the free-software ones, where it was simply
wrong: WinSCP (GPL-3.0), PuTTY and Windows Terminal (MIT) and 7-Zip (LGPL) all
ship their real marks now, and read better for it. **Always check the licence
before drawing a substitute.** What makes this one different is not the vendor
but where the art lives: it is inside Windows, published in no repository, so
there is nothing to take under any licence. Hence a **curated generic**
from `polyhost/res/app_icons.yaml` (a palette for Paint, scissors for Snipping
Tool). It says what the app IS rather than naming a brand, which is the mark's
whole job.

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
| `delay.png` | Fluent `Timer` | MIT |
| `pen.png` | Fluent `Pen` | MIT |
| `highlight.png` | Fluent `Highlight` | MIT |

12 of 12 are Fluent (MIT); nothing is drawn here but the program mark, and that
comes from the curated generic rather than being baked (see above).

## Verifying

The preview (`--preview`, `overlay_preview.png`) reads the **rendered** overlay
back and shows every populated key in its real 72x40 cell. That is the only
check that catches a cell which drew nothing -- see
`tests/res/overlay_cells_test.py`, which now pins it for every app at once.
