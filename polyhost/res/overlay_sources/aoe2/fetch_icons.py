#!/usr/bin/env python3
"""Fetch + render the Age of Empires II shortcut icons (reproducible).

The shortcut icons are from game-icons.net (CC BY 3.0); each author is
credited in SOURCES.md. The ESC marks are drawn by program_mark.py.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/aoe2/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402

ICONS = {
    # selection and view
    "idlevillager": "delapouite/farmer",
    "idlemilitary": "lorc/crossed-swords",
    "towncenter": "delapouite/village",
    "notification": "lorc/ringing-bell",
    "previousview": "lorc/back-forth",
    # go to building
    "mill": "delapouite/windmill",
    "barracks": "delapouite/medieval-barracks",
    "archeryrange": "delapouite/bow-arrow",
    "stable": "delapouite/stable",
    "blacksmith": "lorc/anvil",
    "market": "delapouite/two-coins",
    "monastery": "delapouite/church",
    "castle": "delapouite/castle",
    "siegeworkshop": "heavenly-dog/catapult",
    "dock": "lorc/anchor",
    "lumbercamp": "delapouite/axe-in-log",
    "miningcamp": "lorc/mining",
    "university": "delapouite/graduate-cap",
    # game
    "techtree": "delapouite/family-tree",
    "pause": "guard13007/pause-button",
    "statistics": "delapouite/histogram",
    "gametime": "lorc/sands-of-time",
    "savegame": "delapouite/save",
    "diplomacy": "delapouite/shaking-hands",
    "flare": "delapouite/position-marker",
    "objectives": "delapouite/checklist",
    "chat": "lorc/conversation",
    "sendchat": "delapouite/chat-bubble",
    "allycolours": "delapouite/palette",
    "mapcombat": "lorc/sword-clash",
    "mapeco": "lorc/wheat",
    "mapnormal": "lorc/mountains",
    # parts composed in main(): chat review and save chapter
    "_conversation": "lorc/conversation",
    "_arrow": "delapouite/plain-arrow",
    "_quill": "lorc/quill-ink",
}

# Control groups: one unit per digit, drawn twice as a group (`groups()`).
GROUP_UNITS = {
    "1": "lorc/spartan",
    "2": "lorc/bowman",
    "3": "delapouite/cavalry",
    "4": "delapouite/viking-head",
    "5": "lorc/visored-helm",
    "6": "heavenly-dog/catapult",
    "7": "delapouite/siege-tower",
    "8": "delapouite/elephant",
    "9": "delapouite/drakkar",
    "0": "delapouite/farmer",
}
# The group icon is drawn at keycap scale, so the generator places it 1:1
# (aoe2_hd.yaml gives these bindings `region: [48, 40]`).
GROUP_W, GROUP_H = 48, 40
GROUP_DY = 6        # the front copy sits this much lower than the back one
GROUP_SEAM = 3      # black pixels between the two copies, and around the plus


def chat_review(out: Path) -> None:
    """Chat back / forward: the conversation icon with an up or down arrow."""
    from PIL import Image
    bubble = Image.open(out / "_conversation.png").convert("RGBA").resize((112, 112))
    arrow = Image.open(out / "_arrow.png").convert("RGBA").resize((64, 64))
    for name, rotate in (("chatback", 180), ("chatfwd", 0)):
        canvas = Image.new("RGBA", (160, 128), (0, 0, 0, 0))
        canvas.alpha_composite(bubble, (0, 8))
        canvas.alpha_composite(arrow.rotate(rotate), (100, 32))
        canvas.save(out / f"{name}.png")
        print(f"  {name}.png  <- _conversation.png + _arrow.png")


def save_chapter(out: Path) -> None:
    """Save chapter: the quill with the up arrow of the save icon (F12)."""
    from PIL import Image
    quill = Image.open(out / "_quill.png").convert("RGBA").resize((112, 112))
    arrow = Image.open(out / "_arrow.png").convert("RGBA").resize((56, 56))
    canvas = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    canvas.alpha_composite(quill, (0, 0))
    canvas.alpha_composite(arrow.rotate(180), (72, 72))
    canvas.save(out / "savechapter.png")
    print("  savechapter.png  <- _quill.png + _arrow.png")


def _unit_mask(src: Path, h: int):
    """A unit's ink at `h` px high, 1-bit."""
    import numpy as np
    from PIL import Image
    alpha = Image.open(src).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    w = max(1, round(alpha.width * h / alpha.height))
    return np.array(alpha.resize((w, h), Image.LANCZOS)) > 150


