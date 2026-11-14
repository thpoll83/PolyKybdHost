#!/usr/bin/env python3
"""Fetch + render the Xonotic icons (reproducible).

The key icons are flat 1-bit silhouettes, as in the Counter-Strike 2 set: game
shapes from game-icons.net (CC BY 3.0, credit per author in SOURCES.md) and
interface shapes from Material Symbols (Apache-2.0). The ESC mark is Xonotic's
own icon (GPL-3.0-or-later), reduced to two flat shapes.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/xonotic/fetch_icons.py

The fetched icons are re-rendered on every run. The ESC mark is written only
when its PNG is missing, so a hand edit to the committed PNG is kept.

The Unvanquished and Red Eclipse sets import `flat_icons()`, `lettered()` and
`text_mark()` from this file.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.factorio import fetch_icons as fac  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Movement
    "forward": "ms:arrow_upward",
    "back": "ms:arrow_downward",
    "left": "ms:arrow_back",
    "right": "ms:arrow_forward",
    "jump": "gi:delapouite/jump-across",
    # Weapon groups 1 to 9 and 0
    "blaster": "gi:lorc/ray-gun",
    "shotgun": "gi:delapouite/sawed-off-shotgun",
    "machinegun": "gi:delapouite/uzi",
    "mortar": "gi:lorc/grenade",
    "electro": "gi:sbed/electric",
    "crylink": "gi:lorc/crystal-shine",
    "vortex": "gi:lorc/vortex",
    "hagar": "gi:lorc/missile-swarm",
    "devastator": "gi:lorc/rocket",
    "superweapon": "gi:lorc/star-swirl",
    # Weapon actions
    "lastweapon": "ms:history",
    "reload": "ms:autorenew",
    "drop": "ms:place_item",
    "hook": "gi:lorc/meat-hook",
    "use": "ms:touch_app",
    "drag": "ms:drag_pan",
    "kill": "ms:skull",
    # Communication
    "chat": "ms:public",
    "teamchat": "ms:chat",
    "chathistory": "ms:forum",
    "quickmenu": "ms:menu",
    # Views
    "scoreboard": "ms:scoreboard",
    "radar": "ms:radar",
    "info": "ms:info",
    "console": "ms:terminal",
    "pause": "ms:pause",
    # Function keys
    "voteyes": "ms:thumb_up",
    "voteno": "ms:thumb_down",
    "spectate": "ms:visibility",
    "ready": "ms:check_circle",
    "teamselect": "ms:groups",
    "autojoin": "ms:group_add",
    "sandbox": "ms:deployed_code",
    "minigames": "ms:casino",
    "quit": "ms:logout",
    "screenshot": "ms:screenshot_monitor",
}

# Key area of each icon, from xonotic.yaml; the default is 40 x 40.
F_KEY = (34, 40)            # F1 to F9
F_KEY_WIDE = (30, 40)       # F10 to F12: the legend has one more character
SIZES = {"voteyes": F_KEY, "voteno": F_KEY, "spectate": F_KEY, "ready": F_KEY,
         "teamselect": F_KEY, "autojoin": F_KEY, "sandbox": F_KEY, "quickmenu_f": F_KEY,
         "minigames": F_KEY, "quit": F_KEY_WIDE, "screenshot": F_KEY_WIDE}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box at
# the bottom right of their key area.
INK = {"forward": (30, 30), "back": (30, 30), "left": (30, 30), "right": (30, 30),
       "chat": (34, 34), "teamchat": (34, 34), "chathistory": (36, 36),
       "mortar": (34, 40), "scoreboard": (40, 34), "info": (32, 32), "kill": (32, 34),
       "quickmenu": (32, 32), "pause": (30, 30), "radar": (34, 34), "ready": (32, 32), "voteyes": (32, 32),
       "voteno": (32, 32), "sandbox": (32, 34), "minigames": (32, 32)}

# The ESC mark: Xonotic's icon, misc/logos/xonotic_icon.svg at release 0.8.6.
LOGO_URL = ("https://raw.githubusercontent.com/xonotic/xonotic/"
            "xonotic-v0.8.6/misc/logos/xonotic_icon.svg")
LOGO_PX = 40                # the mark is LOGO_PX square, centred on the 72x40 cell
LOGO_SS = 8                 # the SVG is rendered LOGO_SS times larger and box-filtered
LOGO_THRESHOLD = 128        # grey level (0..255) from which a box-filtered pixel is lit


def flat_icons(icons, sizes, ink, out: Path) -> None:
    """Every icon in `icons` as a flat 1-bit silhouette, drawn at exactly its
    key area (`sizes`, default 40 x 40) so the generator places it 1:1. The
    icons in `ink` fill a smaller box in the bottom-right corner of that area."""
    for stem in icons:
        size = sizes.get(stem, (40, 40))
        cnc._save_mask(zeroad._flat(out / f"{stem}.png", size, ink.get(stem, size)),
                       out / f"{stem}.png")
    print(f"  {len(icons)} key icons drawn flat")


def resized(src: Path, path: Path, size, box) -> None:
    """`src` (a fetched RGBA render) drawn flat into `path` at another key
    area, for an action that sits on two keys with different areas."""
    cnc._save_mask(zeroad._flat(src, size, box), path)
    print(f"  {path.name}  <- {src.name} at {size[0]}x{size[1]}")


def lettered(src: Path, text: str, path: Path, size, box, px: int) -> None:
    """`src` drawn flat at the bottom right of a `size` area in `box`, with
    `text` (DejaVu Sans Bold, at most `px` high) lit in the top-left corner of
    the area. Pixels of the icon within 2 px of the text are cleared."""
    if not fac._missing(path):
        return
    import numpy as np
    m = zeroad._flat(src, size, box)
    d = zeroad._digit(text, px)
    t = np.zeros_like(m)
    t[0:d.shape[0], 0:d.shape[1]] = d
    cnc._save_mask((m & ~program_mark.dilate(t, 2)) | t, path)
    print(f"  {path.name}  <- {src.name} + {text}")


def text_mark(lines, font_url: str, path: Path, threshold: int = 90, gap: int = 2) -> None:
    """`lines` (one or more strings) set in the font at `font_url`, all at the
    largest one size at which each line fits 70 px wide and all lines, `gap` px
    apart, fit 38 px high, centred on the whole 72x40 cell. Drawn 8 times
    larger and box-filtered down; a pixel is lit from grey `threshold`."""
    if not fac._missing(path):
        return
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


def program(out: Path) -> None:
    """program.png: Xonotic's icon as two flat shapes, 40x40 in the centre of
    the 72x40 cell. The bird's head (the red and orange pixels of the icon) is
    lit as one shape. The ring round it (the blue pixels) is lit too, except
    within 1 px of the head, so the two shapes stay apart."""
    path = out / "program.png"
    if not fac._missing(path):
        return
    import io
    import cairosvg
    import numpy as np
    from PIL import Image
    big = LOGO_PX * LOGO_SS
    png = cairosvg.svg2png(bytestring=icon_fetch._get(LOGO_URL), output_width=big, output_height=big)
    px = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA")).astype(int)
    opaque = px[..., 3] > 128
    red, blue = px[..., 0], px[..., 2]

    def down(mask):
        im = Image.fromarray((mask * 255).astype(np.uint8))
        return np.asarray(im.resize((LOGO_PX, LOGO_PX), Image.BOX)) > LOGO_THRESHOLD

    head = down(opaque & (red > blue))
    ring = down(opaque & (blue >= red)) & ~program_mark.dilate(head, 1)
    canvas = np.zeros((40, 72), bool)
    x0 = (72 - LOGO_PX) // 2
    canvas[:, x0:x0 + LOGO_PX] = head | ring
    cnc._save_mask(canvas, path)
    print("  program.png  <- xonotic_icon.svg (head and ring)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    fac.render(ICONS, out)
    # B and F8 both open the quick menu; F8 has the narrower F-key area.
    resized(out / "quickmenu.png", out / "quickmenu_f.png", SIZES["quickmenu_f"], (30, 30))
    flat_icons(ICONS, SIZES, INK, out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
