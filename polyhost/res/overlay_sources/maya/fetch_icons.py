#!/usr/bin/env python3
"""Fetch + render the Autodesk Maya shortcut icons (reproducible source step).

Glyphs are Google Material Symbols (Apache-2.0, ``ms:`` names) and Microsoft
Fluent UI System Icons (MIT), rendered through ``../icon_fetch.py``. Glyphs that
mean the same as in a sibling set are copied byte-identical from it
(``BORROW``): most tools, selection and playback glyphs from the Blender set,
the view-history and manipulator-size glyphs from the 3ds Max set, and a few
editor glyphs from the Cinema 4D set.

Drawn here: the three mesh-smoothness glyphs on 1 / 2 / 3, the shaded disc,
the four "move one pixel" glyphs, and the composites
built with ``../dcc_glyphs.py`` (``with_badge``, ``with_arrow``): the snapping
modes, the "key translate / rotate / scale" keys, the selection conversions,
the visibility toggles and the bookmark keys.

The ESC mark is the Autodesk Maya logo from Simple Icons (``autodeskmaya``,
artwork CC0-1.0; the logo is an Autodesk trademark): its two plates reduced to
32x32 1 bit, with the M redrawn as a pixel map. See SOURCES.md.

    pip install cairosvg Pillow numpy
    PYTHONPATH=. python polyhost/res/overlay_sources/maya/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import dcc_glyphs as g  # noqa: E402
from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

ICONS = {
    # --- tools
    "complete": "ms:check",
    # --- file and edit
    "reference": "ms:link",
    "intermediate": "ms:subdirectory_arrow_right",
    "colorchooser": "ms:palette",
    "quaddraw": "ms:draw",
    # --- display and visibility
    "show": "ms:visibility",
    "quality_default": "ms:settings_backup_restore",
    "rigdisplay": "ms:accessibility_new",
    "proxy_toggle": "ms:compare",
    "proxy_both": "ms:layers",
    # --- menus and menu sets
    "mainmenu": "ms:menu",
    "panelmenu": "ms:top_panel_open",
    "paneltoolbar": "ms:home_repair_service",
    "fullpanels": "ms:desktop_windows",
    "manipulator": "ms:touch_app",
    "hotboxstyle": "ms:dashboard",
    "set_modeling": "ms:deployed_code",
    "set_rigging": "ms:account_tree",
    "set_animation": "ms:animation",
    "set_rendering": "ms:photo_camera",
    # --- view
    "pan2d": "ms:pan_zoom",
    # --- bookmarks
    "bookmark_add": "ms:bookmark_add",
    "bookmark_quick": "ms:bookmark_added",
    # --- bases for the composites below (not bound directly)
    "b_grid": "ms:grid_4x4",
    "b_curve": "ms:gesture",
    "b_point": "ms:scatter_plot",
    "b_delta": "ms:change_history",
    "b_convert": "ms:autorenew",
    "b_settings": "ms:settings",
    "b_plus": "ms:add",
    "b_history": "ms:history",
    "b_cursor": "ms:arrow_selector_tool",
    "b_polygon": "ms:pentagon",
    "b_image": "ms:image",
    "b_bookmark": "ms:bookmark",
    "b_width": "ms:width",
    "b_close": "ms:close",
    "b_lock": "ms:lock",
    "b_straighten": "ms:straighten",
    "b_sync": "ms:sync",
}

# Same action as in a sibling set: a byte-identical copy.
BORROW = {
    "move.png": "blender",            # Move Tool
    "rotate.png": "blender",          # Rotate Tool
    "scale.png": "blender",           # Scale Tool
    "gizmo.png": "blender",           # universal manipulator
    "pivot.png": "blender",           # tool edit mode / move pivot
    "tab_next.png": "blender",        # cycle In-View Editor values
    "tab_prev.png": "blender",
    "repeat.png": "blender",          # repeat last action
    "edit_mode.png": "blender",       # object / component mode
    "sel_vert.png": "blender",
    "sel_edge.png": "blender",
    "sel_face.png": "blender",
    "uv_unwrap.png": "blender",       # select UV
    "parent.png": "blender",
    "parent_clear.png": "blender",    # unparent
    "key_insert.png": "blender",      # set key
    "key_next.png": "blender",
    "key_prev.png": "blender",
    "play.png": "blender",
    "jump_start.png": "blender",      # go to min frame
    "frame_next.png": "blender",
    "frame_prev.png": "blender",
    "shading.png": "blender",         # wireframe / shaded toggle
    "localview.png": "blender",       # isolate select
    "hide_others.png": "blender",     # hide unselected
    "subdiv_up.png": "blender",       # division levels up
    "subdiv_down.png": "blender",
    "knife.png": "blender",           # Multi-Cut
    "duplicate.png": "blender",
    "group.png": "blender",
    "grow.png": "blender",
    "shrink.png": "blender",
    "frame_all.png": "blender",
    "quadview.png": "blender",        # base for "in all views"
    "workspace_prev.png": "blender",  # previous layout
    "workspace_next.png": "blender",
    "hier_parent.png": "blender",     # pick walk up
    "hier_child.png": "blender",      # pick walk down
    "select_left.png": "blender",     # pick walk left
    "select_right.png": "blender",
    "snap.png": "blender",            # base for the snapping modes
    "smartselect.png": "3dsmax",      # Select Tool
    "gizmo_up.png": "3dsmax",         # manipulator size up
    "gizmo_down.png": "3dsmax",
    "viewundo.png": "3dsmax",         # undo view change
    "viewredo.png": "3dsmax",
    "background.png": "3dsmax",       # background colour
    "hide.png": "3dsmax",             # hide selection
    "lighting.png": "3dsmax",         # use all lights
    "zoomextsel.png": "3dsmax",       # frame selected
    "new.png": "3dsmax",
    "open.png": "3dsmax",
    "save.png": "3dsmax",
    "saveas.png": "3dsmax",
    "undo.png": "3dsmax",
    "redo.png": "3dsmax",
    "quantize.png": "cinema4d",       # move / rotate / scale snapping
    "lasttool.png": "cinema4d",       # last used tool
    "attributes.png": "cinema4d",     # Attribute Editor
    "help.png": "cinema4d",
    "quit.png": "cinema4d",
    "cut.png": "cinema4d",
    "copy.png": "cinema4d",
    "paste.png": "cinema4d",
}

# (output, base, badge): ``base`` in the upper left, ``badge`` in the lower right.
BADGES = [
    ("snap_grid.png", "b_grid.png", "snap.png"),
    ("snap_curve.png", "b_curve.png", "snap.png"),
    ("snap_point.png", "b_point.png", "snap.png"),
    ("snap_relative.png", "quantize.png", "b_delta.png"),
    ("repeat_cursor.png", "repeat.png", "b_cursor.png"),
    ("sel_vertface.png", "sel_face.png", "sel_vert.png"),
    ("conv_vert.png", "sel_vert.png", "b_convert.png"),
    ("conv_edge.png", "sel_edge.png", "b_convert.png"),
    ("conv_face.png", "sel_face.png", "b_convert.png"),
    ("conv_uv.png", "uv_unwrap.png", "b_convert.png"),
    ("key_move.png", "move.png", "key_insert.png"),
    ("key_rotate.png", "rotate.png", "key_insert.png"),
    ("key_scale.png", "scale.png", "key_insert.png"),
    ("ins_move.png", "move.png", "b_plus.png"),
    ("ins_rotate.png", "rotate.png", "b_plus.png"),
    ("ins_scale.png", "scale.png", "b_plus.png"),
    ("key_insert_all.png", "key_insert.png", "b_plus.png"),
    ("selkey_next.png", "key_next.png", "b_cursor.png"),
    ("selkey_prev.png", "key_prev.png", "b_cursor.png"),
    ("vis_curves.png", "b_curve.png", "show.png"),
    ("vis_polys.png", "b_polygon.png", "show.png"),
    ("vis_imageplane.png", "b_image.png", "show.png"),
    ("show_last.png", "show.png", "b_history.png"),
    ("rig_cycle.png", "rigdisplay.png", "b_sync.png"),
    ("subdiv.png", "smooth1.png", "smooth3.png"),
    ("proxy_options.png", "subdiv.png", "b_settings.png"),
    ("to_subdiv.png", "subdiv.png", "b_convert.png"),
    ("to_subdiv_options.png", "b_convert.png", "b_settings.png"),
    ("lock_length.png", "b_straighten.png", "b_lock.png"),
    ("dup_special.png", "duplicate.png", "b_settings.png"),
    ("dup_transform.png", "duplicate.png", "move.png"),
    ("frame_all_views.png", "frame_all.png", "quadview.png"),
    ("frame_sel_views.png", "zoomextsel.png", "quadview.png"),
    ("bm_frame.png", "b_bookmark.png", "b_width.png"),
    ("bm_unframe.png", "b_bookmark.png", "b_close.png"),
]

# (output, base, forward): ``base`` over a heavy arrow.
ARROWS = [
    ("bm_next.png", "b_bookmark.png", True),
    ("bm_prev.png", "b_bookmark.png", False),
    ("bm_range_next.png", "bm_frame.png", True),
    ("bm_range_prev.png", "bm_frame.png", False),
]

MAYA_ICON_URL = ("https://raw.githubusercontent.com/simple-icons/simple-icons/"
                 "develop/icons/autodeskmaya.svg")


def _smooth(path: Path, level: int) -> None:
    """Mesh smoothness glyphs: 1 a hexagon outline (no smoothing), 2 the
    hexagon with a circle inside (cage + smooth), 3 a circle (smooth)."""
    import math
    u, m, d = g._canvas()
    w = int(u * 0.06)
    c, r = u / 2, u * 0.40
    if level in (1, 2):
        pts = [(c + r * math.cos(math.radians(30 + 60 * i)),
                c + r * math.sin(math.radians(30 + 60 * i))) for i in range(6)]
        d.line(pts + pts[:1], fill=255, width=w, joint="curve")
    if level in (2, 3):
        rr = r * (0.62 if level == 2 else 0.95)
        d.ellipse([c - rr, c - rr, c + rr, c + rr], outline=255, width=w)
    g._save_mask(m, path)


# The logo's M at 32 px: 1 px diagonals that the 1-bit trace breaks up. Drawn
# here as a pixel map instead (X = knocked out of the front tile), placed at
# column 6, row 4 so it is centred on the tile (columns 1..28).
MAYA_M = """\
XXXXX........XXXXX
XXXXXX......XXXXXX
XXXXXXX....XXXXXXX
XXXX.XXX..XXX.XXXX
XXXX..XXXXXX..XXXX
XXXX...XXXX...XXXX
XXXX....XX....XXXX
XXXX..........XXXX
XXXX..........XXXX
XXXX..........XXXX
XXXX..........XXXX
XXXX..........XXXX
XXXX..........XXXX
XXXX..........XXXX"""


def _nudge(path: Path, direction: str) -> None:
    """Move one pixel: a small filled square (the pixel) and a short arrow
    leaving it, pointing up, down, left or right. Drawn for the up direction
    and rotated."""
    u, m, d = g._canvas()
    s = u * 0.11
    cx = u / 2
    d.rectangle([cx - s, u * 0.70, cx + s, u * 0.70 + 2 * s], fill=255)
    t, h = u * 0.045, u * 0.16
    d.rectangle([cx - t, u * 0.30, cx + t, u * 0.58], fill=255)
    d.polygon([(cx, u * 0.12), (cx - h, u * 0.12 + h), (cx + h, u * 0.12 + h)], fill=255)
    angle = {"up": 0, "left": 90, "down": 180, "right": 270}[direction]
    g._save_mask(m.rotate(angle), path)


def _maya_mark(path: Path) -> None:
    """The ESC mark, 32x32 1-bit, WHITE on transparent (the spec uses
    program_icon_mode: alpha).

    The two plates are the first two sub-paths of the Simple Icons
    ``autodeskmaya`` path (CC0-1.0), rendered at 256 px and reduced to 32 px.
    The sub-paths after them are the M and the word MAYA: the word is 3 px tall
    at this size and the M's diagonals break apart, so both are left out and
    the M is knocked out of the front plate from ``MAYA_M``."""
    import io
    import re
    import urllib.request
    import cairosvg
    import numpy as np
    req = urllib.request.Request(MAYA_ICON_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        svg = r.read().decode("utf-8")
    d = re.search(r'd="([^"]+)"', svg).group(1)
    plates = "".join(re.split(r"(?<=[zZ])", d)[:2])
    png = cairosvg.svg2png(bytestring=svg.replace(d, plates).encode("utf-8"),
                           output_width=256, output_height=256)
    alpha = Image.open(io.BytesIO(png)).convert("RGBA").split()[3]
    on = np.asarray(alpha.resize((32, 32), Image.LANCZOS)) >= 128
    for j, row in enumerate(MAYA_M.splitlines()):
        for i, c in enumerate(row):
            if c == "X":
                on[4 + j, 6 + i] = False
    a = (on * 255).astype(np.uint8)
    Image.fromarray(np.dstack([a, a, a, a]), "RGBA").save(path)


def _save_white(m: Image.Image, path: Path) -> None:
    """White on transparent, the alpha channel taken from the 1-bit mask `m`."""
    img = Image.new("RGBA", m.size, (255, 255, 255, 0))
    img.putalpha(m.point(lambda v: 255 if v else 0))
    img.save(path)


# 4, 5 and 6 show one sphere three ways: the same 30 px disc at the same place,
# drawn at the 36x32 key size so the generator copies it 1:1.
_SW, _SH, _SCX, _SCY, _SR = 36, 32, 18, 15.5, 15


def _sphere_grid():
    """Pixel grid of the sphere: x, y on the unit disc, the inside mask, the
    surface normal's z, and the 1-px outline."""
    import numpy as np
    from PIL import ImageDraw
    yy, xx = np.mgrid[0:_SH, 0:_SW]
    x, y = (xx - _SCX) / _SR, (yy - _SCY) / _SR
    r2 = x ** 2 + y ** 2
    ring = Image.new("L", (_SW, _SH), 0)
    ImageDraw.Draw(ring).ellipse([_SCX - _SR, _SCY - _SR, _SCX + _SR, _SCY + _SR], outline=255)
    return xx, yy, x, y, r2 <= 1.0, np.sqrt(np.clip(1 - r2, 0, 1)), np.array(ring) > 0


