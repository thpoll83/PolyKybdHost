#!/usr/bin/env python3
"""Fetch + render the Figma shortcut icons (reproducible).

Most glyphs are Microsoft Fluent UI System Icons (MIT) rendered to 96x96 RGBA
PNG; the generator's `luma` mode keeps the linework at 1-bit. A handful of
Figma-specific tools (slice, frame-selection, the program mark) have no clean
Fluent glyph and are drawn in code as white-on-transparent (`mode: alpha`).
The program icon (ESC) is a generic, license-clean rounded-square "F" mark — it
is NOT Figma's multi-dot logo.

    pip install cairosvg
    python polyhost/res/overlay_sources/figma/fetch_icons.py
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

# All probed against raw.githubusercontent.com (HTTP 200) before use.
MS_ICONS = {
    # --- tools (no-mod) ---
    "move": "Arrow Move/SVG/ic_fluent_arrow_move_24_regular.svg",
    "scale": "Resize Large/SVG/ic_fluent_resize_large_24_regular.svg",
    "frame": "Frame/SVG/ic_fluent_frame_24_regular.svg",
    "rectangle": "Rectangle Landscape/SVG/ic_fluent_rectangle_landscape_24_regular.svg",
    "ellipse": "Circle/SVG/ic_fluent_circle_24_regular.svg",
    "line": "Line/SVG/ic_fluent_line_24_regular.svg",
    "pen": "Pen/SVG/ic_fluent_pen_24_regular.svg",
    "text": "Text T/SVG/ic_fluent_text_t_24_regular.svg",
    "hand": "Hand Right/SVG/ic_fluent_hand_right_24_regular.svg",
    "comment": "Comment/SVG/ic_fluent_comment_24_regular.svg",
    "eyedropper": "Eyedropper/SVG/ic_fluent_eyedropper_24_regular.svg",
    # --- edit (Ctrl) ---
    "copy": "Copy/SVG/ic_fluent_copy_24_regular.svg",
    "cut": "Cut/SVG/ic_fluent_cut_24_regular.svg",
    "paste": "Clipboard Paste/SVG/ic_fluent_clipboard_paste_24_regular.svg",
    "undo": "Arrow Undo/SVG/ic_fluent_arrow_undo_24_regular.svg",
    "duplicate": "Document Copy/SVG/ic_fluent_document_copy_24_regular.svg",
    "group": "Group/SVG/ic_fluent_group_24_regular.svg",
    "selectall": "Select All On/SVG/ic_fluent_select_all_on_24_regular.svg",
    "save": "Save/SVG/ic_fluent_save_24_regular.svg",
    "newfile": "Document Add/SVG/ic_fluent_document_add_24_regular.svg",
    "rename": "Rename/SVG/ic_fluent_rename_24_regular.svg",
    "flatten": "Layer/SVG/ic_fluent_layer_24_regular.svg",
    "find": "Search/SVG/ic_fluent_search_24_regular.svg",
    # --- text format (Ctrl) ---
    "bold": "Text Bold/SVG/ic_fluent_text_bold_24_regular.svg",
    "italic": "Text Italic/SVG/ic_fluent_text_italic_24_regular.svg",
    "underline": "Text Underline/SVG/ic_fluent_text_underline_24_regular.svg",
    "strikethrough": "Text Strikethrough/SVG/ic_fluent_text_strikethrough_24_regular.svg",
    # --- Ctrl+Shift ---
    "ungroup": "Group Dismiss/SVG/ic_fluent_group_dismiss_24_regular.svg",
    "pasteover": "Clipboard Paste/SVG/ic_fluent_clipboard_paste_24_regular.svg",
    "placeimage": "Image Add/SVG/ic_fluent_image_add_24_regular.svg",
    "outlinestroke": "Pen Sparkle/SVG/ic_fluent_pen_sparkle_24_regular.svg",
    "export": "Arrow Export/SVG/ic_fluent_arrow_export_24_regular.svg",
    "copypng": "Image Copy/SVG/ic_fluent_image_copy_24_regular.svg",
    # --- Shift ---
    "rulers": "Ruler/SVG/ic_fluent_ruler_24_regular.svg",
    "grid": "Grid/SVG/ic_fluent_grid_24_regular.svg",
    "outlineview": "Eye Off/SVG/ic_fluent_eye_off_24_regular.svg",
    "zoomfit": "Full Screen Maximize/SVG/ic_fluent_full_screen_maximize_24_regular.svg",
    "zoomsel": "Select Object/SVG/ic_fluent_select_object_24_regular.svg",
    "pencil": "Inking Tool/SVG/ic_fluent_inking_tool_24_regular.svg",
    "arrowtool": "Arrow Up Right/SVG/ic_fluent_arrow_up_right_24_regular.svg",
    # --- Ctrl+Alt ---
    "component": "Cube Add/SVG/ic_fluent_cube_add_20_regular.svg",
    "detach": "Plug Disconnected/SVG/ic_fluent_plug_disconnected_24_regular.svg",
    # --- added (coverage audit 2026-06) ---
    "tofront": "Position To Front/SVG/ic_fluent_position_to_front_24_regular.svg",
    "toback": "Position To Back/SVG/ic_fluent_position_to_back_24_regular.svg",
    "forward": "Arrow Up/SVG/ic_fluent_arrow_up_24_regular.svg",
    "backward": "Arrow Down/SVG/ic_fluent_arrow_down_24_regular.svg",
    "mask": "Crop/SVG/ic_fluent_crop_24_regular.svg",
    "selinverse": "Arrow Swap/SVG/ic_fluent_arrow_swap_24_regular.svg",
}


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _white(u: int) -> Image.Image:
    return Image.new("RGBA", (u, u), (0, 0, 0, 0))


def _save_alpha(img: Image.Image, path: Path) -> None:
    img.resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def _draw_slice(path: Path) -> None:
    """Slice tool (S): a dashed export-region rectangle with corner ticks.
    No clean Fluent glyph exists, so draw it. White on transparent."""
    ss = 4
    u = RENDER_PX * ss
    w = int(u * 0.05)
    white = (255, 255, 255, 255)
    img = _white(u)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 0.18 * u, 0.24 * u, 0.82 * u, 0.76 * u
    dash = 0.07 * u
    # dashed horizontal edges
    x = x0
    while x < x1:
        d.line([(x, y0), (min(x + dash, x1), y0)], fill=white, width=w)
        d.line([(x, y1), (min(x + dash, x1), y1)], fill=white, width=w)
        x += 2 * dash
    # dashed vertical edges
    y = y0
    while y < y1:
        d.line([(x0, y), (x0, min(y + dash, y1))], fill=white, width=w)
        d.line([(x1, y), (x1, min(y + dash, y1))], fill=white, width=w)
        y += 2 * dash
    # solid corner ticks (top-left, bottom-right) so it reads as a slice handle
    t = 0.13 * u
    for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y1, -1, -1)):
        d.line([(cx, cy), (cx + dx * t, cy)], fill=white, width=w * 2)
        d.line([(cx, cy), (cx, cy + dy * t)], fill=white, width=w * 2)
    _save_alpha(img, path)


def _draw_frame_selection(path: Path) -> None:
    """Frame selection (Ctrl+Alt+G): a solid object inside a frame's corner
    brackets. White on transparent."""
    ss = 4
    u = RENDER_PX * ss
    w = int(u * 0.055)
    white = (255, 255, 255, 255)
    img = _white(u)
    d = ImageDraw.Draw(img)
    # four corner brackets (the frame)
    x0, y0, x1, y1 = 0.14 * u, 0.18 * u, 0.86 * u, 0.82 * u
    t = 0.18 * u
    for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1),
                             (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(cx, cy), (cx + dx * t, cy)], fill=white, width=w)
        d.line([(cx, cy), (cx, cy + dy * t)], fill=white, width=w)
    # the selected object in the middle
    d.rectangle([0.38 * u, 0.40 * u, 0.62 * u, 0.60 * u], fill=white)
    _save_alpha(img, path)


def _draw_figma_mark(path: Path) -> None:
    """Generic, license-clean program mark (NOT Figma's logo): a rounded-square
    *outline* with the monogram 'Fi' drawn inside — the unified outlined-monogram
    style shared with the other creative-app marks. White on transparent
    (program_icon_mode: alpha)."""
    ss = 4
    u = RENDER_PX * ss
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0.12 * u, 0.12 * u, 0.88 * u, 0.88 * u],
                        radius=0.16 * u, outline=255, width=int(u * 0.05))
    font = None
    for cand in ("DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(cand, int(u * 0.42))
            break
        except OSError:
            continue
    if font:
        bb = d.textbbox((0, 0), "Fi", font=font)
        cx, cy = 0.50 * u, 0.50 * u
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
               "Fi", font=font, fill=255)
    rgba = np.zeros((u, u, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.asarray(m)
    _save_alpha(Image.fromarray(rgba, "RGBA"), path)


_DRAWN = {
    "slice.png": _draw_slice,
    "frameselection.png": _draw_frame_selection,
    "figma.png": _draw_figma_mark,
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
    for fname, fn in _DRAWN.items():
        if (out / fname).exists():
            print(f"  {fname}  <- committed asset (left as-is)")
        else:
            fn(out / fname)
            print(f"  {fname}  <- drawn (white-on-transparent)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
