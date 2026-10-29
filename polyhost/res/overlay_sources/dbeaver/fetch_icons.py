#!/usr/bin/env python3
"""Fetch + render the DBeaver shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The ESC mark is the DBeaver
logo from Simple Icons (CC0 artwork; nominative use, see `../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/dbeaver/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    # --- connections and scripts ---
    "newconnection": "Database Plug Connected",
    "gotoobject": "Database Search",
    "newconsole": "Window Console",
    "newscript": "Document Add",
    "openscript": "Document Arrow Right",
    "openobject": "Table Edit",
    "commit": "Checkmark Circle",
    "rollback": "Arrow Undo",
    "selectschema": "ms:schema",
    "selectconnection": "Database Link",
    "syncconnection": "ms:sync_alt",
    "linkeditor": "Link",
    "setdefault": "Star",
    "tools": "Wrench",
    "dashboard": "Data Area",
    "uuid": "ms:fingerprint",
    "bookmark": "Bookmark",
    "aicomplete": "Sparkle",
    # --- SQL editor ---
    "runstatement": "Play",
    "runnewtab": "ms:play_arrow",
    "runscript": "ms:fast_forward",
    "runnative": "ms:terminal",
    "runfromhere": "ms:skip_next",
    "runtabs": "ms:tab_group",
    "allrows": "Table",
    "expression": "ms:function",
    "explain": "ms:account_tree",
    "format": "Text Indent Increase",
    "output": "ms:output",
    "results": "Panel Bottom",
    "maxresults": "ms:open_in_full",
    "switchpanel": "ms:swap_vert",
    "closeresults": "Dismiss Square",
    "pintab": "Pin",
    "loadfile": "Folder Open",
    "comment": "ms:comment",
    "blockcomment": "ms:code_blocks",
    "wordwrap": "Text Wrap",
    "renamescript": "Rename",
    "matchbracket": "ms:data_array",
    "selectbrackets": "ms:select",
    "nextquery": "Arrow Down",
    "prevquery": "Arrow Up",
    "autocomplete": "ms:auto_awesome_motion",
    # --- results ---
    "reject": "Dismiss Circle",
    "fetchall": "ms:all_inclusive",
    "fetchpage": "ms:read_more",
    "frombelow": "ms:arrow_upward_alt",
    "addrow": "Table Insert Row",
    "addrowbefore": "ms:add_row_above",
    "duplicaterow": "Copy Add",
    "deleterow": "Table Delete Row",
    "setnull": "Eraser",
    "presentation": "ms:view_quilt",
    "references": "ms:key",
    "sort": "Arrow Sort",
    "panels": "Panel Right",
    "focuspanel": "ms:right_panel_open",
    "focusfilter": "ms:manage_search",
    "gotorow": "ms:table_rows",
    "gotocolumn": "Column",
    "selectcolumn": "Column Edit",
    "selectrow": "ms:select_all",
    "firstrow": "ms:first_page",
    "lastrow": "ms:last_page",
    "prevrow": "ms:chevron_left",
    "nextrow": "ms:chevron_right",
    "followlink": "ms:north_east",
    "distinct": "ms:filter_1",
    "filtermenu": "ms:filter_list",
    "fontup": "Text Font Size",
    "fontdown": "ms:text_decrease",
    "advcopy": "Copy",
    "advcopylast": "Copy Arrow Right",
    "advpaste": "Clipboard Paste",
    # --- Eclipse platform ---
    "saveall": "Save Multiple",
    "closeall": "ms:cancel_presentation",
    "rename": "ms:edit",
    "refresh": "Arrow Clockwise",
    "properties": "Info",
    "findactions": "ms:bolt",
    "shortcuts": "Keyboard",
    "search": "Document Search",
    "openitem": "Open",
    "maximize": "Maximize",
    "nexteditor": "ms:keyboard_tab",
    "preveditor": "ms:keyboard_tab_rtl",
    "nexttab": "ms:tab",
    "prevtab": "ms:tab_unselected",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "fullscreen": "ms:fullscreen",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    brand_marks.ensure(out / "dbeaver.png", "dbeaver")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
