#!/usr/bin/env python3
"""Fetch + draw the tmux shortcut icons (reproducible).

Four sources:

* Microsoft Fluent UI System Icons (MIT), with Material Symbols (Apache-2.0)
  for the `ms:` entries, through `icon_fetch`.
* Composites of the GNU Emacs set (`../emacs/fetch_icons.py`, `composite()`):
  a glyph above a word of up to four capitals (WIN = window, PANE, SESS =
  session, CLNT = client, BUF = paste buffer).
* Pane pictures drawn here, 1-bit at the binding size (40x32): a window frame
  with the panes a split or a layout makes, and a window with its number for
  the keys 0 to 9.
* The ESC mark: the tmux logo (the logo/ directory of the tmux repository,
  pinned to the 3.8 tag) reduced to a 32x32 1-bit trace, dark pixels (luma 100 or less) lit.

Drawn icons and the mark are guarded: a committed file is left as-is, so a
hand edit survives a re-run.

    pip install cairosvg
    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/tmux/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.emacs import fetch_icons as emacs  # noqa: E402

FLUENT = {
    "newwindow": "Window New",
    "detach": "Plug Disconnected",
    "zoom": "Full Screen Maximize",
    "paste": "Clipboard Paste",
    "clock": "Clock",
    "info": "Info",
    "redraw": "Arrow Sync",
    "customize": "Settings",
    "suspend": "Arrow Minimize",
    "listkeys": "Question Circle",
    "command": "ms:terminal",
    "messages": "ms:chat",
    # top glyphs for composites only (not bound directly)
    "_history": "History",
    "_choose": "ms:checklist",
    "_bullets": "Text Bullet List",
    "_dismiss": "Dismiss",
    "_rename": "Rename",
    "_move": "Arrow Move",
    "_delete": "Delete",
    "_keyboard": "Keyboard",
    "_menu": "ms:menu",
    "_rotate": "Arrow Rotate Clockwise",
    "_rotateccw": "Arrow Rotate Counterclockwise",
    "_bell": "Alert",
    "_copy": "Copy",
    "_cycle": "ms:cycle",
    "_center": "ms:center_focus_strong",
    "_opennew": "ms:open_in_new",
    "_layout": "ms:dashboard",
}

# file stem -> (glyph, word), drawn by `emacs.composite`.
COMPOSITES = {
    "win_next": ("right", "WIN"), "win_prev": ("left", "WIN"),
    "win_last": ("png:_history", "WIN"),
    "win_choose": ("png:_choose", "WIN"),
    "win_find": ("search", "WIN"),
    "win_kill": ("png:_dismiss", "WIN"),
    "win_rename": ("png:_rename", "WIN"),
    "win_move": ("png:_move", "WIN"),
    "win_index": ("text:#", "WIN"),
    "win_menu": ("png:_menu", "WIN"),
    "win_alert_next": ("png:_bell", "NEXT"), "win_alert_prev": ("png:_bell", "PREV"),
    "pane_up": ("up", "PANE"), "pane_down": ("down", "PANE"),
    "pane_left": ("left", "PANE"), "pane_right": ("right", "PANE"),
    "pane_next": ("png:_cycle", "PANE"),
    "pane_last": ("png:_history", "PANE"),
    "pane_kill": ("png:_dismiss", "PANE"),
    "pane_break": ("png:_opennew", "PANE"),
    "pane_numbers": ("text:123", "PANE"),
    "pane_mark": ("caret", "PANE"), "pane_unmark": ("caret", "CLR"),
    "pane_swap_up": ("up", "SWAP"), "pane_swap_down": ("down", "SWAP"),
    "pane_rotate": ("png:_rotate", "PANE"), "pane_rotate_back": ("png:_rotateccw", "PANE"),
    "pane_menu": ("png:_menu", "PANE"),
    "size_up": ("up", "SZ1"), "size_down": ("down", "SZ1"),
    "size_left": ("left", "SZ1"), "size_right": ("right", "SZ1"),
    "size5_up": ("up", "SZ5"), "size5_down": ("down", "SZ5"),
    "size5_left": ("left", "SZ5"), "size5_right": ("right", "SZ5"),
    "view_up": ("up", "VIEW"), "view_down": ("down", "VIEW"),
    "view_left": ("left", "VIEW"), "view_right": ("right", "VIEW"),
    "view_reset": ("png:_center", "VIEW"),
    "sess_choose": ("png:_choose", "SESS"),
    "sess_rename": ("png:_rename", "SESS"),
    "client_choose": ("png:_choose", "CLNT"),
    "client_prev": ("left", "CLNT"), "client_next": ("right", "CLNT"),
    "client_last": ("png:_history", "CLNT"),
    "buf_list": ("png:_bullets", "BUF"),
    "buf_choose": ("png:_choose", "BUF"),
    "buf_delete": ("png:_delete", "BUF"),
    "copymode": ("png:_copy", "MODE"),
    "copymode_up": ("png:_copy", "UP"),
    "describekey": ("png:_keyboard", "KEY"),
    "layout_next": ("png:_layout", "NEXT"),
    "layout_even": ("png:_layout", "EVEN"),
    "prefix": ("text:tmux", "PRFX"),
}

# ------------------------------------------------------------ pane pictures

W, H = 40, 32
# The window frame: outer box (x0, y0, x1, y1), exclusive ends, 2 px lines.
FX0, FY0, FX1, FY1 = 3, 2, 37, 30
LINE = 2


def _frame():
    import numpy as np
    m = np.zeros((H, W), bool)
    m[FY0:FY1, FX0:FX0 + LINE] = True
    m[FY0:FY1, FX1 - LINE:FX1] = True
    m[FY0:FY0 + LINE, FX0:FX1] = True
    m[FY1 - LINE:FY1, FX0:FX1] = True
    # Round the four corners by one pixel.
    for y, x in ((FY0, FX0), (FY0, FX1 - 1), (FY1 - 1, FX0), (FY1 - 1, FX1 - 1)):
        m[y, x] = False
    return m


def _vline(m, x, y0=FY0, y1=FY1):
    m[y0:y1, x:x + LINE] = True


def _hline(m, y, x0=FX0, x1=FX1):
    m[y:y + LINE, x0:x1] = True


# Inner area: x 5..34, y 4..27. Divider positions are chosen so the panes on
# each side have the same width or height in whole pixels.
def _panes(name):
    m = _frame()
    if name == "split_h":            # % : two panes side by side
        _vline(m, 19)
    elif name == "split_v":          # " : two panes one above the other
        _hline(m, 15)
    elif name == "layout_even_h":    # M-1 even-horizontal: three columns
        _vline(m, 14)
        _vline(m, 24)
    elif name == "layout_even_v":    # M-2 even-vertical: three rows
        _hline(m, 11)
        _hline(m, 19)
    elif name == "layout_main_h":    # M-3 main-horizontal: big top, two below
        _hline(m, 17)
        _vline(m, 19, 17, FY1)
    elif name == "layout_main_v":    # M-4 main-vertical: big left, two right
        _vline(m, 22)
        _hline(m, 15, 22, FX1)
    elif name == "layout_tiled":     # M-5 tiled: four panes
        _vline(m, 19)
        _hline(m, 15)
    else:
        raise ValueError(name)
    return m


PANES = ["split_h", "split_v", "layout_even_h", "layout_even_v",
         "layout_main_h", "layout_main_v", "layout_tiled"]


def panes(out: Path) -> None:
    for name in PANES:
        dest = out / f"{name}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        cnc._save_mask(_panes(name), dest)
        print(f"  {dest.name}  <- drawn: panes")


def window_digits(out: Path) -> None:
    """win0.png .. win9.png: the window frame with a lit title bar and the
    window number in it, as tmux's status line shows the windows by number."""
    import numpy as np
    from PIL import Image, ImageDraw
    font = emacs._font(18)
    for n in range(10):
        dest = out / f"win{n}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        m = _frame()
        m[FY0:FY0 + 5, FX0:FX1] = True       # title bar
        m[FY0, FX0] = m[FY0, FX1 - 1] = False
        im = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(im)
        text = str(n)
        tw = d.textlength(text, font=font)
        # Baseline 2 px above the bottom line; centred across.
        d.text(((W - tw) / 2, FY1 - LINE - 2), text, font=font, fill=255, anchor="ls")
        m |= np.asarray(im) >= 128
        cnc._save_mask(m, dest)
        print(f"  {dest.name}  <- drawn: window {n}")


