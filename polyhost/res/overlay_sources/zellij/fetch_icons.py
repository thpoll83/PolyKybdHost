#!/usr/bin/env python3
"""Fetch + render the Zellij shortcut icons (reproducible source step).

Glyphs are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0, `ms:` entries), both through `icon_fetch`. Five glyphs are drawn
here: move tab left / right and previous / next swap layout (a Fluent or
Material glyph with an arrow under it), and the word "tmux" for the tmux mode.

The ESC mark is the Zellij logo (`assets/logo.png` in the Zellij repository,
MIT) reduced to a 32x32 1-bit trace, dark pixels lit. See SOURCES.md.

    pip install cairosvg Pillow
    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/zellij/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from nle_glyphs import WHITE, _canvas, _save  # noqa: E402

FLUENT = {
    # --- mode switches (Ctrl) ---
    "lock": "Lock Closed",
    "quit": "Power",
    "pane": "Split Vertical",
    "tab": "ms:tab",
    "resize": "Resize",
    "scroll": "ms:height",
    "session": "ms:dns",
    "move": "Arrow Move",
    # --- normal-mode actions (Alt) ---
    "floating": "ms:picture_in_picture",
    "newpane": "ms:splitscreen_vertical_add",
    "left": "Arrow Left",
    "right": "Arrow Right",
    "up": "Arrow Up",
    "down": "Arrow Down",
    "grow": "Arrow Maximize",
    "shrink": "Arrow Minimize",
    "layout": "Board",
    "group": "Checkbox Checked",
    "groupmark": "ms:checklist",
}

# The Zellij logo from the Zellij repository (MIT), pinned to the v0.45.1 tag.
ZELLIJ_LOGO_URL = ("https://raw.githubusercontent.com/zellij-org/zellij/"
                   "efd8fd5a89a20c07a111d248ad7fce53848d2c18/assets/logo.png")
ZELLIJ_DARK_LUMA = 128

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _fit(src: Path, box: int) -> Image.Image:
    """`src` cropped to its ink and scaled to fit a `box` square."""
    im = Image.open(src).convert("RGBA")
    im = im.crop(im.split()[3].getbbox())
    k = box / max(im.size)
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)


def _with_arrow(path: Path, glyph: Path, forward: bool) -> None:
    """`glyph` at the top with a heavy arrow under it, pointing left or right."""
    img, d, u = _canvas()
    g = _fit(glyph, int(u * 0.62))
    img.alpha_composite(g, ((u - g.width) // 2, 0))
    y, t, h = int(u * 0.84), int(u * 0.05), int(u * 0.14)
    x0, x1 = int(u * 0.14), int(u * 0.86)
    d.rectangle([x0, y - t, x1 - h, y + t], fill=WHITE)
    d.polygon([(x1, y), (x1 - h, y - h), (x1 - h, y + h)], fill=WHITE)
    if not forward:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    _save(img, path)


def _word(path: Path, text: str = "tmux", size: tuple[int, int] = (36, 32)) -> None:
    """`text` drawn 1-bit at keycap size, centred in a `size` box. The binding's
    region equals `size`, so the generator places it 1:1."""
    w, h = size
    img = Image.new("L", size, 0)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    pt = 20
    while pt > 6:
        font = ImageFont.truetype(FONT, pt)
        box = d.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= w - 2 and box[3] - box[1] <= h - 2:
            break
        pt -= 1
    x = (w - (box[2] - box[0])) // 2 - box[0]
    y = (h - (box[3] - box[1])) // 2 - box[1]
    d.text((x, y), text, font=font, fill=255)
    Image.merge("RGBA", (img, img, img, img)).save(path)


def _zellij_mark(dest: Path, px: int = 32) -> None:
    """The Zellij logo as a px*px 1-bit trace: fitted into the square, pixels at
    luma 128 or darker lit (the dark outlines and the >_ prompt). Drawn at the
    keycap size so the generator copies it 1:1."""
    import io
    import urllib.request
    req = urllib.request.Request(ZELLIJ_LOGO_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    src = white.convert("L")
    scale = px / max(src.size)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.LANCZOS)
    square = Image.new("L", (px, px), 255)
    square.paste(fitted, ((px - fitted.width) // 2, (px - fitted.height) // 2))
    a = square.point(lambda v: 255 if v <= ZELLIJ_DARK_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)


def _guarded(path: Path, draw) -> None:
    """Draw a custom glyph only when its PNG is missing. To redraw one after
    changing its drawing, delete the PNG first (see SOURCES.md)."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        draw(path)
        print(f"  {path.name}  <- custom (drawn in zellij/fetch_icons.py)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    _guarded(out / "tableft.png", lambda p: _with_arrow(p, out / "tab.png", forward=False))
    _guarded(out / "tabright.png", lambda p: _with_arrow(p, out / "tab.png", forward=True))
    _guarded(out / "layoutprev.png", lambda p: _with_arrow(p, out / "layout.png", forward=False))
    _guarded(out / "layoutnext.png", lambda p: _with_arrow(p, out / "layout.png", forward=True))
    _guarded(out / "tmux.png", _word)
    _guarded(out / "zellij.png", _zellij_mark)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
