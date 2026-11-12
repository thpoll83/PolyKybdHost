#!/usr/bin/env python3
"""Fetch + render the Thunderbird shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. Tabs 1..9 and tags 0..9
are numbered glyphs from `../number_badge.py`. No program icon: the host draws
the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/thunderbird/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, number_badge  # noqa: E402

FLUENT = {
    # --- main window: messages ---
    "newmsg": "ms:edit_square",
    "getmsg": "ms:download",
    "getall": "ms:downloading",
    "reply": "ms:reply",
    "replyall": "ms:reply_all",
    "replylist": "ms:groups",
    "forward": "ms:forward",
    "editnew": "ms:edit_note",
    "openmsg": "ms:open_in_new",
    "conversation": "ms:forum",
    "moveagain": "ms:drive_file_move",
    "savefile": "ms:file_save",
    "source": "ms:code",
    "search": "ms:manage_search",
    "quickfilter": "ms:filter_alt",
    "searchmsgs": "ms:search_insights",
    "msgpane": "ms:vertical_split",
    "todaypane": "ms:right_panel_open",
    "rename": "ms:drive_file_rename_outline",
    "help": "ms:help",
    "history": "ms:history",
    "addressbook": "ms:contacts",
    "savedfiles": "ms:list_alt",
    "back": "ms:arrow_back",
    "fwd": "ms:arrow_forward",
    "reopentab": "ms:tab_recent",
    "selthread": "ms:select_all",
    "deleteperm": "ms:delete_forever",
    "nexttab": "ms:keyboard_tab",
    "prevtab": "ms:keyboard_tab_rtl",
    "newevent": "ms:event",
    "newtask": "ms:add_task",
    # spaces
    "spacemail": "ms:mail",
    "spacecontacts": "ms:contacts",
    "spacecalendar": "ms:calendar_month",
    "spacetasks": "ms:task_alt",
    "spacechat": "ms:chat",
    # message list keys
    "readunread": "ms:mark_email_unread",
    "star": "ms:star",
    "junk": "ms:report",
    "notjunk": "ms:verified_user",
    "allread": "ms:mark_email_read",
    "threadread": "ms:mark_chat_read",
    "readbydate": "ms:event_available",
    "nextmsg": "ms:keyboard_arrow_down",
    "nextunread": "ms:keyboard_double_arrow_down",
    "nextthread": "ms:arrow_downward",
    "prevmsg": "ms:keyboard_arrow_up",
    "prevunread": "ms:keyboard_double_arrow_up",
    "archive": "ms:archive",
    "watch": "ms:visibility",
    "ignore": "ms:visibility_off",
    "ignoresub": "ms:notifications_off",
    "expand": "ms:unfold_more",
    "collapse": "ms:unfold_less",
    "notags": "Tag Off",
    # --- compose window ---
    "send": "ms:send",
    "sendlater": "ms:schedule_send",
    "savedraft": "ms:drafts",
    "pastequote": "ms:format_quote",
    "pasteplain": "ms:content_paste_go",
    "rewrap": "ms:wrap_text",
    "attach": "ms:attach_file",
    "attachpane": "ms:attachment",
    "reorder": "ms:reorder",
    "sortattach": "ms:sort_by_alpha",
    "to": "ms:person",
    "cc": "ms:person_add",
    "bcc": "ms:visibility_off",
    "contacts": "ms:left_panel_open",
    "spell": "ms:spellcheck",
    "mainwin": "ms:home",
    "fixedwidth": "ms:format_shapes",
    "indent": "ms:format_indent_increase",
    "outdent": "ms:format_indent_decrease",
    "clearstyle": "ms:format_clear",
    "unlink": "ms:link_off",
    "anchors": "ms:anchor",
    "fontdown": "ms:text_decrease",
    "fontup": "ms:text_increase",
    "link": "ms:add_link",
    "findprev": "ms:youtube_searched_for",
    "zoomreset": "ms:fit_screen",
    # bases for the numbered glyphs
    "_tabbase": "Tab",
    "_tagbase": "Tag",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += number_badge.numbered(out / "_tabbase.png", "123456789", out, "tab")
    # Smaller than the default, so the digit clears the outline and the hole.
    n += number_badge.numbered(out / "_tagbase.png", "123456789", out, "tag",
                               size=0.40, centre=(0.50, 0.53))
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
