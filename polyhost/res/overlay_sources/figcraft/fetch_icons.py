#!/usr/bin/env python3
"""Fetch + render the FigCraft shortcut icons (reproducible).

FigCraft (github.com/storytold/figcraft, MIT OR Apache-2.0) is an open-source
Figma-like design tool, so the actions it shares with Figma reuse the Figma
overlay's committed icons byte-for-byte (`icon_fetch.borrow`), and the rest are
Microsoft Fluent UI System Icons (MIT) with Material Symbols (Apache-2.0) for
gaps. A few icons are composites of stock glyphs (chevrons turned on their side,
bold + arrow, auto layout struck through) because no single glyph says it.

The program mark (ESC) is FigCraft's OWN icon (assets/app-icon/figcraft-small.svg,
MIT OR Apache-2.0), reduced to its silhouette outline plus its darkest ink lines
so the chameleon reads on a 1-bit 46x40 panel. Every drawn/derived asset is
guarded: a committed file is left as-is.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/figcraft/fetch_icons.py
"""
from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from polyhost.res.overlay_sources import icon_fetch

RENDER_PX = 96
FIGCRAFT_SHA = "e56856f4016c76fbc862ac2fb4fd3fb43a68f396"
MARK_URL = (f"https://raw.githubusercontent.com/storytold/figcraft/{FIGCRAFT_SHA}/"
            "assets/app-icon/figcraft-small.svg")

# Same action as the Figma overlay -> the same committed glyph (concept dedupe,
# consistency between the two apps).
FROM_FIGMA = [
    "move", "scale", "frame", "rectangle", "ellipse", "line", "pen", "text",
    "hand", "comment", "eyedropper", "slice", "copy", "cut", "paste", "undo",
    "duplicate", "group", "selectall", "save", "newfile", "rename", "flatten",
    "find", "bold", "italic", "underline", "strikethrough", "ungroup",
    "placeimage", "outlinestroke", "export", "copypng", "rulers", "grid",
    "outlineview", "zoomfit", "zoomsel", "pencil", "arrowtool", "component",
    "detach", "tofront", "toback", "forward", "backward", "mask", "selinverse",
    "frameselection",
]

# FigCraft-only actions. All names probed (HTTP 200) before use.
FLUENT = {
    "nextframe": "Arrow Next",
    "prevframe": "Arrow Previous",
    "cursorchat": "Chat",
    "selparent": "Arrow Up Left",
    "prevpage": "Document Arrow Up",
    "nextpage": "Document Arrow Down",
    "nextregion": "Arrow Circle Right",
    "prevregion": "Arrow Circle Left",
    "selarea": "ms:select",
    "opacity": "ms:opacity",
    "zoomtool": "Zoom In",
    "zoomtoolout": "Zoom Out",
    "section": "Board",
    "shapebuilder": "Shapes",
    "pixelgrid": "Grid Dots",
    "snappixel": "ms:grid_guides",
    "comments": "Comment Multiple",
    "designproto": "Arrow Bidirectional Left Right",
    "devmode": "Code",
    "contextmenu": "ms:menu_open",
    "zoom100": "Ratio One To One",
    "removestroke": "Border None",
    "removefill": "ms:format_color_reset",
    "swapfill": "Arrow Sort",
    "fliph": "Flip Horizontal",
    "flipv": "Flip Vertical",
    "autolayout": "Auto Fit Width",
    "suggestlayout": "Wand",
    "deleteheal": "Pen Prohibited",
    "layerspanel": "Stack",
    "assets": "Square Multiple",
    "libraries": "Library",
    "designpanel": "Design Ideas",
    "protopanel": "Flowchart",
    "collapselayers": "Arrow Collapse All",
    "lineheightup": "ms:unfold_more",
    "lineheightdown": "ms:unfold_less",
    "rotorigin": "Arrow Rotate Clockwise",
    "alignleft": "Align Left",
    "alignhcenter": "Align Center Horizontal",
    "alignright": "Align Right",
    "aligntop": "Align Top",
    "alignvcenter": "Align Center Vertical",
    "alignbottom": "Align Bottom",
    "union": "Shape Union",
    "subtract": "Shape Subtract",
    "intersect": "Shape Intersect",
    "exclude": "Shape Exclude",
    "distributeh": "Align Space Evenly Horizontal",
    "distributev": "Align Space Evenly Vertical",
    "tidy": "Layout Cell Four",
    "actions": "Flash",
    "toggleui": "ms:fullscreen",
    "leftsidebar": "Panel Left Contract",
    "cursors": "Cursor",
    "preferences": "Settings",
    "open": "Folder Open",
    "close": "Dismiss",
    "join": "Arrow Join",
    "smoothjoin": "ms:line_curve",
    "saveas": "Save Copy",
    "saveversion": "History",
    "runplugin": "Puzzle Piece",
    "pixelpreview": "ms:background_grid_small",
    "visible": "Eye",
    "lock": "Lock Closed",
    "bulletlist": "Text Bullet List",
    "numberlist": "ms:format_list_numbered",
    "sizeup": "Font Increase",
    "sizedown": "Font Decrease",
    "textleft": "Text Align Left",
    "textcenter": "Text Align Center",
    "textright": "Text Align Right",
    "textjustify": "Text Align Justify",
    "selmatching": "Target Arrow",
    "pastereplace": "ms:find_replace",
    "pasteover": "Clipboard Arrow Right",
    "import": "Arrow Import",
    "resizefit": "Arrow Fit",
    "gotomain": "Arrow Square Up Right",
    "shortcuts": "Keyboard",
}


