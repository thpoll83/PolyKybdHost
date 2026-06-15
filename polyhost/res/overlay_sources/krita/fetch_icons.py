#!/usr/bin/env python3
"""Fetch + render the Krita shortcut icons (reproducible).

Most glyphs are Microsoft Fluent UI System Icons (MIT) — license-clean (the host
is GPL-2.0, and MIT is GPLv2-compatible). Rendered to 96x96 RGBA PNG; the
generator's `luma` mode keeps the linework at 1-bit.

A few painting actions have no clean Fluent glyph, so they are drawn directly in
this file as white-on-transparent glyphs (consumed with `mode: alpha`):
brush-size decrease/increase (a small / large dot) and switch-to-previous-preset
(two swatches with a swap arrow).

⚠️ We deliberately do NOT bundle Krita's own icons — they are GPLv3, which is
incompatible with the host's GPL-2.0. The program mark (ESC) is a generic
license-clean "Kr" monogram drawn in code, NOT Krita's logo.

    pip install cairosvg
    python polyhost/res/overlay_sources/krita/fetch_icons.py
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

# All probed (raw fetch, HTTP 200) before being relied on. See SOURCES.md.
MS_ICONS = {
    # --- file ---
    "new": "Document Add/SVG/ic_fluent_document_add_24_regular.svg",
    "open": "Folder Open/SVG/ic_fluent_folder_open_24_regular.svg",
    "save": "Save/SVG/ic_fluent_save_24_regular.svg",
    "saveas": "Save Edit/SVG/ic_fluent_save_edit_24_regular.svg",
    "close": "Document Dismiss/SVG/ic_fluent_document_dismiss_24_regular.svg",
    # --- edit ---
    "copy": "Copy/SVG/ic_fluent_copy_24_regular.svg",
    "cut": "Cut/SVG/ic_fluent_cut_24_regular.svg",
    "paste": "Clipboard Paste/SVG/ic_fluent_clipboard_paste_24_regular.svg",
    "undo": "Arrow Undo/SVG/ic_fluent_arrow_undo_24_regular.svg",
    "redo": "Arrow Redo/SVG/ic_fluent_arrow_redo_24_regular.svg",
    "selectall": "Select All On/SVG/ic_fluent_select_all_on_24_regular.svg",
    "deselect": "Select All Off/SVG/ic_fluent_select_all_off_24_regular.svg",
    "invertsel": "Square Hint/SVG/ic_fluent_square_hint_24_regular.svg",
    "transform": "Resize/SVG/ic_fluent_resize_24_regular.svg",
    "copymerged": "Layer Diagonal/SVG/ic_fluent_layer_diagonal_24_regular.svg",
    # --- layers ---
    "mergedown": "Layer/SVG/ic_fluent_layer_24_regular.svg",
    "group": "Group/SVG/ic_fluent_group_24_regular.svg",
    "flatten": "Group List/SVG/ic_fluent_group_list_24_regular.svg",
    # --- tools / view ---
    "brush": "Inking Tool/SVG/ic_fluent_inking_tool_24_regular.svg",
    "eraser": "Eraser/SVG/ic_fluent_eraser_24_regular.svg",
    "mirror": "Flip Horizontal/SVG/ic_fluent_flip_horizontal_24_regular.svg",
    "zoom100": "Ratio One To One/SVG/ic_fluent_ratio_one_to_one_24_regular.svg",
    "fitpage": "Resize/SVG/ic_fluent_resize_24_regular.svg",
    "fitwidth": "Arrow Autofit Width/SVG/ic_fluent_arrow_autofit_width_24_regular.svg",
}


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _save_alpha(mask_u: np.ndarray, path: Path) -> None:
    """Save an (H,W) uint8 alpha mask as white-on-transparent RGBA at RENDER_PX."""
    rgba = np.zeros((mask_u.shape[0], mask_u.shape[1], 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = mask_u
    Image.fromarray(rgba, "RGBA").resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def _draw_brushdec(path: Path) -> None:
    """Decrease-brush-size glyph: a small filled dot (white on transparent)."""
    ss = 4
    u = RENDER_PX * ss
    img = Image.new("L", (u, u), 0)
    ImageDraw.Draw(img).ellipse(
        [0.40 * u, 0.40 * u, 0.60 * u, 0.60 * u], fill=255)   # small dot, centred
    _save_alpha(np.asarray(img), path)


def _draw_brushinc(path: Path) -> None:
    """Increase-brush-size glyph: a large filled dot (white on transparent)."""
    ss = 4
    u = RENDER_PX * ss
    img = Image.new("L", (u, u), 0)
    ImageDraw.Draw(img).ellipse(
        [0.22 * u, 0.22 * u, 0.78 * u, 0.78 * u], fill=255)   # large dot, centred
    _save_alpha(np.asarray(img), path)


def _draw_preset(path: Path) -> None:
    """Switch-to-previous-preset glyph: two rounded swatches with a curved swap
    arrow between them (white on transparent). Reads as 'toggle between two
    presets' — distinct from the plain undo/redo arrows."""
    ss = 4
    u = RENDER_PX * ss
    w = int(u * 0.055)
    img = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(img)
    # two preset swatches (top-left, bottom-right)
    d.rounded_rectangle([0.12 * u, 0.12 * u, 0.40 * u, 0.40 * u],
                        radius=0.06 * u, fill=255)
    d.rounded_rectangle([0.60 * u, 0.60 * u, 0.88 * u, 0.88 * u],
                        radius=0.06 * u, outline=255, width=w)
    # swap arrows (two opposing short lines with heads) along the diagonal
    d.line([(0.40 * u, 0.30 * u), (0.66 * u, 0.30 * u)], fill=255, width=w)
    d.polygon([(0.66 * u, 0.24 * u), (0.78 * u, 0.30 * u), (0.66 * u, 0.36 * u)], fill=255)
    d.line([(0.60 * u, 0.70 * u), (0.34 * u, 0.70 * u)], fill=255, width=w)
    d.polygon([(0.34 * u, 0.64 * u), (0.22 * u, 0.70 * u), (0.34 * u, 0.76 * u)], fill=255)
    _save_alpha(np.asarray(img), path)


def _draw_outlined_monogram(path: Path, text: str) -> None:
    """Shared program-mark style across the creative apps: a rounded-square
    *outline* with a centred monogram, white-on-transparent (alpha = the lit
    linework, `program_icon_mode: alpha`)."""
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
        bb = d.textbbox((0, 0), text, font=font)
        cx, cy = 0.50 * u, 0.50 * u
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
               text, font=font, fill=255)
    _save_alpha(np.asarray(m).astype(np.uint8), path)


def _draw_krita_logo(path: Path) -> None:
    """Generic, license-clean 'Kr' program mark (NOT Krita's logo): a rounded-
    square *outline* with the monogram 'Kr' drawn inside it — the unified
    outlined-monogram style shared with the other creative-app marks. White on
    transparent, rendered with `program_icon_mode: alpha`. Krita's real icons are
    GPLv3 and are deliberately not used."""
    _draw_outlined_monogram(path, "Kr")


DRAWN = {
    "brushdec.png": _draw_brushdec,
    "brushinc.png": _draw_brushinc,
    "preset.png": _draw_preset,
    "krita.png": _draw_krita_logo,
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
    for fname, draw in DRAWN.items():
        if (out / fname).exists():
            print(f"  {fname}  <- committed asset (left as-is)")
        else:
            draw(out / fname)
            print(f"  {fname}  <- drawn (white-on-transparent glyph)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
