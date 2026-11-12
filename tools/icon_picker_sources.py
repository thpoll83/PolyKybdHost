"""Picture sources for gen_icon_picker.py, one class per game-asset reader.

A source turns a picker spec's `src` string into a palette-index image and a
font name into glyphs. The palette is the game's, 256 RGB entries. Nothing
here is shipped: the generator embeds what it reads in a local HTML file.

Dune II (`westwood_d2`): the `src` strings are the reader's
(westwood_d2/reader.py `source()`): ``shp:``, ``sprite:``, ``icn:``,
``icnset:`` and ``icntile:``.

Warzone 2100 (`warzone2100`): the game's art is GPL-2.0-or-later, so its picks
ship as icons instead of being read from the user's files at run time. The
``src`` strings are ``intfac:<image>`` (a PNG of ``images/intfac/``, from a
Warzone ``data/base`` folder or ``base.wz``) and ``model:<name>`` (a unit of
``warzone2100/wz_models.py``, rendered from the game's models).
"""
from __future__ import annotations

import numpy as np



class WestwoodD2:
    """Dune II: DUNE.PAK as the westwood_d2 reader finds it. Pictures and fonts
    come from the reader itself, so the page and the keyboard read the same."""

    KINDS = ("shp", "sprite", "icn", "icnset", "icntile")    # the src prefixes picture() reads

    def __init__(self, files: dict):
        from polyhost.services.game_assets.westwood_d2 import reader as d2
        self._d2 = d2
        self.sprites = d2.open_source(files)
        self.palette = d2.palette(self.sprites)

    def picture(self, src: str) -> np.ndarray:
        return self._d2.source(self.sprites, src)

    def font(self, name: str) -> tuple[int, dict]:
        return self._d2.font(self.sprites, name)


class Warzone2100:
    """Warzone 2100's interface images and 3D units. The palette is fixed: 190
    colours from all interface images, 64 greys for the rendered units, and
    index 255 for "no picture", which the page cuts as the background."""

    BG = 255
    KINDS = ("intfac", "model")
    SHIPS = True               # GPL art: apply_icon_picks.py writes its picks to pictures.yaml

    @staticmethod
    def find(data_dir: str):
        """{"intfac": a function name -> PNG bytes}, from a data/base folder, a
        repository checkout or a base.wz archive; None if none is found."""
        import zipfile
        from pathlib import Path
        roots = [Path(data_dir)] if data_dir else [Path("/usr/share/games/warzone2100"), Path("/usr/share/warzone2100")]
        for root in roots:
            for d in (root / "images" / "intfac", root / "base" / "images" / "intfac",
                      root / "data" / "base" / "images" / "intfac"):
                if d.is_dir():
                    return {"intfac": lambda name, d=d: (d / f"{name}.png").read_bytes()}
            for z in (root, root / "base.wz", root / "data" / "base.wz"):
                if z.is_file() and zipfile.is_zipfile(z):
                    arc = zipfile.ZipFile(z)
                    return {"intfac": lambda name, arc=arc: arc.read(f"images/intfac/{name}.png")}
        return None

    def __init__(self, files: dict):
        import io
        from PIL import Image
        self._read = files["intfac"]
        self._img = lambda name: Image.open(io.BytesIO(self._read(name))).convert("RGBA")
        # 190 colours from a sample of the interface images, then 64 greys
        sample = []
        for name in files.get("palette_from", []):
            a = np.asarray(self._img(name))
            sample.append(a[a[..., 3] > 127][:, :3])
        rgb = np.concatenate(sample) if sample else np.zeros((1, 3), np.uint8)
        q = Image.fromarray(rgb[None, :, :].astype(np.uint8), "RGB").quantize(190, method=Image.Quantize.MEDIANCUT)
        pal = np.array(q.getpalette()[:190 * 3], np.uint8).reshape(-1, 3)
        pal = np.vstack([pal, np.zeros((190 - len(pal), 3), np.uint8)])
        greys = np.repeat(np.linspace(0, 255, 64).round().astype(np.uint8)[:, None], 3, 1)
        self.palette = np.vstack([pal, greys, [[0, 0, 0]], [[255, 0, 255]]])          # 190 + 64 + 1 + bg
        self._pal_img = Image.new("P", (1, 1))
        self._pal_img.putpalette(list(self.palette[:254].ravel()) + [0] * 6)

    def picture(self, src: str) -> np.ndarray:
        kind, name = src.split(":", 1)
        if kind == "intfac":
            im = self._img(name)
            a = np.asarray(im)
            idx = np.asarray(im.convert("RGB").quantize(palette=self._pal_img, dither=0))
            return np.where(a[..., 3] > 127, idx, self.BG).astype(np.uint8)
        if kind == "model":
            from polyhost.res.overlay_sources.warzone2100 import wz_models
            grey, cover = wz_models.render(name)
            return np.where(cover, 190 + np.round(np.clip(grey, 0, 1) * 63), self.BG).astype(np.uint8)
        raise ValueError(f"unknown Warzone 2100 source {src!r}")

    def font(self, name: str):
        raise ValueError("the Warzone 2100 picker has no game fonts")


SOURCES = {"westwood_d2": WestwoodD2, "warzone2100": Warzone2100}
