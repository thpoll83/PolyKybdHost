"""Keycap previews for the tiled tray submenus (gui/menu_tiles.py).

Each tile is one 72x40 keycap panel, white on black as the OLED shows it,
drawn from data the host ships (the resident and font-pack faces through
``services/glyph_script_preview``), so no keyboard needs to be attached.

The idle and brightness tiles are sketches, not captures: the idle styles are
animations the firmware computes, and a sketch of each tells them apart.
"""

import random

from PIL import Image, ImageDraw
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon, QImage, QPixmap

from polyhost.services import fontpack_bundle
from polyhost.services import glyph_script_preview as gsp

PANEL_W, PANEL_H = 72, 40
SCALE = 2      # whole pixels per OLED pixel at 100 %


def tile_scale():
    """Whole pixels per OLED pixel at the display's scale (2 at 100 %, 3 at 150 %).

    A whole number keeps every OLED pixel square and sharp.
    """
    from polyhost.gui.ui_kit import ui_scale
    return max(SCALE, int(round(SCALE * ui_scale())))


def tile_size():
    s = tile_scale()
    return QSize(PANEL_W * s, PANEL_H * s)

# The bigger legend faces in latinbig.plyf: ASCII relocated to these bases
# (GlyphSize MEDIUM and LARGE). SMALL is the resident face.
_LATINBIG_BASE = {1: 0xF0000, 2: 0xF3000}

_SAMPLE = "A"


def _panel():
    return Image.new("L", (PANEL_W, PANEL_H), 0)


def _paste_centred(panel, img, dx=0, dy=0, level=255):
    if img is None:
        return panel
    img = img.convert("L")
    if img.width > PANEL_W - 4 or img.height > PANEL_H - 4:
        r = min((PANEL_W - 4) / img.width, (PANEL_H - 4) / img.height)
        img = img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))), Image.NEAREST)
    if level != 255:
        img = img.point(lambda v: v * level // 255)
    x = (PANEL_W - img.width) // 2 + dx
    y = (PANEL_H - img.height) // 2 + dy
    panel.paste(img, (x, y), img)
    return panel


def to_icon(panel):
    """A QIcon of the panel at tile size, scaled without smoothing."""
    s = tile_scale()
    big = panel.resize((PANEL_W * s, PANEL_H * s), Image.NEAREST).convert("RGB")
    qimg = QImage(big.tobytes(), big.width, big.height, big.width * 3,
                  QImage.Format_RGB888).copy()
    return QIcon(QPixmap.fromImage(qimg))


def _legend(text=_SAMPLE):
    """``text`` in the resident face, or None when the preview export is absent."""
    font = gsp.latin_font(gsp.load_resident())
    if font is None:
        return None
    cps = [ord(c) for c in text if font.first <= ord(c) <= font.last]
    return gsp.layout_image(font, cps) if cps else None


# ── Keycap Size ──────────────────────────────────────────────────────────────

def size_panels(values):
    """One panel per GlyphSize value: the sample legend at that size."""
    big = gsp._load(fontpack_bundle.res_dir() / "latinbig.plyf", "latinbig")
    out = []
    for value in values:
        img = None
        base = _LATINBIG_BASE.get(value)
        if base is None:
            img = _legend()
        elif big is not None:
            cp = base + ord(_SAMPLE)
            font = next((f for f in big.fonts if f.first <= cp <= f.last), None)
            if font is not None:
                img = gsp.layout_image(font, [cp])
        out.append(_paste_centred(_panel(), img))
    return out


# ── Keycap Script ────────────────────────────────────────────────────────────

def script_panel(value):
    """The script's sample, as the existing menu icon previews it."""
    return _paste_centred(_panel(), gsp.preview(value))


# ── Brightness ───────────────────────────────────────────────────────────────

def brightness_panel(level):
    """The legend at a brightness level, 0..50 as the firmware counts it.

    The OLED's perceived brightness is far from linear at the low end, so the
    grey is spread on a square-root curve: 1% must still read as "on".
    """
    if level <= 0:
        panel = _panel()
        ImageDraw.Draw(panel).rectangle((0, 0, PANEL_W - 1, PANEL_H - 1), outline=40)
        return panel
    grey = int(70 + 185 * (min(level, 50) / 50) ** 0.5)
    return _paste_centred(_panel(), _legend(), level=grey)


# ── Idle Display ─────────────────────────────────────────────────────────────

def idle_panel(style):
    """A sketch of an idle style (IdleStyle value: 0 pulse, 1 jitter, 2 iddqd, 3 eden)."""
    legend = _legend()
    panel = _panel()
    if style == 0:      # pulse: the legend fades in and out
        for dx, level in ((-14, 70), (0, 255), (14, 70)):
            _paste_centred(panel, legend, dx=dx, level=level)
    elif style == 1:    # jitter: the legend moves a few pixels at a time
        for dx, dy, level in ((-6, -4, 60), (-3, -2, 120), (2, 2, 255)):
            _paste_centred(panel, legend, dx=dx, dy=dy, level=level)
    elif style == 2:    # IDDQD: the attract demo takes over the keycaps
        _paste_centred(panel, _legend("IDDQD"))
    elif style == 3:    # eden: a comet field with the legend cut out
        draw = ImageDraw.Draw(panel)
        rnd = random.Random(3)
        for _ in range(40):
            x, y = rnd.randrange(PANEL_W), rnd.randrange(PANEL_H)
            n = rnd.randrange(4, 9)
            for i in range(n):
                draw.point((x - i, y - i // 2), fill=255 - i * 255 // n)
        if legend is not None:
            mask = legend.convert("L").point(lambda v: 255 if v else 0)
            hole = Image.new("L", mask.size, 0)
            x = (PANEL_W - mask.width) // 2
            y = (PANEL_H - mask.height) // 2
            panel.paste(hole, (x, y), mask)
    return panel
