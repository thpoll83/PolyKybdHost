#!/usr/bin/env python3
"""Fetch + render the PhotoCraft shortcut icons (reproducible source step).

PhotoCraft (github.com/storytold/photocraft, MIT OR Apache-2.0) is the ArtCraft
suite's open-source Photoshop work-alike, and it deliberately keeps Photoshop's
default keymap. So wherever an action matches the Photoshop overlay, the glyph is
the SAME one: the drawn Photoshop tool glyphs are copied byte-identically with
`icon_fetch.borrow` (one drawing per action, stored once in the icon library),
and the Fluent glyphs below use the same Fluent folder names as
`photoshop/fetch_icons.py`, which renders byte-identical PNGs.

Everything else is Microsoft Fluent UI System Icons (MIT) via `icon_fetch`, with
Material Symbols (Apache-2.0, `ms:`) for the gaps Fluent has (layer stacking,
blend steps, wide-angle, vignette/mask, ...).

The ESC **program mark is PhotoCraft's OWN icon** (the kitsune), taken from the
app's own `assets/app-icon/photocraft.ico`. Its LICENSE.txt states the artwork is
the project owner's original drawing, licensed like the rest of PhotoCraft (MIT
OR Apache-2.0), both GPL-3.0-compatible. Rendered from the **64 px frame** with
`program_icon_mode: luma`, threshold 140 (see bindings.yaml for the sweep). The
mark is guarded by `program_marks.own_icon`, so a re-run never clobbers it.

    PYTHONPATH=. python polyhost/res/overlay_sources/photocraft/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import number_badge  # noqa: E402
import program_marks  # noqa: E402

from PIL import Image  # noqa: E402

# Pinned to the commit the shortcuts were read from (see SOURCES.md).
PC_COMMIT = "99e1138877e6aa7e856c6883b415e708d042fc59"
PC_ICO = (f"https://raw.githubusercontent.com/storytold/photocraft/{PC_COMMIT}"
          "/assets/app-icon/photocraft.ico")

FLUENT = {
    # --- shared with photoshop/ (same Fluent folder -> same bytes) ---
    "new": "Document Add",
    "open": "Folder Open",
    "save": "Save",
    "saveas": "Save Edit",
    "close": "Document Dismiss",
    "print": "Print",
    "copy": "Copy",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "selectall": "Select All On",
    "deselect": "Select All Off",
    "freetransform": "Resize",
    "duplayer": "Layer",
    "newlayer": "Add Square",
    "mergedown": "Layer Diagonal",
    "group": "Group",
    "levels": "Data Histogram",
    "curves": "Data Line",
    "huesat": "Color",
    "colorbalance": "Color Fill",
    "invert": "Color Background",
    "desaturate": "Color Line",
    "rulers": "Ruler",
    "extras": "Eye Off",
    "fitscreen": "Full Screen Maximize",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "invertsel": "Arrow Swap",
    "copymerged": "Copy Select",
    "move": "Arrow Move",
    "crop": "Crop",
    "brush": "Paint Brush",
    "eraser": "Eraser",
    "type": "Text T",
    "eyedropper": "Eyedropper",
    "zoom": "Zoom In",
    "hand": "Hand Right",
    "pen": "Pen",
    "shape": "Shapes",
    "historybrush": "History",
    "fill": "Paint Bucket",
    "screenmode": "Full Screen Maximize",
    "stepback": "History",
    "zoom1to1": "Ratio One To One",
    "feather": "Blur",
    # --- file ---
    "exit": "Sign Out",
    "closeall": "Dismiss Square Multiple",
    "closeothers": "Tab Desktop Multiple",
    "saveacopy": "Save Copy",
    "revert": "Arrow Reset",
    "exportas": "Share",
    "saveforweb": "Globe",
    "openas": "Open",
    "fileinfo": "Document Bullet List",
    "printone": "Print Add",
    # --- edit ---
    "search": "Search",
    "pasteinplace": "Clipboard Arrow Right",
    "pasteinto": "Clipboard Image",
    "transformagain": "Arrow Repeat All",
    "transformagaincopy": "Square Multiple",
    "freetransformcopy": "Copy Arrow Right",
    "contentawarescale": "Resize Image",
    "prefs": "Settings",
    "keyboardshortcuts": "Keyboard",
    "menus": "Navigation",
    # --- image / layer / select ---
    "ungroup": "Group Dismiss",
    "mergevisible": "Merge",
    "alllayers": "Stack",
    "findlayers": "Search Square",
    "reselect": "Arrow Counterclockwise",
    "selectandmask": "Select Object",
    "quickexport": "Image Arrow Forward",
    "layerexport": "Arrow Export",
    "composite": "Image",
    "channelbase": "Square",
    "locktransp": "Lock Multiple",
    "clear": "Delete",
    "clipmask": "Arrow Turn Down Right",
    # --- filter / view / window ---
    "camraw": "Camera",
    "flowfill": "Drop",
    "proof": "Eye",
    "gamut": "Warning",
    "grid": "Grid",
    "snap": "Arrow Fit",
    "lockguides": "Lock Closed",
    "targetpath": "Bezier Curve Square",
    "brushsettings": "Paint Brush Sparkle",
    "infopanel": "Info",
    "actions": "Play Circle",
    "blendnext": "Arrow Next",
    "blendprev": "Arrow Previous",
    "rotateview": "Arrow Rotate Clockwise",
    "frame": "Frame",
    # --- Material Symbols (Apache-2.0) for Fluent's gaps ---
    "bringforward": "ms:arrow_upward",
    "sendbackward": "ms:arrow_downward",
    "bringfront": "ms:flip_to_front",
    "sendback": "ms:flip_to_back",
    "layerabove": "ms:keyboard_arrow_up",
    "layerbelow": "ms:keyboard_arrow_down",
    "layertop": "ms:vertical_align_top",
    "layerbottom": "ms:vertical_align_bottom",
    "addabove": "ms:keyboard_double_arrow_up",
    "addbelow": "ms:keyboard_double_arrow_down",
    "hidelayers": "ms:layers_clear",
    "layerspanel": "ms:layers",
    "colorpanel": "ms:palette",
    "colorsettings": "ms:display_settings",
    "blackwhite": "ms:filter_b_and_w",
    "autotone": "ms:auto_fix_high",
    "autocontrast": "ms:contrast",
    "autocolor": "ms:invert_colors",
    "imagesize": "ms:photo_size_select_large",
    "canvassize": "ms:aspect_ratio",
    "fade": "ms:gradient",
    "lastfilter": "ms:filter",
    "wideangle": "ms:panorama_wide_angle",
    "lenscorr": "ms:camera",
    "liquify": "ms:waves",
    "vanishing": "ms:view_in_ar",
    "guides": "ms:grid_guides",
    "stampvisible": "ms:approval",
    "stampdown": "ms:move_down",
    "luminosity": "ms:brightness_6",
    "layermask": "ms:vignette",
    "opacity": "ms:opacity",
    "typesizeup": "ms:text_increase",
    "typesizedown": "ms:text_decrease",
    # --- Enter / Backspace / Tab / Space chords ---
    "panelsall": "Panel Left Contract",
    "panelsdock": "Panel Right Contract",
    "nextdoc": "Document Arrow Right",
    "prevdoc": "Document Arrow Left",
    "pathtosel": "ms:select",
    "fillhistory": "ms:settings_backup_restore",
    "lockbadge": "Lock Closed",
}

# Photoshop's drawn tool glyphs, copied byte-identically (same action, same art).
BORROWED = {f"{n}.png": "photoshop" for n in (
    "marquee", "lasso", "magicwand", "clonestamp", "healing", "dodgeburn",
    "pathselect", "defaultcolors", "quickmask", "gradient", "brushdec",
    "brushinc", "hardnessdec", "hardnessinc", "swapcolors", "fillfg", "fillbg")}


def _preserve(fill: Path, lock: Path, path: Path) -> None:
    """Fill ... Preserve Transparency: the plain fill square shrunk to the top-left
    with a small lock bottom-right. Both inputs are opaque-on-transparent, and the
    binding renders `mode: alpha`, so only the alpha channel matters. Guarded."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    u = 96
    out = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    f = Image.open(fill).convert("RGBA").resize((70, 70), Image.LANCZOS)
    out.alpha_composite(f, (0, 0))
    lk = Image.open(lock).convert("RGBA").resize((46, 46), Image.LANCZOS)
    white = Image.new("RGBA", lk.size, (255, 255, 255, 255))
    white.putalpha(lk.split()[3])
    out.alpha_composite(white, (u - 46, u - 46))
    out.save(path)
    print(f"  {path.name}  <- composite ({fill.stem} + lock)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    # Cmd+3..9 "Target channel N": the digit is the information (number_badge).
    number_badge.numbered(out / "channelbase.png", "3456789", out, "channel")
    icon_fetch.borrow(BORROWED, out)
    _preserve(out / "fillfg.png", out / "lockbadge.png", out / "fillfgpreserve.png")
    _preserve(out / "fillbg.png", out / "lockbadge.png", out / "fillbgpreserve.png")
    program_marks.own_icon(out / "photocraft.png", PC_ICO, frame=64,
                           credit="storytold/photocraft assets/app-icon/photocraft.ico (MIT OR Apache-2.0)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
