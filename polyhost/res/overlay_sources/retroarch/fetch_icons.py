#!/usr/bin/env python3
"""Fetch and draw the RetroArch shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), both through `icon_fetch`. The joypad keys (the keyboard's default
RetroPad buttons) are drawn here at the size the keycap shows them, so the
generator copies them 1:1: a ring with the button letter, or a pill with
START / SELECT, in Press Start 2P (SIL OFL 1.1), whose 8 px grid stays exact at
1 bit. The ESC mark is the RetroArch logo from Simple Icons (CC0-1.0).
See SOURCES.md. `mame/fetch_icons.py` reuses `ring()` and `pill()`.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/retroarch/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402

FLUENT = {
    "menu":        "ms:menu",
    "reset":       "ms:restart_alt",
    "fastforward": "ms:fast_forward",
    "ffhold":      "ms:keyboard_double_arrow_right",
    "slowmo":      "ms:slow_motion_video",
    "rewind":      "ms:fast_rewind",
    "pause":       "ms:pause",
    "frameadv":    "ms:skip_next",
    "mute":        "ms:volume_off",
    "savestate":   "Save",
    "loadstate":   "Folder Open",
    "slotminus":   "ms:exposure_neg_1",
    "slotplus":    "ms:exposure_plus_1",
    "shader":      "ms:filter_b_and_w",
    "shadernext":  "ms:navigate_next",
    "shaderprev":  "ms:navigate_before",
    "cheat":       "ms:key",
    "screenshot":  "Camera",
    "grabmouse":   "ms:mouse",
    "fullscreen":  "ms:fullscreen",
    "fps":         "ms:speed",
    "desktopmenu": "ms:desktop_windows",
}

# Press Start 2P: every glyph sits on an 8 x 8 grid, so 8 px and 16 px are exact.
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/pressstart2p/PressStart2P-Regular.ttf")

RING_PX = 32      # a face button: a 2 px ring, its letter at 16 px
PILL_H = 14       # START / SELECT: a 2 px rounded outline around 8 px text


def _text_mask(text: str, px: int):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(str(cnc._font(FONT_URL)), px)
    l, t, r, b = f.getbbox(text)
    im = Image.new("L", (r - l, b - t), 0)
    ImageDraw.Draw(im).text((-l, -t), text, font=f, fill=255)
    return np.array(im) > 127


def ring(letter: str, dest: Path) -> None:
    """A RING_PX square: a 2 px circle with `letter` centred in it."""
    import numpy as np
    n = RING_PX
    yy, xx = np.mgrid[0:n, 0:n]
    c = (n - 1) / 2
    d = np.hypot(yy - c, xx - c)
    m = (d <= c + 0.2) & (d >= c - 2)
    g = _text_mask(letter, 16)
    y0, x0 = (n - g.shape[0]) // 2, (n - g.shape[1]) // 2
    m[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] |= g
    cnc._save_mask(m, dest)


def pill(text: str, dest: Path) -> None:
    """`text` at 8 px in a rounded outline PILL_H high, 3 px of space each side."""
    import numpy as np
    from PIL import Image, ImageDraw
    g = _text_mask(text, 8)
    w, h = g.shape[1] + 2 * 2 + 2 * 3, PILL_H
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, outline=255, width=2)
    m = np.array(im) > 127
    y0, x0 = (h - g.shape[0]) // 2, (w - g.shape[1]) // 2
    m[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] |= g
    cnc._save_mask(m, dest)


PAD = {"padb": "B", "pada": "A", "pady": "Y", "padx": "X", "padl": "L", "padr": "R"}
PILLS = {"padstart": "START", "padselect": "SELECT"}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    for name, letter in PAD.items():
        ring(letter, out / f"{name}.png")
    for name, text in PILLS.items():
        pill(text, out / f"{name}.png")
    brand_marks.ensure(out / "retroarch.png", "retroarch")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
