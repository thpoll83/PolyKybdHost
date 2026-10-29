#!/usr/bin/env python3
"""Fetch + render the Adobe InDesign shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The ESC mark is a generic
"Id" rectangle (`../rect_mark.py`), not Adobe's logo, sized with the other
Adobe marks.

    pip install cairosvg
    python polyhost/res/overlay_sources/indesign/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, rect_mark  # noqa: E402

FLUENT = {
    # --- tools ---
    "selection": "Cursor",
    "directsel": "ms:arrow_selector_tool",
    "pen": "Pen",
    "type": "Text T",
    "pencil": "ms:stylus",
    "line": "Line",
    "rectframe": "ms:image",
    "rectangle": "Rectangle Landscape",
    "ellipse": "Circle",
    "rotate": "Arrow Rotate Clockwise",
    "scale": "ms:open_in_full",
    "freetransform": "Resize",
    "eyedropper": "Eyedropper",
    "gradient": "ms:gradient",
    "scissors": "Cut",
    "hand": "Hand Right",
    "zoom": "Zoom In",
    "preview": "Eye",
    "fillstroke": "ms:format_color_fill",
    "gap": "ms:space_bar",
    "page": "Document",
    "typepath": "ms:text_rotation_angleup",
    "swapfill": "Arrow Swap",
    "convertpoint": "ms:conversion_path",
    "presentation": "ms:co_present",
    # --- Ctrl ---
    "new": "Document Add",
    "open": "Folder Open",
    "save": "Save",
    "close": "Document Dismiss",
    "print": "Print",
    "place": "Image Add",
    "export": "Arrow Export LTR",
    "settings": "Settings",
    "findchange": "Search",
    "storyeditor": "ms:article",
    "spelling": "Text Proofing Tools",
    "group": "Group",
    "lock": "Lock Closed",
    "gotopage": "Document Arrow Right",
    "textframe": "ms:text_fields",
    "character": "Text Font",
    "rulers": "Ruler",
    "guides": "ms:grid_guides",
    "docgrid": "Grid",
    "smartguides": "ms:auto_awesome_motion",
    "fitpage": "Document Fit",
    "actualsize": "Ratio One To One",
    "forward": "Arrow Up",
    "backward": "Arrow Down",
    "hide": "Eye Off",
    "compound": "ms:join",
    "quickapply": "Flash",
    # --- Ctrl+Shift ---
    "saveas": "Save Edit",
    "deselect": "Select All Off",
    "pasteplain": "ms:content_paste_go",
    "ungroup": "Group Dismiss",
    "front": "ms:flip_to_front",
    "back": "ms:flip_to_back",
    "outlines": "ms:format_shapes",
    "addpage": "Document Add",
    "links": "Link",
    "tabs": "ms:keyboard_tab",
    "allcaps": "ms:match_case",
    "alignleft": "Text Align Left",
    "aligncenter": "Text Align Center",
    "alignright": "Text Align Right",
    "justify": "Text Align Justify",
    "centercontent": "ms:center_focus_strong",
    "move": "Arrow Move",
    "superscript": "Text Superscript",
    "snapguides": "ms:straighten",
    # --- Ctrl+Alt ---
    "docsetup": "Document Settings",
    "savecopy": "Save Copy",
    "pasteinto": "ms:input",
    "textwrap": "Text Wrap",
    "paragraph": "Text Paragraph",
    "unlockall": "Lock Open",
    "fitcontent": "ms:fit_screen",
    "fitframe": "ms:crop_free",
    "steprepeat": "ms:repeat",
    "hiddenchars": "ms:format_paragraph",
    "threads": "ms:timeline",
    "dropshadow": "ms:shadow",
    "fitspread": "ms:auto_stories",
    "newdefault": "Document One Page Add",
    "findnext": "Search Info",
    "lockguides": "ms:lock_clock",
    # --- Ctrl+Alt+Shift ---
    "package": "Box",
    "duplicate": "Copy",
    "pasteinplace": "ms:content_paste",
    "preflight": "Checkmark Circle",
    "fitprop": "ms:aspect_ratio",
    "fillprop": "ms:photo_size_select_large",
    "overprint": "ms:layers",
    # --- panels ---
    "swatches": "ms:style",
    "color": "Color",
    "layers": "Layer",
    "info": "Info",
    "align": "ms:align_horizontal_center",
    "stroke": "ms:line_weight",
    "parastyles": "ms:format_list_bulleted",
    "pages": "Document Multiple",
    "charstyles": "ms:format_size",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    rect_mark.ensure(out / "indesign.png", "Id",
                     size=rect_mark.shared_size(["Ps", "Ai", "Pr", "Ae"]))
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
