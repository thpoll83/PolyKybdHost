"""Readers for the 1995 Westwood file formats of Command & Conquer (Tiberian Dawn).

Only what the C&C overlay needs: MIX archives, LCW ("format 80") and XOR-delta
("format 40") compression, TD shape files (unit and building sprites), the
Dune-2-style shape file TD uses for MOUSE.SHP, and 6-bit palettes. The formats
are documented by the OpenRA and XCC projects; the code here is written from
those descriptions, nothing is copied.

The game files are the user's own and are only ever read; nothing here ships or
uploads them.
"""
from __future__ import annotations

import struct

import numpy as np

# The largest frame decoded: the game's own 640x400 screen (agreed with the
# maintainer, 2026-10-28). The largest frame in the freeware CONQUER.MIX is
# 13,752 px (72x191). The 16-bit header fields allow 65535x65535, which LCW fill
# commands can expand to about 4 GiB from a 256 KiB file.
MAX_FRAME_PIXELS = 640 * 400


def _check_size(w: int, h: int) -> None:
    if w * h > MAX_FRAME_PIXELS:
        raise ValueError(f"frame of {w}x{h} px is larger than {MAX_FRAME_PIXELS} px")


def td_hash(name: str) -> int:
    """The Tiberian Dawn MIX file-name hash: upper-case ASCII, zero-padded to a
    multiple of 4, summed as little-endian words with a 1-bit left rotate first."""
    b = name.upper().encode("ascii")
    b += b"\0" * (-len(b) % 4)
    r = 0
    for (v,) in struct.iter_unpack("<I", b):
        r = ((r << 1) | (r >> 31)) & 0xFFFFFFFF
        r = (r + v) & 0xFFFFFFFF
    return r


class Mix:
    """An unencrypted Tiberian Dawn MIX archive (the freeware and Remastered
    `.MIX` files): a count, a body size, then (hash, offset, size) entries."""

    def __init__(self, data: bytes):
        self.data = data
        count, _size = struct.unpack_from("<HI", data, 0)
        self.body = 6 + 12 * count
        self.entries = {}
        for i in range(count):
            h, off, sz = struct.unpack_from("<III", data, 6 + 12 * i)
            self.entries[h] = (off, sz)

    @classmethod
    def open(cls, path) -> Mix:
        with open(path, "rb") as f:
            return cls(f.read())

    def get(self, name: str) -> bytes | None:
        entry = self.entries.get(td_hash(name))
        if entry is None:
            return None
        off, sz = entry
        return self.data[self.body + off:self.body + off + sz]


def lcw(src: bytes, out_size: int) -> bytes:
    """LCW ("format 80") decompression into `out_size` bytes."""
    dst = bytearray()
    i = 0
    while i < len(src) and len(dst) < out_size:
        b = src[i]
        i += 1
        if b & 0x80 == 0:                       # 0cccpppp pppppppp: copy from dst - p
            cnt = ((b >> 4) & 7) + 3
            p = len(dst) - (((b & 0x0F) << 8) | src[i])
            i += 1
            for k in range(cnt):
                dst.append(dst[p + k])
        elif b & 0x40 == 0:                     # 10cccccc: literal run (0 ends)
            cnt = b & 0x3F
            if cnt == 0:
                break
            dst += src[i:i + cnt]
            i += cnt
        elif b == 0xFE:                         # fill: count, value
            cnt, = struct.unpack_from("<H", src, i)
            dst += bytes([src[i + 2]]) * cnt
            i += 3
        elif b == 0xFF:                         # long copy from absolute position
            cnt, pos = struct.unpack_from("<HH", src, i)
            i += 4
            for k in range(cnt):
                dst.append(dst[pos + k])
        else:                                   # 11cccccc: short copy from absolute position
            cnt = (b & 0x3F) + 3
            pos, = struct.unpack_from("<H", src, i)
            i += 2
            for k in range(cnt):
                dst.append(dst[pos + k])
    if len(dst) < out_size:
        # A frame decodes to exactly its declared size. A short one is a damaged
        # file; padding it would allocate whatever size the header claims.
        raise ValueError(f"LCW data ends after {len(dst)} of {out_size} bytes")
    return bytes(dst[:out_size])


