#!/usr/bin/env python3
"""Fetch + render the Adobe Photoshop shortcut icons (reproducible).

Stock glyphs are Microsoft Fluent UI System Icons (MIT) — license-clean (host is
GPL-2.0; Adobe's real tool icons are proprietary and are NOT used). Rendered to
96x96 RGBA PNG; the generator's `luma` mode keeps the linework at 1-bit.

Photoshop's signature *tools* (marquee, lasso, magic wand, clone stamp, healing
brush, dodge/burn, path-selection, swap/default colours, quick mask) have no good
Fluent equivalent, so they are **drawn here** as simple white-on-transparent
glyphs (alpha is the shape) and the matching binding sets `mode: alpha`.

The program icon (ESC) is a generic, license-clean rounded-square "Ps" monogram
(NOT Adobe's logo styling/colours). All hand-editable / drawn assets are guarded
by an exists-check so a committed edit survives a re-run.

    pip install cairosvg
    python polyhost/res/overlay_sources/photoshop/fetch_icons.py
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RENDER_PX = 96
MS = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/{}"

# --- stock Fluent glyphs (folder name = human name; file = ic_fluent_<snake>_24_regular.svg) ---
MS_ICONS = {
    # --- file (Ctrl) ---
    "new": "Document Add/SVG/ic_fluent_document_add_24_regular.svg",
    "open": "Folder Open/SVG/ic_fluent_folder_open_24_regular.svg",
    "save": "Save/SVG/ic_fluent_save_24_regular.svg",
    "saveas": "Save Edit/SVG/ic_fluent_save_edit_24_regular.svg",
    "close": "Document Dismiss/SVG/ic_fluent_document_dismiss_24_regular.svg",
    "print": "Print/SVG/ic_fluent_print_24_regular.svg",
    # --- edit (Ctrl) ---
    "copy": "Copy/SVG/ic_fluent_copy_24_regular.svg",
    "cut": "Cut/SVG/ic_fluent_cut_24_regular.svg",
    "paste": "Clipboard Paste/SVG/ic_fluent_clipboard_paste_24_regular.svg",
    "undo": "Arrow Undo/SVG/ic_fluent_arrow_undo_24_regular.svg",
    "selectall": "Select All On/SVG/ic_fluent_select_all_on_24_regular.svg",
    "deselect": "Select All Off/SVG/ic_fluent_select_all_off_24_regular.svg",
    "freetransform": "Resize/SVG/ic_fluent_resize_24_regular.svg",
    # --- layer (Ctrl) ---
    "duplayer": "Layer/SVG/ic_fluent_layer_24_regular.svg",
    "newlayer": "Add Square/SVG/ic_fluent_add_square_24_regular.svg",
    "mergedown": "Layer Diagonal/SVG/ic_fluent_layer_diagonal_24_regular.svg",
    "group": "Group/SVG/ic_fluent_group_24_regular.svg",
    # --- image adjustments (Ctrl) ---
    "levels": "Data Histogram/SVG/ic_fluent_data_histogram_24_regular.svg",
    "curves": "Data Line/SVG/ic_fluent_data_line_24_regular.svg",
    "huesat": "Color/SVG/ic_fluent_color_24_regular.svg",
    "colorbalance": "Color Fill/SVG/ic_fluent_color_fill_24_regular.svg",
    "invert": "Color Background/SVG/ic_fluent_color_background_24_regular.svg",
    "desaturate": "Color Line/SVG/ic_fluent_color_line_24_regular.svg",
    # --- view (Ctrl) ---
    "rulers": "Ruler/SVG/ic_fluent_ruler_24_regular.svg",
    "extras": "Eye Off/SVG/ic_fluent_eye_off_24_regular.svg",
    "fitscreen": "Full Screen Maximize/SVG/ic_fluent_full_screen_maximize_24_regular.svg",
    "zoomin": "Zoom In/SVG/ic_fluent_zoom_in_24_regular.svg",
    "zoomout": "Zoom Out/SVG/ic_fluent_zoom_out_24_regular.svg",
    # --- select (Ctrl+Shift) ---
    "invertsel": "Arrow Swap/SVG/ic_fluent_arrow_swap_24_regular.svg",
    "copymerged": "Copy Select/SVG/ic_fluent_copy_select_24_regular.svg",
    "redo": "Arrow Redo/SVG/ic_fluent_arrow_redo_24_regular.svg",
    # --- tools that DO have a clean Fluent glyph (no-mod A channel) ---
    "move": "Arrow Move/SVG/ic_fluent_arrow_move_24_regular.svg",
    "crop": "Crop/SVG/ic_fluent_crop_24_regular.svg",
    "brush": "Paint Brush/SVG/ic_fluent_paint_brush_24_regular.svg",
    "eraser": "Eraser/SVG/ic_fluent_eraser_24_regular.svg",
    "type": "Text T/SVG/ic_fluent_text_t_24_regular.svg",
    "eyedropper": "Eyedropper/SVG/ic_fluent_eyedropper_24_regular.svg",
    "zoom": "Zoom In/SVG/ic_fluent_zoom_in_24_regular.svg",
    "hand": "Hand Right/SVG/ic_fluent_hand_right_24_regular.svg",
    "pen": "Pen/SVG/ic_fluent_pen_24_regular.svg",
    "shape": "Shapes/SVG/ic_fluent_shapes_24_regular.svg",
    "historybrush": "History/SVG/ic_fluent_history_24_regular.svg",
    "fill": "Paint Bucket/SVG/ic_fluent_paint_bucket_24_regular.svg",
    # --- added (coverage audit 2026-06) ---
    "screenmode": "Full Screen Maximize/SVG/ic_fluent_full_screen_maximize_24_regular.svg",
    "stepback": "History/SVG/ic_fluent_history_24_regular.svg",
    "zoom1to1": "Ratio One To One/SVG/ic_fluent_ratio_one_to_one_24_regular.svg",
    "feather": "Blur/SVG/ic_fluent_blur_24_regular.svg",
}

SS = 4               # supersample factor for drawn glyphs
WHITE = (255, 255, 255, 255)


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _canvas():
    u = RENDER_PX * SS
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), u


def _save(img: Image.Image, path: Path) -> None:
    img.resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


# --------------------------------------------------------------------------- #
# Drawn Photoshop tool glyphs (white on transparent -> mode: alpha)           #
# --------------------------------------------------------------------------- #
def _draw_marquee(path: Path) -> None:
    """Rectangular marquee: a dashed rectangle."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    x0, y0, x1, y1 = 0.16 * u, 0.24 * u, 0.84 * u, 0.76 * u
    dash = u * 0.09
    x = x0
    while x < x1:                                          # top + bottom dashes
        d.line([(x, y0), (min(x + dash, x1), y0)], fill=WHITE, width=w)
        d.line([(x, y1), (min(x + dash, x1), y1)], fill=WHITE, width=w)
        x += 2 * dash
    y = y0
    while y < y1:                                          # left + right dashes
        d.line([(x0, y), (x0, min(y + dash, y1))], fill=WHITE, width=w)
        d.line([(x1, y), (x1, min(y + dash, y1))], fill=WHITE, width=w)
        y += 2 * dash
    _save(img, path)


