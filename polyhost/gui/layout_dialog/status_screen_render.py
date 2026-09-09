"""The status-OLED preview as a Qt image, for the editor's board plate.

The composition lives in `polyhost.services.status_screen`, which is Qt-free and
pixel-exact; this is the bridge that turns its lit pixels into a `QImage` and holds
the three faces it draws with, exactly as `MacroKeycapRenderer` does for a keycap.

⚠️ The panel simulation is applied with the **`oled`** preset, not `keycap`. There is
no keycap over a status display -- it is a bare panel behind a window -- so the
`keycap` preset's diffusion and jitter would model a light guide that is not there.
The keys and the screens therefore go through different presets on purpose, and both
come from `fontpack_render.apply_oled_style` so neither is a second set of numbers.
"""

from __future__ import annotations

from PyQt5.QtGui import QColor, QImage

from polyhost.services import status_screen as ss

#: The same ink the macro keycap renderer uses, so one board reads as one panel.
GROUND = QColor(8, 10, 14)
LIT = QColor(207, 231, 245)

#: Output pixels per OLED pixel. The simulation's grid, bloom and jitter are all
#: sized from it, so at 1 there is nothing to see -- the same reason the keycaps
#: render larger than their tile and let the view scale them down.
REAL_SCALE = 3


class StatusScreenRenderer:
    """Holds the faces; renders one 128x64 panel per call."""

    #: The faces `status_screen` draws with, by the name the export lists them under.
    MID = "NotoSans_Regular_Mid_19px7b"
    SMALL = "NotoSans_Regular_Small_15px7b"

    def __init__(self, faces=None):
        self._faces = faces or {}

    @classmethod
    def from_preview_data(cls, data):
        """Build from a loaded `PreviewData`, or return an unusable renderer.

        The icon face is found by COVERAGE rather than by name: IconsFont is the
        firmware's `g_all_fonts[0]` and the C1 band `0x80..0x9F` is its alone, so the
        first font covering `ICON_LAYER` is it -- and a renamed header cannot quietly
        cost the panel its layer icon.
        """
        if data is None or not getattr(data, "ok", False):
            return cls(None)
        icons = next((f for f in data.fonts
                      if f.first <= ss.ICON_LAYER <= f.last), None)
        ui = data.ui_fonts or {}
        return cls({"icons": icons, "mid": ui.get(cls.MID), "small": ui.get(cls.SMALL)})

    @property
    def usable(self) -> bool:
        """Whether anything would be drawn. False leaves the panel a flat rectangle.

        The layer digit is the element the preview exists for, so its face decides:
        without `_Small_` the name row and the side marker drop out and the screen
        still says which layer is selected, which is worth drawing.
        """
        return self._faces.get("mid") is not None

    def render(self, layer: int, layer_name: str, side: str) -> QImage:
        img = QImage(ss.PANEL_W, ss.PANEL_H, QImage.Format_RGB32)
        img.fill(GROUND)
        lit = LIT.rgb()
        for x, y in ss.render(layer, layer_name, side, self._faces):
            img.setPixel(x, y, lit)
        return img
