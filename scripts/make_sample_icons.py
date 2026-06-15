#!/usr/bin/env python3
"""Draw a small starter set of monochrome shortcut icons for the overlay generator.

These are deliberately simple white-on-transparent glyphs (the alpha channel is
the shape) so generate_app_overlays.py renders them as clean 1-bit stamps. They
are meant as *replaceable templates* - drop your own PNGs with the same filenames
into the icons dir to override any of them.

    python scripts/make_sample_icons.py polyhost/res/overlay_sources/icons
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

SS = 4          # supersample factor for smooth edges
S = 48          # final icon size (square); the generator scales to the cell region
W = 255         # white
LW = 3 * SS     # nominal stroke width


def _canvas():
    img = Image.new("RGBA", (S * SS, S * SS), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _finish(img):
    return img.resize((S, S), Image.LANCZOS)


def _line(d, pts, width=LW):
    d.line(pts, fill=(W, W, W, W), width=width, joint="curve")


def _rect(d, box, width=LW):
    d.rectangle(box, outline=(W, W, W, W), width=width)


def _poly(d, pts, fill=False, width=LW):
    if fill:
        d.polygon(pts, fill=(W, W, W, W))
    else:
        d.line(pts + [pts[0]], fill=(W, W, W, W), width=width, joint="curve")


def _arc(d, box, start, end, width=LW):
    d.arc(box, start, end, fill=(W, W, W, W), width=width)


def save(d):
    u = S * SS
    _rect(d, [u * 0.12, u * 0.12, u * 0.88, u * 0.88])
    _poly(d, [(u * 0.7, u * 0.12), (u * 0.7, u * 0.32), (u * 0.3, u * 0.32), (u * 0.3, u * 0.12)])
    _rect(d, [u * 0.32, u * 0.55, u * 0.68, u * 0.82])


def saveall(d):
    save(d)
    u = S * SS
    _line(d, [(u * 0.78, u * 0.7), (u * 0.78, u * 0.92)], width=LW - SS)
    _line(d, [(u * 0.67, u * 0.81), (u * 0.89, u * 0.81)], width=LW - SS)


def new(d):
    u = S * SS
    _poly(d, [(u * 0.22, u * 0.1), (u * 0.62, u * 0.1), (u * 0.78, u * 0.28),
              (u * 0.78, u * 0.9), (u * 0.22, u * 0.9)])
    _poly(d, [(u * 0.62, u * 0.1), (u * 0.62, u * 0.28), (u * 0.78, u * 0.28)])


def open_folder(d):
    u = S * SS
    _poly(d, [(u * 0.1, u * 0.28), (u * 0.4, u * 0.28), (u * 0.5, u * 0.4),
              (u * 0.9, u * 0.4), (u * 0.9, u * 0.82), (u * 0.1, u * 0.82)])


def _magnifier(d, cx=0.42, cy=0.42, r=0.26):
    u = S * SS
    _arc(d, [u * (cx - r), u * (cy - r), u * (cx + r), u * (cy + r)], 0, 360)
    _line(d, [(u * (cx + r * 0.7), u * (cy + r * 0.7)), (u * 0.86, u * 0.86)])


def find(d):
    _magnifier(d)


def findnext(d):
    _magnifier(d, cx=0.38, cy=0.42, r=0.24)
    u = S * SS
    _line(d, [(u * 0.6, u * 0.5), (u * 0.9, u * 0.5)], width=LW - SS)
    _poly(d, [(u * 0.82, u * 0.4), (u * 0.94, u * 0.5), (u * 0.82, u * 0.6)], fill=True)


def replace(d):
    _magnifier(d, cx=0.4, cy=0.38, r=0.22)
    u = S * SS
    _line(d, [(u * 0.5, u * 0.72), (u * 0.9, u * 0.72)], width=LW - SS)
    _line(d, [(u * 0.5, u * 0.86), (u * 0.78, u * 0.86)], width=LW - SS)


def findfiles(d):
    u = S * SS
    _rect(d, [u * 0.5, u * 0.5, u * 0.86, u * 0.9], width=LW - SS)
    _magnifier(d, cx=0.4, cy=0.4, r=0.26)


def copy(d):
    u = S * SS
    _rect(d, [u * 0.18, u * 0.18, u * 0.62, u * 0.62])
    _rect(d, [u * 0.38, u * 0.38, u * 0.82, u * 0.82])


def cut(d):
    u = S * SS
    _arc(d, [u * 0.12, u * 0.6, u * 0.36, u * 0.84], 0, 360)
    _arc(d, [u * 0.12, u * 0.16, u * 0.36, u * 0.4], 0, 360)
    _line(d, [(u * 0.32, u * 0.36), (u * 0.86, u * 0.78)])
    _line(d, [(u * 0.32, u * 0.64), (u * 0.86, u * 0.22)])


def paste(d):
    u = S * SS
    _rect(d, [u * 0.18, u * 0.2, u * 0.82, u * 0.9])
    _rect(d, [u * 0.36, u * 0.1, u * 0.64, u * 0.24])


def undo(d):
    u = S * SS
    _arc(d, [u * 0.2, u * 0.25, u * 0.8, u * 0.85], 200, 20)
    _poly(d, [(u * 0.18, u * 0.3), (u * 0.34, u * 0.28), (u * 0.3, u * 0.5)], fill=True)


def redo(d):
    u = S * SS
    _arc(d, [u * 0.2, u * 0.25, u * 0.8, u * 0.85], 160, 340)
    _poly(d, [(u * 0.82, u * 0.3), (u * 0.66, u * 0.28), (u * 0.7, u * 0.5)], fill=True)


def selectall(d):
    u = S * SS
    step = u * 0.16
    for i in range(0, 6):
        x = u * 0.12 + i * step
        _line(d, [(x, u * 0.12), (x + step * 0.6, u * 0.12)], width=LW - SS)
        _line(d, [(x, u * 0.88), (x + step * 0.6, u * 0.88)], width=LW - SS)
    for i in range(0, 5):
        y = u * 0.12 + i * step
        _line(d, [(u * 0.12, y), (u * 0.12, y + step * 0.6)], width=LW - SS)
        _line(d, [(u * 0.88, y), (u * 0.88, y + step * 0.6)], width=LW - SS)


def goto(d):
    u = S * SS
    _line(d, [(u * 0.85, u * 0.15), (u * 0.85, u * 0.85)], width=LW - SS)
    _line(d, [(u * 0.12, u * 0.5), (u * 0.7, u * 0.5)])
    _poly(d, [(u * 0.6, u * 0.36), (u * 0.78, u * 0.5), (u * 0.6, u * 0.64)], fill=True)


def duplicate(d):
    u = S * SS
    _rect(d, [u * 0.16, u * 0.16, u * 0.66, u * 0.5])
    _rect(d, [u * 0.34, u * 0.5, u * 0.84, u * 0.84])


def deleteline(d):
    u = S * SS
    _line(d, [(u * 0.12, u * 0.4), (u * 0.6, u * 0.4)])
    _line(d, [(u * 0.12, u * 0.6), (u * 0.5, u * 0.6)])
    _line(d, [(u * 0.66, u * 0.66), (u * 0.9, u * 0.9)])
    _line(d, [(u * 0.9, u * 0.66), (u * 0.66, u * 0.9)])


def comment(d):
    u = S * SS
    _line(d, [(u * 0.42, u * 0.22), (u * 0.22, u * 0.78)])
    _line(d, [(u * 0.72, u * 0.22), (u * 0.52, u * 0.78)])


def printer(d):
    u = S * SS
    _rect(d, [u * 0.16, u * 0.4, u * 0.84, u * 0.72])
    _poly(d, [(u * 0.28, u * 0.4), (u * 0.28, u * 0.16), (u * 0.72, u * 0.16), (u * 0.72, u * 0.4)])
    _rect(d, [u * 0.3, u * 0.66, u * 0.7, u * 0.9])


def close(d):
    u = S * SS
    _line(d, [(u * 0.2, u * 0.2), (u * 0.8, u * 0.8)])
    _line(d, [(u * 0.8, u * 0.2), (u * 0.2, u * 0.8)])


def run(d):
    u = S * SS
    _poly(d, [(u * 0.28, u * 0.18), (u * 0.82, u * 0.5), (u * 0.28, u * 0.82)], fill=True)


ICONS = {
    "save": save, "saveall": saveall, "new": new, "open": open_folder,
    "find": find, "findnext": findnext, "replace": replace, "findfiles": findfiles,
    "copy": copy, "cut": cut, "paste": paste, "undo": undo, "redo": redo,
    "selectall": selectall, "goto": goto, "duplicate": duplicate,
    "deleteline": deleteline, "comment": comment, "print": printer,
    "close": close, "run": run,
}


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("icons")
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in ICONS.items():
        img, d = _canvas()
        fn(d)
        _finish(img).save(out / f"{name}.png")
    print(f"Wrote {len(ICONS)} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
