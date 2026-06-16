#!/usr/bin/env python3
"""Fetch + render the Adobe Illustrator shortcut icons (reproducible).

Most glyphs are Microsoft Fluent UI System Icons (MIT) — license-clean (host is
GPL-3.0-or-later; MIT is GPL-compatible). Adobe's own icons are proprietary and are NOT
used. A handful of vector-editing tools have no clean Fluent glyph (pen nib,
scissors, swap/default fill-stroke, the width tool) — those are drawn here as
simple white-on-transparent glyphs and consumed with `mode: alpha`.

Everything renders to 96x96 RGBA PNG; the generator's `luma` mode keeps Fluent
linework at 1-bit, `alpha` mode keeps a drawn glyph's shape. The program icon
(ESC) is a generic, license-clean rounded-square "Ai" monogram (NOT Adobe's
logo) — drop a real mark as icons/illustrator.png to override.

    pip install cairosvg
    python polyhost/res/overlay_sources/illustrator/fetch_icons.py
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

# All probed (raw fetch, 404-checked) before relying on them. See SOURCES.md.
MS_ICONS = {
    # --- tools (no-mod) ---
    "select": "Cursor/SVG/ic_fluent_cursor_24_regular.svg",                  # V Selection
    "directselect": "Select Object/SVG/ic_fluent_select_object_24_regular.svg",  # A Direct selection
    "magicwand": "Wand/SVG/ic_fluent_wand_24_regular.svg",                   # Y Magic wand
    "lasso": "Lasso/SVG/ic_fluent_lasso_24_regular.svg",                     # Q Lasso
    "type": "Text T/SVG/ic_fluent_text_t_24_regular.svg",                    # T Type
    "rectangle": "Rectangle Landscape/SVG/ic_fluent_rectangle_landscape_24_regular.svg",  # M Rectangle
    "ellipse": "Oval/SVG/ic_fluent_oval_24_regular.svg",                     # L Ellipse
    "paintbrush": "Paint Brush/SVG/ic_fluent_paint_brush_24_regular.svg",    # B Paintbrush
    "pencil": "Edit/SVG/ic_fluent_edit_24_regular.svg",                      # N Pencil
    "rotate": "Arrow Rotate Clockwise/SVG/ic_fluent_arrow_rotate_clockwise_24_regular.svg",  # R Rotate
    "reflect": "Flip Horizontal/SVG/ic_fluent_flip_horizontal_24_regular.svg",  # O Reflect
    "scale": "Resize/SVG/ic_fluent_resize_24_regular.svg",                   # S Scale
    "mesh": "Grid/SVG/ic_fluent_grid_24_regular.svg",                        # U Mesh
    "gradient": "Color Line/SVG/ic_fluent_color_line_24_regular.svg",        # G Gradient
    "eyedropper": "Eyedropper/SVG/ic_fluent_eyedropper_24_regular.svg",      # I Eyedropper
    "livepaint": "Paint Bucket/SVG/ic_fluent_paint_bucket_24_regular.svg",   # K Live paint bucket
    "zoom": "Zoom In/SVG/ic_fluent_zoom_in_24_regular.svg",                  # Z Zoom
    "hand": "Hand Right/SVG/ic_fluent_hand_right_24_regular.svg",            # H Hand
    "eraser": "Eraser/SVG/ic_fluent_eraser_24_regular.svg",                  # E Eraser
    # --- file (Ctrl) ---
    "new": "Document Add/SVG/ic_fluent_document_add_24_regular.svg",
    "open": "Folder Open/SVG/ic_fluent_folder_open_24_regular.svg",
    "save": "Save/SVG/ic_fluent_save_24_regular.svg",
    "saveas": "Save Edit/SVG/ic_fluent_save_edit_24_regular.svg",
    "print": "Print/SVG/ic_fluent_print_24_regular.svg",
    "place": "Image Add/SVG/ic_fluent_image_add_24_regular.svg",
    # --- edit (Ctrl) ---
    "undo": "Arrow Undo/SVG/ic_fluent_arrow_undo_24_regular.svg",
    "copy": "Copy/SVG/ic_fluent_copy_24_regular.svg",
    "cut": "Cut/SVG/ic_fluent_cut_24_regular.svg",
    "paste": "Clipboard Paste/SVG/ic_fluent_clipboard_paste_24_regular.svg",
    "selectall": "Select All On/SVG/ic_fluent_select_all_on_24_regular.svg",
    "transformagain": "Arrow Repeat All/SVG/ic_fluent_arrow_repeat_all_24_regular.svg",
    # --- object (Ctrl / Ctrl+Shift) ---
    "group": "Group/SVG/ic_fluent_group_24_regular.svg",
    "ungroup": "Group Dismiss/SVG/ic_fluent_group_dismiss_24_regular.svg",
    "lock": "Lock Closed/SVG/ic_fluent_lock_closed_24_regular.svg",
    "clipmask": "Crop/SVG/ic_fluent_crop_24_regular.svg",
    "compound": "Shape Subtract/SVG/ic_fluent_shape_subtract_24_regular.svg",
    "forward": "Arrow Up/SVG/ic_fluent_arrow_up_24_regular.svg",
    "backward": "Arrow Down/SVG/ic_fluent_arrow_down_24_regular.svg",
    "tofront": "Position To Front/SVG/ic_fluent_position_to_front_24_regular.svg",
    "toback": "Position To Back/SVG/ic_fluent_position_to_back_24_regular.svg",
    "outlines": "Text Effects/SVG/ic_fluent_text_effects_24_regular.svg",
    # --- view (Ctrl) ---
    "zoomin": "Zoom In/SVG/ic_fluent_zoom_in_24_regular.svg",
    "zoomout": "Zoom Out/SVG/ic_fluent_zoom_out_24_regular.svg",
    # --- added (coverage audit 2026-06) ---
    "join": "Link/SVG/ic_fluent_link_24_regular.svg",                   # Ctrl+J Join
    "rulers": "Ruler/SVG/ic_fluent_ruler_24_regular.svg",              # Ctrl+R Rulers
    "hideedges": "Eye Off/SVG/ic_fluent_eye_off_24_regular.svg",       # Ctrl+H Hide edges
    "newlayer": "Add Square/SVG/ic_fluent_add_square_24_regular.svg",  # Ctrl+L New layer
    "applyeffect": "Sparkle/SVG/ic_fluent_sparkle_24_regular.svg",     # Ctrl+Shift+E Apply last effect
    "prefs": "Settings/SVG/ic_fluent_settings_24_regular.svg",         # Ctrl+K Preferences
    "showall": "Eye/SVG/ic_fluent_eye_24_regular.svg",                 # Ctrl+Alt+3 Show all
}


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _new() -> tuple[int, Image.Image, ImageDraw.ImageDraw]:
    """Supersampled transparent canvas + draw handle (4x). Returns (u, img, draw)."""
    ss = 4
    u = RENDER_PX * ss
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    return u, img, ImageDraw.Draw(img)


def _save(img: Image.Image, path: Path) -> None:
    img.resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


WHITE = (255, 255, 255, 255)


def _draw_pen(path: Path) -> None:
    """Pen tool (P): the classic filled pen-nib — a tall blade pointing straight
    down with a round vent hole and a centre slit cut out of it. Drawn as a solid
    silhouette (reads far better at 1-bit than the old thin outline)."""
    u = RENDER_PX * 4
    m = Image.new("L", (u, u), 0)
    dm = ImageDraw.Draw(m)
    # nib body: wide shoulders at the top, tapering to a sharp point at the bottom
    dm.polygon([(0.30 * u, 0.16 * u), (0.70 * u, 0.16 * u),
                (0.60 * u, 0.60 * u), (0.50 * u, 0.88 * u), (0.40 * u, 0.60 * u)],
               fill=255)
    # round vent hole near the top-centre (cut out)
    dm.ellipse([0.425 * u, 0.25 * u, 0.575 * u, 0.40 * u], fill=0)
    # centre slit from the vent down toward the tip (cut out)
    dm.line([(0.50 * u, 0.40 * u), (0.50 * u, 0.74 * u)], fill=0, width=int(u * 0.05))
    arr = np.zeros((u, u, 4), np.uint8)
    arr[..., :3] = 255
    arr[..., 3] = np.asarray(m)
    _save(Image.fromarray(arr, "RGBA"), path)


def _draw_scissors(path: Path) -> None:
    """Scissors (C, Scissors tool): two finger-loops + crossed blades to a point."""
    u, img, d = _new()
    w = int(u * 0.045)
    # two loops on the left
    d.ellipse([0.14 * u, 0.20 * u, 0.34 * u, 0.40 * u], outline=WHITE, width=w)
    d.ellipse([0.14 * u, 0.58 * u, 0.34 * u, 0.78 * u], outline=WHITE, width=w)
    # blades crossing to a point on the right
    d.line([(0.30 * u, 0.30 * u), (0.82 * u, 0.62 * u)], fill=WHITE, width=w)
    d.line([(0.30 * u, 0.68 * u), (0.82 * u, 0.36 * u)], fill=WHITE, width=w)
    _save(img, path)


def _draw_width(path: Path) -> None:
    """Width tool (Shift+W): a horizontal stroke that swells in the middle,
    with up/down arrows showing the variable width handle."""
    u, img, d = _new()
    w = int(u * 0.05)
    # tapered lens shape (stroke that bulges)
    d.polygon([(0.14 * u, 0.50 * u), (0.50 * u, 0.30 * u),
               (0.86 * u, 0.50 * u), (0.50 * u, 0.70 * u)], outline=WHITE, width=w)
    # centre vertical handle with arrowheads
    d.line([(0.50 * u, 0.16 * u), (0.50 * u, 0.84 * u)], fill=WHITE, width=w)
    d.polygon([(0.50 * u, 0.12 * u), (0.44 * u, 0.24 * u), (0.56 * u, 0.24 * u)], fill=WHITE)
    d.polygon([(0.50 * u, 0.88 * u), (0.44 * u, 0.76 * u), (0.56 * u, 0.76 * u)], fill=WHITE)
    _save(img, path)


def _draw_swap(path: Path) -> None:
    """Swap fill/stroke (X): two small overlapping squares (a filled + a hollow)
    with a curved swap arrow between them."""
    u, img, d = _new()
    w = int(u * 0.05)
    # back square hollow (stroke)
    d.rectangle([0.46 * u, 0.16 * u, 0.78 * u, 0.48 * u], outline=WHITE, width=w)
    # front square filled (fill)
    d.rectangle([0.20 * u, 0.46 * u, 0.52 * u, 0.78 * u], fill=WHITE)
    # diagonal double-arrow swapping them
    d.line([(0.70 * u, 0.30 * u), (0.84 * u, 0.16 * u)], fill=WHITE, width=int(w * 0.8))
    d.line([(0.30 * u, 0.62 * u), (0.16 * u, 0.78 * u)], fill=WHITE, width=int(w * 0.8))
    _save(img, path)


def _draw_default(path: Path) -> None:
    """Default fill/stroke (D): the canonical white-fill + black-stroke pair —
    a solid square overlapping a hollow square (mini default-colours swatch)."""
    u, img, d = _new()
    w = int(u * 0.06)
    # hollow square (default stroke = black, shown as outline) back-right
    d.rectangle([0.44 * u, 0.18 * u, 0.80 * u, 0.54 * u], outline=WHITE, width=w)
    # solid square (default fill = white) front-left, with a hole so it reads as a swatch
    d.rectangle([0.20 * u, 0.46 * u, 0.56 * u, 0.82 * u], outline=WHITE, width=w)
    d.rectangle([0.30 * u, 0.56 * u, 0.46 * u, 0.72 * u], fill=WHITE)
    _save(img, path)


def _draw_line(path: Path) -> None:
    """Line segment tool (backslash): a diagonal stroke with end nodes."""
    u, img, d = _new()
    w = int(u * 0.055)
    d.line([(0.22 * u, 0.74 * u), (0.78 * u, 0.26 * u)], fill=WHITE, width=w)
    r = int(u * 0.06)
    for cx, cy in ((0.22 * u, 0.74 * u), (0.78 * u, 0.26 * u)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
    _save(img, path)


def _draw_ai_logo(path: Path) -> None:
    """Generic, license-clean program mark (NOT Adobe's logo): a rounded square
    with an 'Ai' monogram knocked out / stamped on. White-on-transparent ->
    program_icon_mode: alpha."""
    u, img, d = _new()
    # rounded square frame
    d.rounded_rectangle([0.12 * u, 0.12 * u, 0.88 * u, 0.88 * u],
                        radius=0.18 * u, outline=WHITE, width=int(u * 0.05))
    font = None
    for cand in ("DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(cand, int(u * 0.42))
            break
        except OSError:
            continue
    if font:
        txt = "Ai"
        bb = d.textbbox((0, 0), txt, font=font)
        cx, cy = 0.50 * u, 0.50 * u
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
               txt, font=font, fill=WHITE)
    _save(img, path)


def _draw_outline(path: Path) -> None:
    """Outline/Preview view (Ctrl+Y): a wireframe square with anchor handles."""
    u, img, d = _new()
    w = int(u * 0.05)
    d.rectangle([0.26 * u, 0.26 * u, 0.74 * u, 0.74 * u], outline=WHITE, width=w)
    r = int(u * 0.055)
    for cx, cy in [(0.26 * u, 0.26 * u), (0.74 * u, 0.26 * u),
                   (0.26 * u, 0.74 * u), (0.74 * u, 0.74 * u)]:
        d.rectangle([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
    _save(img, path)


def _draw_guides(path: Path) -> None:
    """Show/Hide guides (Ctrl+;): a dashed vertical + horizontal guide cross."""
    u, img, d = _new()
    w = int(u * 0.05)
    dash = int(u * 0.09)
    y = 0.12 * u
    while y < 0.88 * u:
        d.line([(0.5 * u, y), (0.5 * u, min(y + dash, 0.88 * u))], fill=WHITE, width=w)
        y += 2 * dash
    x = 0.12 * u
    while x < 0.88 * u:
        d.line([(x, 0.5 * u), (min(x + dash, 0.88 * u), 0.5 * u)], fill=WHITE, width=w)
        x += 2 * dash
    _save(img, path)


def _draw_smartguides(path: Path) -> None:
    """Smart guides (Ctrl+U): a dashed diagonal alignment line + node + a sparkle."""
    u, img, d = _new()
    w = int(u * 0.05)
    x0, y0, x1, y1 = 0.16 * u, 0.84 * u, 0.84 * u, 0.16 * u
    n = 7
    for i in range(0, n, 2):
        ax, ay = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
        bx, by = x0 + (x1 - x0) * (i + 1) / n, y0 + (y1 - y0) * (i + 1) / n
        d.line([(ax, ay), (bx, by)], fill=WHITE, width=w)
    d.ellipse([0.43 * u, 0.43 * u, 0.57 * u, 0.57 * u], fill=WHITE)
    sw = int(w * 0.7)
    d.line([(0.74 * u, 0.16 * u), (0.74 * u, 0.30 * u)], fill=WHITE, width=sw)
    d.line([(0.67 * u, 0.23 * u), (0.81 * u, 0.23 * u)], fill=WHITE, width=sw)
    _save(img, path)


def _draw_average(path: Path) -> None:
    """Average anchor points (Ctrl+Alt+J): outer points converging on a centre."""
    u, img, d = _new()
    w = int(u * 0.05)
    r = int(u * 0.06)
    pts = [(0.22 * u, 0.28 * u), (0.78 * u, 0.28 * u),
           (0.30 * u, 0.80 * u), (0.70 * u, 0.80 * u)]
    for cx, cy in pts:
        d.line([(cx, cy), (0.5 * u, 0.5 * u)], fill=WHITE, width=int(w * 0.5))
    for cx, cy in pts:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=WHITE, width=int(w * 0.8))
    cr = int(u * 0.085)
    d.ellipse([0.5 * u - cr, 0.5 * u - cr, 0.5 * u + cr, 0.5 * u + cr], fill=WHITE)
    _save(img, path)


def _draw_blend(path: Path) -> None:
    """Make blend (Ctrl+Alt+B): a row of shapes shrinking left→right (blend steps)."""
    u, img, d = _new()
    w = int(u * 0.045)
    for cx, rr in [(0.22 * u, 0.18 * u), (0.46 * u, 0.13 * u),
                   (0.66 * u, 0.09 * u), (0.82 * u, 0.055 * u)]:
        d.ellipse([cx - rr, 0.5 * u - rr, cx + rr, 0.5 * u + rr], outline=WHITE, width=w)
    _save(img, path)


# drawn glyphs: filename -> draw function (only created if not already committed)
DRAWN = {
    "pen.png": _draw_pen,
    "scissors.png": _draw_scissors,
    "width.png": _draw_width,
    "swap.png": _draw_swap,
    "default.png": _draw_default,
    "line.png": _draw_line,
    "outline.png": _draw_outline,
    "guides.png": _draw_guides,
    "smartguides.png": _draw_smartguides,
    "average.png": _draw_average,
    "blend.png": _draw_blend,
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
    for fname, fn in DRAWN.items():
        if (out / fname).exists():
            print(f"  {fname}  <- committed asset (left as-is)")
        else:
            fn(out / fname)
            print(f"  {fname}  <- drawn (white-on-transparent glyph)")
    if (out / "illustrator.png").exists():
        print("  illustrator.png  <- committed asset (left as-is)")
    else:
        _draw_ai_logo(out / "illustrator.png")
        print("  illustrator.png  <- drawn generic 'Ai' monogram (no Adobe logo)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
