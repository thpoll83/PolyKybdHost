#!/usr/bin/env python3
"""Fetch + render the Adobe Substance 3D Painter shortcut icons (reproducible).

Glyphs are Google Material Symbols (Apache-2.0, ``ms:`` names) and Microsoft
Fluent UI System Icons (MIT), rendered through ``../icon_fetch.py``. Glyphs that
mean the same as in a sibling set are copied byte-identical from it
(``BORROW``). Six composites are drawn from those with ``../dcc_glyphs.py``:
the three "+ Particles" tool variants, the absolute-source clone, and the
next / previous channel and mesh map keys.

The ESC mark is the Painter app icon (Adobe's product icon SVG) reduced to a
32x32 1-bit trace with the dark pixels lit. See SOURCES.md.

    pip install cairosvg Pillow numpy
    PYTHONPATH=. python polyhost/res/overlay_sources/substancepainter/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import dcc_glyphs as g  # noqa: E402
from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

ICONS = {
    # --- modes and UI
    "hideui": "ms:fullscreen",
    "mode_paint": "ms:palette",
    "mode_bake": "ms:oven_gen",
    "bakemaps": "ms:local_fire_department",
    # --- manipulator
    "warp": "ms:transform",
    # --- tools
    "tool_paint": "ms:brush",
    "tool_eraser": "ms:ink_eraser",
    "tool_projection": "ms:wallpaper",
    "tool_smudge": "ms:touch_app",
    "tool_clone": "ms:approval",
    "particles": "ms:grain",
    "absolute": "ms:my_location",
    "invertgray": "ms:exposure",
    "ignorestencil": "ms:hide_image",
    "hideexcluded": "ms:disabled_visible",
    # --- camera and display
    "cam_persp": "ms:view_in_ar",
    "cam_ortho": "ms:crop_square",
    "channel": "ms:layers",
    "meshmap": "ms:texture",
    "material": "Circle Half Fill",
    "animation": "ms:play_pause",
    "layout_3d2d": "ms:splitscreen_vertical_add",
    "layout_3d": "ms:deployed_code",
    "layout_2d": "ms:map",
    # --- file and layers
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "open": "Folder Open",
    "save": "Save",
    "new": "Document Add",
    "close": "Dismiss",
    "quit": "Power",
    "export": "Arrow Export",
    "copy": "Copy",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "delete": "Delete",
    "duplicate": "ms:control_point_duplicate",
    "group": "ms:folder",
    "copycontent": "ms:format_paint",
    "pastecontent": "ms:content_paste_go",
}

# Same action as in a sibling set: a byte-identical copy.
BORROW = {
    "gizmo.png": "blender",          # show/hide manipulator
    "orientation.png": "blender",    # cycle manipulation spaces
    "move.png": "blender",
    "rotate.png": "blender",
    "scale.png": "blender",
    "mirror.png": "blender",         # symmetry
    "snap.png": "blender",           # surface tool: snap to the model surface
    "brushinc.png": "photoshop",
    "brushdec.png": "photoshop",
    "eyedropper.png": "blender",     # pick stroke material
    "smooth_stroke.png": "blender",  # lazy mouse
    "stroke.png": "blender",         # resume previous stroke
    "fill.png": "blender",           # polygon fill
    "frame_all.png": "blender",      # center the whole mesh
    "swap.png": "blender",           # swap 2D / 3D view
    "br_mask.png": "blender",        # quick mask edition
    "mask_clear.png": "blender",
    "mask_invert.png": "blender",
    "faceset_isolate.png": "blender",  # texture set isolate
    "render.png": "blender",         # rendering (Iray) mode
}

# (output, base, badge) for the tool variants.
BADGES = [
    ("tool_paint_particles.png", "tool_paint.png", "particles.png"),
    ("tool_eraser_particles.png", "tool_eraser.png", "particles.png"),
    ("tool_projection_particles.png", "tool_projection.png", "particles.png"),
    ("tool_clone_absolute.png", "tool_clone.png", "absolute.png"),
]

# (output, base, forward) for the next / previous display keys.
ARROWS = [
    ("channel_next.png", "channel.png", True),
    ("channel_prev.png", "channel.png", False),
    ("meshmap_next.png", "meshmap.png", True),
    ("meshmap_prev.png", "meshmap.png", False),
]

PAINTER_ICON_URL = "https://www.adobe.com/cc-shared/assets/img/product-icons/svg/substance-3d-painter.svg"


def _painter_icon(svg: Path | None):
    """The Painter app icon: from a local copy of the SVG when one is given,
    else from Adobe's CDN (which refused this script's request on 2026-11-06;
    download the file with a browser or curl and pass ``--icon-svg``)."""
    if svg is None:
        return g.svg_icon(PAINTER_ICON_URL)
    import io
    import cairosvg
    from PIL import Image
    png = cairosvg.svg2png(url=str(svg), output_width=256, output_height=256)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--icon-svg", type=Path, help="local copy of the Painter app icon SVG")
    args = ap.parse_args()
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(ICONS, out)
    icon_fetch.borrow(BORROW, out)
    for name, base, badge in BADGES:
        g.guarded(out / name, lambda p, b=base, s=badge: g.with_badge(out / b, out / s, p),
                  f"composite ({base} + {badge})")
    for name, base, fwd in ARROWS:
        g.guarded(out / name, lambda p, b=base, f=fwd: g.with_arrow(out / b, p, f),
                  f"composite ({base} + arrow)")
    g.guarded(out / "painter.png",
              lambda p: g.trace_mark(_painter_icon(args.icon_svg), p, lit="dark"),
              "Painter app icon, 32x32 trace, dark pixels lit")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
