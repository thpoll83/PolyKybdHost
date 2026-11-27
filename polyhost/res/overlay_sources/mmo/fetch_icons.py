#!/usr/bin/env python3
"""Fetch + render the World of Warcraft and Final Fantasy XIV icons (reproducible).

One icon folder for both games (`wow.yaml`, `ffxiv.yaml`), because they share
most of their actions (move, jump, target, chat, bags, map). Flat 1-bit
silhouettes from game-icons.net (CC BY 3.0, credit per author in SOURCES.md)
and Material Symbols (Apache-2.0), drawn by `game_set.py`. Numbered slots
(action buttons, party members, bags) carry their number in the icon.

The ESC marks set each logo's words in Cinzel (SIL OFL 1.1), a serif close to
both logos' capitals: WORLD OF over WARCRAFT, and FINAL FANTASY over XIV.
Blizzard's and Square Enix's logo art is not used. The marks are drawn from
code and a pinned font alone, so every run redraws them.

    PYTHONPATH=. python polyhost/res/overlay_sources/mmo/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

CINZEL = "ofl/cinzel/Cinzel[wght].ttf"

ICONS = {
    # Movement (both games)
    "forward": "ms:arrow_upward",
    "back": "ms:arrow_downward",
    "strafeleft": "ms:arrow_back",
    "straferight": "ms:arrow_forward",
    "turnleft": "ms:rotate_left",
    "turnright": "ms:rotate_right",
    "jump": "gi:delapouite/jump-across",
    "descend": "ms:south",
    "autorun": "ms:directions_run",
    "sit": "ms:chair",
    "sheathe": "gi:lorc/broadsword",
    "pitchup": "ms:flight_takeoff",
    "pitchdown": "ms:flight_land",
    # Targeting
    "targetenemy": "ms:my_location",
    "prevenemy": "ms:location_searching",
    "targetfriend": "ms:person_search",
    "prevfriend": "ms:person_pin",
    "targetself": "ms:person",
    "src_party": "gi:delapouite/person",               # only drawn with its number
    "targetpet": "ms:pets",
    "src_partypet": "ms:cruelty_free",     # only drawn with its number
    "interact": "ms:touch_app",
    "ping": "gi:delapouite/position-marker",
    "nameplates": "ms:label",
    "friendplates": "ms:label_important",
    "allplates": "ms:new_label",
    "petattack": "gi:lorc/claw-slashes",
    "facetarget": "ms:center_focus_strong",
    "focustarget": "ms:filter_center_focus",
    "targetfocus": "ms:adjust",
    "nearestenemy": "ms:point_scan",
    "nearestnpc": "ms:person_pin_circle",
    "targetoftarget": "ms:double_arrow",
    "attacker": "ms:warning",
    "targetfilter": "ms:filter_alt",
    # Action bars
    "src_action": "ms:check_box_outline_blank",   # only drawn with its number
    "src_bonus": "ms:star",                # only drawn with its number
    "src_stance": "ms:self_improvement",   # only drawn with its number
    "src_hotbarset": "ms:view_agenda",     # only drawn with its number
    "hotbarup": "ms:keyboard_double_arrow_up",
    "hotbardown": "ms:keyboard_double_arrow_down",
    # Bags and panels
    "allbags": "ms:inventory_2",
    "backpack": "ms:backpack",
    "src_bag": "ms:shopping_bag",          # only drawn with its number
    "character": "ms:badge",
    "itemcompare": "ms:compare_arrows",
    "spellbook": "ms:auto_stories",
    "petbook": "ms:book_5",
    "collections": "ms:collections_bookmark",
    "talents": "ms:hub",
    "pvp": "ms:swords",
    "reputation": "ms:handshake",
    "professions": "ms:construction",
    "social": "gi:delapouite/three-friends",
    "guild": "gi:lorc/checked-shield",
    "adventureguide": "ms:menu_book",
    "groupfinder": "ms:group_add",
    "dungeons": "ms:castle",
    "achievements": "gi:delapouite/trophy-cup",
    "statistics": "ms:leaderboard",
    "questlog": "ms:history_edu",
    "worldmap": "ms:map",
    "minimap": "ms:explore",
    "housing": "ms:cottage",
    "housingeditor": "ms:architecture",
    "equipment": "ms:checkroom",
    "chatchannels": "ms:forum",
    "channelpullout": "ms:open_in_new",
    "scoreboard": "ms:scoreboard",
    # Panels (Final Fantasy XIV)
    "currency": "ms:payments",
    "armoury": "ms:shield",
    "saddlebag": "ms:luggage",
    "linkshells": "ms:lan",
    "signs": "ms:flag",
    "waymarks": "ms:pin_drop",
    "orchestrion": "ms:music_note",
    "timers": "ms:timer",
    "charconfig": "ms:manage_accounts",
    "sysconfig": "ms:settings",
    "craftlog": "ms:handyman",
    "gatherlog": "ms:forest",
    "huntlog": "ms:cruelty_free",
    "fishlog": "ms:phishing",
    "fishguide": "ms:set_meal",
    # Chat
    "chat": "ms:chat",
    "slash": "ms:terminal",
    "reply": "ms:reply",
    "replyback": "ms:reply_all",
    "chatup": "ms:expand_less",
    "chatdown": "ms:expand_more",
    "chatbottom": "ms:low_priority",
    "logup": "ms:keyboard_double_arrow_up",
    "logdown": "ms:keyboard_double_arrow_down",
    "logbottom": "ms:vertical_align_bottom",
    "say": "ms:chat_bubble",
    "shout": "ms:campaign",
    "partychat": "ms:group",
    "yell": "ms:record_voice_over",
    "fcchat": "gi:lorc/checked-shield",
    "pvpchat": "ms:swords",
    "alliancechat": "ms:diversity_3",
    "novicechat": "ms:eco",
    "lschat": "ms:link",
    "lschatback": "ms:link_off",
    "cwlschat": "ms:public",
    "cwlschatback": "ms:public_off",
    # Camera (Final Fantasy XIV)
    "camup": "ms:expand_less",
    "camdown": "ms:expand_more",
    "camleft": "ms:chevron_left",
    "camright": "ms:chevron_right",
    "tiltup": "ms:arrow_circle_up",
    "tiltdown": "ms:arrow_circle_down",
    "zoomin": "ms:zoom_in",
    "zoomout": "ms:zoom_out",
    "changecamera": "ms:switch_video",
    "returncamera": "ms:history",
    "savecamera": "ms:bookmark_add",
    "defaultcamera": "ms:settings_backup_restore",
    "flipcamera": "ms:flip_camera_android",
    "facecamera": "ms:face",
    # System
    "screenshot": "ms:screenshot_monitor",
    "toggleui": "ms:visibility_off",
    "fps": "ms:monitoring",
    "music": "ms:music_off",
    "sound": "ms:volume_off",
    "volup": "ms:volume_up",
    "voldown": "ms:volume_down",
    "nextview": "ms:videocam",
    "prevview": "ms:switch_video",
    "windowsize": "ms:fullscreen",
}

FKEY = (34, 40)   # the F-key area AoE2 measured (see the CS2 SOURCES.md)
F_ROW = ("targetself", "targetpet", "targetfocus", "nearestenemy", "nearestnpc", "screenshot",
         "toggleui")
SIZES = {s: FKEY for s in F_ROW}
INK = {"chat": (34, 34), "character": (36, 34), "backpack": (34, 40)}

NUMBERED = {f"action{n}": ("src_action", str(n), (24, 24)) for n in range(1, 13)}
NUMBERED.update({f"bonus{n}": ("src_bonus", str(n), (24, 24)) for n in range(1, 11)})
# On an F key (34 x 40): the party members, party pets, bags and stances.
FNUM = ((22, 34), FKEY)
NUMBERED.update({f"stance{n}": ("src_stance", str(n), *FNUM) for n in range(1, 11)})
NUMBERED.update({f"party{n}": ("src_party", str(n), *FNUM) for n in range(1, 9)})
NUMBERED.update({f"partypet{n}": ("src_partypet", str(n), *FNUM) for n in range(1, 5)})
NUMBERED.update({f"bag{n}": ("src_bag", str(n), *FNUM) for n in range(1, 5)})
NUMBERED.update({f"hotbarset{n}": ("src_hotbarset", str(n)) for n in range(1, 4)})


def wordmark(path: Path, top: str, bottom: str, top_box, bottom_box) -> None:
    """A mark of two lines of Cinzel (Black weight): `top` over `bottom`."""
    im, d, P = game_set.mark_canvas()
    cinzel = game_set.google_font(CINZEL)
    game_set.fit_text(d, top, top_box, cinzel, variation=[900], stroke=2)
    game_set.fit_text(d, bottom, bottom_box, cinzel, variation=[900], stroke=2)
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- {top} / {bottom} (Cinzel)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, numbered=NUMBERED, mark=None)
    # The logo sets WORLD OF small above a wide WARCRAFT.
    wordmark(out / "wow.png", "WORLD OF", "WARCRAFT", (12, 2, 60, 15), (1, 17, 71, 39))
    # The logo sets FINAL FANTASY above a large XIV.
    wordmark(out / "ffxiv.png", "FINAL FANTASY", "XIV", (1, 2, 71, 14), (16, 16, 56, 39))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