def _fluent_rgba(spec: str, px: int) -> Image.Image:
    svg, _, _ = icon_fetch._fetch_svg(spec)
    return Image.open(io.BytesIO(cairosvg.svg2png(
        bytestring=svg, output_width=px, output_height=px))).convert("RGBA")


def _turned(path: Path, spec: str) -> None:
    """`spec`'s glyph turned 90 degrees: letter spacing (tracking) up/down is the
    line-height pair's chevrons laid on their side, so the two pairs read alike."""
    _fluent_rgba(spec, RENDER_PX).transpose(Image.ROTATE_90).save(path)


def _bold_arrow(path: Path, arrow: str) -> None:
    """Font weight up/down: the Bold glyph with an up/down arrow beside it."""
    canvas = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    canvas.alpha_composite(_fluent_rgba("Text Bold", 64), (0, 16))
    canvas.alpha_composite(_fluent_rgba(arrow, 48), (48, 24))
    canvas.save(path)


def _struck(path: Path, spec: str) -> None:
    """`spec`'s glyph with a diagonal strike (remove auto layout)."""
    img = _fluent_rgba(spec, RENDER_PX)
    d = ImageDraw.Draw(img)
    d.line([(10, 86), (86, 10)], fill=(33, 33, 33, 255), width=7)
    img.save(path)


def _program_mark(path: Path) -> None:
    """FigCraft's own chameleon, reduced for a 1-bit keycap: render the SVG at
    256 px, downscale to 92, take the figure (everything not the green field
    #02da96), keep its 5-px-eroded outline plus the darkest ink (luma < 60)
    inside it. White on transparent -> program_icon_mode: alpha. Picked from a
    frame/mode/threshold sweep; plain luma/bright renders of the engraving were
    hatch noise at 46x40."""
    src = Image.open(io.BytesIO(cairosvg.svg2png(
        bytestring=urllib.request.urlopen(MARK_URL, timeout=60).read(),
        output_width=256, output_height=256))).convert("RGBA")
    res = 92
    a = np.asarray(src.resize((res, res), Image.LANCZOS)).astype(float)
    dist = np.sqrt(((a[..., :3] - np.array([2, 218, 150])) ** 2).sum(-1))
    fig = (dist > 80) & (a[..., 3] > 127)
    eroded = np.asarray(Image.fromarray((fig * 255).astype(np.uint8))
                        .filter(ImageFilter.MinFilter(5))) > 127
    lum = a[..., :3] @ [0.2989, 0.587, 0.114]
    lit = (fig & ~eroded) | (fig & (lum < 60))
    rgba = np.zeros((res, res, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = lit * 255
    Image.fromarray(rgba, "RGBA").save(path)


_DERIVED = {
    "trackingup.png": lambda p: _turned(p, "ms:unfold_more"),
    "trackingdown.png": lambda p: _turned(p, "ms:unfold_less"),
    "weightup.png": lambda p: _bold_arrow(p, "Arrow Up"),
    "weightdown.png": lambda p: _bold_arrow(p, "Arrow Down"),
    "removelayout.png": lambda p: _struck(p, "Auto Fit Width"),
    "figcraft.png": _program_mark,
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.borrow({f"{n}.png": "figma" for n in FROM_FIGMA}, out)
    icon_fetch.fluent(FLUENT, out)
    for fname, fn in _DERIVED.items():
        if (out / fname).exists():
            print(f"  {fname}  <- committed asset (left as-is)")
        else:
            fn(out / fname)
            print(f"  {fname}  <- derived")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
