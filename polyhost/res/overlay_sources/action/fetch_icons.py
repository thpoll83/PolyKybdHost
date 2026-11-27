#!/usr/bin/env python3
"""Fetch + render the Elden Ring, Baldur's Gate 3, Cyberpunk 2077 and
Helldivers 2 icons (reproducible).

One icon folder for the four games (`eldenring.yaml`, `bg3.yaml`,
`cyberpunk.yaml`, `helldivers2.yaml`), because they share many actions (move,
jump, interact, inventory, map, quick save). Flat 1-bit silhouettes from
game-icons.net (CC BY 3.0, credit per author in SOURCES.md) and Material
Symbols (Apache-2.0), drawn by `game_set.py`. Numbered slots (hotbar, weapon
slots, party members) carry their number in the icon.

The ESC marks set each logo's words in a free font close to its lettering
(SIL OFL 1.1, google/fonts at the pinned commit): ELDEN / RING and BALDUR'S /
GATE III in Cinzel, CYBERPUNK / 2077 in Orbitron, HELLDIVERS / II in Black Ops
One. No publisher's logo art is used. The marks are drawn from code and pinned
fonts alone, so every run redraws them.

    PYTHONPATH=. python polyhost/res/overlay_sources/action/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

CINZEL = "ofl/cinzel/Cinzel[wght].ttf"
ORBITRON = "ofl/orbitron/Orbitron[wght].ttf"
BLACK_OPS = "ofl/blackopsone/BlackOpsOne-Regular.ttf"

ICONS = {
    # Movement (all four games; BG3 moves the camera)
    "forward": "ms:arrow_upward",
    "back": "ms:arrow_downward",
    "left": "ms:arrow_back",
    "right": "ms:arrow_forward",
    "jump": "gi:delapouite/jump-across",
    "crouch": "gi:delapouite/kneeling",
    "prone": "ms:airline_seat_flat",
    "dodge": "gi:lorc/dodging",
    "walk": "ms:directions_walk",
    "climb": "ms:stairs",
    "sneak": "gi:lorc/cloak-dagger",
    "groupsneak": "ms:group_off",
    # Actions
    "interact": "ms:touch_app",
    "reload": "ms:autorenew",
    "melee": "gi:lorc/punch",
    "heal": "ms:medical_services",
    "stim": "gi:lorc/syringe",
    "holster": "ms:back_hand",
    "useitem": "gi:lorc/drink-me",
    "lockon": "ms:my_location",
    "grenade": "gi:lorc/grenade",
    "throw": "gi:lorc/thrown-spear",
    "shove": "gi:delapouite/push",
    "weaponset": "ms:swap_horiz",
    "dualwield": "gi:lorc/crossed-swords",
    "groupmode": "ms:link",
    "drop": "ms:file_download",
    "backpack": "ms:luggage",
    "scanner": "ms:center_focus_weak",
    "cyberware": "ms:memory",
    "phone": "ms:smartphone",
    "callvehicle": "ms:directions_car",
    "radio": "ms:radio",
    "skipscene": "ms:fast_forward",
    "ping": "gi:delapouite/position-marker",
    "emote": "ms:sentiment_satisfied",
    "talk": "ms:mic",
    "src_weapon": "gi:john-colburn/pistol-gun",   # only drawn with its number
    "primary": "gi:skoll/ak47",
    "secondary": "gi:john-colburn/pistol-gun",
    "support": "gi:lorc/rocket",
    "grenadeslot": "gi:sbed/grenade",
    # Stratagem input (Helldivers 2: Ctrl held, then W A S D)
    "stratup": "ms:keyboard_double_arrow_up",
    "stratdown": "ms:keyboard_double_arrow_down",
    "stratleft": "ms:keyboard_double_arrow_left",
    "stratright": "ms:keyboard_double_arrow_right",
    # Elden Ring equipment slots (arrow keys)
    "switchspell": "gi:delapouite/spell-book",
    "switchitem": "ms:swap_vert",
    "switchright": "gi:lorc/broadsword",
    "switchleft": "gi:sbed/shield",
    # Turns (BG3)
    "endturn": "ms:skip_next",
    "turnbased": "ms:hourglass",
    "highlight": "ms:highlight",
    "examine": "ms:info",
    # Camera (BG3)
    "rotleft": "ms:rotate_left",
    "rotright": "ms:rotate_right",
    "zoomin": "ms:zoom_in",
    "zoomout": "ms:zoom_out",
    "center": "ms:filter_center_focus",
    "tactical": "ms:landscape",
    "src_hotbar": "ms:check_box_outline_blank",   # only drawn with its number
    "src_member": "gi:delapouite/person",        # only drawn with its number
    "nextchar": "ms:arrow_right",
    "prevchar": "ms:arrow_left",
    # Panels
    "hub": "ms:apps",
    "map": "ms:map",
    "journal": "ms:menu_book",
    "inventory": "ms:backpack",
    "perks": "ms:hub",
    "character": "ms:badge",
    "crafting": "ms:construction",
    "party": "ms:group",
    "spellbook": "ms:auto_stories",
    "illithid": "gi:lorc/brain",
    "reactions": "ms:bolt",
    "inspiration": "ms:lightbulb",
    "alchemy": "gi:lorc/round-bottom-flask",
    # System
    "quicksave": "ms:save",
    "quickload": "ms:restore_page",
    "photo": "ms:photo_camera",
    "hideui": "ms:visibility_off",
}

FKEY = (34, 40)   # the F-key area AoE2 measured (see the CS2 SOURCES.md)
SIZES = {s: FKEY for s in ("quicksave", "quickload", "photo", "hideui")}
INK = {"inventory": (34, 40), "character": (36, 34)}

NUMBERED = {f"hotbar{n}": ("src_hotbar", str(n), (24, 24)) for n in range(1, 13)}
NUMBERED.update({f"weapon{n}": ("src_weapon", str(n)) for n in range(1, 5)})
NUMBERED.update({f"member{n}": ("src_member", str(n), (22, 34), FKEY) for n in range(1, 5)})


def wordmark(path: Path, font: str, top: str, bottom: str, top_box, bottom_box,
             variation=None, stroke=0) -> None:
    """A mark of two lines: `top` over `bottom`."""
    im, d, P = game_set.mark_canvas()
    f = game_set.google_font(font)
    game_set.fit_text(d, top, top_box, f, variation=variation, stroke=stroke)
    game_set.fit_text(d, bottom, bottom_box, f, variation=variation, stroke=stroke)
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- {top} / {bottom}")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, numbered=NUMBERED, mark=None)
    wordmark(out / "eldenring.png", CINZEL, "ELDEN", "RING", (4, 1, 68, 19), (10, 21, 62, 39),
             variation=[700], stroke=2)
    wordmark(out / "bg3.png", CINZEL, "BALDUR'S", "GATE III", (1, 2, 71, 19), (6, 21, 66, 38),
             variation=[900], stroke=2)
    wordmark(out / "cyberpunk.png", ORBITRON, "CYBERPUNK", "2077", (1, 3, 71, 19), (12, 22, 60, 38),
             variation=[900])
    wordmark(out / "helldivers2.png", BLACK_OPS, "HELLDIVERS", "II", (1, 3, 71, 20), (26, 22, 46, 39))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
