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


def aider():
    """The whole 'Ai' frame at half size; its lines are 2 px, so they stay 1 px."""
    m = _crop(_ink("aider.png") > 0.5)
    h, w = (m.shape[0] // 2) * 2, (m.shape[1] // 2) * 2
    return m[:h, :w].reshape(h // 2, 2, w // 2, 2).any(axis=(1, 3))


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
