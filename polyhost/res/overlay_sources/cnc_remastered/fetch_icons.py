#!/usr/bin/env python3
"""Fetch + render the Command & Conquer Remastered Collection icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0) and
Material Design Icons (Apache-2.0); SOURCES.md credits each one. The ten
control-group units are drawn in units.py: each unit twice, the back copy as a
1 px outline and the front copy as drawn, a plus for Ctrl. The ESC mark is
"C&C" in the stencil face Black Ops One (SIL OFL 1.1), not the game's logo.

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
from polyhost.res.overlay_sources.cnc_remastered import units  # noqa: E402
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
    "scatter": "fa:burst",
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

# Control groups 1..0 are drawn in units.py: 1 rifleman, 2 engineer, 3 buggy,
# 4 APC, 5 Mammoth tank, 6 rocket launcher, 7 Orca, 8 jet, 9 gunboat, 0 harvester.

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


def _solid(m):
    """`m` with its enclosed holes filled (a flood fill from the border)."""
    import numpy as np
    H, W = m.shape
    outside = np.zeros_like(m)
    stack = [(y, x) for y in range(H) for x in (0, W - 1) if not m[y, x]]
    stack += [(y, x) for x in range(W) for y in (0, H - 1) if not m[y, x]]
    while stack:
        y, x = stack.pop()
        if outside[y, x] or m[y, x]:
            continue
        outside[y, x] = True
        stack += [(a, b) for a, b in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1))
                  if 0 <= a < H and 0 <= b < W]
    return ~outside


def _outline(m):
    """The 1 px edge of `m`'s solid shape: a traced, wireframe copy."""
    s = _solid(m)
    return s & program_mark.dilate(~s, 1)


def _layout(src: Path):
    """The unit's mask at the largest height whose two copies fit GROUP_W x GROUP_H,
    and the front copy's offset. A standing figure puts the second copy beside the
    first (as in AoE2); a vehicle is wide, so its second copy sits above and behind,
    or the pair would be only ~14 px high."""
    for h in range(aoe2.GROUP_H - 6, 8, -1):
        m = aoe2._unit_mask(src, h)
        w = m.shape[1]
        if w < h * 1.2:
            dx, dy = max(8, w * 2 // 5), aoe2.GROUP_DY
        else:
            dx, dy = max(6, w // 5), max(6, h * 9 // 20)
        if w + dx <= aoe2.GROUP_W and h + dy <= aoe2.GROUP_H:
            return m, dx, dy
    raise ValueError(f"{src.name} does not fit a group cell")


def groups(out: Path) -> None:
    """group<N>.png and groupnew<N>.png: the unit twice, the back copy as a 1 px
    outline and the front copy as drawn, with GROUP_SEAM px clear between them. Same
    size and placement rule as aoe2.groups(), so the bindings are the same."""
    import numpy as np
    for digit in units.UNITS:
        src = out / f"_unit{digit}.png"
        m, dx, dy = _layout(src)
        h, w = m.shape
        H, W = h + dy, w + dx
        back = np.zeros((H, W), bool)
        front = np.zeros((H, W), bool)
        back[:h, :w] = _outline(m)
        front[dy:, dx:] = m
        cover = np.zeros((H, W), bool)          # the front unit hides what is behind it
        cover[dy:, dx:] = _solid(m)
        g = (back & ~program_mark.dilate(cover, aoe2.GROUP_SEAM)) | front
        aoe2._save_cell(g, out / f"group{digit}.png")
        aoe2._save_cell(aoe2._with_plus(g), out / f"groupnew{digit}.png")
        print(f"  group{digit}.png, groupnew{digit}.png  <- _unit{digit}.png, outline + front")


def bookmark_set(out: Path) -> None:
    """bookmarkset.png: the bookmark with the control groups' plus (Ctrl+F1..F4)."""
    import numpy as np
    from PIL import Image
    src = Image.open(out / "bookmark.png").convert("RGBA").getchannel("A")
    src = src.crop(src.getbbox())
    src = src.resize((round(src.width * 40 / src.height), 40), Image.LANCZOS)
    m = aoe2._with_plus(np.array(src) > 150)
    canvas = np.zeros((*m.shape, 4), np.uint8)
    canvas[..., 3] = np.where(m, 255, 0)
    Image.fromarray(canvas, "RGBA").save(out / "bookmarkset.png")
    print("  bookmarkset.png  <- bookmark.png + plus")


def program(out: Path) -> None:
    """program.png: "C&C" in the stencil face over the whole 72x40 cell. Kept when committed."""
    dest = out / "program.png"
    if dest.exists():
        print("  program.png  <- committed asset (left as-is)")
        return
    import tempfile
    import numpy as np
    from PIL import Image
    font = Path(tempfile.gettempdir()) / "BlackOpsOne-Regular.ttf"
    if not font.exists():
        font.write_bytes(_get(STENCIL_URL))
    program_mark.FONT_DIR = font.parent
    for px in range(60, 10, -1):     # the largest size that leaves 1 px all round
        word = program_mark.text("C&C", font.name, px)
        if word.shape[1] <= program_mark.W - 2 and word.shape[0] <= program_mark.H - 2:
            break
    canvas = np.zeros((program_mark.H, program_mark.W), bool)
    program_mark.place(canvas, word, program_mark.W // 2,
                       (program_mark.H - word.shape[0]) // 2)
    rgba = np.zeros((program_mark.H, program_mark.W, 4), np.uint8)
    rgba[..., 3] = np.where(canvas, 255, 0)
    Image.fromarray(rgba, "RGBA").save(dest)
    print("  program.png  <- drawn \"C&C\" (Black Ops One)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    render(ICONS, out)
    for digit, draw in units.UNITS.items():
        draw().resize((units.GW * 2, units.GH * 2)).save(out / f"_unit{digit}.png")
        print(f"  _unit{digit}.png  <- units.{draw.__name__}()")
    for stem in ICONS:
        aoe2.trim(out, stem)
    groups(out)
    bookmark_set(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
