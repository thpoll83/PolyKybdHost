#!/usr/bin/env python3
"""Generate the PolyKybd brand icon set (SVG masters + PNG/ICO/ICNS).

The mark is a 6x6 keycap grid whose UNLIT keys spell a "P" in negative space;
the lit keys carry one continuous blue -> cyan gradient across the grid. The
geometry is the 64x64 original's, scaled to a 1024 unit viewBox, so the new art
is the same silhouette at any resolution.

Everything under polyhost/res/icons/p{color,gray,think,warn}.* is written by
this script -- edit the constants here, never the PNGs.

    python3 tools/gen_brand_icons.py            # write SVG + PNG + ICO + ICNS
    python3 tools/gen_brand_icons.py --sheet X  # contact sheet to X, write nothing
"""
import argparse
import pathlib
import struct

import cairosvg
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ICONS = HERE.parent / "polyhost" / "res" / "icons"

# --- geometry (1024 unit viewBox, proportions taken from the 64px original) ---
S = 1024
BODY_INSET = 16
BODY_R = 48              # edgier than the original's ~160
AREA_INSET = 112          # key grid margin from the canvas edge
PITCH = (S - 2 * AREA_INSET) / 6
KEY = PITCH * 0.875
KEY_R = KEY * 0.12

# The mark: 1 = lit key, 0 = dark. The zeros spell a "P".
GRID = [
    "111111",
    "100001",
    "101101",
    "100001",
    "101111",
    "111111",
]

# "HOST" stamped out of the four rightmost keys of the bottom row, as a 3x5
# pixel font so it needs no typeface and matches the keycap grid it sits in.
STAMP_ROW = 5
STAMP_COLS = (2, 3, 4, 5)
STAMP_TEXT = "HOST"
PIXEL_FONT = {
    "H": ("101", "101", "111", "101", "101"),
    "O": ("111", "101", "101", "101", "111"),
    "S": ("111", "100", "111", "001", "111"),
    "T": ("111", "010", "010", "010", "010"),
}

PNG_SIZES = (16, 20, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 20, 24, 32, 48, 64, 128, 256)
ICNS_SIZES = (16, 32, 64, 128, 256, 512, 1024)
LADDER_SIZES = (16, 24, 32, 48, 64, 128, 256)

# Below this the stamped letters are mush rather than detail -- measured: clean
# at 128+, legible at 96, unreadable at 64. So the small renders come from the
# UNSTAMPED master and the mark stays a clean grid at tray sizes.
STAMP_MIN_SIZE = 128


def _keys():
    for r, row in enumerate(GRID):
        for c, ch in enumerate(row):
            x = AREA_INSET + c * PITCH + (PITCH - KEY) / 2
            y = AREA_INSET + r * PITCH + (PITCH - KEY) / 2
            yield r, c, x, y, ch == "1"


def _stamp_path(letter, kx, ky, scale=0.62, fill="#000"):
    """Blocky glyph knocked out of the key at (kx, ky), drawn in the body fill."""
    rows = PIXEL_FONT[letter]
    h = KEY * scale
    cell = h / 5
    w = cell * 3
    x0 = kx + (KEY - w) / 2
    y0 = ky + (KEY - h) / 2
    out = []
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "1":
                # inflate slightly so neighbouring cells overlap -- abutting
                # rects leave a hairline seam once antialiased
                b = cell * 0.06
                out.append(
                    f'<rect x="{x0 + c*cell - b:.2f}" y="{y0 + r*cell - b:.2f}" '
                    f'width="{cell + 2*b:.2f}" height="{cell + 2*b:.2f}" fill="{fill}"/>'
                )
    return "".join(out)


def _hourglass(cx, cy, w, h, col):
    """A flat hourglass glyph, drawn as two triangles plus caps."""
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h / 2, cy + h / 2
    t = h * 0.10
    return (
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{w:.1f}" height="{t:.1f}" rx="{t/2:.1f}" fill="{col}"/>'
        f'<rect x="{x0:.1f}" y="{y1-t:.1f}" width="{w:.1f}" height="{t:.1f}" rx="{t/2:.1f}" fill="{col}"/>'
        f'<path d="M {x0+w*0.10:.1f} {y0+t:.1f} L {x1-w*0.10:.1f} {y0+t:.1f} '
        f'L {cx:.1f} {cy:.1f} L {x1-w*0.10:.1f} {y1-t:.1f} L {x0+w*0.10:.1f} {y1-t:.1f} '
        f'L {cx:.1f} {cy:.1f} Z" fill="{col}"/>'
    )


