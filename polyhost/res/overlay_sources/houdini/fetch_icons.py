#!/usr/bin/env python3
"""Fetch + render the SideFX Houdini shortcut icons (reproducible source step).

Glyphs are Google Material Symbols (Apache-2.0, ``ms:`` names) and Microsoft
Fluent UI System Icons (MIT), rendered through ``../icon_fetch.py``. Glyphs that
mean the same as in a sibling set are copied byte-identical from it
(``BORROW``). The keyframe composites ("key translations", "key handle") and
the vertex selection glyph are drawn here with ``../dcc_glyphs.py``.

The ESC mark is the Houdini logo from Simple Icons (``houdini``, artwork
CC0-1.0) reduced to a 32x32 1-bit trace. See SOURCES.md.

    pip install cairosvg Pillow numpy
    PYTHONPATH=. python polyhost/res/overlay_sources/houdini/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from PIL import Image  # noqa: E402

from polyhost.res.overlay_sources import dcc_glyphs as g  # noqa: E402
from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

ICONS = {
    # --- viewport tools and selection
    "select_tool": "ms:arrow_selector_tool",
    "display_options": "ms:display_settings",
    "sel_object": "ms:deployed_code",
    "sel_particles": "ms:grain",
    "sel_dynamics": "ms:cyclone",
    "sel_boundary": "ms:border_outer",
    "secure_select": "ms:shield_lock",
    "sel_pattern": "ms:pattern",
    "tool_parms": "ms:settings_applications",
    "radial_current": "ms:hub",
    # --- panes and tabs
    "tab_new": "ms:tab_new_right",
    "tab_close": "ms:tab_close",
    "tab_tearoff": "ms:open_in_new",
    "details_view": "ms:table_view",
    # --- composite inputs (no binding draws them directly)
    "selectall": "Select All On",
    "camera": "ms:videocam",
}

# Same action as in a sibling set: a byte-identical copy.
BORROW = {
    "move.png": "blender",            # T: move tool
    "rotate.png": "blender",          # R: rotate tool
    "scale.png": "blender",           # E: scale tool
    "gizmo.png": "blender",           # Enter: show the node's handles
    "shading.png": "3dsmax",          # W: shaded / wireframe
    "edit_mode.png": "3dsmax",        # F8: object / component selection
    "sel_vert.png": "blender",        # 2: points
    "sel_edge.png": "blender",        # 3: edges
    "sel_face.png": "blender",        # 4: primitives (faces)
    "deselect.png": "blender",        # Shift+N: select nothing
    "key_insert.png": "3dsmax",       # K: set keyframe
    "autokey.png": "3dsmax",          # Alt+K: auto-key
    "play.png": "3dsmax",
    "play_reverse.png": "blender",
    "frame_next.png": "3dsmax",
    "frame_prev.png": "blender",
    "jump_start.png": "3dsmax",       # Ctrl+Up: first frame
    "key_next.png": "blender",        # Ctrl+Right: next keyframe
    "key_prev.png": "blender",        # Ctrl+Left: previous keyframe
    "snap.png": "blender",            # X: snapping menu
    "view_pie.png": "blender",        # V: view radial menu
    "frame_all.png": "blender",       # Shift+A: home all
    "walk.png": "3dsmax",             # M: first-person navigation
    "pivot.png": "3dsmax",            # Insert: pivot handle
    "nodesearch.png": "nuke",         # Tab: add a node from the menu
    "tab_next.png": "nuke",
    "tab_prev.png": "nuke",
    "closeall.png": "cinema4d",       # Alt+/: close all tabs
    "view_persp.png": "cinema4d",     # Alt+1, Alt+9: Scene View
    "nodeeditor.png": "cinema4d",     # Alt+2: Network Editor
    "attributes.png": "cinema4d",     # Alt+3: Parameters
    "objectmanager.png": "cinema4d",  # Alt+4: Tree View
    "materialmanager.png": "cinema4d",  # Alt+7: Material Palette
    "ed_console.png": "blender",      # Alt+5: Textport
    "ed_graph.png": "blender",        # Alt+6: Animation Editor
    "new.png": "cinema4d",
    "open.png": "cinema4d",
    "save.png": "cinema4d",
    "undo.png": "cinema4d",
}

HOUDINI_ICON_URL = "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/houdini.svg"


def _sel_vertex(path: Path) -> None:
    """Houdini's vertex: a primitive's corner reference, not a point. A face
    outline with a dot inside each corner, so it reads apart from the point
    glyph (``sel_vert``: filled squares ON the corners)."""
    from PIL import ImageDraw
    u = g.PX * g.SS
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    a, b = int(u * 0.12), int(u * 0.88)
    d.rectangle([a, a, b, b], outline=255, width=int(u * 0.06))
    r, i = int(u * 0.085), int(u * 0.27)
    for cx, cy in ((i, i), (u - i, i), (i, u - i), (u - i, u - i)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    g._save_mask(m, path)


def _badge_key(path: Path) -> None:
    """A filled keyframe diamond, the badge of the "key X" composites. The
    key_insert glyph has a plus beside the diamond, and at badge size the two
    merge into one blob."""
    from PIL import ImageDraw
    u = g.PX * g.SS
    m = Image.new("L", (u, u), 0)
    c, r = u / 2, u * 0.48
    ImageDraw.Draw(m).polygon([(c, c - r), (c + r, c), (c, c + r), (c - r, c)], fill=255)
    g._save_mask(m, path)


def _badge_pin(path: Path) -> None:
    """A filled push pin (head, collar, needle), the badge of "pin camera".
    The outline pin from the Blender set is too thin at badge size."""
    from PIL import ImageDraw
    u = g.PX * g.SS
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    d.rectangle([u * 0.30, u * 0.04, u * 0.70, u * 0.44], fill=255)
    d.rectangle([u * 0.14, u * 0.44, u * 0.86, u * 0.60], fill=255)
    d.rectangle([u * 0.43, u * 0.60, u * 0.57, u * 0.98], fill=255)
    g._save_mask(m, path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(ICONS, out)
    icon_fetch.borrow(BORROW, out)
    g.guarded(out / "sel_vertex.png", _sel_vertex, "drawn vertex selection glyph")
    g.guarded(out / "badge_key.png", _badge_key, "drawn keyframe diamond (badge)")
    g.guarded(out / "badge_pin.png", _badge_pin, "drawn push pin (badge)")
    # Keyframe composites: the transform glyph with a keyframe diamond badge.
    for name, base in (("key_move", "move"), ("key_rotate", "rotate"),
                       ("key_scale", "scale"), ("key_handle", "gizmo")):
        g.guarded(out / f"{name}.png",
                  lambda p, b=base: g.with_badge(out / f"{b}.png", out / "badge_key.png", p),
                  f"{base} + key badge")
    g.guarded(out / "pin_camera.png",
              lambda p: g.with_badge(out / "camera.png", out / "badge_pin.png", p),
              "camera + pin badge")
    g.guarded(out / "houdini.png",
              lambda p: g.trace_mark(g.svg_icon(HOUDINI_ICON_URL), p, lit="dark"),
              "simple-icons/houdini (CC0), 32x32 trace")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
