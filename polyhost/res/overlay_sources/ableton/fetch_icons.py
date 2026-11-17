#!/usr/bin/env python3
"""Fetch + render the Ableton Live shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. The track keys F1..F8 are
numbered squares from `../number_badge.py`. The Clip View sets
(`clip_midi.yaml`, `clip_audio.yaml`) also use glyph + word composites, drawn
1-bit at 40x40 by `../ghidra/fetch_icons.py`'s `composites()` (an arrow or a
glyph over a short word, for example an up arrow over VEL). No program icon:
the host draws the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/ableton/fetch_icons.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

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
    # --- Session View (session.yaml) ---
    "stopbutton": "ms:stop",
    "insertscene": "ms:playlist_add",
    "capturescene": "ms:photo_camera",
    "midiclip": "ms:music_note_add",
    "launch": "ms:play_arrow",
    "followact": "ms:shuffle",
    "stopclips": "ms:playlist_remove",
    "followchain": "ms:link",
    # --- Clip View, MIDI Note Editor (clip_midi.yaml) ---
    "chopnotes": "ms:view_week",
    "joinnotes": "ms:join",
    "fittime": "ms:straighten",
    "groupnotes": "ms:bubble_chart",
    "ungroupnotes": "ms:scatter_plot",
    "applytool": "ms:auto_fix_high",
    "invertsel": "ms:flip",
    "highlightscale": "ms:format_ink_highlighter",
    "foldnotes": "ms:compress",
    "foldscale": "ms:filter_list",
    "focusmode": "ms:center_focus_strong",
    "notefilters": "ms:filter_alt",
    "expandclip": "ms:open_in_full",
    "cliphome": "ms:skip_previous",
    "clipend": "ms:skip_next",
    "nexttab": "ms:tab",
}

# Clip View keys that differ only by a direction or a target: name -> (glyph,
# word), drawn by ../ghidra/fetch_icons.py composites(). A glyph is an arrow
# ("up", "down", "left", "right"), "text:<chars>", or an icon stem above.
COMPOSITES = {
    # MIDI Note Editor
    "oct_up": ("up", "OCT"),            # PgUp / PgDn: scroll one octave
    "oct_down": ("down", "OCT"),
    "row_up": ("up", "ROW"),            # Shift+PgUp / PgDn: one key track
    "row_down": ("down", "ROW"),
    "note_up": ("up", "NOTE"),          # Alt+Up / Down: select next/previous note
    "note_down": ("down", "NOTE"),
    "note_left": ("left", "NOTE"),      # Alt+Left / Right: same key track
    "note_right": ("right", "NOTE"),
    "vel_up": ("up", "VEL"),            # Ctrl+Up / Down: velocity
    "vel_down": ("down", "VEL"),
    "dev_up": ("up", "DEV"),            # Ctrl+Shift+Up / Down: velocity deviation
    "dev_down": ("down", "DEV"),
    "prob_up": ("up", "PROB"),          # Ctrl+Alt+Up / Down: chance
    "prob_down": ("down", "PROB"),
    "tab_edit": ("nexttab", "EDIT"),    # Alt+Shift+1..3: editor tabs
    "tab_env": ("nexttab", "ENV"),
    "tab_mpe": ("nexttab", "MPE"),
    # Sample Editor
    "warp_left": ("left", "WARP"),      # Left / Right: move the selected warp marker
    "warp_right": ("right", "WARP"),
    "warpsel_left": ("left", "SEL"),    # Ctrl+Left / Right: select a warp marker
    "warpsel_right": ("right", "SEL"),
    "region_left": ("left", "CLIP"),    # Shift+Left / Right: move the clip region
    "region_right": ("right", "CLIP"),
    "warp_add": ("text:+", "WARP"),     # Ctrl+I / Delete: warp marker
    "warp_del": ("text:\u2212", "WARP"),
    "trans_add": ("text:+", "TRNS"),    # Ctrl+Shift+I / Ctrl+Shift+Delete: transient
    "trans_del": ("text:\u2212", "TRNS"),
}


def ghidra_helpers():
    """`../ghidra/fetch_icons.py` as a module, for its composite drawing code."""
    path = Path(__file__).resolve().parent.parent / "ghidra" / "fetch_icons.py"
    spec = importlib.util.spec_from_file_location("ghidra_fetch_icons", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += number_badge.numbered(out / "_trackbase.png", "12345678", out, "track")
    g = ghidra_helpers()
    g.COMPOSITES = COMPOSITES
    g.ISA = {}
    g.composites(out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
