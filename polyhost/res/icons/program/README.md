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

## Why these are PNG and not SVG

| file | form | why |
|---|---|---|
| `terminal.svg` | vector | plain line work, nothing stops it being an SVG |
| `chrome.svg` | vector | Simple Icons' `googlechrome`, unchanged (see below) |
| `notes.png` | mask | rendered at box **34** so it is smaller than 38 in *both* axes |
| `photos.png` | mask | carries a per-petal **dither** |
| `finder.png` | mask | a thinned raster of mdi's art |
| `clion.png`, `datagrip.png`, `goland.png`, `intellijidea.png`, `phpstorm.png`, `pycharm.png`, `rider.png`, `rubymine.png`, `webstorm.png` | mask | Simple Icons' filled plate, inverted inside the square plus a 2 px frame |
| `idea.png` | mask | `intellijidea.png` again, under the executable's slug (see below) |

⚠️ **Why the JetBrains marks are not simply `si:`.** Simple Icons draws each
IDE as a filled square with its letters cut out. On this panel that is a
38 × 38 lit block, which `mark_rank` reads inside-out (`False`, about 0.21), so
the OS icon won instead: CLion showed its dithered colour icon (hardware,
2026-09-29). Hollowing the plate lights the letters and underline, which is
what the real product logos show (white letters in a black square), and ranks
0.66–0.82. The sources are vendored in `src/si-<ide>.svg`, so the generator
does not depend on the CDN pin.

⚠️ **Why `idea.png` duplicates `intellijidea.png`.** Every other JetBrains IDE's
executable is its product name (`clion`, `pycharm64`), so the exe alone reaches
its mark. IntelliJ's is `idea`, and `poly:intellijidea` is reached only through
the display name "IntelliJ IDEA". A Linux install with no desktop entry gives
the forwarder no display name, so a forwarded IntelliJ drew no mark while CLion
did (field, 2026-09-30). `tools/gen_program_icons.py` writes the same mask under
both names (`JETBRAINS_EXE_SLUGS`).

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

The JetBrains IDE marks (`clion.png` … `webstorm.png`) are derived from
[Simple Icons](https://simpleicons.org/) (CC0-1.0) by inverting the plate and
adding a frame; the vendored sources are `src/si-<ide>.svg`. The product names
and logos are trademarks of JetBrains s.r.o.; Simple Icons' own disclaimer on
brand marks applies.

None of these reproduce Apple's own artwork. `photos.png` is a generic eight-petal
rosette, not Apple's asset.

## `chrome.svg`: a shipped copy of a catalog mark

`chrome.svg` is Simple Icons' `googlechrome` (15.22.0, CC0-1.0; "Google Chrome"
is a Google trademark), byte for byte. It ships because the ranking would never
pick it from the catalog: `mark_score` rewards thin line art, so
`mdi:google-chrome`'s 1-2 px segment strokes score 0.61 against this logo's
0.24, while on the keycap the solid logo is the one that reads (keycap preview,
2026-09-29). A shipped `poly:` mark that reads the right way up outranks every
catalog and OS candidate (`app_icons.contest_key`), so dropping the file here is
the whole fix. It answers `poly:chrome`, i.e. the `chrome` executable only; Edge,
Brave and the other Chromium browsers keep their own marks.
