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

The ESC program mark is Simple Icons' Blender mark (marks/si_blender.svg),
rendered by the host's own ESC renderer; SOURCES.md has the provenance.

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

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

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
    # --- mode audit (2026-11): sequencer, outliner, text, curve, grease pencil, NLA, clip
    "multicam": "ms:switch_video", "gap_insert": "ms:space_bar",
    "gap_remove": "ms:horizontal_distribute", "unmute": "ms:do_not_disturb_off",
    "offset_clear": "ms:format_clear", "paste_place": "ms:content_paste", "speed": "ms:speed",
    "retime": "ms:slow_motion_video", "slip": "ms:settings_ethernet", "change": "ms:change_circle",
    "filter_off": "ms:filter_alt_off", "collection_include": "ms:folder", "driver": "ms:functions",
    "keying_set_remove": "ms:key_off", "page_up": "ms:keyboard_double_arrow_up",
    "page_down": "ms:keyboard_double_arrow_down", "backspace": "ms:backspace",
    "line_break": "ms:keyboard_return", "top": "ms:vertical_align_top",
    "bottom": "ms:vertical_align_bottom", "word_prev": "ms:keyboard_double_arrow_left",
    "arrow_left": "ms:arrow_back", "arrow_right": "ms:arrow_forward", "text_new": "ms:note_add",
    "text_open": "ms:file_open", "overwrite": "ms:keyboard", "select_line": "ms:short_text",
    "spacing_less": "ms:format_letter_spacing", "spacing_more": "ms:format_letter_spacing_wide",
    "small_caps": "ms:format_size", "accent": "ms:translate", "cyclic": "ms:cycle",
    "row": "ms:table_rows", "erase": "ms:ink_eraser", "layer_hide": "ms:visibility_off",
    "layers": "ms:layers", "material": "ms:style", "to_front": "ms:flip_to_front",
    "opacity": "ms:opacity", "edit_lines": "ms:line_style", "single_user": "ms:person",
    "sound": "ms:music_note", "transition": "ms:transition_fade", "clip_open": "ms:video_file",
    "prefetch": "ms:download", "reconstruct": "ms:view_in_ar", "solve": "ms:calculate",
    "track": "ms:location_searching", "path_clear": "ms:remove_road",
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
        _save(m, path)
        return
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


def _del_forward(path: Path, out: Path) -> None:
    """Backspace mirrored: delete the word AFTER the cursor (Material has no
    forward-delete key glyph)."""
    Image.open(out / "backspace.png").transpose(Image.FLIP_LEFT_RIGHT).save(path)


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


