#!/usr/bin/env python3
"""Draw the Age of Empires II ESC marks, pixel by pixel at 72x40.

A large serif "II" in the light pattern the firmware uses for a dimmed browser
mark (every second pixel in x and y), with "Age", a smaller "— of —" and
"Empires" in italic serif over it, each with a 1 px dark gap around its
letters. `program_de.png` adds a small "D" and "E" for the Definitive Edition.

The font is Liberation Serif (SIL OFL 1.1). Without it the committed PNGs are
kept as they are.

    pip install numpy pillow
    python polyhost/res/overlay_sources/aoe2/program_mark.py
"""
from __future__ import annotations

from pathlib import Path

# numpy and Pillow are imported inside the functions, so fetch_icons.py can
# import this module without them (ensure() keeps the committed PNGs).

W, H = 72, 40
FONT_DIR = Path("/usr/share/fonts/truetype/liberation")
II_FONT = "LiberationSerif-Regular.ttf"
TITLE_FONT = "LiberationSerif-BoldItalic.ttf"
OF_FONT = "LiberationSerif-Italic.ttf"
LETTER_FONT = "LiberationSerif-Bold.ttf"


def text(s: str, font: str, px: int) -> np.ndarray:
    """`s` as a 1-bit mask cropped to its ink."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(str(FONT_DIR / font), px)
    left, top, right, bottom = f.getbbox(s)
    im = Image.new("L", (right - left + 4, bottom - top + 4), 0)
    ImageDraw.Draw(im).text((2 - left, 2 - top), s, font=f, fill=255)
    m = np.array(im) > 128
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def of_line() -> np.ndarray:
    """"— of —". The font's dashes are thinner than a pixel at 10 px, so they
    are drawn as 1 px lines; the f gets its crossbar and a closed stem."""
    import numpy as np
    of = text("of", OF_FONT, 10)
    of[2, 5] = of[2, 7] = True
    of[6, 6] = True
    h, w = of.shape
    dash, gap = 8, 3
    m = np.zeros((h, w + 2 * (dash + gap)), bool)
    m[:, dash + gap:dash + gap + w] = of
    y = h - h // 3 - 1
    m[y, :dash] = True
    m[y, -dash:] = True
    return m


def place(canvas: np.ndarray, m: np.ndarray, cx: int, top: int) -> None:
    h, w = m.shape
    x0 = cx - w // 2
    canvas[top:top + h, x0:x0 + w] |= m


def dilate(m: np.ndarray, n: int) -> np.ndarray:
    """`m` grown by `n` px in the four axis directions per step, as
    scipy.ndimage.binary_dilation does with its default cross."""
    import numpy as np
    out = m.copy()
    for _ in range(n):
        grown = out.copy()
        grown[1:, :] |= out[:-1, :]
        grown[:-1, :] |= out[1:, :]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        out = grown
    return out


def mark(de: bool) -> np.ndarray:
    import numpy as np
    ii = np.zeros((H, W), bool)
    g = text("II", II_FONT, 56)[:H, :W]
    place(ii, g, W // 2, (H - g.shape[0]) // 2)
    yy, xx = np.mgrid[0:H, 0:W]
    light = ((xx % 2) == 0) & ((yy % 2) == 0)
    lines = [text("Age", TITLE_FONT, 14), of_line(), text("Empires", TITLE_FONT, 14)]
    words = np.zeros((H, W), bool)
    y = (H - sum(line.shape[0] for line in lines)) // 2
    for line in lines:
        place(words, line[:, :W], W // 2, y)
        y += line.shape[0]
    if de:
        d, e = text("D", LETTER_FONT, 9), text("E", LETTER_FONT, 9)
        words[37 - d.shape[0]:37, 4:4 + d.shape[1]] |= d
        words[37 - e.shape[0]:37, 68 - e.shape[1]:68] |= e
    return (ii & light & ~dilate(words, 1)) | words


def save(m: np.ndarray, dest: Path) -> None:
    import numpy as np
    from PIL import Image
    a = np.zeros((H, W, 4), np.uint8)
    a[m] = (0, 0, 0, 255)
    Image.fromarray(a, "RGBA").save(dest)
    print(f"  {dest.name}  <- drawn ({'with' if 'de' in dest.stem else 'without'} D E)")


def ensure(out: Path) -> None:
    if not (FONT_DIR / II_FONT).exists():
        print(f"  program.png, program_de.png  <- committed assets (no {FONT_DIR})")
        return
    save(mark(False), out / "program.png")
    save(mark(True), out / "program_de.png")


if __name__ == "__main__":
    ensure(Path(__file__).resolve().parent / "icons")
