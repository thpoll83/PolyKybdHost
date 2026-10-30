#!/usr/bin/env python3
"""Fetch + render the YouTube player shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The digit keys seek to 0 %
to 90 % of the video; `seek_icons()` draws each as a seek bar filled to that
point, 1-bit at keycap size. The ESC mark is the YouTube logo from Simple Icons
(CC0 artwork; nominative use, see `../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/youtube/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    "playpause": "ms:play_pause",
    "back10": "ms:replay_10",
    "fwd10": "ms:forward_10",
    "back5": "ms:replay_5",
    "fwd5": "ms:forward_5",
    "mute": "Speaker Mute",
    "volup": "ms:volume_up",
    "voldown": "ms:volume_down",
    "prevframe": "ms:chevron_left",
    "nextframe": "ms:chevron_right",
    "slower": "ms:slow_motion_video",
    "faster": "ms:speed",
    "start": "ms:first_page",
    "end": "ms:last_page",
    "prevchapter": "ms:keyboard_double_arrow_left",
    "nextchapter": "ms:keyboard_double_arrow_right",
    "search": "Search",
    "fullscreen": "Full Screen Maximize",
    "captions": "Closed Caption",
    "nextvideo": "ms:skip_next",
    "prevvideo": "ms:skip_previous",
    "miniplayer": "ms:picture_in_picture_alt",
    "shortcuts": "Keyboard",
}

SEEK_SIZE = (40, 40)


def seek_icons(out: Path) -> None:
    """Draw seek_<digit>.png: a seek bar filled to digit x 10 %.

    Every image is 40x40 and the generator scales the whole image, so all ten
    are placed at the same position. The end caps at x 0 and x 39 mark the
    ends of the video.
    """
    w, h = SEEK_SIZE
    x0, x1, cy = 5, w - 6, h - 12
    for digit in range(10):
        dest = out / f"seek_{digit}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        mask = Image.new("L", SEEK_SIZE, 0)
        d = ImageDraw.Draw(mask)
        d.rectangle([0, cy - 6, 1, cy + 6], fill=255)
        d.rectangle([w - 2, cy - 6, w - 1, cy + 6], fill=255)
        d.rectangle([x0, cy - 4, x1, cy + 4], outline=255, width=1)
        fill = x0 + round((x1 - x0) * digit / 10)
        if fill > x0:
            d.rectangle([x0, cy - 4, fill, cy + 4], fill=255)
        img = Image.new("RGBA", SEEK_SIZE, (255, 255, 255, 0))
        img.putalpha(mask)
        img.save(dest)
        print(f"  {dest.name}  <- drawn seek bar at {digit * 10} %")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    seek_icons(out)
    brand_marks.ensure(out / "youtube.png", "youtube")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
