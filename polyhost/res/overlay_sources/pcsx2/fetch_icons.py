#!/usr/bin/env python3
"""Fetch and draw the PCSX2 shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), through `icon_fetch`, with the same icon for the same action as
the RetroArch and MAME sets. The DualShock 2 controls are drawn at keycap size
by `pad_keys.ps_pad()`. The ESC mark is PCSX2's own icon
(`bin/resources/icons/AppIconLarge.png`, GPL-3.0-or-later like PCSX2), cut to
1 bit by `pad_keys.logo_mark()`. The mipmapping icon is drawn by `mipmap()`. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/pcsx2/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, pad_keys  # noqa: E402

FLUENT = {
    "savestate":   "Save",
    "loadstate":   "Folder Open",
    "slotplus":    "ms:exposure_plus_1",
    "slotminus":   "ms:exposure_neg_1",
    "framelimit":  "ms:speed",
    "pause":       "ms:pause",
    "turbo":       "ms:fast_forward",
    "ffhold":      "ms:keyboard_double_arrow_right",
    "slowmo":      "ms:slow_motion_video",
    "fullscreen":  "ms:fullscreen",
    "screenshot":  "Camera",
    "aspect":      "ms:aspect_ratio",
    "interlace":   "ms:blur_linear",
    "software":    "ms:memory",
    "gsdump":      "ms:download",
    "gsdumpmulti": "ms:burst_mode",
    "zoomout":     "ms:zoom_out",
}

# Mipmapping: a square, then the same square at half, a quarter and an eighth of
# its size, tucked into one corner, as a mip chain is usually drawn. Drawn at
# its exact key area (40 x 40) so the generator places it 1:1.
def mipmap(out: Path) -> None:
    import numpy as np
    from PIL import Image

    def box(c, x0, y0, x1, y1, t):
        c[y0:y0 + t, x0:x1] = c[y1 - t:y1, x0:x1] = True
        c[y0:y1, x0:x0 + t] = c[y0:y1, x1 - t:x1] = True

    m = np.zeros((40, 40), bool)
    box(m, 1, 1, 39, 39, 2)
    box(m, 19, 19, 39, 39, 2)
    box(m, 29, 29, 39, 39, 1)
    m[34:39, 34:39] = True
    rgba = np.zeros((40, 40, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.where(m, 255, 0)
    Image.fromarray(rgba, "RGBA").save(out / "mipmap.png")
    print("  mipmap.png  <- drawn")


# PCSX2's own icon at the release the keys were read from.
LOGO_URL = "https://raw.githubusercontent.com/PCSX2/pcsx2/v2.8.2/bin/resources/icons/AppIconLarge.png"


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    mipmap(out)
    pad_keys.ps_pad(out)
    pad_keys.logo_mark(out / "pcsx2.png", LOGO_URL, lit="alpha")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
