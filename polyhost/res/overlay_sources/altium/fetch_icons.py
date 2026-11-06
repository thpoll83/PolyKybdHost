#!/usr/bin/env python3
"""Fetch + render the Altium Designer shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) for the `ms:` entries. Where KiCad, Eclipse or CADCraft already
draw the same action (fit all, interactive routing, measure, toggle units,
next / previous snap grid, the Properties panel, ...), the icon is a
byte-identical copy of theirs, so one action has one glyph in every set.

The ESC mark is the Altium logo (the altium.com favicon: a dark rounded tile
with a white italic A) reduced to a 32x32 1-bit trace, dark pixels lit, so the
A reads as a cut-out. Altium is a trademark of Altium Limited; see SOURCES.md.
The file is guarded: a committed altium.png is left as it is.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/altium/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

FLUENT = {
    # --- environment and panels ---
    "togglepanels": "ms:dock_to_right",
    "tiledocs": "ms:view_quilt",
    "focuspanel": "ms:swap_horiz",
    "netcolor": "ms:palette",
    "filterpanel": "Filter",
    "listpanel": "ms:list_alt",
    "maximize": "ms:open_in_full",
    "savews": "Cloud Arrow Up",
    "msgnext": "ms:keyboard_double_arrow_down",
    "msgprev": "ms:keyboard_double_arrow_up",
    "comment": "ms:add_comment",
    # --- view ---
    "viewconfig": "ms:layers",
    "viewoptions": "ms:visibility",
    "planmode": "ms:dashboard",
    "mode2d": "ms:crop_square",
    "zoom400": "ms:pageview",
    "redrawlayer": "ms:restart_alt",
    "masknext": "ms:brightness_high",
    "maskprev": "ms:brightness_low",
    "singlelayer": "ms:filter_1",
    "models3d": "ms:view_in_ar",
    "hudtrack": "ms:track_changes",
    "huddelta": "ms:change_history",
    "violations": "ms:report",
    "underobjects": "ms:info",
    "deltaorigin": "ms:location_searching",
    "absorigin": "ms:home_pin",
    # --- grids and snapping ---
    "hotspot": "ms:adjust",
    "snapoptions": "ms:tune",
    "grideditor": "ms:grid_on",
    "globalgrid": "ms:grid_goldenratio",
    "visiblegrid": "ms:grid_off",
    "elecgrid": "ms:electrical_services",
    # --- selection ---
    "similar": "ms:category",
    "clearfilter": "ms:filter_alt_off",
    "crosssel": "ms:sync_alt",
    "crossrepos": "ms:open_with",
    "selboard": "ms:select",
    "selmemory": "ms:bookmarks",
    "rubberstamp": "ms:approval",
    "edittext": "Rename",                 # text field with an I-beam cursor
    "annotate": "ms:format_list_numbered",
    "simulate": "ms:play_circle",
    # --- routing ---
    "bspcroute": "ms:backspace",
    "gloss": "ms:auto_fix_high",
    # --- aligning ---
    "alignleft": "ms:align_horizontal_left",
    "alignright": "ms:align_horizontal_right",
    "aligntop": "ms:vertical_align_top",
    "alignbottom": "ms:vertical_align_bottom",
    "spaceh": "ms:horizontal_distribute",
    "spacev": "ms:vertical_distribute",
    "aligngrid": "ms:grid_guides",
    "rulealignleft": "Align Left",
    "rulealignright": "Align Right",
    "rulealigntop": "Align Top",
    "rulealignbottom": "Align Bottom",
    "nudgeleft": "ms:keyboard_arrow_left",
    "nudgeright": "ms:keyboard_arrow_right",
    "nudgeup": "ms:keyboard_arrow_up",
    "nudgedown": "ms:keyboard_arrow_down",
    # --- pop-up menus ---
    "menualign": "ms:format_align_center",
    "menutoolbars": "ms:toolbar",
    "menugrid": "ms:grid_3x3",
    "menucompplace": "ms:dashboard_customize",
    "menujump": "ms:jump_to_element",
    "menupanels": "ms:view_sidebar",
    "menuconn": "ms:cable",
    "menuoptions": "Settings",
    "menuselect": "ms:ads_click",
    "menufilter": "ms:filter_alt",
    "menuzoom": "ms:zoom_in_map",
    "menuplace": "ms:add_box",
}

# Same action, same glyph as another set (byte-identical copies).
BORROW = {
    "zoomfit.png": "kicad",        # Ctrl+PgDn: fit all objects
    "center.png": "kicad",         # Home: centre the view on the cursor
    "refresh.png": "kicad",        # End: redraw
    "units.png": "kicad",          # Q: toggle mm / mil
    "measure.png": "kicad",        # Ctrl+M: measure distance
    "flip.png": "kicad",           # Ctrl+F: flip board
    "route.png": "kicad",          # Ctrl+W: interactive routing
    "autoroute.png": "kicad",      # Shift+A: ActiveRoute
    "delfulltrack.png": "kicad",   # Ctrl+Del: delete routing
    "expandconn.png": "kicad",     # Ctrl+H: select connected copper
    "pastespecial.png": "kicad",   # Alt+Ins: paste on current layer
    "viewer3d.png": "kicad",       # 3: 3D layout mode
    "localorigin.png": "kicad",    # Ctrl+End: relative origin
    "navback.png": "kicad",        # Alt+Left: previous document
    "navforward.png": "kicad",     # Alt+Right: next document
    "gridnext.png": "kicad",       # G: next snap grid
    "gridprev.png": "kicad",       # Shift+G: previous snap grid
    "findreplace.png": "kicad",    # Ctrl+H (schematic): find and replace
    "wire.png": "kicad",           # Ctrl+W (schematic): place wire
    "rotccw.png": "kicad",         # Space: rotate counterclockwise
    "rotcw.png": "kicad",          # Shift+Space: rotate clockwise
    "move.png": "kicad",           # M: Move menu
    "unselectall.png": "kicad",    # X: DeSelect menu
    "routesel.png": "kicad",       # U: Route menu
    "nexttab.png": "eclipse",      # Ctrl+Tab: next document
    "prevtab.png": "eclipse",      # Ctrl+Shift+Tab: previous document
    "properties.png": "cadcraft",  # F11: Properties panel
}

# altium.com's favicon is the Altium logo. Google's favicon service serves it.
ALTIUM_ICON_URL = "https://www.google.com/s2/favicons?domain=altium.com&sz=256"
ALTIUM_DARK_LUMA = 128


def _altium_mark(dest: Path, px: int = 32) -> None:
    """The Altium logo as a px*px 1-bit trace: fitted into the square, pixels at
    luma 128 or darker lit. Drawn at the keycap size so the generator copies it
    1:1."""
    req = urllib.request.Request(ALTIUM_ICON_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    src = white.convert("L")
    scale = px / max(src.size)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.LANCZOS)
    square = Image.new("L", (px, px), 255)
    square.paste(fitted, ((px - fitted.width) // 2, (px - fitted.height) // 2))
    a = square.point(lambda v: 255 if v <= ALTIUM_DARK_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    mark = out / "altium.png"
    if mark.exists():
        print("  altium.png  <- committed asset (left as-is)")
    else:
        _altium_mark(mark)
        print("  altium.png  <- traced from the altium.com favicon")
    print(f"Wrote {n + 1} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
