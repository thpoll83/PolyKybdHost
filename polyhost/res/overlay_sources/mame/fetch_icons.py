#!/usr/bin/env python3
"""Fetch and draw the MAME shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), through `icon_fetch`. The player 1 buttons are rings with the
button number and the start and coin keys are pills, drawn at keycap size by
`retroarch/fetch_icons.py`'s `ring()` and `pill()` in Press Start 2P (SIL OFL
1.1). The ESC mark is a drawn "M" tile (`program_marks`): MAME's own icon is
GPL-2.0 and the logo a registered trademark, so it is not copied here.
See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/mame/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402
from polyhost.res.overlay_sources.retroarch import fetch_icons as ra  # noqa: E402

FLUENT = {
    "menu":       "ms:menu",
    "pause":      "ms:pause",
    "step":       "ms:skip_next",
    "rewindstep": "ms:skip_previous",
    "gfx":        "ms:grid_view",
    "savestate":  "Save",
    "quicksave":  "ms:save_as",
    "loadstate":  "Folder Open",
    "quickload":  "ms:file_open",
    "softreset":  "ms:restart_alt",
    "hardreset":  "ms:power_settings_new",
    "skipminus":  "ms:exposure_neg_1",
    "skipplus":   "ms:exposure_plus_1",
    "cheat":      "ms:key",
    "throttle":   "ms:speed",
    "fps":        "ms:analytics",
    "fastfwd":    "ms:fast_forward",
    "snapshot":   "Camera",
    "recordmng":  "ms:videocam",
    "recordavi":  "ms:movie",
    "service":    "ms:build",
    "tilt":       "ms:vibration",
    "osd":        "ms:tune",
}

BUTTONS = {f"button{n}": str(n) for n in range(1, 7)}
PILLS = {"start1": "1UP", "start2": "2UP", "coin1": "COIN", "coin2": "COIN2"}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    for name, text in BUTTONS.items():
        ra.ring(text, out / f"{name}.png")
    for name, text in PILLS.items():
        ra.pill(text, out / f"{name}.png")
    program_marks.ensure(out / "mame.png", "M")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
