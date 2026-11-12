#!/usr/bin/env python3
"""Fetch + render the Adobe Acrobat shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The ESC mark is a generic
"Ac" rectangle (`../rect_mark.py`), not Adobe's logo, sized with the other
Adobe marks.

    pip install cairosvg
    python polyhost/res/overlay_sources/acrobat/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, rect_mark  # noqa: E402

FLUENT = {
    # --- pages ---
    "gotopage": "ms:move_down",
    "firstpage": "ms:first_page",
    "lastpage": "ms:last_page",
    "prevpage": "Arrow Circle Up",
    "nextpage": "Arrow Circle Down",
    "insertblank": "Document Add",
    "insertfiles": "Document Arrow Up",
    "deletepages": "Document Dismiss",
    # --- view ---
    "fitpage": "ms:fit_screen",
    "actualsize": "ms:1x_mobiledata",
    "fullscreen": "Full Screen Maximize",
    "reflow": "ms:wrap_text",
    "menubar": "ms:menu",
    "navpane": "Panel Left",
    "taskpane": "Panel Right",
    # --- documents ---
    "nextdoc": "ms:tab",
    "prevdoc": "ms:tab_move",
    "nextwindow": "Window Multiple",
    "closedoc": "Document Dismiss",
    "closeall": "ms:tab_close",
    "findnext": "ms:manage_search",
    "prevresultdoc": "ms:arrow_back",
    "nextresultdoc": "ms:arrow_forward",
    # --- tools ---
    "jsdebugger": "Bug",
    "readingorder": "ms:format_list_numbered",
    "edittag": "ms:sell",
    "readingsettings": "ms:chrome_reader_mode",
    # --- read out loud ---
    "readaloud": "Speaker 2",
    "readpage": "ms:record_voice_over",
    "readdoc": "ms:text_to_speech",
    "readpause": "ms:pause",
    "readstop": "ms:stop",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    rect_mark.ensure(out / "acrobat.png", "Ac",
                     size=rect_mark.shared_size(["Ps", "Ai", "Pr", "Ae"]))
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
