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
| `lang_demo.py` | Base-layer language tour. `LangBoard` (its `KleRenderer` subclass) takes a pre-rendered `L` image per key via `KeyContent._oled`, which is what makes it reusable as the board renderer for any composed still — see **Composed stills** below. |
| `intl_picker_demo.py` | Walks the Intl variation picker: hold Intl → tap Ctrl → page a letter's variations → pick one → watch that keycap change, lower case then upper. Slots, page arrows and the remap key are read out of the `_ADDLANG1` keymap, so moving a key needs no change here. Also exports `parse_latin_ex_map()` + `render_cps()`, the two helpers every Intl still reuses. |
| `intl_remap_demo.py` | Walks the Intl **letter remap**: two-step prompt (PICKKEY → PICKLTR) onto `q`/`j`/`;`, each then given its own accent, ending on `é è ê ë` across four keys. Mirrors `render_key()`'s blanking rules; inversion is *rendered*, never `kdisp_invert`ed. |
| `intl_remap_hero.py` | The composed **still** for that feature — a French line needing all four accented `e`s, each letter colour-matched and curve-linked to the keycap that types it. `--tail-style {oblique,script,tuned}` picks the subline treatment. |
| `poly_console.py` | Reads the keyboard's QMK HID console (a `hid-listen` equivalent), using only `hid` from polyhost's own deps. **Needed to see anything the firmware prints during a flash**: the update runs under `worker.exclusive()`, which suspends every periodic including the 250 ms console read, and QMK drops output nobody drains — so the FW-2 `FW_UP: image signature OK/INVALID/UNSIGNED` verdict is invisible from the host log. Run it in a second terminal *before* flashing. Also the practical answer to `qmk console` refusing to run outside MSYS2 MinGW64 on Windows. |
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

## Composed stills (post / hero images)

A GIF shows a mechanism; a still is what a post or a social preview leads with.
Both are built the same way, and the rule that matters is:

> **Drive the keycaps from the demo pipeline — never mock them up.**

`intl_remap_hero.py` is the worked example: the board half is `LangBoard` +
`intl_picker_demo.render_cps()` over the firmware's generated `latin_ex_map`, so
the glyphs are the ones the keyboard draws, at the firmware's own baseline. Only
the typography *around* the caps is composed. It also **asserts** what it claims —
that `SENTENCE[idx]` really is that character, and that variation `vi` of the
source letter really is that glyph — so a table change fails the render loudly
instead of shipping an image that quietly lies.

Four things that cost a round each when composing over the board render:

- **Key out the board's background.** `KleRenderer` paints its own `Theme.bg`
  across the whole canvas, so pasting it onto a gradient leaves a flat slab behind
  the caps. Render with a sentinel `bg` that appears nowhere else
  (`Theme(bg=(255, 0, 255))`) and build an alpha mask from it. The renderer does
  not anti-alias its cap edges, so an exact colour compare is safe.
- **PIL does not anti-alias lines, curves or rounded-rect outlines.** Draw them on
  a transparent overlay at 3× and `resize(..., LANCZOS)` down, or connectors look
  like a staircase.
- **Glyphs sit LEFT in the 72×40 panel, not centred** — `render_cps()` draws at
  `BUFFER_X`, which is where the firmware draws picker/legend text. That is
  correct; don't "fix" it.
- **Shadows go under the caps**, so compute the key rects *before* the paste
  (`board._corners_px(board.km[mp])` minus `board.ox/oy`, plus the paste offset).

### Fonts for the surrounding typography

`fc-list` on a plain Linux box gives you **obliques and serif italics only** — no
script/cursive face, and DejaVu ships **no proportional-sans oblique** (only
`DejaVuSansMono-Oblique`). `LiberationSans-Italic.ttf` is the closest italic to the
DejaVu Sans used elsewhere, and is what `--tail-style oblique` (the default) uses.

An OFL script face can be fetched if you want one — `--tail-style script|tuned`
looks for `tools/DancingScript.ttf` and falls back with a warning if it is absent:

```bash
curl -sSLo tools/DancingScript.ttf \
  'https://raw.githubusercontent.com/google/fonts/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf'
```

**Pick a face by rendering the actual line, not by its name** — the same rule this
repo already applies to tray icons. Rendering the real subline is what showed Great
Vibes' hairlines disappearing against the dark ground while Dancing Script held up,
and what showed a script face reads visibly smaller and lighter than a sans at
equal px (smaller x-height) — hence `tuned` existing as a separate style rather than
being folded into `script`.

`out/` and `assets/fonts/` are generated and git-ignored.

## `render_tray_menu.py`

Renders the tray menu (and each submenu) to PNGs for the documentation, from the
**real** `QMenu` the app builds — same labels, icons, order and separators — so a
docs screenshot can be regenerated from the code instead of re-taken by hand.

```sh
xvfb-run -a env QT_QPA_PLATFORM=offscreen \
    .venv/bin/python tools/render_tray_menu.py --out-dir /tmp/menus
```

It runs the GUI in `--connect` client mode against a small fake core reporting a
connected Split72, because a menu rendered with no keyboard attached is entirely
greyed out. `--mode normal|developer|both` (default both).

The X display is only for **pynput** (imported by `host.py`, and it refuses to
load without an X connection); Qt itself renders offscreen, so the `xcb` platform
plugin and its system libraries are not needed.
