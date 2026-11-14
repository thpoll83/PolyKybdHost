#!/usr/bin/env python3
"""Fetch the ScummVM shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), through `icon_fetch`, with the same icon for the same action as
the RetroArch and MAME sets. The ESC mark is the "S" of ScummVM's own icon
(`icons/scummvm.svg`, GPL-3.0-or-later like ScummVM), cut to 1 bit by
`pad_keys.logo_mark()`. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/scummvm/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, pad_keys  # noqa: E402

FLUENT = {
    "menu":       "ms:menu",
    "mute":       "Speaker Mute",
    "quit":       "Sign Out",
    "debugger":   "ms:bug_report",
    "fullscreen": "ms:fullscreen",
    "grabmouse":  "ms:mouse",
    "screenshot": "Camera",
    "aspect":     "ms:aspect_ratio",
    "filter":     "ms:blur_on",
    "stretch":    "ms:fit_screen",
    "scaledown":  "ms:zoom_out",
    "scalernext": "ms:navigate_next",
    "scalerprev": "ms:navigate_before",
}

# ScummVM's own icon at the release the keys were read from.
LOGO_URL = "https://raw.githubusercontent.com/scummvm/scummvm/v2.9.1/icons/scummvm.svg"


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    # The icon is a yellow-green "S" with a dark outline: the bright pixels are the S.
    pad_keys.logo_mark(out / "scummvm.png", LOGO_URL, lit="bright", cut=120)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
