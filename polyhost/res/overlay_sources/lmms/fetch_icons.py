#!/usr/bin/env python3
"""Fetch + render the LMMS shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. An action another DAW set
already draws is copied from that set (`BORROW`), so the same action shows the
same cell in every DAW.

The ESC program mark is LMMS's OWN icon (GPL-2.0-or-later, like the rest of the
LMMS tree): `cmake/linux/icons/256x256/apps/lmms.png`, a white glyph on a green
tile. Only the white glyph is lit (`dcc_glyphs.trace_mark`, `lit="light"`, luma
210), drawn at 32x32 so the generator places it 1:1. Guarded: a committed
`lmms.png` is left as it is.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/lmms/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dcc_glyphs, icon_fetch  # noqa: E401,E402

# Pinned to the commit the shortcut table was read from (SOURCES.md).
LMMS_SHA = "f2a4cd24de5ab61c12d706d8d8fed0b731963467"
LMMS_ICON = ("https://raw.githubusercontent.com/LMMS/lmms/"
             f"{LMMS_SHA}/cmake/linux/icons/256x256/apps/lmms.png")

# Same action as another DAW set -> the same art (byte-identical copy).
BORROW = {
    **{n: "ableton" for n in (
        "exportaudio.png", "exportmidi.png", "playstop.png", "insertsilence.png",
        "deltime.png", "automation.png", "midimap.png", "fullscreen.png")},
    **{n: "reaper" for n in (
        "saveversion.png", "tostart.png", "rewind.png", "fastforward.png",
        "mixer.png")},
    **{n: "flstudio" for n in ("pause.png", "pianoroll.png")},
    **{n: "logicpro" for n in ("exportall.png", "mainwin.png", "stepseq.png")},
    **{n: "garageband" for n in ("notepad.png",)},
}

FLUENT = {
    "detach": "ms:open_in_new",
    "attach": "ms:close_fullscreen",
}


def _mark(path: Path) -> None:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    with urllib.request.urlopen(LMMS_ICON, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read()))
        icon.load()
    dcc_glyphs.trace_mark(icon, path, px=32, luma=210, lit="light")
    print(f"  {path.name}  <- LMMS/lmms@{LMMS_SHA[:8]} lmms.png (light pixels, luma 210)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    _mark(out / "lmms.png")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
