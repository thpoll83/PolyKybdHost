#!/usr/bin/env python3
"""Fetch + render the Adobe Lightroom Classic shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). Star ratings and colour
labels are numbered glyphs from `../number_badge.py`. The ESC mark is a
generic "Lr" rectangle (`../rect_mark.py`), not Adobe's logo, sized with the
other Adobe marks.

    pip install cairosvg
    python polyhost/res/overlay_sources/lightroom/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, number_badge, rect_mark  # noqa: E402

FLUENT = {
    "grid": "Grid",
    "loupe": "Image",
    "compare": "ms:compare",
    "survey": "ms:view_module",
    "develop": "ms:tune",
    "lightsout": "Lightbulb",
    "screenmode": "Full Screen Maximize",
    "info": "Info",
    "toolbar": "ms:toolbar",
    "crop": "Crop",
    "whitebalance": "Eyedropper",
    "brush": "Paint Brush",
    "lineargradient": "ms:gradient",
    "healing": "ms:healing",
    "pick": "Flag",
    "reject": "Flag Off",
    "unflag": "ms:flag_circle",
    "quickcollection": "ms:bookmark_add",
    "grayscale": "ms:filter_b_and_w",
    "clipping": "Warning",
    "zoomview": "ms:zoom_in_map",
    "beforeafter": "Split Vertical",
    "beforeaftertb": "Split Horizontal",
    "splitview": "ms:vertical_split",
    "norating": "Star Off",
    "_star": "Star",
    "_tag": "Tag",
    "sidepanels": "ms:side_navigation",
    "rename": "Rename",
    "filmstrip": "ms:view_carousel",
    "leftpanels": "Panel Left",
    "rightpanels": "Panel Right",
    "masking": "ms:ink_selection",
    "radialgradient": "ms:blur_circular",
    "reference": "ms:compare_arrows",
    "hdrview": "ms:hdr_on",
    "deselect": "Select All Off",
    "find": "Search",
    "stack": "Stack",
    "filters": "Filter",
    "keywords": "Tag Add",
    "viewoptions": "ms:view_list",
    "showquick": "ms:bookmarks",
    "photoshop": "ms:open_in_new",
    "showfolder": "Folder Open",
    "autotone": "ms:auto_fix_high",
    "savemeta": "Save",
    "print": "Print",
    "settings": "Settings",
    "rotateright": "Arrow Rotate Clockwise",
    "rotateleft": "Arrow Rotate Counterclockwise",
    "virtualcopy": "Copy Add",
    "slideshow": "ms:slideshow",
    "shortcuts": "Keyboard",
    "prevphoto": "Arrow Previous",
    "nextphoto": "Arrow Next",
    "catalog": "ms:library_books",
    "hdrmerge": "ms:hdr_plus",
    "panorama": "ms:panorama",
    "import": "Arrow Download",
    "export": "Arrow Upload",
    "copysettings": "ms:content_copy",
    "pastesettings": "ms:content_paste",
    "resetall": "Arrow Reset",
    "sync": "Arrow Sync",
    "autowb": "ms:wb_auto",
    "lightsdim": "ms:brightness_medium",
    "unstack": "ms:layers_clear",
    "editkeywords": "Tag Edit",
    "library": "Library",
    "map": "Map",
    "book": "Book",
    "web": "Globe",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "prevmodule": "Arrow Up",
    "pasteprev": "ms:content_paste_go",
    "othereditor": "Window New",
    "normalscreen": "ms:fullscreen_exit",
    "savequick": "ms:bookmark_added",
    "zoom100": "Ratio One To One",
    "catalogsettings": "ms:settings_applications",
    "enhance": "ms:auto_awesome",
    "exportprev": "ms:upload",
}


# --- One icon per action (maintainer, 2026-11-15) ----------------------------
# Two keys of this app share an image only when they do the same thing. The
# glyphs below give the other keys their own image. The older files stay, because
# other sets may copy them (icon_fetch.borrow).
ACTION_FLUENT = {
    "impromptu": "Slide Play",
    "_modules": "ms:grid_view",
}
# file -> (base, badge): the base reduced to the upper left, the badge in the
# lower right (dcc_glyphs.with_badge).
ACTION_BADGED = {
    "printmodule.png": ("print.png", "_modules.png"),
}
# file -> (base, forward): the base over a heavy arrow (dcc_glyphs.with_arrow).
ACTION_ARROWS = {
    "picknext.png": ("pick.png", True),
    "rejectnext.png": ("reject.png", True),
    "unflagnext.png": ("unflag.png", True),
}


def action_icons(out: Path) -> None:
    """Draw the ACTION_* icons; a committed composite is left as it is."""
    from polyhost.res.overlay_sources import dcc_glyphs, icon_fetch as fetch
    if ACTION_FLUENT:
        fetch.fluent(ACTION_FLUENT, out)
    for name, (base, badge) in ACTION_BADGED.items():
        dcc_glyphs.guarded(out / name, lambda p, b=base, g=badge: dcc_glyphs.with_badge(
            out / b, out / g, p), f"{base} + {badge}")
    for name, (base, fwd) in ACTION_ARROWS.items():
        dcc_glyphs.guarded(out / name, lambda p, b=base, f=fwd: dcc_glyphs.with_arrow(
            out / b, p, f), f"{base} + arrow")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    number_badge.numbered(out / "_star.png", "12345", out, "star", size=0.36, centre=(0.50, 0.56))
    number_badge.numbered(out / "_tag.png", "RYGB", out, "label", size=0.36, centre=(0.50, 0.53))
    rect_mark.ensure(out / "lightroom.png", "Lr",
                     size=rect_mark.shared_size(["Ps", "Ai", "Pr", "Ae"]))
    action_icons(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
