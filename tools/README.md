# tools — keycap demo renderer

Render promo images / animated GIFs of the PolyKybd per-keycap OLEDs, laid out
from the **same KLE file the layout editor uses**
(`polyhost/res/polykybd-split72.json`). The first consumer is an emoji-layer
walk-through, but the renderer is generic — you tell it, per frame, what each
keycap should show.

## Files

| File | Role |
|------|------|
| `kle_render.py` | Reusable renderer. Reuses `polyhost.kle.kle_praser.parse_kle`, lays out the keyboard (rotated thumb cluster included), and draws each key as a dark cap with a 72×40 monochrome "OLED". Per-frame API is `{matrix_pos: KeyContent}`; `save_gif()` writes the animation. |
| `emoji_demo.py` | Data-driven driver for the emoji layer. Pulls geometry + roles + glyphs straight from the firmware so the demo always matches the keyboard. |
| `dl-demo-fonts.sh` | Downloads the mono Noto Emoji + Symbols2 fonts the renderer uses. |

## Setup

```bash
python -m venv .venv
.venv/bin/pip install Pillow fonttools
./tools/dl-demo-fonts.sh            # → ~/.cache/emojigif/fonts
```

## Run

```bash
.venv/bin/python tools/emoji_demo.py                   # → tools/out/emoji_layer.gif
.venv/bin/python tools/emoji_demo.py --unit 96 --still # bigger, plus a still PNG
.venv/bin/python tools/emoji_demo.py --no-bezel --scale 0.8 --out /tmp/e.gif
.venv/bin/python tools/emoji_demo.py --qmk /path/to/qmk_firmware
```

The frame plan (linger → sweep every tab → page through the first category so the
◀ / ▶ arrows light up) is a short list near the bottom of `emoji_demo.py:main()`
— retime it or point it at a different "hero" category there.

## How the emoji demo stays in sync with the firmware

`emoji_demo.py` reads, from the `--qmk` checkout:

- `split72/keyboard.json` — arg-index → matrix (`LAYOUT_left_right_stacked`)
- `split72/keymaps/default/keymap.c` — the `[_EMJ]` layer → matrix → key role
  (category tab / emoji slot / page arrow / unused)
- `keyboards/handwired/polykybd/emoji/emoji_data.h` — codepoints per category
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

## Fidelity note

Glyphs are rendered from Noto Emoji (monochrome) and 1-bit dithered — a faithful
*approximation* of the keycaps, not the exact pixel fonts the firmware ships. For
pixel-exact output the same `KeyContent` path could blit the real generated GFX
bitmaps instead.

`out/` and `assets/fonts/` are generated and git-ignored.
