#!/usr/bin/env python3
"""Fetch + render the Google Meet shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The ESC mark is the Google
Meet logo from Simple Icons (CC0 artwork; nominative use, see
`../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/meet/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    "mute": "Mic Off",
    "camera": "Video",
    "present": "Share Screen Start",
    "moretiles": "ms:grid_on",
    "fewertiles": "ms:grid_view",
    "chat": "Chat",
    "people": "People",
    "raisehand": "Hand Right",
    "minimize": "ms:picture_in_picture_alt",
    "speaker": "ms:record_voice_over",
    "roominfo": "Info",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    brand_marks.ensure(out / "meet.png", "googlemeet")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
