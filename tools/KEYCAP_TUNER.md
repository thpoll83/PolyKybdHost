# Keycap tuner (`gen_keycap_tuner.py`)

An interactive, **offline HTML** tool for hand-placing the per-keycap OLED glyphs of
a PolyKybd language layout (base / Shift / AltGr) and the whole-layout offsets, then
exporting the result for `lang_lut.xlsx`. It renders **pixel-identical to the
firmware**, so what you see is what the panel shows.

## Generate one for any layout — or all of them

```bash
cd PolyKybdHost/tools
python gen_keycap_tuner.py --lang ps-AF          # one layout   -> /tmp/ps-AF_tuner.html
python gen_keycap_tuner.py --lang te-IN --out /tmp/te.html
python gen_keycap_tuner.py --all                 # every layout -> /tmp/all_tuner.html
python gen_keycap_tuner.py --all --out /tmp/all.html
```

Open the file in any browser (no install, no network). It already shows the layout's
**current** state from `lang_lut.xlsx`.

It works for **every** layout in `lang_lut.xlsx` — the generator pulls that lang's
cells, the exact glyph bitmaps it uses (any script), the category offsets, and the
en-US fallback glyphs, and embeds them in the page.

`--all` bakes **every** layout into one file behind a **Layout dropdown** at the top.
The glyph bitmaps are stored once in a **shared pool keyed by codepoint** (Latin
layouts reuse the same a/b/c bitmaps), so the page stays a few MB even with every
script. Switching the dropdown keeps each layout's edits alive, and **Export** emits
one `=== code ===` block per edited layout — feed the whole box straight to
`apply_tuner.py` (below). `--lang X` is just `--all` restricted to one layout (the
dropdown then has a single entry); both share the same render mirror and page code.

## Using it

- **base = green, Shift = blue, AltGr = red**; overlaps mix; faded pixels are
  **clipped off the 72×40 keycap**; a faint crosshair marks each element's **offset
  origin** (the anchor the H/V offset sets).
- A red border / label flags a key with out-of-bounds or overlap; the top line tallies
  them. An **en-US** badge marks a key with no own glyph (Latin fallback).
- The line **under each preview** is that key's positioning **control-char sequence**
  (`\f` up · `\x05` down · `\b` left · `\x06` right), coloured per element — i.e. the
  escapes that get written into the cell. `·` means no offset.
- On the selected key you can **drag** the active glyph in the preview to position it;
  it **snaps to 2px** (one control char — the firmware has no 1px positioning code).
  The d-pad does the same in fixed 2px steps.
- Click a key → bottom-left: nudge **base/Shift/AltGr** with the ↑↓←→ d-pad (2px per
  press) or tick **drop**. The active element (base/Shift/AltGr, in its own colour)
  gets a tint overlay showing its origin quadrant — everything except the **top-right**
  of the origin. Click an element's control block to activate it and preview its tint
  **without nudging**; selecting a key activates **base** by default.
- Bottom-right: the **whole-layout offsets** (letter/num/sym × small/shift/altgr × H/V)
  with ◀▶ / ▲▼ buttons.
- **Export changes** → paste the box back to whoever applies it.

## Export format → how to apply

```
=== ps-AF ===                          # one block per edited layout (Export adds these)
KC_Q base: U"\f\f" ARABIC_DAD          # a cell value -> lang_lut.xlsx (var base/shift/altgr)
KC_D altgr: <drop / empty>             # clear that cell
[offset] letter shift H = 44           # a settings value -> the SET[cat] offset rows
```

**Apply it automatically** — `apply_tuner.py` parses exactly this format and writes the
cells straight back into `lang_lut.xlsx`:

```bash
python apply_tuner.py changes.txt              # from a file
pbpaste | python apply_tuner.py -              # from the clipboard (paste the Export box)
python apply_tuner.py changes.txt --dry-run    # just print the resolved cell edits
```

It edits **only** `xl/worksheets/sheet2.xml` (set / clear cells) and copies every other
zip entry byte-for-byte, so the formula caches in the other sheets stay intact — the
same surgical approach as `lang/_patch_xlsx.py`, which only *appends* columns. Per-key
lines map to the `key_lut` sheet (`KC_* row`, col = lang\*4 + {base:0, shift:1,
altgr:3}); `[offset]` lines map to the offset rows (`oled_preview.SET[cat]` =
voffset/hoffset, var {small:0, shift:1, altgr:3}); `<drop / empty>` clears the cell.
After applying: `cog -r lang_lut.c`, build, flash. (To apply by hand instead, the same
row/col mapping is all you need.)

## The 2px positioning control codes (cells)

Embedded in a cell, they nudge the glyph (the tuner d-pad emits these):

| code | move | code | move |
|------|------|------|------|
| `\f`   (0x0c) | up 2px   | `\x05` | down 2px |
| `\b`   (0x08) | left 2px | `\x06` | right 2px |

(`\t`/`\v` are coarse tab stops, `\n`/`\r`/`\x18` reset — see `disp_array.c`.) The
category **offsets** (VAR_* settings) are arbitrary px and move every key in the
category at once.

## Extending / keeping it correct

The page embeds a JS reimplementation of the firmware render path. It **must** stay in
sync with three things, which all already mirror `keymap.c render_key` +
`disp_array.c`:

- **`oled_preview.Renderer.bounds`** — uses `x + xOffset + width - 1` (the rightMOST
  pixel) under a `width > 0` guard. This drives the Shift clearance / right-edge clamp;
  an off-by-one here shifts clamp-driven placement 1px (this was a real bug).
- **`oled_preview.render_key`** — `base_x = 28 + h`, the `+2` Shift clearance, the
  `−6 / +4` diagonal stagger when forced to overlap, the AltGr right-edge clamp, the
  en-US fallbacks, baseline 23 / `BUFFER_X` 28 / `SCREEN_WIDTH` 72.
- **the control codes** in `Renderer.draw` / `bounds`.

If you change any of those, mirror the change in `keycap_tuner_template.html`
(functions `bounds`, `draw`, `renderKey`) and **re-verify** with a headless diff —
the JS must agree with the firmware-faithful `oled_preview.warn_key` for every key:

```bash
# render the JS render logic in node and diff its per-key out-of-bounds/overlap
# against oled_preview.py --check-bounds for the same lang (they must be identical).
# Slice off the DOM-touching init (node has no document), then load the layout and
# walk the keys. Generate the file with --lang ps-AF so DATA.order[0] is that layout.
node <(python - <<'PY'
import re; h=open("/tmp/ps-AF_tuner.html").read()
js=re.search(r"<script>(.*)</script>",h,re.S).group(1).split("const _sel=")[0]
print(js + 'loadLang(DATA.order[0]);'
  + 'for(const r of DATA.rows)for(const k of r){if(!(k in st))continue;const w=keyWarn(renderKey(k));if(w)console.log(k,w);}')
PY
)
python oled_preview.py --lang ps-AF --check-bounds
```

## Notes / limits

- `--lang` is one layout per file; `--all` puts every layout in one file behind the
  dropdown, sharing a single codepoint-keyed glyph pool to keep the page small.
- Combining marks the layout drops (e.g. Arabic harakat, the nukta hint) follow the
  layout; the tuner shows what `lang_lut.xlsx` has.
- A key with no own glyph renders the **en-US** fallback (tagged); nudging it exports a
  real per-lang cell that overrides the fallback — leave it alone to keep the fallback.
