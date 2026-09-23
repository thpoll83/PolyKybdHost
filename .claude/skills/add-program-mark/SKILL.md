---
name: add-program-mark
description: Design and ship an ESC program mark — the per-application icon on the ESC keycap — for an app neither Simple Icons nor Material Design Icons carries at a legible size. Draws it under the constraints the 72x40 1-bit panel and svg_raster actually impose, previews it on the real keycap before any hardware round, measures legibility/ink/transport, and wires it into the shipped `poly:` catalog with its licence note. Use when asked to "add an icon for <app>", "the ESC icon for X looks bad / is a blob / is missing", "make a mark for <app>", or when program_overlay resolves an app to nothing or to something unreadable. NOT for keycap shortcut hints (add-polykybd-shortcut-hint), NOT for app shortcut overlay PNGs (generate-app-overlays), and NOT for the legend layer of an ordinary keycap (keycap-layout-preview).
---

# Add an ESC program mark

The mark drawn on the **ESC** keycap for the focused application. Three sources,
ranked by legibility: the OS's own icon, the two catalogs (`si:`, `mdi:`), and
`poly:` — marks shipped in this repo under `polyhost/res/icons/program/`.

⚠️ **Read [`docs/generic-icons-plan.md`](../../../docs/generic-icons-plan.md)
first.** Its rule is **no per-application configuration**, and it reverses an
earlier 70-entry name→slug map. `poly:` stays inside that rule *only because the
filename IS the slug* — `terminal.svg` answers `poly:terminal`. Adding a lookup
table anywhere is the thing that plan exists to refuse.

## 1. Establish that the gap is real

Never draw before checking; the catalogs cover more than you expect, and a
catalog mark that nothing can *ask for* is a different bug with a cheaper fix.

```bash
cd ~/PolyKybdHost
.venv/bin/python -c "
from polyhost.services import app_icons as a
print(a.candidates('<exe-name>', ('<Display Name>',)))"
# then probe each candidate — 200 vs 404 is the whole answer
for n in <slug> <other>; do
  echo "si:$n $(curl -s -o /dev/null -w '%{http_code}' -A PolyKybdHost \
    https://cdn.jsdelivr.net/npm/simple-icons@15.22.0/icons/$n.svg)"
  echo "mdi:$n $(curl -s -o /dev/null -w '%{http_code}' -A PolyKybdHost \
    https://api.iconify.design/mdi/$n.svg)"
done
```

Three outcomes, three different jobs:

| finding | do this |
|---|---|
| a good catalog mark exists but `candidates()` never offers it | fix the naming rule (a prefix, the hyphen rule) — **not** a new asset |
| a catalog mark is offered but reads badly | check polarity first: a mark `score()` reads *inverted* is a solid blob on this panel |
| nothing in either catalog | draw one — the rest of this skill |

## 2. Draw it, under the real constraints

`polyhost/services/svg_raster.py` is the primary rasteriser (cairosvg is a
Windows-less fallback). It is deliberately narrow:

- **`<path d=…>` ONLY.** No `<rect>`, no `<circle>`, no `<line>`, **no strokes**,
  **no transforms**, no groups, no opacity, no patterns.
- Filled with the **nonzero** winding rule — a hole is a sub-path wound the
  opposite way to the shape around it.
- ⚠️ **A zero-radius arc (`A0 0 0 0 0`) is DEGENERATE and FreeType drops it
  silently**, filling the shape solid. Use plain lines for a straight hole.
- ⚠️ **A `transform="rotate(...)"` is parsed away**, so every rotated copy lands
  on top of the first. Compute rotated coordinates in Python and bake them in.

Two geometry rules that are easy to get backwards:

- ⚠️ **`render_overlay` fits the LONGEST side to the 38 px box**, so one dimension
  is always exactly 38. "Narrower *and* shorter" is unreachable by reshaping the
  viewBox — it needs a smaller `box=`, which is per-icon, which means the result
  must be **baked as a mask** rather than shipped as an SVG.
- **Stroke width is in viewBox units and the scale is 38/24 = 1.583**: `t=1.4`
  draws 2.2 px, `t=2.0` draws 3.2 px. 2.0 reads heavy on the panel.

