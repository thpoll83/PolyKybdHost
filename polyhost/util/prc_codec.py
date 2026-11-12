"""PRC overlay images (HID cmd 41, protocol v19).

PRC = Predictive Range Coding. "Predictive": before a pixel is coded, its 10
already-coded neighbours predict how likely it is to be 0. "Range coding": an
arithmetic coder spends few bits on a pixel that matches the prediction and more
on one that does not. Keycap icons are mostly empty space and clean edges, so the
predictions are nearly always right. The idea is JBIG's (the fax standard); the
format is our own and is not JBIG-compatible.

A 1-bit overlay is sent as its region of interest (ROI), coded pixel by pixel.
Each pixel's probability comes from a FIXED table indexed by its 10 already
decoded neighbours (the JBIG template below), and a binary range coder turns
those probabilities into bytes. Measured on the shipped templates this needs
~26-30 bytes per icon against ~87 for the best of the four older encodings, so
nearly every icon fits one HID report and two usually share one.

⚠️ This file, ``polyhost/res/prc_table_v1.bin`` and the firmware's
``keyboards/polykybd/base/prc_codec.c`` + ``prc_table.h`` are ONE format. The
firmware decodes exactly what this encodes, bit for bit: the template order, the
zero padding outside the ROI, the probability scale and every step of the range
coder must stay identical. ``tests/util/prc_codec_test.py`` pins golden vectors
that the firmware's ``make test:polykybd_prc_codec`` checks too.

⚠️ Table v1 is FROZEN. A retrained table is a new table id, never an edit to
this one: a keyboard that decodes with a different table than the host encoded
with draws garbage with nothing reporting an error.
"""
from __future__ import annotations

import os
from functools import lru_cache

# Neighbours as (dy, dx) relative to the pixel, most significant context bit
# first. Only already-decoded pixels: the two rows above and the two to the left.
TEMPLATE = ((-1, -1), (-1, 0), (-1, 1), (0, -2), (0, -1),
            (-2, -1), (-2, 0), (-2, 1), (-1, -2), (-1, 2))
CONTEXTS = 1 << len(TEMPLATE)          # 1024
TABLE_ID = 1
TABLE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          "res", f"prc_table_v{TABLE_ID}.bin")

# One image inside a cmd 41 report: a 6-byte big-endian bit field, then the
# payload. Mirrors prc_parse_record() in the firmware's base/prc_codec.c.
#   keycode 8 | modifier 4 | top 6 | left 7 | height-1 6 | width-1 7 | len 6 | 0 4
RECORD_HDR = 6
MAX_RECORD_PAYLOAD = 63   # the 6-bit length field

_TOP = 1 << 24
_MASK32 = 0xFFFFFFFF


@lru_cache(maxsize=1)
def table() -> bytes:
    """The frozen probability table: P(pixel is 0) * 256, 1..255, per context."""
    with open(TABLE_FILE, "rb") as fh:
        data = fh.read()
    if len(data) != CONTEXTS or min(data) < 1:
        raise ValueError(f"{TABLE_FILE}: expected {CONTEXTS} bytes in 1..255")
    return data


def contexts(roi):
    """Context index of every ROI pixel, row-major, as a flat list of ints.

    ``roi`` is a 2-D bool/0-1 array. Pixels outside the ROI count as 0, which is
    also what the firmware reads: it decodes into a cleared 72x40 buffer, and
    the ROI is the ink's bounding box, so every pixel around it is 0 anyway."""
    import numpy as np
    a = np.asarray(roi, dtype=np.uint16)
    h, w = a.shape
    p = np.zeros((h + 2, w + 4), dtype=np.uint16)
    p[2:, 2:w + 2] = a
    ctx = np.zeros((h, w), dtype=np.uint16)
    for dy, dx in TEMPLATE:
        ctx = (ctx << 1) | p[2 + dy:2 + dy + h, 2 + dx:2 + dx + w]
    return ctx.flatten().tolist()


class _Encoder:
    """LZMA-style range encoder with 8-bit probabilities."""

    def __init__(self):
        self.low = 0
        self.range = _MASK32
        self.cache = 0
        self.cache_size = 1
        self.out = bytearray()

    def _shift_low(self):
        if self.low < 0xFF000000 or self.low > _MASK32:
            carry = self.low >> 32
            temp = self.cache
            while True:
                self.out.append((temp + carry) & 0xFF)
                temp = 0xFF
                self.cache_size -= 1
                if self.cache_size == 0:
                    break
            self.cache = (self.low >> 24) & 0xFF
        self.cache_size += 1
        self.low = (self.low << 8) & _MASK32

    def bit(self, value: int, p0: int):
        bound = (self.range >> 8) * p0
        if value:
            self.low += bound
            self.range -= bound
        else:
            self.range = bound
        while self.range < _TOP:
            self.range = (self.range << 8) & _MASK32
            self._shift_low()

    def finish(self) -> bytes:
        for _ in range(5):
            self._shift_low()
        out = bytes(self.out)
        # The first byte of an LZMA-style stream is always 0; the decoder does
        # not read it. Trailing zeros are dropped too: the decoder reads 0 past
        # the end of the payload.
        assert out[0] == 0, "range coder invariant: first byte is 0"
        return out[1:].rstrip(b"\x00")