# ------------------------------------------------------------------ worded variants
# One icon per action (maintainer rule, 2026-11-15): two keys may share an image
# only when they do the same thing, across all Blender sets. A variant of an
# action ("all", "fine", "select to", a numbered slot, another target) is its
# base glyph over a short bold word. Drawn 1-bit, white on transparent, at the
# spec's region size (36x32), so `mode: auto` renders it in alpha 1:1.
# Not guarded: drawn from code and committed icons only (the skill's guard rule).
#
# stem -> (glyph, word). `glyph` is a stem in icons/ or "text:<characters>".
WORDED = {f"multicam_{n}": ("multicam", str(n)) for n in range(1, 11)}
WORDED.update({
    # sequencer / NLA
    "add_action_strip": ("add", "ACT"), "apply_scale": ("apply", "SCL"),
    "meta_make": ("group", "META"), "meta_ungroup": ("ungroup", "META"),
    "meta_toggle": ("group_enter", "META"), "tweak": ("group_enter", "TWK"),
    "tweak_isolate": ("group_enter", "ISO"),
    "strip_up": ("hier_parent", "STRIP"), "strip_down": ("hier_child", "STRIP"),
    "swap_strips": ("swap", "STRIP"), "swap_left": ("swap", "LEFT"),
    "swap_right": ("swap", "RIGHT"), "swap_inputs": ("swap", "IN"),
    "lock_strips": ("lock_channel", "STRIP"), "unlock_strips": ("lock_pie", "STRIP"),
    "lock_tracks": ("lock_channel", "TRK"), "unlock_tracks": ("lock_pie", "TRK"),
    "mute_strips": ("mute", "STRIP"), "mute_unsel": ("mute", "OTHR"),
    "unmute_unsel": ("unmute", "OTHR"), "markers_toggle": ("mute", "MRK"),
    "mute_footage": ("mute", "CLIP"), "gap_remove_all": ("gap_remove", "ALL"),
    "retime_menu": ("retime", "MENU"), "split_hard": ("split", "HARD"),
    "split_stroke": ("split", "STRK"), "separate_images": ("separate", "IMG"),
    "separate_fills": ("separate", "FILL"), "view_type": ("render_view", "PREV"),
    "overlay_reset": ("overlays", "RST"), "overlay_frame": ("overlays", "FRM"),
    "refresh_all": ("refresh", "ALL"), "reload_length": ("refresh", "LEN"),
    "strips_connect": ("link", "CONN"), "strips_snap": ("snap", "STRIP"),
    "strip_next": ("same_next", "STRIP"), "strip_next_center": ("same_next", "CTR"),
    "strip_prev": ("same_prev", "STRIP"), "strip_prev_center": ("same_prev", "CTR"),
    "linked_extend": ("select_linked", "EXT"), "select_box_handles": ("select_box", "HNDL"),
    # movie clip
    "clip_mode": ("track", "MASK"), "track_next": ("track", "+1"),
    "track_prev": ("track", "-1"), "track_fwd": ("track", "FWD"), "track_back": ("track", "BWD"),
    "path_end": ("jump_end", "PATH"), "path_start": ("jump_start", "PATH"),
    "jump_failed": ("key_jump", "FAIL"), "marker_delete": ("marker", "DEL"),
    "marker_pie": ("marker", "PIE"), "join_tracks": ("join", "TRK"),
    "lock_selection": ("pin", "SEL"), "show_disabled": ("reveal", "DSBL"),
    "search_area": ("search", "AREA"), "path_clear_after": ("path_clear", "AFT"),
    "path_clear_before": ("path_clear", "BEF"),
    # outliner
    "collapse_all": ("collapse", "ALL"), "expand_all": ("shrink_fatten", "ALL"),
    "collapse_item": ("collapse", "ONE"), "expand_item": ("shrink_fatten", "ONE"),
    "expand_toggle": ("collapse", "TOGL"),
    "extend_up": ("hier_parent", "EXT"), "extend_down": ("hier_child", "EXT"),
    "collection_exclude": ("collection_include", "EXCL"),
    "show_hierarchy": ("ed_outliner", "TREE"), "show_active": ("localview", "ACT"),
    "reveal_all": ("reveal", "ALL"), "drivers_delete": ("driver", "DEL"),
    "keying_set_add": ("keying_set", "ADD"),
    # text editor and text objects
    "delete_word": ("backspace", "WORD"), "line_end": ("jump_end", "LINE"),
    "line_start": ("jump_start", "LINE"), "sel_line_end": ("jump_end", "SEL"),
    "sel_line_start": ("jump_start", "SEL"), "sel_text_end": ("bottom", "SEL"),
    "sel_text_start": ("top", "SEL"), "sel_page_down": ("page_down", "SEL"),
    "sel_page_up": ("page_up", "SEL"), "word_prev_w": ("word_prev", "WORD"),
    "word_next_w": ("propagate", "WORD"), "sel_word_prev": ("word_prev", "SEL"),
    "sel_word_next": ("propagate", "SEL"), "sel_up": ("hier_parent", "SEL"),
    "sel_down": ("hier_child", "SEL"), "line_up": ("hier_parent", "LINE"),
    "line_down": ("hier_child", "LINE"), "duplicate_line": ("duplicate", "LINE"),
    "run_script": ("play", "PY"), "char_up": ("text:A", "+1"), "char_down": ("text:A", "-1"),
    "spacing_less_fine": ("spacing_less", "FINE"), "spacing_more_fine": ("spacing_more", "FINE"),
    # curve
    "tilt_clear": ("clear_rot", "TILT"), "tilt": ("rotate", "TILT"),
    "make_segment": ("connect", "SEG"), "handles_recalc": ("handle", "CALC"),
    "curve_radius": ("shrink_fatten", "RAD"),
    # grease pencil
    "multiframe_lines": ("edit_lines", "MULTI"), "select_fill": ("fill", "SEL"),
    "hide_other_layers": ("hide_others", "LYR"), "reveal_layers": ("reveal", "LYR"),
    "order_forward": ("hier_parent", "FWD"), "order_backward": ("hier_child", "BWD"),
    "order_to_back": ("select_invert", "BACK"),
    "gp_interpolate": ("interpolation", "GP"), "gp_interpolate_seq": ("interpolation", "SEQ"),
    "join_fills": ("join", "FILL"), "join_strokes": ("join", "STRK"),
    "join_copy": ("join", "COPY"), "layer_move": ("layers", "MOVE"),
    "stroke_close": ("make_face", "CLS"), "gp_frame_delete": ("key_delete", "FRM"),
    "gp_frame_delete_all": ("key_delete", "ALL"), "gp_blank_key": ("key_insert", "BLNK"),
    "gp_anim_menu": ("key_menu", "ANIM"), "layer_merge": ("merge", "LYR"),
    "paste_behind": ("paste_place", "BACK"),
    "gp_point_select": ("sel_vert", "SEL"), "gp_point_mask": ("sel_vert", "MASK"),
    "gp_segment_select": ("sel_edge", "SEL"), "gp_segment_mask": ("sel_edge", "MASK"),
    "gp_stroke_select": ("stroke", "SEL"), "gp_stroke_mask": ("stroke", "MASK"),
    "weight_direction": ("switch_dir", "WGT"),
    # one icon per action across all Blender sets (2026-11-17 sweep)
    "select_tool": ("select_box", "TOOL"), "to_sphere": ("tosphere", "SPHR"),
    "render_changed": ("render", "CHNG"), "find_node": ("search", "NODE"),
    "fit_backdrop": ("frame_all", "BKDR"), "frame_all_quad": ("frame_all", "QUAD"),
    "same_type_next": ("same_next", "TYPE"), "same_type_prev": ("same_prev", "TYPE"),
    "bone_roll": ("rotate", "ROLL"), "roll_recalc": ("rotate", "CALC"),
    "roll_clear": ("clear_rot", "ROLL"), "skin_resize": ("scale", "SKIN"),
    "deselect_linked": ("deselect", "LINK"), "tool_pie": ("tools", "PIE"),
    "start_frame_set": ("jump_start", "SET"), "end_frame_set": ("jump_end", "SET"),
    "snap_target": ("snap_options", "TRGT"), "column_frame": ("column", "FRM"),
    "column_between": ("column_markers", "BTWN"), "linked_pick": ("select_linked", "PICK"),
    "handles_show": ("handle", "SHOW"), "select_mirror": ("mirror", "SEL"),
    "extrude_menu": ("extrude", "MENU"), "fill_bone": ("fill", "BONE"),
    "parent_add": ("hier_parent", "ADD"), "child_add": ("hier_child", "ADD"),
    "separate_group": ("separate", "GRP"), "select_split": ("split", "SEL"),
    "envelope": ("bbone", "ENV"), "bone_select_mask": ("bbone", "SEL"),
    "bone_option_on": ("bone_options", "ON"), "bone_option_off": ("bone_options", "OFF"),
    "cursor_center_2d": ("frame_cursor", "CTR"), "bone_collection_add": ("collection_add", "BONE"),
    "region_custom": ("render_region", "CUST"), "region_custom_use": ("render_region", "USE"),
    "vertex_parent": ("parent", "VERT"), "align_uv_menu": ("align", "MENU"),
    "sel_vert_add": ("sel_vert", "ADD"), "sel_edge_add": ("sel_edge", "ADD"),
    "sel_face_add": ("sel_face", "ADD"), "sel_vert_exp": ("sel_vert", "EXP"),
    "sel_edge_exp": ("sel_edge", "EXP"), "sel_face_exp": ("sel_face", "EXP"),
    "sel_vert_add_exp": ("sel_vert", "+EXP"), "sel_edge_add_exp": ("sel_edge", "+EXP"),
    "sel_face_add_exp": ("sel_face", "+EXP"), "sel_vert_menu": ("sel_vert", "MENU"),
    "sel_edge_menu": ("sel_edge", "MENU"), "sel_face_menu": ("sel_face", "MENU"),
    "face_mask": ("sel_face", "MASK"), "sel_mode_menu": ("sel_face", "MODE"),
    "knife_selected": ("knife", "SEL"), "rip_fill": ("rip", "FILL"),
    "normals_point": ("normals", "PNT"), "normals_recalc": ("normals", "CALC"),
    "edge_crease": ("crease", "EDGE"), "island_select": ("island", "ISL"),
    "sample_group": ("vgroup", "SMPL"), "triangulate_fixed": ("triangulate", "FIX"),
    "sample_merged": ("eyedropper", "MRG"), "sample_weight": ("eyedropper", "WGT"),
    "weight_set": ("weight", "SET"), "blend_menu": ("blend_neighbor", "MENU"),
    "smooth_keys": ("br_smooth", "KEYS"), "duplicate_inputs": ("duplicate_linked", "IN"),
    "merge_inputs": ("merge", "IN"), "link_sockets": ("link", "SOCK"),
    "collection_remove_active": ("collection_remove", "ACT"), "tex_angle_mask": ("tex_angle", "MASK"),
    "mask_pie": ("br_mask", "PIE"), "grow_visible": ("grow", "VIS"),
    "shrink_visible": ("shrink", "VIS"), "render_slot_next": ("render_slot", "NEXT"),
    "render_slot_prev": ("render_slot", "PREV"), "select_pinned": ("pin", "PIND"),
})
WORDED.update({f"subdiv_{n}": ("subdiv", str(n)) for n in range(6)})
WORDED.update({f"render_slot_{n}": ("render_slot", str(n)) for n in range(5, 10)})

