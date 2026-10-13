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
  the drawn letter frame the folder uses for ChatGPT and Codex (`../rect_mark.py`).

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

import icon_fetch, rect_mark  # noqa: E402
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

LETTERS = {"lmstudio.png": "LM"}

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


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    for fname, letters in LETTERS.items():
        rect_mark.ensure(out / fname, letters)
    _jan_mark(out / "jan.png")
    print(f"Wrote {n} icons (+ {len(LETTERS) + 1} program marks) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
