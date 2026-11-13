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


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    # The ESC mark: Simple Icons bitwig (CC0-1.0), 1 bit at keycap size.
    program_marks.pictogram_mark(
        out / "bitwig_mark.png",
        "https://cdn.jsdelivr.net/npm/simple-icons@15.22.0/icons/bitwig.svg",
        credit="Simple Icons bitwig (CC0-1.0)")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
