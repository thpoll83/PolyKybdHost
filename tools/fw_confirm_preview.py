#!/usr/bin/env python3
"""Preview the FW-2 unsigned-firmware confirmation prompt on a whole split72.

Renders what the keyboard actually shows while it waits for you to accept or
reject an unsigned image: every keycap dark except the two home-row index keys
(a big **A** on the left half, **R** on the right), with each half's status OLED
stating the question above it.

Both surfaces come from the firmware's own composition rules rather than a
mock-up:

  * the keycaps mirror ``render_fw_confirm_key()`` (poly_keymap.c) — a 2x letter
    centred in the space above a caption whose lowest lit pixel is pinned to the
    last screen row;
  * the status panels call ``build_fw_confirm_panel()`` in the qmk repo's
    ``status_oled_preview.py``, which mirrors ``oled_fw_confirm_screen()``;
  * both draw glyphs through that tool's column-native reader, so the pixels are
    the ones the panels light.

Usage:
    python3 tools/fw_confirm_preview.py [--qmk DIR] [--out PNG] [--scale N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)

# Keycap geometry — the visible window of a per-key OLED (base/disp_array.h).
SCREEN_W, SCREEN_H = 72, 40

# Which key carries the prompt, from poly_keymap.c's FW_CONFIRM_ROW/COL. It is a
# LOCAL matrix position on each half; the right half's rows are offset by 5 in
# the full matrix (left = rows 0-4, right = 5-9).
FW_CONFIRM_ROW, FW_CONFIRM_COL = 2, 3
RIGHT_ROW_OFFSET = 5

ACCEPT_MP = f"{FW_CONFIRM_ROW},{FW_CONFIRM_COL}"
REJECT_MP = f"{FW_CONFIRM_ROW + RIGHT_ROW_OFFSET},{FW_CONFIRM_COL}"

# Sentinels handed to KleRenderer as "glyphs"; the shim below returns the
# pre-composed keycap for each instead of looking anything up in a font.
CH_ACCEPT, CH_REJECT = "\x01", "\x02"


def render_confirm_keycap(accept: bool, S) -> Image.Image:
    """Mirror of render_fw_confirm_key() — returns a 72x40 'L' image.

    Everything is measured from the font metrics rather than hardcoded, exactly
    as the firmware does it: "REJECT" descends below the baseline (the J) where
    "ACCEPT" does not, so a fixed bottom baseline would clip one of them.
    """
    disp, small, _icons, tiny, _globe = S.load_fonts()
    letter = "A" if accept else "R"
    caption = "ACCEPT" if accept else "REJECT"

    img = Image.new("L", (SCREEN_W, SCREEN_H), 0)
    px = img.load()

    def setp(x, y):
        if 0 <= x < SCREEN_W and 0 <= y < SCREEN_H:
            px[x, y] = 255

    # Caption: pin its lowest lit pixel to the last screen row.
    cps = S.s2cp(caption)
    cxmin, cxmax, cymin, cymax = S.text_bbox(tiny, cps)
    cap_base = SCREEN_H - 1 - cymax
    S.draw(setp, tiny, (SCREEN_W - (cxmax - cxmin + 1)) // 2 - cxmin, cap_base, cps)

    # The big letter, doubled, centred in what is left above the caption.
    f, bm, gl = disp
    cp = ord(letter)
    if not (f["first"] <= cp <= f["last"]):
        raise SystemExit(f"{letter!r} missing from the Mid font")
    g = gl[cp - f["first"]]
    lw, lh = g["w"] * 2, g["h"] * 2
    free_rows = cap_base + cymin
    ox = (SCREEN_W - lw) // 2
    oy = (free_rows - lh) // 2
    # kdisp_draw_glyph_double_at: column-native source, each source pixel becomes
    # a 2x2 block; the literal top-left of the INK, no baseline align.
    cb = (g["h"] + 7) >> 3
    for sx in range(g["w"]):
        col = g["off"] + sx * cb
        for sy in range(g["h"]):
            if bm[col + (sy >> 3)] & (1 << (sy & 7)):
                for dx in range(2):
                    for dy in range(2):
                        setp(ox + sx * 2 + dx, oy + sy * 2 + dy)
    return img


class _PromptGlyphs:
    """Stands in for kle_render.GlyphRenderer: hands back the pre-composed
    prompt keycaps for the two sentinels and a blank OLED for anything else."""

    def __init__(self, S):
        self._cap = {CH_ACCEPT: render_confirm_keycap(True, S),
                     CH_REJECT: render_confirm_keycap(False, S)}

    def render(self, ch: str, scale: float = 1.0) -> Image.Image:
        return self._cap.get(ch) or Image.new("L", (SCREEN_W, SCREEN_H), 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--qmk", default=os.path.join(os.path.dirname(HOST_REPO), "qmk_firmware"))
    ap.add_argument("--kle", default=os.path.join(HOST_REPO, "polyhost", "res", "polykybd-split72.json"))
    ap.add_argument("--out", default="/tmp/fw_confirm_preview.png")
    ap.add_argument("--unit", type=int, default=72, help="pixels per key unit")
    ap.add_argument("--gap", type=int, default=10, help="gap between the halves, px")
    ap.add_argument("--margin", type=int, default=5)
    ap.add_argument("--exclude", default="3,7;8,0", help="matrix positions with no display")
    ap.add_argument("--oled-scale", type=int, default=3, help="status-OLED pixel scale")
    ap.add_argument("--no-bezel", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(args.qmk, "keyboards", "polykybd", "tools"))
    import status_oled_preview as S           # noqa: E402  (path set above)
    from kle_render import KleRenderer, KeyContent, Theme   # noqa: E402

    theme = Theme()
    glyphs = _PromptGlyphs(S)
    renderer = KleRenderer(json.load(open(args.kle, encoding="utf-8")),
                           unit=args.unit, glyphs=glyphs, bezel=not args.no_bezel,
                           margin=args.margin, dither=False,
                           exclude={m.strip() for m in args.exclude.split(";") if m.strip()})
    renderer.compact_halves(lambda mp: "L" if int(mp.split(",")[0]) < 5 else "R", gap_px=args.gap)

    # The board IS the dialog: every other key is swallowed and dark.
    contents = {mp: KeyContent(blank=True) for mp in renderer.km}
    for mp, ch in ((ACCEPT_MP, CH_ACCEPT), (REJECT_MP, CH_REJECT)):
        if mp not in renderer.km:
            raise SystemExit(f"prompt key {mp} is not in the KLE — check FW_CONFIRM_ROW/COL")
        contents[mp] = KeyContent(glyph=ch)
    kb = renderer.render_frame(contents)

    # Status OLEDs, one per half, each naming its own key.
    _d, small, _i, _t, _g = S.load_fonts()
    panels = [S.render_plain(S.build_fw_confirm_panel(side, small), sc=args.oled_scale)
              for side in ("L", "R")]

    # Pair each panel with an enlarged view of ITS key: at board scale a single
    # 72x40 keycap is too small to read, and the whole point is what those two
    # keys show.
    def chip(img):
        sc = args.oled_scale
        rgb = Image.new("RGB", (SCREEN_W * sc, SCREEN_H * sc), S.OFF)
        px, out_px = img.load(), rgb.load()
        for y in range(SCREEN_H):
            for x in range(SCREEN_W):
                if px[x, y]:
                    for dy in range(sc):
                        for dx in range(sc):
                            out_px[x * sc + dx, y * sc + dy] = S.ON
        return rgb

    caps = [chip(glyphs._cap[ch]) for ch in (CH_ACCEPT, CH_REJECT)]

    pad, gap = 18, 16
    pw, ph = panels[0].size
    cw, ch_ = caps[0].size
    band = max(ph, ch_) + pad
    group_w = cw + gap + pw
    out = Image.new("RGB", (max(kb.width, group_w * 2 + 3 * pad), kb.height + band), theme.bg)
    kb_x = (out.width - kb.width) // 2

    for i, (cap, panel) in enumerate(zip(caps, panels)):
        gx = (out.width // 4 if i == 0 else out.width * 3 // 4) - group_w // 2
        out.paste(cap, (gx, pad // 2 + (band - pad - ch_) // 2))
        out.paste(panel, (gx + cw + gap, pad // 2 + (band - pad - ph) // 2))
    out.paste(kb, (kb_x, band))

    out.save(args.out)
    print(f"wrote {args.out}  ({out.width}x{out.height})")
    print(f"  ACCEPT keycap at matrix {ACCEPT_MP}, REJECT at {REJECT_MP}")


if __name__ == "__main__":
    main()
