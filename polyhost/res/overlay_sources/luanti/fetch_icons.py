#!/usr/bin/env python3
"""Fetch + render the Luanti (formerly Minetest) icons, reproducibly.

The set uses the block style of the Minecraft sets (../minecraft/): every key
icon is drawn on a grid of 2 px squares. Where Luanti has the same action as
Minecraft, the icon is the same picture, taken from the same source by the
Minecraft script's own functions. The other icons are flat silhouettes from
Font Awesome Free (CC BY 4.0) and game-icons.net (CC BY 3.0). The ESC mark is
LUANTI set in Monocraft (SIL OFL 1.1); the game's logo is CC BY-SA 3.0 and is
not used. SOURCES.md credits each icon.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/luanti/fetch_icons.py

The drawn files (slot1..slot10, drop, aux1, rangeup, rangedown, program) are
kept when they already exist, so a hand edit survives a re-run. Delete one to
draw it again.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.minecraft import fetch_icons as mc  # noqa: E402

# The same actions as in Minecraft: the same icon names, read from that set's
# table so a change there is followed here on the next run.
SHARED = ("forward", "left", "back", "right", "jump", "inventory", "chat", "command",
          "hidehud", "screenshot", "debug", "perspective", "fullscreen", "sprint")
ICONS = {
    **{stem: mc.ICONS[stem] for stem in SHARED},
    # Movement modes
    "fly": "fa:dove",
    "noclip": "fa:ghost",
    # View
    "zoom": "fa:magnifying-glass",
    "minimap": "fa:map",
    "fog": "fa:smog",
    # Chat
    "localcommand": "fa:laptop-code",
    "console": "fa:comments",
    "togglechat": "fa:comment-slash",
    # Hotbar
    "hotbarnext": "fa:angles-right",
    "hotbarprev": "fa:angles-left",
    # Sound and tools
    "mute": "fa:volume-xmark",
    "profiler": "fa:chart-line",
}
# Parts of rangeup.png and rangedown.png, drawn by range_icons().
PARTS = {"_range": "fa:mountain-sun"}

BLOCK = mc.BLOCK
# Key area of each icon, from luanti.yaml; the default is 40 x 40. The narrow
# ones keep the key's own legend whole (widths measured for AoE2, see
# ../aoe2/SOURCES.md, Placement).
SIZES = {"hidehud": (34, 40), "togglechat": (34, 40), "debug": (34, 40),
         "profiler": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box at the
# bottom right of their key area. The shared icons keep the Minecraft boxes.
INK = {**{stem: mc.INK[stem] for stem in SHARED if stem in mc.INK},
       "debug": (30, 30), "zoom": (32, 32), "minimap": (36, 32), "fog": (36, 32),
       "noclip": (30, 36), "fly": (36, 32), "localcommand": (38, 30),
       "console": (38, 30), "togglechat": (34, 28), "hotbarnext": (32, 32),
       "hotbarprev": (32, 32), "mute": (38, 30), "profiler": (32, 28)}

SLOT10_SCALE = 3   # "10" in the slot: two 5 x 7 digits at 3x
MARK = "LUANTI"
MARK_SCALE = (2, 3)   # the 5 x 7 Monocraft letters, 2x across and 3x down


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette in BLOCK px squares, drawn at
    exactly its key area so the generator places it 1:1 (as in ../minecraft/)."""
    import numpy as np
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        box = INK.get(stem, size)
        assert box[0] % BLOCK == 0 and box[1] % BLOCK == 0, (stem, box)
        m = mc._mask(out / f"{stem}.png", (box[0] // BLOCK, box[1] // BLOCK))
        m = np.kron(m, np.ones((BLOCK, BLOCK), bool))
        canvas = np.zeros((size[1], size[0]), bool)
        canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat, in {BLOCK} px blocks")


def _digit_font():
    from PIL import ImageFont
    return ImageFont.truetype(str(cnc._font(mc.DIGIT_FONT_URL)), mc.DIGIT_PX)


def slot10(out: Path) -> None:
    """slot10.png (the 0 key): the Minecraft hotbar slot with "10" inside."""
    import numpy as np
    path = out / "slot10.png"
    if path.exists():
        return
    c = np.zeros((mc.SLOT, mc.SLOT), bool)
    b = mc.SLOT_BORDER
    c[:b, :] = c[-b:, :] = c[:, :b] = c[:, -b:] = True
    g = mc._text(_digit_font(), "10", SLOT10_SCALE, SLOT10_SCALE, mc.DIGIT_PX)
    y, x = (mc.SLOT - g.shape[0]) // 2, (mc.SLOT - g.shape[1]) // 2
    c[y:y + g.shape[0], x:x + g.shape[1]] |= g
    cnc._save_mask(c, path)
    print("  slot10.png  <- slot + 10 (Monocraft, 3x)")


def aux1(out: Path) -> None:
    """aux1.png (E): the key's own name, AUX over 1, as the game's key list
    writes it. The key's effect depends on the game that runs in the engine."""
    import numpy as np
    path = out / "aux1.png"
    if path.exists():
        print("  aux1.png  <- committed asset (left as-is)")
        return
    font = _digit_font()
    top = mc._text(font, "AUX", 2, 2, mc.DIGIT_PX)
    one = mc._text(font, "1", 2, 2, mc.DIGIT_PX)
    c = np.zeros((40, 40), bool)
    y = 40 - one.shape[0] - 4 - top.shape[0]
    c[y:y + top.shape[0], 40 - top.shape[1]:] = top
    x = 40 - top.shape[1] // 2 - one.shape[1] // 2
    c[40 - one.shape[0]:, x - one.shape[1] // 2:x - one.shape[1] // 2 + one.shape[1]] = one
    cnc._save_mask(c, path)
    print("  aux1.png  <- AUX / 1 (Monocraft, 2x)")


def range_icons(out: Path) -> None:
    """rangeup.png (=) and rangedown.png (-): a far landscape over a plus or a
    minus, drawn on a 20 x 20 grid and doubled, so the squares match the other
    icons."""
    import numpy as np
    n = 40 // BLOCK
    eye = mc._mask(out / "_range.png", (n, 11))
    for stem, plus in (("rangeup", True), ("rangedown", False)):
        path = out / f"{stem}.png"
        if path.exists():
            print(f"  {stem}.png  <- committed asset (left as-is)")
            continue
        c = np.zeros((n, n), bool)
        c[0:eye.shape[0], n - eye.shape[1]:] = eye
        cy, cx = n - 5, n // 2 - 1
        c[cy:cy + 2, cx - 3:cx + 5] = True
        if plus:
            c[cy - 3:cy + 5, cx:cx + 2] = True
        cnc._save_mask(np.kron(c, np.ones((BLOCK, BLOCK), bool)), path)
        print(f"  {stem}.png  <- fa:mountain-sun over a {'plus' if plus else 'minus'}")


def program(out: Path) -> None:
    """program.png: LUANTI in Monocraft, centred on the whole 72x40 cell."""
    import numpy as np
    path = out / "program.png"
    if path.exists():
        print("  program.png  <- committed asset (left as-is)")
        return
    g = mc._text(_digit_font(), MARK, MARK_SCALE[0], MARK_SCALE[1], mc.DIGIT_PX)
    c = np.zeros((40, 72), bool)
    y, x = (40 - g.shape[0]) // 2, (72 - g.shape[1]) // 2
    c[y:y + g.shape[0], x:x + g.shape[1]] = g
    cnc._save_mask(c, path)
    print(f"  program.png  <- {MARK} (Monocraft, {g.shape[1]} x {g.shape[0]})")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    flat_icons(out)
    mc.sneak_icon(out)
    mc.slots(out)
    slot10(out)
    # mc.drop_icons() draws drop.png and dropstack.png; Luanti has no key that
    # drops a whole stack, so only drop.png is kept.
    mc.drop_icons(out)
    (out / "dropstack.png").unlink()
    aux1(out)
    range_icons(out)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
