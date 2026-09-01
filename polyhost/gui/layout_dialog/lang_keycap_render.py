"""Compose a language-layer flag keycap the way the firmware's
`render_lang_flag_key()` does -- the flag glyph filling the height, the "ll-CC" code
running vertically up the right edge.

Unlike every other keycap the editor previews, this one is not a display list: the
firmware composes it from two primitives at computed positions, so there is no
expression to hand the ordinary renderer. It is modelled here for the same reason
`macro_keycap_render` models `render_macro_key()`.

⚠️ It mirrors the firmware including the parts that look odd:

  * The flag draws through a SINGLE-font pool. `kdisp_write_gfx_char` baseline-aligns
    every glyph to `fonts[0]`, so drawing it through the whole ALL_FONTS pool adds
    `flag.yAdvance - IconsFont.yAdvance` = +14 px and pushes the flag's bottom rows off
    the keycap -- the gap-at-top regression from when flags moved into the font pack.
  * BOTH bearings are compensated (`x - xOffset`, `y - yOffset`) so the flag's CONTENT
    lands flush at the left edge whatever the glyph's own bearing is, and the glyph is
    centred vertically because it is taller than the 40 px keycap by design: the empty
    margins clip off and the flag fills the height.
  * The caption is rotated 90 degrees and advances UPWARD from the bottom, and a column
    longer than the panel is pulled up rather than centred -- otherwise a long code
    ("mn-MN") centres to a first glyph below the panel and vanishes entirely.

The firmware also inverts the caption bar for the ACTIVE language. That is deliberately
not modelled: which language is active is device state, and a static preview that picked
one would mark a key selected on every board.

⚠️ A preview that mirrors an implementation agrees with it by construction, so this
cannot catch a placement bug in the firmware -- only a divergence between the two. The
check with teeth is measuring drawn pixels against the 72x40 window.
"""

from __future__ import annotations

from PIL import Image

# From poly_keymap.c, beside render_lang_flag_key(), expressed relative to BUFFER_X.
#
# ⚠️ TWO coordinate frames meet in this file, and mixing them clips silently.
# `Renderer.draw()` takes a cursor in BUFFER coordinates (BUFFER_X == panel x 0) and
# hands its setpix PANEL coordinates; the plotting `_vtext` does itself is panel
# coordinates throughout. So the flag's cursor is `BUFFER_X + FLAG_LEFT_X_OFF` and the
# caption's column is `LABEL_COL_X_OFF` with no BUFFER_X -- adding it there puts the
# caption at x 87..94 of a 72-wide panel, where it is dropped by the clip and the
# keycap comes out looking like a flag the firmware simply draws without a label.
FLAG_LEFT_X_OFF = -2      # FLAG_LEFT_X = BUFFER_X - 2
LABEL_COL_X_OFF = 66      # LABEL_COL_X = BUFFER_X + 66


class LangKeycapRenderer:
    """Holds the loaded fonts; renders one 72x40 flag keycap per call."""

    def __init__(self, fonts, nano, oled_w: int, oled_h: int, buffer_x: int):
        self._fonts = fonts or []
        self._nano = nano
        self._w, self._h = oled_w, oled_h
        self._bx = buffer_x

    @property
    def usable(self) -> bool:
        return bool(self._fonts) and self._nano is not None

    def render(self, flag_cp: int, code: str):
        """The keycap, or None when the flag glyph is in no loaded font.

        None is the firmware's `else` branch -- no font pack, so it draws the code
        centred instead. That is not modelled: a firmware checkout always carries
        flag_fonts.h, so reaching it means something is wrong, and a bare keycode is a
        more honest answer than a legend for a state this board is not in.
        """
        if not self.usable:
            return None
        font = self._owning_font(flag_cp)
        if font is None:
            return None
        g = self._glyph(font, flag_cp)
        if g is None:
            return None

        img = Image.new("L", (self._w, self._h), 0)
        px = img.load()

        def sp(x, y):
            if 0 <= x < self._w and 0 <= y < self._h:
                px[x, y] = 255

        from tools.oled_preview import Renderer
        # Single-font pool: `fonts[0]` IS this font, so the baseline adjustment is 0.
        Renderer([font]).draw(sp, [flag_cp],
                              self._bx + FLAG_LEFT_X_OFF - g["xOffset"],
                              (self._h - g["height"]) // 2 - g["yOffset"])
        self._vtext(sp, code, LABEL_COL_X_OFF)
        return img

    # -- font lookup ---------------------------------------------------------

    def _owning_font(self, cp: int):
        """Front-to-back, the way the firmware scans `g_all_fonts`."""
        for f in self._fonts:
            if self._glyph(f, cp) is not None:
                return f
        return None

    @staticmethod
    def _glyph(font, cp: int):
        """The glyph record, or None for a codepoint outside the font or a GAP.

        A gap is `{off,0,0,0,0,0}` -- present in the contiguous table so the range
        stays whole, drawn by nothing, and fallen through to the next font.
        """
        if font is None or cp < font.first or cp > font.last:
            return None
        try:
            g = font.glyphs[cp - font.first]
        except IndexError:
            return None
        return None if g["width"] == 0 and g["height"] == 0 else g

    # -- kdisp_write_gfx_vtext ----------------------------------------------

    def _vtext(self, sp, text: str, col_x: int) -> None:
        """The caption, rotated 90 degrees, advancing upward from the bottom.

        `col_x` is PANEL-relative -- see the frame note by the constants above.

        Note the glyph bitmaps are COLUMN-NATIVE (OLED page format): one byte is 8
        vertical pixels, `cb` page-bytes per column, LSB at the top of the page. A
        row-major read produces noise that looks like dithering rather than an error.
        """
        glyphs = [g for g in (self._glyph(self._nano, ord(c)) for c in text) if g]
        total = sum(g["xAdvance"] for g in glyphs)
        if total <= 0:
            return
        top_y = (self._h - total) // 2
        if top_y + total > self._h - 1:          # a long code would start off-panel
            top_y = self._h - 1 - total
        vcur = top_y + total
        for g in glyphs:
            xo, yo, w, h = g["xOffset"], g["yOffset"], g["width"], g["height"]
            cb = (h + 7) >> 3 if h > 0 else 0
            for gy in range(h):
                base, vmsk = g["bitmapOffset"] + (gy >> 3), 1 << (gy & 7)
                for gx in range(w):
                    if self._nano.bitmap[base + gx * cb] & vmsk:
                        sp(col_x + yo + gy, vcur - xo - gx)
            vcur -= g["xAdvance"]
