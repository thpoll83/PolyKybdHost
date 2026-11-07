#!/usr/bin/env python3
"""Fetch the FS-UAE shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), both through `icon_fetch`. The ESC mark is a drawn "FS" tile
(`program_marks`): FS-UAE's own icon files carry no licence statement of their
own. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/fs_uae/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402

FLUENT = {
    "stretch":    "ms:aspect_ratio",
    "border":     "ms:border_outer",
    "freeze":     "ms:ac_unit",
    "debugger":   "ms:bug_report",
    "fullscreen": "ms:fullscreen",
    "grab":       "ms:mouse",
    "keyboard":   "ms:keyboard",
    "mute":       "ms:volume_off",
    "floppymute": "ms:hearing_disabled",
    "pause":      "ms:pause",
    "quit":       "ms:close",
    "softreset":  "ms:restart_alt",
    "hardreset":  "ms:power_settings_new",
    "screenshot": "Camera",
    "zoom":       "ms:zoom_in",
    "warp":       "ms:fast_forward",
    "voldown":    "ms:volume_down",
    "volup":      "ms:volume_up",
    "autozoom":   "ms:fit_screen",
    "menu":       "ms:menu",
    "perf":       "ms:monitoring",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    program_marks.ensure(out / "fs-uae.png", "FS")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
