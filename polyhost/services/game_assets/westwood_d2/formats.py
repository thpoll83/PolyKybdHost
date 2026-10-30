"""Dune II map tiles (ICON.ICN + ICON.MAP) and fonts (*.FNT).

The layouts follow Dune Legacy's Icnfile.cpp and OpenDUNE's gui/font.c.
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
