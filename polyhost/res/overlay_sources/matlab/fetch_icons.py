#!/usr/bin/env python3
"""Fetch + render the MATLAB Editor shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The MathWorks logo is a
trademark and Simple Icons does not carry it, so the ESC mark is a generic
"ML" letter tile from `../program_marks.py`.

    pip install cairosvg
    python polyhost/res/overlay_sources/matlab/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402

FLUENT = {
    # editor window
    "maximize": "ms:open_in_full",
    "undock": "ms:open_in_new",
    "dock": "ms:dock_to_bottom",
    "editor": "ms:edit_document",
    # files
    "newscript": "Document Add",
    "reopen": "ms:history",
    # navigate
    "gotoline": "ms:format_list_numbered",
    "bookmark": "Bookmark",
    "nextbookmark": "ms:bookmark_added",
    "prevbookmark": "ms:bookmarks",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "prevvar": "ms:arrow_upward",
    "nextvar": "ms:arrow_downward",
    "filestart": "ms:vertical_align_top",
    "fileend": "ms:vertical_align_bottom",
    "prevsection": "ms:keyboard_double_arrow_up",
    "nextsection": "ms:keyboard_double_arrow_down",
    # find
    "findnext": "Chevron Down",
    "findprev": "Chevron Up",
    "replace": "ms:find_replace",
    "findsel": "ms:text_select_start",
    # code
    "comment": "ms:code_off",
    "uncomment": "Code",
    "wrap": "ms:wrap_text",
    "smartindent": "ms:format_align_left",
    "indent": "ms:format_indent_increase",
    "outdent": "ms:format_indent_decrease",
    "duplicate": "ms:content_copy",
    "changecase": "ms:match_case",
    "analyzer": "ms:report",
    # sections and running
    "sectionbreak": "ms:splitscreen_bottom",
    "runsection": "ms:play_lesson",
    "runadvance": "ms:skip_next",
    "run": "Play",
    "pause": "Pause",
    "stop": "ms:stop_circle",
    "breakpoint": "ms:radio_button_checked",
    "stepover": "ms:step_over",
    "stepin": "ms:step_into",
    "stepout": "ms:step_out",
    # live scripts
    "textline": "ms:notes",
    "normaltext": "ms:text_fields",
    "h1": "ms:format_h1",
    "h2": "ms:format_h2",
    "h3": "ms:format_h3",
    "titletext": "ms:title",
    "monospace": "ms:code_blocks",
    "bullets": "ms:format_list_bulleted",
    "numbered": "ms:format_list_numbered_rtl",
    "link": "Link",
    "equation": "ms:function",
    "latex": "ms:functions",
    "codeoutput": "ms:output",
    # display
    "fullscreen": "ms:fullscreen",
    "resetzoom": "ms:fit_screen",
    "mdpreview": "ms:preview",
    # folding
    "expand": "ms:unfold_more",
    "collapse": "ms:unfold_less",
    "expandall": "ms:unfold_more_double",
    "collapseall": "ms:unfold_less_double",
    # spelling
    "nextspell": "ms:spellcheck",
    "prevspell": "Text Grammar Arrow Left",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    program_marks.ensure(out / "matlab.png", "ML", motif="none")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
