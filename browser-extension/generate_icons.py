#!/usr/bin/env python3
"""Generate the extension icon set from the PolyKybd brand mark + a globe badge.

Reproducible: run from the repo root (or anywhere — paths are resolved relative
to this file) to regenerate icons/icon-{16,32,48,128}.png. Base is the app's
own brand icon (polyhost/res/icons/pcolor.png); a small globe badge in the
bottom-right corner signals the "website reporter" function.

Needs Pillow:  PolyKybdHost/.venv/bin/python browser-extension/generate_icons.py
"""
import pathlib

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
BRAND = HERE.parent / "polyhost" / "res" / "icons" / "pcolor.png"
OUT = HERE / "icons"
SIZES = (16, 32, 48, 128)

# Badge palette: cyan disc, white globe, dark ring (reads on the busy brand art).
BADGE_FILL = (23, 162, 184, 255)     # cyan
BADGE_RING = (10, 30, 40, 255)       # near-black outline
GLOBE = (255, 255, 255, 255)


def _globe_badge(px):
    """A square RGBA badge of side ``px``: cyan disc + simplified globe."""
    ss = 4  # supersample for smooth curves, then downscale
    s = px * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ring = max(1, round(s * 0.06))
    d.ellipse([0, 0, s - 1, s - 1], fill=BADGE_FILL, outline=BADGE_RING, width=ring)

    # Globe: outer circle inset from the disc, one meridian ellipse, one equator.
    pad = round(s * 0.22)
    box = [pad, pad, s - 1 - pad, s - 1 - pad]
    lw = max(1, round(s * 0.05))
    d.ellipse(box, outline=GLOBE, width=lw)
    cx = s / 2
    # Vertical meridian (a narrow ellipse), horizontal equator line.
    mer_w = (box[2] - box[0]) * 0.42
    d.ellipse([cx - mer_w / 2, box[1], cx + mer_w / 2, box[3]], outline=GLOBE, width=lw)
    d.line([box[0], (box[1] + box[3]) / 2, box[2], (box[1] + box[3]) / 2],
           fill=GLOBE, width=lw)
    return img.resize((px, px), Image.LANCZOS)


def build(size):
    base = Image.open(BRAND).convert("RGBA").resize((size, size), Image.LANCZOS)
    # Badge ~46% of the icon, bottom-right, slightly inset.
    bsz = max(7, round(size * 0.46))
    badge = _globe_badge(bsz)
    pos = (size - bsz, size - bsz)
    base.alpha_composite(badge, pos)
    return base


def main():
    OUT.mkdir(exist_ok=True)
    for sz in SIZES:
        img = build(sz)
        img.save(OUT / f"icon-{sz}.png")
        print(f"wrote icons/icon-{sz}.png")


if __name__ == "__main__":
    main()
