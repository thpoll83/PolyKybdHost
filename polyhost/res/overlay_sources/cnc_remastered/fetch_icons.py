#!/usr/bin/env python3
"""Fetch + render the Command & Conquer Remastered Collection icons (reproducible).

The icons are flat silhouettes from Font Awesome Free (CC BY 4.0), Material
Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0); SOURCES.md credits
each one. The control-group icons reuse the Age of Empires II builder (each
unit twice with a 3 px seam, a plus for Ctrl). The ESC mark is "C&C" drawn in
the stencil face Black Ops One (SIL OFL 1.1), not the game's logo.

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
from polyhost.res.overlay_sources.icon_fetch import _get  # noqa: E402

SOURCES = {
    # Font Awesome Free 6.5.2, solid (CC BY 4.0)
    "fa": "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/{}.svg",
    # Material Design Icons, Pictogrammers (Apache-2.0)
    "mdi": "https://raw.githubusercontent.com/Templarian/MaterialDesign/master/svg/{}.svg",
    # game-icons.net (CC BY 3.0, credit per author)
    "gi": game_icons.URL,
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

# Control groups 1..0: one unit each, drawn twice (aoe2.groups()).
GROUP_UNITS = {
    "1": "fa:person-rifle",         # infantry
    "2": "fa:person-digging",       # engineer
    "3": "fa:truck-monster",        # buggy, Humvee
    "4": "gi:skoll/apc",            # APC
    "5": "mdi:tank",
    "6": "fa:truck-field",          # rocket launcher, artillery
    "7": "fa:helicopter",           # Orca, Apache, Chinook
    "8": "fa:jet-fighter-up",       # A-10, MiG, Yak
    "9": "gi:delapouite/submarine",  # Red Alert submarine
    "0": "fa:truck-moving",         # harvester
}

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
    render({f"_unit{d}": n for d, n in GROUP_UNITS.items()}, out)
    for stem in ICONS:
        aoe2.trim(out, stem)
    aoe2.groups(out, GROUP_UNITS)
    bookmark_set(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