def svg(variant="color", style="engraved", diagonal=True, stamp=True, body_r=None):
    """Return the SVG source for one variant."""
    if variant == "gray":
        g0, g1 = "#8A94A6", "#B9C2CE"
        body, rim = "#1A1D23", "#3A414D"
    else:
        g0, g1 = "#1D4ED8", "#22D3EE"
        body, rim = "#0B1220", None

    a0, a1 = AREA_INSET, S - AREA_INSET
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S}" height="{S}">',
        "<defs>",
        f'<linearGradient id="keys" gradientUnits="userSpaceOnUse" '
        f'x1="{a0}" y1="{a0 if diagonal else 0}" x2="{a1}" y2="{a1 if diagonal else 0}">'
        f'<stop offset="0" stop-color="{g0}"/><stop offset="1" stop-color="{g1}"/></linearGradient>',
        '<linearGradient id="cap" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#FFFFFF" stop-opacity="0.34"/>'
        '<stop offset="0.55" stop-color="#FFFFFF" stop-opacity="0.04"/>'
        '<stop offset="1" stop-color="#000018" stop-opacity="0.22"/></linearGradient>',
        f'<linearGradient id="rim" gradientUnits="userSpaceOnUse" x1="{a0}" y1="0" x2="{a1}" y2="0">'
        f'<stop offset="0" stop-color="{g0}"/><stop offset="1" stop-color="{g1}"/></linearGradient>',
        f'<linearGradient id="body" gradientUnits="userSpaceOnUse" x1="0" y1="{BODY_INSET}" '
        f'x2="0" y2="{S - BODY_INSET}">'
        '<stop offset="0" stop-color="#182135"/><stop offset="1" stop-color="#080C16"/></linearGradient>',
    ]

    out.append("</defs>")

    stamped = {STAMP_COLS[i]: STAMP_TEXT[i] for i in range(len(STAMP_COLS))} if stamp else {}

    bi, br = BODY_INSET, (BODY_R if body_r is None else body_r)
    bw = S - 2 * bi
    body_fill = "url(#body)" if variant != "gray" else body
    out.append(f'<rect x="{bi}" y="{bi}" width="{bw}" height="{bw}" rx="{br}" fill="{body_fill}"/>')

    if style == "hairline":
        out.append(
            f'<rect x="{bi+1}" y="{bi+1}" width="{bw-2}" height="{bw-2}" rx="{br-1}" '
            f'fill="none" stroke="#FFFFFF" stroke-opacity="0.10" stroke-width="6"/>'
        )
    if style in ("rim", "both"):
        stroke = "url(#rim)" if rim is None else rim
        out.append(
            f'<rect x="{bi+14}" y="{bi+14}" width="{bw-28}" height="{bw-28}" rx="{br-14}" '
            f'fill="none" stroke="{stroke}" stroke-width="18" stroke-opacity="0.9"/>'
        )

    for r, c, x, y, lit in _keys():
        if not lit:
            if style in ("engraved", "both"):
                out.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{KEY:.1f}" height="{KEY:.1f}" '
                    f'rx="{KEY_R:.1f}" fill="#FFFFFF" fill-opacity="0.05"/>'
                )
            continue
        out.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{KEY:.1f}" height="{KEY:.1f}" '
            f'rx="{KEY_R:.1f}" fill="url(#keys)"/>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{KEY:.1f}" height="{KEY:.1f}" '
            f'rx="{KEY_R:.1f}" fill="url(#cap)"/>'
        )
        letter = stamped.get(c) if r == STAMP_ROW else None
        if letter:
            out.append(_stamp_path(letter, x, y, fill=body_fill))

    if variant == "think":
        out.append(f'<rect x="{bi}" y="{bi}" width="{bw}" height="{bw}" rx="{br}" fill="#070B14" fill-opacity="0.62"/>')
        out.append(_hourglass(S / 2, S / 2, S * 0.30, S * 0.40, "#E6F6FF"))
    elif variant == "warn":
        out.append(f'<rect x="{bi}" y="{bi}" width="{bw}" height="{bw}" rx="{br}" fill="#070B14" fill-opacity="0.62"/>')
        cx, cy, w = S / 2, S * 0.54, S * 0.48
        h = w * 0.88
        out.append(
            f'<path d="M {cx:.0f} {cy-h*0.62:.0f} L {cx+w/2:.0f} {cy+h*0.38:.0f} '
            f'L {cx-w/2:.0f} {cy+h*0.38:.0f} Z" fill="#F2A93B" stroke="#F2A93B" '
            f'stroke-width="{S*0.075:.0f}" stroke-linejoin="round"/>'
        )
        out.append(
            f'<rect x="{cx-S*0.032:.0f}" y="{cy-h*0.30:.0f}" width="{S*0.064:.0f}" '
            f'height="{h*0.42:.0f}" rx="{S*0.032:.0f}" fill="#1A1206"/>'
            f'<circle cx="{cx:.0f}" cy="{cy+h*0.24:.0f}" r="{S*0.040:.0f}" fill="#1A1206"/>'
        )

    out.append("</svg>")
    return "\n".join(out)


