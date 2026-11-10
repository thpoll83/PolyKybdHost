"""Write the agent-card marks for vendors that Simple Icons and MDI do not carry
(polyhost/res/icons/agents/<vendor>.png), from the ESC marks the AI CLI overlays
already use (res/overlay_sources/aicli/icons/). Each output is a finished 1-bit
mask, at most 16 rows tall: the card shows it as it is (services/agents/card.py).

    python tools/gen_agent_marks.py
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "polyhost", "res", "overlay_sources", "aicli", "icons")
OUT = os.path.join(ROOT, "polyhost", "res", "icons", "agents")
ROWS = 16      # card.MARK_SHOWN
BOX = 26       # card.MARK_BOX


def _ink(name):
    a = np.array(Image.open(os.path.join(SRC, name)).convert("RGBA")).astype(float)
    return (a[..., 3] / 255.0) * (a[..., :3].mean(-1) / 255.0)


def _crop(m):
    r, c = m.any(1).nonzero()[0], m.any(0).nonzero()[0]
    return m[r[0]:r[-1] + 1, c[0]:c[-1] + 1]


def qwen():
    """Simple Icons' qwen (CC0) at the cards' 26 px, its lower 16 rows."""
    ink = _crop(_ink("qwen.png") > 0.02).astype(float) * 255
    img = Image.fromarray(ink.astype(np.uint8))
    s = BOX / max(img.size)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    m = np.array(img) >= 110
    return _crop(m)[-ROWS:]


def opencode():
    """The ESC mark's lower 16 rows: the 'code' wordmark."""
    return _crop(_crop(_ink("opencode.png") > 0.5)[-ROWS:])


# Aider's logo is "aider" in the Glass TTY VT220 font, which draws every dot row
# as a dash with a dark line below it (scanlines). These 5 x 7 glyphs are that
# font's letters on its dot grid; each dot row becomes one lit row and one dark.
_VT220 = {
    "a": [".....", ".....", ".###.", "....#", ".####", "#...#", ".####"],
    "i": ["..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###."],
    "d": ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"],
    "e": [".....", ".....", ".###.", "#...#", "#####", "#....", ".###."],
    "r": [".....", ".....", "#.##.", ".#..#", ".#...", ".#...", ".#..."],
}


def aider():
    """'aider' in VT220 dots with scanlines, 13 x 29: Aider's own logo."""
    word = "aider"
    out = np.zeros((13, 6 * len(word) - 1), dtype=bool)
    for i, ch in enumerate(word):
        for row, line in enumerate(_VT220[ch]):
            for col, dot in enumerate(line):
                if dot == "#":
                    out[2 * row, 6 * i + col] = True
    return out


def antigravity():
    """Google's Material Symbols 'antigravity' (Apache 2.0), vendored in
    res/icons/agents/src/. The whole arch at 16 px: its lower rows alone read
    as two legs."""
    sys.path.insert(0, ROOT)
    from polyhost.services import app_icons
    m = app_icons.render_overlay(os.path.join(OUT, "src", "antigravity.svg"), box=ROWS)
    return _crop(m)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("qwen", qwen), ("opencode", opencode), ("aider", aider),
                     ("antigravity", antigravity)):
        m = fn()
        assert m.shape[0] <= ROWS, (name, m.shape)
        Image.fromarray(m.astype(np.uint8) * 255).convert("1").save(os.path.join(OUT, f"{name}.png"))
        print(name, m.shape)


if __name__ == "__main__":
    main()
