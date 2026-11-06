"""PKWARE Data Compression Library "explode" (the MPQ implode compression, 0x08).

A Python port of blast.c version 1.3 (24 Aug 2013) by Mark Adler, from zlib's
contrib/blast. The original carries this notice, which the port keeps:

    Copyright (C) 2003, 2012, 2013 Mark Adler

    This software is provided 'as-is', without any express or implied
    warranty.  In no event will the author be held liable for any damages
    arising from the use of this software.

    Permission is granted to anyone to use this software for any purpose,
    including commercial applications, and to alter it and redistribute it
    freely, subject to the following restrictions:

    1. The origin of this software must not be misrepresented; you must not
       claim that you wrote the original software. If you use this software
       in a product, an acknowledgment in the product documentation would be
       appreciated but is not required.
    2. Altered source versions must be plainly marked as such, and must not be
       misrepresented as being the original software.
    3. This notice may not be removed or altered from any source distribution.

    Mark Adler    madler@alumni.caltech.edu

This is an altered version: it is a Python translation, it reads from a bytes
object and returns bytes instead of calling input and output functions, it
keeps the whole output instead of a 4 KB window, and it raises ValueError
where blast() returns an error code. The zlib licence is compatible with this
project's GPL-3.0-or-later.

The format (from blast.c): the first byte is 0 when literals are uncoded and 1
when they are Huffman coded; the second is 4, 5 or 6, the number of low
distance bits. Then each item is a 0 bit and a literal, or a 1 bit and a
length/distance pair. Length 519 ends the stream.
"""
from __future__ import annotations

MAXBITS = 13

# Bit lengths of the three fixed codes, in blast.c's compact form: each byte is
# (repeat count - 1) << 4 | code length.
LITLEN = bytes((
    11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8,
    9, 7, 6, 7, 8, 7, 6, 55, 8, 23, 24, 12, 11, 7, 9, 11, 12, 6, 7, 22, 5,
    7, 24, 6, 11, 9, 6, 7, 22, 7, 11, 38, 7, 9, 8, 25, 11, 8, 11, 9, 12,
    8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10, 53, 8, 7, 24, 10, 27,
    44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45,
    44, 173))
LENLEN = bytes((2, 35, 36, 53, 38, 23))
DISTLEN = bytes((2, 20, 53, 230, 247, 151, 248))
BASE = (3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264)
EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8)


def lengths(rep: bytes) -> list[int]:
    """The code length of each symbol from the compact repeat form."""
    out = []
    for b in rep:
        out += [b & 15] * ((b >> 4) + 1)
    return out


def construct(rep: bytes) -> tuple[list[int], list[int]]:
    """(count per length, symbols in canonical order), as blast.c's construct()."""
    length = lengths(rep)
    count = [0] * (MAXBITS + 1)
    for n in length:
        count[n] += 1
    offs = [0] * (MAXBITS + 1)
    for n in range(1, MAXBITS):
        offs[n + 1] = offs[n] + count[n]
    symbol = [0] * len(length)
    for s, n in enumerate(length):
        if n:
            symbol[offs[n]] = s
            offs[n] += 1
    return count, symbol


_LIT, _LEN, _DIST = construct(LITLEN), construct(LENLEN), construct(DISTLEN)


class _Bits:
    """Bits from the least significant end of each byte, as blast.c's bits()."""

    def __init__(self, data: bytes):
        self.data, self.pos, self.buf, self.cnt = data, 0, 0, 0

    def get(self, need: int) -> int:
        while self.cnt < need:
            if self.pos >= len(self.data):
                raise ValueError("imploded data ends early")
            self.buf |= self.data[self.pos] << self.cnt
            self.pos += 1
            self.cnt += 8
        val = self.buf & ((1 << need) - 1)
        self.buf >>= need
        self.cnt -= need
        return val

    def decode(self, table) -> int:
        """One symbol of a code. The stored codes are bit-reversed and
        inverted; blast.c's decode() reads them one bit at a time."""
        count, symbol = table
        code = first = index = 0
        for n in range(1, MAXBITS + 1):
            code |= self.get(1) ^ 1
            c = count[n]
            if code < first + c:
                return symbol[index + code - first]
            index += c
            first = (first + c) << 1
            code <<= 1
        raise ValueError("invalid code in imploded data")


def explode(data: bytes, max_size: int | None = None) -> bytes:
    """Decompress one PKWARE DCL stream. `max_size` stops a damaged stream
    from growing the output past what the caller expects."""
    s = _Bits(data)
    lit = s.get(8)
    if lit > 1:
        raise ValueError("imploded data: bad literal flag")
    dict_bits = s.get(8)
    if dict_bits < 4 or dict_bits > 6:
        raise ValueError("imploded data: bad dictionary size")
    out = bytearray()
    while True:
        if s.get(1):
            sym = s.decode(_LEN)
            length = BASE[sym] + s.get(EXTRA[sym])
            if length == 519:
                break                               # end code
            low = 2 if length == 2 else dict_bits
            dist = (s.decode(_DIST) << low) + s.get(low) + 1
            if dist > len(out):
                raise ValueError("imploded data: distance too far back")
            start = len(out) - dist
            for k in range(length):                 # overlapping copies are allowed
                out.append(out[start + k])
        else:
            out.append(s.decode(_LIT) if lit else s.get(8))
        if max_size is not None and len(out) > max_size:
            raise ValueError(f"imploded data grows past {max_size} bytes")
    return bytes(out)
