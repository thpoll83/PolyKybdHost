#!/usr/bin/env python3
"""Fetch + render the JupyterLab shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The sidebar panel keys are
numbered glyphs from `../number_badge.py`. The ESC mark is the Jupyter logo from
Simple Icons (CC0 artwork; nominative use, see `../brand_marks.py`). The ESC
key shows it redrawn for the 72 x 40 cell, with the word "jupyter", by
`esc_mark` (`esc_jupyter.png`).

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


def esc_mark(dest: Path) -> None:
    """The Jupyter logo for the whole ESC cell (72 x 40 px, 1 bit): the word
    "jupyter" in DejaVu Sans Bold 12 px between the two arcs, and the three
    moons as round dots (4, 3 and 5 px). The arcs are the top and bottom of
    one 38 px circle: each is the circle minus the same circle moved 5 px
    down (top arc) or up (bottom arc), and both stop two rows short of the
    word, which runs across the circle as in the logo. Scaled from the 256 px logo, the
    arcs left loose pixels and the moons came out as uneven blobs, and the
    word could not be read."""
    from PIL import Image, ImageChops, ImageDraw, ImageFont
    w, h = 72, 40

    def disc(box):
        a = Image.new("L", (w, h), 0)
        ImageDraw.Draw(a).ellipse(box, fill=255)
        return a

    cx, cy, r, shift = w / 2 - 0.5, h / 2 - 0.5, 19, 5
    circle = [cx - r, cy - r, cx + r, cy + r]

    def moved(dy):
        return [circle[0], circle[1] + dy, circle[2], circle[3] + dy]

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    left, top, right, bottom = font.getbbox("jupyter")
    word = Image.new("L", (right - left + 4, bottom - top + 4), 0)
    ImageDraw.Draw(word).text((2 - left, 2 - top), "jupyter", fill=255, font=font)
    word = word.point(lambda v: 255 if v > 140 else 0)
    word = word.crop(word.getbbox())
    x, y = (w - word.width) // 2, (h - word.height) // 2
    m = Image.new("L", (w, h), 0)
    m.paste(255, (0, 0), ImageChops.subtract(disc(circle), disc(moved(shift))))    # top arc
    m.paste(255, (0, 0), ImageChops.subtract(disc(circle), disc(moved(-shift))))   # bottom arc
    d = ImageDraw.Draw(m)
    d.rectangle([0, y - 2, w, y + word.height + 1], fill=0)          # arcs out of the text rows
    m.paste(255, (x, y), word)
    d.ellipse([50, 0, 53, 3], fill=255)     # top-right moon
    d.ellipse([17, 4, 19, 6], fill=255)     # top-left moon
    d.ellipse([16, 33, 20, 37], fill=255)   # bottom-left moon
    img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    img.putalpha(m)
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
    guarded(out / "esc_jupyter.png", esc_mark, "the logo with the word, drawn (esc_mark)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
