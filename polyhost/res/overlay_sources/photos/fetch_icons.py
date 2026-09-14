#!/usr/bin/env python3
"""Fetch the Windows Photos shortcut icons (reproducible source step).

All glyphs are Microsoft Fluent UI System Icons (MIT) — the house style across
every PolyKybd app overlay, and license-clean against the GPL-3.0-or-later host.

⚠️ NO program mark is baked here. Photos runs as its own `Photos.exe`, so the
curated generic in `app_icons.yaml` (`photos: mdi:image-multiple`) resolves on
its own -- confirmed in a field daemon_log.txt (2026-09-14): `Program icon for
'photos': mdi:image-multiple`. That is the opposite of `calc`, which bakes its
mark because its process is a host.

    pip install cairosvg
    python polyhost/res/overlay_sources/photos/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

# filename -> Fluent folder name. Every one probed against
# raw.githubusercontent.com before being listed.
FLUENT = {
    "rotate":   "Arrow Rotate Clockwise",
    "zoomin":   "Zoom In",
    "zoomout":  "Zoom Out",
    # ⚠️ The BARE magnifier, not "Zoom Fit". Fit renders as four arrows radiating
    # from a box, which at 40x40 reads as the "Arrow Move" crop glyph three keys
    # away on this same overlay -- two unrelated actions, one silhouette. The
    # plain magnifier instead completes the family the two neighbours already
    # form (magnifier+, magnifier-, magnifier), so the reset reads from its
    # company. Decided by rendering the candidates side by side, not from names.
    "zoomrst":  "Search",
    "save":     "Save",
    "print":    "Print",
    "copy":     "Copy",
    "undo":     "Arrow Undo",
    "redo":     "Arrow Redo",
    # "view the ORIGINAL" — an eye, i.e. look at what it was, rather than
    # History (which reads as a list of past edits, a thing Photos has no
    # shortcut for) or Arrow Undo (already Ctrl+Z on this same overlay).
    "original": "Eye",
    "slides":   "Slide Play",
    "info":     "Info",
    "lock":     "Lock Closed",
    # The two crop families. ONE glyph per family, not per direction: the
    # direction is the arrow key's own legend, which the firmware draws anyway —
    # the same call as Sticky Notes' cycle-forward/backward pair.
    "cropsize": "Resize",
    "cropmove": "Arrow Move",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    count = icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {count} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
