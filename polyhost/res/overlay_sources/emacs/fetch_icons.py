#!/usr/bin/env python3
"""Fetch + draw the GNU Emacs shortcut icons (reproducible).

Three sources:

* Microsoft Fluent UI System Icons (MIT), with Material Symbols (Apache-2.0)
  for the `ms:` entries: commands that have a usual picture (comment, wrap,
  shell, rename, link).
* DRAWN composites, 40x32 and 1-bit at keycap size: a glyph above a word of up
  to four letters. Emacs has families of commands that differ only by the unit
  they act on (move by CHR / WORD / LINE / SENT / PARA / SEXP, kill a CHR /
  WORD / LINE, transpose CHR / WORD / SEXP), and a picture alone cannot name
  the unit. The glyph says what (arrow = move, delete-key shape = kill, swap,
  dashed box = mark, magnifier = search) and the word says the unit.
* The ESC mark: the GNU Emacs logo from Simple Icons (`gnuemacs`, CC0 artwork;
  nominative use, see `../brand_marks.py`).

Drawn icons and the mark are guarded: a committed file is left as-is, so a
hand edit survives a re-run.

    pip install cairosvg
    python polyhost/res/overlay_sources/emacs/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    # global
    "recenter": "ms:vertical_align_center",
    "abort": "Dismiss Circle",
    "openline": "ms:playlist_add",
    "quoted": "ms:format_quote",
    "suspend": "Arrow Minimize",
    "newline_indent": "ms:keyboard_return",
    "inputmethod": "Local Language",
    "recursive_abort": "ms:exit_to_app",
    "recursive_exit": "ms:logout",
    "killwholeline": "Delete Lines",
    "buffermenu": "ms:list",
    "yankpop": "ms:content_paste_go",
    "fill": "ms:wrap_text",
    "command": "Apps List Detail",
    "comment": "Comment",
    "definition": "Target",
    "xref_back": "Arrow Left",
    "xref_forward": "Arrow Right",
    "references": "ms:manage_search",
    "apropos": "ms:quick_reference_all",
    "dabbrev": "ms:auto_fix_high",
    "wordcount": "Text Word Count",
    "cyclespace": "ms:space_bar",
    "indentation": "ms:format_indent_increase",
    "tabstop": "ms:keyboard_tab",
    "windowline": "ms:vertical_align_top",
    "menubar_text": "ms:menu_open",
    "queryreplace": "ms:find_replace",
    "join": "ms:merge",
    "shell": "Window Console",
    "spell": "Text Proofing Tools",
    "unmodified": "ms:edit_off",
    "scrollother": "ms:splitscreen_bottom",
    "reposition": "ms:center_focus_strong",
    "splitline": "ms:call_split",
    "indentregion": "Text Indent Increase",
    "macro_start": "Record",
    "macro_end": "Play",
    "menu": "ms:menu",
    "fullscreen": "Full Screen Maximize",
    "maximize": "Maximize",
    "contextmenu": "ms:more_vert",
    # org-mode
    "cycle": "ms:unfold_more",
    "cycle_all": "ms:unfold_more_double",
    "promote": "ms:format_indent_decrease",
    "demote": "ms:format_indent_increase",
    "agenda_cycle": "Calendar Arrow Right",
    # dired
    "open": "ms:file_open",
    "openother": "ms:open_in_new",
    "display": "ms:preview",
    "findalternate": "ms:input",
    "zip": "ms:folder_zip",
    "compress": "ms:compress",
    "flagdel": "ms:flag",
    "delete": "Delete",
    "deletenow": "ms:delete_forever",
    "refresh": "Arrow Clockwise",
    "redisplay": "Arrow Sync",
    "subdir": "ms:account_tree",
    "gotofile": "Document Search",
    "hide": "ms:visibility_off",
    "mark": "Checkbox Checked",
    "unmark": "Checkbox Unchecked",
    "unmarkall": "ms:deselect",
    "togglemarks": "ms:flip",
    "quitwin": "Dismiss",
    "sort": "Arrow Sort",
    "view": "Eye",
    "filetype": "Info",
    "diff": "ms:difference",
    "clean": "ms:cleaning_services",
    "updir": "Folder Arrow Up",
    "mkdir": "Folder Add",
    "details": "ms:view_headline",
    "hidesubdir": "ms:unfold_less",
    "hideall": "ms:unfold_less_double",
    "unmarkback": "ms:backspace",
    "summary": "ms:info",
    "grep": "ms:manage_search",
    "bytecompile": "ms:build",
    "copyfiles": "Document Copy",
    "chgrp": "People",
    "info": "ms:menu_book",
    "load": "ms:upload_file",
    "chmod": "Lock Closed",
    "man": "ms:description",
    "chown": "Person",
    "rename": "Rename",
    "touch": "ms:schedule",
    "browse": "Globe",
    # top glyphs for composites only (not bound directly)
    "_link": "Link",
    "_copy": "Copy",
    "_cut": "Cut",
    "_flag": "ms:flag",
    "_code": "Code",
}

# ---------------------------------------------------------------- composites

W, H = 40, 32          # the binding region; drawn 1:1
SS = 4                 # supersampling for the glyphs
BAND = 19              # glyph band height (top); the word sits below it
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
_FONTS: dict[int, ImageFont.FreeTypeFont] = {}


def _font(px: int) -> ImageFont.FreeTypeFont:
    if px not in _FONTS:
        _FONTS[px] = ImageFont.truetype(BOLD, px)
    return _FONTS[px]


def _arrow(d, x0, y0, x1, y1, w=3.0, head=7.0):
    """A thick arrow from (x0, y0) to its tip (x1, y1), in output pixels.

    The shaft is a polygon, not `line(width=...)`, which leaves a tick at the
    tail and a notch under the head at keycap size."""
    s = SS
    dx, dy = x1 - x0, y1 - y0
    n = max(abs(dx), abs(dy))
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    bx, by = x1 - ux * head, y1 - uy * head
    hw = w / 2
    d.polygon([((x0 + px * hw) * s, (y0 + py * hw) * s), ((bx + px * hw) * s, (by + py * hw) * s),
               ((bx - px * hw) * s, (by - py * hw) * s), ((x0 - px * hw) * s, (y0 - py * hw) * s)],
              fill=255)
    hh = head * 0.8
    d.polygon([(x1 * s, y1 * s),
               ((bx + px * hh) * s, (by + py * hh) * s),
               ((bx - px * hh) * s, (by - py * hh) * s)], fill=255)


def _bar(d, x0, y0, x1, y1):
    d.rectangle([x0 * SS, y0 * SS, x1 * SS - 1, y1 * SS - 1], fill=255)


def _glyph(d, name, top_png=None):  # noqa: C901 - one branch per glyph, on purpose
    """Draw glyph `name` into the band (output pixels 0..W, 0..BAND)."""
    cy = 9
    if name == "left":
        _arrow(d, 34, cy, 5, cy)
    elif name == "right":
        _arrow(d, 6, cy, 35, cy)
    elif name == "up":
        _arrow(d, 20, 18, 20, 0)
    elif name == "down":
        _arrow(d, 20, 0, 20, 18)
    elif name == "barleft":
        _bar(d, 5, 1, 8, 18)
        _arrow(d, 35, cy, 10, cy)
    elif name == "barright":
        _bar(d, 32, 1, 35, 18)
        _arrow(d, 5, cy, 30, cy)
    elif name == "top":
        _bar(d, 9, 0, 31, 3)
        _arrow(d, 20, 19, 20, 5, head=8)
    elif name == "bottom":
        _bar(d, 9, 16, 31, 19)
        _arrow(d, 20, 0, 20, 14, head=8)
    elif name in ("killright", "killleft"):
        # The Delete / Backspace key shape: a box with a point, an X inside.
        pts = [(4, 1), (27, 1), (36, cy + 0.5), (27, 18), (4, 18)]
        if name == "killleft":
            pts = [(40 - x, y) for x, y in pts]
        d.polygon([(x * SS, y * SS) for x, y in pts], outline=255, width=int(2 * SS))
        cx = 16 if name == "killright" else 24
        for a, b in (((cx - 4, cy - 4), (cx + 4, cy + 5)), ((cx - 4, cy + 5), (cx + 4, cy - 4))):
            d.line([(a[0] * SS, a[1] * SS), (b[0] * SS, b[1] * SS)], fill=255, width=int(2 * SS))
    elif name == "swap":
        _arrow(d, 6, 4, 34, 4, w=2.5, head=6)
        _arrow(d, 34, 14, 6, 14, w=2.5, head=6)
    elif name in ("search", "searchback"):
        cx, r = (12, 6) if name == "search" else (28, 6)
        d.ellipse([(cx - r) * SS, (8 - r) * SS, (cx + r) * SS, (8 + r) * SS],
                  outline=255, width=int(2.5 * SS))
        hx = 1 if name == "search" else -1
        d.line([((cx + hx * 4) * SS, 12 * SS), ((cx + hx * 8) * SS, 17 * SS)],
               fill=255, width=int(3 * SS))
        if name == "search":
            _arrow(d, 23, cy, 39, cy, w=2.5, head=6)
        else:
            _arrow(d, 17, cy, 1, cy, w=2.5, head=6)
    elif name == "selbox":
        # A dashed selection rectangle.
        x0, y0, x1, y1 = 4, 1, 36, 18
        for x in range(x0, x1, 6):
            _bar(d, x, y0, min(x + 4, x1), y0 + 2)
            _bar(d, x, y1 - 2, min(x + 4, x1), y1)
        for y in range(y0, y1, 6):
            _bar(d, x0, y, x0 + 2, min(y + 4, y1))
            _bar(d, x1 - 2, y, x1, min(y + 4, y1))
    elif name == "caret":
        # The mark: an I-beam with a flag on it.
        _bar(d, 13, 1, 16, 18)
        _bar(d, 9, 0, 20, 2)
        _bar(d, 9, 17, 20, 19)
        d.polygon([(16 * SS, 2 * SS), (30 * SS, 6 * SS), (16 * SS, 11 * SS)], fill=255)
    elif name == "plus":
        _bar(d, 18, 1, 22, 18)
        _bar(d, 11, 7, 29, 11)
    elif name == "plusafter":
        # "+ after the subtree": a plus and a down-to-bar arrow.
        _bar(d, 9, 1, 13, 18)
        _bar(d, 2, 7, 20, 11)
        _arrow(d, 30, 0, 30, 12, w=3, head=6)
        _bar(d, 24, 15, 37, 18)
    elif name.startswith("text:"):
        text = name[5:]
        f = _font(17 * SS)
        w = d.textlength(text, font=f)
        d.text(((W * SS - w) / 2, 17 * SS), text, font=f, fill=255, anchor="ls")
    elif name.startswith("png:"):
        src = Image.open(top_png).convert("RGBA").split()[3]
        box = src.getbbox() or (0, 0, *src.size)
        src = src.crop(box)
        scale = min((BAND - 1) * SS / src.height, (W - 6) * SS / src.width)
        src = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))),
                         Image.LANCZOS)
        return src
    else:
        raise ValueError(f"unknown glyph {name!r}")
    return None


def composite(dest: Path, glyph: str, word: str, icons: Path) -> None:
    """Draw `glyph` above `word`, 40x32 white-on-transparent, 1-bit."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    big = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(big)
    top_png = None
    if glyph.startswith("png:"):
        top_png = icons / f"{glyph[4:]}.png"
    pasted = _glyph(d, glyph, top_png)
    if pasted is not None:
        big.paste(255, ((W * SS - pasted.width) // 2, 0), pasted)
    # A pasted Fluent/Material glyph has 1.5 px strokes; a lower cut keeps them.
    cut = 80 if pasted is not None else 128
    mask = big.resize((W, H), Image.LANCZOS).point(lambda v: 255 if v >= cut else 0)
    if word:
        md = ImageDraw.Draw(mask)
        f = _font(16 if len(word) == 1 else 12)
        w = md.textlength(word, font=f)
        md.text(((W - w) / 2, H - 1), word, font=f, fill=255, anchor="ls")
        mask = mask.point(lambda v: 255 if v >= 128 else 0)
    img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    img.putalpha(mask)
    img.save(dest)
    print(f"  {dest.name}  <- drawn: {glyph} + '{word}'")


# file stem -> (glyph, word). A word is at most four capitals so it reads at 12 px.
COMPOSITES = {
    # motion
    "char_fwd": ("right", "CHR"), "char_back": ("left", "CHR"),
    "word_fwd": ("right", "WORD"), "word_back": ("left", "WORD"),
    "line_next": ("down", "LINE"), "line_prev": ("up", "LINE"),
    "line_start": ("barleft", "LINE"), "line_end": ("barright", "LINE"),
    "sent_back": ("left", "SENT"), "sent_fwd": ("right", "SENT"),
    "para_back": ("up", "PARA"), "para_fwd": ("down", "PARA"),
    "page_down": ("down", "PAGE"), "page_up": ("up", "PAGE"),
    "buf_start": ("top", "BUF"), "buf_end": ("bottom", "BUF"),
    "sexp_fwd": ("right", "SEXP"), "sexp_back": ("left", "SEXP"),
    "defun_start": ("barleft", "FUNC"), "defun_end": ("barright", "FUNC"),
    "list_fwd": ("right", "LIST"), "list_back": ("left", "LIST"),
    "list_up": ("up", "LIST"), "list_down": ("down", "LIST"),
    "scroll_right": ("right", "SCRL"), "scroll_left": ("left", "SCRL"),
    # killing and deleting
    "kill_line": ("killright", "LINE"), "del_char": ("killright", "CHR"),
    "kill_word": ("killright", "WORD"), "kill_word_back": ("killleft", "WORD"),
    "kill_sent": ("killright", "SENT"), "kill_sexp": ("killright", "SEXP"),
    "zap": ("killright", "ZAP"), "del_space": ("killright", "SPC"),
    "append_kill": ("png:_cut", "NEXT"),
    # transposing, marking, case
    "tr_char": ("swap", "CHR"), "tr_word": ("swap", "WORD"), "tr_sexp": ("swap", "SEXP"),
    "set_mark": ("caret", "MARK"),
    "mark_word": ("selbox", "WORD"), "mark_para": ("selbox", "PARA"),
    "mark_defun": ("selbox", "FUNC"), "mark_sexp": ("selbox", "SEXP"),
    "upcase": ("text:AB", "WORD"), "downcase": ("text:ab", "WORD"),
    "capitalize": ("text:Ab", "WORD"),
    # search
    "isearch_fwd": ("search", ""), "isearch_back": ("searchback", ""),
    "re_search_fwd": ("search", "REGX"), "re_search_back": ("searchback", "REGX"),
    "re_replace": ("png:queryreplace", "REGX"),
    # misc
    "universal": ("text:×4", "ARG"),
    "complete": ("png:dabbrev", "SYM"), "dabbrev_list": ("png:dabbrev", "LIST"),
    "overwrite": ("text:OVR", "MODE"),
    "parens": ("text:( )", "INS"),
    "shell_async": ("png:shell", "&"),
    "shell_region": ("png:shell", "|"),
    "eval": ("png:_code", "EVAL"),
    # org-mode
    "org_heading": ("plus", "HEAD"), "org_heading_after": ("plusafter", "HEAD"),
    "org_todo_new": ("plus", "TODO"), "org_todo_after": ("plusafter", "TODO"),
    "org_promote_tree": ("png:promote", "TREE"), "org_demote_tree": ("png:demote", "TREE"),
    "org_tree_up": ("up", "TREE"), "org_tree_down": ("down", "TREE"),
    "org_line_up": ("up", "LINE"), "org_line_down": ("down", "LINE"),
    "org_todo_prev": ("left", "TODO"), "org_todo_next": ("right", "TODO"),
    "org_prio_up": ("up", "PRIO"), "org_prio_down": ("down", "PRIO"),
    "org_set_prev": ("left", "SET"), "org_set_next": ("right", "SET"),
    "org_elem_back": ("up", "ELEM"), "org_elem_fwd": ("down", "ELEM"),
    "org_mark_elem": ("selbox", "ELEM"), "org_tr_elem": ("swap", "ELEM"),
    "org_copy_down": ("down", "COPY"),
    # dired
    "dired_dir_prev": ("up", "DIR"), "dired_dir_next": ("down", "DIR"),
    "dired_subdir_prev": ("left", "SDIR"), "dired_subdir_next": ("right", "SDIR"),
    "dired_tree_up": ("up", "TREE"), "dired_tree_down": ("down", "TREE"),
    "dired_marked_prev": ("up", "MARK"), "dired_marked_next": ("down", "MARK"),
    "dired_copyname": ("png:_copy", "NAME"),
    "dired_flag_autosave": ("png:_flag", "AUTO"), "dired_flag_backup": ("png:_flag", "BAK"),
    "dired_hardlink": ("png:_link", "HARD"), "dired_symlink": ("png:_link", "SYM"),
    "dired_relsymlink": ("png:_link", "REL"),
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    for stem, (glyph, word) in COMPOSITES.items():
        composite(out / f"{stem}.png", glyph, word, out)
    brand_marks.ensure(out / "emacs.png", "gnuemacs")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
