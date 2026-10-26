#!/usr/bin/env python3
"""Fetch + render the Command & Conquer Remastered Collection icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0) and
Material Design Icons (Apache-2.0). The ten control-group units are Warzone
2100 models (GPL-2.0-or-later) rendered by wz_units.py: textured, lit,
dithered, with a lit outline; a plus for Ctrl. SOURCES.md credits each. The ESC
mark is "C&C" in the stencil face Black Ops One (SIL OFL 1.1), not the game's
logo.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/cnc_remastered/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import cairosvg

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import wz_units  # noqa: E402
from polyhost.res.overlay_sources.icon_fetch import _get  # noqa: E402

SOURCES = {
    # Font Awesome Free 6.5.2, solid (CC BY 4.0)
    "fa": "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/{}.svg",
    # Material Design Icons, Pictogrammers (Apache-2.0)
    "mdi": "https://raw.githubusercontent.com/Templarian/MaterialDesign/master/svg/{}.svg",
}

ICONS = {
    # Sidebar tabs
    "tabstructures": "fa:industry",
    "tabinfantry": "fa:person-military-rifle",
    "tabvehicles": "mdi:tank",
    "tabsuper": "fa:radiation",
    # Orders and selection
    "stop": "fa:hand",
    "scatter": "fa:arrows-up-down-left-right",
    "guard": "fa:shield-halved",
    "selectscreen": "fa:crosshairs",
    "selectall": "fa:earth-americas",
    "queuedmove": "fa:route",
    # Camera
    "conyard": "fa:helmet-safety",
    "lastevent": "fa:satellite-dish",
    "bookmark": "fa:bookmark",
    # Display
    "graphics": "fa:gem",
    "fullscreen": "fa:expand",
}

# Control groups 1..0 are Warzone 2100 units rendered by wz_units.py.

# "C&C" in Black Ops One (SIL OFL 1.1), a stencil face.
STENCIL_URL = ("https://raw.githubusercontent.com/google/fonts/main/ofl/blackopsone/"
               "BlackOpsOne-Regular.ttf")


def render(mapping: dict[str, str], out_dir: Path, render_px: int = 256) -> None:
    """Render `{filename_stem: "source:name"}` into `out_dir` as black-on-transparent PNGs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for stem, spec in mapping.items():
        src, name = spec.split(":", 1)
        png = cairosvg.svg2png(bytestring=_get(SOURCES[src].format(name)),
                               output_width=render_px, output_height=render_px)
        (out_dir / f"{stem}.png").write_bytes(png)
        print(f"  {stem}.png  <- {spec}")


# Key area of each icon, from cnc_remastered.yaml; the default is 40 x 40.
NARROW = {"lastevent", "bookmark", "fullscreen"}          # region [30, 40]


