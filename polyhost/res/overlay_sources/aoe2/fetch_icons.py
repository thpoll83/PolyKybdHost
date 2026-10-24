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
    # control groups and the ESC mark
    "groupselect": "lorc/backup",
    "program": "lorc/swords-emblem",
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


def group_create(out: Path) -> None:
    """Create group (Ctrl+digit): the squad of "Select group" with a plus sign."""
    from PIL import Image, ImageDraw
    squad = Image.open(out / "groupselect.png").convert("RGBA")
    canvas = Image.new("RGBA", (squad.width + 56, squad.height), (0, 0, 0, 0))
    canvas.alpha_composite(squad, (0, 0))
    d = ImageDraw.Draw(canvas)
    cx, cy = squad.width + 30, squad.height // 2
    d.rectangle((cx - 22, cy - 7, cx + 22, cy + 7), fill=(0, 0, 0, 255))
    d.rectangle((cx - 7, cy - 22, cx + 7, cy + 22), fill=(0, 0, 0, 255))
    canvas.save(out / "groupcreate.png")
    print("  groupcreate.png  <- groupselect.png + a plus sign")


def trim(out: Path, stem: str) -> None:
    """Crop an icon to its drawn area, so it fills a narrow area beside a wide legend."""
    from PIL import Image
    im = Image.open(out / f"{stem}.png").convert("RGBA")
    im.crop(im.getchannel("A").getbbox()).save(out / f"{stem}.png")
    print(f"  {stem}.png  trimmed to its drawn area")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_icons.render(ICONS, out)
    chat_review(out)
    save_chapter(out)
    for stem in ("idlevillager", "techtree", "statistics", "gametime", "savegame",
                 "previousview", "groupselect"):
        trim(out, stem)
    group_create(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
