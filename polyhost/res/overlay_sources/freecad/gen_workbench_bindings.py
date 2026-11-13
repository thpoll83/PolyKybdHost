#!/usr/bin/env python3
"""Write one bindings spec per FreeCAD workbench whose default keys differ.

`bindings.yaml` is the fallback set: the global keys plus the single keys of
Sketcher, Draft and TechDraw together, for when no report from the FreeCAD
add-on (`freecad-addon/`) arrives. With the add-on the host knows the active
workbench (`freecad://<workbench>`) and shows one of these sets instead:

    bindings_global.yaml       every other workbench (PartDesign, Part, ...)
    bindings_sketcher.yaml     + the Sketcher constraint keys
    bindings_draft.yaml        + Draft's Shift+S and Shift+Space
    bindings_bim.yaml          + Shift+S and the BIM keys
    bindings_techdraw.yaml     + TechDraw's D, Shift+H and Shift+V
    bindings_assembly.yaml     + the Assembly joint and tool keys
    bindings_spreadsheet.yaml  + the Spreadsheet style keys (Ctrl+B is Bold here)

The global set is `bindings.yaml` without the workbench keys. A workbench key
replaces a global binding on the same key and modifiers. Shortcuts are from
FreeCAD's source at tag 1.1.4 (see SOURCES.md).

    python polyhost/res/overlay_sources/freecad/gen_workbench_bindings.py
    for f in polyhost/res/overlay_sources/freecad/bindings_*.yaml; do
        python scripts/generate_app_overlays.py "$f"; done
"""
from __future__ import annotations

from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent

# Keys of the fallback set that belong to one workbench (key, modifiers).
SKETCHER_KEYS = set("DAHVCOLIPNTRESW")
FALLBACK_WORKBENCH = {
    "draft": {("S", ("SHIFT",)), ("SPACE", ("SHIFT",))},
    "techdraw": {("H", ("SHIFT",)), ("V", ("SHIFT",))},
}

# Keys that are not in the fallback set (sAccel / "Accel" in the 1.1.4 source).
EXTRA = {
    "techdraw": [
        {"key": "D", "mods": [], "icon": "dimension.png", "label": "Dimension (TechDraw)"},
    ],
    "bim": [
        {"key": "DEL", "mods": ["SHIFT"], "icon": "trash.png", "label": "Move to trash"},
        {"key": "9", "mods": ["CMDCTRL"], "icon": "viewsmanager.png", "label": "Views manager"},
        {"key": "0", "mods": ["CMDCTRL"], "icon": "panelbottom.png", "label": "Toggle bottom panels"},
        {"key": "9", "mods": [], "icon": "wpview.png", "label": "Working plane view"},
        {"key": "SLASH", "mods": ["CMDCTRL"], "icon": "nudgeswitch.png", "label": "Nudge switch"},
        {"key": "PGUP", "mods": ["CMDCTRL"], "icon": "nudgeextend.png", "label": "Nudge extend"},
        {"key": "PGDN", "mods": ["CMDCTRL"], "icon": "nudgeshrink.png", "label": "Nudge shrink"},
        {"key": "DOT", "mods": ["CMDCTRL"], "icon": "rotright.png", "label": "Nudge rotate right"},
    ],
    "assembly": [
        {"key": "I", "mods": [], "icon": "insertcomp.png", "label": "Insert component"},
        {"key": "F", "mods": [], "icon": "fixedjoint.png", "label": "Fixed joint"},
        {"key": "R", "mods": [], "icon": "revolute.png", "label": "Revolute joint"},
        {"key": "C", "mods": [], "icon": "cylindrical.png", "label": "Cylindrical joint"},
        {"key": "S", "mods": [], "icon": "slider.png", "label": "Slider joint"},
        {"key": "B", "mods": [], "icon": "balljoint.png", "label": "Ball joint"},
        {"key": "D", "mods": [], "icon": "dimension.png", "label": "Distance joint"},
        {"key": "N", "mods": [], "icon": "parallel.png", "label": "Parallel joint"},
        {"key": "M", "mods": [], "icon": "perpendicular.png", "label": "Perpendicular joint"},
        {"key": "X", "mods": [], "icon": "angle.png", "label": "Angle joint"},
        {"key": "Q", "mods": [], "icon": "rackpinion.png", "label": "Rack and pinion joint"},
        {"key": "W", "mods": [], "icon": "screwjoint.png", "label": "Screw joint"},
        {"key": "T", "mods": [], "icon": "gears.png", "label": "Gears joint"},
        {"key": "L", "mods": [], "icon": "beltjoint.png", "label": "Belt joint"},
        {"key": "G", "mods": [], "icon": "gearbelt.png", "label": "Gears/belt joint"},
        {"key": "O", "mods": [], "icon": "bom.png", "label": "Bill of materials"},
        {"key": "A", "mods": [], "icon": "newassembly.png", "label": "New assembly"},
        {"key": "Z", "mods": [], "icon": "solve.png", "label": "Solve assembly"},
        {"key": "P", "mods": [], "icon": "newpart.png", "label": "New part"},
        {"key": "E", "mods": [], "icon": "exploded.png", "label": "Exploded view"},
        {"key": "V", "mods": [], "icon": "simulation.png", "label": "Simulation"},
    ],
    "spreadsheet": [
        {"key": "B", "mods": ["CMDCTRL"], "icon": "bold.png", "label": "Bold"},
        {"key": "I", "mods": ["CMDCTRL"], "icon": "italic.png", "label": "Italic"},
        {"key": "U", "mods": ["CMDCTRL"], "icon": "underline.png", "label": "Underline"},
        {"key": "A", "mods": ["CMDCTRL", "SHIFT"], "icon": "alias.png", "label": "Set alias"},
    ],
}

