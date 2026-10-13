#!/usr/bin/env python3
"""Fetch + render the WordCraft shortcut icons (reproducible).

WordCraft (github.com/storytold/wordcraft, MIT OR Apache-2.0) is a Word-like
word processor, so its glyphs follow the Word overlay: Microsoft Fluent UI
System Icons (MIT) via the shared `icon_fetch`, Material Symbols (Apache-2.0,
`ms:` specs) for the gaps, and the Word set's drawn composites (hanging indent,
line spacing 1 / 1.5 / 2) copied byte-for-byte from `../word/icons/` so the same
action draws the same cell in both apps.

The program icon (ESC) is WordCraft's OWN app icon
(`assets/app-icon/wordcraft.svg`, MIT OR Apache-2.0), rendered without its blue
rounded-square background: the page, its text lines and the pencil read at
keycap size, the full tile is one lit blob (see SOURCES.md).

Drawn / composed assets (program mark, text glyphs, level badges, the few
custom glyphs) are guarded: a committed PNG is left as-is so hand edits survive
a re-run. Plain Fluent / Material downloads are deterministic and re-fetch.

    cd PolyKybdHost && PYTHONPATH=. .venv/bin/python \
        polyhost/res/overlay_sources/wordcraft/fetch_icons.py
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from polyhost.res.overlay_sources import icon_fetch, number_badge  # noqa: E402

PX = 96
SS = 4
WHITE = (255, 255, 255, 255)
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# WordCraft's own app icon, pinned to the commit the shortcuts were read from.
APP_SHA = "159b84f54c74e9e82fb3109b758ae7dd6f4e3ab0"
APP_ICON_SVG = (f"https://raw.githubusercontent.com/storytold/wordcraft/{APP_SHA}"
                "/assets/app-icon/wordcraft.svg")

FLUENT = {
    # file
    "new": "Document Add",
    "open": "Folder Open",
    "save": "Save",
    "saveas": "Save Edit",
    "print": "Print",
    "close": "Document Dismiss",
    # edit
    "copy": "Copy",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "pastespecial": "Clipboard More",
    "pastetext": "Clipboard Letter",
    "pasteformat": "Paint Brush Arrow Down",
    "copyformat": "Paint Brush",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "selectall": "Select All On",
    "find": "Search",
    "findnext": "Chevron Down",
    "findprev": "Chevron Up",
    "replace": "Arrow Swap",
    "goto": "Arrow Down",
    "goback": "Arrow Hook Up Left",
    "repeat": "Arrow Repeat All",
    "extendsel": "Text Expand",
    "columnsel": "Column Triple",
    "tellme": "Lightbulb",
    "contextmenu": "Navigation",
    "keytips": "Keyboard",
    # character format
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "doubleunderline": "Text Underline Double",
    "subscript": "Text Subscript",
    "superscript": "Text Superscript",
    "allcaps": "Text Case Uppercase",
    "smallcaps": "Text Case Title",
    "hidden": "Eye Off",
    "font": "Text Font",
    "fontname": "Text Font Info",
    "fontsize": "Text Font Size",
    "fontinc": "Font Increase",
    "fontdec": "Font Decrease",
    "font1inc": "ms:text_increase",
    "font1dec": "ms:text_decrease",
    "highlight": "Highlight",
    "changecase": "Text Change Case",
    # paragraph
    "left": "Text Align Left",
    "center": "Text Align Center",
    "right": "Text Align Right",
    "justify": "Text Align Justify",
    "distribute": "Text Align Distributed",
    "indent": "Text Indent Increase",
    "outdent": "Text Indent Decrease",
    "spacebefore": "Text Add Space Before",
    "clearfmt": "Text Clear Formatting",
    "normalstyle": "Text T",
    "heading1": "Text Header 1",
    "heading2": "Text Header 2",
    "heading3": "Text Header 3",
    "bullets": "Text Bullet List",
    "applystyles": "Text Effects",
    "stylespane": "Style Guide",
    "moveup": "ms:move_up",
    "movedown": "ms:move_down",
    "promote": "ms:format_indent_decrease",
    "demote": "ms:format_indent_increase",
    # insert / references / fields
    "hyperlink": "Link",
    "bookmark": "Bookmark",
    "field": "Braces",
    "datefield": "Calendar",
    "timefield": "Clock",
    "pagefield": "Document Page Number",
    "footnote": "Text Footnote",
    "endnote": "Document Endnote",
    "equation": "Math Formula",
    "markcitation": "Text Quote",
    "markentry": "Tag",
    "fieldcodes": "Code",
    "togglefield": "Code Block",
    "updatefield": "Arrow Sync",
    "unlinkfields": "Link Dismiss",
    "lockfields": "Lock Closed",
    "unlockfields": "Lock Open",
    "nextfield": "ms:skip_next",
    "prevfield": "ms:skip_previous",
    # mailings
    "recipients": "Person Edit",
    "mergefield": "Braces Variable",
    "previewmerge": "Mail Read",
    "finishmerge": "Mail Arrow Up",
    # review
    "comment": "Comment Add",
    "trackchanges": "Document Edit",
    "wordcount": "Text Word Count",
    "spelling": "Text Grammar Checkmark",
    "thesaurus": "Book Search",
    # view
    "printlayout": "Document One Page",
    "draft": "Document Text",
    "outlineview": "Document Bullet List",
    "split": "Split Horizontal",
    "expand": "ms:unfold_more",
    "collapse": "ms:unfold_less",
    "showall": "Text Bullet List Tree",
    # navigation
    "wordleft": "ms:keyboard_double_arrow_left",
    "wordright": "ms:keyboard_double_arrow_right",
    "paraup": "ms:keyboard_double_arrow_up",
    "paradown": "ms:keyboard_double_arrow_down",
    "docstart": "ms:vertical_align_top",
    "docend": "ms:vertical_align_bottom",
    "resetchar": "ms:format_clear",
    "readaloud": "Read Aloud",
    "pagebreak": "Document Page Break",
    "columnbreak": "Text Column Two",
    "linebreak": "ms:keyboard_return",
    "delwordback": "ms:backspace",
    "backspace_src": "ms:backspace",       # mirrored below into delwordfwd.png
    "square_src": "Square",                # base for the outline-level badges
}

# Same drawing as Word for the same action: byte-identical copies.
BORROW = {
    "hangindent.png": "word",
    "linespacing1.png": "word",
    "linespacing15.png": "word",
    "linespacing2.png": "word",
    "hyphen.png": "word",
}

# Single-glyph keycaps (text the app inserts). White on transparent -> mode: alpha.
TEXT_GLYPHS = {
    "emdash": ("—", 0.80),
    "copyright": ("©", 0.80),
    "registered": ("®", 0.80),
    "trademark": ("™", 0.80),
    "ellipsis": ("…", 0.80),
    "nbhyphen": ("a‑b", 0.56),
    "unicode": ("U+", 0.56),
    "pilcrow": ("¶", 0.80),
    "nbsp": ("a°b", 0.56),
}


def _guarded(path: Path) -> bool:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return True
    return False


def _text_glyph(path: Path, text: str, size: float) -> None:
    u = PX * SS
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(BOLD, int(u * size))
    d.text((u / 2, u / 2), text, font=font, fill=WHITE, anchor="mm")
    img = img.crop(img.getbbox())
    canvas = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    canvas.paste(img, ((u - img.width) // 2, (u - img.height) // 2))
    canvas.resize((PX, PX), Image.LANCZOS).save(path)
    print(f"  {path.name}  <- drawn text {text!r} (DejaVu Sans Bold)")


def _word_underline(path: Path) -> None:
    """Underline Words Only: two words, each underlined, the space between not."""
    u = PX * SS
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(BOLD, int(u * 0.40))
    for x, word in ((0.27, "ab"), (0.73, "cd")):
        d.text((x * u, 0.50 * u), word, font=font, fill=WHITE, anchor="ms")
        bb = d.textbbox((x * u, 0.50 * u), word, font=font, anchor="ms")
        d.rectangle([bb[0], 0.62 * u, bb[2], 0.62 * u + u * 0.07], fill=WHITE)
    img.resize((PX, PX), Image.LANCZOS).save(path)
    print(f"  {path.name}  <- drawn (two words, each underlined)")


def _reduce_hanging(path: Path) -> None:
    """Reduce Hanging Indent: the hanging-indent lines plus a left arrow."""
    u = PX * SS
    w = int(u * 0.06)
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(0.14 * u, 0.24 * u), (0.86 * u, 0.24 * u)], fill=WHITE, width=w)
    for y in (0.44, 0.62, 0.80):
        d.line([(0.52 * u, y * u), (0.86 * u, y * u)], fill=WHITE, width=w)
    # arrow pointing left, in the indent gap
    y = 0.62 * u
    d.line([(0.16 * u, y), (0.42 * u, y)], fill=WHITE, width=w)
    d.polygon([(0.10 * u, y), (0.24 * u, y - 0.11 * u), (0.24 * u, y + 0.11 * u)], fill=WHITE)
    img.resize((PX, PX), Image.LANCZOS).save(path)
    print(f"  {path.name}  <- drawn (hanging indent + left arrow)")


def _program_mark(path: Path) -> None:
    """WordCraft's own icon, its background tile dropped (page + lines + pencil)."""
    req = urllib.request.Request(APP_ICON_SVG, headers={"User-Agent": "polykybd"})
    svg = urllib.request.urlopen(req, timeout=30).read().decode()
    svg = re.sub(r"<rect [^>]*/>", "", svg, count=1)   # the blue rounded square
    path.write_bytes(cairosvg.svg2png(bytestring=svg.encode(), output_width=256, output_height=256))
    print(f"  {path.name}  <- storytold/wordcraft@{APP_SHA[:7]} assets/app-icon/wordcraft.svg (bg removed)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    icon_fetch.fluent(FLUENT, out)
    icon_fetch.borrow(BORROW, out)

    # Delete Next Word: the backspace key glyph mirrored (the forward-delete key, ⌦).
    Image.open(out / "backspace_src.png").transpose(Image.FLIP_LEFT_RIGHT).save(out / "delwordfwd.png")
    print("  delwordfwd.png  <- ms:backspace mirrored")

    if not _guarded(out / "level1.png"):
        number_badge.numbered(out / "square_src.png", "123456789", out, "level")
    for stem, (text, size) in TEXT_GLYPHS.items():
        if not _guarded(out / f"{stem}.png"):
            _text_glyph(out / f"{stem}.png", text, size)
    if not _guarded(out / "wordunderline.png"):
        _word_underline(out / "wordunderline.png")
    if not _guarded(out / "reducehang.png"):
        _reduce_hanging(out / "reducehang.png")
    if not _guarded(out / "wordcraft.png"):
        _program_mark(out / "wordcraft.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
