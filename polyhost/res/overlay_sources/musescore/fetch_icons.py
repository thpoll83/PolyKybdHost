#!/usr/bin/env python3
"""Fetch + render the MuseScore Studio shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. Note names, durations,
accidentals, intervals, voices and tuplets are text, drawn here in DejaVu Sans
Bold, because the letter or the value is the information. No program icon:
the host draws the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/musescore/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RENDER_PX = 96
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

FLUENT = {
    # --- file and edit ---
    "close": "Dismiss Square",
    "swap": "ms:swap_horiz",
    "pastehalf": "ms:content_paste_go",
    "pastedouble": "ms:content_paste_search",
    # --- note input ---
    "inputname": "ms:edit_note",
    "inputduration": "ms:timer",
    "repitch": "ms:swap_vert",
    "rest": "ms:music_off",
    "tie": "Link",
    "grace": "ms:music_note",
    "halve": "ms:collapse_content",
    "double": "ms:expand_content",
    "halvedot": "ms:arrow_downward",
    "doubledot": "ms:arrow_upward",
    "repeat": "ms:repeat",
    "enharmonic": "ms:sync_alt",
    "enharmonic1": "ms:sync",
    "flip": "ms:flip",
    "fliph": "ms:flip_camera_android",
    "mirror": "ms:flip_to_back",
    "visible": "ms:visibility",
    "parens": "ms:data_array",
    "extend": "ms:start",
    # --- articulations and lines ---
    "slur": "ms:gesture",
    "dynamic": "ms:volume_up",
    "cresc": "ms:chevron_left",
    "dim": "ms:chevron_right",
    "staccato": "ms:fiber_manual_record",
    "tenuto": "ms:remove",
    "marcato": "ms:keyboard_arrow_up",
    "accent": "ms:arrow_back_ios",
    "hammer": "ms:construction",
    "bend": "ms:trending_up",
    "gracebend": "ms:call_made",
    # --- text ---
    "lyrics": "ms:lyrics",
    "tempo": "ms:speed",
    "systemtext": "ms:text_fields",
    "stafftext": "Text T",
    "expression": "ms:format_italic",
    "chordsym": "ms:queue_music",
    "rehearsal": "ms:bookmark",
    "figbass": "ms:filter_9_plus",
    # --- measures and layout ---
    "appendmeasure": "ms:add_box",
    "appendmeasures": "ms:library_add",
    "insertmeasure": "ms:add_column_left",
    "insertmeasures": "ms:view_week",
    "timedelete": "ms:backspace",
    "measurerest": "ms:horizontal_rule",
    "systembreak": "ms:keyboard_return",
    "pagebreak": "ms:insert_page_break",
    "systemlock": "Lock Closed",
    "lockselected": "ms:lock_open_right",
    "lockall": "ms:lock_person",
    "makesystem": "ms:view_stream",
    "mmrest": "ms:compress",
    "insertmode": "ms:edit",
    "editelement": "Edit",
    "reset": "ms:restart_alt",
    # --- panels ---
    "instruments": "ms:piano",
    "pianokbd": "Keyboard",
    "percussion": "ms:graphic_eq",
    "layout": "ms:view_list",
    "properties": "ms:tune",
    "palettes": "ms:palette",
    "masterpalette": "ms:dashboard",
    "palettesearch": "Search",
    "mixer": "ms:equalizer",
    "timeline": "ms:view_timeline",
    "braille": "ms:blind",
    "fullscreen": "Full Screen Maximize",
    "help": "Question Circle",
    # --- playback and view ---
    "play": "ms:play_pause",
    "playsel": "ms:play_circle",
    "pausesel": "ms:pause_circle",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoom100": "ms:fit_screen",
    # --- navigation ---
    "octup": "ms:keyboard_double_arrow_up",
    "octdown": "ms:keyboard_double_arrow_down",
    "diaup": "ms:expand_less",
    "diadown": "ms:expand_more",
    "pitchup": "ms:arrow_upward_alt",
    "pitchdown": "ms:arrow_downward_alt",
    "staffup": "ms:vertical_align_top",
    "staffdown": "ms:vertical_align_bottom",
    "topchord": "ms:north",
    "bottomchord": "ms:south",
    "firstel": "ms:first_page",
    "lastel": "ms:last_page",
    "nextel": "ms:arrow_forward",
    "prevel": "ms:arrow_back",
    "nextmeasure": "ms:keyboard_double_arrow_right",
    "prevmeasure": "ms:keyboard_double_arrow_left",
    "pageprev": "Document Arrow Up",
    "pagenext": "Document Arrow Down",
}

# Text icons: the value is the information.
TEXT = {
    "sharp": "♯", "natural": "♮", "flat": "♭",
    "dot": "♩.",
    **{f"note{c}": c for c in "ABCDEFG"},
    **{f"chord{c}": "+" + c for c in "ABCDEFG"},
    **{f"insert{c}": "^" + c for c in "ABCDEFG"},
    "dur1": "1/64", "dur2": "1/32", "dur3": "1/16", "dur4": "1/8",
    "dur5": "1/4", "dur6": "1/2", "dur7": "1", "dur8": "2", "dur9": "4",
    **{f"up{n}": f"+{n}" for n in range(1, 11)},
    **{f"down{n}": f"−{n}" for n in range(2, 11)},
    **{f"voice{n}": f"V{n}" for n in range(1, 5)},
    **{f"tuplet{n}": f"({n})" for n in range(2, 10)},
}


def _draw_text(path: Path, text: str) -> None:
    """Black text on transparent, like the fetched glyphs, scaled so its ink
    fills the icon. The music symbols sit small inside their em box, so the
    size comes from the measured ink box, not from the font size."""
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    probe = ImageFont.truetype(FONT, 100)
    box = d.textbbox((0, 0), text, font=probe)
    scale = min(RENDER_PX * 0.95 / (box[2] - box[0]), RENDER_PX * 0.9 / (box[3] - box[1]))
    font = ImageFont.truetype(FONT, max(8, int(100 * scale)))
    box = d.textbbox((0, 0), text, font=font)
    x = (RENDER_PX - (box[2] - box[0])) / 2 - box[0]
    y = (RENDER_PX - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), text, font=font, fill=(0, 0, 0, 255))
    img.save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    for name, text in TEXT.items():
        _draw_text(out / f"{name}.png", text)
        n += 1
    print(f"Wrote {n} icons to {out} ({len(TEXT)} drawn as text)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
