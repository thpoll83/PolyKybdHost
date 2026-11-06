#!/usr/bin/env python3
"""Fetch + render the Autodesk 3ds Max shortcut icons (reproducible source step).

Glyphs are Google Material Symbols (Apache-2.0, ``ms:`` names) and Microsoft
Fluent UI System Icons (MIT), rendered through ``../icon_fetch.py``. Glyphs that
mean the same as in a sibling set are copied byte-identical from it
(``BORROW``). Drawn here with ``../dcc_glyphs.py``: the view cubes (front, left,
top, orthographic user view), the X / Y / Z / XY constraint letters, the
border and element sub-object tiles, and the eight "hide <category>" keys
(the category icon with a diagonal stroke).

The ESC mark is DRAWN (``_max_mark``): Simple Icons has no 3ds Max mark and the
Autodesk product icon is a trademark. See SOURCES.md.

    pip install cairosvg Pillow numpy
    PYTHONPATH=. python polyhost/res/overlay_sources/3dsmax/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import dcc_glyphs as g  # noqa: E402
from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

ICONS = {
    # --- file and edit
    "new": "Document Add",
    "open": "Folder Open",
    "save": "Save",
    "saveas": "ms:save_as",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "delete": "Delete",
    "selectall": "Select All On",
    "hold": "ms:move_to_inbox",
    "fetch": "ms:outbox",
    "assettracking": "ms:inventory",
    "normalalign": "ms:arrow_outward",
    "typein": "ms:keyboard",
    "groupattach": "ms:group_add",
    "cam_physical": "ms:add_a_photo",
    "cam_standard": "ms:camera",
    "endresult": "ms:layers",
    # --- editable poly and PolyTools
    "backfacing": "ms:flip_to_front",
    "loop": "ms:all_inclusive",
    "ring": "ms:donut_large",
    "refine": "ms:polyline",
    "setflow": "ms:waves",
    "insertloop": "ms:view_stream",
    "polyshift": "ms:moving",
    "spinedge": "ms:rotate_90_degrees_cw",
    "straighten": "ms:straighten",
    "circleloops": "ms:circle",
    "geopoly": "ms:hexagon",
    "geomvisibility": "ms:checklist",
    # --- quad menus, render
    "lock": "ms:lock",
    "quad_windows": "ms:tab_group",
    "advlighting": "ms:light_mode",
    "animsequence": "ms:theaters",
    "environment": "ms:public",
    "renderlast": "ms:repeat",
    "rendersetup": "ms:video_settings",
    # --- selection
    "children": "ms:account_tree",
    "selectbyname": "ms:format_list_bulleted",
    "smartselect": "Cursor",
    "cycleselect": "ms:ink_selection",
    "windowcrossing": "ms:select",
    # --- animation, snaps
    "autokey": "ms:radio_button_checked",
    "anglesnap": "ms:rotate_90_degrees_ccw",
    "axisconstraints": "ms:linear_scale",
    # --- tools
    "centercycle": "ms:adjust",
    "hide": "ms:visibility_off",
    "shortcutoverride": "ms:keyboard_command_key",
    "material": "ms:texture",
    "pan": "ms:pan_tool",
    "pan_view": "ms:back_hand",
    "quickalign": "ms:align_horizontal_center",
    "scalecycle": "ms:photo_size_select_large",
    "smartplace": "ms:place_item",
    "statistics": "ms:query_stats",
    "sound": "ms:volume_up",
    "spacing": "ms:horizontal_distribute",
    "gizmo_down": "ms:do_not_disturb_on",
    "gizmo_up": "ms:add_circle",
    "lighting": "ms:lightbulb",
    "safeframes": "ms:crop_free",
    "highquality": "ms:hd",
    "shadeselected": "ms:imagesearch_roller",
    "bracket": "ms:crop",
    "zoomextall": "ms:aspect_ratio",
    "zoomextsel": "ms:fit_screen",
    "zoom2x": "ms:pageview",
    "zoommode": "ms:search",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "trackparams": "ms:tune",
    "globalsearch": "ms:manage_search",
    # --- views
    "degradation": "ms:speed",
    "cameraview": "ms:videocam",
    "disableviewport": "ms:desktop_access_disabled",
    "expert": "ms:width_full",
    "homeview": "ms:home",
    "orbit": "ms:3d_rotation",
    "view_persp": "ms:view_in_ar",
    "viewundo": "ms:history",
    "viewredo": "ms:update",
    "highlights": "ms:highlight",
    "floating": "ms:picture_in_picture",
    "spotview": "ms:flashlight_on",
    "bgupdate": "ms:wallpaper",
    "edgedfaces": "ms:grid_4x4",
    "background": "ms:image",
    # --- bases for the "hide <category>" composites
    "cat_cameras": "ms:videocam",
    "cat_geometry": "ms:deployed_code",
    "cat_grids": "ms:grid_on",
    "cat_helpers": "ms:my_location",
    "cat_lights": "ms:lightbulb",
    "cat_particles": "ms:grain",
    "cat_shapes": "ms:shape_line",
    "cat_spacewarps": "ms:cyclone",
}

# Same action as in a sibling set: a byte-identical copy.
BORROW = {
    "move.png": "blender",            # select and move
    "rotate.png": "blender",          # select and rotate
    "scale.png": "blender",           # smart scale
    "align.png": "blender",
    "duplicate.png": "blender",       # clone
    "extrude.png": "blender",         # extrude face
    "grow.png": "blender",            # grow selection
    "shrink.png": "blender",          # shrink selection
    "proportional.png": "blender",    # soft selection
    "loopcut.png": "blender",         # swift loop
    "save_incremental.png": "blender",
    "ed_console.png": "blender",      # MAXScript listener
    "sel_vert.png": "blender",        # sub-object level 1: vertex
    "sel_edge.png": "blender",        # sub-object level 2: edge
    "sel_face.png": "blender",        # sub-object level 4: polygon
    "quadview.png": "blender",        # viewports quad menu
    "render.png": "blender",
    "hier_parent.png": "blender",     # select ancestor
    "hier_child.png": "blender",      # select child
    "select_invert.png": "blender",
    "deselect.png": "blender",        # select none
    "select_similar.png": "blender",
    "key_insert.png": "blender",      # set keys
    "snap.png": "blender",            # snaps toggle
    "snap_options.png": "blender",    # cycle snap type
    "frame_prev.png": "blender",
    "frame_next.png": "blender",
    "jump_start.png": "blender",
    "jump_end.png": "blender",
    "play.png": "blender",
    "pivot.png": "blender",           # affect pivot only
    "xray.png": "blender",            # see-through
    "hide_others.png": "blender",     # hide unselected
    "reveal.png": "blender",          # unhide all
    "localview.png": "blender",       # isolate selection
    "maximize.png": "blender",        # maximize viewport
    "edit_mode.png": "blender",       # sub-object selection toggle
    "frame_all.png": "blender",       # zoom extents
    "zoom_region.png": "blender",     # zoom region mode
    "refresh.png": "blender",         # redraw all views
    "walk.png": "blender",            # walkthrough
    "shading.png": "blender",         # wireframe / smooth toggle
}

VIEWS = {"view_front.png": "front", "view_left.png": "left", "view_top.png": "top",
         "view_ortho.png": "none"}
AXES = {"axis_x.png": "X", "axis_y.png": "Y", "axis_z.png": "Z", "axis_plane.png": "XY"}
HIDE = ["cameras", "geometry", "grids", "helpers", "lights", "particles", "shapes", "spacewarps"]

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def _tile(path: Path, kind: str) -> None:
    """Sub-object tiles in the style of Blender's select-mode tiles:
    ``border`` lights a hole's outline inside a thin face outline; ``element``
    lights two faces of one connected piece."""
    u, m, d = g._canvas()
    a, b = 0.18 * u, 0.82 * u
    w = int(u * 0.045)
    if kind == "border":
        d.rectangle([a, a, b, b], outline=255, width=w)
        c0, c1 = 0.36 * u, 0.64 * u
        d.rectangle([c0, c0, c1, c1], outline=255, width=int(u * 0.09))
    else:
        mid = u / 2
        d.rectangle([a, a, mid - w, b], fill=255)
        d.rectangle([mid + w, a, b, b], fill=255)
    g._save_mask(m, path)


def _max_mark(path: Path, px: int = 32) -> None:
    """A rounded tile with "3ds" knocked out, drawn at 8x and cut to 1 bit at
    px x px. White on transparent (the spec uses program_icon_mode: alpha).
    Not the Autodesk product icon, which is a trademark."""
    s = 8
    u = px * s
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, u - 1, u - 1], radius=int(u * 0.18), fill=255)
    f = ImageFont.truetype(BOLD, int(u * 0.50))
    d.text((u * 0.50, u * 0.47), "3ds", fill=0, font=f, anchor="mm")
    a = np.asarray(m.resize((px, px), Image.LANCZOS))
    a = np.where(a >= 128, 255, 0).astype(np.uint8)
    Image.fromarray(np.dstack([a, a, a, a]), "RGBA").save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(ICONS, out)
    icon_fetch.borrow(BORROW, out)
    for name, face in VIEWS.items():
        g.guarded(out / name, lambda p, f=face: g.view_cube(p, f), f"drawn view cube ({face})")
    for name, letters in AXES.items():
        g.guarded(out / name, lambda p, t=letters: g.axis_letter(p, t), f"drawn axis {letters}")
    for kind in ("border", "element"):
        g.guarded(out / f"sel_{kind}.png", lambda p, k=kind: _tile(p, k), f"drawn tile ({kind})")
    for cat in HIDE:
        g.guarded(out / f"hide_{cat}.png",
                  lambda p, c=cat: g.slashed(out / f"cat_{c}.png", p), f"composite (cat_{cat} slashed)")
    g.guarded(out / "3dsmax.png", _max_mark, "drawn program mark")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
