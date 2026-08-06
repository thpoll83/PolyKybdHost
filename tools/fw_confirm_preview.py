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

from PIL import Image, ImageDraw

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

# --- status OLED, at its real place and size -------------------------------
# Measured off the PCBs (poly_kybd_split72_{left,right}.kicad_pcb): a unique
# 24.84 x 14.04 mm Eco2.User rectangle, mirrored between the halves, sitting at
# each half's top INNER corner. 24.84/128 == 14.04/64 == 0.194 mm/px, i.e. square
# pixels — which is what identifies it as the active area rather than the module
# outline. Converted to key units against the socket grid (19.05 mm/U, anchored
# on the second column and the top row, since the outermost column's gap differs
# slightly between the KLE artwork and the board).
# The surrounding bezel is the plate's 27 x 26 mm module opening
# (poly_kybd_split72_plate_*.kicad_pcb; the plate is drawn mirrored relative to
# the board, which is why its cutout looks like it sits on the outer edge).
OLED_ACTIVE_U = {"L": (7.817, 0.360, 9.121, 1.097),
                 "R": (11.879, 0.360, 13.183, 1.097)}
MODULE_MM = (27.0, 26.0)      # plate cutout
ACTIVE_TOP_INSET_MM = 2.51    # active-area top below the module top
MM_PER_U = 19.05


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


def module_rect_bounds(active):
    """Module (bezel) rect in key units around an active-area rect."""
    x0, y0, x1, y1 = active
    mw, mh = MODULE_MM[0] / MM_PER_U, MODULE_MM[1] / MM_PER_U
    cx = (x0 + x1) / 2
    top = y0 - ACTIVE_TOP_INSET_MM / MM_PER_U
    return (cx - mw / 2, top, cx + mw / 2, top + mh)


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
    ap.add_argument("--status-oled", action="store_true",
                    help="draw the status OLEDs at their real PCB position and size")
    ap.add_argument("--oled-gap", type=float, default=0.30,
                    help="clearance between the two OLED modules, in key units "
                         "(--status-oled only; the halves are moved apart to make room)")
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
                           exclude={m.strip() for m in args.exclude.split(";") if m.strip()},
                           panels=[module_rect_bounds(OLED_ACTIVE_U[s_]) for s_ in ("L", "R")]
                                  if args.status_oled else None)
    active = dict(OLED_ACTIVE_U)
    if args.status_oled:
        # The OLEDs live in the inner gap, so the halves are spaced by what the
        # two modules need rather than by the key gap: slide the right half (and
        # its panel rects, which are not part of the key map) until the modules
        # clear each other by --oled-gap.
        ml, mr = module_rect_bounds(active["L"]), module_rect_bounds(active["R"])
        delta = (mr[0] - ml[2]) - args.oled_gap
        if delta > 0:
            for mp, p_ in renderer.km.items():
                if int(mp.split(",")[0]) >= 5:
                    p_["x"] -= delta
                    p_["rx"] -= delta
            x0, y0, x1, y1 = active["R"]
            active["R"] = (x0 - delta, y0, x1 - delta, y1)
            renderer.panels = [module_rect_bounds(active[s_]) for s_ in ("L", "R")]
            renderer._geom()
    else:
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

    # Bezel: the module opening, with the active area inset at its real offset.
    module_rect = module_rect_bounds
    out = kb
    if args.status_oled:
        d = ImageDraw.Draw(out)
        for side, panel in zip(("L", "R"), panels):
            mx0, my0, mx1, my1 = renderer.panel_box_px(module_rect(active[side]))
            # Same body/outline as a keycap, so the module reads as part of the
            # board rather than a floating black box.
            d.rounded_rectangle([mx0, my0, mx1, my1], radius=max(2, (mx1 - mx0) // 18),
                                fill=theme.key_bg, outline=theme.key_outline, width=2)
            ax0, ay0, ax1, ay1 = renderer.panel_box_px(active[side])
            out.paste(panel.resize((max(1, ax1 - ax0), max(1, ay1 - ay0)), Image.NEAREST), (ax0, ay0))

    out.save(args.out)
    print(f"wrote {args.out}  ({out.width}x{out.height})")
    print(f"  ACCEPT keycap at matrix {ACCEPT_MP}, REJECT at {REJECT_MP}")


if __name__ == "__main__":
    main()
