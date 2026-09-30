#!/usr/bin/env python3
"""Fetch + render the Zoom meeting shortcut icons (reproducible source step).

One spec serves Windows, Linux and macOS. Zoom's Mac meeting keymap is a
REMAP of its Windows/Linux one (Alt+letter there, mostly Cmd+Shift+letter here),
so `bindings.yaml` writes most chords twice with disjoint `only:` lists; every
icon below is shared by both lines. See SOURCES.md.

Two kinds of icon live in `icons/`:

* RECLAIMED -- the 14 shortcut icons and the ESC program mark of the previously
  shipped hand-drawn overlay, lifted pixel-for-pixel out of the old PNGs (72x40
  cells, white on transparent). They have no other source, so they are committed
  assets: never fetched, never clobbered, restore them from git if lost.
* Fetched -- Microsoft Fluent UI System Icons (MIT) by folder name, or Google
  Material Symbols (Apache-2.0) for an `ms:` name. Deterministic, so a re-run may
  overwrite them freely.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/zoom/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RECLAIMED = {
    "zoom.png",
    "closechat.png", "showcontrols.png", "mute.png", "cloudrecord.png",
    "invite.png", "muteall.png", "switchcamera.png", "pauserecord.png",
    "localrecord.png", "sharescreen.png", "pauseshare.png", "participants.png",
    "video.png", "raisehand.png",
}

FLUENT = {
    "chatpanel": "Chat Multiple",
    "fullscreen": "Full Screen Maximize",
    "speakerview": "ms:record_voice_over",
    "galleryview": "Grid",
    "endmeeting": "Call End",
    "screenshot": "Screenshot",
    "unmuteall": "Mic",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    # Never fetched, never clobbered -- see RECLAIMED above.
    for name in sorted(RECLAIMED):
        f = out / name
        print(f"  {name}  <- committed asset (left as-is)" if f.exists()
              else f"  !! {name} MISSING -- restore it from git, it is not fetchable")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
