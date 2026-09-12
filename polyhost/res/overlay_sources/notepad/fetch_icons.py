#!/usr/bin/env python3
"""Fetch + render the Windows Notepad shortcut icons (reproducible source step).

Style route: **all shortcut icons come from Microsoft Fluent UI System Icons
(MIT)** — the house style across every PolyKybd app overlay, and license-clean
against the GPL-3.0-or-later host. The ESC **program mark** is NOT baked here -- it
comes from the curated generic `mdi:note-text` (`polyhost/res/app_icons.yaml`);
Notepad's own product icon is Microsoft trademark art and neither catalog draws
it, so the generic says what the app IS instead of naming a brand.

⚠️ Notepad is closed source, so unlike Windows Terminal there is no `defaults.json`
to read. Every binding in `bindings.yaml` is one that TWO independent references
agree on; the ones only one reference claims are listed in SOURCES.md as
unverified rather than guessed at.

Where an action exists in Notepad++ too, the SAME Fluent glyph is used, so the
two editors' overlays read alike.

    pip install cairosvg
    python polyhost/res/overlay_sources/notepad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RENDER_PX = 96

# action filename -> Microsoft Fluent System Icon folder (all MIT).
# Probed against raw.githubusercontent.com before use -- there is no "Save As"
# folder, no "Calendar Ltr", no "Text Bullet List Ltr".
MS_ICONS = {
    # file  (same glyphs as the notepadpp overlay, deliberately)
    "new":        "Document Add",
    "open":       "Folder Open",
    "save":       "Save",
    "saveas":     "Save Edit",
    "print":      "Print",
    "closetab":   "Document Dismiss",
    "newwindow":  "Window New",
    "reopentab":  "Arrow Hook Up Left",
    "nexttab":    "Arrow Right",
    "prevtab":    "Arrow Left",
    # edit
    "undo":       "Arrow Undo",
    "redo":       "Arrow Redo",
    "cut":        "Cut",
    "copy":       "Copy",
    "paste":      "Clipboard Paste",
    "selectall":  "Select All On",
    "datetime":   "Calendar Clock",
    # search
    "find":       "Search",
    "findnext":   "Chevron Right",
    "findprev":   "Chevron Left",
    "replace":    "Arrow Swap",
    "goto":       "Text Position Line",
    # view / navigation
    "zoomin":     "Zoom In",
    "zoomout":    "Zoom Out",
    "zoomreset":  "Zoom Fit",
    "doctop":     "Arrow Upload",
    "docend":     "Arrow Download",
    "wordleft":   "Arrow Previous",
    "wordright":  "Arrow Next",
}



def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    icon_fetch.fluent(MS_ICONS, out)

    print(f"Wrote {len(MS_ICONS)} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
