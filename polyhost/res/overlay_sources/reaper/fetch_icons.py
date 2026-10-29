#!/usr/bin/env python3
"""Fetch + render the REAPER shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. The numbered marker
and region keys are numbered squares and circles from `../number_badge.py`. No
program icon: the host draws the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/reaper/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, number_badge  # noqa: E402

FLUENT = {
    # --- transport ---
    "playstop": "ms:play_pause",
    "pause": "Pause",
    "playskip": "ms:play_arrow",
    "record": "Record",
    "repeat": "ms:repeat",
    "tostart": "ms:first_page",
    "toend": "ms:last_page",
    "rewind": "Rewind",
    "fastforward": "Fast Forward",
    "panic": "ms:emergency_home",
    # --- file ---
    "saveversion": "ms:note_stack_add",
    "render": "ms:audio_file",
    "bounce": "ms:output",
    "projsettings": "ms:settings_applications",
    "newtab": "ms:tab",
    "closetab": "ms:tab_close",
    "prefs": "Settings",
    "keyhelp": "Keyboard",
    "actions": "ms:list_alt",
    "batch": "ms:transform",
    # --- edit ---
    "history": "ms:history",
    "smartcopy": "ms:copy_all",
    "smartcut": "ms:content_cut",
    "cutarea": "ms:delete_sweep",
    "dynsplit": "ms:auto_awesome_motion",
    # --- tracks ---
    "inserttrack": "ms:playlist_add",
    "nexttrack": "ms:keyboard_arrow_down",
    "prevtrack": "ms:keyboard_arrow_up",
    "volup": "Speaker 2",
    "voldown": "Speaker 1",
    "volenv": "ms:show_chart",
    "panenv": "ms:sync_alt",
    "trackgroup": "ms:group_work",
    "tempoenv": "ms:speed",
    # --- items ---
    "split": "ms:vertical_split",
    "splitsel": "ms:splitscreen_vertical_add",
    "splitplay": "ms:call_split",
    "splitzero": "ms:exposure_zero",
    "glue": "ms:merge",
    "duplicate": "ms:library_add",
    "duparea": "ms:control_point_duplicate",
    "inspaste": "ms:content_paste_go",
    "crossfade": "ms:gradient",
    "trim": "ms:crop",
    "inlineedit": "Edit",
    "exteditor": "Open",
    "takefx": "ms:graphic_eq",
    "stretch": "ms:open_in_full",
    "import": "ms:upload_file",
    "nudgedlg": "ms:move",
    "itemprops": "ms:info",
    "sourceprops": "ms:description",
    "mute": "ms:volume_off",
    "normalize": "ms:equalizer",
    "normalizeall": "ms:align_vertical_top",
    "pitchup": "ms:arrow_upward",
    "pitchdown": "ms:arrow_downward",
    "centup": "ms:expand_less",
    "centdown": "ms:expand_more",
    "rateup": "ms:fast_forward",
    "ratedown": "ms:slow_motion_video",
    "rateup10": "ms:north_east",
    "ratedown10": "ms:south_east",
    "deltake": "ms:layers_clear",
    "croptake": "ms:crop_free",
    "activetake": "ms:check_circle",
    "nexttake": "ms:keyboard_double_arrow_down",
    "prevtake": "ms:keyboard_double_arrow_up",
    "group": "Group",
    "ungroup": "ms:stack_off",
    "selgroup": "ms:select_all",
    # --- navigation ---
    "gridleft": "ms:keyboard_double_arrow_left",
    "gridright": "ms:keyboard_double_arrow_right",
    "nexttransient": "ms:arrow_right_alt",
    "prevtransient": "ms:arrow_left_alt",
    "itemstart": "ms:align_horizontal_left",
    "itemend": "ms:align_horizontal_right",
    "zeronext": "ms:redo",
    "zeroprev": "ms:undo",
    "toplay": "ms:play_circle",
    "toedit": "ms:edit_location",
    "jump": "ms:alarm",
    # --- time selection and loop ---
    "selleft": "ms:west",
    "selright": "ms:east",
    "shiftleft": "ms:keyboard_tab_rtl",
    "shiftright": "ms:keyboard_tab",
    "nudgeleft": "ms:chevron_left",
    "nudgeright": "ms:chevron_right",
    "loopstart": "ms:start",
    "loopend": "ms:line_end_arrow_notch",
    # --- markers ---
    "marker": "Flag",
    "editmarker": "ms:edit_note",
    "region": "ms:select",
    "prevmarker": "ms:skip_previous",
    "nextmarker": "ms:skip_next",
    "tempomarker": "ms:timer",
    "measure": "ms:straighten",
    "_markbase": "Square",
    "_setbase": "Circle",
    # --- zoom ---
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "vzoomin": "ms:unfold_more",
    "vzoomout": "ms:unfold_less",
    "zoomsel": "ms:zoom_in_map",
    "zoomproject": "ms:zoom_out_map",
    "zoomitems": "ms:fit_screen",
    "minheight": "ms:density_small",
    "maxheight": "ms:density_large",
    "expandsel": "ms:expand",
    "minall": "ms:compress",
    "peaksup": "ms:vertical_align_top",
    "peaksdown": "ms:vertical_align_bottom",
    # --- windows ---
    "mixer": "ms:tune",
    "master": "ms:speaker",
    "transport": "ms:smart_display",
    "docker": "ms:dock_to_bottom",
    "toolbar": "ms:toolbar",
    "fxbrowser": "ms:extension",
    "routing": "ms:hub",
    "groupmatrix": "ms:grid_on",
    "trackmanager": "ms:view_list",
    "regionmanager": "ms:bookmarks",
    "navigator": "ms:explore",
    "perfmeter": "ms:monitor_heart",
    "midikeyboard": "ms:piano",
    "bigclock": "Clock",
    "projectbay": "ms:inventory_2",
    "screensets": "ms:dashboard",
    "floating": "ms:filter_none",
    "mediaexplorer": "Folder",
    "video": "Video",
    "fullscreen": "Full Screen Maximize",
    # --- options ---
    "snap": "ms:grid_goldenratio",
    "snapsettings": "ms:settings_suggest",
    "gridlines": "ms:grid_4x4",
    "ripple": "ms:waves",
    "itemgrouping": "ms:join",
    "autofade": "ms:blur_linear",
    "lock": "Lock Closed",
    "locksettings": "ms:lock_open",
    "alltakes": "ms:layers",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    digits = "1234567890"
    n += number_badge.numbered(out / "_markbase.png", digits, out, "goto")
    n += number_badge.numbered(out / "_setbase.png", digits, out, "setmark")
    n += number_badge.numbered(out / "region.png", digits, out, "region")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
