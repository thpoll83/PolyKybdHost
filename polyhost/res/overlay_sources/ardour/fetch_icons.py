#!/usr/bin/env python3
"""Fetch + render the Ardour shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. An action another DAW set
already draws is copied from that set (`BORROW`), so the same action shows the
same cell in every DAW.

The ESC program mark is Ardour's OWN logo (GPL-2.0-or-later, like the rest of
the Ardour tree): `share/web_surfaces/builtin/protocol/ardour-icon.svg`, a flat
one-colour triangle whose bottom edge is a waveform. It is rendered at 8x the
keycap size, reduced to 37x32 with LANCZOS and cut at alpha 160, so the
generator places it 1:1 (`program_icon_region: [37, 32]`). Guarded: a
committed `ardour.png` is left as it is.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/ardour/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

# Pinned to the commit the shortcut table was read from (SOURCES.md).
ARDOUR_SHA = "35f6a410ce9e6deac3e06983f29deef12757e527"
ARDOUR_SVG = ("https://raw.githubusercontent.com/Ardour/ardour/"
              f"{ARDOUR_SHA}/share/web_surfaces/builtin/protocol/ardour-icon.svg")
MARK_W, MARK_H, MARK_SS, MARK_CUT = 37, 32, 8, 160

# Same action as another DAW set -> the same art (byte-identical copy).
BORROW = {
    **{n: "ableton" for n in (
        "arm.png", "armarr.png", "browser.png", "consolidate.png",
        "continue.png", "crop.png", "cuttime.png", "deltime.png",
        "duplicate.png", "duptime.png", "exportaudio.png", "fade.png",
        "fitheight.png", "fixedgrid.png", "fullscreen.png", "group.png",
        "inout.png", "keymap.png", "loop.png", "loopend.png", "loopstart.png",
        "metronome.png", "narrowgrid.png", "playstop.png", "quantize.png",
        "record.png", "rename.png", "reverse.png", "search.png", "solo.png",
        "split.png", "stopsel.png", "ungroup.png", "widegrid.png",
        "zoomsel.png")},
    **{n: "reaper" for n in (
        "fastforward.png", "gridleft.png", "gridright.png", "import.png",
        "inserttrack.png", "mute.png", "nextmarker.png", "nexttrack.png",
        "nexttransient.png", "normalize.png", "nudgeleft.png",
        "nudgeright.png", "panic.png", "pitchup.png", "playskip.png",
        "prevmarker.png", "prevtrack.png", "prevtransient.png",
        "projsettings.png", "rewind.png", "routing.png",
        "saveversion.png", "snap.png", "stretch.png", "tempoenv.png",
        "toend.png", "tostart.png", "video.png", "voldown.png", "volup.png",
        "zoomproject.png", "mixer.png")},
    **{n: "soundcraft" for n in (
        "bringfront.png", "cyclemode.png", "follow.png", "heightdown.png",
        "heightup.png", "memlocs.png", "newmarker.png", "trimstart.png",
        "trimend.png")},
    **{n: "protools" for n in (
        "discardrec.png", "fadein.png", "fadeout.png", "openrecent.png",
        "syncpoint.png", "zoomtoggle.png")},
    **{n: "flstudio" for n in ("draw.png", "invert.png", "select.png", "slice.png")},
    **{n: "cubase" for n in (
        "locsel.png", "playsel.png", "punchin.png", "punchout.png",
        "rangetool.png", "rightzone.png", "stationary.png")},
    **{n: "logicpro" for n in (
        "delmarker.png", "exportall.png", "goto.png", "liveloops.png")},
}

FLUENT = {
    "alignstart": "ms:align_justify_flex_start",
    "alignend": "ms:align_justify_flex_end",
    "alignsync": "ms:align_justify_center",
    "autoreturn": "ms:keyboard_return",
    "contentmode": "ms:ink_selection",
    "cuemarker": "ms:add_location",
    "exportregion": "ms:file_export",
    "meterbridge": "ms:view_column",
    "multidup": "ms:copy_all",
    "moveup": "ms:move_up",
    "movedown": "ms:move_down",
    "naturalize": "ms:restart_alt",
    "opacity": "ms:opacity",
    "punchrange": "ms:data_array",
    "punchtoggle": "ms:compare_arrows",
    "quickexport": "ms:bolt",
    "recorder": "ms:mic_external_on",
    "smartmode": "ms:auto_awesome",
    "rangestart": "ms:line_start",
    "rangeend": "ms:line_end",
}


def _mark(path: Path) -> None:
    """Ardour's logo as a 37x32 1-bit mark, white on transparent (mode alpha)."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    with urllib.request.urlopen(ARDOUR_SVG, timeout=60) as r:
        svg = r.read()
    png = cairosvg.svg2png(bytestring=svg, output_width=MARK_W * MARK_SS,
                           output_height=MARK_H * MARK_SS)
    alpha = Image.open(io.BytesIO(png)).split()[3].resize((MARK_W, MARK_H), Image.LANCZOS)
    on = (np.asarray(alpha) >= MARK_CUT).astype(np.uint8) * 255
    Image.fromarray(np.dstack([on, on, on, on]), "RGBA").save(path)
    print(f"  {path.name}  <- Ardour/ardour@{ARDOUR_SHA[:8]} ardour-icon.svg")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    _mark(out / "ardour.png")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
