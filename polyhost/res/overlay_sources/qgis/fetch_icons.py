#!/usr/bin/env python3
"""Fetch + render the QGIS shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. Some icons are copied
byte-identical from the FreeCAD, KiCad and Blender sets (`icon_fetch.borrow`). The
layer-type keys (PostgreSQL, Oracle, WMS, ...) and the expression key are text
in DejaVu Sans Bold. The ESC mark is QGIS's own monochrome logo
(`images/icons/qgis-icon-minimal-black.svg` at tag final-4_2_3), rendered at
32x32 and reduced to 1 bit. See SOURCES.md.

The drawn text glyphs, the lock composites and the ESC mark are skipped when
their PNG exists, so a hand edit survives a re-run. To redraw one, delete its
PNG first. The fetched and borrowed icons are written again on every run.

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
import space_hint  # noqa: E402
from dcc_glyphs import guarded, with_badge  # noqa: E402

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
    "newlayout": "ms:print_add",
    "printlayout": "ms:print",
    "zoomarea": "ms:pageview",
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
    # --- digitizing and vertex tool (mode sets) ---
    "removevertex": "ms:backspace",
    "deletevertex": "ms:cancel",
    "rangesel": "ms:linear_scale",
    "construction": "ms:construction",
    "cadlock": "ms:lock",
    # --- print layout designer (mode set) ---
    "pagesetup": "ms:aspect_ratio",
    "grid": "ms:grid_on",
    "snapgrid": "ms:grid_4x4",
    "guides": "ms:border_vertical",
    "smartguides": "ms:auto_fix_high",
    "boxes": "ms:activity_zone",
    "selbelow": "ms:move_down",
    "selabove": "ms:move_up",
    "lockitems": "ms:lock",
    "unlockall": "ms:lock_open",
    "raise": "ms:flip_to_front",
    "lower": "ms:flip_to_back",
    "tofront": "ms:vertical_align_top",
    "toback": "ms:vertical_align_bottom",
    "group": "ms:group_work",
    "ungroup": "ms:workspaces",
    "movecontent": "ms:open_with",
    "pasteinplace": "ms:content_paste",
    "atlaspreview": "ms:auto_stories",
    "selectmove": "ms:arrow_selector_tool",
    "close": "ms:close",
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
    # Advanced Digitizing: type a value into a field, or make it relative.
    "cadx": "X=",
    "cady": "Y=",
    "cadz": "Z=",
    "cadm": "M=",
    "cada": "∠=",
    "cadd": "d=",
    "cadrelx": "ΔX",
    "cadrely": "ΔY",
    "cadrelz": "ΔZ",
    "cadrelm": "ΔM",
    "cadrela": "Δ∠",
    "cadperp": "⊥∥",
    "cadnext": "∠+",
    "cadprev": "∠-",
    "zoom100": "1:1",
}

# Advanced Digitizing locks: the lock glyph with the constrained value beside it.
LOCKS = {"cadlockx": "X", "cadlocky": "Y", "cadlockz": "Z", "cadlockm": "M",
         "cadlocka": "∠", "cadlockd": "d"}


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


def _lock_with(src: Path, dest: Path, text: str) -> None:
    """The fetched lock glyph on the left half and `text` on the right half,
    so each lock key names the value it locks."""
    lock = Image.open(src).convert("RGBA").resize((RENDER_PX // 2, RENDER_PX // 2), Image.LANCZOS)
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX // 2), (0, 0, 0, 0))
    img.alpha_composite(lock, (0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(RENDER_PX * 0.42))
    box = d.textbbox((0, 0), text, font=font)
    x = RENDER_PX * 3 // 4 - (box[2] - box[0]) / 2 - box[0]
    y = (RENDER_PX // 2 - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), text, font=font, fill=(0, 0, 0, 255))
    img.save(dest)


def _vertex_step(dest: Path, forward: bool) -> None:
    """Previous / next vertex: a vertex (filled square) on a line segment, with a
    chevron on the side it steps to. Differs from the bare chevrons of
    Previous / Next edited feature (`prevfeat.png`, `nextfeat.png`)."""
    ss = 4
    u = RENDER_PX * ss
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    cy, t = u // 2, int(u * 0.05)
    sq = int(u * 0.17)
    # chevron at the left for "previous"; mirrored at the end for "next"
    cx0, cx1, ch = int(u * 0.04), int(u * 0.30), int(u * 0.28)
    w = int(u * 0.09)
    d.line([(cx1, cy - ch), (cx0, cy), (cx1, cy + ch)], fill=255, width=w, joint="curve")
    vx = int(u * 0.66)
    d.rectangle([int(u * 0.40), cy - t, u - 1, cy + t], fill=255)
    d.rectangle([vx - sq, cy - sq, vx + sq, cy + sq], fill=255)
    if forward:
        m = m.transpose(Image.FLIP_LEFT_RIGHT)
    a = m.resize((RENDER_PX, RENDER_PX), Image.LANCZOS)
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    img.putalpha(a)
    img.save(dest)


def _curve_vertex(dest: Path) -> None:
    """Toggle curve vertex: a quarter arc (like `curve.png`) with a filled
    square vertex on its middle, so it differs from Digitize with curve."""
    import math
    ss = 4
    u = RENDER_PX * ss
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    cx, cy, r, w = 0.10 * u, 0.95 * u, 0.80 * u, int(u * 0.08)
    d.arc([cx - r, cy - r, cx + r, cy + r], 270, 360, fill=255, width=w)
    mx = cx + (r - w / 2) * math.cos(math.radians(45))
    my = cy - (r - w / 2) * math.sin(math.radians(45))
    h = 0.13 * u
    d.rectangle([mx - h, my - h, mx + h, my + h], fill=255)
    a = m.resize((RENDER_PX, RENDER_PX), Image.LANCZOS)
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    img.putalpha(a)
    img.save(dest)


def _rulers_frame(dest: Path) -> None:
    """Show rulers: a page with a ruler along its top and its left edge, each
    with tick marks. Differs from the single ruler of Measure line."""
    ss = 4
    u = RENDER_PX * ss
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    w, band = int(u * 0.06), int(u * 0.20)
    x0, y0, x1, y1 = int(u * 0.06), int(u * 0.10), int(u * 0.94), int(u * 0.90)
    d.rectangle([x0, y0, x1, y1], outline=255, width=w)          # page
    d.rectangle([x0, y0, x1, y0 + band], fill=255)               # top ruler
    d.rectangle([x0, y0, x0 + band, y1], fill=255)               # left ruler
    t = int(u * 0.04)
    for i in range(1, 5):                                        # ticks cut out
        x = x0 + band + i * (x1 - x0 - band) // 5
        d.rectangle([x - t // 2, y0 + band // 2, x + t // 2, y0 + band], fill=0)
        y = y0 + band + i * (y1 - y0 - band) // 5
        d.rectangle([x0 + band // 2, y - t // 2, x0 + band, y + t // 2], fill=0)
    a = m.resize((RENDER_PX, RENDER_PX), Image.LANCZOS)
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    img.putalpha(a)
    img.save(dest)


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
        guarded(out / f"{name}.png", lambda p, t=text: _draw_text(p, t),
                f"text {text!r} in DejaVu Sans Bold")
    for name, text in LOCKS.items():
        guarded(out / f"{name}.png",
                lambda p, t=text: _lock_with(out / "cadlock.png", p, t),
                f"cadlock.png + {text!r} in DejaVu Sans Bold")
    guarded(out / "prevvertex.png", lambda p: _vertex_step(p, forward=False),
            "drawn: chevron + vertex on a segment (_vertex_step)")
    guarded(out / "nextvertex.png", lambda p: _vertex_step(p, forward=True),
            "drawn: vertex on a segment + chevron (_vertex_step)")
    guarded(out / "space_pan.png",
            lambda p: space_hint.draw(space_hint.glyph_from_png(out / "pan.png", 20), p),
            "pan.png + four arrows (space_hint.py)")
    composites = {
        # name: (base, badge) -- dcc_glyphs.with_badge
        "deselalllayers": ("unselectall", "togglelayer"),  # Deselect all layers
        "snapguides": ("snap", "guides"),                  # Snap to guides (layout)
        "atlasfirst": ("firstfeat", "atlaspreview"),       # atlas navigation (layout)
        "atlasprev": ("prevfeat", "atlaspreview"),
        "atlasnext": ("nextfeat", "atlaspreview"),
        "atlaslast": ("lastfeat", "atlaspreview"),
    }
    for name, (base, badge) in composites.items():
        guarded(out / f"{name}.png",
                lambda p, b=base, g=badge: with_badge(out / f"{b}.png", out / f"{g}.png", p),
                f"{base}.png + {badge}.png badge (dcc_glyphs.with_badge)")
    guarded(out / "curvevertex.png", _curve_vertex, "drawn: arc + square vertex (_curve_vertex)")
    guarded(out / "showrulers.png", _rulers_frame, "drawn: page with two rulers (_rulers_frame)")
    mark = out / "qgis.png"
    if mark.exists():
        print("  qgis.png  <- committed asset (left as-is)")
    else:
        _qgis_mark(mark)
        print(f"  qgis.png  <- QGIS {QGIS_TAG} qgis-icon-minimal-black.svg at {MARK_PX}x{MARK_PX}")
    print(f"Fetched {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
