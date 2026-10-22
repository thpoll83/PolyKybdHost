#!/usr/bin/env python3
"""Fetch + render the RStudio shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The pane-zoom keys are
numbered glyphs from `../number_badge.py`. The ESC mark is the RStudio logo
from Simple Icons (`rstudioide`, CC0 artwork; nominative use, see
`../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/rstudio/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch, number_badge  # noqa: E402

FLUENT = {
    # general
    "palette": "Apps List Detail",
    "shortcuts": "Keyboard",
    "gotofile": "Document Search",
    "setwd": "Folder Arrow Right",
    "clearconsole": "ms:clear_all",
    "terminal": "Window Console",
    "newterminal": "ms:add_to_queue",
    "restart": "Arrow Clockwise",
    # documents
    "newscript": "Document Add",
    "saveall": "Save Multiple",
    "closeall": "ms:tab_close",
    "outline": "ms:toc",
    "knit": "ms:article",
    "insertchunk": "ms:add_box",
    "insertsection": "ms:splitscreen_bottom",
    # run
    "runline": "Play",
    "runretain": "Play Circle",
    "rerun": "ms:replay",
    "runall": "ms:fast_forward",
    "runtoline": "ms:vertical_align_top",
    "runfromline": "ms:vertical_align_bottom",
    "runfunction": "ms:function",
    "runsection": "ms:play_lesson",
    "runchunk": "ms:play_arrow",
    "nextchunk": "ms:skip_next",
    "sourcefile": "Document Arrow Right",
    "sourcedoc": "ms:input",
    "sourceecho": "ms:subtitles",
    "toterminal": "ms:terminal",
    # navigate
    "fold": "ms:unfold_less",
    "unfold": "ms:unfold_more",
    "foldall": "ms:unfold_less_double",
    "unfoldall": "ms:unfold_more_double",
    "gotoline": "ms:format_list_numbered",
    "jumpto": "ms:jump_to_element",
    "nextsection": "ms:keyboard_double_arrow_down",
    "prevsection": "ms:keyboard_double_arrow_up",
    "switchtab": "ms:tab",
    "prevtab": "ms:keyboard_tab_rtl",
    "nexttab": "ms:keyboard_tab",
    "firsttab": "ms:first_page",
    "lasttab": "ms:last_page",
    "navback": "Arrow Left",
    "navfwd": "Arrow Right",
    "matchbrace": "ms:data_object",
    # edit
    "expandsel": "ms:expand_content",
    "shrinksel": "ms:collapse_content",
    "cursorup": "ms:text_select_jump_to_beginning",
    "cursordown": "ms:text_select_jump_to_end",
    "lineup": "ms:move_up",
    "linedown": "ms:move_down",
    "copyup": "ms:arrow_upward",
    "copydown": "ms:arrow_downward",
    "deleteline": "Delete Lines",
    "comment": "ms:code_off",
    "reflow": "ms:wrap_text",
    "reindent": "ms:format_indent_increase",
    "reformat": "ms:format_align_left",
    "extractfn": "ms:function",
    "extractvar": "ms:variables",
    "rename": "Rename",
    "roxygen": "ms:description",
    "assign": "ms:arrow_back",
    "pipe": "ms:conversion_path",
    "pasteindent": "ms:content_paste_go",
    # find
    "findnext": "Chevron Down",
    "findprev": "Chevron Up",
    "usesel": "ms:text_select_start",
    "replacefind": "ms:find_replace",
    "findinfiles": "Document Search",
    "spell": "ms:spellcheck",
    "help": "Question Circle",
    "showsource": "Code",
    # build
    "installrestart": "ms:install_desktop",
    "loadall": "ms:upload",
    "testpkg": "ms:science",
    "checkpkg": "ms:checklist",
    "docpkg": "ms:menu_book",
    # debug
    "breakpoint": "ms:radio_button_checked",
    "stepover": "ms:step_over",
    "stepinto": "ms:step_into",
    "stepout": "ms:step_out",
    "continue": "ms:resume",
    "stopdebug": "ms:stop_circle",
    # plots, git
    "prevplot": "ms:arrow_back_ios",
    "nextplot": "ms:arrow_forward_ios",
    "gitdiff": "ms:difference",
    "gitcommit": "ms:commit",
    # panes (Ctrl+1..9)
    "pane1": "Code",
    "pane2": "Window Console",
    "pane3": "Question Circle",
    "pane4": "History",
    "pane5": "Folder",
    "pane6": "Data Line",
    "pane7": "Box",
    "pane8": "ms:data_table",
    "pane9": "ms:preview",
    "_zoombase": "ms:fullscreen",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    number_badge.numbered(out / "_zoombase.png", "123456789", out, "zoom",
                          size=0.42, centre=(0.50, 0.50))
    brand_marks.ensure(out / "rstudio.png", "rstudioide")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
