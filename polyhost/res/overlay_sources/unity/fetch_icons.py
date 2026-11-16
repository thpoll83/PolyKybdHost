#!/usr/bin/env python3
"""Fetch + render the Unity Editor shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). Icons another 3D set
already draws (frame, keyframe, wireframe, shading) are copied from
`../blender/icons` so both sets show the same pixels. Text labels for the
render modes and 2D mode are drawn here in Liberation Sans Bold. The ESC mark is
the Unity logo from Simple Icons (CC0 artwork; nominative use, see
`../brand_marks.py`).

    pip install cairosvg
    PYTHONPATH=. python polyhost/res/overlay_sources/unity/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from polyhost.res.overlay_sources import brand_marks, dcc_glyphs, icon_fetch  # noqa: E402

FLUENT = {
    # --- File ---
    "newscene": "Document Add",
    "openscene": "Folder Open",
    "save": "Save",
    "saveas": "Save Edit",
    "buildrun": "Rocket",
    "buildprofiles": "Box Multiple",
    # --- Edit ---
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "pastechild": "Clipboard Arrow Right",
    "duplicate": "Copy Add",
    "selectall": "Select All On",
    "deselectall": "Select All Off",
    "find": "Search",
    "searchall": "Search Square",
    "delete": "Delete",
    "refresh": "Arrow Sync",
    "undohistory": "History",
    "prevselection": "Arrow Circle Left",
    "nextselection": "Arrow Circle Right",
    "selectchildren": "ms:subdirectory_arrow_right",
    "prefabroot": "ms:deployed_code_update",
    "prefabmode": "ms:deployed_code",
    # --- Play mode ---
    "play": "Play",
    "pause": "Pause",
    "step": "Next",
    # --- GameObject ---
    "createempty": "Cube Add",
    "emptychild": "ms:add_link",
    "emptyparent": "ms:account_tree",
    "movetoview": "ms:control_camera",
    "alignview": "ms:switch_video",
    "toggleactive": "Checkbox Checked",
    "firstsibling": "ms:vertical_align_top",
    "lastsibling": "ms:vertical_align_bottom",
    # --- Window ---
    "win_scene": "Cube",
    "win_game": "Games",
    "win_inspector": "Info",
    "win_hierarchy": "Text Bullet List Tree",
    "win_project": "Folder",
    "win_animation": "Filmstrip",
    "win_profiler": "Gauge",
    "win_audiomixer": "ms:tune",
    "win_lighting": "Lightbulb",
    "win_services": "Cloud",
    "win_console": "Window Console",
    "maximize": "Full Screen Maximize",
    # --- Tools ---
    "tool_view": "Hand Left",
    "tool_move": "Arrow Move",
    "tool_rotate": "Arrow Rotate Clockwise",
    "tool_scale": "ms:open_in_full",
    "tool_rect": "ms:crop_square",
    "tool_transform": "ms:transform",
    "pivotpos": "ms:adjust",
    "pivotrot": "Globe",
    "lockview": "Lock Closed",
    "visibility": "Eye",
    "isolate": "ms:filter_center_focus",
    "picking": "Cursor Click",
    "keyselected": "Key",
    "keymodified": "Key Multiple",
    # --- Scene view ---
    "snapping": "ms:grid_4x4",
    "pushgrid": "ms:straighten",
    "aligngrid": "ms:grid_guides",
    "gridreset": "ms:restart_alt",
    "gridtoobject": "ms:move_down",
    "gridtoobjectrot": "ms:rotate_90_degrees_cw",
    "gridtohandle": "ms:pan_tool_alt",
    "gridtohandlerot": "ms:rotate_right",
    "vertexsnap": "ms:polyline",
    "vertexsnaptoggle": "ms:timeline",
    "toolsettings": "Settings",
    "overlaymenu": "Layer",
    "overlaystoggle": "Layer Diagonal",
    "fly_up": "Arrow Up",
    "fly_down": "Arrow Down",
    "fly_left": "Arrow Left",
    "fly_right": "Arrow Right",
    # --- Animation window ---
    "curves": "ms:show_chart",
    "ripple": "ms:waves",
    "rippletoggle": "ms:water",
    # --- Timeline window ---
    "tl_split": "Split Vertical",
    "tl_trimstart": "ms:align_horizontal_left",
    "tl_trimend": "ms:align_horizontal_right",
    "zoom_in": "Zoom In",
    "zoom_out": "Zoom Out",
    "tl_multileft": "ms:keyboard_double_arrow_left",
    "tl_multiright": "ms:keyboard_double_arrow_right",
    "tl_multiup": "ms:keyboard_double_arrow_up",
    "tl_multidown": "ms:keyboard_double_arrow_down",
    "tl_area": "ms:keyboard_tab",
    "tl_match": "ms:fit_width",
    "tl_jog": "ms:swipe",
    "tl_mix": "ms:join",
    "tl_replace": "ms:swap_horiz",
    # --- one icon per action (2026-11-15) ---
    "playpreview": "ms:play_pause",
    # --- Search window (2026-11-16) ---
    "srch_builder": "ms:extension",
    "srch_rename": "Rename",
    "srch_saved": "Bookmark Multiple",
    "srch_inspector": "Panel Right",
    "srch_newline": "ms:keyboard_return",
    # parts of the composites below, not drawn on their own
    "part_tab": "ms:tab",
    "part_add": "Add",
    "part_subtract": "Subtract",
    "part_select": "Select Object",
}

# Composites (output, base, badge): dcc_glyphs.with_badge, base upper left,
# badge lower right.
BADGES = [
    ("gridbigger_plus.png", "snapping.png", "part_add.png"),
    ("gridsmaller_minus.png", "snapping.png", "part_subtract.png"),
    ("tl_select_left.png", "fly_left.png", "part_select.png"),
    ("tl_select_right.png", "fly_right.png", "part_select.png"),
    ("tl_select_up.png", "fly_up.png", "part_select.png"),
    ("tl_select_down.png", "fly_down.png", "part_select.png"),
    # one icon per action (2026-11-16): Lock track and Apply last grid values
    # each looked the same as another key (Lock view to selected, Undo history).
    ("tl_locktrack.png", "lockview.png", "part_tracks.png"),
    ("gridlast.png", "snapping.png", "undohistory.png"),
    # Search window
    ("srch_refresh.png", "find.png", "refresh.png"),
    ("srch_older.png", "find.png", "fly_up.png"),
    ("srch_newer.png", "find.png", "fly_down.png"),
    ("srch_tab_prev.png", "part_tab.png", "fly_left.png"),
    ("srch_tab_next.png", "part_tab.png", "fly_right.png"),
    ("srch_toblocks.png", "srch_builder.png", "part_add.png"),
]

# Drawn by the Blender set already: copy, so both show the same pixels.
BORROW = {
    "frame_all.png": "blender",
    "fit_view.png": "blender",
    "frame_next.png": "blender",
    "frame_prev.png": "blender",
    "jump_start.png": "blender",
    "jump_end.png": "blender",
    "key_next.png": "blender",
    "key_prev.png": "blender",
    "wireframe.png": "blender",
    "shading.png": "blender",
    "select_invert.png": "blender",
    "key_delete.png": "blender",
    "mute.png": "blender",
}

# Scene view render modes and 2D mode: no icon set has a glyph for them.
LETTERS = {
    "mode2d.png": "2D",
    "rm_unlit.png": "UL",
    "rm_shadedwire.png": "SW",
    "rm_debug.png": "DB",
}


def _label(path: Path, text: str) -> None:
    """``text`` in bold, black on transparent, 96 px (supersampled 4x), the
    same convention as `dcc_glyphs`: the alpha is the shape."""
    px, ss = 96, 4
    u = px * ss
    m = Image.new("L", (u, u), 0)
    f = ImageFont.truetype(dcc_glyphs.BOLD, int(u * (0.62 if len(text) <= 2 else 0.42)))
    ImageDraw.Draw(m).text((u * 0.5, u * 0.5), text, fill=255, font=f, anchor="mm")
    m = m.resize((px, px), Image.LANCZOS)
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    img.putalpha(m)
    img.save(path)


def _key_at_edge(path: Path, first: bool) -> None:
    """A filled keyframe diamond against a bar: the bar on the left for "first
    keyframe", on the right for "last keyframe". Black on transparent, 96 px."""
    u, m, d = dcc_glyphs._canvas()
    cy, r = u // 2, int(u * 0.30)
    bar_w = int(u * 0.09)
    if first:
        bx = int(u * 0.12)
        cx = bx + bar_w + int(u * 0.06) + r
    else:
        bx = u - int(u * 0.12) - bar_w
        cx = bx - int(u * 0.06) - r
    d.rectangle([bx, cy - r, bx + bar_w, cy + r], fill=255)
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=255)
    dcc_glyphs._save_mask(m, path)


