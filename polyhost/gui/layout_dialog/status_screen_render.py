"""The status-OLED preview as a Qt image, for the editor's board plate.

The composition lives in `polyhost.services.status_screen`, which is Qt-free and
pixel-exact; this is the bridge that turns its lit pixels into a `QImage` and holds
the faces it draws with, exactly as `MacroKeycapRenderer` does for a keycap.

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

    #: The two standalone UI faces, by the name the export lists them under. The
    #: icon and globe faces are found by coverage instead -- see `from_preview_data`.
    MID = "NotoSans_Regular_Mid_19px7b"
    SMALL = "NotoSans_Regular_Small_15px7b"
    NANO = "NotoSans_Regular_Nano_10px7b"

    def __init__(self, faces=None):
        self._faces = faces or {}

    @classmethod
    def from_preview_data(cls, data):
        """Build from a loaded `PreviewData`, or return an unusable renderer.

        The icon and globe faces are found by COVERAGE rather than by name: IconsFont
        is the firmware's `g_all_fonts[0]` and the C1 band `0x80..0x9F` is its alone,
        and the World face is the only resident font covering U+1F310 -- so a renamed
        header cannot quietly cost the panel its layer icon.
        """
        if data is None or not getattr(data, "ok", False):
            return cls(None)

        def covering(cp):
            return next((f for f in data.fonts if f.first <= cp <= f.last), None)

        ui = data.ui_fonts or {}
        return cls({"icons": covering(ss.ICON_LAYER), "globe": covering(0x1F310),
                    "mid": ui.get(cls.MID), "small": ui.get(cls.SMALL),
                    "tiny": ui.get(cls.NANO)})

    @property
    def usable(self) -> bool:
        """Whether anything would be drawn. False leaves the panel a flat rectangle.

        The layer digit is the element the preview exists for, so its face decides:
        without the others a row drops out and the screen still says which layer is
        selected, which is worth drawing.
        """
        return self._faces.get("mid") is not None

    def render(self, side: str, layer: int, layout: str) -> QImage:
        """One panel. `side` is "left" (layout) or "right" (RGB), as on hardware."""
        img = QImage(ss.PANEL_W, ss.PANEL_H, QImage.Format_RGB32)
        img.fill(GROUND)
        lit = LIT.rgb()
        for x, y in ss.render(side, self._faces, layer=layer, layout=layout):
            img.setPixel(x, y, lit)
        return img
