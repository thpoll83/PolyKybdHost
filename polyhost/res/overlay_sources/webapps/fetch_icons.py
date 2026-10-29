#!/usr/bin/env python3
"""Fetch + render icons for the browser-hosted app overlays.

One icon folder serves the browser sets — `github.yaml`, `gitlab.yaml`,
`confluence.yaml`, `confluence_whiteboard.yaml`, `googledocs.yaml`, `notion.yaml`, `jira.yaml`, `web_outlook.yaml`,
`bitbucket.yaml` and the Google sets of `gen_google_specs.py` (Sheets, Slides,
Gmail, Calendar), `drawio.yaml`, `excalidraw.yaml`, `linear.yaml` and
`overleaf.yaml`. They are grouped
because they share a large command vocabulary (search, edit, comment, submit,
and the markdown/rich-text formatting run of bold/italic/link/lists/headings);
duplicating ~30 identical PNGs five times would be pure noise in the tree.

Style route: **Microsoft Fluent UI System Icons (MIT)**. The five ESC
**program marks** come from three sources: GitHub and GitLab use their real
monochrome logos (`../brand_marks.py`, artwork CC0), Google Docs and Notion get
drawn substitutes (`../doc_mark.py` / `../rect_mark.py`), and Confluence is
rebuilt from its geometry (`../geo_marks.py`).

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/webapps/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks, doc_mark, geo_marks, icon_fetch  # noqa: E402
import rect_mark  # noqa: E402
import material_symbols as ms  # noqa: E402

FLUENT = {
    # --- shared: navigation & chrome ---
    "search": "Search",
    "commandpalette": "Apps List Detail",
    "shortcuts": "Keyboard",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "newpage": "Document Add",
    "open": "Folder Open",
    "save": "Save",
    "print": "Print",
    "duplicate": "Square Multiple",
    "darkmode": "Weather Moon",
    "settings": "Settings",
    "sidebar": "Panel Left",
    "rightsidebar": "Panel Right",
    "newtab": "Tab Desktop",
    "closetab": "Dismiss",
    "graph": "Branch Fork",
    # --- shared: editing ---
    "edit": "Document Edit",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "pasteplain": "Clipboard Paste",
    "selectall": "Select All On",
    "find": "Search",
    "findreplace": "Arrow Swap",
    "findfiles": "Document Search",
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "strikethrough": "Text Strikethrough",
    "code": "Code",
    "codeblock": "Code Block",
    "link": "Link",
    "quote": "Text Quote",
    "clearfmt": "Text Clear Formatting",
    "superscript": "Text Superscript",
    "subscript": "Text Subscript",
    "fontinc": "Text Font",
    "fontdec": "Text Font Size",
    "indent": "Text Indent Increase",
    "outdent": "Text Indent Decrease",
    "heading1": "Text Header 1",
    "heading2": "Text Header 2",
    "heading3": "Text Header 3",
    "normaltext": "Text Paragraph",
    "bulletlist": "Text Bullet List",
    "todo": "Checkbox Checked",
    "togglelist": "Chevron Right",
    "table": "Table Simple",
    "wordcount": "Text Word Count",
    "alignleft": "Text Align Left",
    "aligncenter": "Text Align Center",
    "alignright": "Text Align Right",
    "alignjustify": "Text Align Justify",
    "comment": "Comment",
    "addcomment": "Chat Add",
    "submit": "Send",
    "preview": "Eye",
    "publish": "Rocket",
    # --- GitHub / GitLab specific ---
    "filefinder": "Document Search",
    "branch": "Branch",
    "blame": "History",
    "canonical": "Link",
    "webide": "Code",
    "createissue": "Add Circle",
    "openitem": "Open",
    "reviewer": "Person Add",
    "assignee": "Person",
    "label": "Tag",
    "milestone": "Flag",
    "nextfile": "Chevron Right",
    "prevfile": "Chevron Left",
    "nextthread": "Arrow Down",
    "prevthread": "Arrow Up",
    "filebrowser": "Folder Open",
    "diffcomments": "Comment Multiple",
    "annotations": "Note",
    # --- Atlassian: Jira and Bitbucket (replacing the hand-drawn jira_*/bb_* art) ---
    "watch": "Eye",
    "share": "Share",
    "actions": "More Horizontal",
    "assigntome": "Person Arrow Left",
    "nextitem": "Chevron Down",
    "previtem": "Chevron Up",
    "approve": "Checkmark Circle",
    "sidebyside": "Split Vertical",
    "prlist": "Branch Request",
    "previewcomment": "Glasses",
    "worddiff": "Highlight",
    "markread": "Document Checkmark",
    "changestatus": "Arrow Sync Circle",
    "help": "Question Circle",
    "fullscreen": "Full Screen Maximize",
    "filter": "Filter",
    "sortorder": "Arrow Sort",
    "childissue": "Add Square Multiple",
    "logwork": "Timer",
    "epicpanel": "Flash",
    "swimlanes": "Arrow Collapse All",
    "linkissue": "Link Add",
    # --- Confluence (General, Formatting and Navigation tabs of its "?" dialog) ---
    "notifications": "Alert",
    "gohome": "Home",
    "recent": "Clock",
    "starred": "Star",
    "spaceoverview": "Grid",
    "blogpost": "News",
    "quickinsert": "Slash Forward",
    "nextcomment": "Comment Arrow Right",
    "prevcomment": "Comment Arrow Left",
    "nextunread": "Mail Unread",
    "favorite": "Star Add",
    "presenter": "Presenter",
    "publishnote": "Note Edit",
    "heading4": "Text Header 4",
    "heading5": "Text Header 5",
    "heading6": "Text Header 6",
    "highlight": "Highlight",
    "insertimage": "Image Add",
    "markup": "Code Text",
    "macro": "Puzzle Piece",
    # --- Confluence whiteboards (Whiteboards tab) ---
    "sticky": "Note",
    "textbox": "Text Field",
    "ellipse": "Circle",
    "line": "Line",
    "handtool": "Hand Left",
    "select": "Cursor",
    "delete": "Delete",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoomreset": "Ratio One To One",
    "zoomfit": "Zoom Fit",
    "zoomselection": "Select Object",
    "lock": "Lock Closed",
    "hideui": "Eye Off",
    # --- Outlook on the web (replacing the reclaimed hand-drawn owa_* art) ---
    "mailnew": "Mail Add",
    "mailreply": "Arrow Reply",
    "mailreplyall": "Arrow Reply All",
    "mailforward": "Arrow Forward",
    "mailarchive": "Archive",
    "mailread": "Mail Read",
    "mailunread": "Mail Unread",
    "mailflag": "Flag",
    "deleteperm": "Delete Dismiss",
    "openwindow": "Window New",
    "mailview": "Mail Inbox",
    "calview": "Calendar",
    "copilot": "Sparkle",
    "peopleview": "People",
    "newcontact": "Person Add",
    "editcontact": "Person Edit",
    "newcontactlist": "People Add",
    "caltoday": "Calendar Today",
    "calday": "Calendar Day",
    "calworkweek": "Calendar Work Week",
    "calweek": "Calendar Week Numbers",
    "calmonth": "Calendar Month",
    "calprev": "Arrow Previous",
    "calnext": "Arrow Next",
}

# Google Sheets, Slides, Gmail and Calendar (gen_google_specs.py). `ms:` names are
# Material Symbols (Apache-2.0) where Fluent has no glyph.
GOOGLE = {
    # --- Google Calendar ---
    "calrefresh": "Arrow Clockwise",
    "calgoto": "Calendar Arrow Right",
    "calcustom": "ms:date_range",
    "calagenda": "ms:view_agenda",
    "calnew": "Calendar Add",
    "calinfo": "Info",
    # --- Google Sheets ---
    "fillrange": "ms:format_color_fill",
    "filldown": "ms:vertical_align_bottom",
    "fillright": "ms:keyboard_tab",
    "pastevalues": "ms:content_paste_go",
    "compact": "ms:toolbar",
    "toolfinder": "ms:manage_search",
    "rename": "Rename",
    "gotorange": "ms:jump_to_element",
    "bordertop": "ms:border_top",
    "borderright": "ms:border_right",
    "borderbottom": "ms:border_bottom",
    "borderleft": "ms:border_left",
    "bordernone": "ms:border_clear",
    "borderouter": "ms:border_outer",
    "inserttime": "ms:more_time",
    "insertdate": "Calendar Add",
    "insertdatetime": "Calendar Clock",
    "fmtdecimal": "ms:decimal_increase",
    "fmttime": "ms:schedule",
    "fmtdate": "ms:calendar_today",
    "fmtcurrency": "ms:attach_money",
    "fmtpercent": "ms:percent",
    "fmtexponent": "ms:superscript",
    "sheetstart": "ms:first_page",
    "sheetend": "ms:last_page",
    "activecell": "ms:center_focus_strong",
    "nextsheet": "Arrow Next",
    "prevsheet": "Arrow Previous",
    "sheetlist": "ms:list",
    "openlink": "Open",
    "explore": "ms:explore",
    "sidepanel": "Panel Right",
    "quicksum": "ms:functions",
    "history": "History",
    "sheetmenu": "ms:tab",
    "contextmenu": "ms:menu_open",
    "columnmenu": "ms:arrow_drop_down_circle",
    "insertmenu": "ms:add_box",
    "deletemenu": "ms:indeterminate_check_box",
    "showmenus": "ms:menu",
    "hiderow": "ms:visibility_off",
    "unhiderow": "ms:visibility",
    "hidecol": "Eye Off",
    "unhidecol": "Eye",
    "group": "Group",
    "ungroup": "Group Dismiss",
    "expand": "ms:unfold_more",
    "collapse": "ms:unfold_less_double",
    "formulas": "ms:function",
    "arrayformula": "ms:data_array",
    "collapsearray": "ms:compress",
    "screenreader": "ms:record_voice_over",
    "braille": "ms:blind",
    "readcolumn": "ms:view_column",
    "readrow": "ms:table_rows",
    # --- Google Slides ---
    "newslide": "Slide Add",
    "copyformat": "ms:format_paint",
    "pasteformat": "ms:format_ink_highlighter",
    "findnext": "ms:arrow_downward",
    "findprev": "ms:arrow_upward",
    "captions": "Closed Caption",
    "alttext": "ms:image",
    "filmstrip": "ms:view_carousel",
    "canvas": "ms:crop_landscape",
    "notes": "ms:speaker_notes",
    "htmlview": "ms:html",
    "animations": "ms:animation",
    "dictionary": "Book",
    "present": "Presenter",
    "presentstart": "ms:slideshow",
    "hidecomment": "Comment Off",
    "paradown": "ms:move_down",
    "paraup": "ms:move_up",
    "nextspell": "Text Grammar Arrow Right",
    "prevspell": "Text Grammar Arrow Left",
    "sendbackward": "ms:keyboard_arrow_down",
    "bringforward": "ms:keyboard_arrow_up",
    "rotateccw": "Arrow Rotate Counterclockwise",
    "rotatecw": "Arrow Rotate Clockwise",
    "widen": "Arrow Autofit Width",
    "taller": "Arrow Autofit Height",
    "shrink": "ms:close_fullscreen",
    "grow": "ms:open_in_full",
    "shorter": "Arrow Minimize Vertical",
    "speak": "ms:text_to_speech",
    "speakcursor": "ms:voice_selection",
    # --- Gmail ---
    "nextchat": "ms:arrow_forward",
    "prevchat": "ms:arrow_back",
    "addcc": "ms:person_add",
    "addbcc": "ms:visibility_off",
    "fromaddr": "ms:alternate_email",
    "spelling": "ms:spellcheck",
    "prevfont": "ms:keyboard_double_arrow_left",
    "nextfont": "ms:keyboard_double_arrow_right",
    # Gmail single keys
    "gm_select": "ms:check_box",
    "gm_star": "Star",
    "gm_archive": "Archive",
    "gm_mute": "ms:notifications_off",
    "gm_reply": "Arrow Reply",
    "gm_newwindow": "Window New",
    "gm_replyall": "Arrow Reply All",
    "gm_forward": "Arrow Forward",
    "gm_update": "Arrow Sync",
    "gm_archprev": "ms:keyboard_arrow_left",
    "gm_archnext": "ms:keyboard_arrow_right",
    "gm_read": "ms:drafts",
    "gm_unread": "ms:mark_email_unread",
    "gm_important": "ms:label_important",
    "gm_notimportant": "ms:label_off",
    "gm_snooze": "ms:snooze",
    "gm_expand": "ms:unfold_more",
    "gm_addtask": "ms:add_task",
    "gm_list": "ms:view_list",
    "gm_newer": "ms:keyboard_arrow_up",
    "gm_older": "ms:keyboard_arrow_down",
    "gm_prevmsg": "ms:arrow_upward",
    "gm_nextmsg": "ms:arrow_downward",
    "gm_more": "ms:more_vert",
    "gm_move": "ms:drive_file_move",
    "gm_label": "ms:label",
}
# draw.io, Excalidraw, Linear and Overleaf (diagram, whiteboard, project and
# LaTeX web apps). Prefixed by app where the same action has another meaning
# in an existing set.
DIAGRAM_ETC = {
    # --- draw.io ---
    "dio_layers": "Layer",
    "dio_outline": "ms:map",
    "dio_format": "Panel Right",
    "dio_shapes": "Shapes",
    "dio_tags": "Tag",
    "dio_geometry": "Ruler",
    "dio_metadata": "ms:dataset",
    "dio_grid": "Grid",
    "dio_arrows": "ms:open_with",
    "dio_points": "ms:add_circle",
    "dio_entergroup": "ms:login",
    "dio_exitgroup": "ms:logout",
    "dio_fitwindow": "ms:fit_screen",
    "dio_fittwo": "ms:auto_stories",
    "dio_customzoom": "ms:zoom_in_map",
    "dio_editstyle": "ms:style",
    "dio_setstyle": "ms:verified",
    "dio_tooltip": "ms:tooltip",
    "dio_note": "Note",
    "dio_editnote": "Note Edit",
    "dio_saveas": "ms:save_as",
    "dio_copysize": "ms:straighten",
    "dio_pastesize": "ms:aspect_ratio",
    "dio_copydata": "ms:data_object",
    "dio_pastedata": "ms:content_paste_go",
    "dio_waypoints": "ms:timeline",
    "dio_autosize": "ms:fit_width",
    "dio_prevpage": "ms:navigate_before",
    "dio_nextpage": "ms:navigate_next",
    "dio_selvertices": "ms:select_all",
    "dio_seledges": "ms:polyline",
    "dio_selnone": "ms:deselect",
    "dio_rect": "ms:rectangle",
    "dio_freehand": "ms:gesture",
    "dio_copyimage": "Image Copy",
    "dio_copystyle": "ms:format_paint",
    "dio_pastestyle": "Clipboard Brush",
    "dio_home": "Home",
    "dio_resetview": "ms:recenter",
    # --- Excalidraw ---
    "exc_hand": "Hand Left",
    "exc_diamond": "Diamond",
    "exc_arrow": "Arrow Up Right",
    "exc_pen": "Pen",
    "exc_image": "Image",
    "exc_eraser": "Eraser",
    "exc_frame": "ms:frame_source",
    "exc_laser": "ms:stylus_laser_pointer",
    "exc_fill": "ms:format_color_fill",
    "exc_eyedrop": "ms:colorize",
    "exc_toollock": "ms:keep",
    "exc_wrap": "ms:wrap_text",
    "exc_flipx": "ms:flip",
    "exc_flipy": "ms:swap_vert",
    "exc_stroke": "ms:border_color",
    "exc_background": "ms:imagesearch_roller",
    "exc_fonts": "Text Font",
    "exc_zen": "ms:self_improvement",
    "exc_snap": "ms:grid_goldenratio",
    "exc_viewmode": "Eye",
    "exc_theme": "ms:contrast",
    "exc_stats": "ms:analytics",
    "exc_copypng": "Image Copy",
    "exc_alignt": "ms:vertical_align_top",
    "exc_alignb": "ms:vertical_align_bottom",
    "exc_alignl": "ms:align_horizontal_left",
    "exc_alignr": "ms:align_horizontal_right",
    "exc_clear": "ms:delete_sweep",
    "exc_textsize_dn": "ms:text_decrease",
    "exc_textsize_up": "ms:text_increase",
    # --- Linear ---
    "lin_layout": "ms:view_kanban",
    "lin_agent": "Sparkle",
    "lin_insights": "ms:insights",
    "lin_attach": "Attach",
    "lin_branch": "Branch",
    "lin_createmore": "ms:repeat",
    "lin_template": "ms:note_stack",
    "lin_inline": "Comment Add",
    "lin_moveup": "Arrow Up",
    "lin_movedown": "Arrow Down",
    "lin_movetop": "ms:vertical_align_top",
    "lin_movebottom": "ms:vertical_align_bottom",
    "lin_copymd": "ms:markdown_copy",
    "lin_upload": "ms:upload_file",
    "lin_new": "ms:add_box",
    "lin_assign": "ms:person_add",
    "lin_assignme": "ms:person_pin",
    "lin_select": "ms:check_box",
    "lin_selectmore": "ms:library_add_check",
    "lin_status": "ms:radio_button_partial",
    "lin_subscribe": "ms:notifications_active",
    "lin_filter": "Filter",
    "lin_next": "ms:keyboard_arrow_down",
    "lin_prev": "ms:keyboard_arrow_up",
    "lin_snooze": "ms:snooze",
    "lin_collapse": "ms:unfold_less",
    "lin_milestone": "ms:flag",
    "lin_project": "ms:deployed_code",
    # --- Overleaf ---
    "ol_compile": "ms:play_arrow",
    "ol_gotoline": "ms:format_list_numbered_rtl",
    "ol_comment": "ms:code_off",
    "ol_deleteline": "ms:playlist_remove",
    "ol_upper": "Text Case Uppercase",
    "ol_lower": "Text Case Lowercase",
    "ol_autocomplete": "ms:auto_fix_normal",
    "ol_review": "ms:rate_review",
    "ol_track": "ms:track_changes",
    "ol_dupsel": "ms:content_copy",
    "ol_first": "ms:vertical_align_top",
    "ol_last": "ms:vertical_align_bottom",
}
# Their ESC marks: each app's own logo from Simple Icons (CC0 artwork).
DIAGRAM_ETC_BRAND = {"drawio.png": "diagramsdotnet", "excalidraw.png": "excalidraw",
                     "linear.png": "linear", "overleaf.png": "overleaf"}

# narrower.png is shorter.png turned 90 degrees: Fluent has a vertical
# "Arrow Minimize" but no horizontal one.
ROTATED = {"narrower.png": ("shorter.png", 90)}


# GitHub and GitLab publish plain monochrome marks that read cleanly as a 1-bit
# silhouette, and Simple Icons redistributes that artwork CC0 — so these get the
# REAL logo (nominative use; see brand_marks).
BRAND = {"gh.png": "github", "gl.png": "gitlab",
         "gmail.png": "gmail", "gcal.png": "googlecalendar"}
# Google Docs is a document, and Google's logo is not ours to ship — a labelled
# page frame says what it is without borrowing the mark.
DOC = {"gd.png": ("googledocs", "DOCS"),
       "gs.png": ("calc", "SHEETS"), "gsl.png": ("impress", "SLIDES")}
# Notion: a framed serif N with a 1-bit extruded shade — its brand letter IS a
# serif, and the depth is what separates it from the other framed marks.
SHADED = {"nt.png": "N"}
# Confluence: Atlassian's mark is a trademark, but its construction — a pair of
# mirrored, rotated hooks — is a shape we can draw ourselves (see geo_marks).
GEO = {"cf.png": geo_marks.ensure_confluence}


# Fluent ships NO ordered-list glyph (every "Text Number List *" name 404s), and
# its nearest match, "Text Number Format", draws "ABC 123" -- that reads as
# alphanumeric formatting, not a numbered list. This is exactly the gap Material
# Symbols (Apache-2.0, GPL-3.0-compatible) is kept around to fill.
# Fluent has no whitespace glyph either ("Text Whitespace" 404s); Bitbucket's
# "Ignore whitespace" takes Material's space bar.
# Fluent has no z-order pair either ("Bring To Front", "Arrange Forward" 404);
# Confluence whiteboards' bring to front / send to back take Material's.
MATERIAL = {"numberlist": "format_list_numbered", "whitespace": "space_bar",
            "bringfront": "flip_to_front", "sendback": "flip_to_back"}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.fluent(GOOGLE, out)
    n += icon_fetch.fluent(DIAGRAM_ETC, out)
    for fname, (src, angle) in ROTATED.items():
        Image.open(out / src).rotate(angle).save(out / fname)
        print(f"  {fname}  <- {src} turned {angle} degrees")
    n += len(ROTATED)
    for stem, name in MATERIAL.items():
        ms.render(name, out / f"{stem}.png", weight=300)
        print(f"  {stem}.png  <- material-symbols/{name}")
    n += len(MATERIAL)
    for fname, slug in {**BRAND, **DIAGRAM_ETC_BRAND}.items():
        brand_marks.ensure(out / fname, slug)
    for fname, (app, label) in DOC.items():
        dest = out / fname
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
        else:
            if app not in doc_mark.MOTIF:
                doc_mark.MOTIF[app] = doc_mark.MOTIF["writer"]   # a text document
            r = doc_mark.build(app, [label], page_h=39.6, stretch=1.0, save=dest)
            assert r and r[1] == 0 and r[2] == 0, f"{app}: touches the page outline: {r}"
            print(f"  {dest.name}  <- fluent Document + '{r[0]}'")
    for fname, letters in SHADED.items():
        rect_mark.ensure(out / fname, letters, serif=True, shade=2, shade_dir="tl")
    for fname, draw in GEO.items():
        draw(out / fname)
    print(f"Wrote {n} icons (+ {len(BRAND)+len(DIAGRAM_ETC_BRAND)+len(DOC)+len(SHADED)+len(GEO)} program marks) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
