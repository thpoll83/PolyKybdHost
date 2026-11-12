#!/usr/bin/env python3
"""Fetch the FS-UAE shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), both through `icon_fetch`. The ESC mark is drawn here, 1 bit: a
double tick and "FS", the motif of FS-UAE's icon. The icon file itself is not
used: FS-UAE is GPL-2.0 without "or later". See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/fs_uae/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.retroarch import fetch_icons as ra  # noqa: E402

FLUENT = {
    "stretch":    "ms:aspect_ratio",
    "border":     "ms:border_outer",
    "freeze":     "ms:ac_unit",
    "debugger":   "ms:bug_report",
    "fullscreen": "ms:fullscreen",
    "grab":       "ms:mouse",
    "keyboard":   "ms:keyboard",
    "mute":       "ms:volume_off",
    "floppymute": "ms:hearing_disabled",
    "pause":      "ms:pause",
    "quit":       "ms:close",
    "softreset":  "ms:restart_alt",
    "hardreset":  "ms:power_settings_new",
    "screenshot": "Camera",
    "zoom":       "ms:zoom_in",
    "warp":       "ms:fast_forward",
    "voldown":    "ms:volume_down",
    "volup":      "ms:volume_up",
    "autozoom":   "ms:fit_screen",
    "menu":       "ms:menu",
    "perf":       "ms:monitoring",
}


def fs_uae_mark(dest: Path, w: int = 37, h: int = 32, stroke: int = 3, gap: int = 7) -> None:
    """Two check marks side by side with "FS" (Press Start 2P, 8 px) at the bottom
    right, drawn 1 bit at `w` x `h` so the spec places it 1:1."""
    import numpy as np
    from PIL import Image, ImageDraw
    im = Image.new("1", (w, h), 0)
    d = ImageDraw.Draw(im)
    tick_w = int(w * 0.62)
    for x in (0, gap):
        vx = x + tick_w * 0.30                 # the vertex at the bottom
        d.polygon([(x, h * 0.55), (x + stroke, h * 0.55),
                   (vx + stroke * 0.5, h - 1 - stroke * 1.6),
                   (x + tick_w - stroke, 0), (x + tick_w, 0),
                   (vx + stroke * 0.5, h - 1)], fill=1)
    m = np.array(im, bool)
    text = ra._text_mask("FS", 8)
    y, x = h - text.shape[0], w - text.shape[1]
    m[y - 1:h, x - 2:w] = False                # clear the ticks around the text
    m[y:, x:] |= text
    cnc._save_mask(m, dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    fs_uae_mark(out / "fs-uae.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
