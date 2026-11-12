#!/usr/bin/env python3
"""Fetch + render the GitKraken Desktop shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The git actions that GitHub
Desktop also has (commit, fetch, new branch, clone, ...) are copied from
`../githubdesktop/icons`, so both apps draw the same picture for the same action.
`tab1..tab9.png` are Fluent `Tab` with a digit from `../number_badge.py`;
`fav1..fav9.png` are Fluent `Star`, filled, with the digit cut out. The ESC mark is the GitKraken
logo from Simple Icons (CC0 artwork; nominative use, see `../brand_marks.py`).

    pip install cairosvg
    PYTHONPATH=. python polyhost/res/overlay_sources/gitkraken/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402
import number_badge  # noqa: E402

FLUENT = {
    "shortcuts": "Keyboard",
    "stage": "Add Square",
    "unstage": "Subtract Square",
    "stageall": "Add Square Multiple",
    "unstageall": "Subtract Square Multiple",
    "stagecommit": "ms:done_all",
    "firstcommit": "ms:vertical_align_top",
    "lastcommit": "ms:vertical_align_bottom",
    "palette": "ms:keyboard_command_key",
    "searchcommits": "ms:manage_search",
    "openpalette": "Folder Search",
    "blame": "Document Search",
    "terminal": "Window Console",
    "terminalpanel": "ms:terminal",
    "filemanager": "Folder Open",
    "difftool": "ms:difference",
    "closetab": "Dismiss",
    "leftpanel": "Panel Left",
    "detailpanel": "Panel Right",
    "newtab": "Tab Add",
    "nexttab": "ms:keyboard_tab",
    "prevtab": "ms:keyboard_tab_rtl",
    "reopentab": "ms:tab_recent",
    "tabslist": "ms:view_list",
    "init": "ms:create_new_folder",
    "openrepo": "ms:folder_open",
    "repomanagement": "ms:library_books",
    "_tabbase": "Tab",
    "_starbase": "Star",
}

# Same action as in GitHub Desktop: copy that set's drawing byte for byte.
BORROW = {name: "githubdesktop" for name in (
    "commit.png", "fetch.png", "newbranch.png", "clone.png", "summary.png",
    "filter.png", "fullscreen.png", "resetzoom.png", "editor.png", "devtools.png",
)}


def _star_digits(base: Path, out_dir: Path, digits: str = "123456789") -> None:
    """`fav<d>.png`: the star outline in `base` filled solid, with the digit cut
    out (transparent), so the digit reads as unlit inside a lit star."""
    from collections import deque

    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    star = Image.open(base).convert("RGBA")
    px = star.width
    stroke = np.array(star.getchannel("A")) > 128
    # Everything not reachable from the corner without crossing the stroke is
    # the star: stroke plus interior.
    outside = np.zeros_like(stroke)
    outside[0, 0] = True
    queue = deque([(0, 0)])
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if (0 <= ny < px and 0 <= nx < px and not outside[ny, nx]
                    and not stroke[ny, nx]):
                outside[ny, nx] = True
                queue.append((ny, nx))
    filled = Image.fromarray((~outside * 255).astype("uint8"))
    font = ImageFont.truetype(number_badge.BOLD, int(px * 0.40))
    for d in digits:
        cut = Image.new("L", (px, px), 0)
        ImageDraw.Draw(cut).text((px * 0.5, px * 0.56), d, fill=255, font=font,
                                 anchor="mm")
        alpha = Image.fromarray(
            (np.array(filled) & ~np.array(cut)).astype("uint8"))
        black = Image.new("L", (px, px), 0)
        Image.merge("RGBA", (black, black, black, alpha)).save(out_dir / f"fav{d}.png")
    print(f"  fav{digits[0]}..fav{digits[-1]}.png  <- {base.stem} filled, digit cut out")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.borrow(BORROW, out)
    # Digit centre 3/96 above the helper's default: 1 px higher on the keycap.
    number_badge.numbered(out / "_tabbase.png", "123456789", out, "tab",
                          centre=(0.50, 0.53))
    _star_digits(out / "_starbase.png", out)
    brand_marks.ensure(out / "gitkraken.png", "gitkraken")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
