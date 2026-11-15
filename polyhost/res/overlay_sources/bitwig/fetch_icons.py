#!/usr/bin/env python3
"""Fetch + render the Bitwig Studio shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. An action another DAW set
already draws is copied from that set (`BORROW`), so the same action shows the
same cell in every DAW. The ESC mark is drawn by
`program_marks.pictogram_mark()`.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/bitwig/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import program_marks  # noqa: E402

# Same action as another DAW set -> the same art (byte-identical copy).
BORROW = {
    **{n: "ableton" for n in (
        "settings.png", "duplicate.png", "group.png", "ungroup.png",
        "split.png", "consolidate.png", "loop.png", "quantize.png",
        "playstop.png", "continue.png", "narrowgrid.png", "widegrid.png",
        "fixedgrid.png", "automation.png", "deviceview.png", "browser.png")},
    **{n: "reaper" for n in (
        "snap.png", "itemprops.png", "prevtrack.png", "nexttrack.png",
        "nudgeleft.png", "nudgeright.png", "tostart.png", "mixer.png",
        "pitchup.png", "pitchdown.png")},
    **{n: "musescore" for n in ("octup.png", "octdown.png")},
    **{n: "flstudio" for n in (
        "select.png", "draw.png", "deltool.png", "slice.png", "pianoroll.png")},
    **{n: "protools" for n in (
        "prevclip.png", "nextclip.png", "fadein.png", "fadeout.png",
        "gainup.png", "gaindown.png")},
    **{n: "soundcraft" for n in (
        "trimstart.png", "trimend.png", "extendup.png", "extenddown.png")},
    **{n: "cubase" for n in ("rangetool.png",)},
    **{n: "logicpro" for n in ("bounceinplace.png",)},
}

FLUENT = {
    "seltoggle": "ms:swap_horiz",
    "subdivless": "ms:grid_3x3",
    "subdivmore": "ms:grid_4x4",
    # Edit View (bindings_edit.yaml): event keys in the Detail Editor.
    "fineleft": "ms:arrow_left",
    "fineright": "ms:arrow_right",
    "extendleft": "ms:keyboard_double_arrow_left",
    "extendright": "ms:keyboard_double_arrow_right",
    "shorter": "ms:keyboard_tab_rtl",
    "longer": "ms:keyboard_tab",
}


BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def fine_variants(out: Path) -> int:
    """Edit View: give the fine and coarse steps of one action different art.

    Shorter/Longer by grid keep the arrow-to-bar glyph. The fine step
    (1/16 of the grid) draws the same bar with the small filled triangle the
    fine move keys use (`fineleft`/`fineright`), so the whole set reads
    "triangle = fine". Gain draws the step in dB, 6 or 1, in the empty
    top-right corner of the borrowed gain glyph.
    """
    from PIL import Image, ImageDraw, ImageFont
    bar = Image.open(out / "shorter.png").convert("RGBA").crop((10, 25, 16, 72))
    tri = Image.open(out / "fineleft.png").convert("RGBA").crop((37, 30, 56, 67))
    img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    img.alpha_composite(bar, (28, 25))
    img.alpha_composite(tri, (38, 30))
    img.save(out / "shorterfine.png")
    img.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(out / "longerfine.png")
    font = ImageFont.truetype(BOLD, 40)
    n = 2
    for src in ("gainup", "gaindown"):
        base = Image.open(out / f"{src}.png").convert("RGBA")
        for step in ("6", "1"):
            img = base.copy()
            ImageDraw.Draw(img).text((83, 24), step, fill=(0, 0, 0, 255),
                                     font=font, anchor="mm")
            img.save(out / f"{src}{step}.png")
            n += 1
    return n


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    n += fine_variants(out)
    # The ESC mark: Simple Icons bitwig (CC0-1.0), 1 bit at keycap size.
    program_marks.pictogram_mark(
        out / "bitwig_mark.png",
        "https://cdn.jsdelivr.net/npm/simple-icons@15.22.0/icons/bitwig.svg",
        credit="Simple Icons bitwig (CC0-1.0)")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