WORD_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
WORD_SIZE = (36, 32)            # the spec's region: placed 1:1
WORD_GLYPH_BOX = (2, 0, 34, 20)  # x0, y0, x1, y1 of the glyph above the word
WORD_PX = 11
WORD_GLYPH_TEXT_PX = 18
WORD_BASELINE = 31


def _worded(dest: Path, out: Path, glyph: str, word: str) -> None:
    from PIL import ImageFont
    w, h = WORD_SIZE
    mask = Image.new("L", WORD_SIZE, 0)
    d = ImageDraw.Draw(mask)
    x0, y0, x1, y1 = WORD_GLYPH_BOX
    if glyph.startswith("text:"):
        f = ImageFont.truetype(WORD_BOLD, WORD_GLYPH_TEXT_PX)
        d.text((w / 2, (y0 + y1) / 2), glyph[5:], font=f, fill=255, anchor="mm")
    else:
        im = Image.open(out / f"{glyph}.png").convert("RGBA")
        a = np.asarray(im).astype(np.float32)
        # ink = alpha where the art is dark (Material, drawn glyphs) or light (borrowed)
        ink = Image.fromarray(a[..., 3].astype(np.uint8), "L")
        bbox = ink.getbbox() or (0, 0, im.width, im.height)
        ink = ink.crop(bbox)
        k = min((x1 - x0) / ink.width, (y1 - y0) / ink.height)
        nw, nh = max(1, round(ink.width * k)), max(1, round(ink.height * k))
        ink = ink.resize((nw, nh), Image.LANCZOS).point(lambda v: 255 if v >= 128 else 0)
        mask.paste(255, (x0 + (x1 - x0 - nw) // 2, y0 + (y1 - y0 - nh) // 2), ink)
    f = ImageFont.truetype(WORD_BOLD, WORD_PX)
    tw = d.textlength(word, font=f)
    if tw > w:
        raise ValueError(f"{dest.name}: word {word!r} is {tw:.0f} px wide (max {w})")
    d.text(((w - tw) / 2, WORD_BASELINE), word, font=f, fill=255, anchor="ls")
    mask = mask.point(lambda v: 255 if v >= 128 else 0)
    img = Image.new("RGBA", WORD_SIZE, (255, 255, 255, 0))
    img.putalpha(mask)
    img.save(dest)


def _blender_mark(path):
    """ESC mark: Simple Icons' Blender logo (marks/si_blender.svg, vendored
    from simple-icons@15.22.0), rendered by the host's own ESC renderer so the
    baked mark is pixel-identical to what the runtime path would draw. It is a
    finished 72x40 mask placed full-cell (program_icon_region [72, 40])."""
    from polyhost.services import app_icons
    mask = app_icons.render_mark(str(HERE / "marks" / "si_blender.svg"))
    a = np.where(mask, 255, 0).astype("uint8")
    rgba = np.dstack([a, a, a, a])
    Image.fromarray(rgba, "RGBA").save(path)
    print(f"  {path.name}  <- marks/si_blender.svg ({int(mask.sum())} px)")


def main() -> int:
    out = HERE / "icons"
    out.mkdir(exist_ok=True)
    only = set(sys.argv[1:])
    todo = {k: v for k, v in ICONS.items() if not only or k in only}
    icon_fetch.fluent(todo, out)
    # Mirrors play.png, which exists only once "play" has been fetched; a run
    # limited to other stems on a fresh icons/ must not fail on it.
    if (out / "play.png").exists():
        _play_reverse(out / "play_reverse.png", out)
    if (out / "backspace.png").exists():
        _del_forward(out / "del_forward.png", out)
    # Drawn and borrowed glyphs are guarded: the committed file is the source of
    # truth once it exists, so a hand-tuned one survives. The program mark is
    # NOT guarded: it is rebuilt from the vendored marks/si_blender.svg every
    # run, deterministically, so the SVG is its source of truth.
    for name, draw in DRAWN.items():
        if (out / name).exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            draw(out / name)
            print(f"  {name}  <- drawn")
    icon_fetch.borrow(BORROWED, out)
    for name, (glyph, word) in WORDED.items():
        if only and name not in only:
            continue
        _worded(out / f"{name}.png", out, glyph, word)
        print(f"  {name}.png  <- drawn {glyph} + '{word}'")
    _blender_mark(out / "blender_mark.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
