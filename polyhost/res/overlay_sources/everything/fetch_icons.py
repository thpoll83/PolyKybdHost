#!/usr/bin/env python3
"""Fetch and draw the Everything (voidtools) shortcut icons.

Icons are Microsoft Fluent UI System Icons (MIT) and, for the three search
options Fluent has no glyph for, Google Material Symbols (Apache-2.0), both
through `icon_fetch`. The text badges (window sizes, thumbnail sizes, the
diacritics letter) are drawn here. The ESC mark is the Everything app icon
(a magnifying glass) reduced to a 1-bit outline. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/everything/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

# voidtools.com's favicon is the app icon (an orange magnifying glass).
# Google's favicon service returns it at 256 px.
EVERYTHING_ICON_URL = "https://www.google.com/s2/favicons?domain=voidtools.com&sz=256"
# Pixels this dark or darker are lit: the glass's dark outline, not its
# orange fill, so the mark is an outline with the handle at the lower left.
EVERYTHING_DARK_LUMA = 128

FLUENT = {
    # file operations in the result list
    "rename":      "Rename",
    "reload":      "Arrow Sync",
    "props":       "Document Settings",
    "switchfocus": "Arrow Swap",
    "contextmenu": "Navigation",
    "deleteperm":  "Delete Dismiss",
    "copypath":    "Clipboard Letter",
    "openpath":    "Folder Open",
    "readinfo":    "Document Search",
    # sort (Ctrl+1..9)
    "sortname":    "Text Sort Ascending",
    "sortpath":    "Folder",
    "sortsize":    "Data Bar Vertical",
    "sortext":     "Document",
    "sorttype":    "Shapes",
    "sortmod":     "Calendar Edit",
    "sortcreated": "Calendar Add",
    "sortattr":    "Tag",
    "sortchanged": "Calendar Clock",
    # search options
    "matchcase":   "ms:match_case",
    "matchword":   "ms:match_word",
    "regex":       "ms:regular_expression",
    "matchpath":   "Folder Search",
    # window and view
    "search":      "Search",
    "newwindow":   "Window New",
    "filelist":    "Document Bullet List",
    "options":     "Settings",
    "exit":        "Power",
    "export":      "Document Arrow Right",
    "ontop":       "Pin",
    "bookmark":    "Bookmark Add",
    "bookmarks":   "Bookmark Multiple",
    "filters":     "Filter",
    "history":     "History",
    "home":        "Home",
    "back":        "Arrow Left",
    "forward":     "Arrow Right",
    "fullscreen":  "Full Screen Maximize",
    "preview":     "Panel Right",
    "autosize":    "Arrow Autofit Content",
    "details":     "Document Table",
    "textbigger":  "Font Increase",
    "textsmaller": "Font Decrease",
    "textreset":   "Text Font Size",
    "thumbbigger": "Arrow Maximize",
    "thumbsmaller": "Arrow Minimize",
    "nextwindow":  "Arrow Next",
    "prevwindow":  "Arrow Previous",
    "debug":       "Bug",
    "about":       "Info",
}

# Text badges: a rounded outline with the text inside. Drawn at 4x the 36x32
# key area and reduced, so the outline stays 2 px.
BADGES = {
    "size512": "512",
    "size640": "640",
    "size768": "768",
    "thumbxl": "XL",
    "thumbl":  "L",
    "thumbm":  "M",
}
W, H, S = 36, 32, 4


def _badge(path: Path, text: str) -> None:
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    stroke = 2 * S
    pad = stroke // 2 + S
    d.rounded_rectangle([pad, 4 * S, W * S - pad, H * S - 4 * S],
                        radius=6 * S, outline=white, width=stroke)
    font = ImageFont.truetype(BOLD, (13 if len(text) > 2 else 15) * S)
    d.text(((W * S) / 2, (H * S) / 2), text, font=font, fill=white, anchor="mm")
    img.resize((W, H), Image.LANCZOS).save(path)


def _letter(path: Path, text: str) -> None:
    """One large letter, white on transparent (the diacritics option)."""
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(BOLD, 30 * S)
    d.text(((W * S) / 2, (H * S) / 2 + S), text, font=font,
           fill=(255, 255, 255, 255), anchor="mm")
    img.resize((W, H), Image.LANCZOS).save(path)


def _everything_mark(dest: Path, px: int = 32) -> None:
    """The Everything app icon as a px*px 1-bit outline.

    Drawn at the keycap size so the generator copies it 1:1.
    """
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    import io
    import urllib.request
    with urllib.request.urlopen(EVERYTHING_ICON_URL, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    a = white.convert("L").resize((px, px), Image.LANCZOS).point(
        lambda v: 255 if v <= EVERYTHING_DARK_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)
    print(f"  {dest.name}  <- Everything app icon, 1-bit outline")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    for name, text in BADGES.items():
        _badge(out / f"{name}.png", text)
    _letter(out / "diacritics.png", "é")
    _everything_mark(out / "progmark.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
