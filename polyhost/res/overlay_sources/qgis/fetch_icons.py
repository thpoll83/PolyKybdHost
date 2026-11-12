#!/usr/bin/env python3
"""Fetch + render the QGIS shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. Some icons are copied
byte-identical from the FreeCAD, KiCad and Blender sets (`icon_fetch.borrow`). The
layer-type keys (PostgreSQL, Oracle, WMS, ...) and the expression key are text
in DejaVu Sans Bold. The ESC mark is QGIS's own monochrome logo
(`images/icons/qgis-icon-minimal-black.svg` at tag final-4_2_3), rendered at
32x32 and reduced to 1 bit. See SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/qgis/fetch_icons.py
"""
from __future__ import annotations

import io
import re
import sys
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RENDER_PX = 96
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# QGIS's monochrome logo at the release tag the shortcut list was read from.
QGIS_TAG = "final-4_2_3"
QGIS_LOGO_URL = ("https://raw.githubusercontent.com/qgis/QGIS/" + QGIS_TAG
                 + "/images/icons/qgis-icon-minimal-black.svg")
MARK_PX = 32          # program_icon_region [37, 32], fit contain -> 32x32, copied 1:1
MARK_ALPHA = 128      # alpha at or above this is lit

FLUENT = {
    # --- project, windows, panels ---
    "datasource": "ms:database",
    "newlayout": "ms:print",
    "projprops": "ms:settings_applications",
    "newmap": "ms:map",
    "elevation": "ms:landscape",
    "homepage": "ms:open_in_browser",
    "devtools": "ms:bug_report",
    "panelsvis": "ms:left_panel_close",
    "maponly": "ms:open_in_full",
    "gpspanel": "ms:my_location",
    "browserpanel": "ms:topic",
    "stylepanel": "ms:palette",
    "cadpanel": "ms:architecture",
    "undopanel": "ms:sync_alt",
    "statspanel": "ms:functions",
    "bookmarks": "ms:bookmarks",
    "overviewpanel": "ms:picture_in_picture",
    "orderpanel": "ms:swap_vert",
    # --- layers ---
    "addvector": "ms:polyline",
    "addraster": "ms:image",
    "scratchlayer": "ms:content_paste_go",
    "removelayer": "ms:playlist_remove",
    "setcrs": "ms:public",
    "filter": "ms:filter_alt",
    "hidelayers": "ms:visibility_off",
    "showlayers": "ms:visibility",
    # --- selection and editing ---
    "deselectlayer": "ms:remove_selection",
    "selbyvalue": "ms:checklist",
    "addfeature": "ms:add_location_alt",
    "curve": "ms:line_curve",
    "stream": "ms:gesture",
    "tracing": "ms:conversion_path",
    # --- view, measure, identify ---
    "zoomintool": "ms:zoom_in_map",
    "zoomouttool": "ms:zoom_out_map",
    "zoomsel": "ms:frame_inspect",
    "pan": "ms:pan_tool",
    "measurearea": "ms:square_foot",
    "identify": "ms:info",
    # --- attribute table and profile/3D nudges ---
    "table": "ms:table",
    "tablesel": "ms:table_rows",
    "tablevis": "ms:table_eye",
    "firstfeat": "ms:first_page",
    "prevfeat": "ms:navigate_before",
    "nextfeat": "ms:navigate_next",
    "lastfeat": "ms:last_page",
    "profleft": "ms:keyboard_double_arrow_left",
    "profright": "ms:keyboard_double_arrow_right",
    "scene3d": "ms:crop",
    "xsecleft": "ms:switch_left",
    "xsecright": "ms:switch_right",
    # --- processing ---
    "toolbox": "ms:handyman",
    "modeler": "ms:account_tree",
    "history": "ms:history",
    "results": "ms:fact_check",
}

