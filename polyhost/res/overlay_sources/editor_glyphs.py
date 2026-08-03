#!/usr/bin/env python3
"""Custom-drawn glyphs for **text-editor** overlays.

Multiple cursors are the defining feature of a modern editor (Sublime's
`Ctrl+D` / `Ctrl+Alt+Up` / `Ctrl+Alt+Down`), and no general UI icon set draws
them — the nearest Fluent glyphs read as "select all" or a plain text cursor,
which is exactly the wrong idea. `delete_line` is here for the reason the
Notepad++ set drew its own: a trash can reads as delete-*file*.

All are **white on transparent** at 96x96 -> render with `mode: alpha`.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PX = 96
SS = 4
WHITE = (255, 255, 255, 255)


def _canvas():
    u = PX * SS
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), u


def _save(img: Image.Image, path: Path) -> None:
    img.resize((PX, PX), Image.LANCZOS).save(path)


def _rows(d, u, ys, x0=0.10, x1=0.72):
    """Text rows: the 'document' the cursors sit in."""
    w = int(u * 0.055)
    for y in ys:
        d.rectangle([int(u * x0), int(u * y), int(u * x1), int(u * y) + w], fill=WHITE)


def _caret(d, u, x, y0, y1):
    """An I-beam text cursor at x spanning y0..y1."""
    t, arm = int(u * 0.030), int(u * 0.075)
    d.rectangle([x - t, int(u * y0), x + t, int(u * y1)], fill=WHITE)
    for y in (int(u * y0), int(u * y1) - t * 2):
        d.rectangle([x - arm, y, x + arm, y + t * 2], fill=WHITE)


def multicursor(path: Path) -> None:
    """Two rows, each carrying its own cursor — add next occurrence."""
    img, d, u = _canvas()
    _rows(d, u, (0.20, 0.62), x0=0.06, x1=0.60)
    _caret(d, u, int(u * 0.76), 0.10, 0.36)
    _caret(d, u, int(u * 0.76), 0.52, 0.78)
    _save(img, path)


def _cursor_dir(path: Path, up: bool) -> None:
    img, d, u = _canvas()
    _rows(d, u, (0.30, 0.56, 0.82), x0=0.06, x1=0.62)
    _caret(d, u, int(u * 0.80), 0.44, 0.70)
    # the direction the new cursor is added in
    cx = int(u * 0.80)
    h, t = int(u * 0.090), int(u * 0.030)
    if up:
        d.rectangle([cx - t, int(u * 0.06), cx + t, int(u * 0.30)], fill=WHITE)
        d.polygon([(cx, int(u * 0.00)), (cx - h, int(u * 0.14)), (cx + h, int(u * 0.14))], fill=WHITE)
    else:
        d.rectangle([cx - t, int(u * 0.74), cx + t, int(u * 0.94)], fill=WHITE)
        d.polygon([(cx, u), (cx - h, int(u * 0.88)), (cx + h, int(u * 0.88))], fill=WHITE)
    _save(img, path)


def cursor_above(path: Path) -> None:
    """Add a cursor on the line above."""
    _cursor_dir(path, up=True)


def cursor_below(path: Path) -> None:
    """Add a cursor on the line below."""
    _cursor_dir(path, up=False)


def delete_line(path: Path) -> None:
    """Text rows with a strike through — delete *line*, not delete *file*.

    The strike is DIAGONAL: a horizontal one lands on the middle row and the two
    merge into a single longer row once downscaled, so the glyph reads as three
    lines of text with nothing struck at all.
    """
    img, d, u = _canvas()
    _rows(d, u, (0.24, 0.48, 0.72), x0=0.12, x1=0.76)
    d.line([(int(u * 0.06), int(u * 0.82)), (int(u * 0.90), int(u * 0.14))],
           fill=WHITE, width=int(u * 0.070))
    _save(img, path)


def select_line(path: Path) -> None:
    """One row highlighted out of three — select line."""
    img, d, u = _canvas()
    _rows(d, u, (0.18, 0.76), x0=0.10, x1=0.72)
    d.rounded_rectangle([int(u * 0.06), int(u * 0.40), int(u * 0.88), int(u * 0.62)],
                        radius=int(u * 0.045), fill=WHITE)
    _save(img, path)


ALL = {
    "multicursor": multicursor,
    "cursorabove": cursor_above,
    "cursorbelow": cursor_below,
    "deleteline": delete_line,
    "selectline": select_line,
}


def draw_all(out_dir: Path, names: list[str] | None = None) -> int:
    """Draw the named glyphs (default: all). Never clobbers a committed file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    picked = names or list(ALL)
    for n in picked:
        p = out_dir / f"{n}.png"
        if p.exists():
            print(f"  {n}.png  <- committed asset (left as-is)")
            continue
        ALL[n](p)
        print(f"  {n}.png  <- custom (drawn: editor_glyphs.{n})")
    return len(picked)
