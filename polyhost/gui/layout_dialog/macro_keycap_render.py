"""Compose a macro keycap the way the firmware's `render_macro_key()` does.

Lifted out of `MacroTab` unchanged so a SECOND surface can draw the same keycap: the
keymap editor paints it onto the key tile, where a macro key otherwise reads `MACRO(3)`
— sixteen keys that say "this is a macro" and nothing about which one, which is the
exact problem the on-keycap caption exists to solve.

The fonts are loaded once and held here; everything that varies per keycap (caption,
style, icon codepoint, macro index) is an argument. That split is the whole point of the
extraction — the old code read them off the tab's widgets, so nothing else could call it.

⚠️ This mirrors firmware behaviour, including the parts that look like bugs: the mark is
HALVED when a captioned key leaves too few rows, a missing icon glyph falls back to the
index rather than drawing nothing, and glyphs are plotted through their OWN font because
`kdisp_write_gfx_char` baseline-aligns to `fonts[0]`. Change it only alongside
`poly_keymap.c`, and re-check with `tools/macro_label_preview.py --check`.
"""

from __future__ import annotations

from PyQt5.QtGui import QColor, QImage

from polyhost.device.command_ids import MacroStyle
from polyhost.services import macro_look as mk
from polyhost.services import macro_label as ml


