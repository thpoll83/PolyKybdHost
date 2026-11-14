#!/usr/bin/env python3
"""Fetch and draw the PPSSPP shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), through `icon_fetch`, with the same icon for the same action as
the RetroArch and MAME sets. The PSP controls are drawn at keycap size: the four
face buttons as rings with their shape, the D-pad and the analog stick
(`pad_keys`), L and R as rings with the letter and START / SELECT as pills
(`retroarch/fetch_icons.py`). The ESC mark is PPSSPP's own icon
(`icons/icon-512.svg`, GPL-2.0-or-later like PPSSPP), cut to 1 bit by
`pad_keys.logo_mark()`. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/ppsspp/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, pad_keys  # noqa: E402
from polyhost.res.overlay_sources.retroarch import fetch_icons as ra  # noqa: E402

FLUENT = {
    "ffhold":     "ms:keyboard_double_arrow_right",
    "speed":      "ms:speed",
    "rewind":     "ms:fast_rewind",
    "pause":      "ms:pause",
    "rapidfire":  "ms:bolt",
    "debugger":   "ms:bug_report",
    # The Windows menu keys
    "savestate":  "Save",
    "loadstate":  "Folder Open",
    "slotplus":   "ms:exposure_plus_1",
    "open":       "ms:file_open",
    "stop":       "ms:stop",
    "reset":      "ms:restart_alt",
    "cheat":      "ms:key",
    "resolution": "ms:aspect_ratio",
    "fullscreen": "ms:fullscreen",
}

RINGS = {"pspl": "L", "pspr": "R"}
PILLS = {"pspstart": "START", "pspselect": "SELECT"}

# PPSSPP's own icon at the release the keys were read from.
LOGO_URL = "https://raw.githubusercontent.com/hrydgard/ppsspp/v1.20.4/icons/icon-512.svg"


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    for name in pad_keys.SHAPES:
        pad_keys.shape(name, out / f"{name}.png")
    for name, letter in RINGS.items():
        ra.ring(letter, out / f"{name}.png")
    for name, text in PILLS.items():
        ra.pill(text, out / f"{name}.png")
    for d in pad_keys.DIRECTIONS:
        pad_keys.dpad(d, out / f"dpad{d}.png")
        pad_keys.stick(d, out / f"stick{d}.png")
    # The icon is four light buttons on a blue tile: the bright pixels are the buttons.
    pad_keys.logo_mark(out / "ppsspp.png", LOGO_URL, lit="bright", cut=120)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
