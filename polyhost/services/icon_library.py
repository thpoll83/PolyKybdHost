"""The overlay icon library ("PlyI", HID cmd 42, protocol v20).

Icons the overlay templates share live in the keyboard's flash (font-pack bundle
id 8). Instead of uploading such an icon's bitmap, the host sends a
``(pool slot, icon id)`` pair and each half draws the icon from its own flash.
Design: ``qmk_firmware/keyboards/polykybd/OVERLAY_ICON_LIBRARY_DESIGN.md``;
firmware: ``base/icon_lib.{c,h}``.

The FORMAT is a PlyF pack's byte layout with three differences, all mirrored
from ``base/icon_lib.h``:

- magic ``PlyI``, so neither loader can pick up the other's bundle;
- a record's ``first..last`` is a range of icon ids, contiguous from 0. There are
  several records only because ``GFXglyph.bitmapOffset`` is 16 bits;
- a glyph bitmap is row-major, MSB first, ``(w*h + 7) // 8`` bytes, and
  ``xOffset``/``yOffset`` are its top-left corner in the 72x40 keycap frame.

HOW THE HOST DECIDES TO FILL: by exact pixels. :func:`frame_index` renders every
glyph back into a 360-byte frame and maps those bytes to the id, and the send
path fills an image only when its packed bytes are a key of that map. So the
keyboard draws exactly what an upload would have drawn, by construction, and no
per-template sidecar has to stay in step with the templates.
"""
from __future__ import annotations

import binascii
import struct

MAGIC = b"PlyI"
ABI_VERSION = 2                  # FONTPACK_ABI_VERSION: the shared header layout
FRAME_W, FRAME_H = 72, 40
FRAME_BYTES = FRAME_W * FRAME_H // 8          # 360
BUNDLE_ID = 8                    # FONTPACK_ICONS_BUNDLE_ID (fontpack_layout.h)
MAX_RECORDS = 16                 # ICONLIB_MAX_RECORDS

_HDR = "<4sHHIIIIII"             # magic abi flags content_version font_count table_off total crc reserved
_REC = "<IIIIhH"                 # bitmap_off glyph_off first last yAdvance reserved
_GLYPH = "<Hbbbbbx"              # bitmapOffset width height xAdvance xOffset yOffset pad
HDR_SIZE = struct.calcsize(_HDR)
REC_SIZE = struct.calcsize(_REC)
GLYPH_SIZE = struct.calcsize(_GLYPH)
assert (HDR_SIZE, REC_SIZE, GLYPH_SIZE) == (32, 20, 8)


class IconLibraryError(ValueError):
    """The bytes are not a well-formed PlyI bundle."""


