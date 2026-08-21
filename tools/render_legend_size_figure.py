#!/usr/bin/env python3
"""Render the docs figure for the keycap legend size (HID cmd 34) — one labelled
row per size, real legends for a real layout.

    python3 tools/render_legend_size_figure.py \
        --lang fr-FR --keys KC_2,KC_7,KC_9,KC_0,KC_Q \
        --out ../polykybd-docs/src/assets/using/legend-sizes-french.png

Draws through oled_preview's `render_key`, so what it shows is what the 72x40
keycap OLED shows — including the Shift and AltGr previews, which is the point of
picking a real layout: they visibly stay put while the main legend grows.

The palette and the rounded outline match the sibling figure
`src/assets/using/legend-sizes.png` so the two read as one set. Keep them matching
if either is regenerated.

⚠️ Check the cells before shipping the image — `--check` reports clipped pixels and
element overlap per cell and exits non-zero on either. A figure of a defect is
worse than no figure, and the previews sit close enough to the legend at the big
sizes that this is a real risk (see plan_main_legend's AltGr push-clear).

⚠️ `render_key` returns the panel PLUS a 2 px `OVERSHOOT` margin on every side —
(76, 44), not (72, 40) — so that ink drawn outside the panel stays visible. The
panel occupies cols/rows `OVERSHOOT .. OVERSHOOT + OLED_* - 1`; reading from 0
shifts the whole cell up-left by 2 px AND chops the panel's last two columns. That
is invisible on a glyph sitting away from the edge and obvious on one that reaches
it — fr-FR's AltGr `@` ends on column 71 and lost its right edge, reading as an
oversized glyph spilling out of the keycap. `_panel_pixels` asserts the returned
size so a change to OVERSHOOT cannot silently re-introduce the offset.

⚠️ The keycap outline is drawn in a MARGIN around the panel, never on top of it.
A glyph may legitimately ink the outermost column — fr-FR's AltGr `@` ends on
column 71 of 0..71 — so a border stroked at the cell edge paints over it, and the
glyph reads as an oversized one spilling out of the frame. That is a defect of the
figure, not of the firmware, and it is invisible in a figure whose glyphs happen to
sit away from the edge (the sibling sample-letter figure never shows it).
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gfx_font import load_all_fonts                                    # noqa: E402
from oled_preview import (Lang, Renderer, load_named_glyphs, render_key,  # noqa: E402
                          ROW, OLED_W, OLED_H, OVERSHOOT)

BG, KEY_BG, INK, BORDER, LABEL = (17, 18, 22), (6, 8, 12), (168, 216, 255), (58, 62, 72), (190, 195, 205)
ROWS = [(0, "Small  (default)"), (1, "Medium"), (2, "Large")]
SCALE, PAD, GAP, LBL_H, RADIUS = 4, 26, 24, 26, 14
FRAME = 6          # margin the outline lives in, so it never overdraws panel ink


def _panel_pixels(img):
    """The 72x40 panel out of render_key's overshoot-padded image (see the note above)."""
    want = (OLED_W + 2 * OVERSHOOT, OLED_H + 2 * OVERSHOOT)
    if img.size != want:
        sys.exit(f"render_key returned {img.size}, expected {want} — the panel offset "
                 f"below assumes OVERSHOOT={OVERSHOOT} padding on every side")
    return img.convert("L").load()


def load(fw: str):
    L = Lang(f"{fw}/lang/lang_lut.xlsx", load_named_glyphs(f"{fw}/lang/named_glyphs.h"))
    return L, Renderer(load_all_fonts(f"{fw}/base/fonts"))


def check(L, R, lang: str, keys) -> int:
    bad = 0
    for kc in keys:
        for size, name in ROWS:
            rep = {}
            render_key(L, R, lang, kc, False, False, report=rep, size=size)
            clip, ov = sum(rep["oob"].values()), rep["overlap"]
            if clip or ov:
                bad += 1
                print(f"  {lang} {kc:16s} {name:16s} clipped={clip} overlap={ov}")
    print(f"{'FAIL' if bad else 'OK'}: {len(keys) * 3} cells checked, {bad} with a defect")
    return 1 if bad else 0


def render(L, R, lang: str, keys, out: str) -> None:
    from PIL import Image, ImageDraw, ImageFont
    kw, kh = OLED_W * SCALE, OLED_H * SCALE
    cw, ch = kw + 2 * FRAME, kh + 2 * FRAME        # panel + the outline's margin
    W = PAD * 2 + len(keys) * cw + (len(keys) - 1) * GAP
    H = PAD * 2 + len(ROWS) * (LBL_H + ch + GAP) - GAP
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    y = PAD
    for size, label in ROWS:
        d.text((PAD, y), label, fill=LABEL, font=font)
        y += LBL_H
        x = PAD
        for kc in keys:
            src = _panel_pixels(render_key(L, R, lang, kc, False, False, size=size))
            cell = Image.new("RGB", (kw, kh), KEY_BG)
            cd = ImageDraw.Draw(cell)
            for yy in range(OLED_H):
                for xx in range(OLED_W):
                    if src[xx + OVERSHOOT, yy + OVERSHOOT]:
                        cd.rectangle([xx * SCALE, yy * SCALE,
                                      xx * SCALE + SCALE - 1, yy * SCALE + SCALE - 1], fill=INK)
            d.rounded_rectangle([x, y, x + cw - 1, y + ch - 1],
                                radius=RADIUS, fill=KEY_BG, outline=BORDER, width=2)
            img.paste(cell, (x + FRAME, y + FRAME))   # ink inside the margin, never under it
            x += cw + GAP
        y += ch + GAP
    img.save(out)
    print(f"wrote {out} {img.size}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fw", default=os.path.join(os.path.dirname(os.path.dirname(HERE)),
                                                 "qmk_firmware", "keyboards", "polykybd"))
    ap.add_argument("--lang", default="fr-FR")
    ap.add_argument("--keys", default="KC_2,KC_7,KC_9,KC_0,KC_Q")
    ap.add_argument("--out", help="PNG to write; omit to only --check")
    ap.add_argument("--check", action="store_true", help="report clipping/overlap per cell")
    a = ap.parse_args()
    keys = [k if k.startswith("KC_") else f"KC_{k}" for k in a.keys.split(",")]
    unknown = [k for k in keys if k not in ROW]
    if unknown:
        sys.exit(f"unknown keycode(s): {', '.join(unknown)}")
    L, R = load(a.fw)
    if a.lang not in L.langs:
        sys.exit(f"unknown layout {a.lang!r}")
    rc = check(L, R, a.lang, keys) if (a.check or not a.out) else 0
    if a.out:
        render(L, R, a.lang, keys, a.out)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
