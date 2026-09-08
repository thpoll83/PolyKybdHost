"""Put a rendered keycap through the OLED simulation, as a Qt image.

The font-pack inspector has always been able to show a glyph the way the physical
panel shows it — cool-white emissive pixels, bloom, a staggered pixel grid and the
diffusion of the clear keycap cover. The keymap editor draws the same 72x40 keycaps
and had only the flat bitmap, so a layout could look right in the editor and read
differently on the board.

This is the Qt bridge to that model and nothing more: the LOOK lives in
`fontpack_render.apply_oled_style`, shared with the inspector so the two surfaces
cannot drift into different-looking previews of one panel.
"""

from __future__ import annotations

# The simulation is pure PIL/NumPy, both hard requirements — but a broken install
# must cost the picture, not the editor, so the caller asks `available()` and offers
# the mode only when it answers.
try:
    from PIL import Image as _Image
    _ERR = None
except Exception as e:                                  # pragma: no cover - install
    _Image = None
    _ERR = e


def available() -> bool:
    """Whether the simulation can run at all (Pillow present)."""
    return _Image is not None


def reason() -> str:
    """Why it cannot, for a tooltip. Empty when it can."""
    return "" if _Image is not None else f"Pillow is unavailable: {_ERR}"


def _to_pil_l(qimg):
    """QImage -> PIL 'L', honouring the row stride rather than assuming w == pitch."""
    from PyQt5.QtGui import QImage

    g = qimg.convertToFormat(QImage.Format_Grayscale8)
    ptr = g.constBits()
    ptr.setsize(g.byteCount())
    return _Image.frombuffer("L", (g.width(), g.height()), bytes(ptr),
                             "raw", "L", g.bytesPerLine(), 1)


def _to_qimage(pil):
    """PIL 'RGB' -> QImage, copied off the temporary buffer."""
    from PyQt5.QtGui import QImage

    if pil.mode != "RGB":
        pil = pil.convert("RGB")
    data = pil.tobytes("raw", "RGB")
    return QImage(data, pil.width, pil.height, 3 * pil.width,
                  QImage.Format_RGB888).copy()


def render(qimg, style: str = "keycap", scale: int = 3):
    """The keycap as the panel shows it, at `scale` output pixels per OLED pixel.

    ⚠️ `scale` is not cosmetic. The grid, the bloom radius and the per-pixel jitter are
    all sized from it, so at 1 there is nothing to see — the effect needs a logical
    pixel drawn at least ~3 px. The editor therefore renders LARGER than the tile and
    lets the view scale it down, which also means zooming in reveals more of the panel
    rather than a bigger flat bitmap.

    Returns None when the simulation is unavailable, so a caller falls back to the
    plain render instead of showing an empty key.
    """
    if _Image is None or qimg is None:
        return None
    from polyhost.services.fontpack_render import apply_oled_style

    src = _to_pil_l(qimg)
    if scale > 1:
        src = src.resize((src.width * scale, src.height * scale), _Image.NEAREST)
    return _to_qimage(apply_oled_style(src, style, scale))
