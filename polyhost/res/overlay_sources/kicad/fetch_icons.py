#!/usr/bin/env python3
"""Fetch + render the KiCad shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. The fast-grid keys
(Alt+1, Alt+2) are numbered squares from `../number_badge.py`. KiCad's own
toolbar icons are not used (they are CC-BY-SA 4.0). No program icon: the host
draws the ESC mark for KiCad itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/kicad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, number_badge  # noqa: E402

FLUENT = {
    # --- both editors: file, edit, view ---
    "pastespecial": "ms:content_paste_go",
    "duplicate": "ms:library_add",
    "findreplace": "ms:find_replace",
    "findprev": "Arrow Previous",
    "nextmarker": "ms:flag",
    "search": "ms:manage_search",
    "refresh": "Arrow Clockwise",
    "zoomfit": "ms:fit_screen",
    "zoomobjects": "ms:zoom_out_map",
    "zoomarea": "ms:zoom_in_map",
    "center": "ms:center_focus_strong",
    "units": "Ruler",
    "measure": "ms:straighten",
    "gridoverride": "ms:grid_goldenratio",
    "gridnext": "Grid",
    "gridprev": "ms:grid_4x4",
    "_gridbase": "Square",
    "gridcycle": "ms:autorenew",
    "localorigin": "ms:my_location",
    "linemode": "ms:architecture",
    "updatepcb": "Arrow Sync",
    "viewer3d": "Cube",
    "prefs": "Settings",
    "hotkeys": "Keyboard",
    "properties": "Edit",
    "rotccw": "Arrow Rotate Counterclockwise",
    "rotcw": "Arrow Rotate Clockwise",
    "move": "Arrow Move",
    "drag": "ms:gesture",
    "swap": "Arrow Swap",
    "highlight": "Highlight",
    "clearhighlight": "Eraser",
    "designblock": "ms:widgets",
    "openeditor": "Open",
    "library": "Library",
    "importgfx": "ms:add_photo_alternate",
    "text": "Text T",
    "lines": "Line",
    "datasheet": "Document PDF",
    # --- PCB Editor ---
    "route": "ms:polyline",
    "diffpair": "ms:conversion_path",
    "tune": "ms:airwave",
    "tunediff": "ms:waves",
    "skew": "ms:compare_arrows",
    "footprints": "ms:memory",
    "getfootprint": "Target Arrow",
    "fill": "Paint Bucket",
    "unfill": "ms:format_color_reset",
    "drag45": "ms:north_east",
    "flip": "ms:flip",
    "contrast": "Dark Theme",
    "sketch": "Line Dashes",
    "lock": "Lock Closed",
    "unconnected": "ms:select",
    "grabnearest": "ms:pan_tool",
    "pack": "ms:view_compact",
    "expandconn": "ms:hub",
    "togglelayer": "Layer",
    "layerpair": "ms:swap_vert",
    "nextwidth": "Line Thickness",
    "prevwidth": "ms:line_weight",
    "togglehl": "ms:flashlight_on",
    "viainc": "Add Circle",
    "viadec": "Subtract Circle",
    "nextlayer": "Arrow Up",
    "prevlayer": "Arrow Down",
    "frontlayer": "ms:flip_to_front",
    "backlayer": "ms:flip_to_back",
    "opacityinc": "ms:opacity",
    "opacitydec": "ms:water_drop",
    "corner": "ms:rounded_corner",
    "snaplayers": "ms:layers",
    "moveexact": "ms:pin_drop",
    "zonecutout": "ms:crop",
    "posrelative": "ms:place_item",
    "routesel": "ms:route",
    "routeother": "ms:u_turn_left",
    "autoroute": "ms:automation",
    "delfulltrack": "ms:delete_sweep",
    "array": "ms:view_module",
    "moveindiv": "ms:scatter_plot",
    "dupincrement": "ms:exposure_plus_1",
    "polygon": "ms:pentagon",
    "bezier": "ms:line_curve",
    "dimension": "ms:width",
    "rulearea": "ms:block",
    "via": "ms:radio_button_checked",
    "zone": "ms:texture",
    "similarzone": "ms:add_box",
    # --- Schematic Editor ---
    "symbol": "ms:memory",
    "power": "ms:bolt",
    "noconnect": "Dismiss",
    "junction": "ms:fiber_manual_record",
    "busentry": "ms:subdirectory_arrow_right",
    "netlabel": "Tag",
    "hierlabel": "ms:label_important",
    "globallabel": "Globe",
    "sheet": "ms:article",
    "wire": "ms:timeline",
    "bus": "ms:view_headline",
    "mirrorh": "Flip Horizontal",
    "mirrorv": "Flip Vertical",
    "reference": "ms:badge",
    "value": "ms:123",
    "footprint": "ms:developer_board",
    "autoplace": "ms:auto_awesome_mosaic",
    "repeat": "Arrow Repeat All",
    "nextnet": "ms:keyboard_tab",
    "prevnet": "ms:keyboard_tab_rtl",
    "prevsheet": "Document Arrow Up",
    "nextsheet": "Document Arrow Down",
    "leavesheet": "ms:logout",
    "navup": "Arrow Up",
    "navback": "Arrow Left",
    "navforward": "Arrow Right",
    "hierarchy": "ms:account_tree",
    "selectnode": "ms:radio_button_checked",
    # --- Footprint Editor and Symbol Editor ---
    "anchor": "ms:anchor",
    "pin": "ms:pin_end",
    "savelibas": "Save Multiple",
    "unselectall": "ms:deselect",
    "copytext": "ms:text_snippet",
    # --- 3D Viewer ---
    "pivot": "ms:filter_center_focus",
    "homeview": "Home",
    "viewfront": "ms:flip_to_front",
    "viewback": "ms:flip_to_back",
    "viewleft": "ms:align_horizontal_left",
    "viewright": "ms:align_horizontal_right",
    "viewtop": "ms:vertical_align_top",
    "viewbottom": "ms:vertical_align_bottom",
    "showtht": "ms:settings_input_component",
    "showsmd": "ms:developer_board",
    "showvirtual": "ms:question_mark",
    "shownotpos": "ms:location_off",
    "showdnp": "ms:do_not_disturb_on",
    # --- GerbView ---
    "layerup": "ms:move_up",
    "layerdown": "ms:move_down",
    "sketchflashed": "ms:radio_button_unchecked",
    "sketchpoly": "ms:shape_line",
    "dcodes": "ms:numbers",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += number_badge.numbered(out / "_gridbase.png", "12", out, "fastgrid")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
