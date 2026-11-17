"""Captions under a keycap picture tile (gui/keyboard_settings.py TileChoice).

A QToolButton draws its text on one line, so a long caption under its picture
would widen the tile. :func:`wrap_caption` breaks it into at most two lines,
between words, or between characters for Chinese, Japanese and Korean.

The tray menu's tile grids that this module also held are gone: their choices
are in Settings > Keyboard and Settings > Brightness now.
"""
import unicodedata

from PyQt5.QtCore import Qt


def _is_wide(ch):
    """A Chinese, Japanese or Korean character: text in these scripts has no
    spaces, and a line may break between any two such characters."""
    return bool(ch) and unicodedata.east_asian_width(ch) in ("W", "F")


def _break_units(text, metrics, width):
    """The pieces a caption may break between, as ``(piece, glued)``: words,
    and each wide character on its own. ``glued`` marks a piece split out of
    the same word, which joins its neighbour without a space; a word keeps
    the space the text had before it. Without the split, a Japanese caption
    was one unbreakable word and was shortened even where it fits on two lines."""
    units = []
    for word in text.split():
        if any(_is_wide(c) for c in word) and metrics.horizontalAdvance(word) > width:
            pieces, run = [], ""
            for c in word:
                if _is_wide(c):
                    if run:
                        pieces.append(run)
                        run = ""
                    pieces.append(c)
                else:
                    run += c
            if run:
                pieces.append(run)
            units.extend((p, i > 0) for i, p in enumerate(pieces))
        else:
            units.append((word, False))
    return units


def wrap_caption(text, metrics, width, max_lines=2):
    """Break ``text`` into at most ``max_lines`` lines that fit ``width`` px.

    QToolButton draws its text on one line, so a long menu label under an icon
    would widen the tile. A word that does not fit is elided.
    """
    # The "…" that marks an entry opening a dialog reads as a cut-off word
    # under an icon.
    text = text.rstrip().rstrip("\u2026").rstrip(".").rstrip() if text.rstrip().endswith(("\u2026", "...")) else text
    lines, line = [], ""
    for word, glued in _break_units(text, metrics, width):
        candidate = f"{line}{'' if glued else ' '}{word}" if line else word
        if line and metrics.horizontalAdvance(candidate) > width:
            lines.append((line, glued))
            line = word
        else:
            line = candidate
    if line:
        lines.append((line, None))
    if len(lines) > max_lines:
        # Past the last line: join the rest back with the space (or none) the
        # text had at each break, and let the elision below shorten it.
        tail = lines[max_lines - 1][0]
        for (piece, _), (_, glued) in zip(lines[max_lines:], lines[max_lines - 1:]):
            tail += ("" if glued else " ") + piece
        lines = lines[:max_lines - 1] + [(tail, None)]
    lines = [ln for ln, _ in lines]
    return "\n".join(metrics.elidedText(ln, Qt.ElideRight, width) for ln in lines)
