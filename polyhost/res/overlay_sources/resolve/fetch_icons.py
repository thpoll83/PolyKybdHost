#!/usr/bin/env python3
"""Fetch + render the DaVinci Resolve shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** for everything generic,
plus the shared custom-drawn NLE glyphs (`../nle_glyphs.py`) for the timeline
operations no UI icon set has — blade, mark in/out, overwrite, append, ripple
delete, trim, snapping. The ESC **program mark** is a drawn, license-clean
substitute (`../geo_marks.py`): Blackmagic's Resolve logo is a trademark we may
not redistribute, but the shape it is built from — a ring of three drops — is a
plain construction we can draw ourselves.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/resolve/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geo_marks  # noqa: E402
import icon_fetch  # noqa: E402
import nle_glyphs  # noqa: E402

# action filename -> Fluent folder name (icon_fetch resolves the asset + size).
FLUENT = {
    # file / project
    "newtimeline": "Add Square",
    "save": "Save",
    "import": "Arrow Import",
    "render": "Arrow Export",
    "renderqueue": "List",
    # edit
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "selectall": "Select All On",
    "group": "Group",
    "ungroup": "Group Dismiss",
    "link": "Link",
    "addedit": "Split Vertical",
    # view / timeline
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "select": "Cursor",
    "marker": "Flag",
    "dyntrim": "Arrow Autofit Width",
    "insert": "Arrow Between Down",
    # transport
    "play": "Play",
    "stop": "Stop",
    "fwd": "Fast Forward",
    "rev": "Rewind",
    # the six pages (Shift+3..8)
    "pagecut": "Filmstrip",
    "pageedit": "Timeline",
    "pagefusion": "Branch",
    "pagecolor": "Color",
    "pagefairlight": "Music Note 2",
    "pagedeliver": "Cloud Arrow Up",
}

# The per-page sets (pages.yaml): Material Symbols (Apache-2.0), weight 300.
PAGE_ICONS = {
    "pagemedia": "ms:perm_media",
    # transport and marks
    "loop": "ms:repeat", "playagain": "ms:replay", "stopreturn": "ms:stop_circle",
    "playaround": "ms:sync", "fastfwd": "ms:keyboard_double_arrow_right",
    "fastrev": "ms:keyboard_double_arrow_left", "prevedit": "ms:skip_previous",
    "nextedit": "ms:skip_next", "gotoin": "ms:keyboard_tab_rtl", "gotoout": "ms:keyboard_tab",
    "clearin": "ms:format_indent_decrease", "clearout": "ms:format_indent_increase",
    "clearinout": "ms:cancel", "markclip": "ms:width_normal",
    "markerdel": "ms:bookmark_remove", "markernote": "ms:edit_note",
    # media pool / file
    "newbin": "ms:create_new_folder", "importtl": "ms:file_open", "exporttl": "ms:ios_share",
    "poster": "ms:image", "posterclear": "ms:hide_image", "subclip": "ms:video_library",
    # viewers
    "cinema": "ms:fullscreen", "enhanced": "ms:open_in_full", "scopes": "ms:monitoring",
    "zoomfit": "ms:fit_screen", "zoom100": "ms:aspect_ratio", "zoom200": "ms:zoom_in_map",
    "viewerfocus": "ms:flip", "viewer1": "ms:looks_one", "viewer2": "ms:looks_two",
    "quadview": "ms:grid_view", "showctl": "ms:visibility",
    # timeline editing
    "selectedit": "ms:vertical_split", "selectclip": "ms:select", "selectunder": "ms:select_all",
    "editside": "ms:swap_horiz", "extend": "ms:start", "disable": "ms:toggle_off",
    "disableall": "ms:toggle_on", "selfwd": "ms:arrow_right_alt", "selback": "ms:arrow_left_alt",
    "replace": "ms:find_replace", "placeontop": "ms:layers", "rippleoverwrite": "ms:move_down",
    "fittofill": "ms:fit_width", "lift": "ms:space_bar", "ripplecut": "ms:content_cut",
    "pasteinsert": "ms:content_paste_go", "linkedsel": "ms:add_link",
    "transition": "ms:transition_dissolve", "duration": "ms:timer", "bypass": "ms:layers_clear",
    "nudgeleft": "ms:chevron_left", "nudgeright": "ms:chevron_right",
    "nudgeleft5": "ms:keyboard_double_arrow_left", "nudgeright5": "ms:keyboard_double_arrow_right",
    "trimstart": "ms:align_horizontal_left", "trimend": "ms:align_horizontal_right",
    "trimsel": "ms:crop", "deselect": "ms:deselect",
    # fairlight
    "trackheight": "ms:height", "prevclip": "ms:navigate_before", "nextclip": "ms:navigate_next",
    "trackup": "ms:arrow_upward", "trackdown": "ms:arrow_downward",
    # fusion
    "addtool": "ms:add_box", "find": "ms:search", "bypassnode": "ms:block", "locknode": "ms:lock",
    "opengroup": "ms:folder_open", "swapinputs": "ms:swap_vert", "pasteinstance": "ms:content_paste_go",
    "prevkey": "ms:first_page", "nextkey": "ms:last_page", "firstframe": "ms:first_page",
    "lastframe": "ms:last_page", "smoothkey": "ms:show_chart", "linearkey": "ms:linear_scale",
    # color
    "nodeserial": "ms:arrow_forward", "nodebefore": "ms:arrow_back", "nodeappend": "ms:keyboard_tab",
    "nodeparallel": "ms:call_split", "nodelayer": "ms:stacks", "nodeoutside": "ms:flip_to_back",
    "nodesplit": "ms:alt_route", "wincircle": "ms:circle", "winlinear": "ms:rectangle",
    "winpolygon": "ms:pentagon", "wincurve": "ms:gesture", "prevnode": "ms:navigate_before",
    "nextnode": "ms:navigate_next", "grabstill": "ms:photo_camera", "wipe": "ms:compare",
    "wipeinvert": "ms:flip", "splitscreen": "ms:splitscreen", "nextstill": "ms:skip_next",
    "prevstill": "ms:skip_previous", "gradeversion": "ms:library_add", "gradedefault": "ms:restart_alt",
    "autocolor": "ms:auto_fix_high", "wheels": "ms:tune", "trackfwd": "ms:my_location",
    "trackrev": "ms:location_searching", "trackstop": "ms:location_disabled",
    "highlight": "ms:highlight", "highlightbw": "ms:contrast", "winoutline": "ms:border_outer",
    "addkey": "ms:add_diamond", "statickey": "ms:square", "delkey": "ms:remove",
    "resetgrade": "ms:layers_clear",
}

DRAWN = ["blade", "markin", "markout", "overwrite", "append", "rippledelete", "trim", "snap"]


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.fluent(PAGE_ICONS, out)
    n += nle_glyphs.draw_all(out, DRAWN)
    geo_marks.ensure_resolve(out / "resolve.png")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
