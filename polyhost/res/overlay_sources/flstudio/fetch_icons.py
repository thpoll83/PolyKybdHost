#!/usr/bin/env python3
"""Fetch + render the FL Studio shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. No program icon: the host
draws the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/flstudio/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    # --- file and export ---
    "savenew": "ms:note_stack_add",
    "exportwav": "ms:audio_file",
    "exportmp3": "ms:music_note",
    "exportmidi": "ms:piano",
    "arrange": "ms:dashboard",
    "undosteps": "ms:history",
    # --- transport and recording ---
    "playstop": "ms:play_pause",
    "pause": "Pause",
    "songmode": "ms:repeat",
    "record": "Record",
    "snap": "ms:grid_on",
    "stepedit": "ms:steppers",
    "panic": "ms:emergency_home",
    "waitinput": "ms:hourglass_top",
    "metronome": "ms:timer",
    "typingpiano": "ms:keyboard",
    # --- windows ---
    "playlist": "ms:view_timeline",
    "channelrack": "ms:view_list",
    "pianoroll": "ms:piano",
    "pluginpicker": "ms:extension",
    "browser": "Folder",
    "mixer": "ms:tune",
    "midisettings": "ms:settings_input_hdmi",
    "songinfo": "Info",
    "closeall": "Dismiss Square",
    "cyclewin": "ms:tab",
    "maxplaylist": "Full Screen Maximize",
    "help": "Question Circle",
    "rename": "Rename",
    "emptypattern": "ms:add_box",
    "projectpicker": "ms:folder_special",
    "touch": "ms:touch_app",
    "tohome": "ms:first_page",
    # --- Playlist and Piano roll tools ---
    "paint": "ms:brush",
    "slice": "ms:content_cut",
    "deltool": "ms:ink_eraser",
    "select": "ms:select",
    "draw": "Pen",
    "mutetool": "ms:volume_off",
    "playtool": "Play",
    "zoomtool": "Zoom In",
    # --- edit ---
    "duplicate": "ms:library_add",
    "deselect": "ms:deselect",
    "delspace": "ms:keyboard_tab_rtl",
    "insspace": "ms:keyboard_tab",
    "invert": "ms:flip",
    "group": "Group",
    "ungroup": "ms:stack_off",
    "mutesel": "ms:music_off",
    "unmutesel": "ms:music_note_add",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "centerplay": "ms:center_focus_strong",
    "showall": "ms:fit_screen",
    "zoomsel": "ms:zoom_in_map",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
