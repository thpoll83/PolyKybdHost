#!/usr/bin/env python3
"""Fetch + render the Blender overlay icons (reproducible).

Every stem `actions.yaml` names lives here. Three sources:

* **Google Material Symbols (Apache-2.0)** for most glyphs, via the shared
  `icon_fetch` helper (`ms:<name>`, weight 300). Blender's vocabulary (pivot,
  orientation, X-ray, loop cut, face sets, ...) is far outside the editing
  concepts Fluent covers, and Material's much larger set fits it more often.
* **Drawn here**, black on transparent so they render in the spec's `luma`
  mode like the fetched glyphs: the vertex / edge / face select-mode tiles and
  the keyframe diamonds, which no icon set draws the way Blender does, and the
  snapping magnet, which neither Fluent nor Material has. The
  program mark is white on transparent (`program_icon_mode: alpha`).
  Three drawn glyphs are BORROWED byte-identical from sibling apps so the shared
  icon library stores them once (brush size -/+ from photoshop, swap colours
  from gimp); they are white-on-transparent, so their actions.yaml entries say
  `mode: alpha` -- in `luma` they would render as EMPTY cells.

The ESC program mark is a generic "Bl" tile, NOT Blender's logo -- see
SOURCES.md for the logo-policy reading behind that.

    pip install cairosvg
    python polyhost/res/overlay_sources/blender/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402

PX = icon_fetch.RENDER_PX

# stem -> icon_fetch spec ("ms:<material name>" or a Fluent folder name).
ICONS = {
    # --- file / window
    "recent": "ms:history", "save_incremental": "ms:difference", "favorites": "ms:star",
    "rename": "ms:edit", "batch_rename": "ms:edit_note", "search": "ms:search",
    "file_menu": "ms:draft", "tools": "ms:handyman", "preferences": "ms:settings",
    # --- editors (Shift+F1..F12)
    "ed_files": "ms:folder_open", "ed_clip": "ms:movie", "ed_node": "ms:account_tree",
    "ed_console": "ms:terminal", "ed_view3d": "ms:deployed_code", "ed_graph": "ms:show_chart",
    "ed_properties": "ms:build", "ed_sequencer": "ms:video_library", "ed_outliner": "ms:list",
    "ed_image": "ms:image", "ed_text": "ms:description", "ed_dopesheet": "ms:view_timeline",
    # --- screen
    "tab_next": "ms:tab", "tab_prev": "ms:tab_unselected",
    "workspace_next": "ms:arrow_right_alt", "workspace_prev": "ms:arrow_left_alt",
    "quadview": "ms:window", "repeat": "ms:repeat", "render": "ms:photo_camera",
    "render_anim": "ms:videocam", "render_seq": "ms:movie_edit", "render_seq_anim": "ms:slideshow",
    "render_view": "ms:monitor", "play_rendered": "ms:smart_display",
    "maximize": "ms:web_asset", "adjust_last": "ms:settings_backup_restore",
    # --- frames / timeline
    "frame_prev": "ms:chevron_left", "frame_next": "ms:chevron_right",
    "jump_start": "ms:first_page", "jump_end": "ms:last_page",
    "time_back": "ms:fast_rewind", "time_fwd": "ms:fast_forward",
    "play": "ms:play_arrow", "preview_range": "ms:date_range",
    "preview_range_clear": "ms:event_busy", "seconds": "ms:timer",
    # --- view
    "zoom_region": "ms:zoom_in_map", "panel_left": "ms:left_panel_open",
    "panel_right": "ms:right_panel_open", "overlays": "ms:stacks", "gizmo": "ms:control_camera",
    "localview": "ms:center_focus_weak", "localview_remove": "ms:playlist_remove",
    "dolly_in": "ms:north", "dolly_out": "ms:south", "frame_all": "ms:zoom_out_map",
    "frame_cursor": "ms:filter_center_focus", "view_pie": "ms:pie_chart",
    "walk": "ms:directions_walk", "select_box": "ms:select", "select_circle": "ms:panorama_fish_eye",
    "clip_region": "ms:crop", "render_region": "ms:crop_landscape",
    "render_region_clear": "ms:hide_image",
    "snap_options": "ms:settings_input_component", "snap_cursor": "ms:my_location",
    "pivot": "ms:trip_origin", "orientation": "ms:explore", "shading": "ms:contrast",
    "wireframe": "ms:grid_on", "xray": "ms:radiology", "fit_view": "ms:fit_screen",
    # --- modes
    "edit_mode": "ms:edit_square", "transfer_mode": "ms:move_up", "mode_pie": "ms:donut_large",
    # --- transform
    "move": "ms:open_with", "rotate": "ms:rotate_right", "scale": "ms:open_in_full",
    "mirror": "ms:flip", "shear": "ms:transform", "bend": "ms:turn_slight_right",
    "tosphere": "ms:circle", "shrink_fatten": "ms:unfold_more", "crease": "ms:filter_hdr",
    "vert_slide": "ms:commit", "bbone": "ms:line_weight", "time_extend": "ms:width_wide",
    "time_slide": "ms:swipe",
    # --- selection
    "deselect": "ms:deselect", "select_invert": "ms:flip_to_back", "hide_others": "ms:disabled_visible",
    "reveal": "ms:visibility", "select_linked": "ms:schema", "hier_parent": "ms:arrow_upward",
    "hier_child": "ms:arrow_downward", "select_grouped": "ms:category", "select_similar": "ms:compare",
    "select_left": "ms:keyboard_tab_rtl", "select_right": "ms:start", "column": "ms:view_column",
    "column_markers": "ms:view_week", "island": "ms:landscape", "selection_sets": "ms:bookmarks",
    # --- object
    "duplicate": "ms:control_point_duplicate", "duplicate_linked": "ms:dynamic_feed",
    "parent": "ms:supervisor_account", "parent_clear": "ms:person_remove",
    "separate": "ms:call_split", "split": "ms:vertical_split", "paste_flipped": "ms:content_paste_go",
    "falloff": "ms:blur_linear", "proportional": "ms:radar", "proportional_connected": "ms:hub",
    "delete_global": "ms:delete_forever", "clear_loc": "ms:location_off",
    "clear_rot": "ms:sync_disabled", "clear_scale": "ms:photo_size_select_small",
    "axis_target": "ms:target", "add": "ms:add_box", "apply": "ms:done_all", "link": "ms:link",
    "join": "ms:join", "origin": "ms:adjust", "collection_new": "ms:create_new_folder",
    "collection_add": "ms:library_add", "collection_remove": "ms:folder_delete",
    "collection_remove_all": "ms:delete_sweep", "collection_move": "ms:drive_file_move",
    "collection_link": "ms:snippet_folder", "collection_hide": "ms:folder_off",
    "subdiv": "ms:grid_4x4", "subdiv_up": "ms:exposure_plus_1", "subdiv_down": "ms:exposure_neg_1",
    "context_menu": "ms:menu_open", "keying_set": "ms:key",
    # --- edit mesh
    "loopcut": "ms:horizontal_split", "offset_loop": "ms:view_stream", "inset": "ms:filter_frames",
    "bevel": "ms:rounded_corner", "bevel_vert": "ms:hexagon", "extrude": "ms:upload",
    "make_face": "ms:pentagon", "fill": "ms:format_color_fill", "knife": "ms:restaurant",
    "connect": "ms:polyline", "rip": "ms:link_off", "dissolve": "ms:grain",
    "normals": "ms:arrow_outward", "normals_in": "ms:call_received", "triangulate": "ms:change_history",
    "quads": "ms:grid_view", "vgroup": "ms:workspaces", "vgroup_remove": "ms:group_remove",
    "merge": "ms:merge", "hook": "ms:phishing", "uv_unwrap": "ms:map",
    # --- armature / pose
    "align": "ms:align_horizontal_left", "bone_add": "ms:add_circle",
    "extrude_forked": "ms:fork_right", "switch_dir": "ms:swap_horizontal_circle",
    "bone_options": "ms:checklist", "blend_neighbor": "ms:compare_arrows", "breakdown": "ms:tune",
    "push": "ms:compress", "relax": "ms:spa", "constraint": "ms:anchor",
    "constraint_clear": "ms:do_not_disturb_on", "ik": "ms:accessibility_new", "ik_clear": "ms:person_off",
    "flip_quat": "ms:swap_vert", "rotation_mode": "ms:360", "propagate": "ms:keyboard_double_arrow_right",
    # --- sculpt / paint
    "radius": "ms:radio_button_checked", "strength": "ms:fitness_center", "weight": "ms:weight",
    "tex_angle": "ms:rotate_90_degrees_ccw", "eyedropper": "ms:colorize", "stroke": "ms:draw",
    "smooth_stroke": "ms:gesture", "brushes": "ms:palette", "br_draw": "ms:brush",
    "br_clay": "ms:texture", "br_grab": "ms:pan_tool", "br_inflate": "ms:bubble_chart",
    "br_mask": "ms:theater_comedy", "br_pinch": "ms:pinch", "br_scrape": "ms:cleaning_services",
    "br_smooth": "ms:blur_on", "br_snake": "ms:route", "remesh": "ms:view_quilt",
    "voxel_size": "ms:straighten", "mask_box": "ms:check_box_outline_blank",
    "mask_invert": "ms:invert_colors", "mask_clear": "ms:layers_clear", "grow": "ms:expand_content",
    "shrink": "ms:close_fullscreen", "fill_color": "ms:format_paint", "mask_expand": "ms:unfold_more_double",
    "faceset_expand": "ms:open_in_new", "faceset_hide": "ms:hide_source",
    "faceset_isolate": "ms:center_focus_strong", "automask": "ms:auto_fix_high",
    "faceset": "ms:auto_awesome_mosaic", "gradient": "ms:gradient", "gradient_radial": "ms:blur_circular",
    "lock_pie": "ms:lock_open",
    # --- node editor
    "backdrop_zoom_in": "ms:zoom_in", "backdrop_zoom_out": "ms:zoom_out", "node_detach": "ms:ios_share",
    "group_enter": "ms:subdirectory_arrow_right", "group_exit": "ms:subdirectory_arrow_left",
    "group": "ms:inventory_2", "ungroup": "ms:unarchive", "sockets": "ms:settings_input_hdmi",
    "collapse": "ms:unfold_less", "frame_node": "ms:crop_square", "link_replace": "ms:sync_alt",
    "mute": "ms:block", "node_preview": "ms:thumbnail_bar", "refresh": "ms:refresh",
    "linked_from": "ms:input", "linked_to": "ms:output", "same_next": "ms:navigate_next",
    "same_prev": "ms:navigate_before", "viewer": "ms:preview", "viewer_store": "ms:bookmark_add",
    "swap": "ms:swap_horiz",
    # --- image / uv
    "render_slot": "ms:auto_awesome_motion", "image_new": "ms:add_photo_alternate",
    "image_open": "ms:photo_library", "image_save": "ms:save", "image_save_as": "ms:save_as",
    "seam": "ms:line_end", "pin": "ms:push_pin", "unpin": "ms:keep_off", "stitch": "ms:join_inner",
    # --- dope sheet / graph
    "bake": "ms:local_fire_department", "easing": "ms:moving", "extrapolation": "ms:trending_flat",
    "handle": "ms:line_curve", "interpolation": "ms:timeline", "lock_channel": "ms:lock",
    "filter": "ms:filter_alt", "marker": "ms:flag", "camera_bind": "ms:linked_camera",
    "samples": "ms:scatter_plot", "modifier": "ms:build_circle",
}

# Borrowed drawn glyphs: byte-identical copies from sibling apps.
BORROWED = {"brushdec.png": "photoshop", "brushinc.png": "photoshop", "swapcolors.png": "gimp"}


# ------------------------------------------------------------------ drawn glyphs
def _canvas():
    ss = 4
    u = PX * ss
    return u, Image.new("L", (u, u), 0)


def _save(m: Image.Image, path: Path) -> None:
    a = np.asarray(m.resize((PX, PX), Image.LANCZOS)).astype(np.uint8)
    rgba = np.zeros((PX, PX, 4), np.uint8)
    rgba[..., :3] = 0          # black on transparent: renders in the spec's luma mode
    rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save(path)


def _select_mode(path: Path, which: str) -> None:
    """Blender's select-mode tiles: a square whose vertices, one edge, or face lights."""
    u, m = _canvas()
    d = ImageDraw.Draw(m)
    a, b = 0.18 * u, 0.82 * u
    w = int(u * 0.045)
    if which == "face":
        d.rectangle([a, a, b, b], fill=255)
        return _save(m, path)
    d.rectangle([a, a, b, b], outline=255, width=w)
    if which == "edge":
        d.rectangle([a - w, b - 2.4 * w, b + w, b + w], fill=255)
    if which == "vert":
        r = 0.10 * u
        for x, y in ((a, a), (b, a), (a, b), (b, b)):
            d.rectangle([x - r, y - r, x + r, y + r], fill=255)
    _save(m, path)