⚠️ **A mark carrying a DITHER cannot be a vector at all** (no patterns, no
opacity, one-bit panel). Resolve it to pixels at authoring time and ship a
finished 72×40 mask; `load_mask()` reads those **verbatim**, because putting a
halftone back through `icon_binarise` is what turns it into mush.

Add the generator to `tools/gen_program_icons.py` so the asset is reproducible,
and ⚠️ **produce the mask through `app_icons.render_overlay` itself** rather than
a local copy of its steps — thresholding the supersampled alpha *before* the
downscale instead of after moved 89 px in one mark, and the file that ships must
be exactly what the renderer produces.

## 3. Preview on the real keycap, every round

```bash
.venv/bin/python tools/esc_mark_preview.py polyhost/res/icons/program/*.svg \
    polyhost/res/icons/program/*.png --scale 6 --out /tmp/esc.png
```

Real firmware GFX legend, real `render_overlay`, real Chebyshev-3 courtyard.
Sanity check it is faithful: it must report **`ESC legend inks x 2..27`**, the
figure `app_icons.py` documents.

**Require `legend lost 0 px`.** The mark's ink must start at x ≥ 34; the
courtyard clears three columns around it, and the ESC glyph ends at 27.

⚠️ **Judge it as a pixel grid, not a smooth upscale.** A dither that reads as
eight distinct greys at 6× nearest-neighbour can read as noise on the panel,
because a 4×4 Bayer cell is a large fraction of an 8 px feature.

## 4. Measure before showing it

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from polyhost.services import app_icons as ai, icon_binarise as ib
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.overlay_data import OverlayData
m = ai.render_mark('polyhost/res/icons/program/<name>.<ext>')
d = OverlayData(DeviceSettings(), m)
print('ink %d  rank %s  payload %d B  reports %d' % (
    m.sum(), ai.mark_rank(m), min(len(d.compressed_roi_bytes), 360),
    min(d.all_msgs, d.compressed_msgs, d.roi_msgs, d.compressed_roi_msgs)))"
```

- **rank** is `(read_the_right_way_up, score)`. A `False` first element means the
  mark is mostly ink and `score()` is rating its holes — on a white-on-black
  keycap that IS a blob. Fix the drawing, don't chase the number.
- Shipped marks land **0.39–0.72**; the good catalog marks sit around 0.50.
- A halftone does not RLE: one dithered mark compressed to 457 B against a raw
  frame of 360, so it ships uncompressed in 3 reports instead of 2.

## 5. Ship it

1. Drop the asset at `polyhost/res/icons/program/<slug>.{svg,png}` — **the
   filename is the slug**, no table anywhere.
2. `python tools/gen_program_icons.py` then `--check`; the check must be clean.
3. Record licence and provenance in that directory's `README.md`. ⚠️ A mark
   derived from a catalog (mdi is Apache-2.0) **needs attribution and the
   vendored source** kept beside it, so the generator's input cannot die.
4. Confirm end to end, with the network live, that the resolver actually picks it:

```bash
.venv/bin/python -c "
from polyhost.services import app_icons as a
from polyhost.services.os_app_icon import AppIdentity
print(a.program_overlay('<exe>', AppIdentity(None,'',('<Display Name>',)),
                        allow_network=True)[1])"
```

## Output format

Report per mark: the winning slug, ink, rank, payload/reports, and
`legend lost 0 px`. Show the keycap render. Name anything you could not fix.

## Pitfalls

- ⚠️ **Do not add a name→slug map.** If an app cannot be reached by a derived
  name, fix the derivation or accept no mark.
- ⚠️ **A mark that clears a floor is not a mark that wins.** Selection ranks;
  check `mark_rank`, not `MIN_SCORE`.
- ⚠️ **`ImageDraw.floodfill` is a no-op on Pillow 12.3.0** — present, raises
  nothing, fills zero pixels. Hand-roll a BFS if you need hole detection.
- ⚠️ **Do not re-binarise a finished mask.** `render_mark` dispatches on `.png`
  for exactly this reason.
- **An 8 px feature carries almost no detail.** Two overlapping rings, a stack
  of frames, or a 1 px interior line all dissolve; verify at 1× before 6×.
