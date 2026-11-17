#!/usr/bin/env python3
"""Fetch + render the JupyterLab shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The sidebar panel keys are
numbered glyphs from `../number_badge.py`. The ESC mark is the Jupyter logo from
Simple Icons (CC0 artwork; nominative use, see `../brand_marks.py`), redrawn
as a clean 1-bit 32 px bitmap by `clean_mark` (`jupyter_mark.png`).

    pip install cairosvg
    python polyhost/res/overlay_sources/jupyter/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch, number_badge  # noqa: E402
from polyhost.res.overlay_sources.dcc_glyphs import guarded, with_badge  # noqa: E402

FLUENT = {
    "run": "Play",
    "runinsert": "ms:playlist_add",
    "cmdmode": "ms:edit_off",
    "splitcell": "Split Horizontal",
    "mergebelow": "ms:vertical_align_bottom",
    "mergeabove": "ms:vertical_align_top",
    "moveup": "ms:move_up",
    "movedown": "ms:move_down",
    "collapseall": "ms:unfold_less_double",
    "expandall": "ms:unfold_more_double",
    "histprev": "ms:history",
    "histnext": "ms:update",
    "comment": "ms:code_off",
    "blockcomment": "ms:code_blocks",
    "deleteline": "Delete Lines",
    "selectnext": "ms:text_select_move_forward_word",
    "saveas": "Save Copy",
    "findnext": "Chevron Down",
    "findprev": "Chevron Up",
    "findsel": "ms:frame_inspect",
    "palette": "Apps List Detail",
    "shortcuts": "Keyboard",
    "leftarea": "Panel Left",
    "rightarea": "Panel Right",
    "filebrowser": "Folder Open",
    "toc": "ms:toc",
    "running": "ms:memory",
    "launcher": "Rocket",
    "extensions": "Puzzle Piece",
    "debugger": "Bug",
    "propinsp": "Wrench",
    "inspector": "Question Circle",
    "settings": "Settings",
    "nexttab": "ms:keyboard_tab",
    "prevtab": "ms:keyboard_tab_rtl",
    "nexttabbar": "ms:switch_right",
    "prevtabbar": "ms:switch_left",
    "lasttab": "ms:swap_horiz",
    "closetab": "Dismiss",
    "continue": "ms:resume",
    "terminate": "ms:stop_circle",
    "stepover": "ms:step_over",
    "stepout": "ms:step_out",
    # notebook command mode
    "insertabove": "ms:add_row_above",
    "insertbelow": "ms:add_row_below",
    "cutcell": "Cut",
    "copycell": "Copy",
    "pastecell": "Clipboard Paste",
    "undocell": "Arrow Undo",
    "redocell": "Arrow Redo",
    "tocode": "Code",
    "tomarkdown": "ms:markdown",
    "toraw": "ms:raw_on",
    "mergecells": "ms:call_merge",
    "cellbelow": "Arrow Down",
    "cellabove": "Arrow Up",
    "extendbelow": "ms:keyboard_double_arrow_down",
    "extendabove": "ms:keyboard_double_arrow_up",
    "linenumbers": "ms:format_list_numbered",
    "sidebyside": "Split Vertical",
    "_heading": "ms:title",
    "_arrowup": "ms:arrow_upward_alt",
    "_arrowdown": "ms:arrow_downward_alt",
    "_lbase": "Panel Left",
    "_rbase": "Panel Right",
}


def clean_mark(src: Path, dest: Path) -> None:
    """The Jupyter logo as a 1-bit bitmap of 32 x 32 px, the height it gets on
    the ESC key, stored 8x with hard pixel edges. Scaled straight from the
    256 px logo, the arc ends left loose pixels and the three moons came out
    as uneven blobs. So: the right half of each arc is taken from the scaled
    logo and mirrored (the logo is symmetric), pixels with at most one
    neighbour are removed, and the moons are drawn as round dots at their
    places (4, 3 and 5 px)."""
    from PIL import Image, ImageDraw
    w = h = 32
    a = Image.open(src).convert("RGBA").split()[3].resize((w, h), Image.LANCZOS)
    a = a.point(lambda v: 255 if v >= 96 else 0)
    m = Image.new("L", (w, h), 0)
    for y in list(range(3, 10)) + list(range(20, 28)):   # upper arc, lower arc
        for x in range(w // 2, w):
            if y <= 3 and x >= 23:                        # the top-right moon
                continue
            if a.getpixel((x, y)):
                m.putpixel((x, y), 255)
                m.putpixel((w - 1 - x, y), 255)

    def on(img, x, y):
        return 0 <= x < w and 0 <= y < h and img.getpixel((x, y)) > 0

    for _ in range(2):
        c = m.copy()
        for y in range(h):
            for x in range(w):
                if on(m, x, y) and sum(on(m, x + dx, y + dy) for dx in (-1, 0, 1)
                                       for dy in (-1, 0, 1) if dx or dy) <= 1:
                    c.putpixel((x, y), 0)
        m = c
    d = ImageDraw.Draw(m)
    d.ellipse([24, 0, 27, 3], fill=255)    # top-right moon
    d.ellipse([3, 3, 5, 5], fill=255)      # top-left moon
    d.ellipse([4, 27, 8, 31], fill=255)    # bottom-left moon
    big = m.resize((w * 8, h * 8), Image.NEAREST)
    img = Image.new("RGBA", big.size, (255, 255, 255, 0))
    img.putalpha(big)
    img.save(dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    number_badge.numbered(out / "_lbase.png", "123456789", out, "left",
                          size=0.40, centre=(0.62, 0.50))
    number_badge.numbered(out / "_rbase.png", "123456789", out, "right",
                          size=0.40, centre=(0.38, 0.50))
    number_badge.numbered(out / "_heading.png", "123456", out, "heading",
                          size=0.40, centre=(0.78, 0.72))
    # Insert heading above / below: the heading glyph with an up or down arrow
    # badge, so they differ from Merge with cell above (vertical_align_top).
    for name, arrow in (("headingabove", "_arrowup"), ("headingbelow", "_arrowdown")):
        guarded(out / f"{name}.png",
                lambda p, a=arrow: with_badge(out / "_heading.png", out / f"{a}.png", p),
                f"_heading + {arrow} badge (dcc_glyphs.with_badge)")
    # Run and select next: the run glyph with a down arrow badge, so it differs
    # from J (select the cell below, a plain down arrow).
    guarded(out / "runnext.png",
            lambda p: with_badge(out / "run.png", out / "_arrowdown.png", p),
            "run + _arrowdown badge (dcc_glyphs.with_badge)")
    brand_marks.ensure(out / "jupyter.png", "jupyter")
    guarded(out / "jupyter_mark.png", lambda p: clean_mark(out / "jupyter.png", p),
            "jupyter.png as a clean 32 px bitmap (clean_mark)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