def _diamond(d, cx, cy, s, fill=True, w=0):
    pts = [(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)]
    if fill:
        d.polygon(pts, fill=255)
    else:
        d.polygon(pts, outline=255, width=w)


def _key(path: Path, kind: str) -> None:
    """Keyframe diamonds, Blender's own keyframe vocabulary."""
    u, m = _canvas()
    d = ImageDraw.Draw(m)
    w = int(u * 0.06)
    if kind == "insert":
        _diamond(d, 0.40 * u, 0.50 * u, 0.30 * u)
        d.rectangle([0.70 * u, 0.20 * u, 0.80 * u, 0.50 * u], fill=255)
        d.rectangle([0.60 * u, 0.30 * u, 0.90 * u, 0.40 * u], fill=255)
    elif kind == "delete":
        _diamond(d, 0.40 * u, 0.50 * u, 0.30 * u)
        d.rectangle([0.60 * u, 0.20 * u, 0.92 * u, 0.30 * u], fill=255)
    elif kind == "menu":
        _diamond(d, 0.50 * u, 0.42 * u, 0.30 * u, fill=False, w=w)
        for x in (0.30, 0.50, 0.70):
            d.ellipse([(x - 0.06) * u, 0.80 * u, (x + 0.06) * u, 0.92 * u], fill=255)
    elif kind == "type":
        _diamond(d, 0.50 * u, 0.50 * u, 0.36 * u, fill=False, w=w)
        d.polygon([(0.50 * u, 0.14 * u), (0.50 * u, 0.86 * u), (0.14 * u, 0.50 * u)], fill=255)
    elif kind == "jump":
        _diamond(d, 0.50 * u, 0.62 * u, 0.26 * u)
        d.rectangle([0.12 * u, 0.12 * u, 0.88 * u, 0.12 * u + w], fill=255)
        d.rectangle([0.50 * u - w / 2, 0.12 * u, 0.50 * u + w / 2, 0.36 * u], fill=255)
    elif kind in ("next", "prev"):
        cx = 0.36 * u if kind == "next" else 0.64 * u
        _diamond(d, cx, 0.50 * u, 0.28 * u)
        tip, base = (0.94, 0.70) if kind == "next" else (0.06, 0.30)
        d.polygon([(base * u, 0.30 * u), (tip * u, 0.50 * u), (base * u, 0.70 * u)], fill=255)
    _save(m, path)