def _save_bool(mask, path: Path) -> None:
    import numpy as np
    _save_white(Image.fromarray(np.asarray(mask, bool).astype("uint8") * 255), path)


def _wireframe(path: Path) -> None:
    """Wireframe (4): the sphere outline with one ring each way."""
    from PIL import ImageDraw
    m = Image.new("L", (_SW, _SH), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([_SCX - _SR, _SCY - _SR, _SCX + _SR, _SCY + _SR], outline=255)
    d.ellipse([_SCX - _SR, _SCY - 5, _SCX + _SR, _SCY + 5], outline=255)
    d.ellipse([_SCX - 7, _SCY - _SR, _SCX + 7, _SCY + _SR], outline=255)
    _save_white(m, path)


def _shaded(path: Path) -> None:
    """Shaded (5): the sphere lit from the upper left (Lambert), reduced to
    1 bit with a 4x4 ordered dither, inside its outline."""
    import numpy as np
    xx, yy, x, y, inside, z, ring = _sphere_grid()
    light = np.array([-0.55, -0.55, 0.63])
    light /= np.linalg.norm(light)
    lit = np.clip(x * light[0] + y * light[1] + z * light[2], 0, 1)
    bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16
    _save_bool(((lit > bayer[yy % 4, xx % 4] * 0.9 + 0.05) & inside) | ring, path)


def _textured(path: Path) -> None:
    """Shaded and textured (6): a checker texture wrapped on the sphere, 8
    tiles round the longitude and 6 over the latitude, inside its outline."""
    import numpy as np
    _, _, x, y, inside, z, ring = _sphere_grid()
    lon, lat = np.arctan2(x, z), np.arcsin(np.clip(-y, -1, 1))
    checker = (np.floor(lon / (np.pi / 4)) + np.floor(lat / (np.pi / 6))) % 2 == 0
    _save_bool((checker & inside) | ring, path)


def _space_hotbox(path: Path) -> None:
    """Space (hold): the hotbox, menu rows above and below a centre box with a
    marking-menu bar on each side. Drawn on the whole 72x40 keycap at the top
    right: Space is on the thumb row, where the firmware centres the legend
    (x 23..48, y 23..26) and clears it within 3 px of overlay ink, so the glyph
    stays in rows 1..18."""
    from PIL import ImageDraw
    m = Image.new("L", (72, 40), 0)
    d = ImageDraw.Draw(m)
    x0, y0 = 72 - 26, 1
    for y in (0, 3, 14, 17):
        for x in (0, 9, 18):
            d.line([(x0 + x, y0 + y), (x0 + x + 7, y0 + y)], fill=255)
    for y in (8, 9):
        d.line([(x0, y0 + y), (x0 + 6, y0 + y)], fill=255)
        d.line([(x0 + 19, y0 + y), (x0 + 25, y0 + y)], fill=255)
    d.rectangle([x0 + 11, y0 + 6, x0 + 14, y0 + 11], outline=255)
    _save_white(m, path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(ICONS, out)
    icon_fetch.borrow(BORROW, out)
    for lvl in (1, 2, 3):
        g.guarded(out / f"smooth{lvl}.png", lambda p, k=lvl: _smooth(p, k), f"drawn smoothness {lvl}")
    g.guarded(out / "wireframe.png", _wireframe, "drawn wire sphere")
    g.guarded(out / "shaded.png", _shaded, "drawn dithered sphere")
    g.guarded(out / "textured.png", _textured, "drawn checker sphere")
    g.guarded(out / "space_hotbox.png", _space_hotbox, "drawn hotbox (Space, hold), 72x40")
    for dr in ("up", "down", "left", "right"):
        g.guarded(out / f"nudge_{dr}.png", lambda p, k=dr: _nudge(p, k), f"drawn nudge ({dr})")
    for name, base, badge in BADGES:
        g.guarded(out / name, lambda p, a=base, b=badge: g.with_badge(out / a, out / b, p),
                  f"composite ({base} + {badge})")
    for name, base, fwd in ARROWS:
        g.guarded(out / name, lambda p, a=base, f=fwd: g.with_arrow(out / a, p, f),
                  f"composite ({base} + arrow)")
    g.guarded(out / "maya.png", _maya_mark, "simple-icons/autodeskmaya plates (CC0) + drawn M, 32x32")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