def _draw_lasso(path: Path) -> None:
    """Lasso: a freeform loop with a small tail/knot at the bottom."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    # loop (open at the bottom)
    d.arc([0.18 * u, 0.14 * u, 0.82 * u, 0.74 * u], start=70, end=470, fill=WHITE, width=w)
    # tail dropping from the bottom of the loop
    d.line([(0.50 * u, 0.72 * u), (0.44 * u, 0.90 * u)], fill=WHITE, width=w)
    d.ellipse([0.40 * u, 0.86 * u, 0.50 * u, 0.96 * u], outline=WHITE, width=w)
    _save(img, path)


def _draw_magicwand(path: Path) -> None:
    """Magic wand: a diagonal stick with a sparkle/star at the tip."""
    img, d, u = _canvas()
    w = int(u * 0.06)
    d.line([(0.22 * u, 0.82 * u), (0.62 * u, 0.42 * u)], fill=WHITE, width=w)   # wand
    # sparkle (4-point star) at the tip
    cx, cy, r = 0.70 * u, 0.32 * u, 0.16 * u
    d.line([(cx - r, cy), (cx + r, cy)], fill=WHITE, width=w)
    d.line([(cx, cy - r), (cx, cy + r)], fill=WHITE, width=w)
    s = r * 0.55
    d.line([(cx - s, cy - s), (cx + s, cy + s)], fill=WHITE, width=int(w * 0.7))
    d.line([(cx - s, cy + s), (cx + s, cy - s)], fill=WHITE, width=int(w * 0.7))
    _save(img, path)


def _draw_clonestamp(path: Path) -> None:
    """Clone stamp: a rubber-stamp silhouette (handle, neck, wide base)."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    d.rectangle([0.42 * u, 0.16 * u, 0.58 * u, 0.30 * u], outline=WHITE, width=w)   # handle
    d.polygon([(0.34 * u, 0.30 * u), (0.66 * u, 0.30 * u),
               (0.58 * u, 0.62 * u), (0.42 * u, 0.62 * u)], outline=WHITE, width=w)  # neck
    d.rectangle([0.24 * u, 0.62 * u, 0.76 * u, 0.74 * u], outline=WHITE, width=w)   # base
    d.line([(0.18 * u, 0.84 * u), (0.82 * u, 0.84 * u)], fill=WHITE, width=w)       # surface
    _save(img, path)