def _magnet(path: Path) -> None:
    """Blender's snapping magnet: an outlined U, its two pole tips filled."""
    u, m = _canvas()
    d = ImageDraw.Draw(m)
    w = int(0.07 * u)                       # outline stroke
    arm = 0.24 * u                          # arm width
    x0, x1, y0, y1 = 0.12 * u, 0.88 * u, 0.10 * u, 0.90 * u
    r = (x1 - x0) / 2
    cy = y1 - r
    # outer and inner arcs (bottom half of two circles)
    d.arc([x0, cy - r, x1, cy + r], 0, 180, fill=255, width=w)
    d.arc([x0 + arm, cy - r + arm, x1 - arm, cy + r - arm], 0, 180, fill=255, width=w)
    for xa in (x0, x1 - arm):
        d.rectangle([xa, y0, xa + w, cy], fill=255)               # outer side
        d.rectangle([xa + arm - w, y0, xa + arm, cy], fill=255)   # inner side
        d.rectangle([xa, y0, xa + arm, y0 + 0.22 * u], fill=255)  # filled pole tip
    _save(m, path)


def _play_reverse(path: Path, out: Path) -> None:
    """Play mirrored, so Play / Play reverse are one glyph read both ways."""
    Image.open(out / "play.png").transpose(Image.FLIP_LEFT_RIGHT).save(path)


