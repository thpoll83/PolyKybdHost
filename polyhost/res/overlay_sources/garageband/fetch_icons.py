#!/usr/bin/env python3
"""Fetch + render the GarageBand shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. An action another DAW set
already draws is copied from that set (`BORROW`), so the same action shows the
same cell in every DAW. No program icon: the host draws the ESC mark for the
app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/garageband/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

# Same action as another DAW set -> the same art (byte-identical copy).
BORROW = {
    **{n: "ableton" for n in (
        "audiotrack.png", "miditrack.png", "playstop.png", "record.png",
        "loopstart.png", "loopend.png", "solo.png", "arm.png", "loop.png",
        "metronome.png", "settings.png", "keymap.png", "fullscreen.png",
        "automation.png", "quantize.png", "split.png")},
    **{n: "reaper" for n in (
        "inserttrack.png", "master.png", "prevtrack.png", "nexttrack.png",
        "import.png", "video.png", "rewind.png", "fastforward.png",
        "gridright.png", "gridleft.png", "tostart.png", "toend.png",
        "mute.png", "snap.png", "inspaste.png", "cutarea.png",
        "glue.png")},
    **{n: "flstudio" for n in (
        "unmutesel.png", "help.png", "pianoroll.png", "deselect.png",
        "rename.png")},
    **{n: "protools" for n in (
        "inputmon.png", "scoreeditor.png", "prevclip.png", "nextclip.png")},
    **{n: "soundcraft" for n in ("trackdup.png", "follow.png", "trimstart.png")},
    **{n: "cubase" for n in (
        "removetrack.png", "playsel.png", "lowerzone.png", "color.png")},
}

FLUENT = {
    "trackheader": "ms:view_headline",
    "nextpatch": "Arrow Next",
    "prevpatch": "Arrow Previous",
    "preview": "ms:volume_up",
    "clearsolo": "ms:headset_off",
    "countin": "ms:timer_3",
    "guides": "ms:straighten",
    "library": "Library",
    "smartcontrols": "ms:adjust",
    "notepad": "ms:sticky_note_2",
    "loopbrowser": "ms:library_music",
    "loopregion": "ms:autorenew",
    "addloop": "ms:add_to_photos",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