def _draw_healing(path: Path) -> None:
    """Healing brush: a band-aid / plaster (rounded rect + central pad dots)."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    # rotated plaster: draw on a sub-image then rotate
    sub = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sub)
    ds.rounded_rectangle([0.10 * u, 0.36 * u, 0.90 * u, 0.64 * u],
                         radius=0.14 * u, outline=WHITE, width=w)
    ds.line([(0.38 * u, 0.36 * u), (0.38 * u, 0.64 * u)], fill=WHITE, width=int(w * 0.8))
    ds.line([(0.62 * u, 0.36 * u), (0.62 * u, 0.64 * u)], fill=WHITE, width=int(w * 0.8))
    for dx in (-0.05, 0.05):
        for dy in (-0.05, 0.05):
            ds.ellipse([(0.50 + dx) * u - w * 0.8, (0.50 + dy) * u - w * 0.8,
                        (0.50 + dx) * u + w * 0.8, (0.50 + dy) * u + w * 0.8], fill=WHITE)
    sub = sub.rotate(-40, resample=Image.BICUBIC, center=(u / 2, u / 2))
    _save(sub, path)


def _draw_dodgeburn(path: Path) -> None:
    """Dodge/burn: a lollipop dodge tool — circle on a stick (the classic icon)."""
    img, d, u = _canvas()
    w = int(u * 0.06)
    d.ellipse([0.46 * u, 0.16 * u, 0.74 * u, 0.44 * u], outline=WHITE, width=w)   # dodge head
    d.line([(0.50 * u, 0.42 * u), (0.26 * u, 0.82 * u)], fill=WHITE, width=w)     # stick
    _save(img, path)


def _draw_pathselect(path: Path) -> None:
    """Path selection: a solid arrow cursor pointing up-left (the black arrow)."""
    img, d, u = _canvas()
    d.polygon([(0.28 * u, 0.18 * u), (0.28 * u, 0.74 * u), (0.42 * u, 0.60 * u),
               (0.52 * u, 0.82 * u), (0.60 * u, 0.78 * u), (0.50 * u, 0.56 * u),
               (0.70 * u, 0.56 * u)], fill=WHITE)
    _save(img, path)


def _draw_swapcolors(path: Path) -> None:
    """Swap FG/BG: two overlapping squares with a curved double-arrow."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    d.rectangle([0.20 * u, 0.20 * u, 0.50 * u, 0.50 * u], outline=WHITE, width=w)  # front
    d.rectangle([0.46 * u, 0.46 * u, 0.76 * u, 0.76 * u], outline=WHITE, width=w)  # back
    # curved swap arrow (top-right)
    d.arc([0.52 * u, 0.16 * u, 0.84 * u, 0.48 * u], start=270, end=90, fill=WHITE, width=w)
    d.line([(0.84 * u, 0.30 * u), (0.80 * u, 0.20 * u)], fill=WHITE, width=w)
    d.line([(0.84 * u, 0.30 * u), (0.74 * u, 0.26 * u)], fill=WHITE, width=w)
    _save(img, path)