DRAWN = {
    "sel_vert.png": lambda p: _select_mode(p, "vert"),
    "sel_edge.png": lambda p: _select_mode(p, "edge"),
    "sel_face.png": lambda p: _select_mode(p, "face"),
    "key_insert.png": lambda p: _key(p, "insert"),
    "key_delete.png": lambda p: _key(p, "delete"),
    "key_menu.png": lambda p: _key(p, "menu"),
    "key_type.png": lambda p: _key(p, "type"),
    "key_jump.png": lambda p: _key(p, "jump"),
    "key_next.png": lambda p: _key(p, "next"),
    "key_prev.png": lambda p: _key(p, "prev"),
    "snap.png": _magnet,
}


def main() -> int:
    out = HERE / "icons"
    out.mkdir(exist_ok=True)
    only = set(sys.argv[1:])
    todo = {k: v for k, v in ICONS.items() if not only or k in only}
    icon_fetch.fluent(todo, out)
    _play_reverse(out / "play_reverse.png", out)
    # Drawn and borrowed glyphs and the program mark are guarded: the committed
    # file is the source of truth once it exists, so a hand-tuned one survives.
    for name, draw in DRAWN.items():
        if (out / name).exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            draw(out / name)
            print(f"  {name}  <- drawn")
    icon_fetch.borrow(BORROWED, out)
    program_marks.ensure(out / "blender_mark.png", "Bl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
