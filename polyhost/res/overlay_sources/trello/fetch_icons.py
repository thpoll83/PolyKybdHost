#!/usr/bin/env python3
"""Fetch + render the Trello shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The digit keys 1 to 0 apply
a label colour; `label_icons()` draws a tag with the colour's short name, 1-bit
at keycap size. The ESC mark is the Trello logo from Simple Icons (CC0 artwork;
nominative use, see `../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/trello/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    "next": "ms:keyboard_arrow_down",
    "prev": "ms:keyboard_arrow_up",
    "boardmenu": "Panel Right",
    "boards": "Board",
    "search": "Search",
    "archive": "Archive",
    "due": "Calendar Clock",
    "checklist": "ms:checklist",
    "quickedit": "Edit",
    "open": "ms:open_in_full",
    "save": "ms:send",
    "filter": "Filter",
    "labels": "Tag",
    "labelnames": "Tag Multiple",
    "members": "People Add",
    "newcard": "ms:note_add",
    "movebottomleft": "Arrow Left",
    "movebottomright": "Arrow Right",
    "movetopleft": "Arrow Previous",
    "movetopright": "Arrow Next",
    "mycards": "ms:person_search",
    "watch": "Eye",
    "assignself": "ms:how_to_reg",
    "title": "Rename",
    "vote": "Thumb Like",
    "clearfilter": "Filter Dismiss",
    "shortcuts": "Keyboard",
    "repeat": "ms:repeat",
}

# Trello's label colour per digit key (trello.com/shortcuts, "Label").
LABELS = {"1": "GRN", "2": "YEL", "3": "ORG", "4": "RED", "5": "PUR",
          "6": "BLU", "7": "SKY", "8": "LIME", "9": "PINK", "0": "BLK"}
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
LABEL_SIZE = (40, 40)


def _tag(d: ImageDraw.ImageDraw, x0: int, y0: int, w: int, h: int) -> None:
    """A label tag outline: a rectangle with a pointed right end and a hole."""
    tip = h // 2
    pts = [(x0, y0), (x0 + w - tip, y0), (x0 + w, y0 + h // 2),
           (x0 + w - tip, y0 + h), (x0, y0 + h)]
    d.polygon(pts, outline=255, width=3)
    cx, cy = x0 + w - tip - 2, y0 + h // 2
    d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=255)


def label_icons(out: Path) -> None:
    """Draw label_<digit>.png: a tag above the colour's short name, 1-bit."""
    font = None
    for digit, name in LABELS.items():
        dest = out / f"label_{digit}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        # Loaded only when a label is drawn: the committed PNGs need no font.
        font = font or ImageFont.truetype(BOLD, 13)
        mask = Image.new("L", LABEL_SIZE, 0)
        d = ImageDraw.Draw(mask)
        _tag(d, 3, 1, 34, 20)
        w = d.textlength(name, font=font)
        d.text(((LABEL_SIZE[0] - w) / 2, 38), name, font=font, fill=255, anchor="ls")
        mask = mask.point(lambda v: 255 if v >= 128 else 0)
        img = Image.new("RGBA", LABEL_SIZE, (255, 255, 255, 0))
        img.putalpha(mask)
        img.save(dest)
        print(f"  {dest.name}  <- drawn tag + '{name}'")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    label_icons(out)
    brand_marks.ensure(out / "trello.png", "trello")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
