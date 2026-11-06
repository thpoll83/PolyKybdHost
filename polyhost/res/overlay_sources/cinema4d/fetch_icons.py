#!/usr/bin/env python3
"""Fetch + render the Maxon Cinema 4D shortcut icons (reproducible source step).

Glyphs are Google Material Symbols (Apache-2.0, ``ms:`` names) and Microsoft
Fluent UI System Icons (MIT), rendered through ``../icon_fetch.py``. Glyphs that
mean the same as in a sibling set are copied byte-identical from it
(``BORROW``): the view cubes and axis letters come from the 3ds Max set, most
modeling and render glyphs from the Blender set. The right-view cube is drawn
here with ``../dcc_glyphs.py``.

The ESC mark is the Cinema 4D logo from Simple Icons (``cinema4d``, artwork
CC0-1.0) reduced to a 32x32 1-bit trace. See SOURCES.md.

    pip install cairosvg Pillow numpy
    PYTHONPATH=. python polyhost/res/overlay_sources/cinema4d/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import dcc_glyphs as g  # noqa: E402
from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

ICONS = {
    # --- managers (Shift+F-keys)
    "objectmanager": "ms:account_tree",
    "materialmanager": "ms:texture",
    "nodeeditor": "ms:schema",
    "timeline": "ms:view_timeline",
    "layermanager": "ms:layers",
    "attributes": "ms:tune",
    "pictureviewer": "ms:image",
    "coordinates": "ms:my_location",
    "structure": "ms:dataset",
    "scripts": "ms:code",
    "commands": "ms:keyboard_command_key",
    # --- editor and file
    "parentgen": "ms:toggle_on",
    "help": "ms:help",
    "closewindow": "Dismiss",
    "closeall": "ms:cancel_presentation",
    "new": "Document Add",
    "open": "Folder Open",
    "merge": "ms:merge",
    "save": "Save",
    "saveas": "ms:save_as",
    "quit": "Power",
    "delete": "Delete",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "selectall": "Select All On",
    # --- general
    "lasttool": "ms:published_with_changes",
    "lasttwotools": "ms:sync_alt",
    "fullscreen": "Full Screen Maximize",
    "commander": "ms:search",
    # --- viewport
    "cam_move": "ms:pan_tool",
    "cam_scale": "ms:zoom_in",
    "cam_rotate": "ms:3d_rotation",
    "zoomselected": "ms:zoom_in_map",
    "zoomobject": "ms:filter_center_focus",
    "axes": "ms:control_camera",
    "view_persp": "ms:view_in_ar",
    "presets": "ms:bookmarks",
    "presets_all": "ms:collections_bookmark",
    "presets_similar": "ms:bookmark_manager",
    "teamrender": "ms:lan",
    "rendersettings": "ms:video_settings",
    "viewundo": "ms:history",
    "viewredo": "ms:update",
    "isoline": "ms:conversion_path",
    # --- modeling
    "melt": "ms:water_drop",
    "makeeditable": "ms:edit_square",
    "obj_move": "ms:drag_pan",
    "obj_scale": "ms:aspect_ratio",
    "obj_rotate": "ms:rotate_left",
    "freehand": "ms:gesture_select",
    "modelingmode": "ms:switch_access_shortcut",
    "quantize": "ms:stairs",
    "workplane": "ms:lock",
    "modeling": "ms:handyman",
    "modelingsettings": "ms:settings",
    "renderregion": "ms:crop",
}

# Same action as in a sibling set: a byte-identical copy.
BORROW = {
    "view_front.png": "3dsmax",
    "view_top.png": "3dsmax",
    "axis_x.png": "3dsmax",
    "axis_y.png": "3dsmax",
    "axis_z.png": "3dsmax",
    "move.png": "blender",            # move tool
    "rotate.png": "blender",
    "scale.png": "blender",
    "extrude.png": "blender",
    "inset.png": "blender",           # extrude inner
    "stitch.png": "blender",          # bridge
    "knife.png": "blender",
    "dissolve.png": "blender",
    "mirror.png": "blender",          # symmetry
    "orientation.png": "blender",     # change coordinate system
    "context_menu.png": "blender",    # quick command selection
    "save_incremental.png": "blender",
    "render.png": "blender",          # render view
    "render_view.png": "blender",     # render to Picture Viewer
    "play_rendered.png": "blender",   # create preview
    "refresh.png": "blender",         # redraw
    "maximize.png": "blender",        # toggle active view
    "quadview.png": "blender",        # all views
    "frame_all.png": "blender",       # zoom to geometry
    "deselect.png": "blender",
    "select_box.png": "blender",      # rectangle selection
    "select_circle.png": "blender",   # live selection
    "snap.png": "blender",
    "parent.png": "blender",          # move parent
    "adjust_last.png": "blender",     # undo (action)
    "shading.png": "blender",         # display modes (N ...)
}

C4D_ICON_URL = "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/cinema4d.svg"


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(ICONS, out)
    icon_fetch.borrow(BORROW, out)
    g.guarded(out / "view_right.png", lambda p: g.view_cube(p, "right"), "drawn view cube (right)")
    g.guarded(out / "cinema4d.png",
              lambda p: g.trace_mark(g.svg_icon(C4D_ICON_URL), p, lit="dark"),
              "simple-icons/cinema4d (CC0), 32x32 trace")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
