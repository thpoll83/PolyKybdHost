#!/usr/bin/env python3
"""Fetch and draw the Dolphin shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), through `icon_fetch`, with the same icon for the same action as
the RetroArch and MAME sets. The state slot keys (F1 to F8) and the Wii Remote
keys (Alt+F5 to F8) are one icon with the slot number beside it
(`pad_keys.numbered()`). The GameCube controller keys are drawn at keycap size:
rings with the button letter and the START pill from `retroarch/fetch_icons.py`,
the D-pad and stick directions from `pad_keys`. The ESC mark is the Dolphin
logo from Simple Icons (CC0-1.0). See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/dolphin/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch, pad_keys  # noqa: E402
from polyhost.res.overlay_sources.retroarch import fetch_icons as ra  # noqa: E402

FLUENT = {
    "open":         "Folder Open",
    "pause":        "ms:pause",
    "screenshot":   "Camera",
    "fullscreen":   "ms:fullscreen",
    "ffhold":       "ms:keyboard_double_arrow_right",
    "achievements": "ms:emoji_events",
    "undoload":     "ms:undo",
    "undosave":     "ms:settings_backup_restore",
    "balance":      "ms:scale",
}
# Sources of the numbered icons; removed again after numbered() has used them.
PARTS = {"_loadstate": "Folder Open", "_savestate": "Save", "_wiimote": "ms:settings_remote"}
SLOTS = range(1, 9)                 # F1..F8: state slots 1..8
WIIMOTES = range(1, 5)              # Alt+F5..F8: Wii Remote 1..4

# GameCube controller, port 1 (GCPad::LoadDefaults).
RINGS = {"gca": "A", "gcb": "B", "gcx": "X", "gcy": "Y", "gcz": "Z", "gcl": "L", "gcr": "R"}
PILLS = {"gcstart": "START"}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent({**FLUENT, **PARTS}, out)
    for n in SLOTS:
        pad_keys.numbered(out / "_loadstate.png", str(n), out / f"load{n}.png")
        pad_keys.numbered(out / "_savestate.png", str(n), out / f"save{n}.png")
    for n in WIIMOTES:
        pad_keys.numbered(out / "_wiimote.png", str(n), out / f"wiimote{n}.png")
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    for name, letter in RINGS.items():
        ra.ring(letter, out / f"{name}.png")
    for name, text in PILLS.items():
        ra.pill(text, out / f"{name}.png")
    for d in pad_keys.DIRECTIONS:
        pad_keys.dpad(d, out / f"dpad{d}.png")
        pad_keys.stick(d, out / f"stick{d}.png")
        pad_keys.stick(d, out / f"cstick{d}.png", "C")
    brand_marks.ensure(out / "dolphin.png", "dolphin")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