def _bbox(frame: bytes):
    """(x0, y0, w, h) of the set pixels of a packed 72x40 frame, or None."""
    xs, ys = [], []
    for bit in range(FRAME_W * FRAME_H):
        if frame[bit >> 3] & (0x80 >> (bit & 7)):
            ys.append(bit // FRAME_W)
            xs.append(bit % FRAME_W)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def _crop(frame: bytes, x0: int, y0: int, w: int, h: int) -> bytes:
    out = bytearray((w * h + 7) // 8)
    k = 0
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            bit = y * FRAME_W + x
            if frame[bit >> 3] & (0x80 >> (bit & 7)):
                out[k >> 3] |= 0x80 >> (k & 7)
            k += 1
    return bytes(out)


def build(frames: list[bytes], content_version: int) -> bytes:
    """Serialise packed 72x40 ``frames`` (icon id = list index) as a PlyI bundle.

    Byte-reproducible: the same frames and version give the same bytes."""
    if not frames:
        body = b""
        return struct.pack(_HDR, MAGIC, ABI_VERSION, 0, content_version, 0,
                           HDR_SIZE, HDR_SIZE, binascii.crc32(body) & 0xFFFFFFFF, 0)
    glyphs = []
    for i, f in enumerate(frames):
        if len(f) != FRAME_BYTES:
            raise IconLibraryError(f"icon {i}: frame is {len(f)} bytes, not {FRAME_BYTES}")
        box = _bbox(f)
        if box is None:
            raise IconLibraryError(f"icon {i}: frame has no set pixels")
        glyphs.append((box, _crop(f, *box)))

    # Records: contiguous id ranges, each bitmap blob within a 16-bit offset.
    ranges, lo, used = [], 0, 0
    for i, (_, bits) in enumerate(glyphs):
        if used + len(bits) > 0xFFFF:
            ranges.append((lo, i - 1))
            lo, used = i, 0
        used += len(bits)
    ranges.append((lo, len(glyphs) - 1))
    if len(ranges) > MAX_RECORDS:
        raise IconLibraryError(f"{len(ranges)} records exceed the firmware's {MAX_RECORDS}")

    out = bytearray(HDR_SIZE + len(ranges) * REC_SIZE)
    recs = []
    for first, last in ranges:
        while len(out) % 4:
            out.append(0)
        glyph_off = len(out)
        blob = bytearray()
        for (x0, y0, w, h), bits in glyphs[first:last + 1]:
            out += struct.pack(_GLYPH, len(blob), w, h, 0, x0, y0)
            blob += bits
        bitmap_off = len(out)
        out += blob
        recs.append(struct.pack(_REC, bitmap_off, glyph_off, first, last, 0, 0))
    while len(out) % 4:
        out.append(0)
    out[HDR_SIZE:HDR_SIZE + len(recs) * REC_SIZE] = b"".join(recs)
    crc = binascii.crc32(bytes(out[HDR_SIZE:])) & 0xFFFFFFFF
    out[:HDR_SIZE] = struct.pack(_HDR, MAGIC, ABI_VERSION, 0, content_version, len(recs),
                                 HDR_SIZE, len(out), crc, 0)
    return bytes(out)


def parse(data: bytes) -> tuple[int, list[bytes]]:
    """(content_version, frames) of a PlyI bundle, each frame the packed 72x40
    image the keyboard draws for that id. Applies the firmware's own checks."""
    data = bytes(data)
    if len(data) < HDR_SIZE:
        raise IconLibraryError("too small for a header")
    magic, abi, _flags, cver, n_rec, table_off, total, crc, _r = struct.unpack_from(_HDR, data)
    if magic != MAGIC:
        raise IconLibraryError(f"bad magic {magic!r}")
    if abi != ABI_VERSION or total != len(data):
        raise IconLibraryError("ABI or size mismatch")
    if binascii.crc32(data[HDR_SIZE:]) & 0xFFFFFFFF != crc:
        raise IconLibraryError("CRC mismatch")
    if n_rec == 0:
        return cver, []
    if table_off != HDR_SIZE or n_rec > MAX_RECORDS:
        raise IconLibraryError("bad record table")
    frames, nxt = [], 0
    for r in range(n_rec):
        bitmap_off, glyph_off, first, last, _ya, _res = struct.unpack_from(
            _REC, data, table_off + r * REC_SIZE)
        if first != nxt or last < first:
            raise IconLibraryError("records are not contiguous from id 0")
        for k in range(last - first + 1):
            # Bounds first, so a short bundle raises IconLibraryError (a
            # ValueError the callers catch), not struct.error or IndexError.
            if glyph_off + (k + 1) * GLYPH_SIZE > len(data):
                raise IconLibraryError(f"icon {first + k}: glyph table out of range")
            bofs, w, h, _xa, x0, y0 = struct.unpack_from(_GLYPH, data, glyph_off + k * GLYPH_SIZE)
            if w <= 0 or h <= 0 or x0 < 0 or y0 < 0 or x0 + w > FRAME_W or y0 + h > FRAME_H:
                raise IconLibraryError(f"icon {first + k}: box outside the keycap")
            end = bitmap_off + bofs + (w * h + 7) // 8
            if end > len(data):
                raise IconLibraryError(f"icon {first + k}: bitmap out of range")
            bits = data[bitmap_off + bofs:end]
            frame = bytearray(FRAME_BYTES)
            src = 0
            for y in range(h):
                for x in range(w):
                    if bits[src >> 3] & (0x80 >> (src & 7)):
                        bit = (y0 + y) * FRAME_W + x0 + x
                        frame[bit >> 3] |= 0x80 >> (bit & 7)
                    src += 1
            frames.append(bytes(frame))
        nxt = last + 1
    return cver, frames


def frame_index(data: bytes) -> tuple[int, dict[bytes, int]]:
    """(content_version, {packed frame: icon id}) for the send path."""
    cver, frames = parse(data)
    index: dict[bytes, int] = {}
    for i, f in enumerate(frames):
        index.setdefault(f, i)
    return cver, index
