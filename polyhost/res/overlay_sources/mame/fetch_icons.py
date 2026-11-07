#!/usr/bin/env python3
"""Fetch and draw the MAME shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), through `icon_fetch`. The player 1 buttons are rings with the
button number and the start and coin keys are pills, drawn at keycap size by
`retroarch/fetch_icons.py`'s `ring()` and `pill()` in Press Start 2P (SIL OFL
1.1). The ESC mark is a "MAME" wordmark drawn here in pixels (`wordmark()`):
MAME's own icon is GPL-2.0 and the logo a registered trademark, so neither is
copied. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/mame/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from PIL import Image  # noqa: E402

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.retroarch import fetch_icons as ra  # noqa: E402

FLUENT = {
    "menu":       "ms:menu",
    "pause":      "ms:pause",
    "step":       "ms:skip_next",
    "rewindstep": "ms:skip_previous",
    "gfx":        "ms:grid_view",
    "savestate":  "Save",
    "quicksave":  "ms:save_as",
    "loadstate":  "Folder Open",
    "quickload":  "ms:file_open",
    "softreset":  "ms:restart_alt",
    "hardreset":  "ms:power_settings_new",
    "skipminus":  "ms:exposure_neg_1",
    "skipplus":   "ms:exposure_plus_1",
    "cheat":      "ms:key",
    "throttle":   "ms:speed",
    "fastfwd":    "ms:fast_forward",
    "snapshot":   "Camera",
    "recordmng":  "ms:videocam",
    "recordavi":  "ms:movie",
    "service":    "ms:build",
    "tilt":       "ms:vibration",
    "osd":        "ms:tune",
}

BUTTONS = {f"button{n}": str(n) for n in range(1, 7)}
PILLS = {"start1": "1UP", "start2": "2UP", "coin1": "COIN", "coin2": "COIN2"}

# The ESC wordmark, drawn at panel resolution: one grid cell is one OLED pixel.
# 37 x 13 fills the 37-px program-icon region exactly, so the generator scales
# it 1:1. Bold 2-px letters, slanted one pixel every MARK_SLANT_EVERY rows, with
# a 1-px horizontal slit at MARK_SLIT_ROW.
MARK_H = 13
MARK_SLANT_EVERY = 5
MARK_SLIT_ROW = 4
MARK_SCALE = 8          # each panel pixel becomes an 8x8 block in the PNG


def _blank(w: int) -> list[list[int]]:
    return [[0] * w for _ in range(MARK_H)]


def _letter_m(w: int = 9) -> list[list[int]]:
    g = _blank(w)
    for y in range(MARK_H):
        for x in (0, 1, w - 2, w - 1):
            g[y][x] = 1
    for r in range(1, 6):                       # the V, 2 px wide
        for x in (r, r + 1, w - 1 - r, w - 2 - r):
            g[r][x] = 1
    return g


def _letter_a(w: int = 8) -> list[list[int]]:
    g = _blank(w)
    for x in range(2, w - 2):
        g[0][x] = 1
    for x in range(1, w - 1):
        g[1][x] = 1
    for y in range(1, MARK_H):
        for x in (0, 1, w - 2, w - 1):
            g[y][x] = 1
    for y in (6, 7):
        for x in range(w):
            g[y][x] = 1
    return g


def _letter_e(w: int = 6) -> list[list[int]]:
    g = _blank(w)
    for y in range(MARK_H):
        g[y][0] = g[y][1] = 1
    for y in (0, 1, 11, 12):
        for x in range(w):
            g[y][x] = 1
    for y in (6, 7):
        for x in range(w - 1):
            g[y][x] = 1
    return g


def wordmark() -> list[list[int]]:
    """The MAME ESC mark as rows of 0/1, 37 x 13."""
    glyphs = [_letter_m(), _letter_a(), _letter_m(), _letter_e()]
    width = sum(len(g[0]) for g in glyphs) + len(glyphs) - 1
    slant = (MARK_H - 1) // MARK_SLANT_EVERY
    img = [[0] * (width + slant) for _ in range(MARK_H)]
    x0 = 0
    for g in glyphs:
        for y in range(MARK_H):
            shift = (MARK_H - 1 - y) // MARK_SLANT_EVERY
            for x, v in enumerate(g[y]):
                if v:
                    img[y][x0 + x + shift] = 1
        x0 += len(g[0]) + 1
    img[MARK_SLIT_ROW] = [0] * len(img[MARK_SLIT_ROW])
    return img


def save_wordmark(dest: Path) -> None:
    """Write the wordmark white on transparent, for `program_icon_mode: alpha`."""
    grid = wordmark()
    h, w = len(grid), len(grid[0])
    im = Image.new("RGBA", (w * MARK_SCALE, h * MARK_SCALE), (255, 255, 255, 0))
    for y in range(h):
        for x in range(w):
            if grid[y][x]:
                im.paste((255, 255, 255, 255),
                         (x * MARK_SCALE, y * MARK_SCALE,
                          (x + 1) * MARK_SCALE, (y + 1) * MARK_SCALE))
    im.save(dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    for name, text in BUTTONS.items():
        ra.ring(text, out / f"{name}.png")
    for name, text in PILLS.items():
        ra.pill(text, out / f"{name}.png")
    ra.word("FPS", out / "fps.png")
    save_wordmark(out / "mame.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