def _draw_defaultcolors(path: Path) -> None:
    """Default colours: one filled (black=outline) square behind a hollow one."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    d.rectangle([0.42 * u, 0.42 * u, 0.74 * u, 0.74 * u], outline=WHITE, width=w)   # back (white)
    d.rectangle([0.22 * u, 0.22 * u, 0.54 * u, 0.54 * u], fill=WHITE)               # front (black=lit)
    _save(img, path)


def _draw_brushdec(path: Path) -> None:
    """Decrease brush size ([): a small filled dot."""
    img, d, u = _canvas()
    d.ellipse([0.42 * u, 0.42 * u, 0.58 * u, 0.58 * u], fill=WHITE)
    _save(img, path)


def _draw_brushinc(path: Path) -> None:
    """Increase brush size (]): a large filled dot."""
    img, d, u = _canvas()
    d.ellipse([0.26 * u, 0.26 * u, 0.74 * u, 0.74 * u], fill=WHITE)
    _save(img, path)


def _draw_hardnessdec(path: Path) -> None:
    """Decrease brush hardness (Shift+[): a small core with a soft dashed ring."""
    img, d, u = _canvas()
    w = int(u * 0.04)
    d.ellipse([0.41 * u, 0.41 * u, 0.59 * u, 0.59 * u], fill=WHITE)
    cx, cy, r = 0.5 * u, 0.5 * u, 0.30 * u
    for a in range(0, 360, 30):                       # dashed = "soft" edge
        d.arc([cx - r, cy - r, cx + r, cy + r], a, a + 15, fill=WHITE, width=w)
    _save(img, path)


def _draw_hardnessinc(path: Path) -> None:
    """Increase brush hardness (Shift+]): a core with a solid (hard) ring."""
    img, d, u = _canvas()
    d.ellipse([0.41 * u, 0.41 * u, 0.59 * u, 0.59 * u], fill=WHITE)
    d.ellipse([0.22 * u, 0.22 * u, 0.78 * u, 0.78 * u], outline=WHITE, width=int(u * 0.05))
    _save(img, path)


def _draw_fillfg(path: Path) -> None:
    """Fill with foreground colour (Alt+Backspace): a solid filled square."""
    img, d, u = _canvas()
    d.rectangle([0.24 * u, 0.24 * u, 0.76 * u, 0.76 * u], fill=WHITE)
    _save(img, path)


def _draw_fillbg(path: Path) -> None:
    """Fill with background colour (Ctrl+Backspace): a framed square with a solid
    centre — distinct from the solid FG-fill square."""
    img, d, u = _canvas()
    d.rectangle([0.20 * u, 0.20 * u, 0.80 * u, 0.80 * u], outline=WHITE, width=int(u * 0.07))
    d.rectangle([0.38 * u, 0.38 * u, 0.62 * u, 0.62 * u], fill=WHITE)
    _save(img, path)


def _draw_gradient(path: Path) -> None:
    """Gradient tool (G): a swatch split on the diagonal into a lit and an unlit
    half — the universally-recognised gradient glyph, and visually distinct from
    the Paint-Bucket reused for the Fill command (Shift+F5)."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    x0, y0, x1, y1 = 0.16 * u, 0.20 * u, 0.84 * u, 0.80 * u
    # filled lower-left triangle = the dark→light diagonal of a gradient swatch
    d.polygon([(x0, y0), (x0, y1), (x1, y1)], fill=WHITE)
    # frame so the empty (light) upper-right half still reads as part of the swatch
    d.rectangle([x0, y0, x1, y1], outline=WHITE, width=w)
    _save(img, path)


