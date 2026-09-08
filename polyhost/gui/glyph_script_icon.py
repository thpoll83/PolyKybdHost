"""Qt wrapper over the glyph-script previews — the menu-facing half.

`polyhost.services.glyph_script_preview` rasterises a sample of a script out of
the shipped `fantasy` bundle; this turns that into a `QIcon` for the tray's
Keycap Script entries and a rich-text tooltip carrying a bigger sample.

Two things decide how it looks, and both were chosen by rendering the real menu
rather than by reasoning about it (`tools/render_tray_menu.py`):

* **The icon is two glyphs, not the whole sample.**  A menu icon is drawn in a
  square roughly `PM_SmallIconSize` across (16 px on most styles), and `QIcon`
  scales a pixmap to *fit* — so a six-glyph strip arrives about five pixels tall
  and reads as a smudge.  Two glyphs at half the box height still read, and they
  are enough to tell the scripts apart at a glance; the tooltip carries the rest.
* **Lit pixels only, on transparency, in the PALETTE's ink.**  The background
  stays transparent so the menu's own colour shows through, and on a dark menu
  the ink is the OLED's cool white (`fontpack_render.OLED_TINT`) so the entry
  previews the keycap.  ⚠️ That is not a constant: the apps follow the OS theme
  now, and near-white ink on a light menu is an invisible icon — so a light
  palette draws the previews in its own text colour instead, and the tray drops
  the built icons when the theme changes (`PolyHost._refresh_theme`).
"""
from __future__ import annotations

import base64
import io

from PyQt5.QtGui import QIcon, QImage, QPalette, QPixmap
from PyQt5.QtWidgets import QApplication

from polyhost.gui.theme import is_dark
from polyhost.services import glyph_script_preview as gsp
from polyhost.services.fontpack_render import OLED_TINT

# What the icon draws (see the module docstring) and the sizes it is offered at.
# The ladder is for HiDPI: a menu at 150% asks for 24 px and would otherwise get
# a 16 px pixmap stretched.
ICON_SAMPLE = "ab"
ICON_SIZES = (16, 24, 32, 48)

# Tooltip sample height in pixels before integer upscaling — big enough to read a
# Tengwar descender, small enough not to cover the menu it hangs off.
TOOLTIP_HEIGHT = 34


def preview_ink():
    """The colour to draw a preview in, for the palette the app is wearing."""
    app = QApplication.instance()
    palette = app.palette() if app is not None else None
    if palette is None or is_dark(palette):
        return OLED_TINT
    colour = palette.color(QPalette.WindowText)
    return colour.red(), colour.green(), colour.blue()


def _tinted_rgba(img, tint=None):
    """PIL 'L' image -> RGBA: `tint` ink (the palette's, by default), alpha from
    the pixel value, so an unlit pixel is transparent rather than black and the
    menu's own colour shows."""
    from PIL import Image

    tint = tint or preview_ink()
    if img.mode != "L":
        img = img.convert("L")
    flat = [Image.new("L", img.size, c) for c in tint]
    return Image.merge("RGBA", (*flat, img))


def _tinted_pixmap(img, tint=None) -> QPixmap:
    """PIL 'L' image -> QPixmap with `tint` ink on transparency."""
    rgba = _tinted_rgba(img, tint)
    data = rgba.tobytes()
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format_RGBA8888)
    # fromImage copies, so the pixmap does not outlive `data`'s buffer.
    return QPixmap.fromImage(qimg)


def _fit_height(img, height: int, smooth: bool):
    """Scale `img` to `height`, keeping its aspect.  Smooth for a downscale (a
    nearest downscale drops whole stems out of a 1-bit face), nearest for an
    upscale (the pixel grid IS what the keycap shows)."""
    from PIL import Image

    if img.height == height:
        return img
    width = max(1, round(img.width * height / img.height))
    resample = Image.LANCZOS if smooth else Image.NEAREST
    return img.resize((width, height), resample)


def preview_image(script_value: int, sample: str = None):
    """The PIL preview for a script (STANDARD included — it previews the normal
    Latin face), or None when the shipped data cannot draw it."""
    return gsp.preview(script_value, sample)


def glyph_script_icon(script_value: int, sample: str = ICON_SAMPLE,
                      sizes=ICON_SIZES) -> QIcon | None:
    """A menu icon previewing `script_value`, or None for a script the shipped
    pack does not carry (the caller then keeps its own icon)."""
    img = preview_image(script_value, sample)
    if img is None:
        return None
    icon = QIcon()
    for size in sizes:
        icon.addPixmap(_tinted_pixmap(_fit_height(img, size, smooth=size < img.height)))
    return icon


def glyph_script_tooltip(script_value: int, height: int = TOOLTIP_HEIGHT) -> str | None:
    """Rich-text tooltip showing the full sample (letters, plus digits for the
    scripts that have numerals), or None when there is no preview.

    The image rides in the HTML as a base64 ``data:`` URI — Qt's rich text loads
    those, so this needs no temp file to point at and nothing to clean up.
    """
    img = preview_image(script_value)
    if img is None:
        return None
    scale = max(1, round(height / img.height))
    img = _fit_height(img, img.height * scale, smooth=False)
    buf = io.BytesIO()
    _tinted_rgba(img).save(buf, "PNG")
    uri = base64.b64encode(buf.getvalue()).decode("ascii")
    return f'<img src="data:image/png;base64,{uri}">'
