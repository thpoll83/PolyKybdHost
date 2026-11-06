#!/usr/bin/env python3
"""Fetch + render the Autodesk AutoCAD shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) for the `ms:` entries. The drafting toggles (F3 to F12, the
Properties, Tool Palettes and Command Line panels, copy with base point, paste
as block, ...) are byte-identical copies of the CADCraft set's icons, so one
action has one glyph in both CAD sets.

The ESC mark is drawn here, because the AutoCAD logo is an Autodesk trademark:
a rounded tile with the letter A knocked out and the drawing crosshair (with
its pick box) in the lower right corner. White on transparent, so the binding
renders it with `program_icon_mode: alpha`. The file is guarded: a committed
autocad.png is left as it is.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/autocad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

FLUENT = {
    # --- application and files ---
    "closedwg": "Dismiss",
    "closeall": "Dismiss Square Multiple",
    "macros": "ms:play_circle",
    "vba": "Code",
    "nexttab": "Arrow Next",
    "prevtab": "Arrow Previous",
    "firsttab": "ms:first_page",
    "lasttab": "ms:last_page",
    "starttab": "Home",
    "nextlayout": "Document Arrow Right",
    "prevlayout": "Document Arrow Left",
    "docslayouts": "ms:grid_view",
    "export": "Arrow Export Up",
    "newproject": "Folder Add",
    "openproject": "Folder Open",
    "projectmgr": "ms:account_tree",
    "pagesetup": "Document Settings",
    "qnew": "Tab Add",
    "hyperlink": "Link",
    "spell": "ms:spellcheck",
    # --- panels and palettes ---
    "cleanscreen": "Full Screen Maximize",
    "designcenter": "Library",
    "sheetset": "ms:library_books",
    "dbconnect": "Database",
    "markup": "ms:rate_review",
    "hidepalettes": "Eye Off",
    "qprops": "ms:picture_in_picture",
    "blocks": "ms:widgets",
    "xref": "Attach",
    "layers": "Layer",
    "materials": "ms:texture",
    "statusbar": "Panel Bottom",
    # --- drawing and selection ---
    "cycleviewport": "ms:view_quilt",
    "selcycle": "ms:flip_to_front",
    "selprev": "ms:settings_backup_restore",
    "quickselect": "Filter",
    "group": "ms:join",
    "ungroup": "ms:join_left",
    "regen": "Arrow Clockwise",
    "regenall": "ms:sync",
    "cancel": "Dismiss Circle",
    "coords": "Location",
    "infer": "ms:lock",
    "dynucs": "ms:3d_rotation",
    "osnap3d": "ms:view_in_ar",
    "implied": "ms:vertical_align_top",
    # --- subobject selection filters (Shift+F1..F5) ---
    "subnone": "ms:filter_alt_off",
    "subvertex": "ms:scatter_plot",
    "subedge": "ms:diagonal_line",
    "subface": "ms:square",
    "subhistory": "ms:manage_history",
}

# Same action, same glyph as the CADCraft set (byte-identical copies).
BORROW = {
    "history.png": "cadcraft",
    "osnap.png": "cadcraft",
    "isoplane.png": "cadcraft",
    "grid.png": "cadcraft",
    "ortho.png": "cadcraft",
    "snap.png": "cadcraft",
    "polar.png": "cadcraft",
    "otrack.png": "cadcraft",
    "dynmode.png": "cadcraft",
    "properties.png": "cadcraft",
    "toolsets.png": "cadcraft",
    "cmdline.png": "cadcraft",
    "pickstyle.png": "cadcraft",
    "copybase.png": "cadcraft",
    "pasteblock.png": "cadcraft",
    "quickcalc.png": "cadcraft",
    "repeatcmd.png": "cadcraft",
    "prefs.png": "cadcraft",
    "print.png": "cadcraft",
}

SIZE = 256
SS = 4
WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)


def draw_mark(path: Path) -> None:
    """Rounded tile, letter A knocked out, crosshair with pick box at lower right."""
    u = SIZE * SS
    pad = int(u * 0.055)
    img = Image.new("RGBA", (u, u), CLEAR)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([pad, pad, u - pad, u - pad], radius=int(u * 0.16), fill=WHITE)

    f = ImageFont.truetype(BOLD, int(u * 0.56))
    box = d.textbbox((0, 0), "A", font=f)
    cx = int(u * 0.36) - (box[2] + box[0]) // 2
    cy = int(u * 0.40) - (box[3] + box[1]) // 2
    d.text((cx, cy), "A", font=f, fill=CLEAR)

    # The drawing crosshair: two lines and the pick box at their crossing.
    x, y = int(u * 0.70), int(u * 0.70)
    arm, w, pb = int(u * 0.22), int(u * 0.05), int(u * 0.085)
    d.rectangle([x - arm, y - w // 2, x + arm, y + w // 2], fill=CLEAR)
    d.rectangle([x - w // 2, y - arm, x + w // 2, y + arm], fill=CLEAR)
    d.rectangle([x - pb, y - pb, x + pb, y + pb], fill=CLEAR)
    d.rectangle([x - pb + w, y - pb + w, x + pb - w, y + pb - w], fill=WHITE)
    img.resize((SIZE, SIZE), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    mark = out / "autocad.png"
    if mark.exists():
        print("  autocad.png  <- committed asset (left as-is)")
    else:
        draw_mark(mark)
        print("  autocad.png  <- drawn program mark")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
