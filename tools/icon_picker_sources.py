"""Picture sources for gen_icon_picker.py, one class per game-asset reader.

A source turns a picker spec's `src` string into a palette-index image and a
font name into glyphs. The palette is the game's, 256 RGB entries. Nothing
here is shipped: the generator embeds what it reads in a local HTML file.

Dune II (`westwood_d2`), all from the user's DUNE.PAK:

- ``shp:<file>.shp:<frame>``   a frame of a shape file (SHAPES.SHP, MOUSE.SHP);
- ``sprite:<file>:<face>[+<turret>]``  a map sprite, the turret frame drawn over
  the base, as the reader draws it;
- ``icn:<set>:<start>:<w>x<h>``  a building as the map shows it: tiles
  start .. start + w*h - 1 of ICON.MAP group `set`, row by row;
- ``icnset:<set>:<i>``  one tile of an ICON.MAP group;
- ``icntile:<tile>:<n>``  ICON.ICN tile `tile`, repeated n x n.

The ICN and FNT layouts follow Dune Legacy's Icnfile.cpp and OpenDUNE's
gui/font.c.
"""
from __future__ import annotations

import struct

import numpy as np


def icn_tiles(icn: bytes, mapfile: bytes) -> tuple[list, list]:
    """(tiles, groups): every 16x16 tile of ICON.ICN as palette indices, and the
    tile numbers of each ICON.MAP group."""
    if icn[0x18:0x1C] != b"SSET":
        raise ValueError("ICON.ICN has no SSET section")
    sset_len = struct.unpack_from(">I", icn, 0x1C)[0] - 8
    s0 = 0x18 + 16
    rpal = s0 + sset_len
    if icn[rpal:rpal + 4] != b"RPAL":
        raise ValueError("ICON.ICN has no RPAL section")
    p0 = rpal + 8
    rtbl = p0 + struct.unpack_from(">I", icn, rpal + 4)[0]
    if icn[rtbl:rtbl + 4] != b"RTBL":
        raise ValueError("ICON.ICN has no RTBL section")
    t0 = rtbl + 8
    tiles = []
    for i in range(sset_len // 128):
        raw = np.frombuffer(icn, np.uint8, 128, s0 + 128 * i)
        nib = np.stack([raw >> 4, raw & 15], 1).reshape(16, 16)
        tiles.append(np.frombuffer(icn, np.uint8, 16, p0 + 16 * icn[t0 + i])[nib])
    words = struct.unpack_from(f"<{len(mapfile) // 2}H", mapfile)
    groups = [list(words[words[k]:(words[k + 1] if k + 1 < words[0] else len(words))]) for k in range(words[0])]
    return tiles, groups


def font_glyphs(buf: bytes) -> tuple[int, dict]:
    """(height, {code: glyph}) of a Dune II .FNT file. A glyph pixel is 0 (empty),
    1 (letter body), 2 (shade) or 3 (outline)."""
    if buf[2:4] != b"\x00\x05":
        raise ValueError("not a Dune II font")
    start, data_start, width_list, _, line_list = struct.unpack_from("<5H", buf, 4)
    height = buf[start + 4]
    count = struct.unpack_from("<H", buf, 10)[0] - width_list
    chars = {}
    for i in range(count):
        w = buf[width_list + i]
        unused, used = buf[line_list + 2 * i], buf[line_list + 2 * i + 1]
        off = struct.unpack_from("<H", buf, data_start + 2 * i)[0]
        g = np.zeros((height, w), np.uint8)
        if off:
            for y in range(used):
                for x in range(w):
                    d = buf[off + y * ((w + 1) // 2) + x // 2]
                    g[unused + y, x] = (d >> 4 if x % 2 else d) & 15
        chars[i] = g
    return height, chars


class WestwoodD2:
    """Dune II: DUNE.PAK as the westwood_d2 reader finds it."""

    def __init__(self, files: dict):
        from polyhost.services.game_assets.westwood_d2 import reader as d2
        from polyhost.services.game_assets.westwood_d2.pak import Pak
        from polyhost.services.game_assets.westwood_td import westwood
        self._d2, self._w = d2, westwood
        self.pak = Pak.open(files["dune.pak"])
        self.palette = westwood.palette(self.pak.get("ibm.pal")).astype(np.uint8)
        self.sprites = d2.open_source(files)
        self._shp, self._icn = {}, None

    def _file(self, name: str) -> bytes:
        data = self.pak.get(name.lower())
        if data is None:
            raise KeyError(f"{name} is not in DUNE.PAK")
        return data

    def picture(self, src: str) -> np.ndarray:
        kind, _, rest = src.partition(":")
        if kind == "shp":
            name, frame = rest.rsplit(":", 1)
            if name not in self._shp:
                self._shp[name] = self._w.shp_d2_frames(self._file(name))
            return self._shp[name][int(frame)]
        if kind == "sprite":
            name, faces = rest.split(":")
            face, _, turret = faces.partition("+")
            recipe = {"unit": name, "face": int(face)}
            if turret:
                recipe["turret"] = int(turret)
            return self._d2._pixels(self.sprites, recipe)
        if self._icn is None:
            self._icn = icn_tiles(self._file("icon.icn"), self._file("icon.map"))
        tiles, groups = self._icn
        if kind == "icn":
            group, start, size = rest.split(":")
            tw, th = (int(v) for v in size.split("x"))
            t = groups[int(group)][int(start):int(start) + tw * th]
            return np.vstack([np.hstack([tiles[t[r * tw + c]] for c in range(tw)]) for r in range(th)])
        if kind == "icnset":
            group, i = rest.split(":")
            return tiles[groups[int(group)][int(i)]]
        if kind == "icntile":
            tile, n = rest.split(":")
            return np.tile(tiles[int(tile)], (int(n), int(n)))
        raise ValueError(f"unknown source {src!r}")

    def font(self, name: str) -> tuple[int, dict]:
        return font_glyphs(self._file(name))


SOURCES = {"westwood_d2": WestwoodD2}
