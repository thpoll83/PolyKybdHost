#!/usr/bin/env python3
"""Fetch + render the Todoist shortcut icons (reproducible source step).

Shortcut icons: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0, `ms:` names) where Fluent has no match. The ESC program mark is
Todoist's own monochrome mark from Simple Icons (artwork CC0-1.0), through
`../brand_marks.py`. A committed mark is left as it is.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/todoist/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks  # noqa: E402
import icon_fetch  # noqa: E402
import number_badge  # noqa: E402

ICONS = {
    # general
    "quickadd": "Add Circle",
    "newproject": "Folder Add",
    "search": "Search",
    "undo": "Arrow Undo",
    "sidebar": "Panel Left",
    "shortcuts": "Keyboard",
    "quickfind": "Search Square",
    "print": "Print",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoomreset": "Ratio One To One",
    "collapseall": "Arrow Collapse All",
    # navigation
    "home": "Home",
    "gotoproject": "Folder Arrow Right",
    "goto": "Directions",
    "open": "Open",
    "focusup": "Arrow Up",
    "focusdown": "Arrow Down",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    # tasks
    "addbottom": "ms:add_row_below",
    "addtop": "ms:add_row_above",
    "saveedits": "Save",
    "complete": "Checkmark Circle",
    "edit": "Edit",
    "setdate": "Calendar",
    "removedate": "Calendar Cancel",
    "priority": "Flag",
    "changepriority": "ms:low_priority",
    "comment": "Comment",
    "label": "Tag",
    "assign": "Person Add",
    "moveto": "Arrow Move",
    "moreactions": "More Horizontal",
    "select": "Checkbox Checked",
    "multiselect": "Select All On",
    "delete": "Delete",
    "copylink": "Link",
    "taskabove": "Arrow Circle Up",
    "taskbelow": "Arrow Circle Down",
    "indent": "Text Indent Increase",
    "outdent": "Text Indent Decrease",
    "subtasks": "Text Bullet List Tree",
    # projects
    "layout": "Board",
    "addsection": "Add Square",
    "share": "Share",
    "sortdate": "Calendar Arrow Down",
    "sortpriority": "Text Sort Descending",
    "sortname": "Text Sort Ascending",
    "sortassignee": "People Sync",
    "projectactions": "More Vertical",
    "insights": "Data Trending",
    "scrolltop": "ms:vertical_align_top",
    "scrollbottom": "ms:vertical_align_bottom",
    # upcoming
    "today": "Calendar Today",
    "prevweek": "Arrow Previous",
    "nextweek": "Arrow Next",
    # windows
    "newwindow": "Window New",
    "newhomewindow": "Window Multiple",
    "floattop": "Pin",
}


def numbered_flags(base: Path, out: Path) -> int:
    """`priority1..4.png`: the priority flag with its number beside it.

    Todoist's 1..4 keys set priority 1..4, and the number is the information.
    Inside the flag the digit collides with the banner's notch at keycap size,
    so it stands to the right of the pole, in the same font as number_badge.
    """
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(base).convert("RGBA")
    w = im.width
    font = ImageFont.truetype(number_badge.BOLD, int(w * 0.62))
    for d in "1234":
        canvas = Image.new("RGBA", (int(w * 1.5), w), (0, 0, 0, 0))
        canvas.paste(im, (0, 0), im)
        ImageDraw.Draw(canvas).text((w * 1.22, w * 0.62), d, fill=(0, 0, 0, 255),
                                    font=font, anchor="mm")
        canvas.save(out / f"priority{d}.png")
    print("  priority1..priority4.png  <- composite (priority flag + digit)")
    return 4


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(ICONS, out)
    n += numbered_flags(out / "priority.png", out)
    brand_marks.ensure(out / "todoist.png", "todoist")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
