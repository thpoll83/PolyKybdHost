#!/usr/bin/env python3
"""Fetch + draw the Vim mode overlay icons (reproducible).

Every icon is a 40x40 1-bit image, white on transparent, bound with
`region: [40, 40]`, `margin: 0`, `mode: alpha`, so the generator places it 1:1
at the right of the keycap and the firmware legend stays at the left.

Three sources:

* Microsoft Fluent UI System Icons (MIT) and Material Symbols (Apache-2.0)
  for the actions that have a common picture (copy, paste, undo, tag, ...).
  `FLUENT` names them; the 96 px renders are kept in `icons/src/`.
* Drawn glyphs for what no icon set draws: Vim's motions, the insert and
  visual families, and the "arrow + word" composites (`DRAWN` below). They
  follow a small set of rules, so one family reads the same everywhere:
  a horizontal arrow over a word is a motion along the line (w b e), a
  vertical arrow beside a word moves the cursor up or down ({ } - +), the
  same arrow inside a frame scrolls the window (CTRL-F CTRL-D CTRL-E), and
  "again" under a picture repeats something (; , . &).
* The ESC mark is Vim's own logo, `runtime/vimlogo.svg` from vim/vim (Vim
  license, see VIM_LICENSE.txt and SOURCES.md).

    pip install cairosvg
    python polyhost/res/overlay_sources/vim/fetch_icons.py            # missing files only
    python polyhost/res/overlay_sources/vim/fetch_icons.py --redraw   # redraw every drawn glyph

Without `--redraw` a committed icon is left as it is, so a hand edit survives.
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "icons"
SRC = OUT / "src"

S = 40                       # canvas: 40x40, 1 bit
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
VIM_LOGO_URL = ("https://raw.githubusercontent.com/vim/vim/"
                "master/runtime/vimlogo.svg")

# file stem in icons/src -> Fluent folder name or "ms:<material name>"
FLUENT = {
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "eraser": "Eraser",
    "edit": "Edit",
    "info": "Info",
    "tag": "Tag",
    "bookmark": "Bookmark",
    "bookmark_add": "Bookmark Add",
    "filter": "Filter",
    "play": "Play",
    "record": "Record",
    "book_q": "Book Question Mark",
    "split": "Split Vertical",
    "pause": "Pause",
    "indent_inc": "Text Indent Increase",
    "indent_dec": "Text Indent Decrease",
    "align_left": "Text Align Left",
    "clip_letter": "Clipboard Letter",
    "help": "Question Circle",
    "top": "ms:vertical_align_top",
    "bottom": "ms:vertical_align_bottom",
    "swap": "Arrow Swap",
    "history": "History",
    "list": "Text Bullet List",
    "backspace": "ms:backspace",
    "window": "Window",
    "sync": "Arrow Sync",
}

# Fluent / Material glyphs used as they are: icons/<stem>.png is the src
# render scaled to 34 px, 1-bit, at the right of the 40x40 canvas.
PLAIN = ("copy", "paste", "undo", "redo", "info", "bookmark_add", "filter",
         "play", "record", "book_q", "split", "pause", "indent_inc",
         "indent_dec", "align_left", "clip_letter", "help", "sync", "list",
         "window")


# --------------------------------------------------------------------------- #
# primitives (all draw lit = 255 on an "L" canvas, no anti-aliasing)
# --------------------------------------------------------------------------- #
def canvas():
    img = Image.new("L", (S, S), 0)
    return img, ImageDraw.Draw(img)


def _font(px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BOLD, px)


def text(img, s: str, cx: float, cy: float, px: int = 12, max_w: int = S) -> None:
    """Draw `s` centred on (cx, cy), shrinking the size until it fits max_w.
    Rendered in grey, then thresholded, so the strokes stay solid."""
    while px > 7 and _font(px).getbbox(s)[2] - _font(px).getbbox(s)[0] > max_w:
        px -= 1
    layer = Image.new("L", img.size, 0)
    ImageDraw.Draw(layer).text((cx, cy), s, fill=255, font=_font(px), anchor="mm")
    img.paste(255, (0, 0), layer.point(lambda v: 255 if v >= 110 else 0))


def harrow(d, x0, x1, y, t=3, head=5) -> None:
    """Horizontal arrow from x0 to x1 (tip at x1)."""
    sgn = 1 if x1 > x0 else -1
    base = x1 - sgn * head
    d.rectangle([min(x0, base), y - t // 2, max(x0, base), y - t // 2 + t - 1], fill=255)
    d.polygon([(x1, y), (base, y - head), (base, y + head)], fill=255)


def varrow(d, y0, y1, x, t=3, head=5) -> None:
    """Vertical arrow from y0 to y1 (tip at y1)."""
    sgn = 1 if y1 > y0 else -1
    base = y1 - sgn * head
    d.rectangle([x - t // 2, min(y0, base), x - t // 2 + t - 1, max(y0, base)], fill=255)
    d.polygon([(x, y1), (x - head, base), (x + head, base)], fill=255)


def box(d, x0, y0, x1, y1, w=2) -> None:
    d.rectangle([x0, y0, x1, y1], outline=255, width=w)


def bar(d, x0, x1, y, h=3) -> None:
    """One row of text."""
    d.rectangle([x0, y, x1, y + h - 1], fill=255)


def caret(d, x, y0, y1) -> None:
    """An I-beam text cursor."""
    d.rectangle([x, y0, x + 1, y1], fill=255)
    d.rectangle([x - 2, y0, x + 3, y0 + 1], fill=255)
    d.rectangle([x - 2, y1 - 1, x + 3, y1], fill=255)


def magnifier(d, cx, cy, r=6) -> None:
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=255, width=2)
    for i in range(5):
        d.rectangle([cx + r - 1 + i, cy + r - 1 + i, cx + r + i, cy + r + i], fill=255)


def charbox(img, d, x0, y0, w=13, h=15, ch="x") -> None:
    box(d, x0, y0, x0 + w - 1, y0 + h - 1)
    text(img, ch, x0 + w / 2, y0 + h / 2 - 1, px=11)


def frame(d, x0, y0, x1, y1) -> None:
    """A window / screen."""
    box(d, x0, y0, x1, y1)


def wall(d, x, y0, y1, t=2) -> None:
    d.rectangle([x, y0, x + t - 1, y1], fill=255)


def lines(d, x0, x1, y0, n=3, gap=5) -> None:
    for i in range(n):
        bar(d, x0, x1, y0 + i * gap)


def paste_icon(img, stem: str, px: int, x: int, y: int, mirror=False) -> None:
    """A Fluent / Material glyph from icons/src, scaled to px, 1-bit."""
    src = Image.open(SRC / f"{stem}.png").convert("RGBA").split()[3]
    if mirror:
        src = ImageOps.mirror(src)
    small = src.resize((px, px), Image.LANCZOS).point(lambda v: 255 if v >= 100 else 0)
    img.paste(255, (x, y), small)


def keycap_esc(img, d) -> None:
    """A key outline with "Esc": "the same as pressing Esc"."""
    d.rounded_rectangle([3, 9, 36, 30], radius=4, outline=255, width=2)
    text(img, "Esc", 20, 19, px=12, max_w=28)


# --------------------------------------------------------------------------- #
# families
# --------------------------------------------------------------------------- #
def h_word(word, left=False):
    """A horizontal motion: arrow over a word (w b e W B E, CTRL-O ...)."""
    def f(img, d):
        if left:
            harrow(d, 36, 3, 9, t=4, head=7)
        else:
            harrow(d, 3, 36, 9, t=4, head=7)
        text(img, word, 20, 29, px=13, max_w=39)
    return f


def v_word(word, up=False):
    """A vertical cursor motion: arrow beside a word ({ } - +)."""
    def f(img, d):
        if up:
            varrow(d, 36, 3, 6, t=4, head=6)
        else:
            varrow(d, 3, 36, 6, t=4, head=6)
        text(img, word, 26, 20, px=12, max_w=26)
    return f


def scroll(word, up=False):
    """A window scroll: the arrow inside a frame (CTRL-F/B/D/U/E/Y)."""
    def f(img, d):
        frame(d, 0, 1, 14, 38)
        if up:
            varrow(d, 33, 6, 7, t=2, head=5)
        else:
            varrow(d, 6, 33, 7, t=2, head=5)
        text(img, word, 27, 20, px=12, max_w=24)
    return f


def again(top):
    """Repeat something: a picture or a word over "again"."""
    def f(img, d):
        if callable(top):
            top(img, d)
        else:
            text(img, top, 20, 9, px=13, max_w=38)
        text(img, "again", 20, 30, px=12, max_w=38)
    return f


def icon_over(stem, suffix=None, word=None, px=24, mirror=False):
    """A Fluent glyph with a small suffix below: "eol" (to the end of the
    line, the arrow of `$`), "line" (the whole line), "char" (one character),
    or a word."""
    def f(img, d):
        if suffix is None and word is None:
            paste_icon(img, stem, 34, 3, 3, mirror)
            return
        paste_icon(img, stem, px, (S - px) // 2, 0, mirror)
        y = px + 3
        if suffix == "eol":
            harrow(d, 6, 31, y + 6, t=3, head=5)
            wall(d, 33, y + 1, y + 11)
        elif suffix == "line":
            bar(d, 4, 35, y + 1, h=3)
            bar(d, 4, 35, y + 7, h=3)
        elif suffix == "char":
            box(d, 14, y, 25, S - 1)
        elif suffix in ("right", "left"):
            if suffix == "right":
                harrow(d, 8, 32, y + 6, t=3, head=5)
            else:
                harrow(d, 32, 8, y + 6, t=3, head=5)
        if word:
            text(img, word, 20, y + 6, px=12, max_w=38)
    return f


# --------------------------------------------------------------------------- #
# individual glyphs
# --------------------------------------------------------------------------- #
def arrow(direction):
    def f(img, d):
        if direction == "left":
            harrow(d, 36, 3, 20, t=5, head=10)
        elif direction == "right":
            harrow(d, 3, 36, 20, t=5, head=10)
        elif direction == "up":
            varrow(d, 37, 2, 20, t=5, head=10)
        else:
            varrow(d, 2, 37, 20, t=5, head=10)
    return f


def line_start(img, d):          # 0, <Home>, c_CTRL-B
    wall(d, 1, 4, 35)
    harrow(d, 37, 5, 12, t=4, head=7)
    bar(d, 5, 37, 26)
    bar(d, 5, 28, 32)


def first_char(img, d):          # ^
    bar(d, 14, 37, 26)
    bar(d, 14, 30, 32)
    wall(d, 11, 4, 35)
    harrow(d, 37, 15, 12, t=4, head=7)
    for x in range(1, 9, 3):     # the indent
        d.rectangle([x, 27, x, 27], fill=255)


def line_end(img, d):            # $, <End>, c_CTRL-E
    wall(d, 37, 4, 35)
    harrow(d, 2, 34, 12, t=4, head=7)
    bar(d, 2, 34, 26)
    bar(d, 2, 22, 32)


def column(img, d):              # |
    for y in range(2, 38, 4):
        d.rectangle([27, y, 28, y + 1], fill=255)
    harrow(d, 2, 25, 12, t=4, head=7)
    text(img, "col", 13, 30, px=12, max_w=24)


def screen_pos(where):           # H M L
    def f(img, d):
        frame(d, 13, 1, 39, 38)
        y = {"top": 6, "mid": 18, "bot": 30}[where]
        d.rectangle([17, y, 35, y + 3], fill=255)
        d.polygon([(10, y + 1), (2, y - 5), (2, y + 7)], fill=255)
    return f


def match_pair(img, d):          # %
    text(img, "( )", 20, 11, px=20, max_w=38)
    harrow(d, 20, 3, 31, t=3, head=6)
    harrow(d, 20, 37, 31, t=3, head=6)


def find(kind):                  # f F t T
    def f(img, d):
        left = kind in ("F", "T")
        till = kind in ("t", "T")
        if left:
            charbox(img, d, 1, 1)
            harrow(d, 38, 21 if till else 15, 9, t=3, head=6)
        else:
            charbox(img, d, 26, 1)
            harrow(d, 1, 18 if till else 24, 9, t=3, head=6)
        text(img, "till" if till else "find", 20, 30, px=13, max_w=38)
    return f


def find_small(left):
    def f(img, d):
        if left:
            charbox(img, d, 4, 0, w=12, h=14)
            harrow(d, 36, 18, 7, t=3, head=5)
        else:
            charbox(img, d, 24, 0, w=12, h=14)
            harrow(d, 3, 22, 7, t=3, head=5)
    return f


def search(left=False, word=None):
    def f(img, d):
        if word is None:
            magnifier(d, 13, 13, r=9)
            if left:
                harrow(d, 38, 22, 33, t=3, head=6)
            else:
                harrow(d, 20, 38, 33, t=3, head=6)
            return
        magnifier(d, 9, 9, r=6)
        if left is not None:
            if left:
                harrow(d, 38, 22, 9, t=3, head=6)
            else:
                harrow(d, 22, 38, 9, t=3, head=6)
        text(img, word, 20, 30, px=12, max_w=38)
    return f


def insert_at(where):            # i a I A
    def f(img, d):
        if where in ("i", "a"):
            bar(d, 1, 38, 30)
            d.rectangle([16, 8, 25, 22], fill=255)           # the block cursor
            caret(d, 12 if where == "i" else 28, 5, 25)
            d.rectangle([12 if where == "i" else 28, 5, 13 if where == "i" else 29, 25],
                        fill=255)
            d.rectangle([15, 8, 15, 22], fill=0)
            d.rectangle([26, 8, 26, 22], fill=0)
        else:
            bar(d, 9, 30, 16)
            bar(d, 9, 30, 24)
            if where == "I":
                caret(d, 4, 10, 32)
            else:
                caret(d, 34, 10, 32)
    return f


def open_line(below):            # o O
    """The current line (solid) and the new, empty line (dashed) with the
    cursor at its start, below or above it."""
    def f(img, d):
        cur, new = (6, 27) if below else (31, 10)
        bar(d, 2, 37, cur, h=4)
        caret(d, 4, new - 8, new + 10)
        for x in range(11, 37, 6):
            d.rectangle([x, new, x + 3, new + 2], fill=255)
    return f


def visual(kind):                # v V CTRL-V
    def f(img, d):
        rows = (5, 14, 23, 32)
        for y in rows:
            bar(d, 2, 37, y + 2, h=2)
        if kind == "v":
            d.rectangle([16, 3, 37, 10], fill=255)
            d.rectangle([2, 12, 37, 19], fill=255)
            d.rectangle([2, 21, 22, 28], fill=255)
        elif kind == "V":
            d.rectangle([0, 12, 39, 28], fill=255)
        else:
            d.rectangle([12, 3, 27, 37], fill=255)
    return f


def other_end(block):            # visual o O
    def f(img, d):
        if block:
            d.rectangle([8, 2, 31, 22], fill=255)
        else:
            d.rectangle([2, 8, 37, 16], fill=255)
        harrow(d, 20, 2, 31, t=3, head=6)
        harrow(d, 19, 37, 31, t=3, head=6)
    return f


def case(kind):
    """~ swaps case, visual U / u to upper / lower."""
    def f(img, d):
        if kind == "swap":
            text(img, "aA", 20, 11, px=19, max_w=38)
            harrow(d, 6, 34, 27, t=2, head=4)
            harrow(d, 34, 6, 34, t=2, head=4)
        else:
            a, b = ("a", "A") if kind == "upper" else ("A", "a")
            text(img, a, 7, 20, px=19)
            harrow(d, 14, 26, 21, t=3, head=5)
            text(img, b, 33, 20, px=19)
    return f


def replace_char(img, d):        # r
    text(img, "a", 7, 20, px=19)
    harrow(d, 14, 26, 21, t=3, head=5)
    text(img, "b", 33, 20, px=19)


def replace_mode(img, d):        # R, <Insert>
    text(img, "a", 7, 11, px=17)
    harrow(d, 14, 26, 12, t=3, head=5)
    text(img, "b", 33, 11, px=17)
    text(img, "mode", 20, 31, px=12, max_w=38)


def join(img, d):                # J
    """The second line moves up to the end of the first."""
    bar(d, 1, 17, 6, h=4)
    bar(d, 1, 17, 30, h=4)
    d.rectangle([20, 30, 37, 33], fill=255)
    d.rectangle([34, 12, 37, 33], fill=255)
    d.rectangle([28, 6, 37, 9], fill=0)
    harrow(d, 37, 20, 8, t=4, head=7)
    d.rectangle([34, 9, 37, 12], fill=255)


def counter(sign):               # CTRL-A CTRL-X
    def f(img, d):
        text(img, sign + "1", 20, 20, px=24, max_w=38)
    return f


def cmdline(img, d):             # :
    """The window with the command line at its bottom: ":" and the cursor."""
    frame(d, 1, 1, 38, 38)
    d.rectangle([1, 24, 38, 25], fill=255)
    d.rectangle([7, 28, 9, 30], fill=255)
    d.rectangle([7, 33, 9, 35], fill=255)
    d.rectangle([13, 28, 19, 35], fill=255)


def popup(arrow_dir=None):       # completion list
    def f(img, d):
        w = 25 if arrow_dir else 37
        box(d, 1, 1, w, 38)
        for i, y in enumerate((7, 17, 27)):
            if i == 1:
                d.rectangle([4, y - 3, w - 3, y + 5], fill=255)
            else:
                bar(d, 5, w - 5, y)
        if arrow_dir == "down":
            varrow(d, 4, 35, 33, t=3, head=5)
        elif arrow_dir == "up":
            varrow(d, 35, 4, 33, t=3, head=5)
    return f


def char_from(below):            # i_CTRL-E i_CTRL-Y
    def f(img, d):
        if below:
            caret(d, 19, 1, 15)
            charbox(img, d, 13, 25, w=14, h=15)
            varrow(d, 25, 16, 33, t=2, head=4)
        else:
            charbox(img, d, 13, 0, w=14, h=15)
            caret(d, 19, 24, 38)
            varrow(d, 3, 22, 33, t=2, head=4)
    return f


def word_top(top, bottom, top_px=13):
    def f(img, d):
        text(img, top, 20, 10, px=top_px, max_w=38)
        text(img, bottom, 20, 30, px=12, max_w=38)
    return f


def digraph(img, d):             # CTRL-K
    text(img, "e:", 10, 11, px=15)
    harrow(d, 20, 34, 12, t=3, head=5)
    text(img, "ë", 20, 30, px=17)


def esc_key(img, d):
    keycap_esc(img, d)


def history(up):
    def f(img, d):
        paste_icon(img, "history", 26, 0, 7)
        if up:
            varrow(d, 36, 4, 33, t=3, head=5)
        else:
            varrow(d, 4, 36, 33, t=3, head=5)
    return f


def tag_jump(back):
    def f(img, d):
        paste_icon(img, "tag", 24, 8, 0)
        if back:
            harrow(d, 34, 5, 32, t=3, head=6)
        else:
            harrow(d, 5, 34, 32, t=3, head=6)
    return f


def alt_file(img, d):            # CTRL-^
    paste_icon(img, "swap", 22, 9, 0)
    text(img, "file", 20, 31, px=12, max_w=38)


def mark_jump(word):
    def f(img, d):
        paste_icon(img, "bookmark", 22, 0, 0)
        harrow(d, 22, 38, 11, t=3, head=5)
        text(img, word, 20, 31, px=12, max_w=38)
    return f


def restore(what):               # Replace mode <BS> CTRL-W CTRL-U
    return icon_over("undo", word=what, px=22) if what != "char" else icon_over(
        "undo", suffix="char", px=22)


def backspace_word(word):
    return icon_over("backspace", word=word, px=22)


def delete_fwd(img, d):          # x, <Del>
    paste_icon(img, "backspace", 36, 2, 2, mirror=True)


def delete_back(img, d):         # X, i_CTRL-H
    paste_icon(img, "backspace", 36, 2, 2)


def substitute_again(img, d):
    text(img, ":s", 20, 10, px=15)
    text(img, "again", 20, 30, px=12, max_w=38)


def plain(stem):
    def f(img, d):
        paste_icon(img, stem, 34, 3, 3)
    return f


DRAWN = {
    # cursor
    "left": arrow("left"), "right": arrow("right"),
    "up": arrow("up"), "down": arrow("down"),
    "word_next": h_word("word"), "word_prev": h_word("word", left=True),
    "word_end": h_word("end"),
    "bigword_next": h_word("WORD"), "bigword_prev": h_word("WORD", left=True),
    "bigword_end": h_word("END"),
    "sentence_prev": h_word("sent.", left=True), "sentence_next": h_word("sent."),
    "jump_older": h_word("jump", left=True), "jump_newer": h_word("jump"),
    "line_start": line_start, "first_char": first_char, "line_end": line_end,
    "column": column,
    "line_prev": v_word("line", up=True), "line_next": v_word("line"),
    "para_prev": v_word("para", up=True), "para_next": v_word("para"),
    "screen_top": screen_pos("top"), "screen_mid": screen_pos("mid"),
    "screen_bot": screen_pos("bot"),
    "file_end": plain("bottom"), "file_start": plain("top"),
    "match_pair": match_pair,
    "find_next": find("f"), "find_prev": find("F"),
    "till_next": find("t"), "till_prev": find("T"),
    "find_again": again(find_small(False)), "find_again_rev": again(find_small(True)),
    "search_fwd": search(), "search_back": search(left=True),
    "match_next": search(None, "next"), "match_prev": search(None, "prev"),
    "word_search_fwd": search(False, "word"), "word_search_back": search(True, "word"),
    "mark_pos": mark_jump("pos"), "mark_line": mark_jump("line"),
    "tag_jump": tag_jump(False), "tag_back": tag_jump(True), "alt_file": alt_file,
    # scrolling
    "page_down": scroll("page"), "page_up": scroll("page", up=True),
    "half_down": scroll("half"), "half_up": scroll("half", up=True),
    "scroll_down": scroll("line"), "scroll_up": scroll("line", up=True),
    # inserting
    "insert": insert_at("i"), "append": insert_at("a"),
    "insert_bol": insert_at("I"), "append_eol": insert_at("A"),
    "open_below": open_line(True), "open_above": open_line(False),
    # editing
    "delete": plain("eraser"), "delete_eol": icon_over("eraser", "eol"),
    "delete_lines": icon_over("eraser", "line"),
    "change": plain("edit"), "change_eol": icon_over("edit", "eol"),
    "change_char": icon_over("edit", "char"), "change_line": icon_over("edit", "line"),
    "delete_char": delete_fwd, "delete_before": delete_back,
    "yank_lines": icon_over("copy", "line"),
    "put_after": icon_over("paste", "right"), "put_before": icon_over("paste", "left"),
    "undo_line": icon_over("undo", "line"),
    "replace_char": replace_char, "replace_mode": replace_mode,
    "swap_case": case("swap"), "to_upper": case("upper"), "to_lower": case("lower"),
    "join": join,
    "increment": counter("+"), "decrement": counter("-"),
    "repeat_change": again(lambda img, d: paste_icon(img, "edit", 20, 10, 0)),
    "repeat_subst": substitute_again,
    "cmdline": cmdline,
    "visual_char": visual("v"), "visual_line": visual("V"), "visual_block": visual("b"),
    "other_end": other_end(False), "other_corner": other_end(True),
    # insert / replace / command-line mode
    "complete_next": popup("down"), "complete_prev": popup("up"),
    "complete": popup(None),
    "char_below": char_from(True), "char_above": char_from(False),
    "insert_again": word_top("ins", "again"),
    "normal_once": word_top("norm", "once"),
    "literal": word_top("^M", "raw", top_px=15),
    "digraph": digraph,
    "esc": esc_key,
    "del_word_before": backspace_word("word"),
    "del_line_before": backspace_word("line"),
    "restore_char": restore("char"), "restore_word": restore("word"),
    "restore_line": restore("line"),
    "history_prev": history(True), "history_next": history(False),
}
DRAWN.update({stem: plain(stem) for stem in PLAIN})


def _to_rgba(img: Image.Image) -> Image.Image:
    alpha = img.point(lambda v: 255 if v >= 128 else 0)
    white = Image.new("L", img.size, 255)
    return Image.merge("RGBA", (white, white, white, alpha))


def _draw_one(func):
    img, d = canvas()
    func(img, d)
    return img


def vim_logo(dest: Path) -> None:
    """Vim's own logo, runtime/vimlogo.svg, rendered at 256 px."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    req = urllib.request.Request(VIM_LOGO_URL, headers={"User-Agent": "polykybd"})
    svg = urllib.request.urlopen(req, timeout=30).read()
    png = cairosvg.svg2png(bytestring=svg, output_width=256, output_height=256)
    Image.open(io.BytesIO(png)).convert("RGBA").save(dest)
    print(f"  {dest.name}  <- vim/vim runtime/vimlogo.svg (Vim license)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--redraw", action="store_true",
                    help="redraw every drawn glyph, even a committed one")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    missing = {k: v for k, v in FLUENT.items() if not (SRC / f"{k}.png").exists()}
    if missing:
        icon_fetch.fluent(missing, SRC)
    for name, func in DRAWN.items():
        dest = OUT / f"{name}.png"
        if dest.exists() and not args.redraw:
            continue
        _to_rgba(_draw_one(func)).save(dest)
    print(f"  {len(DRAWN)} drawn glyphs in {OUT}")
    vim_logo(OUT / "vim.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
