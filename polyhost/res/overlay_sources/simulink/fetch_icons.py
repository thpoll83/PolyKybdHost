#!/usr/bin/env python3
"""Fetch + render the Simulink Editor shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) for the `ms:` entries. Icons for the same action as a MATLAB,
LabVIEW or COMSOL key are byte copies of those sets' icons (BORROW). The ESC
mark is a 32x32 1-bit trace of the Simulink logo (see SOURCES.md); it is traced
only when the PNG is missing, so a committed or hand-edited mark is never
redrawn.

    pip install cairosvg
    python polyhost/res/overlay_sources/simulink/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.typingtests.fetch_icons import (  # noqa: E402
    _guarded, _load, trace_mark)

FLUENT = {
    "saveref": "ms:save_as",
    "changetab": "ms:tab",
    "undermask": "ms:visibility",
    "library": "ms:local_library",
    "explorer": "ms:travel_explore",
    "inspector": "ms:tune",
    "interface": "ms:settings_input_component",
    "typeeditor": "ms:data_object",
    "mainparam": "ms:edit_note",
    "quickinsert": "ms:add_box",
    "librarybrowser": "ms:widgets",
    "commentthrough": "ms:linear_scale",
    "arrange": "ms:auto_awesome_mosaic",
    "rotatecw": "ms:rotate_right",
    "rotateccw": "ms:rotate_left",
    "flip": "ms:flip",
    "subsystem": "ms:account_tree",
    "mask": "ms:masks",
    "refresh": "ms:sync",
    "updatemodel": "ms:update",
    "config": "ms:settings",
    "shortcuts": "ms:keyboard",
}

# Same action as a MATLAB, LabVIEW or COMSOL key: byte copies of their icons.
BORROW = {f"{n}.png": "matlab" for n in (
    "back", "forward", "comment", "run", "stop", "stepover", "stepin", "stepout")}
BORROW.update({"actualsize.png": "labview", "newmodel.png": "labview",
               "deselect.png": "comsol", "rename.png": "comsol",
               "build.png": "comsol"})
# A name that differs in the source set.
SOURCE_NAME = {"newmodel.png": "newvi.png", "build.png": "buildsel.png"}

# The Simulink logo (MathWorks, 2014), Wikimedia Commons
# "File:Simulink_Logo_(non-wordmark).png", public domain as a simple
# geometric logo; a MathWorks trademark. Rendered at 256 px.
MARK_URL = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
            "Simulink_Logo_(non-wordmark).png?width=256")
MARK_LUMA = 225
MARK_DARK_LIT = True


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    here = Path(__file__).resolve().parent.parent
    for name, app in sorted(BORROW.items()):
        dest = out / name
        src = here / app / "icons" / SOURCE_NAME.get(name, name)
        if dest.exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            dest.write_bytes(src.read_bytes())
            print(f"  {name}  <- copied from {app}/icons/{src.name}")
    _guarded(out / "simulink.png",
             lambda p: trace_mark(_load(MARK_URL), p, MARK_LUMA, MARK_DARK_LIT))
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
