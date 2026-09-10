#!/usr/bin/env python3
"""Fetch + render the WordPad shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** via the shared
`icon_fetch` helper. Where an action also exists in the `word` overlay the SAME
Fluent glyph is used, so the two rich-text editors read alike. The ESC
**program mark** is the shared license-clean letter tile (`../program_marks.py`)
with the document motif -- WordPad's own icon is Microsoft trademark art.

⚠️ WordPad is closed source AND was REMOVED from Windows in the 24H2 update, so
this overlay only fires on a machine that still has it. `bindings.yaml` carries
only what two independent references agree on; see SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/wordpad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import program_marks  # noqa: E402

RENDER_PX = 96

FLUENT = {
    # file
    "new":       "Document Add",
    "open":      "Folder Open",
    "save":      "Save",
    "saveas":    "Save Edit",
    "print":     "Print",
    # edit
    "undo":      "Arrow Undo",
    "redo":      "Arrow Redo",
    "cut":       "Cut",
    "copy":      "Copy",
    "paste":     "Clipboard Paste",
    "selectall": "Select All On",
    # search
    "find":      "Search",
    "findnext":  "Chevron Right",
    "replace":   "Arrow Swap",
    # character formatting  (same glyphs as the `word` overlay)
    "bold":      "Text Bold",
    "italic":    "Text Italic",
    "underline": "Text Underline",
    "subscript": "Text Subscript",
    "superscript": "Text Superscript",
    "allcaps":   "Text Case Uppercase",
    "fontbig":   "Font Increase",
    "fontsmall": "Font Decrease",
    # paragraph
    "alignleft":   "Text Align Left",
    "aligncenter": "Text Align Center",
    "alignright":  "Text Align Right",
    "justify":     "Text Align Justify",
    "bullets":     "Text Bullet List",
    "linespacing": "Text Line Spacing",
    # insert  (Ctrl+D is WordPad-specific: insert a Paint drawing)
    "drawing":   "Paint Brush",
    # navigation
    "doctop":    "Arrow Upload",
    "docend":    "Arrow Download",
    "wordleft":  "Arrow Previous",
    "wordright": "Arrow Next",
}


def _compose_linespacing(out: Path) -> None:
    """Compose the three line-spacing icons: the VALUE over the shared glyph.

    ⚠️ The same three rules the `word` overlay learned the hard way, because a
    set of composites is only readable when the shared half is pixel-identical
    across it: a STATIC font size (auto-fitting per value renders the same digit
    at different sizes), a COMMON LEFT EDGE centred on the widest value (so the
    leading "1" is in the exact same spot in "1" and in "1½"), and a fixed
    baseline. Real Arial is not installed -- Liberation Sans is metric-compatible.
    """
    p = RENDER_PX
    base = Image.open(out / "linespacing.png").convert("RGBA").split()[3]
    glyph = base.crop(base.getbbox())
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", int(p * 0.46))

    num_baseline, glyph_top = 30, 28
    gw, gh = glyph.size
    s = min(p / gw, (p - glyph_top) / gh)
    g = glyph.resize((max(1, int(gw * s)), max(1, int(gh * s))), Image.LANCZOS)
    x_left = (p - ImageDraw.Draw(Image.new("L", (1, 1))).textlength("1½", font=font)) / 2

    for fname, num in (("linespacing1.png", "1"), ("linespacing15.png", "1½"),
                       ("linespacing2.png", "2")):
        img = Image.new("L", (p, p), 0)
        ImageDraw.Draw(img).text((x_left, num_baseline), num, fill=255,
                                 font=font, anchor="ls")
        img.paste(g, ((p - g.width) // 2, glyph_top), g)
        Image.merge("RGBA", (img, img, img, img)).save(out / fname)
        print(f"  {fname}  <- composite (ms-fluent/Text Line Spacing + '{num}')")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    _compose_linespacing(out)
    program_marks.ensure(out / "wordpad.png", "WP", motif="corner")
    print(f"Wrote {n + 3} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
