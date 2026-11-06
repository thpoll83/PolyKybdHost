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
# Rows of the 1072x1090 logo above the "Lazygit" word; the mark is the figure.
LAZYGIT_FIGURE_ROWS = 820


def _lazygit_mark(dest: Path, px: int = 32) -> None:
    """The lazygit figure as a px*px 1-bit trace: cropped to its dark pixels
    above the word, fitted into the square, pixels at luma 128 or darker lit.
    The coloured circles, the cap and the grey quotes are lighter than 128 and
    stay unlit. Drawn at the keycap size so the generator copies it 1:1."""
    import io
    import urllib.request

    import numpy as np

    req = urllib.request.Request(LAZYGIT_LOGO_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    src = white.convert("L")
    dark = np.array(src)[:LAZYGIT_FIGURE_ROWS] <= LAZYGIT_DARK_LUMA
    ys, xs = np.where(dark)
    src = src.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    scale = px / max(src.size)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.LANCZOS)
    square = Image.new("L", (px, px), 255)
    square.paste(fitted, ((px - fitted.width) // 2, (px - fitted.height) // 2))
    a = square.point(lambda v: 255 if v <= LAZYGIT_DARK_LUMA else 0)
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
