# Keycap tuner (`gen_keycap_tuner.py`)

An interactive, **offline HTML** tool for hand-placing the per-keycap OLED glyphs of
a PolyKybd language layout (base / Shift / AltGr) and the whole-layout offsets, then
exporting the result for `lang_lut.xlsx`. It renders **pixel-identical to the
firmware**, so what you see is what the panel shows.

## Generate one for any layout

```bash
cd PolyKybdHost/tools
python gen_keycap_tuner.py --lang ps-AF          # -> /tmp/ps-AF_tuner.html
python gen_keycap_tuner.py --lang te-IN --out /tmp/te.html
```

Open the file in any browser (no install, no network). It already shows the layout's
**current** state from `lang_lut.xlsx`.

It works for **every** layout in `lang_lut.xlsx` — the generator pulls that lang's
cells, the exact glyph bitmaps it uses (any script), the category offsets, and the
en-US fallback glyphs, and embeds them in the page.

## Using it

- **base = green, Shift = blue, AltGr = red**; overlaps mix; faded pixels are
  **clipped off the 72×40 keycap**; a faint crosshair marks each element's **offset
  origin** (the anchor the H/V offset sets).
- A red border / label flags a key with out-of-bounds or overlap; the top line tallies
  them. An **en-US** badge marks a key with no own glyph (Latin fallback).
- Click a key → bottom-left: nudge **base/Shift/AltGr** with the ↑↓←→ d-pad (2px per
  press) or tick **drop**. The active Shift/AltGr element gets a tint overlay showing
  its origin quadrant.
- Bottom-right: the **whole-layout offsets** (letter/num/sym × small/shift/altgr × H/V)
  with ◀▶ / ▲▼ buttons.
- **Export changes** → paste the box back to whoever applies it.

## Export format → how to apply

```
KC_Q base: U"\f\f" ARABIC_DAD          # a cell value -> lang_lut.xlsx (var base/shift/altgr)
KC_D altgr: <drop / empty>             # clear that cell
[offset] letter shift H = 44           # a settings value -> the SET[cat] offset rows
```
Per-key lines go into the `key_lut` sheet (`KC_* row`, col = lang*4 + {base:0,shift:1,
altgr:3}); `[offset]` lines go into the offset rows (`oled_preview.SET[cat]` = the
voffset/hoffset rows). Then `cog -r lang_lut.c`, build, flash.

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
# against oled_preview.py --check-bounds for the same lang (they must be identical)
node <(python - <<'PY'
import re; h=open("/tmp/ps-AF_tuner.html").read()
print(re.search(r"<script>(.*)</script>",h,re.S).group(1).split("buildOffPanel();")[0]
  + 'for(const r of DATA.rows)for(const k of r){if(!(k in st))continue;const w=keyWarn(renderKey(k));if(w)console.log(k,w);}')
PY
)
python oled_preview.py --lang ps-AF --check-bounds
```

## Notes / limits

- One layout per file (the glyph set is per-lang to keep the page small).
- Combining marks the layout drops (e.g. Arabic harakat, the nukta hint) follow the
  layout; the tuner shows what `lang_lut.xlsx` has.
- A key with no own glyph renders the **en-US** fallback (tagged); nudging it exports a
  real per-lang cell that overrides the fallback — leave it alone to keep the fallback.