def _group_mask(src: Path):
    """The unit twice: a back copy, and a front copy shifted right by 40 % of its
    width and down GROUP_DY. The front copy's ink grown by GROUP_SEAM is cleared
    from the back copy. The largest height whose group fits GROUP_W x GROUP_H
    without rescaling, so the seam stays exactly GROUP_SEAM px."""
    import numpy as np
    for h in range(GROUP_H - GROUP_DY, 10, -1):
        m = _unit_mask(src, h)
        dx = max(8, m.shape[1] * 2 // 5)
        if m.shape[1] + dx <= GROUP_W:
            break
    H, W = h + GROUP_DY, m.shape[1] + dx
    back = np.zeros((H, W), bool)
    front = np.zeros((H, W), bool)
    back[:h, :m.shape[1]] = m
    front[GROUP_DY:, dx:] = m
    return (back & ~program_mark.dilate(front, GROUP_SEAM)) | front


def _with_plus(mask, size=13, bar=3):
    """A plus sign in the lower-right corner, GROUP_SEAM px clear around it."""
    import numpy as np
    H, W = mask.shape
    p = np.zeros((H, W), bool)
    cy, cx = H - size // 2 - 1, W - size // 2 - 1
    p[cy - bar // 2:cy + bar // 2 + 1, cx - size // 2:cx + size // 2 + 1] = True
    p[cy - size // 2:cy + size // 2 + 1, cx - bar // 2:cx + bar // 2 + 1] = True
    return (mask & ~program_mark.dilate(p, GROUP_SEAM)) | p


def _save_cell(mask, path: Path) -> None:
    """Black ink on transparent, bottom-right in a GROUP_W x GROUP_H canvas."""
    import numpy as np
    from PIL import Image
    canvas = np.zeros((GROUP_H, GROUP_W, 4), np.uint8)
    h, w = mask.shape
    canvas[GROUP_H - h:, GROUP_W - w:, 3] = np.where(mask, 255, 0)
    Image.fromarray(canvas, "RGBA").save(path)


def groups(out: Path, units=GROUP_UNITS) -> None:
    """group<N>.png (select) and groupnew<N>.png (create, with a plus), from
    _unit<N>.png for each digit in `units`. The C&C Remastered set calls this too."""
    for digit in units:
        g = _group_mask(out / f"_unit{digit}.png")
        _save_cell(g, out / f"group{digit}.png")
        _save_cell(_with_plus(g), out / f"groupnew{digit}.png")
        print(f"  group{digit}.png, groupnew{digit}.png  <- _unit{digit}.png twice")


def trim(out: Path, stem: str) -> None:
    """Crop an icon to its drawn area, so it fills a narrow area beside a wide legend."""
    from PIL import Image
    im = Image.open(out / f"{stem}.png").convert("RGBA")
    im.crop(im.getchannel("A").getbbox()).save(out / f"{stem}.png")
    print(f"  {stem}.png  trimmed to its drawn area")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_icons.render(ICONS, out)
    game_icons.render({f"_unit{d}": n for d, n in GROUP_UNITS.items()}, out, render_px=256)
    chat_review(out)
    save_chapter(out)
    for stem in ("idlevillager", "techtree", "statistics", "gametime", "savegame",
                 "previousview"):
        trim(out, stem)
    groups(out)
    program_mark.ensure(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
