# PuTTY overlay -- sources & provenance

Reproducible record for the PuTTY keycap overlays. Re-run

```bash
python polyhost/res/overlay_sources/putty/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/putty/bindings.yaml --preview /tmp/putty_preview
```

to rebuild; both steps are deterministic given the committed `icons/` and
`bindings.yaml`, and a re-run must leave every PNG byte-identical.

## Shortcuts

⚠️ **THIS IS NOT A LIST OF PuTTY'S OWN SHORTCUTS, and that is deliberate.**
PuTTY is a terminal: essentially every key you press is *sent to the remote
host*, and its own set is two entries (`Alt+Enter` full screen, `Ctrl+right-click`
menu). That is not an overlay.

So this overlay is of the **remote shell's line editing** -- GNU readline in
emacs mode, plus the tty driver's control characters -- because that is what a
person sitting in a PuTTY window is actually pressing.

Source: **`bind -p` from bash's own readline**, i.e. the binding table itself
rather than a summary of it, plus the POSIX tty special characters
(`stty -a`: `intr` `susp` `eof` `erase` `werase` `kill`).

⚠️ **The meanings are not the familiar ones**, which is exactly why this overlay
earns its keycaps: `Ctrl+A` is beginning-of-line, not select-all; `Ctrl+W` kills
a word, not a window; `Ctrl+R` searches history, not reload. Third-party "PuTTY
shortcuts" pages list precisely these keys **without saying they belong to the
shell**, which is how they end up mislabelled -- so those pages are not cited
here even though they agree.

- https://www.gnu.org/software/bash/manual/html_node/Bindable-Readline-Commands.html
- https://man7.org/linux/man-pages/man1/stty.1.html

### Known conflation

`Ctrl+T` (transpose characters) and `Alt+T` (transpose words) share one glyph.
Both mean "swap two adjacent things" and the labels differ; a picture that
separates them at 40x40 px has not been found. Recorded rather than hidden.

## Icons

Every icon is either **Microsoft Fluent UI System Icons** (MIT, the house style
across all PolyKybd overlays) or drawn in `fetch_icons.py`. MIT and our own art
are both compatible with this repo's **GPL-3.0-or-later**.

Drawn here: the three kill-* glyphs, the mirrored kill-word-forward, and the program mark.

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
| `linestart.png` | Fluent `Arrow Previous` | MIT |
| `lineend.png` | Fluent `Arrow Next` | MIT |
| `charback.png` | Fluent `Arrow Left` | MIT |
| `charfwd.png` | Fluent `Arrow Right` | MIT |
| `prevcmd.png` | Fluent `Arrow Up` | MIT |
| `nextcmd.png` | Fluent `Arrow Down` | MIT |
| `searchback.png` | Fluent `Search` | MIT |
| `searchfwd.png` | Fluent `History` | MIT |
| `killtoend.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |
| `killtostart.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |
| `killword.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |
| `yank.png` | Fluent `Clipboard Paste` | MIT |
| `transpose.png` | Fluent `Arrow Swap` | MIT |
| `delchar.png` | Fluent `Backspace` | MIT |
| `complete.png` | Fluent `Text Position Line` | MIT |
| `clear.png` | Fluent `Broom` | MIT |
| `interrupt.png` | Fluent `Stop` | MIT |
| `suspend.png` | Fluent `Pause` | MIT |
| `eof.png` | Fluent `Sign Out` | MIT |
| `wordback.png` | Fluent `Skip Back 10` | MIT |
| `wordfwd.png` | Fluent `Skip Forward 10` | MIT |
| `killwordfwd.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |
| `upcase.png` | Fluent `Text Case Uppercase` | MIT |
| `downcase.png` | Fluent `Text Case Lowercase` | MIT |
| `capitalize.png` | Fluent `Text Case Title` | MIT |
| `revertline.png` | Fluent `Arrow Undo` | MIT |
| `lastarg.png` | Fluent `Arrow Hook Up Left` | MIT |
| `fullscreen.png` | Fluent `Full Screen Maximize` | MIT |

24 of 28 are Fluent (MIT, some with a digit composited over); the rest are drawn.

## Verifying

The preview (`--preview`, `overlay_preview.png`) reads the **rendered** overlay
back and shows every populated key in its real 72x40 cell. That is the only
check that catches a cell which drew nothing -- see
`tests/res/overlay_cells_test.py`, which now pins it for every app at once.
