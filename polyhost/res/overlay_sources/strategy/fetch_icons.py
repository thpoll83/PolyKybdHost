#!/usr/bin/env python3
"""Fetch + render the Paradox grand-strategy icons (reproducible).

One icon folder for six games (`eu4.yaml`, `eu5.yaml`, `ck3.yaml`,
`hoi4.yaml`, `stellaris.yaml`, `vic3.yaml`), because they share most of their
keys (pause, game speed, panels, ledger, find, capital, screenshot). Flat
1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`.
Numbered keys (speed 1-5, control groups, EU4 map-mode slots) carry their
number in the icon.

The ESC marks set each game's name in Cinzel (SIL OFL 1.1), a serif close to
the Paradox logos' capitals. No Paradox logo art is used. The marks are drawn
from code and a pinned font alone, so every run redraws them.

    PYTHONPATH=. python polyhost/res/overlay_sources/strategy/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

CINZEL = "ofl/cinzel/Cinzel[wght].ttf"

ICONS = {
    # Time
    "pause": "ms:pause",
    "pauseonly": "ms:pause_circle",
    "unpause": "ms:play_arrow",
    "faster": "ms:fast_forward",
    "slower": "ms:fast_rewind",
    "nextday": "ms:skip_next",
    "src_speed": "ms:speed",            # only drawn with its number
    "src_group": "ms:group_work",       # only drawn with its number
    "src_mapslot": "ms:map",            # only drawn with its number
    # Camera and navigation
    "panup": "ms:arrow_upward",
    "pandown": "ms:arrow_downward",
    "panleft": "ms:arrow_back",
    "panright": "ms:arrow_forward",
    "zoomin": "ms:zoom_in",
    "zoomout": "ms:zoom_out",
    "maxzoom": "ms:zoom_out_map",
    "scrollup": "ms:keyboard_double_arrow_up",
    "scrolldown": "ms:keyboard_double_arrow_down",
    "capital": "ms:home_pin",
    "focus": "ms:center_focus_strong",
    "rotation": "ms:3d_rotation",
    "cycle": "ms:autorenew",
    "back": "ms:arrow_back_ios",
    "forward": "ms:arrow_forward_ios",
    # Tools
    "find": "ms:search",
    "findtitle": "ms:manage_search",
    "charfinder": "ms:person_search",
    "searchfocus": "ms:pageview",
    "ledger": "ms:table_chart",
    "encyclopedia": "ms:menu_book",
    "outliner": "ms:list",
    "chat": "ms:chat",
    "help": "ms:help",
    "mapmenu": "ms:layers",
    "confirm": "ms:check",
    "decline": "ms:close",
    "undo": "ms:undo",
    "redo": "ms:redo",
    "alerts": "ms:notifications",
    "journal": "ms:import_contacts",
    "situation": "ms:report",
    "actionlist": "ms:pending_actions",
    "macro": "ms:view_module",
    "screenshot": "ms:screenshot_monitor",
    "mapshot": "ms:panorama",
    "hidegui": "ms:visibility_off",
    "lockcam": "ms:lock",
    # Panels
    "country": "ms:flag",
    "court": "gi:delapouite/throne-king",
    "royalcourt": "ms:workspace_premium",
    "government": "ms:account_balance",
    "diplomacy": "ms:handshake",
    "economy": "ms:payments",
    "trade": "ms:currency_exchange",
    "logistics": "ms:local_shipping",
    "technology": "ms:science",
    "ideas": "ms:lightbulb",
    "missions": "ms:task_alt",
    "decisions": "ms:gavel",
    "stability": "ms:balance",
    "religion": "ms:church",
    "military": "ms:swords",
    "subjects": "ms:account_tree",
    "estates": "ms:groups",
    "age": "ms:hourglass_top",
    "greatpowers": "ms:star_rate",
    "production": "ms:factory",
    "society": "ms:diversity_3",
    "geography": "ms:public",
    "content": "ms:article",
    "character": "ms:person",
    "realm": "ms:castle",
    "council": "ms:group",
    "intrigue": "gi:lorc/cloak-dagger",
    "factions": "ms:campaign",
    "openholding": "ms:location_city",
    "domicile": "ms:house",
    "culture": "ms:palette",
    "activities": "ms:hiking",
    "warview": "ms:military_tech",
    "faction": "ms:diversity_1",
    "intel": "ms:radar",
    "market": "ms:storefront",
    "construction": "ms:construction",
    "recruit": "ms:engineering",
    "navy": "ms:anchor",
    "air": "ms:flight",
    "budget": "ms:savings",
    "buildings": "ms:apartment",
    "powerbloc": "ms:hub",
    "companies": "ms:domain",
    "population": "ms:person_pin",
    "queuepause": "ms:pending",
    # Map modes
    "map_realms": "ms:flag_circle",
    "map_religions": "ms:temple_buddhist",
    "map_cultures": "ms:language",
    "map_houses": "ms:family_restroom",
    "map_duchies": "ms:shield",
    "map_kingdoms": "ms:crown",
    "map_empires": "ms:fort",
    "map_hegemonies": "ms:travel_explore",
    "map_plagues": "ms:coronavirus",
    "map_legends": "ms:auto_stories",
    "map_default": "ms:public_off",
    "map_naval": "ms:sailing",
    "map_air": "ms:cloud",
    "map_supply": "ms:inventory_2",
    "map_terrain": "ms:landscape",
    "map_resistance": "ms:local_police",
    "map_compliance": "ms:policy",
    "map_resource": "ms:energy_savings_leaf",
    "map_infrastructure": "ms:route",
    "map_factions": "ms:flag_2",
    "map_counters": "ms:badge",
    "map_colours": "ms:brightness_6",
    "map_battleplans": "ms:timeline",
    "map_daynight": "ms:nightlight",
    "map_empire": "ms:flag_circle",
    "map_diplomatic": "ms:waving_hand",
    "map_opinion": "ms:thumbs_up_down",
    "map_attitude": "ms:psychology",
    "map_neighbor": "ms:scatter_plot",
    "map_intel": "ms:visibility",
    "galaxy": "ms:travel_explore",
    "lens_production": "ms:precision_manufacturing",
    "lens_political": "ms:how_to_vote",
    "lens_diplomatic": "ms:waving_hand",
    "lens_military": "ms:military_tech",
    "lens_trade": "ms:sailing",
}

FKEY = (34, 40)   # the F-key area AoE2 measured (see the CS2 SOURCES.md)
F_ICONS = ("country", "court", "royalcourt", "government", "diplomacy", "economy", "trade",
           "technology", "ideas", "missions", "decisions", "production", "society", "geography",
           "content", "character", "realm", "military", "council", "intrigue", "factions",
           "encyclopedia", "ledger", "screenshot", "mapshot", "hidegui", "lockcam", "budget",
           "buildings", "market", "powerbloc", "population", "companies", "map_default",
           "map_naval", "map_air", "map_supply", "map_terrain", "map_resistance",
           "map_compliance", "map_resource", "map_infrastructure", "map_factions", "mapmenu")
SIZES = {s: FKEY for s in F_ICONS}
INK = {"chat": (34, 34), "character": (34, 34)}

NUMBERED = {f"speed{n}": ("src_speed", str(n), (24, 24)) for n in range(1, 6)}
NUMBERED.update({f"group{n}": ("src_group", str(n), (24, 24)) for n in range(10)})
NUMBERED.update({f"mapslot{n}": ("src_mapslot", str(n), (24, 24)) for n in range(1, 11)})

MARKS = {
    # stem: (top line, bottom line, top box, bottom box)
    "eu4": ("EUROPA IV", "UNIVERSALIS", (3, 2, 69, 19), (1, 22, 71, 38)),
    "eu5": ("EUROPA V", "UNIVERSALIS", (5, 2, 67, 19), (1, 22, 71, 38)),
    "ck3": ("CRUSADER", "KINGS III", (1, 2, 71, 19), (6, 21, 66, 38)),
    "hoi4": ("HEARTS OF", "IRON IV", (2, 2, 70, 18), (6, 21, 66, 38)),
    "stellaris": ("STELLARIS", None, (1, 8, 71, 32), None),
    "vic3": ("VICTORIA", "III", (1, 2, 71, 20), (22, 22, 50, 39)),
}


def mark(path: Path, top: str, bottom: str | None, top_box, bottom_box) -> None:
    """The game's name in Cinzel (Black weight): `top` over `bottom`."""
    im, d, P = game_set.mark_canvas()
    cinzel = game_set.google_font(CINZEL)
    game_set.fit_text(d, top, top_box, cinzel, variation=[900], stroke=2)
    if bottom:
        game_set.fit_text(d, bottom, bottom_box, cinzel, variation=[900], stroke=2)
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- {top} / {bottom or ''} (Cinzel)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, numbered=NUMBERED, mark=None)
    for stem, (top, bottom, tbox, bbox) in MARKS.items():
        mark(out / f"{stem}.png", top, bottom, tbox, bbox)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
