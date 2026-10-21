#!/usr/bin/env python3
"""Fetch + render the icons for the Office on the web overlays (reproducible).

One icon folder serves four sets: `word_web.yaml`, `excel_web.yaml`,
`powerpoint_web.yaml` and `onenote_web.yaml`. The program marks and the icons the
desktop sets already draw are copied byte for byte from `../word`, `../excel`,
`../powerpoint` and `../onenote` (`icon_fetch.borrow`), so a web key and its
desktop key show the same cell. The rest are Fluent UI System Icons (MIT), with
Material Symbols (Apache-2.0) through `ms:`.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/officeweb/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

BORROWED = {
    # program marks
    "word.png": "word",
    "excel.png": "excel",
    "powerpoint.png": "powerpoint",
    "onenote.png": "onenote",
    # Word
    "replace.png": "word",
    "clearfmt.png": "word",
    "bullets.png": "word",
    # Excel
    "goto.png": "excel",
    "table.png": "excel",
    "filter.png": "excel",
    "formatcells.png": "excel",
    "delcells.png": "excel",
    "flashfill.png": "excel",
    "filldown.png": "excel",
    "autosum.png": "excel",
    "currency.png": "excel",
    "calc.png": "excel",
    "edit.png": "excel",
    "saveas.png": "excel",
    # PowerPoint
    "newslide.png": "powerpoint",
    "duplicate.png": "powerpoint",
    "fontinc.png": "powerpoint",
    "fontdec.png": "powerpoint",
    "left.png": "powerpoint",
    "center.png": "powerpoint",
    "right.png": "powerpoint",
    "justify.png": "powerpoint",
    "hyperlink.png": "powerpoint",
    # OneNote
    "numbering.png": "onenote",
    "pastetext.png": "onenote",
    "pasteformat.png": "onenote",
    "date.png": "onenote",
    "time.png": "onenote",
    "equation.png": "onenote",
    "spelling.png": "onenote",
    "indent.png": "onenote",
    "outdent.png": "onenote",
    "rowbelow.png": "onenote",
    "firstpage.png": "onenote",
    "lastpage.png": "onenote",
    "nextpage.png": "onenote",
    "prevpage.png": "onenote",
    "moveup.png": "onenote",
    "movedown.png": "onenote",
    "tagtodo.png": "onenote",
    "tagimportant.png": "onenote",
    "tagquestion.png": "onenote",
    "tagremember.png": "onenote",
    "tagdefinition.png": "onenote",
    "taghighlight.png": "onenote",
    "tagcontact.png": "onenote",
    "tagaddress.png": "onenote",
    "tagphone.png": "onenote",
}

FLUENT = {
    "tellme": "Lightbulb",
    "ribbon": "Panel Top Contract",
    "comment": "Comment Add",
    "threadreply": "Comment Multiple",
    "note": "Note Edit",
    "chart": "Chart Multiple",
    "newsheet": "Tab Add",
    "nextsheet": "Arrow Circle Right",
    "prevsheet": "Arrow Circle Left",
    "refresh": "Arrow Clockwise",
    "refreshall": "Arrow Sync",
    "fullcalc": "Arrow Sync Circle",
    "reapplyfilter": "Filter Sync",
    "function": "Math Symbols",
    "numberfmt": "ms:123",
    "percent": "ms:percent",
    "scientific": "ms:exposure_plus_1",
    "border": "Border Outside",
    "hiderows": "ms:unfold_less",
    "hidecols": "ms:hide",
    "unhiderows": "ms:unfold_more",
    "unhide": "Eye",
    "valueabove": "ms:vertical_align_top",
    "front": "ms:flip_to_front",
    "back": "ms:flip_to_back",
    "forward": "ms:move_up",
    "backward": "ms:move_down",
    "rotleft": "Arrow Rotate Counterclockwise",
    "rotright": "Arrow Rotate Clockwise",
    "slideup": "Arrow Up",
    "slidedown": "Arrow Down",
    "slidefirst": "ms:vertical_align_top",
    "slidelast": "ms:vertical_align_bottom",
    "newoutline": "Text Box Settings",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.borrow(BORROWED, out)
    n += icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
