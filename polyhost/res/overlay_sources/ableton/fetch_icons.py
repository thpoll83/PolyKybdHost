#!/usr/bin/env python3
"""Fetch + render the Ableton Live shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. The track keys F1..F8 are
numbered squares from `../number_badge.py`. No program icon: the host draws
the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/ableton/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, number_badge  # noqa: E402

FLUENT = {
    # --- views ---
    "fullscreen": "Full Screen Maximize",
    "secondwin": "ms:select_window_2",
    "sessionarr": "ms:swap_horiz",
    "deviceclip": "ms:swap_vert",
    "hotswap": "ms:swap_calls",
    "browser": "ms:left_panel_open",
    "overview": "ms:view_compact_alt",
    "inout": "ms:input",
    "sends": "ms:call_split",
    "mixer": "ms:tune",
    "clipview": "ms:view_agenda",
    "deviceview": "ms:memory",
    "groove": "ms:waves",
    "learn": "ms:school",
    "settings": "Settings",
    # --- sets ---
    "exportaudio": "ms:audio_file",
    "exportmidi": "ms:file_export",
    # --- edit ---
    "duplicate": "ms:library_add",
    "rename": "Rename",
    "search": "Search",
    # --- grid and quantization ---
    "narrowgrid": "ms:grid_on",
    "widegrid": "ms:grid_view",
    "triplet": "ms:looks_3",
    "snapgrid": "ms:grid_goldenratio",
    "fixedgrid": "ms:grid_guides",
    "q16": "ms:counter_1",
    "q8": "ms:counter_2",
    "q4": "ms:counter_3",
    "qbar": "ms:counter_4",
    "qoff": "ms:block",
    "quantize": "ms:align_horizontal_left",
    "quantizeset": "ms:settings_suggest",
    # --- tracks ---
    "audiotrack": "ms:graphic_eq",
    "miditrack": "ms:queue_music",
    "returntrack": "ms:u_turn_left",
    "group": "Group",
    "ungroup": "ms:stack_off",
    "returns": "ms:visibility",
    "arm": "ms:mic",
    "solo": "ms:headphones",
    "deactivate": "ms:power_settings_new",
    "fold": "ms:unfold_less",
    "unfoldall": "ms:unfold_more",
    # --- transport ---
    "playstop": "ms:play_pause",
    "continue": "ms:resume",
    "stopsel": "ms:stop_circle",
    "record": "Record",
    "armarr": "ms:radio_button_checked",
    "recsession": "ms:fiber_smart_record",
    "backtoarr": "ms:undo",
    "metronome": "ms:timer",
    "_trackbase": "Square",
    # --- modes ---
    "automation": "ms:show_chart",
    "drawmode": "Pen",
    "midikeyboard": "ms:piano",
    "midimap": "ms:settings_input_component",
    "keymap": "Keyboard",
    "engine": "ms:power",
    # --- arrangement ---
    "split": "ms:content_cut",
    "consolidate": "ms:merge",
    "crop": "ms:crop",
    "loop": "ms:repeat",
    "insertsilence": "ms:space_bar",
    "cuttime": "ms:hourglass_disabled",
    "copytime": "ms:more_time",
    "pastetime": "ms:pending_actions",
    "duptime": "ms:update",
    "deltime": "ms:timer_off",
    "fade": "ms:gradient",
    "reverse": "ms:fast_rewind",
    "zoomsel": "ms:zoom_in_map",
    "zoomback": "ms:zoom_out_map",
    "fitheight": "ms:height",
    "fitwidth": "ms:width",
    "bounce": "ms:output",
    "startmarker": "ms:first_page",
    "loopstart": "ms:keyboard_tab_rtl",
    "loopend": "ms:keyboard_tab",
    "endmarker": "ms:last_page",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += number_badge.numbered(out / "_trackbase.png", "12345678", out, "track")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
