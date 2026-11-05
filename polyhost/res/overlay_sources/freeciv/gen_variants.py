#!/usr/bin/env python3
"""Write the variant specs of the Freeciv set from freeciv.yaml.

freeciv.yaml holds the keys of the Freeciv 3.2 GTK clients. The other clients
and games share most of them, so each variant is the base list with a few
changes, applied in order:

    ("drop", key, mods)              remove a binding
    ("set", key, mods, {fields})     change fields of a binding (icon, label, region)
    ("add", {binding})               add a binding the base does not have
    ("keep", [(key, mods), ...])     remove every binding not in the list

Each step checks that the binding it names exists (or, for "add", that it does
not), so a change to freeciv.yaml that a variant depends on stops this script
instead of leaving a stale variant. tests/res/freeciv_spec_test.py checks that
the committed variant specs equal what this script writes.

    python polyhost/res/overlay_sources/freeciv/gen_variants.py
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
BASE = "freeciv.yaml"

# The binding fields, in the order they are written.
FIELDS = ("key", "mods", "icon", "label", "region", "shared")
# The spec fields above `bindings:`, in the order they are written.
SETTINGS = ("app", "match", "output", "icon_dir", "fit", "mode", "threshold", "anchor",
            "region", "margin", "program_icon", "program_icon_mode", "program_icon_region",
            "program_icon_margin", "program_icon_legend")

F34, F30 = [34, 40], [30, 40]
GROUPS = [(f"F{n}", mods) for n in "1234"
          for mods in (["SHIFT"], ["CTRL"], ["CTRL", "SHIFT"])]

# Freeciv 3.2.6 Qt client (client/gui-qt/shortcuts.cpp, menu.cpp, mapctrl.cpp).
QT_OPS = [
    ("set", "Z", [], {"icon": "delayed_goto.png", "label": "Delayed go to"}),
    ("add", {"key": "Z", "mods": ["SHIFT"], "icon": "select_single.png",
             "label": "Select single unit"}),
    ("set", "S", ["SHIFT"], {"icon": "rally.png", "label": "Set or unset rally point"}),
    ("add", {"key": "D", "mods": ["CTRL", "SHIFT"], "icon": "unsentry.png",
             "label": "Unsentry all on tile"}),
    ("add", {"key": "N", "mods": ["SHIFT"], "icon": "nuke.png", "label": "Go and explode nuclear"}),
    ("add", {"key": "B", "mods": ["SHIFT"], "icon": "go_build.png", "label": "Go and build city"}),
    ("add", {"key": "J", "mods": ["SHIFT"], "icon": "go_join.png", "label": "Go and join city"}),
    ("set", "T", ["CTRL"], {"icon": "trade_plan.png",
                            "label": "Add or remove city in trade planning"}),
    ("drop", "F9", []),
    ("add", {"key": "H", "mods": ["SHIFT"], "icon": "minimap.png", "label": "Minimap"}),
    ("drop", "P", ["CTRL", "SHIFT"]),
    ("drop", "G", ["CTRL", "SHIFT"]),
    ("drop", "Q", ["CTRL"]),
    ("set", "F", ["CTRL"], {"icon": "fullbar.png", "label": "City full bar"}),
    ("set", "L", ["CTRL", "SHIFT"], {"icon": "lock.png", "label": "Lock interface"}),
    ("drop", "R", ["CTRL", "SHIFT"]),
    ("drop", "F", ["CTRL", "SHIFT"]),
    ("set", "E", ["CTRL"], {"icon": "adv_select.png", "label": "Advanced unit selection"}),
    ("set", "Y", ["CTRL"], {"icon": "quick_airlift.png", "label": "Quick airlift"}),
    ("drop", "'", []),
    ("drop", "HOME", ["SHIFT"]),
    ("add", {"key": "ENTER", "mods": [], "icon": "chat.png", "label": "Chat line"}),
    ("add", {"key": "=", "mods": ["SHIFT"], "icon": "zoom_in.png", "label": "Zoom in",
             "shared": False}),
    ("add", {"key": "BACKSPACE", "mods": ["CTRL"], "icon": "zoom_std.png",
             "label": "Default zoom"}),
    ("add", {"key": "Z", "mods": ["CTRL"], "icon": "delayed_exec.png",
             "label": "Execute delayed orders"}),
    ("add", {"key": "C", "mods": ["CTRL", "SHIFT"], "icon": "clear_orders.png",
             "label": "Clear orders"}),
    ("add", {"key": "J", "mods": ["CTRL"], "icon": "auto_caravan.png",
             "label": "Automatic caravan"}),
    ("add", {"key": "SPACE", "mods": ["CTRL"], "icon": "units_sel.png",
             "label": "Units on the tile under the mouse"}),
    ("add", {"key": "ENTER", "mods": ["ALT"], "icon": "fullscreen.png", "label": "Fullscreen",
             "shared": False}),
]

# Freeciv21 3.1.3 (client/shortcuts.cpp, menu.cpp, mapctrl.cpp), on top of QT_OPS.
FC21_OPS = QT_OPS + [
    ("drop", "X", []),
    ("drop", "X", ["SHIFT"]),
    ("set", "M", ["CTRL"], {"icon": "minimap.png", "label": "Minimap"}),
    ("drop", "H", ["SHIFT"]),
    ("drop", "V", ["CTRL"]),
    ("add", {"key": "W", "mods": ["CTRL"], "icon": "city_output.png", "label": "City output"}),
    ("drop", "O", ["CTRL"]),
    ("drop", "O", ["SHIFT"]),
    ("set", "U", ["SHIFT"], {"icon": "unload_all.png", "label": "Unload all from transporter"}),
    ("drop", "T", ["SHIFT"]),
    ("add", {"key": "U", "mods": ["CTRL"], "icon": "upgrade.png", "label": "Upgrade unit"}),
    ("set", "P", [], {"label": "Clean pollution, or paradrop"}),
    ("drop", "J", []),
    ("add", {"key": "N", "mods": [], "icon": "fallout.png", "label": "Clean nuclear fallout"}),
] + [("drop", k, m) for k, m in GROUPS] + [
    ("add", {"key": "F1", "mods": ["CTRL"], "icon": "combat_info.png",
             "label": "Combat information", "region": F34}),
]

# Freeciv 3.2.6 SDL2 and SDL3 clients (client/gui-sdl2/menu.c, mapctrl.c,
# gui_main.c; the gui-sdl3 files bind the same keys).
SDL_OPS = [
    ("drop", "M", ["CTRL"]),
    ("drop", "Z", []),
    ("drop", "V", []),
    ("drop", "V", ["SHIFT"]),
    ("drop", "C", ["SHIFT"]),
    ("drop", "X", ["SHIFT"]),
    ("drop", "-", []),
    ("drop", "'", []),
    ("drop", "HOME", ["SHIFT"]),
    ("drop", "F1", []),
    ("set", "F9", [], {"label": "Show or hide messages"}),
    ("set", "SPACE", [], {"label": "No orders"}),
    ("drop", "T", ["CTRL"]),
    ("drop", "P", ["CTRL", "SHIFT"]),
    ("drop", "S", ["CTRL"]),
    ("drop", "Q", ["CTRL"]),
    ("drop", "L", ["CTRL", "SHIFT"]),
    ("drop", "R", ["CTRL", "SHIFT"]),
    ("drop", "F", ["CTRL", "SHIFT"]),
    ("drop", "E", ["CTRL"]),
    ("add", {"key": "N", "mods": ["SHIFT"], "icon": "nuke.png", "label": "Explode nuclear"}),
] + [("drop", k, m) for k, m in GROUPS]

# Civilization II: the 1996 manual (MicroProse), checked against the 2000
# printing. See SOURCES.md.
CIV2_OPS = [
    ("keep", [("B", []), ("R", []), ("I", []), ("M", []), ("O", []), ("F", []), ("P", []),
              ("P", ["SHIFT"]), ("U", []), ("G", []), ("H", []), ("S", []), ("D", ["SHIFT"]),
              ("W", []), ("SPACE", []), ("C", []), ("L", []), ("A", []), ("Z", []), ("X", []),
              ("X", ["SHIFT"]), ("C", ["SHIFT"]), ("T", []), ("T", ["SHIFT"]), ("V", []),
              ("S", ["CTRL"]), ("G", ["CTRL"]), ("T", ["CTRL"]), ("L", ["CTRL"]),
              ("O", ["CTRL"]), ("P", ["CTRL"]), ("E", ["CTRL"]), ("R", ["CTRL"]),
              ("F1", []), ("F2", []), ("F3", []), ("F4", []), ("F5", []), ("F6", []),
              ("F7", []), ("F8", []), ("F9", []), ("F11", []), ("F12", [])]),
    ("set", "B", [], {"label": "Build new city or join city"}),
    ("set", "R", [], {"label": "Build road or railroad"}),
    ("set", "I", [], {"label": "Build irrigation"}),
    ("set", "M", [], {"label": "Build mines"}),
    ("set", "O", [], {"label": "Transform"}),
    ("set", "P", [], {"label": "Clean up pollution"}),
    ("set", "S", [], {"label": "Sleep"}),
    ("set", "D", ["SHIFT"], {"label": "Disband"}),
    ("set", "SPACE", [], {"label": "Skip turn"}),
    ("set", "L", [], {"icon": "quick_airlift.png", "label": "Airlift"}),
    ("set", "A", [], {"icon": "activate.png", "label": "Activate unit"}),
    ("add", {"key": "E", "mods": [], "icon": "airbase.png", "label": "Build airbase"}),
    ("set", "Z", [], {"icon": "zoom_in.png", "label": "Zoom in", "shared": False}),
    ("set", "X", [], {"icon": "zoom_out.png", "label": "Zoom out", "shared": False}),
    ("add", {"key": "Z", "mods": ["CTRL"], "icon": "zoom_max.png", "label": "Maximum zoom in"}),
    ("add", {"key": "Z", "mods": ["SHIFT"], "icon": "zoom_std.png", "label": "Standard zoom"}),
    ("set", "X", ["SHIFT"], {"icon": "zoom_mid.png", "label": "Medium zoom out"}),
    ("set", "T", [], {"icon": "hidden_terrain.png", "label": "Show hidden terrain"}),
    ("set", "V", [], {"icon": "pieces.png", "label": "Move pieces or view pieces"}),
    ("set", "C", ["SHIFT"], {"icon": "find_city.png", "label": "Find city", "shared": False}),
    ("set", "T", ["SHIFT"], {"icon": "tax.png", "label": "Tax rate"}),
    ("add", {"key": "H", "mods": ["SHIFT"], "icon": "throne.png", "label": "View throne room"}),
    ("add", {"key": "R", "mods": ["SHIFT"], "icon": "revolution.png", "label": "Revolution"}),
    ("set", "G", ["CTRL"], {"label": "Show map grid"}),
    ("set", "T", ["CTRL"], {"icon": "council.png", "label": "Town council"}),
    ("set", "L", ["CTRL"], {"icon": "load_game.png", "label": "Load game"}),
    ("set", "O", ["CTRL"], {"icon": "options.png", "label": "Game options"}),
    ("set", "P", ["CTRL"], {"icon": "graphic_options.png", "label": "Graphic options"}),
    ("set", "E", ["CTRL"], {"icon": "report_options.png", "label": "City report options"}),
    ("set", "R", ["CTRL"], {"icon": "retire.png", "label": "Retire"}),
    ("set", "F1", [], {"icon": "city_status.png", "label": "City status"}),
    ("set", "F2", [], {"label": "Defense minister"}),
    ("set", "F3", [], {"label": "Foreign minister"}),
    ("set", "F4", [], {"icon": "attitude.png", "label": "Attitude advisor"}),
    ("set", "F5", [], {"label": "Trade advisor"}),
    ("set", "F6", [], {"label": "Science advisor"}),
    ("set", "F8", [], {"label": "Top 5 cities"}),
    ("set", "F9", [], {"icon": "score.png", "label": "Civilization score"}),
    ("set", "F12", [], {"label": "Spaceships"}),
]

# Civilization I (DOS): the IBM technical supplement and the manual
# (MicroProse). See SOURCES.md.
CIV1_OPS = [
    ("keep", [("B", []), ("R", []), ("I", []), ("M", []), ("F", []), ("S", []), ("G", []),
              ("W", []), ("SPACE", []), ("H", []), ("U", []), ("C", []), ("P", []),
              ("P", ["SHIFT"]), ("D", ["SHIFT"]), ("T", []), ("S", ["SHIFT"]), ("-", []),
              ("F1", []), ("F2", []), ("F3", []), ("F4", []), ("F5", []), ("F6", []),
              ("F7", []), ("F8", []), ("F9", [])]),
    ("set", "B", [], {"label": "Found new city"}),
    ("set", "R", [], {"label": "Build road or railroad"}),
    ("set", "I", [], {"label": "Agricultural improvement"}),
    ("set", "M", [], {"label": "Industrial improvement"}),
    ("set", "P", [], {"label": "Clear pollution"}),
    ("set", "D", ["SHIFT"], {"label": "Disband"}),
    ("set", "SPACE", [], {"label": "No orders"}),
    ("set", "H", [], {"label": "Home city"}),
    ("set", "U", [], {"label": "Unload ship"}),
    ("set", "C", [], {"label": "Center map on active unit"}),
    ("set", "T", [], {"icon": "pieces.png", "label": "Units on or off"}),
    ("set", "S", ["SHIFT"], {"icon": "save.png", "label": "Save game", "shared": False}),
    ("set", "-", [], {"icon": "luxury.png", "label": "Change luxury rate", "shared": None}),
    ("add", {"key": "=", "mods": [], "icon": "tax.png", "label": "Change tax rate"}),
    ("add", {"key": "/", "mods": ["SHIFT"], "icon": "find_city.png", "label": "Find city",
             "shared": False}),
    ("set", "F1", [], {"icon": "city_status.png", "label": "City status"}),
    ("set", "F2", [], {"label": "Military advisor"}),
    ("set", "F3", [], {"icon": "intelligence.png", "label": "Intelligence advisor"}),
    ("set", "F4", [], {"icon": "attitude.png", "label": "Attitude advisor"}),
    ("set", "F5", [], {"label": "Trade advisor"}),
    ("set", "F6", [], {"label": "Science advisor"}),
    ("set", "F8", [], {"label": "Top 5 cities"}),
    ("set", "F9", [], {"icon": "score.png", "label": "Civilization score"}),
    ("add", {"key": "F10", "mods": [], "icon": "world_map.png", "label": "World map"}),
]

VARIANTS = {
    "freeciv_qt.yaml": {
        "about": ["Freeciv 3.2 Qt client (freeciv-qt): its keys differ from the GTK",
                  "clients in the Multiplayer menu, the selection keys and several Ctrl keys."],
        "app": "freeciv_qt", "match": ["freeciv-qt", "freeciv-qt.exe", "org.freeciv.qt"],
        "output": "freeciv_qt_template", "program_icon": "program_freeciv.png", "ops": QT_OPS},
    "freeciv_sdl.yaml": {
        "about": ["Freeciv 3.2 SDL2 and SDL3 clients (freeciv-sdl2, freeciv-sdl3): the GTK",
                  "unit orders and reports, without the keys the SDL clients bind otherwise."],
        "app": "freeciv_sdl", "match": ["freeciv-sdl2", "freeciv-sdl3", "freeciv-sdl2.exe",
                                         "freeciv-sdl3.exe", "org.freeciv.sdl2",
                                         "org.freeciv.sdl3"],
        "output": "freeciv_sdl_template", "program_icon": "program_freeciv.png", "ops": SDL_OPS},
    "freeciv21.yaml": {
        "about": ["Freeciv21 3.1.3 (freeciv21-client), a fork of the Freeciv Qt client."],
        "app": "freeciv21", "match": ["freeciv21-client", "freeciv21-clien",
                                      "freeciv21-client.exe", "net.longturn.freeciv21"],
        "output": "freeciv21_template", "program_icon": "program_freeciv21.png", "ops": FC21_OPS},
    "civ2.yaml": {
        "about": ["Civilization II (civ2.exe; the name is not checked on an install): the",
                  "keys of the 1996 manual. The 2000 printing puts the advisors on 1 to 9,",
                  "- and = instead of the function keys; every other drawn key is the same."],
        "app": "civ2", "match": ["civ2", "civ2.exe"],
        "output": "civ2_template", "program_icon": "program_civ2.png", "ops": CIV2_OPS},
    "civ1.yaml": {
        "about": ["Civilization I (DOS) in DOSBox: the keys of the IBM technical supplement.",
                  "overlay-mapping.poly.yaml routes it by the DOSBox window title."],
        "app": "civ1", "match": ["civ1"],
        "output": "civ1_template", "program_icon": "program_civ1.png", "ops": CIV1_OPS},
}


def _id(key: str, mods) -> tuple[str, tuple[str, ...]]:
    return str(key).upper(), tuple(sorted(str(m).upper() for m in mods or []))


def _index(bindings: list[dict], key: str, mods) -> int:
    want = _id(key, mods)
    hits = [i for i, b in enumerate(bindings) if _id(b["key"], b.get("mods")) == want]
    if len(hits) != 1:
        raise SystemExit(f"{BASE}: expected one binding {key}+{mods}, found {len(hits)}")
    return hits[0]


def apply(bindings: list[dict], ops) -> list[dict]:
    """The bindings after `ops` (see the module docstring)."""
    out = [dict(b) for b in bindings]
    for op in ops:
        if op[0] == "drop":
            del out[_index(out, op[1], op[2])]
        elif op[0] == "set":
            b = out[_index(out, op[1], op[2])]
            for k, v in op[3].items():
                if v is None:
                    b.pop(k, None)
                else:
                    b[k] = v
        elif op[0] == "add":
            new = dict(op[1])
            want = _id(new["key"], new.get("mods"))
            if any(_id(b["key"], b.get("mods")) == want for b in out):
                raise SystemExit(f"{BASE}: binding {new['key']}+{new.get('mods')} already exists")
            out.append(new)
        elif op[0] == "keep":
            keep = {_id(k, m) for k, m in op[1]}
            for k, m in op[1]:
                _index(out, k, m)
            out = [b for b in out if _id(b["key"], b.get("mods")) in keep]
        else:
            raise SystemExit(f"unknown step {op[0]!r}")
    return out


def _scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_scalar(x) for x in v) + "]"
    s = str(v)
    if s.replace("_", "").replace("-", "").replace(".", "").isalnum() and s[0].isalpha():
        return s
    return json.dumps(s)


def _binding_line(b: dict) -> str:
    parts = []
    for k in FIELDS:
        if k not in b or (k == "mods" and not b[k]):
            continue
        v = b[k]
        parts.append(f"{k}: {json.dumps(str(v)) if k == 'label' else _scalar(v)}")
    extra = sorted(set(b) - set(FIELDS))
    if extra:
        raise SystemExit(f"binding {b['key']} has fields this script does not write: {extra}")
    return "  - { " + ", ".join(parts) + " }\n"


def render(name: str) -> str:
    """The text of the variant spec `name` for the current freeciv.yaml."""
    v = VARIANTS[name]
    base = yaml.safe_load((HERE / BASE).read_text(encoding="utf-8"))
    settings = {k: base[k] for k in SETTINGS if k in base}
    settings.update(app=v["app"], match=v["match"], output=v["output"],
                    program_icon=v["program_icon"])
    lines = [f"# GENERATED by gen_variants.py from {BASE} -- edit those files, not this one.\n"]
    lines += [f"# {s}\n" for s in v["about"]]
    lines.append("# Keys and sources: SOURCES.md.\n")
    lines += [f"{k}: {_scalar(settings[k])}\n" for k in SETTINGS if k in settings]
    lines.append("\nbindings:\n")
    lines += [_binding_line(b) for b in apply(base["bindings"], v["ops"])]
    return "".join(lines)


def main() -> int:
    for name in VARIANTS:
        (HERE / name).write_text(render(name), encoding="utf-8")
        print(f"{name} written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
