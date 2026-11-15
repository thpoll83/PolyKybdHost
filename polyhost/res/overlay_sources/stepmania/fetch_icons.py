#!/usr/bin/env python3
"""Fetch + render the StepMania 5 icons (reproducible).

The key icons are flat 1-bit silhouettes from Material Symbols (Apache-2.0),
Font Awesome Free (CC BY 4.0) and game-icons.net (CC BY 3.0); SOURCES.md
credits each. The ESC mark is the game's name set in Bungee (SIL OFL 1.1); the
game's logo art has no stated licence and is not used.

The Etterna and osu! sets import the helpers of this file (`render`,
`flat_icons`, `badged`, `copies`, `text_mark`).

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/stepmania/fetch_icons.py

Every icon and the ESC mark are drawn again on each run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

F_KEY = (34, 40)            # F1 to F9: the width that keeps the legend whole
F_KEY_WIDE = (30, 40)       # F10 to F12: the legend has one more character

# The ESC mark is set in Bungee (SIL OFL 1.1).
MARK_FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
                 "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/bungee/Bungee-Regular.ttf")

ICONS = {
    # Menu buttons
    "start": "ms:play_circle",
    "select": "ms:menu",
    "coin": "fa:coins",
    "operator": "ms:settings",
    "back2": "ms:undo",
    "menuleft": "ms:arrow_back",
    "menuright": "ms:arrow_forward",
    "menuup": "ms:arrow_upward",
    "menudown": "ms:arrow_downward",
    # Reload (F2 and its chords)
    "reload": "ms:refresh",
    "reloadmetrics": "ms:description",
    "reloadscripts": "ms:code",
    "reloadoverlays": "ms:layers",
    # Debug and speed
    "debug": "ms:bug_report",
    "fast": "ms:fast_forward",
    "slow": "ms:slow_motion_video",
    "mute": "ms:volume_off",
    # Gameplay
    "revertsync": "ms:history",
    "autosync": "ms:sync",
    "assist": "fa:hands-clapping",
    "metronome": "gi:delapouite/metronome",
    "autoplay": "ms:smart_toy",
    # Window
    "screenshot": "ms:photo_camera",
    "screenshotraw": "ms:high_quality",
    "fullscreen": "ms:fullscreen",
    "quit": "ms:power_settings_new",
    # Song select
    "reloadsong": "ms:audio_file",
}
# Icons that get a plus or a minus: {file: (source file, sign)}. The source
# files are fetched, used and deleted.
BADGE_PARTS = {"_bpm": "ms:speed", "_offset": "ms:schedule", "_global": "ms:public"}
BADGED = {
    "bpmdown": ("_bpm", "-"), "bpmup": ("_bpm", "+"),
    "offsetdown": ("_offset", "-"), "offsetup": ("_offset", "+"),
    "globaldown": ("_global", "-"), "globalup": ("_global", "+"),
}

# Key area of each icon, from stepmania.yaml; the default is 40 x 40.
SIZES = {"coin": F_KEY, "reload": F_KEY, "reloadmetrics": F_KEY, "reloadscripts": F_KEY,
         "reloadoverlays": F_KEY, "debug": F_KEY, "revertsync": F_KEY, "autosync": F_KEY,
         "assist": F_KEY, "metronome": F_KEY, "autoplay": F_KEY, "bpmdown": F_KEY, "bpmup": F_KEY_WIDE,
         "offsetdown": F_KEY_WIDE, "offsetup": F_KEY_WIDE,
         "globaldown": F_KEY_WIDE, "globalup": F_KEY_WIDE, "quit": F_KEY}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box at
# the bottom right of their key area.
INK = {"menuleft": (30, 30), "menuright": (30, 30), "menuup": (30, 30), "menudown": (30, 30),
       "start": (34, 34), "select": (32, 32), "operator": (34, 34), "back2": (32, 32),
       "reload": (30, 30), "reloadmetrics": (30, 34), "reloadscripts": (32, 32),
       "reloadoverlays": (32, 32), "debug": (32, 32), "revertsync": (32, 32),
       "autosync": (30, 30), "autoplay": (32, 32), "assist": (32, 32),
       "fast": (34, 34), "slow": (34, 34), "mute": (34, 34),
       "screenshot": (34, 34), "screenshotraw": (34, 34), "fullscreen": (32, 32),
       "quit": (30, 30), "reloadsong": (30, 34), "coin": (32, 32)}
# The box of the icon under a plus or a minus.
BADGE_BOX = (26, 26)

MARK_LINES = ("STEP", "MANIA")


def render(mapping: dict[str, str], out_dir: Path, render_px: int = 256) -> None:
    """`{stem: "ms:name" | "fa:name" | "mdi:name" | "gi:author/name"}` into
    `out_dir` as RGBA PNGs. `ms:` is Material Symbols through `icon_fetch`; the
    other three use the URLs in `cnc.SOURCES`."""
    import cairosvg
    out_dir.mkdir(parents=True, exist_ok=True)
    for stem, spec in mapping.items():
        src, name = spec.split(":", 1)
        if src == "ms":
            svg, _, _ = icon_fetch._fetch_svg(spec)
        else:
            svg = icon_fetch._get(cnc.SOURCES[src].format(name))
        png = cairosvg.svg2png(bytestring=svg, output_width=render_px, output_height=render_px)
        (out_dir / f"{stem}.png").write_bytes(png)
        print(f"  {stem}.png  <- {spec}")


def flat_icons(icons, sizes, ink, out: Path) -> None:
    """Every icon in `icons` as a flat 1-bit silhouette, drawn at exactly its
    key area (`sizes`, default 40 x 40) so the generator places it 1:1. The
    icons in `ink` fill a smaller box in the bottom-right corner of that area."""
    for stem in icons:
        size = sizes.get(stem, (40, 40))
        cnc._save_mask(zeroad._flat(out / f"{stem}.png", size, ink.get(stem, size)),
                       out / f"{stem}.png")
    print(f"  {len(icons)} key icons drawn flat")


def _sign(sign: str, px: int = 11, bar: int = 3):
    """A plus, a minus, or a triangle that points left ("<") or right (">"),
    as a `px` square 1-bit mask."""
    import numpy as np
    m = np.zeros((px, px), bool)
    mid = px // 2
    if sign in "+-":
        m[mid - bar // 2:mid + bar // 2 + 1, :] = True
        if sign == "+":
            m[:, mid - bar // 2:mid + bar // 2 + 1] = True
        return m
    for x in range(px):                      # a triangle with its point at x = 0
        half = (x * mid) // (px - 1)
        m[mid - half:mid + half + 1, x] = True
    return m if sign == "<" else m[:, ::-1]


def badged(src: Path, sign: str, path: Path, size=(40, 40), box=BADGE_BOX) -> None:
    """`src` drawn flat in `box` at the bottom right of a `size` area, with the
    sign (see `_sign`) lit in the top-left corner of the area. Pixels of the
    icon within 2 px of the sign are cleared."""
    import numpy as np
    m = zeroad._flat(src, size, box)
    s = _sign(sign)
    t = np.zeros_like(m)
    t[0:s.shape[0], 0:s.shape[1]] = s
    cnc._save_mask((m & ~program_mark.dilate(t, 2)) | t, path)
    print(f"  {path.name}  <- {src.name} with {sign}")


def copies(mapping, sizes, out: Path) -> None:
    """`{stem: (source stem, box)}`: the fetched render of the source drawn
    flat at the key area of `stem`, for an action that sits on two keys with
    different areas. Call it before `flat_icons` redraws the sources."""
    for stem, (src, box) in mapping.items():
        size = sizes.get(stem, (40, 40))
        cnc._save_mask(zeroad._flat(out / f"{src}.png", size, box), out / f"{stem}.png")
        print(f"  {stem}.png  <- {src}.png at {size[0]}x{size[1]}")


def text_mark(lines, font_url: str, path: Path, threshold: int = 90, gap: int = 2) -> None:
    """`lines` (one or more strings) set in the font at `font_url`, all at the
    largest one size at which each line fits 70 px wide and all lines, `gap` px
    apart, fit 38 px high, centred on the whole 72x40 cell. Drawn 8 times
    larger and box-filtered down; a pixel is lit from grey `threshold`."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h, ss = 72, 40, 8
    font_path = str(cnc._font(font_url))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(font_path, px)
        boxes = [font.getbbox(line) for line in lines]
        height = sum(b[3] - b[1] for b in boxes) + gap * ss * (len(boxes) - 1)
        if all(b[2] - b[0] <= (w - 2) * ss for b in boxes) and height <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    draw = ImageDraw.Draw(im)
    y = (h * ss - height) // 2
    for line, box in zip(lines, boxes):
        draw.text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                  line, font=font, fill=255)
        y += box[3] - box[1] + gap * ss
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > threshold, path)
    print(f"  {path.name}  <- {' / '.join(lines)} ({px / ss:.1f} px)")


def build(icons, parts, badges, sizes, ink, out: Path, same=None) -> None:
    """One set: fetch `icons` and `parts`, draw the copies in `same`, the
    badged icons and the flat icons, then delete the part files."""
    render({**icons, **parts}, out)
    copies(same or {}, sizes, out)
    for stem, (src, sign) in badges.items():
        badged(out / f"{src}.png", sign, out / f"{stem}.png", sizes.get(stem, (40, 40)))
    flat_icons(icons, sizes, ink, out)
    for stem in parts:
        (out / f"{stem}.png").unlink()


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    build(ICONS, BADGE_PARTS, BADGED, SIZES, INK, out)
    text_mark(MARK_LINES, MARK_FONT_URL, out / "program.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