def relief(mask, seed=0):
    """A grey image of `mask` as a raised plate: the edges slope down over ~8 %
    of the size, lit from the top left and darker towards the bottom right, with a
    brushed-metal texture. It
    gives a flat icon the shading the rendered units have, so the same dither
    and outline (wz_units.keycap) make it match them."""
    import numpy as np
    h, w = mask.shape
    r = max(2, round(0.08 * min(h, w)))
    dist = np.zeros((h, w))
    m = mask.copy()
    for _ in range(r):                     # distance to the edge, capped at r
        dist += m
        m = m & ~program_mark.dilate(~m, 1)
    height = dist / r
    gy, gx = np.gradient(height)
    n = np.dstack([-gx * r, -gy * r, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    light = np.array([-0.55, -0.55, 0.63])
    shade = 0.35 + 0.65 * np.clip(n @ light / np.linalg.norm(light), 0, 1)
    yy, xx = np.mgrid[0:h, 0:w]
    falloff = 0.45 * (xx / w + yy / h) / 2       # top left bright, bottom right darker
    rng = np.random.default_rng(seed)
    grain = rng.normal(0, 1, (h, 1)) * 0.08 + rng.normal(0, 1, (h, w)) * 0.05
    return np.where(mask, np.clip(shade - falloff + grain, 0, 1), 0.0)


def _alpha(path: Path):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGBA").getchannel("A")) > 127


def _save_mask(mask, path: Path) -> None:
    import numpy as np
    from PIL import Image
    rgba = np.zeros((*mask.shape, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.where(mask, 255, 0)
    Image.fromarray(rgba, "RGBA").save(path)


def dither_icons(out: Path) -> None:
    """Every key icon in the style of the units: relief, dither, lit outline,
    drawn at exactly its key area so the generator places it 1:1."""
    import numpy as np
    from PIL import Image
    for stem in ICONS:
        size = (30, 40) if stem in NARROW else (40, 40)
        # Re-render the glyph large so the relief has room for its slope.
        big = Image.open(out / f"{stem}.png").convert("RGBA").getchannel("A")
        scale = 320 / max(big.size)
        big = big.resize((round(big.width * scale), round(big.height * scale)), Image.LANCZOS)
        mask = np.asarray(big) > 127
        m = wz_units.keycap(relief(mask, seed=len(stem)), mask, size=size, mirror=False)
        canvas = np.zeros((size[1], size[0]), bool)
        canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
        _save_mask(canvas, out / f"{stem}.png")
        if stem == "bookmark":
            for n in "1234":
                numbered = _stamp(canvas, n)
                _save_mask(numbered, out / f"bookmark{n}.png")
                _save_mask(wz_units._with_plus(numbered), out / f"bookmarkset{n}.png")
    print(f"  {len(ICONS)} key icons dithered (+ bookmark1..4, bookmarkset1..4)")


DIGIT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"   # Bitstream Vera licence


def _stamp(mask, text, height=11, top=16):
    """`text` cut out of `mask` (unlit) in a regular-weight face, centred, its top
    at `top`, with a lit 1 px rim so the thin strokes read against the dither."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    for px in range(40, 6, -1):
        f = ImageFont.truetype(DIGIT_FONT, px)
        left, t, right, bottom = f.getbbox(text)
        im = Image.new("L", (right - left + 4, bottom - t + 4), 0)
        ImageDraw.Draw(im).text((2 - left, 2 - t), text, font=f, fill=255)
        glyph = np.array(im) > 110
        ys, xs = np.nonzero(glyph)
        glyph = glyph[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        if glyph.shape[0] <= height:
            break
    h, w = mask.shape
    g = np.zeros((h, w), bool)
    x0 = (w - glyph.shape[1]) // 2 + 1
    g[top:top + glyph.shape[0], x0:x0 + glyph.shape[1]] = glyph
    rim = program_mark.dilate(g, 1) & ~g
    return (mask & ~g) | (rim & program_mark.dilate(mask, 1))


def program(out: Path) -> None:
    """program.png: "C&C" in the stencil face over the whole 72x40 cell, with the
    same relief, dither and outline as the other keys."""
    import tempfile
    import numpy as np
    font = Path(tempfile.gettempdir()) / "BlackOpsOne-Regular.ttf"
    if not font.exists():
        font.write_bytes(_get(STENCIL_URL))
    program_mark.FONT_DIR = font.parent
    for px in range(240, 40, -4):          # 4x the cell, leaving 1 px all round
        word = program_mark.text("C&C", font.name, px)
        if word.shape[1] <= 4 * (program_mark.W - 2) and word.shape[0] <= 4 * (program_mark.H - 2):
            break
    m = wz_units.keycap(relief(word, seed=1), word,
                        size=(program_mark.W - 2, program_mark.H - 2), mirror=False)
    canvas = np.zeros((program_mark.H, program_mark.W), bool)
    y0, x0 = (program_mark.H - m.shape[0]) // 2, (program_mark.W - m.shape[1]) // 2
    canvas[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = m
    _save_mask(canvas, out / "program.png")
    print("  program.png  <- \"C&C\" (Black Ops One), relief + dither")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    render(ICONS, out)
    for stem in ICONS:
        aoe2.trim(out, stem)
    dither_icons(out)
    wz_units.main(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
