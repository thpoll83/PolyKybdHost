"""Render the keycap the KEYBOARD draws, for any keycode, for the layout editor.

The macro renderer beside this one composes the one keycap the host itself owns.
Everything else on a keycap is composed by the FIRMWARE, from two sources this
module drives rather than reimplements:

- `tools/oled_preview.py` -- the language LUT (`lang_lut.xlsx`): letters, digits and
  the punctuation row, per language, including the shift and AltGr previews. It
  already mirrors `render_key()` in `poly_keymap.c` coordinate for coordinate.
- `tools/lang_demo.py` -- `keycode_helper.c`'s static-text switch, i.e. every key
  whose legend is a fixed mini display list: modifiers, arrows, Esc/Tab/Enter, the
  layer keys, the custom PolyKybd keycodes.

⚠️ Both read the FIRMWARE checkout beside this repo (`macro_label.default_font_dir`
resolves the same way), and the LUT needs `openpyxl` to open the .xlsx. Neither
ships with the host, so on an ordinary install `usable` is False and the editor
keeps drawing keycode text -- exactly what it did before previews existed. This is
the same limitation the macro keycap preview already has; it is not new here.

⚠️ These are a PYTHON MODEL of the C and can drift from it. That is the standing
caveat on `oled_preview.py` and `glyph_size_preview.py`, and it applies with more
force here because the editor shows the result as if it were the keyboard. When a
legend looks wrong, check the firmware source before believing the picture.
"""

from __future__ import annotations

import logging
import os
import sys

from PyQt5.QtGui import QImage

from polyhost.services import macro_label as ml

# The editor's tile shows the resting legend, so no modifier is held.
DEFAULT_LANG = "en-US"
KC_TRANSPARENT = 0x0001
KC_NO = 0x0000


def _tools_dir() -> str:
    """<repo>/tools -- four levels up from polyhost/gui/layout_dialog/<this file>.

    ⚠️ Count them: layout_dialog -> gui -> polyhost -> repo. Three lands on
    `polyhost/` and yields `polyhost/tools`, which does not exist -- and the import
    then fails so fast that `usable` reads False in 0.00 s, i.e. exactly like a
    machine with no firmware checkout.
    """
    here = os.path.abspath(__file__)
    for _ in range(4):
        here = os.path.dirname(here)
    return os.path.join(here, "tools")


class KeycapPreview:
    """Keycode -> the 72x40 keycap, or None when this keycode has no preview.

    Everything is loaded on FIRST USE, not at construction: opening the workbook and
    the font headers costs about a second, and the editor must not pay that when the
    toggle is off or the firmware checkout is absent.
    """

    def __init__(self, lang: str = DEFAULT_LANG):
        self.log = logging.getLogger("Preview")
        self._lang = lang
        self._loaded = False
        self._ok = False
        self._op = self._ld = self._L = self._R = None
        self._static: dict = {}

    # -- loading ------------------------------------------------------------

    def _load(self):
        if self._loaded:
            return self._ok
        self._loaded = True
        try:
            tools = _tools_dir()
            if tools not in sys.path:
                sys.path.insert(0, tools)
            import oled_preview as op
            import lang_demo as ld
            from gfx_font import load_all_fonts

            fonts_dir = ml.default_font_dir()                  # <fw>/base/fonts
            pk = os.path.dirname(os.path.dirname(fonts_dir))   # <fw>/keyboards/polykybd
            named = op.load_named_glyphs(os.path.join(pk, "lang", "named_glyphs.h"))
            # keycode_helper.h carries the names the static-text switch returns; without
            # it those legends resolve to nothing and the key silently renders blank.
            named.update(op.load_named_glyphs(os.path.join(pk, "keycode_helper.h")))
            self._L = op.Lang(os.path.join(pk, "lang", "lang_lut.xlsx"), named)
            self._R = op.Renderer(load_all_fonts(fonts_dir))
            self._static = ld.parse_static_text_map(os.path.join(pk, "keycode_helper.c"))
            self._op, self._ld = op, ld
            self._ok = True
        except Exception as e:
            self.log.debug("keycap previews unavailable (%s: %s)", type(e).__name__, e)
            self._ok = False
        return self._ok

    @property
    def usable(self) -> bool:
        return self._load()

    @property
    def languages(self) -> list:
        return list(self._L.langs) if self._load() else []

    def set_language(self, lang: str) -> bool:
        """Point the LUT at another layout. False when the keyboard names one this
        firmware's spreadsheet does not have, so the caller can keep the old one
        rather than render every letter blank."""
        if not self._load() or lang not in self._L.langs:
            return False
        self._lang = lang
        return True

    # -- rendering ----------------------------------------------------------

    def render(self, keycode: int, name: str | None) -> QImage | None:
        """The keycap for `keycode`, whose keymap token is `name`, or None.

        `name` comes from the browser's keycode->name mapping rather than being
        derived here: that table is what the editor already labels tiles from, so a
        keycode it cannot name is one the editor cannot preview either.
        """
        if not self._load() or not name:
            return None
        kc = self._ld.normalize_kc(name)
        try:
            if kc in self._op.ROW:
                img = self._op.render_key(self._L, self._R, self._lang, kc,
                                          shift=False, caps=False)
            else:
                expr = self._static.get(kc)
                if expr is None:
                    return None
                img = self._ld.render_static(self._L, self._R, expr)
        except Exception as e:
            self.log.debug("no preview for %s (%s: %s)", kc, type(e).__name__, e)
            return None
        return self._to_qimage(img)

    @staticmethod
    def _to_qimage(img) -> QImage | None:
        """PIL 'L' -> QImage, cropping oled_preview's overshoot border.

        ⚠️ oled_preview renders OVERSHOOT px BEYOND the panel deliberately, so a glyph
        the hardware would clip is visible in its contact sheets. The editor wants the
        hardware view, so the border is cropped rather than shown.
        """
        try:
            from tools.gfx_font import OLED_W, OLED_H
        except Exception:
            OLED_W, OLED_H = ml.PANEL_W, ml.PANEL_H
        # Centred crop rather than a fixed 2 px: OVERSHOOT is oled_preview's constant,
        # not ours, so the border is derived from the size difference and a future
        # change to it needs no edit here.
        if img.size != (OLED_W, OLED_H):
            bw = (img.size[0] - OLED_W) // 2
            bh = (img.size[1] - OLED_H) // 2
            if bw >= 0 and bh >= 0:
                img = img.crop((bw, bh, bw + OLED_W, bh + OLED_H))
        if img.mode != "L":
            img = img.convert("L")
        w, h = img.size
        out = QImage(w, h, QImage.Format_RGB32)
        out.fill(0xFF08_0A0E & 0xFFFFFFFF)
        lit = 0xFFCF_E7F5 & 0xFFFFFFFF
        px = img.load()
        for y in range(h):
            for x in range(w):
                if px[x, y]:
                    out.setPixel(x, y, lit)
        return out
