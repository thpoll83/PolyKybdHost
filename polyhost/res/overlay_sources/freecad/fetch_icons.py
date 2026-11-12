#!/usr/bin/env python3
"""Fetch + render the FreeCAD shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. The standard view names
and the Sketcher constraint symbols are text in DejaVu Sans Bold; the tangent
symbol is drawn. No program icon: the host draws the ESC mark for the app
itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/freecad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RENDER_PX = 96
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

FLUENT = {
    # --- file, edit, tools ---
    "import": "ms:input",
    "export": "ms:file_export",
    "refresh": "ms:refresh",
    "recompute": "ms:sync",
    "properties": "ms:tune",
    "console": "ms:terminal",
    "runmacro": "ms:play_circle",
    "whatsthis": "ms:help_center",
    "help": "ms:help",
    "appearance": "ms:format_paint",
    "preferences": "Settings",
    "rename": "ms:drive_file_rename_outline",
    # --- view ---
    "freeze": "ms:ac_unit",
    "visibility": "Eye",
    "home": "ms:home",
    "isometric": "ms:view_in_ar",
    "rotleft": "ms:rotate_left",
    "rotright": "ms:rotate_right",
    "fullscreen": "ms:fullscreen",
    "boxzoom": "ms:zoom_in_map",
    "boxsel": "ms:select",
    "boxelemsel": "ms:select_all",
    "panelleft": "ms:left_panel_open",
    "panelright": "ms:right_panel_open",
    "paneltop": "ms:top_panel_open",
    "panelbottom": "ms:bottom_panel_open",
    "storeview": "ms:bookmark_add",
    "recallview": "ms:bookmark",
    "nextwin": "ms:select_window",
    "prevwin": "ms:select_window_2",
    # --- workbenches ---
    "dimension": "ms:straighten",
    "pointonobj": "ms:commit",
    "coincident": "ms:adjust",
    "horizontal": "ms:horizontal_rule",
    "transform": "ms:open_with",
    "snaplock": "ms:lock",
    "wireframe": "ms:grid_on",
}

TEXT = {
    # standard views (keys 0..6)
    "front": "FRT",
    "top": "TOP",
    "right": "RGT",
    "rear": "REAR",
    "bottom": "BTM",
    "left": "LFT",
    # Sketcher constraints
    "horver": "H/V",
    "vertical": "|",
    "hdim": "↔",
    "vdim": "↕",
    "parallel": "∥",
    "perpendicular": "⊥",
    "raddia": "⌀",
    "equal": "=",
    "symmetric": "⋈",
}


def _draw_text(path: Path, text: str) -> None:
    """Black text on transparent, like the fetched glyphs, scaled so its ink
    fills the icon."""
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


def _draw_tangent(path: Path) -> None:
    """A circle with a line touching its top, the usual tangent symbol."""
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((22, 30, 74, 82), outline=(0, 0, 0, 255), width=8)
    d.rectangle((2, 22, RENDER_PX - 3, 30), fill=(0, 0, 0, 255))
    img.save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    for name, text in TEXT.items():
        _draw_text(out / f"{name}.png", text)
        n += 1
    _draw_tangent(out / "tangent.png")
    n += 1
    print(f"Wrote {n} icons to {out} ({len(TEXT)} drawn as text)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
