#!/usr/bin/env python3
"""Fetch + render the Age of Empires II shortcut icons (reproducible).

All icons are from game-icons.net (CC BY 3.0); each author is credited in
SOURCES.md.

    pip install cairosvg
    python polyhost/res/overlay_sources/aoe2/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons  # noqa: E402

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
    "market": "delapouite/shop",
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


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_icons.render(ICONS, out)
    chat_review(out)
    save_chapter(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
