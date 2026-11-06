#!/usr/bin/env python3
"""Fetch + render the lazygit shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The git actions that GitHub
Desktop or GitKraken also have (commit, push, pull, fetch, stash, branch list,
history, stage, ...) are copied from `../githubdesktop/icons` and
`../gitkraken/icons`, so the three git clients draw the same picture for the
same action.

Three commit variants are drawn here: the GitHub Desktop commit glyph with a
small badge in the lower right corner (prohibited sign = without the
pre-commit hook, pencil = amend the last commit, code brackets = write the
message in the git editor).

The ESC mark is the lazygit logo from the README of the lazygit repository,
reduced to a 32x32 1-bit trace, dark pixels lit. See SOURCES.md.

Drawn icons and the mark are guarded: a committed file is left as-is, so a
hand edit survives a re-run. Delete the PNG to redraw it.

    pip install cairosvg Pillow numpy
    PYTHONPATH=. python polyhost/res/overlay_sources/lazygit/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

FLUENT = {
    # --- Files panel ---
    "edit": "Edit",
    "ignore": "Eye Off",
    "refreshfiles": "Document Sync",
    "discardfile": "Delete",
    "resetoptions": "Arrow Reset",
    "upstreamreset": "ms:cloud_sync",
    "stashoptions": "Archive Settings",
    "treeview": "Text Bullet List Tree",
    "collapseall": "ms:unfold_less",
    "expandall": "ms:unfold_more",
    "mainview": "Panel Right",
    "statusfilter": "ms:filter_alt",
    "filteroptions": "ms:tune",
    "copypath": "Clipboard Link",
    # --- panels ---
    "status": "Info",
    "files": "Document Multiple",
    # --- global ---
    "quitkeepdir": "Power",
    "refresh": "Arrow Clockwise",
    "suspend": "Pause",
    "screenprev": "Full Screen Minimize",
    "patch": "ms:healing",
    "jumptofile": "ms:find_in_page",
    "whitespace": "ms:space_bar",
    "commandlog": "ms:receipt_long",
    "editconfig": "Document Settings",
    "contextmore": "ms:expand",
    "contextless": "ms:compress",
    "fixupbase": "ms:manage_search",
    # --- navigation ---
    "itemprev": "ms:keyboard_arrow_up",
    "itemnext": "ms:keyboard_arrow_down",
    "pageprev": "ms:keyboard_double_arrow_up",
    "pagenext": "ms:keyboard_double_arrow_down",
    "panelprev": "ms:arrow_back",
    "panelnext": "ms:arrow_forward",
    "scrollup": "ms:swipe_up",
    "scrolldown": "ms:swipe_down",
    "scrollleft": "ms:swipe_left",
    "scrollright": "ms:swipe_right",
    "rangeselect": "ms:select",
    "scrolltop": "ms:align_vertical_top",
    "scrollbottom": "ms:align_vertical_bottom",
    # badges for the commit composites only (not bound directly)
    "_nohook": "Prohibited",
}

# Same action as in GitHub Desktop or GitKraken: copy that set's drawing byte
# for byte.
BORROW = {
    **{name: "githubdesktop" for name in (
        "commit.png", "push.png", "pull.png", "fetch.png", "stash.png",
        "stashall.png", "branches.png", "history.png", "filter.png",
        "repolist.png", "shell.png", "openwith.png", "fullscreen.png",
        "compare.png", "merge.png", "rebase.png", "editor.png",
    )},
    **{name: "gitkraken" for name in (
        "stage.png", "stageall.png", "shortcuts.png", "difftool.png",
        "prevtab.png", "nexttab.png",
    )},
}

# file -> badge drawn in the lower right corner of the commit glyph
COMMIT_BADGES = {
    "commitnohook.png": "_nohook.png",
    "amend.png": "edit.png",
    "commiteditor.png": "editor.png",
}


def _commit_badge(dest: Path, commit: Path, badge: Path) -> None:
    """The commit glyph, shrunk to the upper left, with `badge` in the lower
    right corner and a transparent ring around the badge so the two shapes do
    not touch at 1 bit."""
    import numpy as np
    from PIL import ImageFilter

    px = 96
    base = Image.open(commit).convert("RGBA").resize((72, 72), Image.LANCZOS)
    mark = Image.open(badge).convert("RGBA").resize((50, 50), Image.LANCZOS)
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    img.alpha_composite(base, (0, 0))
    pos = (px - mark.width, px - mark.height)
    ring = Image.new("L", (px, px), 0)
    ring.paste(mark.getchannel("A"), pos)
    ring = ring.filter(ImageFilter.MaxFilter(13))
    alpha = np.array(img.getchannel("A")).astype(int)
    alpha[np.array(ring) > 0] = 0
    img.putalpha(Image.fromarray(alpha.astype("uint8")))
    img.alpha_composite(mark, pos)
    img.save(dest)


# The logo shown at the top of README.md in jesseduffield/lazygit (the
# reclining git graph with a nightcap, above the word "Lazygit"). It is an image
# uploaded to the repository's README, not a file in the repository tree.
LAZYGIT_LOGO_URL = ("https://user-images.githubusercontent.com/8456633/"
                    "174470852-339b5011-5800-4bb9-a628-ff230aa8cd4e.png")
LAZYGIT_DARK_LUMA = 128


# The 6-row micro font for the word under the figure: row 0 ascender, rows 1-4
# x-height, row 5 descender. "#" is lit.
_MICRO_FONT = {
    "l": ["#.", "#.", "#.", "#.", "##", ".."],
    "a": ["...", ".##", "#.#", "#.#", ".##", "..."],
    "z": ["...", "###", "..#", ".#.", "###", "..."],
    "y": ["...", "#.#", "#.#", ".##", "..#", "##."],
    "g": ["...", ".##", "#.#", ".##", "..#", "##."],
    "i": ["#", ".", "#", "#", "#", "."],
    "t": ["#.", "##", "#.", "#.", ".#", ".."],
}
# The figure (with the cap and the moon) occupies rows 85..800 of the logo.
LAZYGIT_FIGURE_BOX = (0, 85, 1072, 800)
LAZYGIT_FIGURE_HEIGHT = 22   # rows of the 32x32 mark for the figure
LAZYGIT_COLOUR_COVER = 0.3   # cap/moon pixels at least this covered get the checker


def _micro_text(word: str):
    import numpy as np
    cols = []
    for i, ch in enumerate(word):
        glyph = _MICRO_FONT[ch]
        if i:
            cols.append(np.zeros(6, bool))
        for x in range(len(glyph[0])):
            cols.append(np.array([glyph[y][x] == "#" for y in range(6)]))
    return np.stack(cols, 1)


def _lazygit_mark(dest: Path, px: int = 32) -> None:
    """The lazygit figure as a px*px 1-bit mark with the word under it.

    The figure (the dark graph, luma 128 or darker) is lit where a pixel is at
    least 45% covered. The green cap and the blue moon are lit on a
    checkerboard where a pixel is at least 30% covered, so they read as a
    second shade. Under the figure, one blank row, then "lazygit" in a 6-row
    micro font. Drawn at the keycap size so the generator copies it 1:1."""
    import io
    import urllib.request

    import numpy as np

    req = urllib.request.Request(LAZYGIT_LOGO_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    rgb = np.array(white.convert("RGB")).astype(int)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    sat = rgb.max(-1) - rgb.min(-1)
    dark = np.array(white.convert("L")) <= LAZYGIT_DARK_LUMA
    cap = (g > r + 40) & (g > b) & (sat > 60)
    moon = (b > r + 30) & (b >= g) & (sat > 40) & (r > 100)
    size = (px, LAZYGIT_FIGURE_HEIGHT)

    def cover(mask):
        img = Image.fromarray((mask * 255).astype("uint8")).crop(LAZYGIT_FIGURE_BOX)
        return np.array(img.resize(size, Image.BOX)) / 255.0

    yy, xx = np.mgrid[0:LAZYGIT_FIGURE_HEIGHT, 0:px]
    figure = cover(dark) >= 0.45
    for mask in (cap, moon):
        figure |= (cover(mask) >= LAZYGIT_COLOUR_COVER) & ((xx + yy) % 2 == 0)
    word = _micro_text("lazygit")
    out = np.zeros((px, px), bool)
    top = (px - (LAZYGIT_FIGURE_HEIGHT + 1 + word.shape[0])) // 2
    out[top:top + LAZYGIT_FIGURE_HEIGHT] = figure
    x0 = (px - word.shape[1]) // 2
    y0 = top + LAZYGIT_FIGURE_HEIGHT + 1
    out[y0:y0 + word.shape[0], x0:x0 + word.shape[1]] = word
    a = Image.fromarray((out * 255).astype("uint8"))
    Image.merge("RGBA", (a, a, a, a)).save(dest)


def _guarded(path: Path, draw) -> None:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        draw(path)
        print(f"  {path.name}  <- drawn in lazygit/fetch_icons.py")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.borrow(BORROW, out)
    for name, badge in COMMIT_BADGES.items():
        _guarded(out / name, lambda p, b=badge: _commit_badge(p, out / "commit.png", out / b))
    _guarded(out / "lazygit.png", _lazygit_mark)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
