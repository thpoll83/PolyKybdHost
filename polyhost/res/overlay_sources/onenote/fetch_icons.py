#!/usr/bin/env python3
"""Fetch + render the Microsoft OneNote shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. Outline levels
(Alt+Shift+1..9) are numbered squares from `../number_badge.py`, because the
number is the information. The program icon (ESC) is the Office-family drawn
mark with an "N" (no Microsoft logo); a committed `onenote.png` is left as-is.

    pip install cairosvg Pillow numpy
    python polyhost/res/overlay_sources/onenote/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, number_badge  # noqa: E402

RENDER_PX = 96

FLUENT = {
    # --- edit / file ---
    "newpage": "Document Add",
    "newwindow": "Window New",
    "quicknote": "Note Add",
    "dock": "Panel Right",
    "open": "Folder Open",
    "print": "Print",
    "sync": "Arrow Sync",
    "syncall": "Arrow Sync Circle",
    "pastetext": "ms:content_paste_go",
    "copy": "Copy",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "selectall": "Select All On",
    "selectpage": "Document Checkmark",
    "selectpara": "Text Paragraph",
    "pagetitle": "Document Header",
    # --- format ---
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "strike": "Text Strikethrough",
    "superscript": "Text Superscript",
    "subscript": "Text Subscript",
    "highlight": "Highlight",
    "hyperlink": "Link",
    "copyformat": "Paint Brush",
    "pasteformat": "Paint Brush Arrow Down",
    "bullets": "Text Bullet List",
    "numbering": "ms:format_list_numbered",
    "clearfmt": "Text Clear Formatting",
    "left": "Text Align Left",
    "right": "Text Align Right",
    "fontinc": "Font Increase",
    "fontdec": "Font Decrease",
    "indent": "Text Indent Increase",
    "outdent": "Text Indent Decrease",
    "rulelines": "Ruler",
    "h1": "Text Header 1",
    "h2": "Text Header 2",
    "h3": "Text Header 3",
    "h4": "Text Header 4",
    "h5": "Text Header 5",
    "h6": "Text Header 6",
    # --- insert ---
    "date": "Calendar",
    "datetime": "Calendar Clock",
    "time": "Clock",
    "equation": "Math Formula",
    "rowbelow": "Table Insert Row",
    "colright": "ms:add_column_right",
    "colleft": "ms:add_column_left",
    # --- tags (Ctrl+1..9, Ctrl+0) ---
    "tagtodo": "Checkbox Checked",
    "tagimportant": "Star",
    "tagquestion": "Question Circle",
    "tagremember": "Bookmark",
    "tagdefinition": "Book",
    "taghighlight": "ms:ink_highlighter",
    "tagcontact": "Person",
    "tagaddress": "Location",
    "tagphone": "Call",
    "tagclear": "Tag Dismiss",
    # --- outline ---
    "moveup": "Arrow Up",
    "movedown": "Arrow Down",
    "expand": "Chevron Down",
    "collapse": "Chevron Up",
    "expandall": "Text Expand",
    "pagegroup": "Text Collapse",
    "_levelbase": "Square",
    # --- pages, sections, notebooks ---
    "notebook": "Notebook",
    "newsection": "Tab Add",
    "opensection": "Notebook Section Arrow Right",
    "subpage": "ms:subdirectory_arrow_right",
    "nextsection": "Arrow Circle Right",
    "prevsection": "Arrow Circle Left",
    "nextpage": "Document Arrow Down",
    "prevpage": "Document Arrow Up",
    "firstpage": "Arrow Previous",
    "lastpage": "Arrow Next",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "movepage": "Arrow Move",
    "copypage": "Document Copy",
    "navwider": "Panel Left Expand",
    "navnarrower": "Panel Left Contract",
    "pagein": "Text Indent Increase",
    "pageout": "Text Indent Decrease",
    "fullpage": "Full Screen Maximize",
    "closenb": "Dismiss",
    "settings": "Settings",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoomreset": "Zoom Fit",
    # --- search ---
    "find": "Search",
    "searchall": "Book Search",
    "nextresult": "Arrow Down",
    "prevresult": "Arrow Up",
    "lookup": "Lightbulb",
    # --- review / share / audio ---
    "spelling": "Text Grammar Checkmark",
    "thesaurus": "Book Open",
    "email": "Mail",
    "markunread": "Mail Unread",
    "lock": "Lock Closed",
    "play": "Play",
    "stop": "Stop",
    "rewind": "Rewind",
    "fastforward": "Fast Forward",
    "record": "Record",
    # --- Outlook tasks (Ctrl+Shift+1..5, K, 9, 0) ---
    "tasktoday": "Calendar Today",
    "tasktomorrow": "Calendar Arrow Right",
    "taskweek": "ms:date_range",
    "tasknextweek": "ms:next_week",
    "tasknodate": "Task List Add",
    "taskopen": "ms:task",
    "taskdone": "Checkmark Circle",
    "taskdelete": "Delete",
}


def _draw_onenote_logo(path: Path) -> None:
    """Office-family program icon, drawn (no Microsoft logo): the rotated
    trapezoid on the left with an 'N' knocked out, plus a rounded rect on the
    right with three section tabs on its right edge. Same geometry as Word's
    mark (`../word/fetch_icons.py`), so the family reads as one set. White on
    transparent; the bindings render it with `program_icon_mode: alpha`."""
    ss = 4
    u = RENDER_PX * ss
    px = lambda n: n * ss          # final px -> supersampled px

    right = Image.new("L", (u, u), 0)
    dr = ImageDraw.Draw(right)
    dr.rounded_rectangle([0.50 * u, 0.24 * u, 0.88 * u, 0.76 * u],
                         radius=0.08 * u, outline=255, width=px(3))
    for y in (0.30, 0.45, 0.60):
        dr.rectangle([0.84 * u, y * u, 0.95 * u, (y + 0.09) * u], fill=255)

    right_x = 0.58 * u
    trap = Image.new("L", (u, u), 0)
    ImageDraw.Draw(trap).polygon(
        [(0.10 * u, 0.20 * u), (right_x, 0.11 * u),
         (right_x, 0.89 * u), (0.10 * u, 0.80 * u)], fill=255)
    nmask = Image.new("L", (u, u), 0)
    dn = ImageDraw.Draw(nmask)
    font = None
    for cand in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(cand, int(u * 0.34))
            break
        except OSError:
            continue
    if font:
        bb = dn.textbbox((0, 0), "N", font=font)
        cx, cy = (0.10 * u + right_x) / 2, 0.50 * u
        dn.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
                "N", font=font, fill=255)
    knock = np.where(np.asarray(nmask) > 127, 0, np.asarray(trap)).astype(np.uint8)

    alpha = np.maximum(np.asarray(right), knock)
    rgba = np.zeros((u, u, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = alpha
    Image.fromarray(rgba, "RGBA").resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += number_badge.numbered(out / "_levelbase.png", "123456789", out, "level")
    if (out / "onenote.png").exists():
        print("  onenote.png  <- committed asset (left as-is)")
    else:
        _draw_onenote_logo(out / "onenote.png")
        print("  onenote.png  <- drawn program mark")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