def _tracks(path: Path) -> None:
    """Three track lanes, each with a clip at a different start: the badge of
    Lock track. Black on transparent, 96 px."""
    u, m, d = dcc_glyphs._canvas()
    h, gap = int(u * 0.20), int(u * 0.14)
    top = (u - 3 * h - 2 * gap) // 2
    for i, x0 in enumerate((0.0, 0.30, 0.12)):
        y = top + i * (h + gap)
        d.rectangle([int(u * x0), y, u - 1, y + h - 1], fill=255)
    dcc_glyphs._save_mask(m, path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.borrow(BORROW, out)
    for name, text in sorted(LETTERS.items()):
        dcc_glyphs.guarded(out / name, lambda p, t=text: _label(p, t), f"drawn label {text!r}")
    dcc_glyphs.guarded(out / "part_tracks.png", _tracks, "drawn track lanes")
    for name, base, badge in BADGES:
        dcc_glyphs.guarded(out / name,
                           lambda p, b=out / base, s=out / badge: dcc_glyphs.with_badge(b, s, p),
                           f"composite ({base} + {badge})")
    dcc_glyphs.guarded(out / "key_first.png", lambda p: _key_at_edge(p, True), "drawn bar + keyframe")
    dcc_glyphs.guarded(out / "key_last.png", lambda p: _key_at_edge(p, False), "drawn keyframe + bar")
    brand_marks.ensure(out / "unity.png", "unity")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
