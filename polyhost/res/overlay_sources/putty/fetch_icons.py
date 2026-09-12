#!/usr/bin/env python3
"""Fetch + render the PuTTY session shortcut icons (reproducible source step).

⚠️ READ THIS BEFORE EDITING THE BINDINGS. PuTTY itself handles almost NO
keystrokes -- it is a terminal, so essentially everything you press is sent to
the remote host. Its own set is two entries (Alt+Enter full screen, Ctrl+right
-click menu), which is not an overlay.

So this overlay is deliberately of the **remote shell's** line editing, i.e.
GNU readline in emacs mode plus the tty driver's own control characters. That
is what a person sitting in a PuTTY window is actually pressing, and it is the
class of shortcut nobody memorises: Ctrl+A is not "select all" here, it is
beginning-of-line. The bindings file says so at the top and SOURCES.md explains
where each came from.

Style route: **Microsoft Fluent UI System Icons (MIT)** via `icon_fetch`. Three
line-editing glyphs are drawn here, because a general UI icon set has nothing
for "kill to end of line" and the nearest candidates all say "delete file". The
ESC **program mark** is NOT baked here -- it comes from the curated generic
`mdi:console-network` (`polyhost/res/app_icons.yaml`). ⚠️ It replaced a drawn
monitor-with-a-block-cursor chosen to be DISTINCT from the Windows Terminal
overlay's framed `>_`, and the two generics sit closer together than those two
did: `mdi:console` and `mdi:console-network` are both a `>_`. Taken knowingly --
one is framed, the other carries a network node -- but if the two terminal
overlays ever become hard to tell apart on a keycap, this is why.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/putty/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    # movement
    "linestart":  "Arrow Previous",
    "lineend":    "Arrow Next",
    "charback":   "Arrow Left",
    "charfwd":    "Arrow Right",
    "wordback":   "Skip Back 10",
    "wordfwd":    "Skip Forward 10",
    # history
    "prevcmd":    "Arrow Up",
    "nextcmd":    "Arrow Down",
    "searchback": "Search",
    "searchfwd":  "History",
    "lastarg":    "Arrow Hook Up Left",
    "revertline": "Arrow Undo",
    # editing
    "delchar":    "Backspace",
    "yank":       "Clipboard Paste",
    "transpose":  "Arrow Swap",
    "upcase":     "Text Case Uppercase",
    "downcase":   "Text Case Lowercase",
    "capitalize": "Text Case Title",
    "undo":       "Arrow Undo",
    "complete":   "Text Position Line",
    # screen / signals
    "clear":      "Broom",
    "interrupt":  "Stop",
    "suspend":    "Pause",
    "eof":        "Sign Out",
    "fullscreen": "Full Screen Maximize",
}


def _canvas(ss: int = 4, px: int = 96):
    u = px * ss
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), u


# ⚠️ The kill glyphs are laid out in KEYCAP PIXELS, not in fractions of some
# canvas, because the thing that goes wrong here is a COLLISION and a collision
# happens at the final size. The binding's region is [40, 36] with `margin: 0`
# and `fit: contain`, so a `_KILL_CELL`-sized canvas maps 1:1 onto what the
# keyboard draws and the numbers below are directly checkable against a render.
# Sized by eye in canvas fractions, the cursor's right edge and the X's left
# stroke CAP overlapped and the two merged into one blob at 40 px.
_KILL_CELL = (40, 36)
_KILL_SS = 8                 # supersample; the save downscales to 4x the cell

_BAR_THICK = 5               # the surviving text run
_CARET_W, _CARET_H = 3, 28   # the block cursor
_X_HALF, _X_STROKE = 8.5, 4  # the bold X over what goes


def _kill_glyph_at(path: Path, *, bar, caret_x, x_centre, flip: bool) -> None:
    """Draw one text run, a block cursor and a bold X over the part that goes.

    Every x is in cell pixels (0..40); `bar` is (x0, x1) of the SURVIVING text.
    `flip` mirrors the finished glyph, which is exactly the difference between
    each pair of shortcuts -- Ctrl+K vs Ctrl+U, Ctrl+W vs Alt+D -- so the two
    can never drift apart by a stray coordinate.
    """
    cw, ch = _KILL_CELL
    w, h = cw * _KILL_SS, ch * _KILL_SS
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    mid = h / 2
    d.line([(bar[0] * _KILL_SS, mid), (bar[1] * _KILL_SS, mid)],
           fill=white, width=_BAR_THICK * _KILL_SS)
    d.rectangle([(caret_x - _CARET_W / 2) * _KILL_SS, mid - _CARET_H / 2 * _KILL_SS,
                 (caret_x + _CARET_W / 2) * _KILL_SS, mid + _CARET_H / 2 * _KILL_SS],
                fill=white)
    cx, half, stroke = x_centre * _KILL_SS, _X_HALF * _KILL_SS, _X_STROKE * _KILL_SS
    d.line([(cx - half, mid - half), (cx + half, mid + half)], fill=white, width=stroke)
    d.line([(cx - half, mid + half), (cx + half, mid - half)], fill=white, width=stroke)
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    img.resize((cw * 4, ch * 4), Image.LANCZOS).save(path)


# kept | cursor | killed   -- the line kills take everything past the cursor
_KILL_LINE = dict(bar=(0, 11), caret_x=15, x_centre=29)
# kept | killed | cursor   -- a word kill takes the word ADJACENT to the cursor
_KILL_WORD = dict(bar=(0, 9), caret_x=38, x_centre=23)


def _kill_glyph(path: Path, *, to_end: bool) -> None:
    """`Ctrl+K` kill-to-end / `Ctrl+U` kill-to-start.

    ⚠️ Drawn rather than sourced. Every Fluent candidate reads as delete-*file*
    or clear-*formatting*; what has to be visible here is WHICH SIDE of the
    cursor goes -- the two shortcuts differ in nothing else. Same reasoning as
    the Notepad++ overlay's own delete-line glyph.

    ⚠️ The first version struck the killed run through with a DIAGONAL LINE and
    was rejected after rendering it at keycap size: the strike and the cursor
    are both thin strokes at 40 px, so the pair read as abstract crossed lines
    and Ctrl+K vs Ctrl+U were near-indistinguishable. A bold X survives the
    1-bit downscale and says "gone" on its own.

    ⚠️ Two other compositions were rendered and rejected for reasons that are
    invisible from the source: a FULL-WIDTH run with the X laid over its killed
    half (the run draws straight through the X and the two merge), and cursor +
    a large X with no kept run at all -- the boldest of the three, but with no
    kept text it cannot express the WORD kills, which need exactly that
    contrast. The family has to share one grammar to stay tellable apart.
    """
    _kill_glyph_at(path, flip=not to_end, **_KILL_LINE)


def _draw_killword(path: Path, *, forward: bool) -> None:
    """`Ctrl+W` kill the word before the cursor / `Alt+D` the word after it.

    Same three pieces as the line kills with the cursor at the far side, so the
    four read as one family: `-|X` / `X|-` take the rest of the line, `-X|` /
    `|X-` take one adjacent word.
    """
    _kill_glyph_at(path, flip=forward, **_KILL_WORD)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)

    # ⚠️ Guarded so a re-run never clobbers a hand-tuned glyph.
    drawn = (("killtoend", lambda p: _kill_glyph(p, to_end=True), "kill to end of line"),
             ("killtostart", lambda p: _kill_glyph(p, to_end=False), "kill to start of line"),
             ("killword", lambda p: _draw_killword(p, forward=False),
              "kill the word before the cursor"),
             ("killwordfwd", lambda p: _draw_killword(p, forward=True),
              "kill the word after the cursor"))
    for name, fn, what in drawn:
        p = out / f"{name}.png"
        if p.exists():
            print(f"  {name}.png  <- committed asset (left as-is)")
        else:
            fn(p)
            print(f"  {name}.png  <- custom (drawn: {what})")
        n += 1

    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