# Same action as in a sibling set: copied byte-identical.
BORROW = {
    "snap.png": "blender",
    "fullscreen.png": "freecad",
    "refresh.png": "freecad",
    "console.png": "freecad",
    "isometric.png": "freecad",
    "storeview.png": "freecad",
    "recallview.png": "freecad",
    "measure.png": "kicad",
    "zoomfit.png": "kicad",
    "unselectall.png": "kicad",
    "search.png": "kicad",
    "togglelayer.png": "kicad",
}

TEXT = {
    "pglayer": "PG",
    "oralayer": "ORA",
    "sllayer": "SL",
    "wmslayer": "WMS",
    "csvlayer": "CSV",
    "gpkglayer": "GPKG",
    "expression": "ε",
}


def _draw_text(path: Path, text: str) -> None:
    """Black text on transparent, like the fetched glyphs, scaled so its ink
    fills the icon (the FreeCAD set's text icons are drawn the same way)."""
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    probe = ImageFont.truetype(FONT, 100)
    box = d.textbbox((0, 0), text, font=probe)
    scale = min(RENDER_PX * 0.95 / (box[2] - box[0]), RENDER_PX * 0.9 / (box[3] - box[1]))
    font = ImageFont.truetype(FONT, max(8, int(100 * scale)))
    box = d.textbbox((0, 0), text, font=font)
    x = (RENDER_PX - (box[2] - box[0])) / 2 - box[0]
    y = (RENDER_PX - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), text, font=font, fill=(0, 0, 0, 255))
    img.save(path)


def _add_sign(path: Path, plus: bool) -> None:
    """Draw a + (zoom in) or - (zoom out) in the middle of the fetched
    zoom_in_map / zoom_out_map arrows, so the two tool keys read apart.
    The sign is 24x6 px at the 96 px render size (10x2 px on the keycap)."""
    img = Image.open(path).convert("RGBA")
    d = ImageDraw.Draw(img)
    c, half, w = RENDER_PX // 2, 12, 6
    d.rectangle([c - half, c - w // 2, c + half - 1, c + w // 2 - 1], fill=(0, 0, 0, 255))
    if plus:
        d.rectangle([c - w // 2, c - half, c + w // 2 - 1, c + half - 1], fill=(0, 0, 0, 255))
    img.save(path)


def _logo_svg() -> bytes:
    """The logo SVG with its QGIS SVG-marker parameters resolved: every
    `param(x) <default>` takes its default, and the three without one take a
    black fill, full opacity and no outline. The shapes are not changed."""
    req = urllib.request.Request(QGIS_LOGO_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        svg = r.read().decode("utf-8")
    plain = {"fill": "#000000", "fill-opacity": "1", "outline": "none"}

    def resolve(m: re.Match) -> str:
        return m.group(2).strip() or plain[m.group(1)]

    svg = re.sub(r'param\(([^)]*)\)\s*([^"]*)', resolve, svg)
    return re.sub(r"<script[^>]*/>", "", svg).encode("utf-8")


def _qgis_mark(dest: Path) -> None:
    """The QGIS logo at the keycap size (32x32), white on transparent, 1 bit.
    Drawn at that size so the generator copies it 1:1."""
    png = cairosvg.svg2png(bytestring=_logo_svg(), output_width=MARK_PX, output_height=MARK_PX)
    alpha = Image.open(io.BytesIO(png)).convert("RGBA").getchannel("A")
    a = alpha.point(lambda v: 255 if v >= MARK_ALPHA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    _add_sign(out / "zoomintool.png", plus=True)
    _add_sign(out / "zoomouttool.png", plus=False)
    for name, text in TEXT.items():
        _draw_text(out / f"{name}.png", text)
        n += 1
    mark = out / "qgis.png"
    if mark.exists():
        print("  qgis.png  <- committed asset (left as-is)")
    else:
        _qgis_mark(mark)
        print(f"  qgis.png  <- QGIS {QGIS_TAG} qgis-icon-minimal-black.svg at {MARK_PX}x{MARK_PX}")
    print(f"Wrote {n + 1} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