# Which fallback groups each workbench set takes, beside its EXTRA keys.
# BIM loads Draft's snap toolbar (Shift+S) but not Draft_ToggleDisplayMode.
SETS = {
    "global": (),
    "sketcher": ("sketcher",),
    "draft": ("draft",),
    "bim": ("bim_snap",),
    "techdraw": ("techdraw",),
    "assembly": (),
    "spreadsheet": (),
}

HEADER = """\
# GENERATED by gen_workbench_bindings.py from bindings.yaml. Do not edit.
# FreeCAD 1.1 overlay for the {name} workbench set, shown while the FreeCAD
# add-on (freecad-addon/) reports {routes}. See SOURCES.md.
"""


def _sig(b):
    return str(b["key"]), tuple(sorted(b.get("mods") or ()))


def group_of(b):
    """The workbench group of a fallback binding, or None for a global key."""
    key, mods = _sig(b)
    if not mods and len(key) == 1 and key in SKETCHER_KEYS:
        return "sketcher"
    for name, sigs in FALLBACK_WORKBENCH.items():
        if (key, mods) in sigs:
            return name
    return None


def build(fallback):
    """{set name: list of bindings} from the fallback spec."""
    bindings = fallback["bindings"]
    global_ = [b for b in bindings if group_of(b) is None]
    groups = {}
    for b in bindings:
        g = group_of(b)
        if g is not None:
            groups.setdefault(g, []).append(b)
    groups["bim_snap"] = [b for b in groups.get("draft", []) if _sig(b) == ("S", ("SHIFT",))]
    out = {}
    for name, takes in SETS.items():
        wb = [b for g in takes for b in groups.get(g, [])] + EXTRA.get(name, [])
        taken = {_sig(b) for b in wb}
        out[name] = [b for b in global_ if _sig(b) not in taken] + wb
    return out


def _dump_binding(b):
    return "  - " + yaml.safe_dump(b, default_flow_style=True, sort_keys=False,
                                   allow_unicode=True, width=200).strip()


def main() -> int:
    fallback = yaml.safe_load((HERE / "bindings.yaml").read_text(encoding="utf-8"))
    routes = {"global": "any other workbench"}
    for name, bindings in build(fallback).items():
        spec = {k: v for k, v in fallback.items() if k != "bindings"}
        spec["output"] = f"freecad_{name}_template"
        head = yaml.safe_dump(spec, sort_keys=False, default_flow_style=None)
        text = (HEADER.format(name=name, routes=routes.get(name, f"freecad://{name}"))
                + head + "\nbindings:\n" + "\n".join(_dump_binding(b) for b in bindings) + "\n")
        path = HERE / f"bindings_{name}.yaml"
        path.write_text(text, encoding="utf-8")
        print(f"Wrote {path.name} ({len(bindings)} bindings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
