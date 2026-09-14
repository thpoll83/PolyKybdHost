#!/usr/bin/env python3
"""Fetch + render the Microsoft Paint shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** via the shared
`icon_fetch` helper — the house style, and license-clean against the
GPL-3.0-or-later host. The ESC **program mark** is NOT baked here -- it comes from the
curated generic `mdi:palette` (`polyhost/res/app_icons.yaml`), which says what
the app IS and reads better at 40x40 than the letter tile it replaced.

⚠️ Paint is closed source, so there is no keymap file to read. `bindings.yaml`
carries only what two independent references agree on; see SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/mspaint/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    # file  (same glyphs as the other Windows overlays, deliberately)
    "new":       "Document Add",
    "open":      "Folder Open",
    "save":      "Save",
    "saveas":    "Save Edit",
    "print":     "Print",
    # edit
    "undo":      "Arrow Undo",
    "redo":      "Arrow Redo",
    "cut":       "Cut",
    "copy":      "Copy",
    "paste":     "Clipboard Paste",
    "selectall": "Select All On",
    # image
    "imageprops": "Image",
    "resize":     "Resize Image",
    # text formatting (the Text tool)
    "bold":      "Text Bold",
    "italic":    "Text Italic",
    "underline": "Text Underline",
    # view
    "grid":      "Grid",
    "ruler":     "Ruler",
    "zoomin":    "Zoom In",
    "zoomout":   "Zoom Out",
    "fullscreen": "Full Screen Maximize",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
