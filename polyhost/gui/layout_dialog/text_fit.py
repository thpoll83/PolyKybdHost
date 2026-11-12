"""Fit a (possibly multi-line) label into a rectangle by choosing its font size.

The keycode browser's buttons and the board's key tiles both show captions that
`create_nice_name` breaks into lines (`KC_MEDIA_PLAY_PAUSE` -> MEDIA / PLAY / PAUSE).
Each used to guess a size: the button measured the text as ONE line and stopped at
7 pt, and the tiles used `9 if len(main) < 5 else 7`. Both clipped long captions.
This picks the largest PIXEL size at which every line fits the width and all lines
fit the height. Pixel sizes, because a point size draws at a different pixel size on
Windows than on Linux and macOS, which the button used to correct by hand.
"""
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QFont, QFontMetricsF

# Far larger than any caption, so boundingRect never wraps or clips the measurement.
_MEASURE = QRectF(0, 0, 100000, 100000)


def text_size(font: QFont, text: str) -> tuple[float, float]:
    """(width, height) of `text` drawn in `font`, one line per `\\n`."""
    r = QFontMetricsF(font).boundingRect(_MEASURE, int(Qt.AlignCenter), text)
    return r.width(), r.height()


def fit_pixel_size(font: QFont, text: str, width: float, height: float,
                   max_px: int, min_px: int) -> int:
    """The largest pixel size in [min_px, max_px] at which `text` fits width x height.

    Returns `min_px` when even that does not fit, so the caller still gets a size;
    `fits_at()` says whether it does.
    """
    f = QFont(font)
    for px in range(max_px, min_px - 1, -1):
        f.setPixelSize(px)
        w, h = text_size(f, text)
        if w <= width and h <= height:
            return px
    return min_px


def fits_at(font: QFont, text: str, px: int, width: float, height: float) -> bool:
    f = QFont(font)
    f.setPixelSize(px)
    w, h = text_size(f, text)
    return w <= width and h <= height