def render(src, size):
    import io
    png = cairosvg.svg2png(bytestring=src.encode(), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def write_icns(path, images):
    """Minimal ICNS writer: PNG-backed types, which every modern macOS reads."""
    types = {16: b"icp4", 32: b"icp5", 64: b"icp6", 128: b"ic07",
             256: b"ic08", 512: b"ic09", 1024: b"ic10"}
    import io
    body = b""
    for sz, im in sorted(images.items()):
        if sz not in types:
            continue
        buf = io.BytesIO()
        im.save(buf, "PNG")
        data = buf.getvalue()
        body += types[sz] + struct.pack(">I", len(data) + 8) + data
    path.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="engraved",
                    choices=("flat", "hairline", "rim", "engraved", "both"))
    ap.add_argument("--horizontal", action="store_true", help="sweep the gradient left to right")
    ap.add_argument("--no-stamp", action="store_true", help="omit the HOST stamp")
    ap.add_argument("--body-r", type=float, help="body corner radius override")
    ap.add_argument("--sheet", help="write a comparison sheet here and change nothing else")
    args = ap.parse_args()

    variants = ("color", "gray", "think", "warn")

    if args.sheet:
        cell = 256
        sheet = Image.new("RGBA", (cell * len(variants), cell), (255, 255, 255, 0))
        for i, v in enumerate(variants):
            sheet.paste(render(svg(v, args.style, not args.horizontal, not args.no_stamp, args.body_r), cell), (i * cell, 0))
        sheet.save(args.sheet)
        print(f"wrote {args.sheet}")
        return

    ICONS.mkdir(parents=True, exist_ok=True)
    for v in variants:
        src = svg(v, args.style, not args.horizontal, not args.no_stamp, args.body_r)
        (ICONS / f"p{v}.svg").write_text(src)
        plain = svg(v, args.style, not args.horizontal, False, args.body_r)
        want = sorted(set(PNG_SIZES) | set(ICNS_SIZES) | set(LADDER_SIZES))
        imgs = {
            sz: render(src if sz >= STAMP_MIN_SIZE else plain, sz) for sz in want
        }
        # p<v>.png is the canonical single file (Linux .desktop, the About
        # dialog); p<v>_<n>.png is the ladder get_icon() feeds to QIcon so a
        # tray at 16 px gets a purpose-rendered 16 px, not a downscaled 256.
        imgs[256].save(ICONS / f"p{v}.png")
        imgs[1024].save(ICONS / f"p{v}@1024.png")
        for sz in LADDER_SIZES:
            imgs[sz].save(ICONS / f"p{v}_{sz}.png")
        # Each ICO entry is rendered at its own size rather than downscaled from
        # one image, so the sub-128 entries carry the unstamped mark.
        # WARNING: Pillow's ICO writer SKIPS any requested size larger than the
        # base image, with no error -- passing the 16 px one first yields a
        # single-entry 16x16 .ico. The base must be the LARGEST.
        largest, *rest = [imgs[s] for s in sorted(ICO_SIZES, reverse=True)]
        largest.save(
            ICONS / f"p{v}.ico",
            format="ICO",
            sizes=[(s, s) for s in ICO_SIZES],
            append_images=rest,
        )
        write_icns(ICONS / f"p{v}.icns", {s: imgs[s] for s in ICNS_SIZES})
        print(f"wrote p{v}.svg / .png / @1024.png / _{{{','.join(map(str, LADDER_SIZES))}}}.png / .ico / .icns")


if __name__ == "__main__":
    main()
