#!/usr/bin/env python3
"""Fetch + render the PowerToys Command Palette and PowerToys Run icons.

Two sets share this folder, one per focused PowerToys window:

* `cmdpal.yaml` -- Command Palette (`Microsoft.CmdPal.UI.exe`).
* `run.yaml`    -- PowerToys Run (`PowerToys.PowerLauncher.exe`).

The other PowerToys features are global shortcuts that work in any window, so
they have no keycap set here. See SOURCES.md.

Shortcut icons: Microsoft Fluent UI System Icons (MIT). ESC program marks: the
apps' OWN icons from microsoft/PowerToys (MIT, no trademark terms in LICENSE,
README or NOTICE.md):

* Command Palette: `src/modules/cmdpal/Microsoft.CmdPal.UI/Assets/Stable/icon.ico`
* PowerToys Run:   `src/runner/svgs/icon.ico` (the PowerToys logo). Run's own
  `RunAsset.ico` was rendered too and loses its magnifier at 1 bit.

Both marks are guarded by `program_marks.own_icon`, so a re-run never
overwrites a committed asset.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/powertoys/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import program_marks  # noqa: E402

# file stem -> Fluent folder name (MIT). Each name was probed before use.
FLUENT = {
    "run":         "Play",
    "secondary":   "Arrow Enter",
    "more":        "More Horizontal",
    "back":        "Arrow Left",
    "home":        "Home",
    "settings":    "Settings",
    "filter":      "Filter",
    "pin":         "Pin",
    "folder":      "Folder Open",
    "copypath":    "Document Copy",
    "console":     "Window Console",
    "admin":       "Shield",
    "otheruser":   "Person Swap",
}

REPO = "https://raw.githubusercontent.com/microsoft/PowerToys/main/"
CMDPAL_ICO = REPO + "src/modules/cmdpal/Microsoft.CmdPal.UI/Assets/Stable/icon.ico"
POWERTOYS_ICO = REPO + "src/runner/svgs/icon.ico"


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    program_marks.own_icon(out / "cmdpal_progmark.png", CMDPAL_ICO, 64,
                           credit="microsoft/PowerToys Microsoft.CmdPal.UI icon.ico")
    program_marks.own_icon(out / "powertoys_progmark.png", POWERTOYS_ICO, 64,
                           credit="microsoft/PowerToys src/runner/svgs/icon.ico")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
