# Shipped program marks (`poly:`)

The mark drawn on the **ESC** keycap for the focused application, when neither
Simple Icons nor Material Design Icons carries one that reads at 38 px.

`app_icons.candidates()` offers `poly:<slug>` for every name it derives, so the
**filename is the slug** — `terminal.svg` answers `poly:terminal`. There is no
name→slug table, which is what keeps this a catalog rather than the per-app
configuration `docs/generic-icons-plan.md` rejects. Drop a file in and any
application reporting that name gets it, including one nobody here has heard of.

Regenerate with `python tools/gen_program_icons.py`; preview on a real keycap
with `python tools/esc_mark_preview.py`.

## Why four of these are PNG and not SVG

| file | form | why |
|---|---|---|
| `terminal.svg` | vector | plain line work, nothing stops it being an SVG |
| `notes.png` | mask | rendered at box **34** so it is smaller than 38 in *both* axes |
| `photos.png` | mask | carries a per-petal **dither** |
| `finder.png` | mask | a thinned raster of mdi's art |

⚠️ `render_overlay` fits an icon's **longest side** to the 38 px box, so one
dimension is always exactly 38. "Narrower *and* shorter" is unreachable by
reshaping the viewBox — it needs a smaller box, which is per-icon, which means
the result has to be baked. That is `notes.png`.

⚠️ A dither cannot be a vector here at all: `svg_raster` supports no patterns
and no opacity, and the panel is one bit, so a per-region grey has to be
resolved to pixels when the icon is authored. `load_mask()` therefore reads
these **verbatim** — putting a halftone back through `icon_binarise` is what
turns it into mush.

## Licensing

`terminal.svg`, `notes.png` and `photos.png` are original work for this project
and carry the repository's licence.

⚠️ **`finder.png` is a derivative work of `mdi:apple-finder` from
[Material Design Icons](https://pictogrammers.com/library/mdi/), Apache-2.0.**
It is that mark's own geometry with every stroke thinned 0.75 px per side (see
`tools/gen_program_icons.py`). Redrawing it by hand was tried and lost what makes
it recognisable — the asymmetric "Picasso" face — so the retrace is deliberate
and the attribution is required. Keep this note with the file.

None of these reproduce Apple's own artwork. `photos.png` is a generic eight-petal
rosette, not Apple's asset.
