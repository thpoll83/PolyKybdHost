#!/usr/bin/env python3
"""Fetch and draw the DuckStation shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), through `icon_fetch`, with the same icon for the same action as
the RetroArch and MAME sets. The PlayStation controller keys are drawn at keycap
size by `pad_keys.ps_pad()`. The ESC mark is the name "Duck" over "Station" set
in Russo One (SIL OFL 1.1): DuckStation is licensed CC BY-NC-ND 4.0, so none of
its art is copied. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/duckstation/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, pad_keys  # noqa: E402

FLUENT = {
    "ffhold":     "ms:keyboard_double_arrow_right",
    "pause":      "ms:pause",
    "screenshot": "Camera",
    "fullscreen": "ms:fullscreen",
    "loadstate":  "Folder Open",
    "savestate":  "Save",
    "slotminus":  "ms:exposure_neg_1",
    "slotplus":   "ms:exposure_plus_1",
}

# The ESC mark is set in Russo One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/russoone/RussoOne-Regular.ttf")
MARK_LINES = ("Duck", "Station")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    pad_keys.ps_pad(out)
    pad_keys.wordmark(MARK_LINES, out / "program.png", FONT_URL)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
