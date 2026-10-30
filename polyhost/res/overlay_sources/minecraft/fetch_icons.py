#!/usr/bin/env python3
"""Fetch + render the Minecraft icons (Java Edition and Bedrock Edition), reproducibly.

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0) and
game-icons.net (CC BY 3.0), as in the Warcraft III set. The hotbar slots 1 to 9
are a square slot with the digit in Press Start 2P (SIL OFL 1.1). Drop item and
drop stack are one block or three blocks over a drawn down arrow. The ESC marks
are MINECRAFT over JAVA or BEDROCK, set in Press Start 2P; the game's logo art
is not used. SOURCES.md credits each icon.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/minecraft/fetch_icons.py

The drawn files (slot1..9, drop, dropstack, program_java, program_bedrock) are
kept when they already exist, so a hand edit survives a re-run. Delete one to
draw it again.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402

ICONS = {
    # Movement
    "forward": "fa:arrow-up",
    "left": "fa:arrow-left",
    "back": "fa:arrow-down",
    "right": "fa:arrow-right",
    "jump": "gi:delapouite/jump-across",
    "sneak": "fa:user-ninja",
    "sprint": "fa:person-running",
    # Inventory
    "inventory": "gi:lorc/knapsack",
    "offhand": "fa:right-left",
    "savehotbar": "fa:floppy-disk",
    "loadhotbar": "fa:folder-open",
    # Chat and players
    "chat": "gi:delapouite/chat-bubble",
    "command": "fa:terminal",
    "playerlist": "fa:users",
    "friends": "fa:handshake",
    "socialhide": "fa:user-slash",
    "socialdrawer": "fa:user-group",
    "narrator": "fa:volume-high",
    "emote": "fa:face-smile",
    "notification": "fa:bell",
    # Game screens
    "advancements": "fa:trophy",
    "quickactions": "fa:bolt",
    "effects": "fa:flask",
    "contentlog": "fa:file-lines",
    "tableft": "fa:angles-left",
    "tabright": "fa:angles-right",
    "copycoords": "fa:location-dot",
    "copyfacing": "fa:crosshairs",
    # Function keys
    "hidehud": "fa:eye-slash",
    "screenshot": "fa:camera",
    "debug": "fa:bug",
    "shader": "fa:wand-magic-sparkles",
    "perspective": "fa:street-view",
    "paperdoll": "fa:person",
    "controllerhints": "fa:gamepad",
    "fullscreen": "fa:expand",
}

# Part of the drawn drop icons; not used by a binding directly.
PARTS = {
    "_block": "gi:delapouite/cube",
}

# Key area of each icon, from the two specs; the default is 40 x 40. The narrow
# ones keep the key's own legend whole (widths measured for AoE2, see
# ../aoe2/SOURCES.md, Placement).
SIZES = {"hidehud": (34, 40), "screenshot": (34, 40), "perspective": (34, 40),
         "paperdoll": (34, 40), "shader": (30, 40), "socialdrawer": (30, 40),
         "sprint": (34, 40), "sneak": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box at the
# bottom right of their key area.
INK = {"savehotbar": (32, 32), "loadhotbar": (34, 34), "screenshot": (30, 30),
       "emote": (32, 32), "notification": (34, 34), "contentlog": (32, 36),
       "chat": (34, 34), "playerlist": (36, 36), "socialdrawer": (30, 30),
       "debug": (34, 34), "controllerhints": (36, 36),
       "forward": (30, 36), "back": (30, 36), "left": (36, 30), "right": (36, 30)}

# Press Start 2P (SIL OFL 1.1): every glyph is drawn on an 8 x 8 pixel grid, so
# at 8 px it renders 1:1 and any integer multiple stays exact.
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/pressstart2p/PressStart2P-Regular.ttf")
FONT_PX = 8
SLOT = 40          # hotbar slot image, square
SLOT_BORDER = 2    # px
SLOT_SCALE = 3     # digit: the 8 px glyph at 3x


def _mask(path: Path, box: tuple[int, int]):
    """The ink of `path`, scaled to fit `box` (w, h), as a bool array."""
    import numpy as np
    from PIL import Image
    alpha = Image.open(path).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    scale = min(box[0] / alpha.width, box[1] / alpha.height)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                         Image.LANCZOS)
    return np.asarray(alpha) > 150


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area so
    the generator places it 1:1. The icons in INK fill a smaller box in the
    bottom-right corner of that area."""
    import numpy as np
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        m = _mask(out / f"{stem}.png", INK.get(stem, size))
        canvas = np.zeros((size[1], size[0]), bool)
        canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def _arrow_down(width: int = 14, head: int = 7, shaft: int = 4, length: int = 13):
    """A solid down arrow, drawn pixel by pixel: a `shaft` px wide shaft and a
    triangular head `head` px tall and `width` px wide."""
    import numpy as np
    a = np.zeros((length, width), bool)
    c = width // 2
    a[:length - head, c - shaft // 2:c - shaft // 2 + shaft] = True
    for i in range(head):                       # row i of the head, from its base
        half = round((width / 2) * (head - i) / head)
        a[length - head + i, max(0, c - half):c + half] = True
    return a


def _paste(canvas, m, cx: int, top: int) -> None:
    x = cx - m.shape[1] // 2
    canvas[top:top + m.shape[0], x:x + m.shape[1]] |= m


def drop_icons(out: Path) -> None:
    """drop.png (Q) and dropstack.png (Ctrl+Q), 40x40: one block, or three
    blocks (one on top of two), over a solid down arrow, all centred on one
    vertical axis."""
    import numpy as np
    arrow = _arrow_down()
    for stem in ("drop", "dropstack"):
        if (out / f"{stem}.png").exists():
            print(f"  {stem}.png  <- committed asset (left as-is)")
            continue
        canvas = np.zeros((40, 40), bool)
        if stem == "drop":
            _paste(canvas, _mask(out / "_block.png", (24, 24)), 20, 0)
        else:
            block = _mask(out / "_block.png", (13, 13))
            _paste(canvas, block, 20, 0)
            _paste(canvas, block, 20 - 7, 13)
            _paste(canvas, block, 20 + 7, 13)
        _paste(canvas, arrow, 20, 40 - arrow.shape[0])
        cnc._save_mask(canvas, out / f"{stem}.png")
        print(f"  {stem}.png  <- {'one block' if stem == 'drop' else 'three blocks'} over a down arrow")


def _text(font, s: str, sx: int = 1, sy: int = 1):
    """`s` in Press Start 2P at 8 px, trimmed to its ink and scaled by whole
    pixels (sx across, sy down)."""
    import numpy as np
    from PIL import Image, ImageDraw
    im = Image.new("L", (FONT_PX * (len(s) + 1), FONT_PX + 4), 0)
    ImageDraw.Draw(im).text((0, 0), s, font=font, fill=255)
    a = np.asarray(im) > 127
    ys, xs = np.nonzero(a)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return np.kron(a, np.ones((sy, sx), bool))


def _load_font(font):
    from PIL import ImageFont
    return font or ImageFont.truetype(str(cnc._font(FONT_URL)), FONT_PX)


def slots(out: Path) -> None:
    """slot1.png .. slot9.png: a square hotbar slot with a 2 px border and the
    digit at 3x inside it, 40x40."""
    import numpy as np
    font = None
    for d in "123456789":
        path = out / f"slot{d}.png"
        if path.exists():
            continue
        font = _load_font(font)
        c = np.zeros((SLOT, SLOT), bool)
        b = SLOT_BORDER
        c[:b, :] = c[-b:, :] = c[:, :b] = c[:, -b:] = True
        g = _text(font, d, SLOT_SCALE, SLOT_SCALE)
        y, x = (SLOT - g.shape[0]) // 2, (SLOT - g.shape[1]) // 2
        c[y:y + g.shape[0], x:x + g.shape[1]] |= g
        cnc._save_mask(c, path)
        print(f"  {path.name}  <- slot + {d} (Press Start 2P, 3x)")


def program(out: Path) -> None:
    """program_java.png and program_bedrock.png: MINECRAFT at 1x across and 2x
    down (71x16), over the edition name at 1x, centred on the whole 72x40 cell."""
    import numpy as np
    font = None
    for stem, edition in (("program_java", "JAVA"), ("program_bedrock", "BEDROCK")):
        path = out / f"{stem}.png"
        if path.exists():
            print(f"  {path.name}  <- committed asset (left as-is)")
            continue
        font = _load_font(font)
        rows = [_text(font, "MINECRAFT", 1, 2), _text(font, edition)]
        gap = 5
        h = sum(r.shape[0] for r in rows) + gap
        c = np.zeros((40, 72), bool)
        y = (40 - h) // 2
        for r in rows:
            x = (72 - r.shape[1]) // 2
            c[y:y + r.shape[0], x:x + r.shape[1]] = r
            y += r.shape[0] + gap
        cnc._save_mask(c, path)
        print(f"  {path.name}  <- MINECRAFT / {edition} (Press Start 2P)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    flat_icons(out)
    drop_icons(out)
    slots(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
