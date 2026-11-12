#!/usr/bin/env python3
"""Fetch + render the icons for the local-model chat apps: LM Studio and Jan.

Companion of `fetch_icons.py` (which builds the Claude / ChatGPT / Codex
icons). Kept separate only so it could be added without touching that script;
both write into the same `icons/` folder and reuse each other's glyphs by NAME,
so `newchat.png`, `search.png`, `sidebar.png`, `settings.png` and `model.png`
come from `fetch_icons.py` and are not rebuilt here. Run that one first.

Style route: Microsoft Fluent UI System Icons (MIT), as for the rest of the
folder. Program marks:

* Jan -- its own app icon from the Jan repo (`src-tauri/icons/icon.png`,
  Apache-2.0, GPLv3-compatible), pinned to a commit.
* LM Studio -- closed source, and in neither Simple Icons nor MDI, so it gets
  a drawn generic mark: a rounded box holding five bars offset along one
  period of a vertical sine wave (`_lmstudio_mark`). Picked by the maintainer
  over the earlier `LM` letter frame.

Both marks are guarded: a committed file is never overwritten by a re-run.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/aichat/fetch_icons.py
    python polyhost/res/overlay_sources/aichat/fetch_icons_localai.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
from PIL import Image  # noqa: E402

FLUENT = {
    # --- LM Studio ---
    "newfolder": "Folder Add",          # Ctrl+Shift+N new chat folder; Jan Ctrl+P new project
    "discover": "ms:explore",             # Ctrl+2 Discover tab (find + download models)
    "mymodels": "Library",              # Ctrl+3 My Models tab
    "runtimes": "Developer Board",      # Ctrl+Shift+R LM Runtimes (llama.cpp / MLX engines)
    # --- Jan ---
    "assistant": "Person Swap",         # Ctrl+J cycle to the next assistant
}


JAN_SHA = "3d9529df281e4d5d2784cdbae75979bf05929013"
JAN_ICON = f"https://raw.githubusercontent.com/janhq/jan/{JAN_SHA}/src-tauri/icons/icon.png"


def _jan_mark(dest: Path) -> None:
    """Jan's own 512 px app icon, saved as fetched (RGBA). Guarded."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    req = urllib.request.Request(JAN_ICON, headers={"User-Agent": "polykybd"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    Image.open(io.BytesIO(data)).convert("RGBA").save(dest)
    print(f"  {dest.name}  <- janhq/jan@{JAN_SHA[:7]} src-tauri/icons/icon.png (Apache-2.0)")


def _lmstudio_mark(dest: Path) -> None:
    """LM Studio's ESC mark, a finished 72x40 white-on-transparent mask placed
    full-cell (program_icon_region [72, 40]): a rounded box (x 37..69) with five
    2 px bars, 14 px long, whose x offset follows one period of a vertical sine
    of amplitude 4 px. The bars are drawn on the pixel grid so every bar is the
    same thickness; drawing them at 4x and downscaling made some 1 px. 368 lit
    px, legend lost 0 px (tools/esc_mark_preview.py). Guarded."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    import math
    import numpy as np
    from PIL import ImageDraw
    k = 4
    big = Image.new("L", (72 * k, 40 * k), 0)
    ImageDraw.Draw(big).rounded_rectangle([37 * k, 4 * k, 70 * k, 36 * k],
                                          radius=6 * k, outline=255, width=2 * k)
    m = np.asarray(big.resize((72, 40), Image.LANCZOS)) >= 128
    n, amp, length, lw, top, bot, cx = 5, 4, 14, 2, 10, 29, 53.5
    for i in range(n):
        t = i / (n - 1)
        y = round(top + t * (bot - top - lw + 1))
        x0 = round(cx + amp * math.sin(2 * math.pi * t) - length / 2)
        m[y:y + lw, x0:x0 + length] = True
    a = np.where(m, 255, 0).astype("uint8")
    Image.fromarray(np.dstack([a, a, a, a]), "RGBA").save(dest)
    print(f"  {dest.name}  <- drawn ({int(m.sum())} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    _lmstudio_mark(out / "lmstudio.png")
    _jan_mark(out / "jan.png")
    print(f"Wrote {n} icons (+ 2 program marks) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