def encode(roi, tbl: bytes | None = None) -> bytes:
    """Encode a ROI (2-D 0/1 array, row-major) with the frozen table."""
    import numpy as np
    tbl = tbl or table()
    bits = np.asarray(roi, dtype=np.uint8).flatten().tolist()
    enc = _Encoder()
    for value, c in zip(bits, contexts(roi)):
        enc.bit(value, tbl[c])
    return enc.finish()


def decode(payload: bytes, height: int, width: int, tbl: bytes | None = None):
    """Reference decoder, step for step what ``base/prc_codec.c`` does."""
    import numpy as np
    tbl = tbl or table()
    pos = 0

    def next_byte():
        nonlocal pos
        b = payload[pos] if pos < len(payload) else 0
        pos += 1
        return b

    rng, code = _MASK32, 0
    for _ in range(4):
        code = (code << 8) | next_byte()
    out = np.zeros((height + 2, width + 4), dtype=np.uint16)
    for y in range(height):
        for x in range(width):
            c = 0
            for dy, dx in TEMPLATE:
                c = (c << 1) | int(out[2 + y + dy, 2 + x + dx])
            bound = (rng >> 8) * tbl[c]
            if code < bound:
                rng = bound
                bit = 0
            else:
                code -= bound
                rng -= bound
                bit = 1
            while rng < _TOP:
                rng = (rng << 8) & _MASK32
                code = ((code << 8) | next_byte()) & _MASK32
            out[2 + y, 2 + x] = bit
    return out[2:, 2:width + 2].astype(bool)


def train(masks) -> bytes:
    """Build a table from 72x40 masks (each cropped to its ROI first).

    p0 = round(256 * (n0 + 0.5) / (n0 + n1 + 1)), clamped to 1..255, where
    n0/n1 count the 0/1 pixels seen in that context. Deterministic: the same
    masks in any order give the same table."""
    import numpy as np
    n = np.zeros((CONTEXTS, 2), dtype=np.int64)
    for m in masks:
        roi = crop_to_roi(m)
        if roi is None:
            continue
        bits = np.asarray(roi, dtype=np.uint8).flatten()
        ctx = np.asarray(contexts(roi), dtype=np.int64)
        np.add.at(n, (ctx, bits), 1)
    p0 = np.rint(256 * (n[:, 0] + 0.5) / (n.sum(axis=1) + 1))
    return bytes(np.clip(p0, 1, 255).astype(np.uint8).tolist())


def crop_to_roi(mask):
    """A 72x40 mask cropped to its ink bounding box, or None if it is empty."""
    import numpy as np
    m = np.asarray(mask, dtype=bool)
    rows, cols = np.any(m, axis=1), np.any(m, axis=0)
    if not rows.any():
        return None
    t, b = np.where(rows)[0][[0, -1]]
    l, r = np.where(cols)[0][[0, -1]]
    return m[t:b + 1, l:r + 1]


def pack_record(keycode: int, modifier: int, top: int, left: int,
                height: int, width: int, payload: bytes) -> bytes:
    """One cmd 41 record: the header bit field followed by ``payload``."""
    if not 0 < keycode <= 0xFF or not 0 <= modifier <= 0x0F:
        raise ValueError(f"address out of range: keycode {keycode}, modifier {modifier}")
    if not (0 < height and 0 < width and top + height <= 40 and left + width <= 72 and top >= 0 and left >= 0):
        raise ValueError(f"box outside the frame: {top},{left} {height}x{width}")
    if len(payload) > MAX_RECORD_PAYLOAD:
        raise ValueError(f"payload of {len(payload)} bytes exceeds the length field")
    f = modifier
    f = (f << 6) | top
    f = (f << 7) | left
    f = (f << 6) | (height - 1)
    f = (f << 7) | (width - 1)
    f = (f << 6) | len(payload)
    f <<= 4
    return bytes([keycode]) + f.to_bytes(5, "big") + bytes(payload)


def roi_box(mask):
    """(top, left, height, width) of a 72x40 mask's ink, or None if it is empty."""
    import numpy as np
    m = np.asarray(mask, dtype=bool)
    rows, cols = np.any(m, axis=1), np.any(m, axis=0)
    if not rows.any():
        return None
    t, b = (int(v) for v in np.where(rows)[0][[0, -1]])
    l, r = (int(v) for v in np.where(cols)[0][[0, -1]])
    return t, l, b - t + 1, r - l + 1


def parse_records(report: bytes):
    """Yield (keycode, modifier, top, left, height, width, payload) for each record
    in a cmd 41 report payload, the way the firmware's prc_parse_record() walks it:
    a keycode of 0, too few bytes for a header, or a malformed record ends it."""
    pos = 0
    while len(report) - pos >= RECORD_HDR and report[pos] != 0:
        f = int.from_bytes(report[pos + 1:pos + RECORD_HDR], "big")
        if f & 0x0F:
            return
        modifier, top = (f >> 36) & 0x0F, (f >> 30) & 0x3F
        left, height = (f >> 23) & 0x7F, ((f >> 17) & 0x3F) + 1
        width, n = ((f >> 10) & 0x7F) + 1, (f >> 4) & 0x3F
        if top + height > 40 or left + width > 72 or n > len(report) - pos - RECORD_HDR:
            return
        start = pos + RECORD_HDR
        yield report[pos], modifier, top, left, height, width, bytes(report[start:start + n])
        pos = start + n
