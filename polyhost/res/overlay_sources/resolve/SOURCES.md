# DaVinci Resolve overlay — sources & licenses

## Shortcuts

DaVinci Resolve **Windows** defaults, as shipped in Resolve 18/19/20 (the
keymap has been stable across those releases). Cross-checked against two
independent references because Blackmagic publishes the keymap only inside the
application manual PDF, not as a web page:

- <https://www.davincishortcuts.com/> — "Complete Cheat Sheet (Resolve 21)",
  covers Resolve 18–21, Windows/Linux and Mac modifiers side by side.
- <https://pixflow.net/blog/davinci-resolve-keyboard-shortcuts/> — 2026 cheat
  sheet covering every page (Media, Cut, Edit, Fusion, Color, Fairlight,
  Deliver).

Where the two disagreed, the disagreement is resolved and recorded here:

| Action | Used | Note |
|---|---|---|
| Redo | `Ctrl+Shift+Z` | davincishortcuts listed `Ctrl+Y`; pixflow and Resolve's own Edit menu use `Ctrl+Shift+Z`. |
| `Ctrl+N` | New **timeline** | pixflow captioned it "New Project"; Resolve's File menu binds `Ctrl+N` to New Timeline (a new *project* is created from the Project Manager and has no default key). Labelled "New timeline" to avoid asserting the ambiguous one. |

Deliberately **not** included: `Ctrl+F` (pixflow calls it Full Screen, other
references call it Find — unresolved, so it is left off rather than guessed);
anything on the numeric keypad (no overlay cell).

## Icons

| File(s) | Source | License |
|---|---|---|
| `newtimeline, save, import, render, renderqueue, undo, redo, cut, copy, paste, selectall, group, ungroup, link, addedit, zoomin, zoomout, select, marker, dyntrim, insert, play, stop, fwd, rev, pagecut, pageedit, pagefusion, pagecolor, pagefairlight, pagedeliver` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `blade, markin, markout, overwrite, append, rippledelete, trim, snap` | Custom-drawn, `../nle_glyphs.py` | GPL-3.0-or-later (this repo) |
| `resolve.png` (ESC program mark) | Custom-drawn, `../geo_marks.py` | GPL-3.0-or-later (this repo) |

**The program mark is NOT the Blackmagic logo.** The DaVinci Resolve logo is a
Blackmagic Design trademark that we may not redistribute. What the ESC cell
shows is *drawn from the construction* rather than copied: a 2px ring with three
teardrops at 120°, tips pointing inwards. It replaced a generic "R" letter tile,
which said nothing about the app.

Both radii matter at 37x32. A drop that reaches the ring, or the centre, merges
into a blob once the mark is thresholded to 1 bit — hence the bulb radius
(`bulb`, 0.20 of the ring) and the orbit (`ring`, 0.52) leave air at both ends.
The mark is drawn 8x supersampled and Lanczos-downscaled, because `ImageDraw`
has no antialiasing and a circle drawn straight at this size is visibly ragged.

The eight custom NLE glyphs exist because neither Fluent nor Material has them,
and the nearest generic glyph actively misleads at keycap size — a scissors
reads as clipboard-*cut* (which is a different key here, `Ctrl+X`), a trash can
as delete-*file*, a download arrow as *export*.

PolyKybdHost is GPL-3.0-or-later; MIT is GPL-3.0-compatible.

## Regenerate

```bash
python polyhost/res/overlay_sources/resolve/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/resolve/bindings.yaml --preview /tmp/resolve_preview
```

## macOS

The spec serves Windows and macOS from one file: `resolve_template.*`
(Windows/Linux) and `resolve_template_mac.*` (macOS). Resolve's Mac keymap is the
Windows one with Ctrl→Command and Alt→Option, so 16 bindings are `CMDCTRL`.

Sources:

- **Blackmagic's DaVinci Resolve 18 Reference Manual** (official; its shortcuts are
  written in Mac form), mirrored at
  <https://github.com/ltbits/davinci-resolve-manuals> (`DR18/DR18-RM05-Edit.pdf`,
  `RM03-IngestAndOrganizeMedia`, `RM01`, `RM02`, `RM06`). Confirms: Command-N new
  timeline, Command-S, Command-I import media, Command-Z / Command-Shift-Z,
  Command-X/C/V, Command-A, Command-Backslash split, Command-Equals / Command-Minus
  zoom, Option-Command-L link, Shift-2…8 pages, F9 / F10 / Shift-F12, and
  **Forward Delete = ripple delete**. `documents.blackmagicdesign.com` itself was
  egress-blocked.
- Web-search snippets (davinciresolveclub.com, motionarray.com, evercast.us) for
  the three chords the manual does not list: Cmd+B (razor at playhead), Cmd+G /
  Cmd+Shift+G (group / ungroup). These follow the uniform Ctrl→Cmd pattern.

| Action | Windows | macOS | Why |
|---|---|---|---|
| Ripple delete | `Shift+Backspace` | `Forward Delete` (the DELETE key) | Reference manual: "Forward Delete — Ripple delete". Written twice with `only:`. |
| Start render | — (dropped) | — (dropped) | The manual documents Command-R as **Retime Controls** (Edit page) / Resolve Live (Color page), not render. |
| Render queue | `Ctrl+Shift+R` | — (dropped) | The manual documents Shift-Command-R as Resolve Live Freeze; no confirmed render-queue chord. |

No macOS chord drawn here is system-reserved (`Shift+3/4/5` carry no Cmd, so they
do not collide with the ⌘⇧3/4/5 screenshot keys).

Fixed 2026-09-30: the Windows `Ctrl+R` "Start render" cell is gone, because
`Ctrl+R` is Retime Controls (manual, see above). ⚠️ `Ctrl+Shift+R` "Render queue"
is still drawn on Windows but unconfirmed: the manual gives Shift-Command-R as
Resolve Live Freeze.

## Standard editing chords (shared Fluent concepts, 2026-10)

Nothing added. Save/New timeline/Undo/Redo/Cut/Copy/Paste/Select all and
Ctrl+= / Ctrl+- zoom were already drawn.

- **Ctrl+O (Open)**, **Ctrl+W (Close)**, **Ctrl+P (Print)**: no default documented in the
  DR18 reference manual or the cheat sheets above.
- **Ctrl+F**: still unresolved (Full Screen vs Find) — left off, as before.
