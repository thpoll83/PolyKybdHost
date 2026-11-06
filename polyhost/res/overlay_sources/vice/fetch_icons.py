#!/usr/bin/env python3
"""Fetch the VICE shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), both through `icon_fetch`. The ESC mark is a drawn "V" tile
(`program_marks`): VICE's own machine icons carry no licence statement of their
own, and their source folder says not to ship them. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/vice/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402

FLUENT = {
    "smartattach":   "ms:attach_file",
    "monitor":       "ms:terminal",
    "resetcpu":      "ms:restart_alt",
    "powercycle":    "ms:power_settings_new",
    "quit":          "ms:close",
    "driveattach":   "ms:hard_drive",
    "eject":         "ms:eject",
    "flipadd":       "ms:playlist_add",
    "flipremove":    "ms:playlist_remove",
    "flipnext":      "ms:arrow_forward",
    "flipprev":      "ms:arrow_back",
    "tape":          "ms:voicemail",
    "cartattach":    "ms:memory",
    "freeze":        "ms:ac_unit",
    "formfeed":      "ms:print",
    "copy":          "Copy",
    "paste":         "Clipboard Paste",
    "snapload":      "Folder Open",
    "snapsave":      "Save",
    "quickload":     "ms:file_open",
    "quicksave":     "ms:save_as",
    "milestone":     "ms:flag",
    "milestoneback": "ms:history",
    "record":        "ms:fiber_manual_record",
    "stop":          "ms:stop",
    "screenshot":    "Camera",
    "fullscreen":    "ms:fullscreen",
    "restoredisp":   "ms:fit_screen",
    "decorations":   "ms:web_asset",
    "warp":          "ms:fast_forward",
    "pause":         "ms:pause",
    "frameadv":      "ms:skip_next",
    "mousegrab":     "ms:mouse",
    "swapports":     "ms:swap_horiz",
    "keysetjoy":     "ms:sports_esports",
    "settings":      "Settings",
    "settingsreset": "ms:settings_backup_restore",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    program_marks.ensure(out / "vice.png", "V")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
