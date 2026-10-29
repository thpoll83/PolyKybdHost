#!/usr/bin/env python3
"""Fetch + render the DesignCraft shortcut icons (reproducible).

DesignCraft (github.com/storytold/designcraft, MIT OR Apache-2.0) is an
InDesign-like page-layout app from the ArtCraft "Crafting Apps" suite.

Sources, in order of preference:
  * glyphs the Illustrator overlay already ships for the same action, copied
    byte-identically (`icon_fetch.borrow`) so both apps render the same cell;
  * Microsoft Fluent UI System Icons (MIT), the house style;
  * Material Symbols (Apache-2.0, `ms:` specs) for the few Fluent gaps;
  * four drawn white-on-transparent glyphs (add/delete anchor, rectangle frame,
    shear), consumed with `mode: alpha`.

The program mark (ESC) is DesignCraft's OWN app icon (the calico cat), frame
64 of assets/app-icon/designcraft.ico, MIT OR Apache-2.0
(assets/app-icon/LICENSE.txt). Drawn assets and the mark are guarded: a
committed file is left as-is.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/designcraft/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))   # repo root, for `polyhost.…`
sys.path.insert(0, str(HERE.parent))       # overlay_sources, for program_marks

from PIL import Image, ImageDraw  # noqa: E402

import program_marks  # noqa: E402
from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

RENDER_PX = 96
WHITE = (255, 255, 255, 255)

# Source commit of the app icon (also the shortcut source; see SOURCES.md).
DC_SHA = "e862e0a613c0793c6fea7cfd37ad4145ed6cf686"
ICO_URL = ("https://raw.githubusercontent.com/storytold/designcraft/"
           f"{DC_SHA}/assets/app-icon/designcraft.ico")

# Same action as in Illustrator -> the same bytes.
BORROW = {n: "illustrator" for n in (
    "select.png", "directselect.png", "type.png", "line.png", "pen.png",
    "pencil.png", "rectangle.png", "ellipse.png", "scissors.png", "scale.png",
    "rotate.png", "gradient.png", "eyedropper.png", "hand.png", "zoom.png",
    "swap.png", "default.png", "new.png", "open.png", "save.png", "saveas.png",
    "print.png", "place.png", "undo.png", "copy.png", "cut.png", "paste.png",
    "selectall.png", "group.png", "ungroup.png", "lock.png", "compound.png",
    "tofront.png", "toback.png", "forward.png", "backward.png", "outlines.png",
    "zoomin.png", "zoomout.png", "rulers.png", "guides.png", "prefs.png",
    "transformagain.png",
)}

# All probed (fetched, 404-checked) before use. "ms:" = Material Symbols.
GLYPHS = {
    # tools
    "gap": "Auto Fit Width",
    "collector": "Tray Item Add",
    "convertpoint": "ms:conversion_path",
    "freetransform": "ms:crop_free",
    "measure": "ms:straighten",
    "pagetool": "Document One Page",
    "typeonpath": "ms:text_rotation_angleup",
    "gradfeather": "ms:gradient",
    "colortheme": "Color",
    # single-key commands
    "preview": "ms:preview",
    "togglefs": "ms:flip_to_front",
    "applynone": "Prohibited",
    "clear": "Delete",
    "tablepanel": "Table",
    "quickapply": "Search Sparkle",
    "hidepanels": "Panel Right Contract",
    "hidepanelsx": "ms:right_panel_close",
    # file
    "quit": "Arrow Exit",
    "export": "Arrow Export",
    "savecopy": "Save Copy",
    "placeopts": "Image Edit",
    "package": "Folder Zip",
    "docsetup": "Document Settings",
    # edit / find
    "findchange": "ms:find_replace",
    "findnext": "Search",
    "deselect": "Select All Off",
    "pasteplain": "Clipboard Letter",
    "pasteinto": "Clipboard Arrow Right",
    "duplicate": "Copy Select",
    "steprepeat": "Square Multiple",
    "spelling": "Text Proofing Tools",
    "storyeditor": "Document Text",
    # view
    "fitpage": "Page Fit",
    "fitspread": "Book Open",
    "fitsel": "Zoom Fit",
    "actualsize": "Ratio One To One",
    "pasteboard": "Arrow Expand",
    "frameedges": "Border None",
    "snapguides": "ms:vertical_align_center",
    "baseline": "Line Horizontal 3",
    "threads": "Link",
    "hiddenchars": "ms:format_paragraph",
    "typical": "Image",
    "highq": "HD",
    "fast": "Flash",
    "overprint": "Shape Intersect",
    "controlbar": "Panel Top Expand",
    "nextdoc": "Arrow Next",
    "prevdoc": "Arrow Previous",
    "gotopage": "Document Arrow Right",
    # object / layout
    "hide": "Eye Off",
    "unlockall": "Lock Open",
    "dropshadow": "Square Shadow",
    "textwrap": "Text Wrap",
    "frameopts": "Text Box Settings",
    "releasecompound": "ms:call_split",
    "insertpages": "Copy Add",
    "overrideparent": "Document Edit",
    "firstabove": "Arrow Upload",
    "lastbelow": "Arrow Download",
    "createtable": "Table Add",
    # type
    "alignleft": "Text Align Left",
    "aligncenter": "Text Align Center",
    "alignright": "Text Align Right",
    "justify": "Text Align Justify",
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "allcaps": "Text Case Uppercase",
    "sizeup": "Font Increase",
    "sizedown": "Font Decrease",
}


def _canvas():
    u = RENDER_PX * 4
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    return u, img, ImageDraw.Draw(img)


def _save(img: Image.Image, path: Path) -> None:
    img.resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def _pen_with(path: Path, sign: str) -> None:
    """Add/Delete Anchor Point tools (= / -): the shared pen nib, shifted left,
    with a bold + or - beside it."""
    pen = Image.open(path.parent / "pen.png").convert("RGBA")
    u, img, d = _canvas()
    nib = pen.resize((u, u), Image.LANCZOS)
    img.alpha_composite(nib, (-int(u * 0.16), 0))
    w = int(u * 0.09)
    cx, cy, r = int(u * 0.76), int(u * 0.30), int(u * 0.15)
    d.rectangle([cx - r, cy - w // 2, cx + r, cy + w // 2], fill=WHITE)
    if sign == "+":
        d.rectangle([cx - w // 2, cy - r, cx + w // 2, cy + r], fill=WHITE)
    _save(img, path)


def _draw_addanchor(path: Path) -> None:
    _pen_with(path, "+")


def _draw_delanchor(path: Path) -> None:
    _pen_with(path, "-")


def _draw_rectframe(path: Path) -> None:
    """Rectangle Frame tool (F): the placeholder frame, a rectangle with an X."""
    u, img, d = _canvas()
    w = int(u * 0.055)
    box = [0.12 * u, 0.20 * u, 0.88 * u, 0.80 * u]
    d.rectangle(box, outline=WHITE, width=w)
    d.line([(box[0], box[1]), (box[2], box[3])], fill=WHITE, width=int(w * 0.7))
    d.line([(box[0], box[3]), (box[2], box[1])], fill=WHITE, width=int(w * 0.7))
    _save(img, path)


def _draw_shear(path: Path) -> None:
    """Shear tool (O): a sheared square, i.e. a parallelogram outline."""
    u, img, d = _canvas()
    w = int(u * 0.06)
    pts = [(0.30 * u, 0.20 * u), (0.90 * u, 0.20 * u), (0.70 * u, 0.80 * u), (0.10 * u, 0.80 * u)]
    d.line(pts + [pts[0]], fill=WHITE, width=w, joint="curve")
    _save(img, path)


DRAWN = {
    "addanchor.png": _draw_addanchor,
    "delanchor.png": _draw_delanchor,
    "rectframe.png": _draw_rectframe,
    "shear.png": _draw_shear,
}


def main() -> int:
    out = HERE / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.borrow(BORROW, out)
    icon_fetch.fluent(GLYPHS, out)
    for fname, fn in DRAWN.items():
        if (out / fname).exists():
            print(f"  {fname}  <- committed asset (left as-is)")
        else:
            fn(out / fname)
            print(f"  {fname}  <- drawn (white-on-transparent glyph)")
    program_marks.own_icon(out / "designcraft.png", ICO_URL, frame=64,
                           credit="storytold/designcraft assets/app-icon/designcraft.ico (MIT OR Apache-2.0)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