class MacroKeycapRenderer:
    """Holds the loaded fonts; renders one 72x40 keycap per call."""

    def __init__(self, fonts, nano, mid, ladder):
        self._fonts = fonts or []
        self._font = nano          # the caption face
        self._mid = mid            # the fallback "M3" face
        self._ladder = ladder or []
        self._icon = 0
        self._index = 0

    @property
    def usable(self) -> bool:
        """False when no font loaded -- the caller should fall back to plain text."""
        return self._font is not None

    def render(self, label: str, style: int, icon: int = 0, index: int = 0) -> QImage:
        """Draw the keycap the way render_macro_key() composes it, for this style."""
        self._icon, self._index = icon, index
        img = QImage(ml.PANEL_W, ml.PANEL_H, QImage.Format_RGB32)
        img.fill(QColor(8, 10, 14))
        lit = QColor(207, 231, 245).rgb()

        if style == MacroStyle.TEXT.value and label and self._ladder:
            plan = mk.plan_caption(label, self._ladder)
            if plan is not None:
                fonts, base, box, _name = plan
                self._plot(img, label, fonts, base, lit,
                           x0=(ml.PANEL_W - (box[1] - box[0] + 1)) // 2 - box[0],
                           baseline=(ml.PANEL_H - (box[3] - box[2] + 1)) // 2 - box[2])
                return img
            # Nothing on the ladder fits: the firmware falls through to a captioned
            # style rather than drawing an empty keycap, so the preview does too.

        mark, mark_fonts, mark_base, mark_glyph = self._mark(style)
        # ICON_ONLY draws the icon alone in the whole cell -- the caption is kept in
        # storage but not drawn, so it takes the same branch an uncaptioned key does.
        # A missing glyph leaves mark_glyph None and falls back to the captioned index.
        if style == MacroStyle.ICON_ONLY.value and mark_glyph is not None:
            label = ""
        if not label:
            if mark and mark_fonts:
                box = mk.bbox(mark, mark_fonts, mark_base)
                if box:
                    self._plot(img, mark, mark_fonts, mark_base, lit,
                               x0=(ml.PANEL_W - (box[1] - box[0] + 1)) // 2 - box[0],
                               baseline=(ml.PANEL_H - (box[3] - box[2] + 1)) // 2 - box[2])
            return img

        cap = mk.bbox(label, [self._font], 0)
        if cap is None:
            return img
        cap_base = ml.PANEL_H - 1 - cap[3]
        free_rows = cap_base + cap[2]
        self._plot(img, label, [self._font], 0, lit,
                   x0=(ml.PANEL_W - (cap[1] - cap[0] + 1)) // 2 - cap[0],
                   baseline=cap_base)

        if mark and mark_fonts:
            drawn = self._draw_mark(img, lit, mark, mark_fonts, mark_base,
                                    free_rows, mark_glyph)
            if not drawn and mark_glyph is not None:
                # An icon that fits at no size falls back to the index, which always
                # does -- the same fallback a missing glyph takes, so an icon can
                # never leave the keycap without a mark.
                idx, idx_fonts, idx_base, _ = self._index_mark()
                if idx and idx_fonts:
                    self._draw_mark(img, lit, idx, idx_fonts, idx_base, free_rows, None)
        return img

    def _draw_mark(self, img: QImage, lit: int, mark: str, fonts, base: int,
                   free_rows: int, glyph) -> bool:
        """Place the mark in the rows the caption left; report whether it landed.

        Mirrors draw_macro_mark() in poly_keymap.c, including the HALVING: a pack
        emoji renders at 40 px while a captioned key leaves about 29 rows, so drawing
        only at native size showed NOTHING for four picker icons out of five -- and
        because this preview mirrors the firmware, it was silent on both ends.
        """
        box = mk.bbox(mark, fonts, base)
        if box is None:
            return False
        h = box[3] - box[2] + 1
        if h < free_rows:
            self._plot(img, mark, fonts, base, lit,
                       x0=(ml.PANEL_W - (box[1] - box[0] + 1)) // 2 - box[0],
                       baseline=(free_rows - h) // 2 - box[2])
            return True
        if glyph is None:      # text marks (the index) are never rescaled
            return False
        hw, hh = (glyph["width"] + 1) // 2, (glyph["height"] + 1) // 2
        if hh >= free_rows:
            return False
        self._plot_half(img, fonts[0], glyph, lit,
                        x=(ml.PANEL_W - hw) // 2, y=(free_rows - hh) // 2)
        return True

    def _index_mark(self):
        """The fallback mark: "M3" in the mid face, which fits any caption."""
        if self._mid is None:
            return "", [], 0, None
        return f"M{self._index}", [self._mid], 0, None

    def _mark(self, style):
        """What goes above the caption: a chosen glyph, or the macro's index.

        An icon the keyboard has no glyph for falls back to the index, exactly as the
        firmware does -- so a choice made against a richer font pack still names its
        macro here rather than drawing nothing. The glyph comes back too, because a
        tall one is drawn at half size (see _draw_mark).
        """
        if style in (MacroStyle.ICON.value, MacroStyle.ICON_ONLY.value) and self._icon:
            hit = mk.find_glyph(self._fonts, self._icon)
            if hit is not None:
                # Through the glyph's OWN font: kdisp_write_gfx_char baseline-aligns to
                # fonts[0], so drawing a tall pack glyph through the whole pool shifts
                # it down by the difference (the language-flag gap-at-top regression).
                return chr(self._icon), [hit[0]], 0, hit[1]
        return self._index_mark()

    def _plot(self, img: QImage, text: str, fonts, base: int, lit: int,
              x0: int, baseline: int):
        x = x0
        for ch in text:
            hit = mk.find_glyph(fonts, ord(ch) + base)
            if hit is None:
                continue
            f, g = hit
            bo, cb = g["bitmapOffset"], (g["height"] + 7) >> 3   # column-native
            for xx in range(g["width"]):
                col = bo + xx * cb
                for yy in range(g["height"]):
                    if f.bitmap[col + (yy >> 3)] & (1 << (yy & 7)):
                        vx, vy = x + g["xOffset"] + xx, baseline + g["yOffset"] + yy
                        if 0 <= vx < ml.PANEL_W and 0 <= vy < ml.PANEL_H:
                            img.setPixel(vx, vy, lit)
            x += g["xAdvance"]

    def _plot_half(self, img: QImage, font, g, lit: int, x: int, y: int):
        """2x2-OR downsample at a literal top-left -- kdisp_draw_glyph_half_at().

        OR rather than decimation because it keeps thin strokes a sampled downscale
        drops, and the halved extents round UP or an odd-width glyph loses its last
        column.
        """
        bo, w, h = g["bitmapOffset"], g["width"], g["height"]
        cb = (h + 7) >> 3                                   # column-native
        for dy in range((h + 1) // 2):
            for dx in range((w + 1) // 2):
                on = False
                for oy in range(2):
                    for ox in range(2):
                        sx, sy = dx * 2 + ox, dy * 2 + oy
                        if sx >= w or sy >= h:
                            continue
                        if font.bitmap[bo + sx * cb + (sy >> 3)] & (1 << (sy & 7)):
                            on = True
                            break
                    if on:
                        break
                if on and 0 <= x + dx < ml.PANEL_W and 0 <= y + dy < ml.PANEL_H:
                    img.setPixel(x + dx, y + dy, lit)