def xor_delta(src: bytes, size: int) -> bytes:
    """Format 40 delta, applied to zeros; the caller XORs it onto the base frame.
    A run past the end of the frame is a damaged file and raises ValueError."""
    dst = bytearray(size)
    i = p = 0
    while i < len(src):
        if len(dst) != size:                    # a run wrote past the frame end
            raise ValueError(f"XOR delta runs past the {size}-byte frame")
        b = src[i]
        i += 1
        if b == 0:                              # fill: count, value
            cnt, v = src[i], src[i + 1]
            i += 2
            dst[p:p + cnt] = bytes([v]) * cnt
            p += cnt
        elif b & 0x80 == 0:                     # literal run
            dst[p:p + b] = src[i:i + b]
            i += b
            p += b
        elif b != 0x80:                         # short skip
            p += b & 0x7F
        else:
            w, = struct.unpack_from("<H", src, i)
            i += 2
            if w == 0:
                break
            cnt = w & 0x3FFF
            if w & 0x8000 == 0:                 # long skip
                p += w
            elif w & 0x4000 == 0:               # long literal run
                dst[p:p + cnt] = src[i:i + cnt]
                i += cnt
                p += cnt
            else:                               # long fill
                dst[p:p + cnt] = bytes([src[i]]) * cnt
                i += 1
                p += cnt
    if len(dst) != size:
        raise ValueError(f"XOR delta runs past the {size}-byte frame")
    return bytes(dst)


def shp_frames(data: bytes, count: int | None = None) -> list[np.ndarray]:
    """The first `count` frames (all when None) of a TD shape file as (h, w)
    palette-index arrays. A frame is LCW-compressed (0x80), an XOR delta against
    an earlier keyframe (0x40) or against the previous frame (0x20). Decoding
    stops at `count`, so a header claiming 65535 frames costs only what is used."""
    n, _x, _y, w, h = struct.unpack_from("<HHHHH", data, 0)
    _check_size(w, h)
    hdr = [struct.unpack_from("<II", data, 14 + 8 * i) for i in range(n + 1)]
    offs = [a & 0xFFFFFF for a, _ in hdr]
    frames, by_offset = [], {}
    for i in range(n if count is None else min(n, count)):
        a, b = hdr[i]
        off, fmt, ref = a & 0xFFFFFF, a >> 24, b & 0xFFFFFF
        raw = data[off:offs[i + 1]]
        if fmt == 0x80:
            f = np.frombuffer(lcw(raw, w * h), np.uint8).copy()
        else:
            base = by_offset[ref] if fmt == 0x40 else frames[-1].ravel()
            f = base ^ np.frombuffer(xor_delta(raw, w * h), np.uint8)
        by_offset[off] = f
        frames.append(f.reshape(h, w))
    return frames


def _rle_zeros(src: bytes, size: int) -> bytes:
    out = bytearray()
    i = 0
    while i < len(src) and len(out) < size:
        b = src[i]
        i += 1
        if b == 0:
            out += b"\0" * src[i]
            i += 1
        else:
            out.append(b)
    if len(out) < size:
        raise ValueError(f"zero-run data ends after {len(out)} of {size} bytes")
    return bytes(out[:size])


def shp_d2_frames(data: bytes, count: int | None = None) -> list[np.ndarray]:
    """The first `count` frames (all when None) of a Dune-2-style shape file, the
    format of TD's MOUSE.SHP: a frame count, 2- or 4-byte offsets, then per frame
    a small header, an optional colour table, LCW and a zero-run encoding."""
    n, = struct.unpack_from("<H", data, 0)
    two_byte = (struct.unpack_from("<I", data, 2)[0] & 0xFF0000) > 0
    fmt, step = ("<H", 2) if two_byte else ("<I", 4)
    offs = [struct.unpack_from(fmt, data, 2 + step * i)[0] + 2 for i in range(n + 1)]
    frames = []
    for i in range(n if count is None else min(n, count)):
        p = offs[i]
        flags, = struct.unpack_from("<H", data, p)
        p += 3
        w, = struct.unpack_from("<H", data, p)
        p += 2
        h = data[p]
        p += 1
        _check_size(w, h)
        left, dsize = struct.unpack_from("<HH", data, p)
        p += 4
        left -= 10
        if flags & 1:                           # colour table
            nt = 16
            if flags & 4:
                nt = data[p]
                p += 1
            table = list(data[p:p + nt])
            p += nt
            left -= nt
        else:
            table = list(range(256))
            table[1:5] = [0x7F, 0x7E, 0x7D, 0x7C]
        comp = data[p:p + left]
        if not flags & 2:
            comp = lcw(comp, dsize)
        px = np.frombuffer(_rle_zeros(comp, w * h), np.uint8)
        frames.append(np.asarray(table, np.uint8)[px].reshape(h, w))
    return frames


def palette(data: bytes) -> np.ndarray:
    """A 256-colour palette of 6-bit RGB triplets, scaled to 0..255, as (256, 3)."""
    return np.frombuffer(data[:768], np.uint8).reshape(256, 3).astype(np.uint16) * 255 // 63