# --------------------------------------------------------------- ESC mark

# The tmux logomark (screen with a pane split, green status bar) as the
# repository ships it at 128x128. logo/LICENSE: ISC-style permission notice,
# Copyright (c) 2015, Jason Long. Pinned to the 3.8 tag's commit.
TMUX_ICON_URL = ("https://raw.githubusercontent.com/tmux/tmux/"
                 "7f2a35ad3321f9ba57a1062ca73b1f3ff26aca53/logo/icons/128x128/tmux.png")
TMUX_DARK_LUMA = 100


def _tmux_mark(dest: Path, px: int = 32) -> None:
    """The tmux logo as a px*px 1-bit mark: the dark screen (luma 100 or
    darker) is lit where a pixel is at least half covered; the pane split lines
    and the background stay unlit. The green status bar under the screen is
    lit on a diagonal hatch ((x + y) % 3 == 0). Two fixes after the trace: the
    horizontal split runs straight to the right edge (the trace rounded its
    end off), and the screen's last row is full width, so the bar follows it
    with no notch. The logo is stretched to the square, as the committed mark
    always was. Drawn at the keycap size so the generator copies it 1:1."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    import io
    import urllib.request

    import numpy as np
    from PIL import Image
    req = urllib.request.Request(TMUX_ICON_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    icon = icon.crop(icon.getchannel("A").getbbox())
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    rgb = np.array(white.convert("RGB")).astype(int)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    green = (g > r + 50) & (g > b + 50)
    dark = (np.array(white.convert("L")) <= TMUX_DARK_LUMA) & ~green

    def cover(mask):
        img = Image.fromarray((mask * 255).astype("uint8"))
        return np.array(img.resize((px, px), Image.BOX)) / 255.0

    yy, xx = np.mgrid[0:px, 0:px]
    screen = cover(dark) >= 0.5
    bar = (cover(green) >= 0.5) & ~screen
    out = screen | (bar & ((xx + yy) % 3 == 0))
    # The horizontal split: the row of the right half that is unlit across.
    right = slice(px // 2 + 1, px - 1)
    for y in range(2, px - 2):
        if not out[y, right].any() and out[y - 1, right].all():
            out[y - 1, px - 1] = out[y + 1, px - 1] = True
    # The screen's last row (the row above the first bar row) is full width.
    last = max(y for y in range(px) if screen[y].sum() > px // 2)
    out[last, 0] = out[last, px - 1] = True
    a = Image.fromarray((out * 255).astype("uint8"))
    Image.merge("RGBA", (a, a, a, a)).save(dest)
    print(f"  {dest.name}  <- tmux logo, 1-bit trace with a hatched status bar")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    _tmux_mark(out / "tmux.png")
    for stem, (glyph, word) in COMPOSITES.items():
        emacs.composite(out / f"{stem}.png", glyph, word, out)
    panes(out)
    window_digits(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
