#!/usr/bin/env python3
"""Fetch and draw the Ship of Harkinian (Ocarina of Time PC port) key icons.

The port maps the Nintendo 64 controller to the keyboard. The keys show the
control they press, drawn at keycap size by `pad_keys.n64_pad()`. The two
hotkey icons are Material Symbols (Apache-2.0) through `icon_fetch`. The ESC
mark is "Ship of" over "Harkinian" set in Russo One (SIL OFL 1.1).
See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/soh/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, pad_keys  # noqa: E402

FLUENT = {
    "altassets": "ms:swap_horiz",
    "tts":       "ms:record_voice_over",
}

# The ESC mark is set in Russo One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/russoone/RussoOne-Regular.ttf")
MARK_LINES = ("Ship of", "Harkinian")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    pad_keys.n64_pad(out)
    pad_keys.wordmark(MARK_LINES, out / "program.png", FONT_URL)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
