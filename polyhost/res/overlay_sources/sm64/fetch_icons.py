#!/usr/bin/env python3
"""Fetch and draw the key icons of the Super Mario 64 PC ports (sm64ex and
sm64coopdx).

Both ports map the Nintendo 64 controller to the keyboard. The keys show the
control they press, drawn at keycap size by `pad_keys.n64_pad()`; sm64coopdx
adds X and Y. The icons of sm64coopdx's own keys (chat, player list, console,
pages, disconnect) are Material Symbols (Apache-2.0) through `icon_fetch`. The
ESC marks are the port names set in Russo One (SIL OFL 1.1). See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/sm64/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, pad_keys  # noqa: E402

# sm64coopdx only
FLUENT = {
    "chat":       "ms:chat",
    "playerlist": "ms:group",
    "console":    "ms:terminal",
    "prevpage":   "ms:navigate_before",
    "nextpage":   "ms:navigate_next",
    "disconnect": "ms:link_off",
}

# The ESC marks are set in Russo One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/russoone/RussoOne-Regular.ttf")
MARKS = {"sm64ex": ("sm64", "ex"), "sm64coopdx": ("sm64", "coopdx")}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    pad_keys.n64_pad(out, extra="XY")
    for name, lines in MARKS.items():
        pad_keys.wordmark(lines, out / f"{name}.png", FONT_URL)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
