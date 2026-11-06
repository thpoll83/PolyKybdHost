#!/usr/bin/env python3
"""Fetch and draw the icons of the yazi, ranger and lf overlay sets (reproducible).

The three terminal file managers share one icon folder, so an action that two of
them have (copy, cut, paste, parent directory, toggle hidden, next tab) is drawn
with the same picture in each set. Sources:

* Microsoft Fluent UI System Icons (MIT), with Material Symbols (Apache-2.0) for
  the `ms:` entries. Where an action is the same as in the Total Commander set
  (`../totalcmd/`), the same glyph is used: parent folder, back, forward, view,
  rename, new file, close tab, new tab, reload, filter, shell.
* DRAWN composites, 40x32 and 1-bit at keycap size: a glyph above a word of up
  to four letters, made with the GNU Emacs set's `composite()`
  (`../emacs/fetch_icons.py`), so a motion reads the same as in Emacs and nano.
* Four search composites copied from the nano set (`../nano/icons/`), so the
  same search action draws byte-identical cells in every terminal program.
* The three ESC marks (see SOURCES.md):
  - yazi: the duck of `assets/logo.png` in the yazi repository (MIT).
  - ranger: the "r" of `ranger_logo.png` from the ranger website repository.
  - lf: the project has no logo, so a folder with "lf" cut out is drawn here.

Drawn icons and the marks are guarded: a committed file is left as-is, so a hand
edit survives a re-run. To redraw one, delete its PNG first.

    pip install cairosvg
    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/tui_file_managers/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.emacs import fetch_icons as emacs  # noqa: E402
from polyhost.res.overlay_sources import number_badge  # noqa: E402

FLUENT = {
    # --- movement and navigation ---
    "up": "Arrow Up",
    "down": "Arrow Down",
    "parent": "Folder Arrow Up",          # totalcmd parent
    "enter": "Folder Arrow Right",       # totalcmd mkdirtarget
    "back": "Arrow Left",                 # totalcmd back
    "forward": "Arrow Right",             # totalcmd forward
    "screen_top": "ms:align_vertical_top",
    "screen_mid": "ms:align_vertical_center",
    "screen_low": "ms:align_vertical_bottom",
    "traverse_fwd": "ms:subdirectory_arrow_right",
    "traverse_back": "ms:subdirectory_arrow_left",
    # --- open, view, edit ---
    "open": "Open",
    "open_with": "ms:menu_open",
    "view": "Eye",                        # totalcmd view
    "edit": "Edit",
    "info": "Info",
    # --- copy, cut, paste, links, delete ---
    "copy": "Copy",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "paste_force": "ms:content_paste_go",
    "unyank": "ms:content_paste_off",
    "symlink": "Link",
    "symlink_rel": "Link Square",
    "hardlink": "Link Multiple",
    "trash": "Delete",
    "delete_perm": "Delete Dismiss",      # totalcmd deleteperm
    "copy_path": "Clipboard Link",
    # --- create and rename ---
    "newfile": "Document Add",            # totalcmd newfile
    "bulk_create": "ms:library_add",
    "newfolder": "Folder Add",            # totalcmd newfolder
    "rename": "Rename",                   # totalcmd rename
    "rename_all": "ms:edit_note",
    "rename_start": "ms:text_select_start",
    "chmod": "Key",
    # --- selection ---
    "toggle_select": "Checkbox Checked",
    "select_all": "Select All On",
    "invert_select": "ms:flip",
    "visual": "ms:select",
    "visual_unset": "ms:deselect",
    "tag": "Tag",
    "tag_with": "Tag Multiple",
    # --- search, filter, sort, view options ---
    "search": "Search",
    "search_content": "Document Search",  # totalcmd lister
    "search_cancel": "ms:search_off",
    "find_file": "Search Square",         # totalcmd findproc
    "jump_dir": "Folder Search",          # totalcmd treedialog
    "filter": "Filter",                   # totalcmd quickfilter
    "sort": "Arrow Sort",                 # totalcmd unsorted
    "hidden": "Eye Off",
    "linemode": "ms:view_list",
    "viewmode": "ms:view_column",
    "options": "Options",
    "goto": "Location Arrow",
    # --- bookmarks (marks) ---
    "bookmark": "Bookmark",
    "bookmark_add": "Bookmark Add",
    "bookmark_off": "Bookmark Off",
    # --- tabs ---
    "tab": "Tab",                         # base of tab1..tab9 (number_badge), as WezTerm's
    "tab_group": "Tab Desktop Multiple",
    "newtab": "Tab Add",                  # totalcmd newtab
    "closetab": "Dismiss",                # totalcmd closetab
    # --- shell and program ---
    "shell": "Window Console",            # totalcmd cmdhistory
    "subshell": "ms:terminal",
    "console": "Text Field",              # totalcmd pathtocmd
    "history": "History",
    "tasks": "ms:task",
    "log": "Document Text",
    "quit": "Power",                      # totalcmd exit
    "suspend": "Pause",
    "reload": "Arrow Sync",               # totalcmd reread
    "redraw": "ms:screenshot_monitor",
    "reset": "Arrow Reset",
    "abort": "ms:cancel",
    "freeze": "Weather Snowflake",
    "undo": "Arrow Undo",
}

# Drawn with emacs.composite(): file stem -> (glyph, word). A `png:` glyph is one
# of the icons above (or below, for the `_` helpers), drawn small above the word.
COMPOSITES = {
    "half_up": ("up", "HALF"), "half_down": ("down", "HALF"),
    "page_up": ("up", "PAGE"), "page_down": ("down", "PAGE"),
    "scroll_up": ("up", "SCRL"), "scroll_down": ("down", "SCRL"),
    "last": ("bottom", "END"),
    "tab_prev": ("left", "TAB"), "tab_next": ("right", "TAB"),
    "tab_swap_left": ("left", "SWAP"), "tab_swap_right": ("right", "SWAP"),
    "jump_back": ("left", "JUMP"), "jump_fwd": ("right", "JUMP"),
    "dir_prev": ("up", "DIR"), "dir_next": ("down", "DIR"),
    "jump_files": ("down", "FILE"),
    "find_char_fwd": ("right", "FIND"), "find_char_back": ("left", "FIND"),
    "find_char_next": ("right", "NEXT"), "find_char_prev": ("left", "PREV"),
    "preview_up": ("up", "PRVW"), "preview_down": ("down", "PRVW"),
    "shell_wait": ("png:_shell", "WAIT"),
    "shell_pipe": ("png:_shell", "PIPE"),
    "shell_bg": ("png:_shell", "BG"),
    "cmd_next": ("png:_history", "NEXT"), "cmd_prev": ("png:_history", "PREV"),
}

# Top glyphs used only inside a composite.
HELPERS = {
    "_shell": "Window Console",
    "_history": "History",
}

# Copied byte for byte from the nano set: search forward / backward, and the
# next / previous match.
BORROWED = {
    "search_fwd.png": "nano",
    "search_back.png": "nano",
    "find_next.png": "nano",
    "find_prev.png": "nano",
}

# --------------------------------------------------------------- ESC marks

MARK_PX = 32

# yazi: assets/logo.png at the v26.9.1 tag of sxyazi/yazi (MIT).
YAZI_LOGO_URL = ("https://raw.githubusercontent.com/sxyazi/yazi/"
                 "8dd895c695a5950330c2623eb43debf323b60654/assets/logo.png")
# ranger: ranger_logo.png in ranger/ranger.github.io at a pinned commit.
RANGER_LOGO_URL = ("https://raw.githubusercontent.com/ranger/ranger.github.io/"
                   "eae5f11bbb247e221468b466da2d2214442dfa06/ranger_logo.png")
# Both logos put a white or light grey figure on an orange field. At luma 128
# the orange is lit too and the mark is one disc (yazi) or one star (ranger);
# at 190 only the light figure is lit: the duck, and the grey "r".
LIGHT_LUMA = 190
# A connected group of lit pixels this small is noise from the logo's thin
# detail (ranger's "anger" lettering); it is removed.
MIN_SPECK = 3


def _download(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGBA")


def _drop_specks(mask: Image.Image, min_px: int) -> Image.Image:
    """`mask` without the 4-connected lit groups smaller than `min_px`."""
    w, h = mask.size
    px = mask.load()
    seen = set()
    for y in range(h):
        for x in range(w):
            if px[x, y] == 0 or (x, y) in seen:
                continue
            group, todo = [], [(x, y)]
            seen.add((x, y))
            while todo:
                cx, cy = todo.pop()
                group.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and px[nx, ny] and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        todo.append((nx, ny))
            if len(group) < min_px:
                for gx, gy in group:
                    px[gx, gy] = 0
    return mask


def _logo_mark(dest: Path, url: str, px: int = MARK_PX) -> None:
    """A logo as a px*px 1-bit trace: composited over black, fitted into the
    square (contain, LANCZOS), pixels lighter than LIGHT_LUMA lit, specks
    removed. Drawn at the keycap size so the generator copies it 1:1."""
    icon = _download(url)
    black = Image.new("RGBA", icon.size, "black")
    black.alpha_composite(icon)
    src = black.convert("L")
    scale = px / max(src.size)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.LANCZOS)
    square = Image.new("L", (px, px), 0)
    square.paste(fitted, ((px - fitted.width) // 2, (px - fitted.height) // 2))
    a = _drop_specks(square.point(lambda v: 255 if v > LIGHT_LUMA else 0), MIN_SPECK)
    Image.merge("RGBA", (a, a, a, a)).save(dest)


def _lf_mark(dest: Path, px: int = MARK_PX) -> None:
    """lf has no logo (its desktop file names the generic `utilities-terminal`
    icon). A filled folder with the letters "lf" cut out, drawn pixel by pixel
    at 32x32 so the generator copies it 1:1."""
    a = Image.new("L", (px, px), 0)
    p = a.load()

    def rect(x0, y0, x1, y1, v):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                p[x, y] = v

    rect(2, 4, 12, 7, 255)        # the folder tab
    rect(1, 7, 30, 28, 255)       # the folder body
    for x, y in ((1, 7), (30, 7), (1, 28), (30, 28)):
        p[x, y] = 0               # rounded corners
    rect(7, 10, 10, 25, 0)        # l
    rect(16, 12, 19, 25, 0)       # f: stem
    rect(18, 10, 24, 12, 0)       # f: top bar
    p[16, 11] = p[17, 11] = 0     # f: rounded top left
    p[16, 12] = 255
    rect(13, 15, 23, 17, 0)       # f: cross bar
    Image.merge("RGBA", (a, a, a, a)).save(dest)


def _guarded(path: Path, draw) -> None:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        draw(path)
        print(f"  {path.name}  <- drawn in tui_file_managers/fetch_icons.py")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.fluent(HELPERS, out)
    icon_fetch.borrow(BORROWED, out)
    for stem, (glyph, word) in COMPOSITES.items():
        emacs.composite(out / f"{stem}.png", glyph, word, out)
    number_badge.numbered(out / "tab.png", "123456789", out, "tab")
    _guarded(out / "yazi.png", lambda p: _logo_mark(p, YAZI_LOGO_URL))
    _guarded(out / "ranger.png", lambda p: _logo_mark(p, RANGER_LOGO_URL))
    _guarded(out / "lf.png", _lf_mark)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
