#!/usr/bin/env python3
"""Candidate icons for one key, drawn the way the keycap shows them.

Renders each `fa:<name>` (Font Awesome Free) or `gi:<author>/<name>`
(game-icons.net) candidate, fits it into the key's area, places it at the right
of a 72 x 40 cell (bottom or vertically centred) and draws the sheet white on
black, as the OLED shows it, with the firmware legend's corner marked. A name
that does not exist is reported and skipped: many guessed game-icons.net names
return 404, so list several. Material Symbols (`ms:`) names are not taken here.

    .venv/bin/python .claude/skills/generate-app-overlays/icon_candidates.py \\
        --area 34x40 --legend F2 --out /tmp/f2.png \\
        fa:person-military-rifle gi:lorc/rally-the-troops gi:lorc/battle-gear

    --current icons/army.png   draw the committed icon first, labelled "now"
    --block 2                  draw in 2 px blocks (half size, each pixel doubled)
    --anchor bottom            bottom-right instead of centred at the right

Put the current icon first so the sheet compares against it.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402

LIT = (235, 240, 255)
BG = (28, 28, 28)


def fit(alpha: Image.Image, box: tuple[int, int]) -> np.ndarray:
    """The ink of `alpha` scaled to fit `box` (w, h), 1-bit."""
    a = alpha.crop(alpha.getbbox())
    s = min(box[0] / a.width, box[1] / a.height)
    a = a.resize((max(1, round(a.width * s)), max(1, round(a.height * s))), Image.LANCZOS)
    return np.asarray(a) > 150


def place(m: np.ndarray, anchor: str) -> np.ndarray:
    cell = np.zeros((40, 72), bool)
    y = 40 - m.shape[0] if anchor == "bottom" else (40 - m.shape[0]) // 2
    cell[y:y + m.shape[0], 72 - m.shape[1]:] = m
    return cell


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("specs", nargs="+", help="fa:<name> or gi:<author>/<name>")
    ap.add_argument("--area", default="40x40", help="the key's icon area, WxH (default 40x40)")
    ap.add_argument("--anchor", choices=["right", "bottom"], default="right")
    ap.add_argument("--block", type=int, default=1, help="draw in N px blocks")
    ap.add_argument("--current", type=Path, help="the committed icon PNG, drawn first")
    ap.add_argument("--legend", default="", help="the key's legend, marked top-left")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    w, h = (int(v) for v in a.area.lower().split("x"))
    if w % a.block or h % a.block:
        raise SystemExit(f"--area {a.area} is not a multiple of --block {a.block}")
    box = (w // a.block, h // a.block)
    items = []
    if a.current:
        m = np.asarray(Image.open(a.current).convert("RGBA").getchannel("A")) > 127
        ys, xs = np.nonzero(m)
        items.append((f"now: {a.current.name}", place(m[ys.min():ys.max() + 1, xs.min():xs.max() + 1], a.anchor)))
    with tempfile.TemporaryDirectory() as tmp:
        for spec in a.specs:
            stem = spec.replace(":", "_").replace("/", "_")
            try:
                cnc.render({stem: spec}, Path(tmp))
            except Exception as e:                       # a 404 or an unknown prefix
                print(f"skipped {spec}: {type(e).__name__}: {e}")
                continue
            m = fit(Image.open(Path(tmp) / f"{stem}.png").convert("RGBA").getchannel("A"), box)
            if a.block > 1:
                m = np.kron(m, np.ones((a.block, a.block), bool))
            items.append((spec, place(m, a.anchor)))
    if not items:
        raise SystemExit("no candidate rendered")
    scale, cols = 3, 4
    cw, chh = 72 * scale, 40 * scale
    rows = (len(items) + cols - 1) // cols
    im = Image.new("RGB", (cols * (cw + 8) + 8, rows * (chh + 22) + 8), BG)
    d = ImageDraw.Draw(im)
    for i, (label, cell) in enumerate(items):
        x, y = 8 + (i % cols) * (cw + 8), 6 + (i // cols) * (chh + 22)
        d.text((x, y), label[:42], fill=(120, 220, 120))
        rgb = np.zeros((40, 72, 3), np.uint8)
        rgb[cell] = LIT
        tile = Image.fromarray(rgb).resize((cw, chh), Image.NEAREST)
        if a.legend:
            ImageDraw.Draw(tile).text((6, 4), a.legend, fill=(200, 60, 60))
        im.paste(tile, (x, y + 14))
    im.save(a.out)
    print(f"{len(items)} candidates, sheet {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
