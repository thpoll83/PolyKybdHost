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
* PowerToys Run:   the PowerToys logo (`src/runner/svgs/icon.ico`) redrawn here
  as a 32x32 1-bit mark: a square frame, the four colour stripes as four lit
  bars, and the three keys. The icon itself fuses the stripes into one blob at
  1 bit, and Run's own `RunAsset.ico` loses its magnifier.

Neither mark is redrawn once its PNG exists, so a re-run never overwrites a
committed asset.

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
# The PowerToys logo the Run mark is drawn after: REPO + "src/runner/svgs/icon.ico".


def _powertoys_mark(dest: Path) -> None:
    """The PowerToys logo as a 32x32 1-bit mark, drawn at the keycap size so
    the generator copies it 1:1."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    from PIL import Image, ImageDraw
    a = Image.new("L", (32, 32), 0)
    d = ImageDraw.Draw(a)
    d.rectangle((0, 0, 31, 31), fill=255)           # square frame, 2 px
    d.rectangle((2, 2, 29, 29), fill=0)
    for i in range(4):                               # the four colour stripes
        d.rectangle((5 + i * 6, 5, 9 + i * 6, 17), fill=255)
    for i in range(3):                               # the three keys
        d.rectangle((5 + i * 8, 21, 10 + i * 8, 26), fill=255)
    Image.merge("RGBA", (a, a, a, a)).save(dest)
    print(f"  {dest.name}  <- PowerToys logo, drawn 1-bit mark")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    program_marks.own_icon(out / "cmdpal_progmark.png", CMDPAL_ICO, 64,
                           credit="microsoft/PowerToys Microsoft.CmdPal.UI icon.ico")
    _powertoys_mark(out / "powertoys_progmark.png")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
