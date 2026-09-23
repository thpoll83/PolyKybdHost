#!/usr/bin/env python3
"""Preview the ESC keycap: real GFX legend + a real program mark + the courtyard.

    python tools/esc_mark_preview.py polyhost/res/icons/program/*.svg ... 

Answers "what will this mark look like on the keycap, and does it eat the ESC
glyph" without a hardware round. Takes SVGs and finished .png masks alike.

Everything the firmware/host actually do, nothing mocked:
  * the ESC legend comes from gfx_font.load_all_fonts() -- the pixel-exact GFX
    renderer oled_preview and the firmware share;
  * the mark comes from app_icons.render_overlay(), the shipping 38 px path;
  * the courtyard is the Chebyshev-3 clear copy_overlay_to_buffer runs around
    the overlay's ink before drawing it.
"""
import argparse, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HOST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HOST)
sys.path.insert(0, os.path.join(HOST, "tools"))

# ⚠️ Needs the FIRMWARE checkout beside this one for the GFX headers -- the
# legend is drawn with the same renderer the firmware links, not an imitation,
# which is the whole reason the geometry here can be trusted.

from gfx_font import load_all_fonts, OLED_W, OLED_H, BUFFER_X, BASELINE   # noqa: E402
from oled_preview import Renderer                                          # noqa: E402
from polyhost.services import app_icons                                    # noqa: E402

ESC_CP = 0x238B
FONT_DIR = os.path.join(os.path.dirname(HOST), "qmk_firmware", "keyboards", "polykybd", "base", "fonts")


def legend_mask(renderer, cps, x=0):
    """`cps` drawn onto a blank 72x40 panel. `setpix` is a CALLABLE taking
    (x, y) -- not a PixelAccess, which is what tools/courtyard_preview.py hands
    it and why that tool raises TypeError on this Pillow."""
    grid = np.zeros((OLED_H, OLED_W), dtype=bool)

    def setpix(px, py):
        if 0 <= px < OLED_W and 0 <= py < OLED_H:
            grid[py, px] = True

    renderer.draw(setpix, cps, BUFFER_X + x, BASELINE)
    return grid


def courtyard(mark, r=3):
    """Chebyshev-`r` dilation of the mark's ink -- what the legend loses."""
    img = Image.fromarray((mark * 255).astype("uint8"))
    return np.array(img.filter(ImageFilter.MaxFilter(2 * r + 1)), dtype=bool)


def keycap(legend, mark):
    panel = np.zeros((OLED_H, OLED_W), dtype=bool)
    panel |= legend
    if mark is not None:
        panel &= ~courtyard(mark)
        panel |= mark
    return panel


def upscale(panel, scale):
    img = Image.fromarray((panel * 255).astype("uint8"), "L")
    return img.resize((OLED_W * scale, OLED_H * scale), Image.NEAREST).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svgs", nargs="*",
                    help="marks to preview (.svg or a finished .png mask)")
    ap.add_argument("--scale", type=int, default=5)
    ap.add_argument("--out", default="/home/user/scratch/icons/esc_preview.png")
    args = ap.parse_args()

    renderer = Renderer(load_all_fonts(FONT_DIR))
    legend = legend_mask(renderer, [ESC_CP])
    cols = np.flatnonzero(legend.any(0))
    print("ESC legend inks x %d..%d" % (cols.min(), cols.max()))

    rows = [("(no mark)", None, "")]
    for path in args.svgs:
        if path.lower().endswith(".png"):
            # a pre-dithered mark: already 1 bit at panel size, so it is loaded
            # verbatim rather than re-fitted -- re-binarising a halftone is what
            # turns it back into mush.
            mark = np.array(Image.open(path).convert("L")) > 127
        else:
            mark = app_icons.render_overlay(path)
        note = ""
        if mark is None:
            note = "DID NOT RENDER"
        else:
            mcols = np.flatnonzero(mark.any(0))
            mrows = np.flatnonzero(mark.any(1))
            clash = (legend & courtyard(mark)).sum()
            note = "x %d..%d  y %d..%d  ink %d px  legend lost %d px" % (
                mcols.min(), mcols.max(), mrows.min(), mrows.max(),
                mark.sum(), clash)
        rows.append((os.path.basename(path).replace(".svg", ""), mark, note))

    s = args.scale
    pad, label_w, gap = 10, 210, 8
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
        small = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except OSError:
        font = small = ImageFont.load_default()

    cell_h = OLED_H * s + gap
    sheet = Image.new("RGB", (pad * 2 + label_w + OLED_W * s + 330,
                              pad * 2 + cell_h * len(rows)), (22, 22, 26))
    draw = ImageDraw.Draw(sheet)
    for i, (name, mark, note) in enumerate(rows):
        y = pad + i * cell_h
        draw.text((pad, y + 12), name, (235, 235, 240), font=font)
        sheet.paste(upscale(keycap(legend, mark), s), (pad + label_w, y))
        draw.rectangle([pad + label_w - 1, y - 1,
                        pad + label_w + OLED_W * s, y + OLED_H * s],
                       outline=(90, 90, 100))
        draw.text((pad + label_w + OLED_W * s + 14, y + 14), note,
                  (150, 155, 165), font=small)
        print("%-22s %s" % (name, note))
    sheet.save(args.out)
    print("->", args.out)


if __name__ == "__main__":
    main()
