#!/usr/bin/env python3
"""Fetch + render the VectorCraft shortcut icons (reproducible source step).

VectorCraft (storytold/vectorcraft, MIT OR Apache-2.0) is the ArtCraft suite's
Illustrator-like vector editor. Five kinds of icon live in `icons/`:

* BORROWED -- the Illustrator overlay's own glyphs (same repo, GPL-3.0-or-later)
  for every action the two apps share, so the same action draws the same cell
  across both overlays (and the overlay icon library stores it once). Copied once
  and then guarded.
* APP -- VectorCraft's OWN toolbar / panel icons, from `assets/icons/` at the
  pinned commit: the `dc-*` set is original VectorCraft work (MIT OR
  Apache-2.0), the rest is Lucide (ISC) as vendored by VectorCraft. These are the
  icons the user actually sees in the app, so they win over a generic glyph for
  every tool and panel Illustrator's overlay has no picture for. Deterministic,
  so a re-run may overwrite them.
* FLUENT -- Microsoft Fluent UI System Icons (MIT), or Google Material Symbols
  (Apache-2.0) for an `ms:` name, via the shared `icon_fetch`. Deterministic.
* DERIVED -- composites of two of the above (a base glyph plus a corner badge:
  "make" = plus, "release" = minus, a lock, an eye, ...), and two
  small drawn glyphs (checkerboard, pixel staircase). White-on-transparent, so
  the bindings read them with `mode: alpha`. Guarded.
* PROGRAM MARK -- `vectorcraft.png`, the app's own icon (the engraved dragon,
  `assets/app-icon/vectorcraft.ico`, MIT OR Apache-2.0) reduced to the dragon's
  silhouette: every pixel that is not the orange field. Guarded.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/vectorcraft/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RENDER_PX = 96
# Pinned so a re-run reproduces the committed icons byte for byte.
VC_SHA = "0d0ea352df99044589a7ce0efc7004f7a5b6b7c0"
VC_RAW = f"https://raw.githubusercontent.com/storytold/vectorcraft/{VC_SHA}/{{}}"

BORROWED = {  # name -> sibling app folder it is copied from
    name: "illustrator" for name in (
        # tools
        "select.png", "directselect.png", "magicwand.png", "lasso.png", "pen.png",
        "type.png", "line.png", "rectangle.png", "ellipse.png", "paintbrush.png",
        "pencil.png", "scissors.png", "rotate.png", "reflect.png", "scale.png",
        "mesh.png", "gradient.png", "eyedropper.png", "livepaint.png", "zoom.png",
        "hand.png", "eraser.png", "width.png", "swap.png", "default.png",
        # file / edit
        "new.png", "open.png", "save.png", "saveas.png", "print.png", "place.png",
        "undo.png", "copy.png", "cut.png", "paste.png", "selectall.png",
        "transformagain.png", "forward.png", "backward.png",
        # object / view
        "group.png", "ungroup.png", "lock.png", "clipmask.png", "compound.png",
        "tofront.png", "toback.png", "outlines.png", "zoomin.png", "zoomout.png",
        "outline.png", "join.png", "rulers.png", "guides.png", "smartguides.png",
        "hideedges.png", "newlayer.png", "prefs.png", "applyeffect.png",
        "average.png", "blend.png", "showall.png",
    )
}

APP = {  # stem -> VectorCraft assets/icons/<name>.svg (the toolbar icon the app shows)
    "freetransform": "dc-free-transform",   # E   Free Transform tool
    "blendtool": "dc-blend",                # W   Blend tool
    "graph": "chart-column",                # J   Column Graph tool
    "deleteanchor": "pen-tool-delete",      # -   Delete Anchor Point tool
    "addanchor": "pen-tool-add",            # +   Add Anchor Point tool
    "anchorpoint": "dc-anchor",             # Shift+C Anchor Point tool
    "curvature": "spline",                  # Shift+~ Curvature tool
    "touchtype": "dc-touch-type",           # Shift+T Touch Type tool
    "blobbrush": "brush",                   # Shift+B Blob Brush tool
    "shaper": "shapes",                     # Shift+N Shaper tool
    "warp": "waves",                        # Shift+R Warp tool
    "shapebuilder": "dc-shape-builder",     # Shift+M Shape Builder tool
    "liveselect": "dc-live-select",         # Shift+L Live Paint Selection tool
    "perspective": "dc-perspective",        # Shift+P Perspective Grid tool
    "symbolsprayer": "dc-symbol-sprayer",   # Shift+S Symbol Sprayer tool
    "artboard": "frame",                    # Shift+O Artboard tool
    "slice": "slice",                       # Shift+K Slice tool
    "rotateview": "dc-rotate-view",         # Shift+H Rotate View tool
    "selection_arrow": "dc-selection",      # (badge source only)
    "artboards": "dc-artboards",            # (badge source only)
    "paintnone": "dc-fill-none",            # /   None
    "screenmode": "dc-screen-mode",         # F   Screen Mode
    "drawmode": "dc-draw-inside",           # Shift+D Drawing Mode
    "colorguide": "dc-color-guide",         # Shift+F3
    "graphicstyles": "dc-graphic-styles",   # Shift+F5
    "appearance": "dc-appearance",          # Shift+F6
    "align": "dc-align",                    # Shift+F7
    "transformpanel": "dc-transform-panel",  # Shift+F8
    "info": "info",                         # Ctrl+F8
    "gradientpanel": "dc-gradient",         # Ctrl+F9
    "stroke": "dc-stroke",                  # Ctrl+F10
    "pathfinder": "dc-pathfinder",          # Ctrl+Shift+F9
    "transparency": "dc-transparency",      # Ctrl+Shift+F10
    "color": "palette",                     # F6
    "layers": "layers",                     # F7
    "pilcrow": "pilcrow",                   # Ctrl+Alt+T Paragraph (and a badge base)
    "lasteffect": "dc-fx",                  # Ctrl+Alt+Shift+E Last Effect…
}

FLUENT = {  # stem -> Fluent folder name, or "ms:<material symbol>"
    "fillstrokefocus": "ms:flip_to_front",   # X   Toggle Fill/Stroke focus
    "lastcolor": "ms:format_color_fill",     # ,   Apply Last Color
    "lastgradient": "ms:gradient",           # .   Apply Last Gradient (dc-grad-linear loses its light half at 1-bit)
    "clear": "Delete",                       # Delete  Clear
    "revert": "ms:restore_page",             # F12 Revert
    "panels": "ms:right_panel_close",        # Tab Show/hide panels
    "brushes": "ms:brush",                   # F5  Brushes panel
    "presentation": "ms:slideshow",          # Shift+F Presentation Mode
    "nudgeleft": "Arrow Left",
    "nudgeright": "Arrow Right",
    "nudgeup": "Arrow Up",
    "nudgedown": "Arrow Down",
    "nudge10left": "ms:keyboard_double_arrow_left",
    "nudge10right": "ms:keyboard_double_arrow_right",
    "nudge10up": "ms:keyboard_double_arrow_up",
    "nudge10down": "ms:keyboard_double_arrow_down",
    "showgrid": "Grid Dots",                 # Ctrl+'
    "fitartboard": "ms:fit_screen",          # Ctrl+0
    "actualsize": "Ratio One To One",        # Ctrl+1
    "hide": "ms:hide_source",                # Ctrl+3 Hide selection
    "bringforward": "Position Forward",      # Ctrl+]
    "sendbackward": "Position Backward",     # Ctrl+[
    "quit": "Power",                         # Ctrl+Q
    "close": "Dismiss",                      # Ctrl+W
    "attributes": "ms:list_alt",             # Ctrl+F11
    "character": "Text Font",                # Ctrl+T
    "snaptogrid": "ms:background_grid_small",  # Ctrl+Shift+'
    "fontdown": "Font Decrease",             # Ctrl+Shift+,
    "fontup": "Font Increase",               # Ctrl+Shift+.
    "search": "Search",                      # Ctrl+Shift+/ Search Commands
    "resetrotate": "Arrow Reset",            # Ctrl+Shift+1
    "deselect": "ms:deselect",               # Ctrl+Shift+A (Fluent Select All Off reads as a plain square)
    "boundingbox": "ms:crop_free",           # Ctrl+Shift+B
    "aligncenter": "Text Align Center",      # Ctrl+Shift+C
    "justifyall": "Text Align Distributed",  # Ctrl+Shift+F
    "editpattern": "ms:pattern",             # Ctrl+Shift+F8
    "justifyleft": "Text Align Justify",     # Ctrl+Shift+J
    "alignleft": "Text Align Left",          # Ctrl+Shift+L
    "move": "Arrow Move",                    # Ctrl+Shift+M
    "newtemplate": "Document Copy",          # Ctrl+Shift+N
    "alignright": "Text Align Right",        # Ctrl+Shift+R
    "tabs": "ms:keyboard_tab",               # Ctrl+Shift+T
    "pasteinplace": "ms:content_paste_go",   # Ctrl+Shift+V
    "textthreads": "Link Dismiss",           # Ctrl+Shift+Y
    "redo": "Arrow Redo",                    # Ctrl+Shift+Z
    "symbols": "ms:emoji_symbols",           # Ctrl+Shift+F11
    "snaptopoint": "ms:point_scan",          # Ctrl+Alt+'
    "fitall": "ms:zoom_out_map",             # Ctrl+Alt+0
    "unlockall": "Lock Open",                # Ctrl+Alt+2
    "envtop": "ms:stack",                    # Ctrl+Alt+C Envelope: Make with Top Object
    "exportscreens": "ms:devices",           # Ctrl+Alt+E
    "envmesh": "ms:grid_4x4",                # Ctrl+Alt+M Envelope: Make with Mesh
    "docsetup": "Document Settings",         # Ctrl+Alt+P
    "savecopy": "Save Multiple",             # Ctrl+Alt+S
    "pasteplain": "ms:format_clear",         # Ctrl+Alt+V Paste without Formatting
    "closeall": "Dismiss Square Multiple",   # Ctrl+Alt+W
    "transformeach": "ms:transform",         # Ctrl+Alt+Shift+D
    "fileinfo": "ms:description",            # Ctrl+Alt+Shift+I
    "shortcuts": "Keyboard",                 # Ctrl+Alt+Shift+K
    "package": "ms:package_2",               # Ctrl+Alt+Shift+P
    "saveforweb": "Globe",                   # Ctrl+Alt+Shift+S
    "envwarp": "ms:airwave",                 # Ctrl+Alt+Shift+W
    "opentype": "ms:font_download",          # Ctrl+Alt+Shift+T
    # badge sources only
    "_eye": "Eye",
    "_eyeoff": "Eye Off",
    "_settings": "Settings",
    "_redo_ccw": "Arrow Counterclockwise",
}

WHITE = (255, 255, 255, 255)


def _app_svg(name: str) -> bytes:
    url = VC_RAW.format(f"assets/icons/{name}.svg")
    req = urllib.request.Request(url, headers={"User-Agent": "polykybd"})
    return urllib.request.urlopen(req, timeout=30).read()


def _shape(path: Path) -> Image.Image:
    """An icon's shape as an L mask: its alpha (every source here is linework on
    transparent, whichever colour the linework is)."""
    return Image.open(path).convert("RGBA").split()[3]


def _to_png(mask: Image.Image, path: Path) -> None:
    arr = np.zeros((RENDER_PX, RENDER_PX, 4), np.uint8)
    arr[..., :3] = 255
    arr[..., 3] = np.asarray(mask.resize((RENDER_PX, RENDER_PX), Image.LANCZOS))
    Image.fromarray(arr, "RGBA").save(path)


def _sign(kind: str) -> Image.Image:
    """A thick plus / minus badge (L mask, 96 px)."""
    u = RENDER_PX * 4
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    w = int(u * 0.20)
    d.rectangle([int(u * 0.08), u // 2 - w // 2, int(u * 0.92), u // 2 + w // 2], fill=255)
    if kind == "plus":
        d.rectangle([u // 2 - w // 2, int(u * 0.08), u // 2 + w // 2, int(u * 0.92)], fill=255)
    return m.resize((RENDER_PX, RENDER_PX), Image.LANCZOS)


def _badge(out: Path, base: Path, badge: Path | str, scale: float = 0.56) -> None:
    """`base` with `badge` in its bottom-right corner. The base keeps the top-left
    82%; only the pixels under the badge plus a thin moat round its OWN outline
    are cleared, so the base loses as little as possible."""
    canvas = Image.new("L", (RENDER_PX, RENDER_PX), 0)
    canvas.paste(_shape(base).resize((int(RENDER_PX * 0.82),) * 2, Image.LANCZOS), (0, 0))
    bs = int(RENDER_PX * scale)
    sm = (_sign(badge) if isinstance(badge, str) else _shape(badge)).resize((bs, bs), Image.LANCZOS)
    layer = Image.new("L", (RENDER_PX, RENDER_PX), 0)
    layer.paste(sm, (RENDER_PX - bs, RENDER_PX - bs))
    # moat: the badge's solid footprint (holes filled by a closing), dilated
    foot = layer.point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MaxFilter(23)).filter(ImageFilter.MinFilter(5))
    base_arr = np.asarray(canvas, dtype=np.uint16) * (255 - np.asarray(foot, dtype=np.uint16)) // 255
    merged = np.maximum(base_arr.astype(np.uint8), np.asarray(layer))
    _to_png(Image.fromarray(merged), out)


def _checker(out: Path) -> None:
    """Transparency grid (Ctrl+Shift+D): a 4x3 checkerboard in a frame."""
    u = RENDER_PX * 4
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = int(u * 0.10), int(u * 0.20), int(u * 0.90), int(u * 0.80)
    cw, ch = (x1 - x0) / 4, (y1 - y0) / 3
    for r in range(3):
        for c in range(4):
            if (r + c) % 2 == 0:
                d.rectangle([x0 + c * cw, y0 + r * ch, x0 + (c + 1) * cw, y0 + (r + 1) * ch], fill=255)
    d.rectangle([x0, y0, x1, y1], outline=255, width=int(u * 0.035))
    _to_png(m, out)


def _pixels(out: Path) -> None:
    """Pixel Preview (Ctrl+Alt+Y): a curve rasterised into a staircase of pixels."""
    u = RENDER_PX * 4
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    s = u / 8
    for col, row in ((1, 6), (2, 6), (2, 5), (3, 5), (3, 4), (4, 4), (4, 3), (5, 3), (5, 2), (6, 2), (6, 1)):
        d.rectangle([col * s + 3, row * s + 3, (col + 1) * s - 3, (row + 1) * s - 3], fill=255)
    _to_png(m, out)


def _program_mark(out: Path) -> None:
    """The app's OWN icon reduced to what reads at 40 px: the dragon's silhouette.

    The tile is an engraving (ink hatching on paper) over a #e8573f field; at
    keycap size the hatching dithers into noise under any luma/bright threshold
    (swept 70..210, frames 40..256). Separating the figure from the FIELD by
    colour instead gives a solid head-and-neck profile that does read.
    """
    req = urllib.request.Request(VC_RAW.format("assets/app-icon/vectorcraft.ico"),
                                 headers={"User-Agent": "polykybd"})
    ico = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=60).read()))
    ico.size = (256, 256)
    a = np.asarray(ico.convert("RGBA")).astype(float)
    field = np.array([0xE8, 0x57, 0x3F], float)
    dist = np.sqrt(((a[..., :3] - field) ** 2).sum(-1))
    sil = ((dist > 60) & (a[..., 3] > 128)).astype(np.uint8) * 255
    m = Image.fromarray(sil).filter(ImageFilter.MedianFilter(5))
    arr = np.zeros((256, 256, 4), np.uint8)
    arr[..., :3] = 255
    arr[..., 3] = np.asarray(m)
    Image.fromarray(arr, "RGBA").save(out)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    icon_fetch.borrow(BORROWED, out)
    icon_fetch.fluent(FLUENT, out)
    for stem, name in APP.items():
        png = cairosvg.svg2png(bytestring=_app_svg(name), output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{stem}.png").write_bytes(png)
        print(f"  {stem}.png  <- storytold/vectorcraft@{VC_SHA[:7]} assets/icons/{name}.svg")

    i = lambda n: out / f"{n}.png"  # noqa: E731
    derived = {
        # guides family (Ctrl+5 / Ctrl+Alt+5 / Ctrl+Alt+;)
        "makeguides.png": lambda p: _badge(p, i("guides"), "plus"),
        "releaseguides.png": lambda p: _badge(p, i("guides"), "minus"),
        "lockguides.png": lambda p: _badge(p, i("guides"), i("lock")),
        # make / release pairs
        "releaseclip.png": lambda p: _badge(p, i("clipmask"), "minus"),
        "releasecompound.png": lambda p: _badge(p, i("compound"), "minus"),
        "releaseblend.png": lambda p: _badge(p, i("blend"), "minus"),
        "livepaintmake.png": lambda p: _badge(p, i("livepaint"), "plus"),
        # selection
        "reselect.png": lambda p: _badge(p, i("selectall"), i("_redo_ccw")),
        "selectartboard.png": lambda p: _badge(p, i("selectall"), i("artboard")),
        "nextabove.png": lambda p: _badge(p, i("selection_arrow"), i("nudgeup")),
        "nextbelow.png": lambda p: _badge(p, i("selection_arrow"), i("nudgedown")),
        "perspselect.png": lambda p: _badge(p, i("perspective"), i("selection_arrow")),
        # show / hide toggles
        "hideartboards.png": lambda p: _badge(p, i("artboards"), i("_eyeoff")),
        "showpersp.png": lambda p: _badge(p, i("perspective"), i("_eye")),
        "hiddenchars.png": lambda p: _badge(p, i("pilcrow"), i("_eye")),
        "gradannotator.png": lambda p: _badge(p, i("gradient"), i("_eyeoff")),
        "overprint.png": lambda p: _badge(p, i("print"), i("_eye")),
        # misc
        "colorsettings.png": lambda p: _badge(p, i("color"), i("_settings")),
        "pasteartboards.png": lambda p: _badge(p, i("paste"), i("artboards")),
        "nudgecopyleft.png": lambda p: _badge(p, i("copy"), i("nudgeleft")),
        "nudgecopyright.png": lambda p: _badge(p, i("copy"), i("nudgeright")),
        "nudgecopyup.png": lambda p: _badge(p, i("copy"), i("nudgeup")),
        "nudgecopydown.png": lambda p: _badge(p, i("copy"), i("nudgedown")),
        "nudgecopy10left.png": lambda p: _badge(p, i("copy"), i("nudge10left")),
        "nudgecopy10right.png": lambda p: _badge(p, i("copy"), i("nudge10right")),
        "nudgecopy10up.png": lambda p: _badge(p, i("copy"), i("nudge10up")),
        "nudgecopy10down.png": lambda p: _badge(p, i("copy"), i("nudge10down")),
        "transparencygrid.png": _checker,
        "pixelpreview.png": _pixels,
        "vectorcraft.png": _program_mark,
    }
    for name, fn in derived.items():
        if (out / name).exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            fn(out / name)
            print(f"  {name}  <- derived")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
