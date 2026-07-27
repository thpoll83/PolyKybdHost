#!/usr/bin/env python3
"""Generate the Chrome Web Store small promo tile (440x280) from the brand mark.

Reproducible: PolyKybdHost/.venv/bin/python browser-extension/store/make_promo.py
Screenshots of the extension in use must still be captured on a real machine
(see SUBMISSION.md) — those can't be generated headless.
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
BRAND = HERE.parent.parent / "polyhost" / "res" / "icons" / "pgray.png"
OUT = HERE / "assets"
_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

W, H = 440, 280
BG = (18, 18, 20, 255)
TITLE = (235, 235, 235, 255)
SUB = (150, 150, 150, 255)


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def main():
    OUT.mkdir(exist_ok=True)
    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img)

    msz = 132
    mark = Image.open(BRAND).convert("RGBA").resize((msz, msz), Image.LANCZOS)
    img.alpha_composite(mark, (28, (H - msz) // 2))

    tx = 28 + msz + 22
    avail = W - tx - 18  # right margin

    def fit(text, path, size):
        """Largest font <= size whose text fits in `avail`."""
        f = _font(path, size)
        while size > 8 and d.textlength(text, font=f) > avail:
            size -= 1
            f = _font(path, size)
        return f

    d.text((tx, 92), "PolyKybd", font=fit("PolyKybd", _FONT, 34), fill=TITLE)
    d.text((tx, 130), "Website Reporter", font=fit("Website Reporter", _FONT, 26), fill=TITLE)
    d.text((tx, 170), "Website-aware keycap overlays",
           font=fit("Website-aware keycap overlays", _FONT_R, 15), fill=SUB)

    img.convert("RGB").save(OUT / "promo-440x280.png")
    # Store icon (128) alongside for convenience.
    Image.open(BRAND).convert("RGBA").resize((128, 128), Image.LANCZOS).save(
        OUT / "store-icon-128.png")
    print("wrote assets/promo-440x280.png, assets/store-icon-128.png")


if __name__ == "__main__":
    main()
