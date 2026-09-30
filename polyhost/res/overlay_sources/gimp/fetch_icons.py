#!/usr/bin/env python3
"""Fetch + render the GIMP shortcut icons (reproducible source step).

Four kinds of icon live in `icons/`:

* RECLAIMED — the 39 tool/zoom icons and the ESC program mark of the previously
  shipped overlay, lifted pixel-for-pixel out of the old PNGs (72x40 cells,
  white on transparent). The old set was hand-drawn and has no other source, so
  these are committed assets: never fetched, never clobbered, and to be
  restored from git if lost.
* DERIVED — `zoomin.png`, the reclaimed `zoomout.png` magnifier with the minus
  turned into a plus, so Zoom in matches the reclaimed zoom family instead of
  borrowing a differently drawn magnifier. Guarded like a reclaimed asset.
* BORROWED — `dodgeburn.png`, the custom-drawn dodge glyph of the Photoshop
  overlay (same concept, same repo, GPL-3.0-or-later). Copied once and then
  guarded.
* Fetched — Microsoft Fluent UI System Icons (MIT) by folder name, or Google
  Material Symbols (Apache-2.0) for an `ms:` name. Deterministic, so a re-run
  may overwrite them freely.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/gimp/fetch_icons.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RECLAIMED = {
    "gimp.png",
    # Shift + tool
    "bucketfill.png", "crop.png", "flip.png", "bycolorselect.png",
    "perspective.png", "rotate.png", "shear.png", "scale.png",
    # bare tool keys
    "airbrush.png", "paths.png", "clone.png", "defaultcolors.png",
    "ellipseselect.png", "freeselect.png", "gradient.png", "heal.png",
    "iscissors.png", "ink.png", "move.png", "pencil.png", "colorpicker.png",
    "paintbrush.png", "align.png", "rectselect.png", "smudge.png", "text.png",
    "fuzzyselect.png", "warp.png", "swapcolors.png", "mypaint.png",
    "zoomtool.png",
    # view
    "zoom1_1.png", "zoom2_1.png", "zoom4_1.png", "zoom8_1.png", "zoom16_1.png",
    "zoomout.png", "searchactions.png", "help.png",
}

BORROWED = {  # name -> sibling app folder it is copied from
    "dodgeburn.png": "photoshop",
}

FLUENT = {
    # --- file ---
    "export": "ms:file_export",
    "exportas": "Document Arrow Right",
    "openaslayers": "Layer Diagonal Add",
    "closeall": "Dismiss Square Multiple",
    # --- edit ---
    "copyvisible": "Copy Select",
    "pasteasnewimage": "Image Add",
    "pasteinplace": "ms:content_paste_go",
    # --- image / layer ---
    "duplicateimage": "Image Multiple",
    "mergevisible": "Layer Diagonal",
    "newlayer": "Add Square",
    "duplicatelayer": "Layer",
    "anchorlayer": "ms:anchor",
    "toplayer": "ms:vertical_align_top",
    "bottomlayer": "ms:vertical_align_bottom",
    "imageproperties": "Info",
    # --- select ---
    "selectnone": "Select All Off",
    "invertselection": "Arrow Swap",
    "selectionfrompath": "ms:conversion_path",
    "quickmask": "Square Hint",
    # --- view ---
    "fitinwindow": "ms:fit_screen",
    "shrinkwrap": "Arrow Minimize",
    "centerimage": "ms:filter_center_focus",
    "rulers": "Ruler",
    # --- dialogs ---
    "toolbox": "Toolbox",
    "brushes": "ms:brush",
    "patterns": "ms:texture",
    "gradients": "ms:gradient",
    # --- filters ---
    "repeatfilter": "Arrow Repeat All",
    "reshowfilter": "Options",
    # --- tools (Shift+key) ---
    "eraser": "Eraser",
    "blursharpen": "Blur",
    "measure": "ms:straighten",
    "cage": "ms:polyline",
    "handletransform": "ms:control_camera",
    "unifiedtransform": "ms:transform",
    # --- help ---
    "contexthelp": "Question Circle",
}


def _derive_zoomin(out: Path) -> None:
    """Reclaimed zoom-out magnifier with its minus extended into a plus."""
    im = Image.open(out / "zoomout.png").convert("RGBA")
    px = im.load()
    for x in range(54, 60):
        for y in (22, 23):
            px[x, y] = (255, 255, 255, 255)
    for y in range(20, 26):
        for x in (56, 57):
            px[x, y] = (255, 255, 255, 255)
    im.save(out / "zoomin.png")


def main() -> int:
    here = Path(__file__).resolve().parent
    out = here / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    # Never fetched, never clobbered — see RECLAIMED above.
    for name in sorted(RECLAIMED):
        f = out / name
        print(f"  {name}  <- committed asset (left as-is)" if f.exists()
              else f"  !! {name} MISSING — restore it from git, it is not fetchable")
    if (out / "zoomin.png").exists():
        print("  zoomin.png  <- committed asset (left as-is)")
    else:
        _derive_zoomin(out)
        print("  zoomin.png  <- derived from zoomout.png")
    for name, app in sorted(BORROWED.items()):
        if (out / name).exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            shutil.copyfile(here.parent / app / "icons" / name, out / name)
            print(f"  {name}  <- copied from {app}/icons")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
