#!/usr/bin/env python3
"""Fetch the WinUAE shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), both through `icon_fetch`. The ESC mark is a drawn "WU" tile
(`program_marks`). See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/winuae/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402

FLUENT = {
    "gui":        "ms:menu",
    "debugger":   "ms:bug_report",
    "fullscreen": "ms:fullscreen",
    "freeze":     "ms:ac_unit",
    "screenshot": "Camera",
    "pause":      "ms:pause",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    program_marks.ensure(out / "winuae.png", "WU")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
