#!/usr/bin/env python3
"""Draw the OpenGOAL (Jak and Daxter PC port) key icons.

OpenGOAL maps the PlayStation 2 controller to the keyboard. Every key shows the
control it presses, drawn at keycap size by `pad_keys.ps_pad()`. The ESC mark is
"Open" over "GOAL" set in Russo One (SIL OFL 1.1). See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/opengoal/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import pad_keys  # noqa: E402

# The ESC mark is set in Russo One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/russoone/RussoOne-Regular.ttf")
MARK_LINES = ("Open", "GOAL")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    pad_keys.ps_pad(out)
    pad_keys.wordmark(MARK_LINES, out / "program.png", FONT_URL)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
