#!/usr/bin/env python3
"""Fetch + render icons for the terminal program overlays.

One icon folder serves ten sets of programs that run inside a terminal:
lazygit, k9s, htop, btop, Midnight Commander, Yazi, micro, Helix, less and
GDB. Style route as for the other app folders: Microsoft Fluent UI System
Icons (MIT), with Material Symbols (Apache-2.0) through `ms:` where Fluent has
no match. Icons the AI CLI, AI desktop app, nano and IDE sets already draw are
copied byte for byte, so each glyph is stored once in the icon library.

Program marks: htop, Helix and micro from Simple Icons (`../brand_marks.py`,
artwork CC0); the others are drawn letter frames (`../rect_mark.py`).

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/tui/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks, icon_fetch, rect_mark  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

FLUENT = {
    # --- shared ---
    "copy": "Copy",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "save": "Save",
    "delete": "Delete",
    "filter": "Filter",
    "sort": "Arrow Sort",
    "menu": "Navigation",
    "open": "Open",
    "openfile": "Folder Open",
    "newfile": "Document Add",
    "newtab": "Tab Add",
    "tab_new": "Tab Add",
    "selectall": "Select All On",
    "cancel": "Dismiss Circle",
    "swap": "Arrow Swap",
    "merge": "Merge",
    "pause": "ms:pause_circle",
    "tag": "Tag",
    "untag": "Tag Dismiss",
    "user": "Person",
    "path": "Folder Link",
    "image": "Image",
    "sync": "Arrow Sync",
    "reset": "Arrow Counterclockwise",
    "details": "Info",
    "describe": "Info",
    "fileinfo": "Document Text",
    "option": "Options",
    "version": "Number Symbol Square",
    "tree": "Text Bullet List Tree",
    "collapse": "Arrow Minimize",
    "shrink": "Arrow Minimize Vertical",
    "expand_all": "Arrow Expand",
    "jump": "Flash",
    "visual": "Cursor Hover",
    "insert": "Text Edit Style",
    "pipe": "Arrow Export",
    "pipe_to": "Arrow Export Up",
    # --- htop / btop ---
    "kill": "ms:dangerous",
    "terminate": "Stop",
    "signal": "Alert",
    "sort_mem": "ms:memory_alt",
    "sort_cpu": "ms:memory",
    "sort_pid": "Number Symbol",
    "sort_time": "Timer",
    "sort_invert": "Arrow Sort Up",
    "sort_prev": "Arrow Left",
    "sort_next": "Arrow Right",
    "nice_up": "Arrow Circle Up",
    "nice_down": "Arrow Circle Down",
    "affinity": "ms:account_tree",
    "env": "Globe",
    "lsof": "Document Multiple",
    "strace": "Bug",
    "command": "Code",
    "locks": "Lock Closed",
    "hide_threads": "Eye Off",
    "hide_kernel": "Shield",
    "hide_containers": "Box",
    "hide_meters": "Data Bar Horizontal",
    "screen_tab": "Tab",
    "screen_tab_prev": "ms:tab_unselected",
    "box_cpu": "ms:memory",
    "box_mem": "ms:memory_alt",
    "box_net": "ms:lan",
    "box_proc": "ms:list_alt",
    "preset": "Layout Column Two",
    "preset_prev": "Layout Column Two Split Left",
    "timer_up": "ms:more_time",
    "timer_down": "Timer Off",
    "percore": "Grid Dots",
    "mem_mode": "ms:data_usage",
    "disks": "Hard Drive",
    "io_mode": "ms:swap_vert",
    "net_prev": "Arrow Previous",
    "net_next": "Arrow Next",
    "autoscale": "Arrow Maximize",
    # --- Midnight Commander / Yazi ---
    "move": "Folder Arrow Right",
    "hotlist": "Star",
    "dirsize": "Data Pie",
    "selectup": "ms:keyboard_double_arrow_up",
    "selectdown": "ms:keyboard_double_arrow_down",
    "cdchild": "ms:subdirectory_arrow_right",
    "cdparent": "Folder Arrow Up",
    "listing": "Text Bullet List",
    "otherpanel": "Panel Right",
    "panelsync": "ms:sync_alt",
    "codepage": "Translate",
    "selectgroup": "ms:select_check_box",
    "unselectgroup": "ms:check_box_outline_blank",
    "invert": "ms:flip",
    "hidden": "Eye",
    "screens": "Window Multiple",
    "splitequal": "ms:view_column",
    "pathcurrent": "ms:content_paste_go",
    "pathother": "ms:content_paste_search",
    "pathfile": "ms:content_paste",
    "tab_swap": "ms:swap_horiz",
    # --- micro / Helix ---
    "cutline": "ms:content_cut",
    "duplicate": "ms:control_point_duplicate",
    "overwrite": "ms:keyboard",
    "moveup": "Arrow Up",
    "movedown": "Arrow Down",
    "prevchange": "ms:keyboard_arrow_up",
    "nextchange": "ms:keyboard_arrow_down",
    "multicursor": "Cursor Click",
    "multicursorsel": "ms:select",
    "cursorabove": "ms:arrow_upward",
    "cursorbelow": "ms:arrow_downward",
    "cursorremove": "ms:do_not_disturb_on",
    "cursorsclear": "ms:cancel",
    "cursorskip": "ms:skip_next",
    "arrowleft": "ms:west",
    "arrowright": "ms:east",
    "arrowup": "ms:north",
    "arrowdown": "ms:south",
    "wordnext": "ms:text_select_move_forward_word",
    "wordprev": "ms:text_select_move_back_word",
    "wordend": "ms:text_select_end",
    "findchar": "ms:find_in_page",
    "findchar_back": "ms:manage_search",
    "tillchar": "ms:keyboard_tab",
    "tillchar_back": "ms:keyboard_tab_rtl",
    "repeatmotion": "Arrow Repeat All",
    "insert_start": "ms:format_align_left",
    "insert_end": "ms:format_align_right",
    "append": "ms:post_add",
    "openabove": "ms:vertical_align_top",
    "openbelow": "ms:vertical_align_bottom",
    "delete_noyank": "ms:delete_forever",
    "change": "Edit",
    "change_noyank": "Edit Off",
    "replace": "ms:find_replace",
    "replace_yank": "ms:swap_calls",
    "lowercase": "ms:lowercase",
    "uppercase": "ms:uppercase",
    "switchcase": "Text Change Case",
    "join": "ms:join",
    "format": "Text Align Left",
    "increment": "Add Circle",
    "decrement": "Subtract Circle",
    "register": "Database",
    "selectline": "ms:select_all",
    "linebounds": "ms:expand",
    "shrinkline": "ms:compress",
    "selectregex": "ms:regular_expression",
    "splitsel": "ms:call_split",
    "splitnewline": "ms:wrap_text",
    "flip": "ms:flip",
    "forward": "Arrow Forward",
    "keepprimary": "ms:my_location",
    "removeprimary": "ms:location_disabled",
    "keepsel": "ms:filter_alt",
    "removesel": "ms:filter_alt_off",
    "mergesel": "ms:merge",
    "mergeconsec": "ms:merge_type",
    "trim": "ms:content_cut",
    "align": "ms:align_horizontal_left",
    "rotate_back": "Arrow Rotate Counterclockwise",
    "rotate_fwd": "Arrow Rotate Clockwise",
    "search_selection": "ms:saved_search",
    "children": "Flowchart",
    "siblings": "ms:account_tree",
    "prevsibling": "ms:first_page",
    "nextsibling": "ms:last_page",
    "parentstart": "ms:vertical_align_top",
    "parentend": "ms:vertical_align_bottom",
    "shell_insert": "ms:input",
    "shell_append": "ms:output",
    "shell_keep": "ms:filter_list",
    # --- less ---
    "halfdown": "ms:keyboard_double_arrow_down",
    "halfup": "ms:keyboard_double_arrow_up",
    "follow": "ms:vertical_align_bottom",
    "highlight": "Highlight",
    "clearhighlight": "Eraser",
    "gotomark": "Bookmark",
    "clearmark": "Bookmark Off",
    # --- GDB one-letter commands ---
    "gdb_break": "ms:radio_button_checked",
    "gdb_continue": "ms:play_circle",
    "gdb_frame": "ms:layers",
    "gdb_run": "ms:play_arrow",
    "gdb_thread": "ms:alt_route",
    # --- lazygit ---
    "push": "Arrow Upload",
    "pull": "Arrow Download",
    "fetch": "Cloud Arrow Down",
    "commit": "Checkmark Circle",
    "amend": "ms:edit_note",
    "stage": "ms:add_box",
    "stageall": "ms:library_add",
    "stagelines": "Text Line Spacing",
    "discard": "ms:undo",
    "resettree": "History Dismiss",
    "ignore": "Eye Off",
    "findbase": "ms:frame_inspect",
    "rebaseoptions": "Branch Fork",
    "mergetool": "ms:call_merge",
    "difftool": "ms:difference",
    "patch": "Document Edit",
    "commandlog": "ms:terminal",
    "contextmore": "Add Square",
    "contextless": "Subtract Square",
    # --- k9s ---
    "aliases": "ms:label",
    "header": "ms:web_asset",
    "crumbs": "ms:chevron_right",
    "containers": "Cube Multiple",
    "yaml": "ms:data_object",
    "namespace": "Folder",
    "logs": "ms:receipt_long",
    "attachpod": "Plug Connected",
    "transfer": "ms:sync_alt",
    "sanitize": "ms:cleaning_services",
    "node": "Server",
    "owner": "ms:arrow_upward",
    "portforward": "ms:settings_ethernet",
}

BRAND = {"htop.png": "htop", "helix.png": "helix", "micro.png": "microeditor"}
LETTERS = {"btop.png": "bt", "mc.png": "MC", "yazi.png": "YZ", "lazygit.png": "LG",
           "k9s.png": "K9", "less.png": "LS", "gdb.png": "GDB"}

BORROWED = {
    **{name: "aicli" for name in (
        "activity.png", "checklist.png", "clear.png", "commandpalette.png",
        "deleteline.png", "editor.png", "exit.png", "expand.png", "file_end.png",
        "file_start.png", "find.png", "history.png", "leader.png", "next.png",
        "page_down.png", "page_up.png", "prev.png", "rawoutput.png", "redo.png",
        "reload.png", "rename.png", "scroll_down.png", "scroll_up.png",
        "search.png", "shortcuts.png", "stash.png", "stop.png", "suspend.png",
        "terminal.png", "undo.png", "viewmode.png", "warnings.png")},
    **{name: "aichat" for name in (
        "back.png", "close.png", "diff.png", "filelist.png", "focusnext.png",
        "link.png", "newfolder.png", "openfolder.png", "recents.png",
        "settings.png", "splitright.png",
        *(f"tab{d}.png" for d in "123456789"))},
    # GDB's stepping and breakpoint keys use the IDE sets' debugger icons.
    **{name: "vscode" for name in ("stepover.png", "stepinto.png")},
    **{name: "jetbrains" for name in ("runtocursor.png",)},
    **{name: "visualstudio" for name in ("quickwatch.png",)},
    **{name: "nano" for name in (
        "bracket.png", "comment.png", "find_next.png", "find_prev.png",
        "goto_line.png", "helplines.png", "indent.png", "linenumbers.png",
        "macro_record.png", "macro_run.png", "mark.png", "recenter.png",
        "row_bottom.png", "row_top.png", "scroll_left.png", "scroll_right.png",
        "search_back.png", "search_fwd.png", "unindent.png", "whitespace.png")},
}


def stamp_delete_breakpoint(out: Path) -> None:
    """`gdb_delete.png`: the breakpoint glyph (`gdb_break.png`, a ring around a
    filled dot) with an X cut out of the dot."""
    im = Image.open(out / "gdb_break.png").convert("RGBA")
    w, h = im.size
    cx, cy, r, stroke = w / 2, h / 2, w * 0.13, max(2, round(w * 0.075))
    cut = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(cut)
    d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=255, width=stroke)
    d.line([(cx - r, cy + r), (cx + r, cy - r)], fill=255, width=stroke)
    alpha = im.getchannel("A")
    im.putalpha(Image.composite(Image.new("L", im.size, 0), alpha, cut))
    im.save(out / "gdb_delete.png")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    for fname, slug in BRAND.items():
        brand_marks.ensure(out / fname, slug)
    for fname, letters in LETTERS.items():
        rect_mark.ensure(out / fname, letters)
    n += icon_fetch.borrow(BORROWED, out)
    stamp_delete_breakpoint(out)
    print(f"Wrote {n} icons (+ {len(BRAND) + len(LETTERS)} program marks) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