def _draw_quickmask(path: Path) -> None:
    """Quick mask: a circle (selection) inside a rectangle (canvas), with a few
    clean diagonal hatch lines across the lower-right (the rubylith mask)."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    x0, y0, x1, y1 = 0.16 * u, 0.20 * u, 0.84 * u, 0.80 * u
    d.rectangle([x0, y0, x1, y1], outline=WHITE, width=w)
    d.ellipse([0.36 * u, 0.34 * u, 0.64 * u, 0.62 * u], outline=WHITE, width=w)
    # clean parallel diagonals clipped to the rectangle interior (lower-right band)
    hatch = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    dh = ImageDraw.Draw(hatch)
    for c in (0.30, 0.50, 0.70, 0.90):                          # x-intercepts along the top
        dh.line([(c * u, y0), (c * u + (y1 - y0), y1)], fill=WHITE, width=int(w * 0.55))
    mask = Image.new("L", (u, u), 0)
    ImageDraw.Draw(mask).rectangle([x0 + w, 0.50 * u, x1 - w, y1 - w], fill=255)
    img.paste(hatch, (0, 0), Image.composite(hatch.split()[3], Image.new("L", (u, u), 0), mask))
    _save(img, path)


def _draw_ps_logo(path: Path) -> None:
    """Generic, license-clean program mark: a rounded square outline with the
    letters 'Ps' inside (white on transparent -> program_icon_mode: alpha). This
    is deliberately NOT Adobe's logo styling/colours — just a plain monogram."""
    u = RENDER_PX * SS
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0.12 * u, 0.12 * u, 0.88 * u, 0.88 * u],
                        radius=0.16 * u, outline=WHITE, width=int(u * 0.05))
    font = None
    for cand in ("DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(cand, int(u * 0.46))
            break
        except OSError:
            continue
    if font:
        bb = d.textbbox((0, 0), "Ps", font=font)
        cx, cy = 0.50 * u, 0.50 * u
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
               "Ps", font=font, fill=WHITE)
    _save(img, path)


_DRAWN = {
    "marquee": _draw_marquee,
    "lasso": _draw_lasso,
    "magicwand": _draw_magicwand,
    "clonestamp": _draw_clonestamp,
    "healing": _draw_healing,
    "dodgeburn": _draw_dodgeburn,
    "pathselect": _draw_pathselect,
    "swapcolors": _draw_swapcolors,
    "defaultcolors": _draw_defaultcolors,
    "quickmask": _draw_quickmask,
    "gradient": _draw_gradient,
    "brushdec": _draw_brushdec,
    "brushinc": _draw_brushinc,
    "hardnessdec": _draw_hardnessdec,
    "hardnessinc": _draw_hardnessinc,
    "fillfg": _draw_fillfg,
    "fillbg": _draw_fillbg,
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    for fname, asset in MS_ICONS.items():
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{asset.split('/')[0]}")

    # drawn glyphs (guarded: a committed hand-edit survives a re-run)
    for fname, fn in _DRAWN.items():
        p = out / f"{fname}.png"
        if p.exists():
            print(f"  {fname}.png  <- committed asset (left as-is)")
        else:
            fn(p)
            print(f"  {fname}.png  <- custom (drawn)")

    # program mark (guarded)
    if (out / "photoshop.png").exists():
        print("  photoshop.png  <- committed asset (left as-is)")
    else:
        _draw_ps_logo(out / "photoshop.png")
        print("  photoshop.png  <- custom (drawn 'Ps' monogram)")

    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
