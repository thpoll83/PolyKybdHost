#!/usr/bin/env python3
"""Fetch + render the Affinity shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The ESC marks are generic
letter rectangles (`../rect_mark.py`): Simple Icons no longer carries the
Affinity marks, and Serif's logos are not free to use.

    pip install cairosvg
    python polyhost/res/overlay_sources/affinity/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, rect_mark  # noqa: E402

FLUENT = {
    "new": "Document Add",
    "newclip": "Clipboard Paste",
    "open": "Folder Open",
    "closeall": "Dismiss Square Multiple",
    "saveas": "Save Edit",
    "export": "Arrow Export LTR",
    "docsetup": "Document Settings",
    "resizedoc": "ms:photo_size_select_large",
    "resizecanvas": "ms:aspect_ratio",
    "settings": "Settings",
    "deselect": "Select All Off",
    "pastestyle": "ms:format_paint",
    "pastefx": "ms:auto_fix_normal",
    "pasteinside": "ms:input",
    "pasteplain": "ms:content_paste_go",
    "copymerged": "Copy Select",
    "invertsel": "Arrow Swap",
    "selectlayers": "ms:select_all",
    "selectnext": "Arrow Next",
    "selectprev": "Arrow Previous",
    "selectparent": "Arrow Up",
    "group": "Group",
    "ungroup": "Group Dismiss",
    "duplicate": "Copy",
    "front": "ms:flip_to_front",
    "forward": "ms:arrow_upward",
    "back": "ms:flip_to_back",
    "backward": "ms:arrow_downward",
    "moveinside": "ms:login",
    "moveoutside": "ms:logout",
    "showall": "Eye",
    "lock": "Lock Closed",
    "unlock": "Lock Open",
    "unlockall": "ms:lock_open_right",
    "newlayer": "ms:add_box",
    "rename": "Rename",
    "curves": "ms:conversion_path",
    "symbol": "ms:interests",
    "mergedown": "ms:vertical_align_bottom",
    "mergesel": "ms:merge",
    "mergevis": "ms:layers",
    "adjcurves": "ms:show_chart",
    "blackwhite": "ms:filter_b_and_w",
    "levels": "Data Histogram",
    "hsl": "Color",
    "invert": "ms:invert_colors",
    "repeatfilter": "ms:repeat",
    "fade": "ms:gradient",
    "growshrink": "ms:open_in_full",
    "refine": "ms:blur_on",
    "fill": "ms:format_color_fill",
    "feather": "ms:blur_linear",
    "character": "Text Font",
    "typography": "ms:text_format",
    "spelling": "Text Proofing Tools",
    "superscript": "Text Superscript",
    "subscript": "Text Subscript",
    "bigger": "Text Font Size",
    "smaller": "ms:text_decrease",
    "alignleft": "Text Align Left",
    "aligncenter": "Text Align Center",
    "alignright": "Text Align Right",
    "place": "Image Add",
    "addpage": "Document One Page Add",
    "prevpage": "Arrow Previous",
    "nextpage": "Arrow Next",
    "detached": "ms:open_in_new",
    "find": "Search",
    "previewmode": "ms:preview",
    "indenthere": "ms:format_indent_increase",
    "zoomfit": "Full Screen Maximize",
    "zoom100": "Ratio One To One",
    "zoom200": "ms:looks_two",
    "pixelsize": "ms:image_aspect_ratio",
    "rulers": "Ruler",
    "guides": "ms:grid_guides",
    "grid": "Grid",
    "studio": "Panel Right",
    "toolbar": "Panel Left",
    "resetrotation": "Arrow Reset",
    "pixelview": "ms:grid_4x4",
    "wireframe": "ms:deployed_code",
}

# Tool icons with no sibling copy (gen_specs.py TOOLS).
TOOL_FETCH = {
    "contour": "ms:trip_origin",
    "corner": "ms:rounded_corner",
    "transparency": "ms:opacity",
    "shapebuilder": "ms:join_full",
    "selbrush": "ms:ink_selection",
    "colorreplace": "ms:colorize",
    "snapping": "ms:grid_goldenratio",
    "smudgetool": "ms:gesture",
}

# Tool icons copied byte-identical from the sibling sets (icon_fetch.borrow).
TOOL_BORROW = {
    "move.png": "photoshop", "freetransform.png": "photoshop", "crop.png": "photoshop",
    "marquee.png": "photoshop", "lasso.png": "photoshop", "brush.png": "photoshop",
    "eraser.png": "photoshop", "dodgeburn.png": "photoshop", "clonestamp.png": "photoshop",
    "healing.png": "photoshop", "quickmask.png": "photoshop", "defaultcolors.png": "photoshop",
    "directselect.png": "illustrator", "pen.png": "illustrator", "pencil.png": "illustrator",
    "width.png": "illustrator", "scissors.png": "illustrator", "paintbrush.png": "illustrator",
    "gradient.png": "illustrator", "rectangle.png": "illustrator", "type.png": "illustrator",
    "eyedropper.png": "illustrator", "hand.png": "illustrator", "zoom.png": "illustrator",
    "swap.png": "illustrator",
    "filltool.png": "krita", "rectframe.png": "indesign",
}

MARKS = {"designer.png": "Ds", "photo.png": "Ph", "publisher.png": "Pb", "affinity.png": "Af"}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.fluent(TOOL_FETCH, out)
    icon_fetch.borrow(TOOL_BORROW, out)
    size = rect_mark.shared_size(list(MARKS.values()))
    for fname, letters in MARKS.items():
        rect_mark.ensure(out / fname, letters, size=size)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
