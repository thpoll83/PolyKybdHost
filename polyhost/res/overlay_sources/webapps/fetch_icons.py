#!/usr/bin/env python3
"""Fetch + render icons for the browser-hosted app overlays.

One icon folder serves the browser sets — `github.yaml`, `gitlab.yaml`,
`confluence.yaml`, `confluence_whiteboard.yaml`, `googledocs.yaml`, `notion.yaml`, `jira.yaml`, `web_outlook.yaml` and
`bitbucket.yaml`. They are grouped
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

# GitHub and GitLab publish plain monochrome marks that read cleanly as a 1-bit
# silhouette, and Simple Icons redistributes that artwork CC0 — so these get the
# REAL logo (nominative use; see brand_marks).
BRAND = {"gh.png": "github", "gl.png": "gitlab"}
# Google Docs is a document, and Google's logo is not ours to ship — a labelled
# page frame says what it is without borrowing the mark.
DOC = {"gd.png": ("googledocs", "DOCS")}
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
    for stem, name in MATERIAL.items():
        ms.render(name, out / f"{stem}.png", weight=300)
        print(f"  {stem}.png  <- material-symbols/{name}")
    n += len(MATERIAL)
    for fname, slug in BRAND.items():
        brand_marks.ensure(out / fname, slug)
    for fname, (app, label) in DOC.items():
        dest = out / fname
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
        else:
            doc_mark.MOTIF[app] = doc_mark.MOTIF["writer"]   # a text document
            r = doc_mark.build(app, [label], page_h=39.6, stretch=1.0, save=dest)
            assert r and r[1] == 0 and r[2] == 0, f"{app}: touches the page outline: {r}"
            print(f"  {dest.name}  <- fluent Document + '{r[0]}'")
    for fname, letters in SHADED.items():
        rect_mark.ensure(out / fname, letters, serif=True, shade=2, shade_dir="tl")
    for fname, draw in GEO.items():
        draw(out / fname)
    print(f"Wrote {n} icons (+ {len(BRAND)+len(DOC)+len(SHADED)+len(GEO)} program marks) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
