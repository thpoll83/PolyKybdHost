#!/usr/bin/env python3
"""Build the kitty overlay icons (reproducible source step).

Shortcut icons: Microsoft Fluent UI System Icons (MIT). Window 1..9 and 10
carry their number inside Fluent's `Square` glyph (`number_badge`); in kitty a
"window" is a pane inside a tab.

ESC program mark: kitty's own logo, `logo/kitty.png` in kovidgoyal/kitty
(GPL-3.0, the same licence as this host). It is a brown cat above a black
`>_` tile on a transparent background. Composited over white, contain-fitted
to 32x32 with LANCZOS, and lit where luma is 128 or darker, it reads as the
cat's outline with the eyes and the prompt cut out. At 32x32 the generator
places it 1:1. The mark is written only when `kitty.png` is missing, so a
hand edit stays.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/kitty/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
import number_badge  # noqa: E402

# Pinned to the commit the shortcuts were read from (SOURCES.md).
KITTY_COMMIT = "da8cac3264241ac2ae667ffe884c45cc0ec54ae5"
KITTY_ICON_URL = ("https://raw.githubusercontent.com/kovidgoyal/kitty/"
                  f"{KITTY_COMMIT}/logo/kitty.png")
MARK_PX = 32
MARK_DARK_LUMA = 128     # lit when luma <= 128 over white

# file stem -> Fluent folder name (every name probed against the repository).
FLUENT = {
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "pastesel": "Clipboard Arrow Right",
    "passsel": "Open",
    "lineup": "Arrow Sort Up",
    "linedown": "Arrow Sort Down",
    "pageup": "Arrow Circle Up",
    "pagedown": "Arrow Circle Down",
    "totop": "Arrow Upload",
    "tobottom": "Arrow Download",
    "prevprompt": "Arrow Circle Up Left",
    "pager": "Book Open",
    "lastoutput": "Document Text",
    "find": "Search",
    "newwin": "Add Square",
    "newoswin": "Window New",
    "closewin": "Dismiss Square",
    "nextwin": "Arrow Circle Right",
    "prevwin": "Arrow Circle Left",
    "movewinfwd": "Arrow Forward",
    "movewinback": "Arrow Reply",
    "movewintop": "Arrow Up",
    "resizewin": "Resize",
    "square": "Square",
    "focuswin": "Target",
    "swapwin": "Arrow Swap",
    "nexttab": "Chevron Right",
    "prevtab": "Chevron Left",
    "newtab": "Tab Add",
    "closetab": "Dismiss Circle",
    "closeoswin": "Window Multiple",
    "movetabfwd": "Arrow Next",
    "movetabback": "Arrow Previous",
    "tabtitle": "Rename",
    "layout": "Grid",
    "fontbig": "Font Increase",
    "fontsmall": "Font Decrease",
    "fontreset": "Text Font Size",
    "openurl": "Link",
    "hints": "Cursor Click",
    "fullscreen": "Full Screen Maximize",
    "maximize": "Maximize",
    "unicode": "Emoji",
    "config": "Settings",
    "opacity": "Transparency Square",
    "reset": "Arrow Reset",
    "reload": "Arrow Sync",
    "debug": "Bug",
    "secure": "Shield Keyhole",
    "cleartostart": "Eraser",
    "clear": "Broom",
    "clearlast": "Arrow Undo",
    "clearscreen": "Eraser Segment",
    "hideapp": "Eye Off",
    "hideothers": "Eye Tracking Off",
    "minimize": "Arrow Minimize",
    "quit": "Power",
}


def _kitty_mark(dest: Path, px: int = MARK_PX) -> None:
    """kitty's logo as a px*px 1-bit trace: composited over white, fitted into
    the square, pixels at MARK_DARK_LUMA or darker lit."""
    req = urllib.request.Request(KITTY_ICON_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    src = white.convert("L")
    scale = px / max(src.size)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.LANCZOS)
    square = Image.new("L", (px, px), 255)
    square.paste(fitted, ((px - fitted.width) // 2, (px - fitted.height) // 2))
    a = square.point(lambda v: 255 if v <= MARK_DARK_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    number_badge.numbered(out / "square.png", "1234567890", out, "win")
    mark = out / "kitty.png"
    if mark.exists():
        print(f"  {mark.name}  <- committed asset (left as-is)")
    else:
        _kitty_mark(mark)
        print(f"  {mark.name}  <- kovidgoyal/kitty logo/kitty.png (GPL-3.0)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
