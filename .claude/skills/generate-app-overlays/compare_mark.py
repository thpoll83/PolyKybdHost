#!/usr/bin/env python3
"""An overlay set's ESC program mark next to the app's own icon, as the keycap shows them.

One row, four cells, white on black like the OLED:

  1. the app's icon in colour (from a file, or Google's favicon service);
  2. that icon reduced to the mark's size at 1 bit, light pixels lit;
  3. the same, dark pixels lit;
  4. the ESC cell of the generated overlay, the mark that ships.

Columns 2 and 3 show what a faithful conversion of the real logo would look
like, so the maintainer can judge the committed mark against it. Use it when the
maintainer asks to "compare the program icon with the original".

    .venv/bin/python .claude/skills/generate-app-overlays/compare_mark.py \\
        polyhost/res/overlay_sources/<app>/<spec>.yaml --domain <app-site.com> \\
        --out /tmp/<app>_mark.png
    #   --icon <file>      the app's icon as a local file instead of --domain
    #   --platform macos   the macOS set's mark
    #   --luma 128         the split between light and dark for columns 2 and 3

The favicon service (`https://www.google.com/s2/favicons?domain=<d>&sz=256`)
answers for sites that refuse automated requests (canva.com shows a bot check)
and returns the site's apple-touch icon, 180 or 256 px. The download is only
for the comparison; do not commit it.
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preview_black as pb  # noqa: E402

FAVICON = "https://www.google.com/s2/favicons?domain={}&sz=256"
SCALE = 4
FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def _icon(args) -> Image.Image:
    if args.icon:
        img = Image.open(args.icon)
    else:
        req = urllib.request.Request(FAVICON.format(args.domain),
                                     headers={"User-Agent": "PolyKybdHost"})
        with urllib.request.urlopen(req, timeout=60) as r:
            img = Image.open(io.BytesIO(r.read()))
    img = img.convert("RGBA")
    white = Image.new("RGBA", img.size, "white")
    white.alpha_composite(img)
    return white.convert("RGB")


def _cell(mask: np.ndarray) -> Image.Image:
    img = Image.fromarray((mask * 255).astype("uint8"))
    big = img.resize((pb.SLOT_W * SCALE, pb.SLOT_H * SCALE), Image.NEAREST)
    return Image.merge("RGB", [big.point(lambda v, c=c: c if v else b)
                               for c, b in zip(pb.LIT, pb.BG)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec", type=Path)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--domain", help="site whose favicon is the app's icon")
    src.add_argument("--icon", type=Path, help="the app's icon as a local file")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--platform", default=pb.g.PLAT_WINDOWS,
                    choices=[pb.g.PLAT_WINDOWS, pb.g.PLAT_MACOS, pb.g.PLAT_LINUX])
    ap.add_argument("--luma", type=int, default=128)
    ap.add_argument("--res", type=Path, default=pb.ROOT / "polyhost" / "res")
    args = ap.parse_args()

    spec = yaml.safe_load(args.spec.read_text(encoding="utf-8"))
    out = pb._output(spec, args.platform)
    primary = np.array(Image.open(args.res / "overlays" / f"{out}.mods.png").convert("RGBA"))
    ours = pb.cell_of(primary, spec.get("program_icon_key", "ESC"), pb.CH["A"])
    if not ours.any():
        raise SystemExit(f"{out}: the ESC cell is empty")

    # Reduce the icon to the square the mark occupies, right-aligned like ours.
    rw, rh = spec.get("program_icon_region", (pb.SLOT_W, pb.SLOT_H))
    side = min(rw, rh, pb.SLOT_H)
    icon = _icon(args)
    gray = np.asarray(icon.convert("L").resize((side, side), Image.LANCZOS))
    xs = np.nonzero(ours.any(axis=0))[0]
    x0 = min(int(xs.max()) + 1, pb.SLOT_W) - side
    y0 = (pb.SLOT_H - side) // 2

    def placed(m: np.ndarray) -> np.ndarray:
        cell = np.zeros((pb.SLOT_H, pb.SLOT_W), bool)
        cell[y0:y0 + side, x0:x0 + side] = m
        return cell

    w, h = pb.SLOT_W * SCALE, pb.SLOT_H * SCALE
    colour = Image.new("RGB", (w, h), "white")
    thumb = icon.copy()
    thumb.thumbnail((h - 10, h - 10))
    colour.paste(thumb, ((w - thumb.width) // 2, (h - thumb.height) // 2))
    items = [("app icon", colour),
             (f"1-bit, light lit (luma > {args.luma})", _cell(placed(gray > args.luma))),
             (f"1-bit, dark lit (luma <= {args.luma})", _cell(placed(gray <= args.luma))),
             (f"committed ({out})", _cell(ours))]

    pad, top = 12, 30
    sheet = Image.new("RGB", (pad + len(items) * (w + pad), top + h + pad), pb.BG)
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT, 14)
    for i, (label, img) in enumerate(items):
        x = pad + i * (w + pad)
        d.text((x, 8), label, font=font, fill=(220, 220, 220))
        sheet.paste(img, (x, top))
    sheet.save(args.out)
    print(f"{out}: mark sheet {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
