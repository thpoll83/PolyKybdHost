# Adobe Premiere Pro overlay — sources & licenses

## Shortcuts

Premiere Pro **Windows** defaults. Adobe's own "Default keyboard shortcuts" page
renders its tables client-side and could not be extracted, so the set was built
from two independent references and only shortcuts they agree on were shipped:

- `Adobe_Premiere_Pro_Keyboard_Commands.pdf` (tcworkshop handout) —
  <https://www.tcworkshop.com/data/Downloads/Handouts/Adobe_Premiere_Pro_Keyboard_Commands.pdf>
  — the tool row, the Timeline/transport keys, the `Shift+1..7` panel row,
  `=`/`-`/`\` zoom.
- <https://www.simonsaysai.com/blog/adobe-premiere-pro-keyboard-shortcuts> —
  the Ctrl edit set (`Ctrl+K` Add Edit, `Ctrl+L` Link, `Ctrl+G` Group,
  `Ctrl+R` Speed/Duration, `Ctrl+Shift+V` Paste Insert, `Shift+Delete` Ripple
  Delete).
- Tool letters additionally confirmed against Adobe's own tool documentation
  (`V A B N X C Y U P H Z`).

### Deliberately excluded

The tcworkshop handout predates Creative Cloud and several of its single-letter
bindings were **reassigned** since, so anything the two sources disagreed on is
left off rather than guessed — a wrong legend on a keycap is worse than a blank
one:

| Key | Conflict |
|---|---|
| `T` | Trim (handout) vs **Type tool** (CC). |
| `M` | Match Frame (handout) vs **Add Marker** (CC). |
| `Q` / `W` | Go to In/Out (handout) vs **Ripple Trim Previous/Next Edit to Playhead** (CC). |
| `F` | Match Frame (CC) vs Fast Forward in the Capture panel (handout). |
| Ungroup | One source said `Ctrl+T`; Premiere's Clip menu uses `Ctrl+Shift+G`, which is what shipped. |
| Redo | One source said `Ctrl+Shift+Y`; Premiere's Edit menu uses `Ctrl+Shift+Z`, which is what shipped. |

Also excluded: numeric-keypad markers (`*`, `Shift+*`) — the keypad has no
overlay cell.

## Icons

| File(s) | Source | License |
|---|---|---|
| `select, ratestretch, pen, hand, zoom, newproject, newsequence, open, save, saveas, import, export, undo, redo, cut, copy, paste, pasteinsert, selectall, group, ungroup, link, addedit, speed, zoomin, zoomout, zoomfit, play, stop, fwd, rev, panel*` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `blade, markin, markout, rippledelete, rippleedit, rolledit, slip, slide, trackselect` | Custom-drawn, `../nle_glyphs.py` | GPL-3.0-or-later (this repo) |
| `premiere.png` (ESC program mark) | Custom-drawn, `../rect_mark.py` | GPL-3.0-or-later (this repo) |

**The program mark is NOT the Adobe logo.** "Pr" is set in Liberation Sans Bold
inside a generic drawn tile with a playhead motif; Adobe's mark is a trademark
we may not redistribute.

Four glyphs (`rippleedit`, `rolledit`, `slip`, `slide`) were drawn specifically
for the tool row. Those four tools differ *only* in which clip edge moves and
what absorbs the change, so a generic "resize"/"swap"/"move" icon conveys
nothing — each drawn glyph shows the track, which block is affected, and the
direction of travel.

PolyKybdHost is GPL-3.0-or-later; MIT is GPL-3.0-compatible.

## Regenerate

```bash
python polyhost/res/overlay_sources/premiere/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/premiere/bindings.yaml --preview /tmp/premiere_preview
```

## Program mark

The Adobe apps share one treatment (`../rect_mark.py`): a **2px rectangle with
the product's two letters inside** — `Ps` / `Ai` / `Pr` / `Ae`. They are a
family, and what identifies one is its letter pair, so the mark is deliberately
plain. Adobe's real logos are proprietary and cannot ship here; the letters are
the app's own naming, not its trademark styling — no rounded-square gradient, no
brand colours, no attempt to resemble the product tile.

Authored **1:1** at the `[37, 32]` region so the generator never rescales it and
the 2px frame stays exactly 2px; the letter size is *measured* per pair (the
widest that clears the frame by >=2px), since `Ai` is much narrower than `Pr`
and one hardcoded size would either clip or float.
