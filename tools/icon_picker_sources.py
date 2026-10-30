"""Picture sources for gen_icon_picker.py, one class per game-asset reader.

A source turns a picker spec's `src` string into a palette-index image and a
font name into glyphs. The palette is the game's, 256 RGB entries. Nothing
here is shipped: the generator embeds what it reads in a local HTML file.

Dune II (`westwood_d2`): the `src` strings are the reader's
(westwood_d2/reader.py `source()`): ``shp:``, ``sprite:``, ``icn:``,
``icnset:`` and ``icntile:``.
"""
from __future__ import annotations

import numpy as np



class WestwoodD2:
    """Dune II: DUNE.PAK as the westwood_d2 reader finds it. Pictures and fonts
    come from the reader itself, so the page and the keyboard read the same."""

    def __init__(self, files: dict):
        from polyhost.services.game_assets.westwood_d2 import reader as d2
        self._d2 = d2
        self.sprites = d2.open_source(files)
        self.palette = d2.palette(self.sprites)

    def picture(self, src: str) -> np.ndarray:
        return self._d2.source(self.sprites, src)

    def font(self, name: str) -> tuple[int, dict]:
        return self._d2.font(self.sprites, name)


SOURCES = {"westwood_d2": WestwoodD2}
