#!/usr/bin/env python3
"""Fetch + render the Audacity shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. No program icon: the host
draws the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/audacity/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    # --- file ---
    "close": "Dismiss Square",
    "export": "ms:file_export",
    "import": "ms:upload_file",
    "prefs": "Settings",
    # --- edit ---
    "duplicate": "ms:library_add",
    "silence": "ms:volume_off",
    "split": "ms:vertical_split",
    "join": "ms:merge",
    "pitchspeed": "ms:speed",
    "label": "Tag",
    "deleteclip": "ms:backspace",
    "cutgap": "ms:content_cut",
    "deletegap": "ms:delete_sweep",
    "trim": "ms:crop",
    "rename": "Rename",
    "pitchup": "ms:arrow_upward",
    "pitchdown": "ms:arrow_downward",
    "playlabel": "ms:new_label",
    "lcut": "ms:label_off",
    "ldelete": "ms:label_important",
    "lcopy": "ms:label",
    "ldetach": "ms:call_split",
    "pasteoverlap": "ms:content_paste_go",
    "pasteinsert": "ms:content_paste",
    "pasteall": "ms:assignment_returned",
    "cutclose": "ms:cut",
    "deleteclose": "ms:remove_road",
    "deleteall": "ms:layers_clear",
    "splitsilence": "ms:graphic_eq",
    "groupclips": "Group",
    "ungroupclips": "ms:stack_off",
    "splittool": "ms:carpenter",
    # --- select ---
    "selalltracks": "ms:select_all",
    "selsync": "ms:sync_lock",
    "selleft": "ms:line_start",
    "selright": "ms:line_end",
    "seltostart": "ms:keyboard_tab_rtl",
    "seltoend": "ms:keyboard_tab",
    "zerocross": "ms:exposure_zero",
    "spectral": "ms:filter_tilt_shift",
    "prevclip": "ms:skip_previous",
    "nextclip": "ms:skip_next",
    "extendleft": "ms:west",
    "extendright": "ms:east",
    "shrinkleft": "ms:arrow_forward_ios",
    "shrinkright": "ms:arrow_back_ios",
    "selhome": "ms:align_horizontal_left",
    "selend": "ms:align_horizontal_right",
    # --- view ---
    "zoomin": "Zoom In",
    "zoomnormal": "ms:zoom_in_map",
    "zoomout": "Zoom Out",
    "zoomsel": "ms:fit_screen",
    "zoomtoggle": "ms:zoom_out_map",
    "fitwidth": "ms:width",
    "fitheight": "ms:height",
    "collapse": "ms:unfold_less",
    "expand": "ms:unfold_more",
    "fullscreen": "Full Screen Maximize",
    # --- transport ---
    "playstop": "ms:play_pause",
    "playcursor": "ms:play_circle",
    "playonce": "ms:play_arrow",
    "playsel": "ms:smart_display",
    "pause": "Pause",
    "record": "Record",
    "recordnew": "ms:fiber_smart_record",
    "timer": "ms:timer",
    "punch": "ms:radio_button_checked",
    "trackstart": "ms:arrow_left_alt",
    "trackend": "ms:arrow_right_alt",
    "projstart": "ms:first_page",
    "projend": "ms:last_page",
    "loop": "ms:repeat",
    "clearloop": "ms:repeat_on",
    "loopsel": "ms:repeat_one",
    "loopinout": "ms:sync_alt",
    "playtosel": "ms:start",
    "cutpreview": "ms:preview",
    "scrubback": "ms:fast_rewind",
    "scrubfwd": "ms:fast_forward",
    "jumpleft": "ms:chevron_left",
    "jumpright": "ms:chevron_right",
    "longleft": "ms:keyboard_double_arrow_left",
    "longright": "ms:keyboard_double_arrow_right",
    "prevlabel": "ms:turn_left",
    "nextlabel": "ms:turn_right",
    # --- tracks ---
    "muteall": "ms:music_off",
    "unmuteall": "ms:music_note",
    "mutesel": "ms:volume_mute",
    "unmutesel": "ms:volume_up",
    "newtrack": "ms:playlist_add",
    "focusnext": "ms:keyboard_arrow_right",
    "focusprev": "ms:keyboard_arrow_left",
    "trackgain": "ms:tune",
    "trackmenu": "ms:menu",
    "trackmute": "ms:no_sound",
    "tracksolo": "ms:headphones",
    "togglefocus": "ms:check_box",
    # --- effects and tools ---
    "effects": "ms:auto_fix_high",
    "repeateffect": "ms:replay",
    "seltool": "ms:arrow_selector_tool",
    "envtool": "ms:show_chart",
    "drawtool": "Pen",
    "multitool": "ms:handyman",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
