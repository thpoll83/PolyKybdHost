"""The keycaps whose legend the FIRMWARE BUILDS AT RUNTIME, resolved for a resting board.

Most keycaps carry a legend the firmware writes down as a display list, which
`lang_demo.parse_static_text_map` / `parse_to_static_text_map` read straight out of the
C. A hundred-odd do not: the emoji layer's category tabs and slots, and the language
layer's region tabs and slots, are computed from an index into a static table plus the
layer's own paging state. There is no expression to parse, so the editor drew a bare
keycode for them -- 94 keys of two whole layers, the two layers a person is most likely
to be looking at when they open the editor.

They ARE knowable, because the tables are static C and the paging state at rest is
known: a board comes up on emoji category 0 page 0 and language region 0 page 0
(`s_category` / `s_page` / `s_region` in emoji_layer.c and lang_layer.c). This module
parses those tables and answers "what does slot N show on a keyboard nobody has touched
yet".

⚠️ What it deliberately does NOT answer is the MRU rows (`EMRU(n)` / `LMRU(n)`). Those
hold whatever that particular keyboard was last used for; there is no resting value to
resolve, and inventing one would put a specific emoji on a key that is empty on a fresh
board. Those keep their keycode text, which is honest.

Qt-free and offline: it reads the firmware checkout and nothing else.
"""

from __future__ import annotations

import os
import re

# Mirrored from the firmware, with the header each one lives in named so a change
# there is findable from here. These are small and stable; parsing them out of C
# would cost more than it protects.
EMJ_SLOTS_PER_PAGE = 50      # emoji/emoji_layer.h
LANG_SLOTS_PER_PAGE = 38     # lang_layer.h  (split42 overrides to 18 in its config.h)
FLAG_CP_BASE = 0xE000        # poly_keymap.c -- one flag glyph per language index


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _u32_array(text: str, name: str) -> list[int] | None:
    """The integer literals of a `... name[] = { ... };` initialiser."""
    m = re.search(r"\b" + re.escape(name) + r"\s*\[[^\]]*\]\s*=\s*\{(.*?)\}\s*;",
                  text, re.S)
    if not m:
        return None
    return [int(v, 0) for v in re.findall(r"0[xX][0-9a-fA-F]+|\d+", m.group(1))]


def _u_strings(text: str, name: str) -> list[str] | None:
    """The `U"..."` literals of an initialiser, in order."""
    m = re.search(r"\b" + re.escape(name) + r"\s*\[[^\]]*\]\s*=\s*\{(.*?)\}\s*;",
                  text, re.S)
    if not m:
        return None
    return re.findall(r'U"((?:[^"\\]|\\.)*)"', m.group(1))


class RuntimeLegends:
    """Resting-state answers for the emoji and language layers.

    `usable` is False when the firmware sources are missing or a table could not be
    read; every accessor then returns None, so a caller degrades to keycode text
    rather than to a wrong glyph.
    """

    def __init__(self):
        self.usable = False
        self.reason = "not loaded"
        self._cats: list[list[int]] = []      # EMJ_CATEGORIES, expanded
        self._tab_icons: list[int] = []       # emj_tab_icons
        self._regions: list[str] = []         # REGION_LABELS
        self._region_offset: list[int] = []   # REGION_OFFSET
        self._region_langs: list[int] = []    # REGION_LANGS
        self._lang_codes: list[str] = []      # to_static_text()'s cog-built lang_code[]

    # -- loading ------------------------------------------------------------

    def load(self, fw_polykybd: str) -> bool:
        try:
            self._load_emoji(fw_polykybd)
            self._load_lang(fw_polykybd)
        except Exception as e:                      # a missing checkout, a moved file
            self.reason = f"{type(e).__name__}: {e}"
            return False
        self.usable = bool(self._cats and self._regions and self._region_langs
                           and self._lang_codes)
        self.reason = "" if self.usable else "the emoji/language tables did not parse"
        return self.usable

    def _load_emoji(self, pk: str) -> None:
        data = _read(os.path.join(pk, "emoji", "emoji_data.h"))
        # EMJ_CATEGORIES lists the per-category arrays by NAME, and the order of that
        # list is the tab order -- so read the names from it rather than assuming
        # `emj_cat<N>` counts up, which is true today and is not a contract.
        m = re.search(r"EMJ_CATEGORIES\s*\[\]\s*=\s*\{(.*?)\}\s*;", data, re.S)
        if not m:
            return
        for arr in re.findall(r"EMJ_CAT_ENTRY\s*\(\s*(\w+)\s*\)", m.group(1)):
            self._cats.append(_u32_array(data, arr) or [])
        layer = _read(os.path.join(pk, "emoji", "emoji_layer.c"))
        self._tab_icons = _u32_array(layer, "emj_tab_icons") or []

    def _load_lang(self, pk: str) -> None:
        lang = _read(os.path.join(pk, "lang_layer.c"))
        self._regions = _u_strings(lang, "REGION_LABELS") or []
        self._region_offset = _u32_array(lang, "REGION_OFFSET") or []
        self._region_langs = _u32_array(lang, "REGION_LANGS") or []
        # The "ll-CC" caption under each flag. It is the cog-generated `lang_code[]`
        # inside to_static_text()'s KCL_ENUS case range -- read from the firmware
        # rather than from lang_lut.xlsx, so the flag keys do not inherit the
        # language LUT's openpyxl prerequisite.
        keymap = _read(os.path.join(pk, "poly_keymap.c"))
        self._lang_codes = _u_strings(keymap, "lang_code") or []

    # -- resting-state answers ----------------------------------------------

    def emoji_category_cp(self, cat: int) -> int | None:
        """The tab icon for category `cat`.

        Mirrors `emj_display_text()`: the hardwired icon when there is one, else the
        category's first codepoint -- and an EMPTY category draws nothing at all.
        """
        if not (0 <= cat < len(self._cats)) or not self._cats[cat]:
            return None
        if cat < len(self._tab_icons) and self._tab_icons[cat]:
            return self._tab_icons[cat]
        return self._cats[cat][0]

    def emoji_slot_cp(self, slot: int) -> int | None:
        """Slot `slot` of the category and page a resting board shows (0 and 0)."""
        if not self._cats:
            return None
        page0 = self._cats[0]
        return page0[slot] if 0 <= slot < min(len(page0), EMJ_SLOTS_PER_PAGE) else None

    def region_label(self, region: int) -> str | None:
        if 0 <= region < len(self._regions):
            return self._regions[region]
        return None

    def lang_slot_index(self, slot: int) -> int | None:
        """The language index in slot `slot` of region 0, page 0.

        `REGION_OFFSET` has one extra trailing entry (the end of the last region), so
        a region's language count is the difference between its own offset and the
        next -- the same arithmetic `lang_index_for_keycode()` does.
        """
        if len(self._region_offset) < 2 or not self._region_langs:
            return None
        start, end = self._region_offset[0], self._region_offset[1]
        if not (0 <= slot < min(end - start, LANG_SLOTS_PER_PAGE)):
            return None
        idx = start + slot
        return self._region_langs[idx] if idx < len(self._region_langs) else None

    def flag_codepoint(self, lang_index: int) -> int:
        return FLAG_CP_BASE + lang_index

    def lang_code(self, lang_index: int) -> str | None:
        """The "ll-CC" caption drawn up the right edge of a flag keycap."""
        if 0 <= lang_index < len(self._lang_codes):
            return self._lang_codes[lang_index]
        return None
