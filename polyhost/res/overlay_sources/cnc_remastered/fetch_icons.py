#!/usr/bin/env python3
"""Fetch + render the Command & Conquer Remastered Collection icons (reproducible).

The key icons are silhouettes from Font Awesome Free (CC BY 4.0), Material
Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0), shaded and dithered
like the units. The ten control-group units are Warzone
2100 models (GPL-2.0-or-later) rendered by wz_units.py: textured, lit,
dithered, with a lit outline; a plus for Ctrl. SOURCES.md credits each. The ESC
mark is COMMAND & CONQUER set in the stencil face Black Ops One (SIL OFL 1.1),
laid out like the game's title; the game's logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/cnc_remastered/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import cairosvg

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import wz_units  # noqa: E402
from polyhost.res.overlay_sources.icon_fetch import _get  # noqa: E402

SOURCES = {
    # Font Awesome Free 6.5.2, solid (CC BY 4.0)
    "fa": "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/{}.svg",
    # Material Design Icons, Pictogrammers (Apache-2.0), pinned commit
    "mdi": "https://raw.githubusercontent.com/Templarian/MaterialDesign/"
           "2424e748e0cc63ab7b9c095a099b9fe239b737c0/svg/{}.svg",
    # game-icons.net (CC BY 3.0, credit per author)
    "gi": game_icons.URL,
}

ICONS = {
    # Sidebar tabs
    "tabstructures": "mdi:factory",
    "tabinfantry": "gi:delapouite/barracks",
    "tabvehicles": "gi:lorc/battle-tank",
    "tabsuper": "gi:lorc/mushroom-cloud",
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

# The ESC mark is set in Black Ops One (SIL OFL 1.1), a stencil face.
STENCIL_URL = ("https://raw.githubusercontent.com/google/fonts/"
               "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/blackopsone/BlackOpsOne-Regular.ttf")


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
SIZES = {"lastevent": (36, 40), "bookmark": (30, 40), "fullscreen": (30, 40),
         "tabinfantry": (48, 40), "tabvehicles": (48, 40)}
MIRROR = {"tabinfantry"}           # the barracks' flag pole on the right, facing like the units


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
        size = SIZES.get(stem, (40, 40))
        # Re-render the glyph large so the relief has room for its slope.
        big = Image.open(out / f"{stem}.png").convert("RGBA").getchannel("A")
        scale = 320 / max(big.size)
        big = big.resize((round(big.width * scale), round(big.height * scale)), Image.LANCZOS)
        mask = np.asarray(big) > 127
        if stem in MIRROR:
            mask = mask[:, ::-1]
        m = wz_units.keycap(relief(mask, seed=len(stem)), mask, size=size, mirror=False)
        canvas = np.zeros((size[1], size[0]), bool)
        canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
        _save_mask(canvas, out / f"{stem}.png")
        if stem == "bookmark":
            for n in "1234":
                numbered = _stamp(canvas, n)
                _save_mask(numbered, out / f"bookmark{n}.png")
                _save_mask(wz_units._with_plus(numbered, top=True), out / f"bookmarkset{n}.png")
    print(f"  {len(ICONS)} key icons dithered (+ bookmark1..4, bookmarkset1..4)")


# DejaVu Sans Bold (Bitstream Vera licence), from matplotlib v3.9.2's bundled copy.
DIGIT_FONT_URL = ("https://raw.githubusercontent.com/matplotlib/matplotlib/"
                  "a254b687df97cda8c6affa37a1dfcf213f8e6c3a/lib/matplotlib/mpl-data/fonts/ttf/"
                  "DejaVuSans-Bold.ttf")


def _font(url: str) -> Path:
    """`url` downloaded once into the temp dir."""
    import tempfile
    path = Path(tempfile.gettempdir()) / url.rsplit("/", 1)[1]
    if not path.exists():
        path.write_bytes(_get(url))
    return path


def _stamp(mask, text, height=11, top=16):
    """`text` cut out of `mask` (unlit) in DejaVu Sans Bold, centred, its top
    at `top`, with a lit 1 px rim so the strokes read against the dither."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    for px in range(40, 6, -1):
        f = ImageFont.truetype(str(_font(DIGIT_FONT_URL)), px)
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


LOGO_CAP, LOGO_BIG, LOGO_AMP = 8, 10, 6     # cap heights in px: words, big M and Q, "&"
LOGO_SS = 8                                 # supersampling factor


def _glyph(ch, font, cap):
    """`ch` with a cap height of `cap` px: (mask cropped to ink, rows below the baseline)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    ref = ImageFont.truetype(str(font), 200).getbbox("H")
    f = ImageFont.truetype(str(font), round(200 * cap * LOGO_SS / (ref[3] - ref[1])))
    left, top, right, bottom = f.getbbox(ch)
    pad = 2 * LOGO_SS
    im = Image.new("L", (right - left + 2 * pad, bottom - top + 2 * pad), 0)
    ImageDraw.Draw(im).text((pad - left, pad - top), ch, font=f, fill=255)
    baseline = pad - top + f.getbbox("H")[3]
    ys, xs = np.nonzero(np.asarray(im))
    im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    size = (max(1, round(im.width / LOGO_SS)), max(1, round(im.height / LOGO_SS)))
    below = max(0, round((ys.max() + 1 - baseline) / LOGO_SS))
    return np.asarray(im.resize(size, Image.BOX)) > 110, below


def _word(word, font, big):
    """`word` at LOGO_CAP with the letters at indices `big` at LOGO_BIG, each
    letter's cap height centred on the others' (a Q's tail hangs below)."""
    import numpy as np
    gs = [_glyph(c, font, LOGO_BIG if i in big else LOGO_CAP) for i, c in enumerate(word)]
    tops = [(LOGO_CAP - (m.shape[0] - below)) // 2 for m, below in gs]
    y0 = min(tops)
    height = max(t - y0 + m.shape[0] for t, (m, _) in zip(tops, gs))
    out = np.zeros((height, sum(m.shape[1] for m, _ in gs) + len(gs) - 1), bool)
    x = 0
    for t, (m, _) in zip(tops, gs):
        out[t - y0:t - y0 + m.shape[0], x:x + m.shape[1]] = m
        x += m.shape[1] + 1
    return out


def program(out: Path) -> None:
    """program.png: COMMAND / -- & -- / CONQUER in the stencil face, the second
    M and the Q larger, over the whole 72x40 cell."""
    import numpy as np
    font = _font(STENCIL_URL)
    top, amp, bottom = _word("COMMAND", font, {3}), _glyph("&", font, LOGO_AMP)[0], _word("CONQUER", font, {3})
    w, h = program_mark.W, program_mark.H
    gap = 1
    assert max(top.shape[1], bottom.shape[1]) <= w
    canvas = np.zeros((h, w), bool)
    y = (h - top.shape[0] - amp.shape[0] - bottom.shape[0] - 2 * gap) // 2
    for m in (top, amp, bottom):
        x = (w - m.shape[1]) // 2
        canvas[y:y + m.shape[0], x:x + m.shape[1]] = m
        if m is amp:                      # a 1 px rule either side of the "&"
            width = max(top.shape[1], bottom.shape[1])
            rule_y, left = y + amp.shape[0] // 2, (w - width) // 2
            canvas[rule_y, left:x - 3] = True
            canvas[rule_y, x + amp.shape[1] + 3:left + width] = True
        y += m.shape[0] + gap
    _save_mask(canvas, out / "program.png")
    print("  program.png  <- COMMAND & CONQUER (Black Ops One)")


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
