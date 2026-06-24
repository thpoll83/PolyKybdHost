# tools — keycap demo renderer

Render promo images / animated GIFs of the PolyKybd per-keycap OLEDs, laid out
from the **same KLE file the layout editor uses**
(`polyhost/res/polykybd-split72.json`). The first consumer is an emoji-layer
walk-through, but the renderer is generic — you tell it, per frame, what each
keycap should show.

## Files

| File | Role |
|------|------|
| `kle_render.py` | Reusable renderer. Reuses `polyhost.kle.kle_praser.parse_kle` (note: the module file really is spelled `kle_praser.py`), lays out the keyboard (rotated thumb cluster included), and draws each key as a dark cap with a 72×40 monochrome "OLED". Per-frame API is `{matrix_pos: KeyContent}`; `save_gif()` writes the animation. |
| `gfx_font.py` | Pixel-exact glyph rendering from the firmware's generated Adafruit-GFX headers (`base/fonts/`), reproducing `kdisp_write_gfx_char`/`text`. Used by `--font-mode gfx` (the default). |
| `emoji_demo.py` | Data-driven driver for the emoji layer. Pulls geometry + roles + glyphs straight from the firmware so the demo always matches the keyboard. |
| `oled_preview.py` | Pixel-exact **language keycap** preview (rendering analysis). For a chosen layout it replicates the firmware's per-key draw (`translate_keycode` + the letter/num/sym h/v offsets + shift-preview clear/clamp/stagger + AltGr preview), straight from `lang/lang_lut.xlsx` + `named_glyphs.h`, reusing `gfx_font.py`. Writes a contact sheet of every key (or one key with `--key`). Use it to check glyph clipping / overlaps before flashing. Needs `openpyxl` in addition to Pillow. |
| `dl-demo-fonts.sh` | Downloads the mono Noto Emoji + Symbols2 fonts (only needed for `--font-mode ttf`). |

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -r tools/requirements.txt   # Pillow + fontTools
./tools/dl-demo-fonts.sh                           # only for --font-mode ttf
```

## Run

```bash
.venv/bin/python tools/emoji_demo.py                   # → tools/out/emoji_layer.gif (gfx mode)
.venv/bin/python tools/emoji_demo.py --still --max-pages 3   # quicker, plus a still PNG
.venv/bin/python tools/emoji_demo.py --font-mode ttf --no-bezel --out /tmp/e.gif
.venv/bin/python tools/emoji_demo.py --qmk /path/to/qmk_firmware
```

The frame plan (open on the first tab → sweep every tab, cycling through each
tab's pages with a press-blink on the tabs and `‹ ›` arrows) is a short list near
the bottom of `emoji_demo.py:main()` — retime (`--settle`, `--max-pages`) or
re-point it there.

## How the emoji demo stays in sync with the firmware

`emoji_demo.py` reads, from the `--qmk` checkout:

- `split72/keyboard.json` — arg-index → matrix (`LAYOUT_left_right_stacked`)
- `split72/keymaps/default/keymap.c` — the `[_EMJ]` layer → matrix → key role
  (category tab / emoji slot / page arrow / unused)
- `keyboards/polykybd/emoji/emoji_data.h` — codepoints per category
- `.../emoji/emoji_layer.c` — `emj_tab_icons[]`

So re-ordering categories, adding emojis, or remapping keys is picked up
automatically — nothing in this tool is hand-maintained.

## Reusing the renderer

`kle_render.py` knows nothing about emojis. To animate any other layer or idea,
build your own `{matrix_pos: KeyContent}` dicts:

```python
from kle_render import KleRenderer, KeyContent, GlyphRenderer
r = KleRenderer(json.load(open("polyhost/res/polykybd-split72.json")),
                glyphs=GlyphRenderer([("NotoEmoji.ttf", "mono")]))
frame = {"0,1": KeyContent(glyph="A"), "0,2": KeyContent(glyph="😀", frame="cap")}
r.save_gif([frame], "out.gif", durations=800)
```

`KeyContent(glyph=…, label=…, frame='cap'|'bar', dim=…, selected=…, blank=…)`.

## Rendering modes (`--font-mode`)

- **`gfx` (default)** — pixel-exact: glyphs are blitted from the firmware's
  generated Adafruit-GFX pixel-font headers (`gfx_font.py`), at their native
  size/baseline and via the same `ALL_FONTS` lookup the keyboard uses, so the
  output matches the device exactly (real `ICON_LEFT`/`ICON_RIGHT` arrows
  included). Needs only a `qmk_firmware` checkout — no font download.
- **`ttf`** — live Noto Emoji (monochrome), 1-bit dithered and scaled to fit:
  a faithful *approximation*, not pixel-identical. Needs `dl-demo-fonts.sh`.

`out/` and `assets/fonts/` are generated and git-ignored.
