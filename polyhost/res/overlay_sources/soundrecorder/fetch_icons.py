#!/usr/bin/env python3
"""Fetch the Windows Sound Recorder shortcut icons (reproducible source step).

All glyphs are Microsoft Fluent UI System Icons (MIT) — the house style across
every PolyKybd app overlay, and license-clean against the GPL-3.0-or-later host.

⚠️ NO program mark is baked here; the mapping entry names one with `icon:`
(mdi:microphone), because Sound Recorder is a Win11 packaged app and its process
is the host, not the app. See `ICON_APP` in handler/common.py.

    pip install cairosvg
    python polyhost/res/overlay_sources/soundrecorder/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

# filename -> Fluent folder name. Every one probed against
# raw.githubusercontent.com before being listed ("Skip Back 30" does not exist).
FLUENT = {
    "newrec":    "Record",
    "marker":    "Bookmark",
    "delrec":    "Delete",
    "playpause": "Play",
    "goback":    "Arrow Hook Up Left",
    "rename":    "Rename",
    # ⚠️ The seek family is drawn as THREE DISTINCT PAIRS, because the app binds
    # three different jump distances to keys that sit next to each other. They
    # are ordered by SIZE so the picture itself says which is bigger:
    #   Left/Right        = one step -> a single arrow
    #   Shift+Left/Right  = further  -> a double triangle
    #   Home/End          = the ends -> a triangle against a bar
    # One glyph for all six would put three different distances behind one
    # picture on six adjacent keycaps, which is exactly the ambiguity the
    # overlays exist to remove.
    #
    # ⚠️ NOT "Skip Back 10"/"Skip Forward 10", which is what the first cut used:
    # those glyphs have the NUMBER 10 drawn inside them, and the documented jump
    # is not ten seconds -- one reference says five and the other only says
    # "further". A glyph that states a wrong number is the "a wrong icon is worse
    # than no icon, because the user believes it" case, in its most literal form.
    # Seen on the rendered sheet; invisible from the folder names.
    "seekback":  "Arrow Left",
    "seekfwd":   "Arrow Right",
    "jumpback":  "Rewind",
    "jumpfwd":   "Fast Forward",
    "tostart":   "Previous",
    "toend":     "Next",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    count = icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {count} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
