#!/usr/bin/env python3
"""Fetch + render the JupyterLab shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The sidebar panel keys are
numbered glyphs from `../number_badge.py`. The ESC mark is the Jupyter logo from
Simple Icons (CC0 artwork; nominative use, see `../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/jupyter/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch, number_badge  # noqa: E402

FLUENT = {
    "run": "Play",
    "runnext": "ms:arrow_downward",
    "runinsert": "ms:playlist_add",
    "cmdmode": "ms:edit_off",
    "splitcell": "Split Horizontal",
    "mergebelow": "ms:merge",
    "mergeabove": "ms:vertical_align_top",
    "moveup": "ms:move_up",
    "movedown": "ms:move_down",
    "collapseall": "ms:unfold_less_double",
    "expandall": "ms:unfold_more_double",
    "histprev": "ms:history",
    "histnext": "ms:update",
    "comment": "ms:code_off",
    "blockcomment": "ms:code_blocks",
    "deleteline": "Delete Lines",
    "selectnext": "ms:text_select_move_forward_word",
    "saveas": "Save Copy",
    "findnext": "Chevron Down",
    "findprev": "Chevron Up",
    "findsel": "ms:frame_inspect",
    "palette": "Apps List Detail",
    "shortcuts": "Keyboard",
    "leftarea": "Panel Left",
    "rightarea": "Panel Right",
    "filebrowser": "Folder Open",
    "toc": "ms:toc",
    "running": "ms:memory",
    "launcher": "Rocket",
    "extensions": "Puzzle Piece",
    "debugger": "Bug",
    "propinsp": "Wrench",
    "inspector": "Question Circle",
    "settings": "Settings",
    "nexttab": "ms:keyboard_tab",
    "prevtab": "ms:keyboard_tab_rtl",
    "nexttabbar": "ms:switch_right",
    "prevtabbar": "ms:switch_left",
    "lasttab": "ms:swap_horiz",
    "closetab": "Dismiss",
    "continue": "ms:resume",
    "terminate": "ms:stop_circle",
    "stepover": "ms:step_over",
    "stepout": "ms:step_out",
    # notebook command mode
    "insertabove": "ms:add_row_above",
    "insertbelow": "ms:add_row_below",
    "headingabove": "ms:vertical_align_top",
    "headingbelow": "ms:vertical_align_bottom",
    "cutcell": "Cut",
    "copycell": "Copy",
    "pastecell": "Clipboard Paste",
    "undocell": "Arrow Undo",
    "redocell": "Arrow Redo",
    "tocode": "Code",
    "tomarkdown": "ms:markdown",
    "toraw": "ms:raw_on",
    "mergecells": "ms:call_merge",
    "cellbelow": "Arrow Down",
    "cellabove": "Arrow Up",
    "extendbelow": "ms:keyboard_double_arrow_down",
    "extendabove": "ms:keyboard_double_arrow_up",
    "linenumbers": "ms:format_list_numbered",
    "sidebyside": "Split Vertical",
    "_heading": "ms:title",
    "_lbase": "Panel Left",
    "_rbase": "Panel Right",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    number_badge.numbered(out / "_lbase.png", "123456789", out, "left",
                          size=0.40, centre=(0.62, 0.50))
    number_badge.numbered(out / "_rbase.png", "123456789", out, "right",
                          size=0.40, centre=(0.38, 0.50))
    number_badge.numbered(out / "_heading.png", "123456", out, "heading",
                          size=0.40, centre=(0.78, 0.72))
    brand_marks.ensure(out / "jupyter.png", "jupyter")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
