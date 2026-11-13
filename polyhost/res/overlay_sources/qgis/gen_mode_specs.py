#!/usr/bin/env python3
"""Write the QGIS map-tool mode specs from `bindings.yaml` (reproducible).

The QGIS plugin (`qgis-plugin/`) reports `qgis://map/<tool>[/cad][/edit]`.
A mode set REPLACES the main set (`layer: false` in the mapping), so each one
is the main set's bindings with the keys that change in that mode replaced:

    digitize.yaml       a capture tool (add feature, add part/ring, reshape, split)
    digitize_cad.yaml   the same with the Advanced Digitizing tools on
    vertex.yaml         the vertex tool
    vertex_cad.yaml     the same with the Advanced Digitizing tools on

`layout.yaml` (the print layout designer) is written by hand: its window has
its own actions and shares few keys with the main window.

Key sources (QGIS final-4_2_3, see SOURCES.md):
  src/gui/maptools/qgsmaptoolcapture.cpp   keyPressEvent: Backspace/Delete undo the last vertex
  src/app/vertextool/qgsvertextool.cpp     keyPressEvent: Del/Backspace, O, Shift+R, comma, period
  src/gui/qgsadvanceddigitizingdockwidget.cpp
      filterKeyPress, on the map canvas while CAD is on: X Y Z M A D focus a
      field; Shift+X/Y/Z/M/A relative; Ctrl or Alt + X/Y/M/A/D lock (Z: Alt
      only); C construction mode; P perpendicular/parallel; N / Shift+N
      next/previous common angle. canvasKeyPressEventFilter: Backspace/Delete
      remove the previous point.

    python polyhost/res/overlay_sources/qgis/gen_mode_specs.py           # write
    python polyhost/res/overlay_sources/qgis/gen_mode_specs.py --check   # compare only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
BASE = HERE / "bindings.yaml"

# Base keys that are left out of the digitizing modes, as (key, mods) pairs:
# Delete/Backspace act on the vertex, not the selected features.
DIGITIZE_DROP = {("DEL", ()), ("BSPC", ())}
DIGITIZE_ADD = [
    {"key": "BSPC", "mods": [], "icon": "removevertex.png", "label": "Remove last vertex"},
    {"key": "DEL", "mods": [], "icon": "removevertex.png", "label": "Remove last vertex"},
]

# The vertex tool is not a capture tool: stream digitizing (R), tracing (T) and
# "digitize with curve" (Ctrl+Shift+G) set the capture technique and do nothing here.
VERTEX_DROP = DIGITIZE_DROP | {("R", ()), ("T", ()), ("G", ("CMDCTRL", "SHIFT"))}
VERTEX_ADD = [
    {"key": "DEL", "mods": [], "icon": "deletevertex.png", "label": "Delete vertex"},
    {"key": "BSPC", "mods": [], "icon": "deletevertex.png", "label": "Delete vertex"},
    {"key": "O", "mods": [], "icon": "curve.png", "label": "Toggle curve vertex"},
    {"key": "R", "mods": ["SHIFT"], "icon": "rangesel.png", "label": "Range vertex selection"},
    {"key": "COMMA", "mods": [], "icon": "prevfeat.png", "label": "Previous vertex"},
    {"key": "DOT", "mods": [], "icon": "nextfeat.png", "label": "Next vertex"},
]

# Advanced Digitizing. Qt's ControlModifier is Cmd on macOS, so "Ctrl" is CMDCTRL.
_FIELDS = [("X", "x", True), ("Y", "y", True), ("Z", "z", False), ("M", "m", True),
           ("A", "a", True), ("D", "d", True)]
_NAMES = {"x": "X", "y": "Y", "z": "Z", "m": "M", "a": "angle", "d": "distance"}
CAD_ADD = []
for key, f, ctrl_locks in _FIELDS:
    CAD_ADD.append({"key": key, "mods": [], "icon": f"cad{f}.png",
                    "label": f"Enter {_NAMES[f]}"})
    if f != "d":
        CAD_ADD.append({"key": key, "mods": ["SHIFT"], "icon": f"cadrel{f}.png",
                        "label": f"Relative {_NAMES[f]}"})
    if ctrl_locks:
        CAD_ADD.append({"key": key, "mods": ["CMDCTRL"], "icon": f"cadlock{f}.png",
                        "label": f"Lock {_NAMES[f]}"})
    CAD_ADD.append({"key": key, "mods": ["ALT"], "icon": f"cadlock{f}.png",
                    "label": f"Lock {_NAMES[f]}"})
CAD_ADD += [
    {"key": "C", "mods": [], "icon": "construction.png", "label": "Construction mode"},
    {"key": "P", "mods": [], "icon": "cadperp.png", "label": "Perpendicular / parallel"},
    {"key": "N", "mods": [], "icon": "cadnext.png", "label": "Next common angle"},
    {"key": "N", "mods": ["SHIFT"], "icon": "cadprev.png", "label": "Previous common angle"},
]


def _sig(b):
    return (str(b["key"]), tuple(b.get("mods") or ()))


def _cmdctrl_equiv(sig):
    """The base set writes Ctrl+M (new map view) as CTRL, not CMDCTRL, because
    it is left out on macOS. On Windows and Linux both are Ctrl, so a CAD
    CMDCTRL key replaces it."""
    key, mods = sig
    return {sig, (key, tuple("CTRL" if m == "CMDCTRL" else m for m in mods))}


def _derive(base, drop, add, output, title):
    replaced = set(drop)
    for b in add:
        replaced |= _cmdctrl_equiv(_sig(b))
    keep = [b for b in base["bindings"] if _sig(b) not in replaced]
    spec = {k: v for k, v in base.items() if k != "bindings"}
    spec["output"] = output
    return title, spec, keep + add


def specs():
    base = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    return {
        "digitize.yaml": _derive(base, DIGITIZE_DROP, DIGITIZE_ADD, "qgis_digitize_template",
                                 "a capture tool (qgis://map/digitize)"),
        "digitize_cad.yaml": _derive(base, DIGITIZE_DROP, DIGITIZE_ADD + CAD_ADD,
                                     "qgis_digitize_cad_template",
                                     "a capture tool with Advanced Digitizing on "
                                     "(qgis://map/digitize/cad)"),
        "vertex.yaml": _derive(base, VERTEX_DROP, VERTEX_ADD, "qgis_vertex_template",
                               "the vertex tool (qgis://map/vertex)"),
        "vertex_cad.yaml": _derive(base, VERTEX_DROP, VERTEX_ADD + CAD_ADD,
                                   "qgis_vertex_cad_template",
                                   "the vertex tool with Advanced Digitizing on "
                                   "(qgis://map/vertex/cad)"),
    }


def render(name, title, spec, bindings) -> str:
    lines = [
        f"# GENERATED by gen_mode_specs.py from bindings.yaml -- do not edit.",
        f"# QGIS keys for {title}.",
        "#   python polyhost/res/overlay_sources/qgis/gen_mode_specs.py",
        f"#   python scripts/generate_app_overlays.py polyhost/res/overlay_sources/qgis/{name}",
    ]
    lines.append(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True,
                                default_flow_style=None, width=1000).rstrip())
    lines.append("bindings:")
    for b in bindings:
        lines.append("  - " + yaml.safe_dump(b, sort_keys=False, allow_unicode=True,
                                             default_flow_style=True, width=1000).strip())
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if a written spec is stale")
    args = ap.parse_args(argv)
    stale = []
    for name, (title, spec, bindings) in specs().items():
        text = render(name, title, spec, bindings)
        path = HERE / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.name}: {len(bindings)} bindings")
    if stale:
        print("stale (run gen_mode_specs.py): " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
