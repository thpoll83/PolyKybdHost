#!/usr/bin/env python3
"""Fetch + render the OriginPro shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) for the `ms:` entries. Icons for the same action as a MATLAB,
LabVIEW or COMSOL key are byte copies of those sets' icons (BORROW). The ESC
mark is a 32x32 1-bit drawing after the Origin application icon (see
SOURCES.md); it is drawn only when the PNG is missing, so a committed or
hand-edited mark is never redrawn.

    pip install cairosvg
    python polyhost/res/overlay_sources/origin/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

FLUENT = {
    "newproject": "ms:create_new_folder",
    "projprops": "ms:info",
    "image": "ms:image",
    "images": "ms:photo_library",
    "toolbars": "ms:toolbar",
    "closewin": "ms:close_fullscreen",
    "float": "ms:open_in_new",
    "retract": "ms:move_to_inbox",
    "lastwindow": "ms:undo",
    "switcher": "ms:switch_right",
    "switcherback": "ms:switch_left",
    "browser": "ms:folder_open",
    "findfiles": "ms:find_in_page",
    "recent": "ms:history",
    "repeat": "ms:repeat",
    "reopendlg": "ms:replay",
    "explorer": "ms:account_tree",
    "resultslog": "ms:receipt_long",
    "cmdwindow": "ms:terminal",
    "codebuilder": "ms:code",
    "quickhelp": "ms:help",
    "messages": "ms:chat",
    "hints": "ms:lightbulb",
    "objects": "ms:layers",
    "apps": "ms:apps",
    "script": "ms:description",
    "pauserecalc": "ms:pause_circle",
    "importwizard": "ms:upload_file",
    "ascii": "ms:text_snippet",
    "startup": "ms:rocket_launch",
    "customize": "ms:build",
    "options": "ms:settings",
    "themes": "ms:palette",
    "fitbuilder": "ms:function",
    "fitorganizer": "ms:functions",
    "appcenter": "ms:storefront",
    "learning": "ms:school",
    "colors": "ms:format_color_fill",
    "python": "ms:data_object",
    "custom": "ms:person",
    "nlfit": "ms:show_chart",
    "changeparams": "ms:tune",
    "buttonedit": "ms:smart_button",
}

# Same action as a MATLAB or LabVIEW key: byte copies of their icons.
BORROW = {"replace.png": "matlab", "nextwindow.png": "labview"}

# The Origin application icon is a red disc with a line graph, in front of a
# worksheet (www.originlab.com/favicon.ico, 48 px). A trace of it at 32 px is
# noise (the graph line is lost in the disc's highlights), so the mark is
# drawn after it: a worksheet grid at the top right, a lit disc at the bottom
# left, and the line graph with its points cut out of the disc.
S = 4  # drawn at 4x, then reduced to 32x32 1-bit


def draw_mark(dest: Path) -> None:
    from PIL import Image, ImageDraw
    img = Image.new("L", (32 * S, 32 * S), 0)
    d = ImageDraw.Draw(img)
    # worksheet: outline and a 3x3 grid
    x0, y0, x1, y1 = 13 * S, 1 * S, 31 * S - 1, 19 * S - 1
    d.rectangle([x0, y0, x1, y1], outline=255, width=S)
    for i in (1, 2):
        x = x0 + (x1 - x0) * i // 3
        y = y0 + (y1 - y0) * i // 3
        d.line([x, y0, x, y1], fill=255, width=S)
        d.line([x0, y, x1, y], fill=255, width=S)
    # a black ring around the disc keeps it apart from the sheet
    d.ellipse([0, 7 * S, 25 * S, 32 * S - 1], fill=0)
    d.ellipse([1 * S, 8 * S, 24 * S, 31 * S - 1], fill=255)
    pts = [(5, 25), (10, 17), (14, 21), (19, 12)]
    pts = [(x * S, y * S) for x, y in pts]
    d.line(pts, fill=0, width=2 * S)
    for x, y in pts:
        d.ellipse([x - 2 * S, y - 2 * S, x + 2 * S, y + 2 * S], fill=0)
    small = img.resize((32, 32), Image.LANCZOS).point(lambda v: 255 if v >= 128 else 0)
    Image.merge("RGBA", (small, small, small, small)).save(dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.borrow(BORROW, out)
    mark = out / "origin.png"
    if mark.exists():
        print("  origin.png  <- committed asset (left as-is)")
    else:
        draw_mark(mark)
        print("  origin.png  <- drawn program mark")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
