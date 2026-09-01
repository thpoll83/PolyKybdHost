"""The keycap-preview data that ships WITH the host, and how it beats a checkout.

The previews draw through this repo's own `tools/oled_preview.py`, but the data
they draw -- each keycode's legend, the per-language letter table, the layer enum
and the glyph bitmaps -- is generated from the firmware sources. Reading it live
from a `qmk_firmware` clone beside the install made the feature unavailable to
anyone who is not a firmware developer, and silently WRONG for anyone whose clone
had drifted from the keyboard in front of them.

`scripts/export_preview_data.py` writes that data into `res/preview/`; this loads
it. Qt-free and device-free, so the editor, the doctor and the tests share it.

⚠️ WHICH SOURCE WINS is a version comparison, not a preference. The shipped export
is self-consistent by construction -- legends, enum and glyphs all came from one
firmware tree -- while a checkout can be anything. But a firmware developer's tree
is, by definition, AHEAD of the last release and is the whole reason to preview at
all. So the checkout wins only when its FW_VERSION is strictly newer; a clone that
is merely old loses, which is exactly the case that produced a blank Fn key and
retired brightness icons in the field.
"""
from __future__ import annotations

import json
import logging
import pathlib

RES = pathlib.Path(__file__).resolve().parent.parent / "res"
PREVIEW_DIR = RES / "preview"
FONTPACK_DIR = RES / "fontpack"


def parse_version(v: str) -> tuple:
    """`"0.16.20"` -> `(0, 16, 20)`; anything unparseable sorts oldest."""
    out = []
    for part in str(v or "").split("."):
        digits = "".join(c for c in part if c.isdigit())
        if not digits:
            break
        out.append(int(digits))
    return tuple(out) if out else (-1,)


def choose_source(shipped_version: str, checkout_version: str) -> str:
    """"shipped" or "checkout" -- see the module docstring.

    A checkout wins only by being strictly NEWER. Equal versions pick the shipped
    copy: it is the one that was tested, and re-parsing the same firmware twice
    cannot produce a better answer.
    """
    if not checkout_version:
        return "shipped"
    if not shipped_version:
        return "checkout"
    return ("checkout" if parse_version(checkout_version) > parse_version(shipped_version)
            else "shipped")


class PreviewData:
    """Legends, layer tags, the language table and the fonts, from `res/preview/`.

    `ok` is False when the export is absent or unreadable; `reason` says which.
    """

    def __init__(self, directory=None):
        self.log = logging.getLogger("PreviewData")
        self.dir = pathlib.Path(directory or PREVIEW_DIR)
        self.ok = False
        self.reason = ""
        self.fw_version = ""
        self.legends: dict[str, list[int]] = {}
        self.layer_tags: dict[int, str] = {}
        self.langs: list[str] = []
        self._cells: dict[str, dict[str, list[str]]] = {}
        self.fonts: list = []
        self.ui_fonts: dict = {}   # symbol name -> the standalone face

    def load(self) -> bool:
        try:
            legends = self._json("legends.json")
            layers = self._json("layers.json")
            lut = self._json("lang_lut.json")
        except Exception as e:
            self.reason = f"{type(e).__name__}: {e}"
            self.log.debug("no shipped preview data in %s (%s)", self.dir, self.reason)
            return False

        self.fw_version = legends.get("fw_version", "")
        self.legends = {k: list(v) for k, v in legends.get("legends", {}).items()}
        self.layer_tags = {int(k): str(v) for k, v in layers.get("tags", {}).items()}
        self.langs = list(lut.get("langs", []))
        self._cells = lut.get("cells", {})
        try:
            self.fonts = self._fonts()
            self.ui_fonts = self._ui_fonts(legends.get("ui_fonts") or [])
        except Exception as e:
            self.reason = f"fonts: {type(e).__name__}: {e}"
            self.log.debug("shipped preview fonts unreadable (%s)", self.reason)
            return False
        self.ok = bool(self.legends and self.fonts)
        if not self.ok:
            self.reason = "the shipped preview data is empty"
        return self.ok

    def cells(self, lang: str, kc: str):
        """The four variation columns for one key of one language, or None."""
        return (self._cells.get(lang) or {}).get(kc)

    # -- internals ----------------------------------------------------------

    def _json(self, name: str):
        return json.loads((self.dir / name).read_text(encoding="utf-8"))

    def _ui_fonts(self, names) -> dict:
        """The standalone UI faces, by symbol name.

        ⚠️ Reached by NAME, not by codepoint -- no codepoint can route to them,
        which is exactly why the firmware draws each through a single-font array.
        The `.plyf` carries no names, so the export lists them alongside.
        """
        from polyhost.services import fontpack_reader as fr

        path = self.dir / "ui_fonts.plyf"
        if not (names and path.exists()):
            return {}
        fonts = fr.decode_pack_file(str(path), "ui").fonts
        return {n: f for n, f in zip(names, fonts)}

    def _fonts(self) -> list:
        """Resident + every shipped bundle, in ALL_FONTS priority order.

        ⚠️ The order IS the lookup: the firmware scans front to back and the first
        font holding the codepoint wins, so a resident face deliberately shadows a
        pack copy of the same glyph. Each record carries its own global index, so
        the order is reconstructed from those rather than assumed from the file
        order -- `sorted(glob())` is alphabetical, which is not priority.
        """
        from polyhost.services import fontpack_reader as fr

        out = []
        resident = self.dir / "resident.plyf"
        if resident.exists():
            out += [(f.global_index, f) for f in
                    fr.decode_pack_file(str(resident), "resident").fonts]
        for plyf in sorted(FONTPACK_DIR.glob("*.plyf")):
            out += [(f.global_index, f) for f in
                    fr.decode_pack_file(str(plyf), plyf.stem).fonts]
        out.sort(key=lambda pair: pair[0])
        return [f for _, f in out]
