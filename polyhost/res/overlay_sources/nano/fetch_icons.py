#!/usr/bin/env python3
"""Fetch + draw the GNU nano shortcut icons (reproducible).

Three sources:

* Microsoft Fluent UI System Icons (MIT), with Material Symbols (Apache-2.0)
  for the `ms:` entries: commands that have a usual picture (insert file,
  comment, justify, record and play a macro, the toggles).
* DRAWN composites, 40x32 and 1-bit at keycap size: a glyph above a word of up
  to four letters. They are the GNU Emacs set's composites
  (`../emacs/fetch_icons.py`, `composite()`), so the two editors draw a motion
  or a deletion the same way: arrow = move, Delete-key shape = delete,
  magnifier with an arrow = search, I-beam with a flag = mark. A `png:` glyph
  is one of the fetched icons below, drawn small above the word.
* The ESC mark: the word "nano" in reverse video, as nano shows its name in
  the title bar, above "GNU", set in JetBrains Mono ExtraBold (SIL OFL 1.1,
  pinned commit of google/fonts). Simple Icons has no nano mark (its "Nano"
  is a currency) and its GNU head is CC BY-SA 2.0 and names GNU, not nano.

Drawn icons and the mark are guarded: a committed file is left as-is, so a
hand edit survives a re-run.

    pip install cairosvg
    python polyhost/res/overlay_sources/nano/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.emacs import fetch_icons as emacs  # noqa: E402

FLUENT = {
    "exit": "Arrow Exit",
    "insertfile": "Document Add",
    "location": "Location",
    "execute": "Window Console",
    "justify": "ms:format_align_justify",
    "recenter": "ms:vertical_align_center",
    "indent": "Text Indent Increase",
    "unindent": "Text Indent Decrease",
    "macro_record": "Record",
    "macro_run": "Play",
    "anchor": "ms:anchor",
    "comment": "Comment",
    "verbatim": "ms:format_quote",
    "wordcount": "Text Word Count",
    "spell": "Text Proofing Tools",
    # toggles
    "hide_ui": "ms:visibility_off",
    "helplines": "ms:call_to_action",
    "linenumbers": "ms:format_list_numbered",
    "whitespace": "ms:format_paragraph",
    "syntax": "ms:palette",
    "mouse": "ms:mouse",
    # top glyphs for composites only (not bound directly)
    "_cut": "Cut",
    "_wrap": "ms:wrap_text",
    "_tab": "ms:keyboard_tab",
    "_indent": "ms:format_indent_increase",
    "_home": "ms:home",
    "_complete": "ms:auto_fix_high",
}

# file stem -> (glyph, word); glyphs as in `emacs.composite`. A word is at most
# four capitals so it reads at 12 px.
COMPOSITES = {
    # motion
    "char_back_del": ("killleft", "CHR"), "char_del": ("killright", "CHR"),
    "word_fwd": ("right", "WORD"), "word_back": ("left", "WORD"),
    "line_next": ("down", "LINE"), "line_prev": ("up", "LINE"),
    "line_start": ("barleft", "LINE"), "line_end": ("barright", "LINE"),
    "page_down": ("down", "PAGE"), "page_up": ("up", "PAGE"),
    "block_next": ("down", "BLK"), "block_prev": ("up", "BLK"),
    "para_start": ("up", "PARA"), "para_end": ("down", "PARA"),
    "file_start": ("top", "FILE"), "file_end": ("bottom", "FILE"),
    "row_top": ("top", "ROW"), "row_bottom": ("bottom", "ROW"),
    "scroll_up": ("up", "SCRL"), "scroll_down": ("down", "SCRL"),
    "scroll_left": ("left", "SCRL"), "scroll_right": ("right", "SCRL"),
    "buf_prev": ("left", "BUF"), "buf_next": ("right", "BUF"),
    "anchor_prev": ("png:anchor", "PREV"), "anchor_next": ("png:anchor", "NEXT"),
    "goto_line": ("text:#", "GOTO"),
    "bracket": ("text:[ ]", "PAIR"),
    "cycle": ("png:recenter", "CYCL"),
    # deleting and cutting
    "word_del": ("killright", "WORD"), "word_back_del": ("killleft", "WORD"),
    "zap": ("killright", "ZAP"),
    "cut_eof": ("png:_cut", "EOF"),
    # search
    "search_fwd": ("search", ""), "search_back": ("searchback", ""),
    "find_next": ("search", "NEXT"), "find_prev": ("searchback", "PREV"),
    # marking, completion, justify
    "mark": ("caret", "MARK"),
    "complete": ("png:_complete", "WORD"),
    "justify_all": ("png:justify", "ALL"),
    # toggles
    "cursorpos": ("png:location", "SHOW"),
    "softwrap": ("png:_wrap", "SOFT"),
    "hardwrap": ("png:_wrap", "HARD"),
    "tabs_spaces": ("png:_tab", "SPC"),
    "autoindent": ("png:_indent", "AUTO"),
    "smarthome": ("png:_home", "SMRT"),
    "cut_from_cursor": ("png:_cut", "CURS"),
}

# --------------------------------------------------------------- ESC mark

# JetBrains Mono (SIL OFL 1.1), its ExtraBold instance, at a pinned commit.
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf")
MARK_W, MARK_H = 40, 40
MARK_SS = 8
BAR_H = 17          # the reverse-video bar at the bottom of the mark
MARK_THRESHOLD = 110


def _mark_font(px: int):
    from PIL import ImageFont
    f = ImageFont.truetype(str(cnc._font(FONT_URL)), px)
    f.set_variation_by_name("ExtraBold")
    return f


def _fit(text: str, max_w: int, max_cap: int):
    """The font size (at MARK_SS) whose capital height is at most `max_cap`
    px and whose `text` is at most `max_w` px wide."""
    ss = MARK_SS
    ref = _mark_font(200).getbbox("H")
    for cap in range(max_cap, 4, -1):
        px = round(200 * cap * ss / (ref[3] - ref[1]))
        f = _mark_font(px)
        b = f.getbbox(text)
        if b[2] - b[0] <= max_w * ss:
            return f, b
    raise ValueError(text)


def program(out: Path) -> None:
    """nano.png: "GNU" above "nano" knocked out of a lit bar, 40x40."""
    dest = out / "nano.png"
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    import numpy as np
    from PIL import Image, ImageDraw
    w, h, ss = MARK_W, MARK_H, MARK_SS

    def draw(text, font, box, top, height):
        im = Image.new("L", (w * ss, h * ss), 0)
        x = (w * ss - (box[2] - box[0])) // 2 - box[0]
        y = top * ss + (height * ss - (box[3] - box[1])) // 2 - box[1]
        ImageDraw.Draw(im).text((x, y), text, font=font, fill=255)
        return np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD

    canvas = np.zeros((h, w), bool)
    # "GNU" in the free space above the bar.
    f, b = _fit("GNU", w - 8, 11)
    canvas |= draw("GNU", f, b, 2, h - BAR_H - 6)
    # The bar, with "nano" knocked out of it.
    bar = np.zeros((h, w), bool)
    bar[h - BAR_H:, :] = True
    f, b = _fit("nano", w - 4, 9)
    canvas |= bar & ~draw("nano", f, b, h - BAR_H, BAR_H)
    cnc._save_mask(canvas, dest)
    print(f"  {dest.name}  <- drawn: GNU / nano (JetBrains Mono ExtraBold)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    for stem, (glyph, word) in COMPOSITES.items():
        emacs.composite(out / f"{stem}.png", glyph, word, out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
