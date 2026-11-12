#!/usr/bin/env python3
"""Fetch + render the VLC media player shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The set-bookmark keys are
Fluent `Bookmark` with a digit, from `../number_badge.py`. The ESC mark is the
VLC cone from Simple Icons (CC0 artwork; nominative use, see
`../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/vlc/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch, number_badge  # noqa: E402

FLUENT = {
    "openfile": "Document",
    "openmulti": "Document Multiple",
    "openadvanced": "Document Settings",
    "openfolder": "Folder Open",
    "opendisc": "ms:album",
    "opennetwork": "Globe",
    "opencapture": "Camera",
    "openclipboard": "Clipboard Link",
    "saveplaylist": "Save",
    "convert": "ms:transform",
    "stream": "ms:cast",
    "reveal": "Folder Search",
    "playpause": "ms:play_pause",
    "stop": "ms:stop",
    "previous": "Previous",
    "next": "Next",
    "record": "Record",
    "jumptime": "ms:schedule",
    "shuffle": "Arrow Shuffle",
    "repeatall": "Arrow Repeat All",
    "abloop": "ms:linear_scale",
    "faster": "ms:speed",
    "slower": "ms:slow_motion_video",
    "back3": "ms:keyboard_arrow_left",
    "fwd3": "ms:keyboard_arrow_right",
    "back10": "ms:replay_10",
    "fwd10": "ms:forward_10",
    "back60": "ms:keyboard_double_arrow_left",
    "fwd60": "ms:keyboard_double_arrow_right",
    "back300": "ms:fast_rewind",
    "fwd300": "ms:fast_forward",
    "discmenu": "ms:menu_book",
    "titleprev": "ms:skip_previous",
    "titlenext": "ms:skip_next",
    "chapterprev": "ms:first_page",
    "chapternext": "ms:last_page",
    "volup": "Speaker 2",
    "voldown": "Speaker 1",
    "mute": "Speaker Mute",
    "fullscreen": "Full Screen Maximize",
    "snapshot": "ms:photo_camera",
    "zoomquarter": "ms:photo_size_select_small",
    "zoomhalf": "ms:photo_size_select_large",
    "zoomoriginal": "ms:crop_square",
    "zoomdouble": "ms:open_in_full",
    "fitscreen": "ms:fit_screen",
    "scaleup": "ms:zoom_out_map",
    "scaledown": "ms:zoom_in_map",
    "croptop": "ms:border_top",
    "cropleft": "ms:border_left",
    "cropbottom": "ms:border_bottom",
    "cropright": "ms:border_right",
    "uncroptop": "ms:arrow_upward",
    "uncropleft": "ms:arrow_back",
    "uncropbottom": "ms:arrow_downward",
    "uncropright": "ms:arrow_forward",
    "subsize": "ms:format_size",
    "subsync": "ms:subtitles",
    "effects": "ms:tune",
    "videoeffects": "ms:video_settings",
    "audioeffects": "ms:graphic_eq",
    "mediainfo": "Info",
    "codecinfo": "ms:memory",
    "messages": "ms:article",
    "errors": "Warning",
    "playlist": "ms:playlist_play",
    "playbackwin": "ms:smart_display",
    "minimal": "ms:web_asset_off",
    "fsinterface": "ms:fullscreen",
    "clearplaylist": "ms:playlist_remove",
    "_bookmark": "Bookmark",
}

# The single-key hotkeys (libvlc-module.c). The four delay keys are composed in
# delay_icons() from a subtitle or note glyph and an up or down arrow.
HOTKEYS = {
    "position": "ms:timer",
    "framenext": "ms:resume",
    "ratenormal": "ms:1x_mobiledata",
    "syncaudio": "ms:graphic_eq",
    "syncsub": "ms:closed_caption",
    "syncapply": "ms:sync",
    "audiotrack": "ms:library_music",
    "subtrack": "ms:subtitles",
    "subtoggle": "ms:subtitles_off",
    "programnext": "ms:live_tv",
    "programprev": "ms:tv",
    "aspect": "ms:aspect_ratio",
    "crop": "ms:crop",
    "deinterlace": "ms:blur_linear",
    "deinterlacemode": "ms:blur_on",
    "zoom": "ms:zoom_in",
    "unzoom": "ms:zoom_out",
    "audiodevice": "ms:speaker_group",
    "wallpaper": "ms:wallpaper",
    "_subtitles": "ms:subtitles",
    "_note": "ms:music_note",
    "_up": "ms:arrow_upward",
    "_down": "ms:arrow_downward",
}


def delay_icons(out: Path) -> None:
    """Subtitle and audio delay up / down: the glyph with an arrow on its right."""
    from PIL import Image
    for base, kind in (("_subtitles", "sub"), ("_note", "audio")):
        glyph = Image.open(out / f"{base}.png").convert("RGBA").resize((96, 96))
        for arrow, way in (("_up", "up"), ("_down", "down")):
            canvas = Image.new("RGBA", (152, 96), (0, 0, 0, 0))
            canvas.alpha_composite(glyph, (0, 0))
            canvas.alpha_composite(
                Image.open(out / f"{arrow}.png").convert("RGBA").resize((64, 64)), (88, 16))
            canvas.save(out / f"{kind}delay{way}.png")
            print(f"  {kind}delay{way}.png  <- {base}.png + {arrow}.png")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.fluent(HOTKEYS, out)
    delay_icons(out)
    number_badge.numbered(out / "_bookmark.png", "1234567890", out, "setbm",
                          size=0.40, centre=(0.50, 0.42))
    brand_marks.ensure(out / "vlc.png", "vlcmediaplayer")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
