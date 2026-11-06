#!/usr/bin/env python3
"""Build the WezTerm overlay icons (reproducible source step).

Shortcut icons: Microsoft Fluent UI System Icons (MIT). Tab 1..8 carry their
number inside Fluent's `Tab` glyph (`number_badge`).

ESC program mark: WezTerm's own icon, `assets/icon/terminal.png` in
wez/wezterm (MIT). It is a dark tile with a blue "$W". Composited over black,
the tile has luma 24..55 and the glyph 88..95, with nothing in between, so the
mark lights the pixels above luma 72 (the middle of that gap) after a
contain-fit to 32x32 with LANCZOS. At 32x32 the generator places it 1:1.
The mark is written only when `wezterm.png` is missing, so a hand edit stays.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/wezterm/fetch_icons.py
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
WEZTERM_COMMIT = "e68a8ec27727fbbda15e07f0a0737cd5e16481f6"
WEZTERM_ICON_URL = ("https://raw.githubusercontent.com/wez/wezterm/"
                    f"{WEZTERM_COMMIT}/assets/icon/terminal.png")
MARK_PX = 32
MARK_DARK_LUMA = 72      # lit when luma <= 72 (tile <= 55, glyph >= 88)

# file stem -> Fluent folder name (every name probed against the repository).
FLUENT = {
    "newtab": "Tab Add",
    "tab": "Tab",
    "newwindow": "Window New",
    "closetab": "Dismiss Square",
    "prevtab": "Chevron Left",
    "nexttab": "Chevron Right",
    "movetableft": "Arrow Previous",
    "movetabright": "Arrow Next",
    "lasttab": "Arrow Download",
    "splitdown": "Split Horizontal",
    "splitright": "Split Vertical",
    "resizepane": "Resize",
    "focusup": "Arrow Up",
    "focusdown": "Arrow Down",
    "focusleft": "Arrow Left",
    "focusright": "Arrow Right",
    "zoompane": "Arrow Expand",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "copysel": "Copy Select",
    "pastesel": "Clipboard Arrow Right",
    "find": "Search",
    "copymode": "Highlight",
    "quickselect": "Lasso",
    "charselect": "Emoji",
    "palette": "Apps List",
    "clear": "Broom",
    "reload": "Arrow Sync",
    "debug": "Bug",
    "pageup": "Arrow Circle Up",
    "pagedown": "Arrow Circle Down",
    "fullscreen": "Full Screen Maximize",
    "fontbig": "Font Increase",
    "fontsmall": "Font Decrease",
    "fontreset": "Text Font Size",
    "minimize": "Arrow Minimize",
    "hideapp": "Eye Off",
    "quit": "Power",
}


def _wezterm_mark(dest: Path, px: int = MARK_PX) -> None:
    """WezTerm's icon as a px*px 1-bit trace: composited over white, fitted
    into the square, pixels at MARK_DARK_LUMA or darker lit. The dark tile is
    lit with its rounded corners, and the "$W" is cut out of it."""
    req = urllib.request.Request(WEZTERM_ICON_URL, headers={"User-Agent": "PolyKybdHost"})
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
    number_badge.numbered(out / "tab.png", "12345678", out, "tab")
    mark = out / "wezterm.png"
    if mark.exists():
        print(f"  {mark.name}  <- committed asset (left as-is)")
    else:
        _wezterm_mark(mark)
        print(f"  {mark.name}  <- wez/wezterm assets/icon/terminal.png (MIT)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
