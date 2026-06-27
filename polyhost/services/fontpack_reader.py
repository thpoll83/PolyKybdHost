"""Decode a "PlyF" font-pack bundle into renderable GFX fonts — offline, host-side.

This is the read half that the host was missing.  `polyhost/device/hid_fontpack.py`
only ever validated the 32-byte *header* (it ships the blob to the keyboard and lets
the firmware unpack it); `qmk_firmware/.../fonts/fontpack.py` `parse_pack()` decodes
the font *table* but stops there (it never reads the glyph arrays or bitmaps).  To
*inspect* a bundle on the host — show every glyph exactly as the keycap OLED draws
it — we need the full body: header → font table → per-font glyph arrays → per-font
1-bit bitmap blobs.

The output `PackFont` is field-compatible with ``tools/gfx_font.GfxFont`` (name,
bitmap, glyphs[list of dict], first, last, yAdvance) so the existing pixel-exact
renderer (`GfxGlyphRenderer._blit`) draws a pack glyph with zero changes.  Each font
also carries its **global ALL_FONTS index** (the per-record ``reserved`` u16 the
build writes), so several bundles can be merge-sorted back into the firmware's true
front-to-back priority order — the same thing `fontpack_assemble()` does on-device.

Pure stdlib (struct/binascii/dataclasses); no PIL, no Qt — safe to import anywhere.
The binary format is the contract documented in ``base/fontpack.h`` /
``fonts/fontpack.py``; keep this decoder in lockstep with that serializer.
"""
from __future__ import annotations

import binascii
import struct
from dataclasses import dataclass, field

MAGIC = b"PlyF"
ABI_VERSION = 1
HEADER_SIZE = 32
FONT_REC_SIZE = 20
GLYPH_REC_SIZE = 8

_HEADER_FMT = "<4sHHIIIIII"  # magic, abi, flags, content_ver, count, table_off, total, crc, reserved
_FONT_FMT = "<IIIIhH"        # bitmap_off, glyph_off, first, last, yAdvance(i16), global_index(u16)
_GLYPH_FMT = "<Hbbbbbx"      # bitmapOffset(u16), w, h, xAdvance, xOffset, yOffset (i8), pad

assert struct.calcsize(_HEADER_FMT) == HEADER_SIZE
assert struct.calcsize(_FONT_FMT) == FONT_REC_SIZE
assert struct.calcsize(_GLYPH_FMT) == GLYPH_REC_SIZE


@dataclass
class PackFont:
    """A single GFX font decoded from a pack — shape-compatible with gfx_font.GfxFont."""
    name: str
    bitmap: bytes
    glyphs: list           # list of dict(bitmapOffset,width,height,xAdvance,xOffset,yOffset)
    first: int
    last: int
    yAdvance: int
    global_index: int = 0  # position in the full ALL_FONTS priority order (record `reserved`)

    @property
    def glyph_count(self) -> int:
        return self.last - self.first + 1

    def covers(self, cp: int) -> bool:
        return self.first <= cp <= self.last

    def bitmap_content_len(self) -> int:
        """Raw bitmap length (no inter-font padding) — the sum of the per-glyph
        byte-padded bitmaps.  decode_pack's `bitmap` slice includes 4-align padding
        up to the next font; the writer trims to this so re-encoding is faithful."""
        end = 0
        for g in self.glyphs:
            if g["width"] and g["height"]:
                end = max(end, g["bitmapOffset"] + (g["width"] * g["height"] + 7) // 8)
        return end


@dataclass
class Pack:
    """A decoded bundle: header fields + every font with its glyphs and bitmaps."""
    abi_version: int
    content_version: int
    font_count: int
    total_size: int
    crc32: int
    crc_ok: bool
    fonts: list = field(default_factory=list)   # list[PackFont]

    def codepoint_count(self) -> int:
        return sum(f.glyph_count for f in self.fonts)


class PackDecodeError(ValueError):
    """Raised when bytes are not a well-formed PlyF pack."""


def decode_pack(data, name_hint: str = "") -> Pack:
    """Decode a full PlyF pack (header + table + glyph arrays + bitmaps).

    `name_hint` (e.g. the bundle id) is used to label fonts that have no symbol
    name available — they become ``<hint>#<global_index>`` so the UI has something
    readable.  Raises `PackDecodeError` on any structural problem.
    """
    data = bytes(data)
    if len(data) < HEADER_SIZE:
        raise PackDecodeError(f"too small ({len(data)} bytes) to be a font pack")
    (magic, abi, _flags, content_ver, count,
     table_off, total, crc, _res) = struct.unpack_from(_HEADER_FMT, data, 0)
    if magic != MAGIC:
        raise PackDecodeError(f"bad magic {magic!r} (expected {MAGIC!r})")
    if total != len(data):
        raise PackDecodeError(f"total_size {total} != file size {len(data)}")
    crc_ok = (binascii.crc32(data[HEADER_SIZE:]) & 0xFFFFFFFF) == crc

    # Pass 1: read the font table (the bitmap_off values double as block boundaries).
    recs = []
    for i in range(count):
        base = table_off + i * FONT_REC_SIZE
        if base + FONT_REC_SIZE > len(data):
            raise PackDecodeError(f"font table entry {i} runs past end of pack")
        boff, goff, first, last, yadv, gidx = struct.unpack_from(_FONT_FMT, data, base)
        if last < first:
            raise PackDecodeError(f"font {i}: last 0x{last:X} < first 0x{first:X}")
        recs.append((boff, goff, first, last, yadv, gidx))

    # A font's bitmap blob runs from its bitmap_off to the next-higher bitmap_off
    # (blocks are laid out sequentially, 4-aligned), or to total_size for the last.
    bitmap_starts = sorted(r[0] for r in recs)

    def bitmap_end(start: int) -> int:
        for s in bitmap_starts:
            if s > start:
                return s
        return total

    fonts = []
    for i, (boff, goff, first, last, yadv, gidx) in enumerate(recs):
        gcount = last - first + 1
        gend = goff + gcount * GLYPH_REC_SIZE
        if not (HEADER_SIZE <= goff and gend <= len(data)):
            raise PackDecodeError(f"font {i}: glyph block [{goff}:{gend}] out of bounds")
        glyphs = []
        for gi in range(gcount):
            bo, w, h, xadv, xoff, yoff = struct.unpack_from(_GLYPH_FMT, data, goff + gi * GLYPH_REC_SIZE)
            glyphs.append(dict(bitmapOffset=bo, width=w, height=h,
                               xAdvance=xadv, xOffset=xoff, yOffset=yoff))
        bstart, bstop = boff, bitmap_end(boff)
        if not (HEADER_SIZE <= bstart <= bstop <= len(data)):
            raise PackDecodeError(f"font {i}: bitmap block [{bstart}:{bstop}] out of bounds")
        name = name_hint and f"{name_hint}#{gidx}" or f"font{i}#{gidx}"
        fonts.append(PackFont(name=name, bitmap=data[bstart:bstop], glyphs=glyphs,
                              first=first, last=last, yAdvance=yadv, global_index=gidx))

    return Pack(abi_version=abi, content_version=content_ver, font_count=count,
                total_size=total, crc32=crc, crc_ok=crc_ok, fonts=fonts)


def decode_pack_file(path, name_hint: str = "") -> Pack:
    with open(path, "rb") as f:
        return decode_pack(f.read(), name_hint or _stem(path))


def _align4(n: int) -> int:
    return (n + 3) & ~3


def encode_pack(fonts, content_version: int = 0, abi_version: int = ABI_VERSION) -> bytes:
    """Serialize fonts → a "PlyF" pack, byte-identical to the firmware/build
    serializer (fonts/fontpack.py serialize_pack): header, font table (with each
    font's global ALL_FONTS index in the record `reserved`), 4-aligned glyph
    arrays, 4-aligned bitmap blobs.  `fonts` is any iterable of PackFont.

    decode_pack(encode_pack(p.fonts, p.content_version)) reproduces p, and for a
    pack decoded from disk, encode reproduces the original bytes exactly."""
    fonts = list(fonts)
    n = len(fonts)
    table_off = HEADER_SIZE
    glyph_blocks, bitmap_blocks = [], []
    cur = table_off + n * FONT_REC_SIZE
    glyph_offs = []
    for f in fonts:
        glyph_offs.append(cur)
        blob = b"".join(struct.pack(_GLYPH_FMT, g["bitmapOffset"], g["width"],
                                    g["height"], g["xAdvance"], g["xOffset"],
                                    g["yOffset"]) for g in f.glyphs)
        glyph_blocks.append(blob)
        cur = _align4(cur + len(blob))
    bitmap_offs = []
    for f in fonts:
        bitmap_offs.append(cur)
        blob = f.bitmap[:f.bitmap_content_len()]   # trim inter-font padding
        bitmap_blocks.append(blob)
        cur = _align4(cur + len(blob))
    total_size = cur

    table = b"".join(struct.pack(_FONT_FMT, bitmap_offs[i], glyph_offs[i],
                                 f.first, f.last, f.yAdvance, f.global_index)
                     for i, f in enumerate(fonts))
    body = bytearray(total_size - HEADER_SIZE)

    def place(off, blob):
        body[off - HEADER_SIZE:off - HEADER_SIZE + len(blob)] = blob
    place(table_off, table)
    for off, blob in zip(glyph_offs, glyph_blocks):
        place(off, blob)
    for off, blob in zip(bitmap_offs, bitmap_blocks):
        place(off, blob)

    crc = binascii.crc32(bytes(body)) & 0xFFFFFFFF
    header = struct.pack(_HEADER_FMT, MAGIC, abi_version, 0, content_version,
                         n, table_off, total_size, crc, 0)
    return header + bytes(body)


def splice_font(pack: Pack, new_font: PackFont) -> list:
    """Return `pack`'s fonts with `new_font` replacing the one at the same
    global_index (or inserted in global-index order if none matches) — the core
    of the font-pack *extend* path.  Caller re-encodes with encode_pack()."""
    out = [f for f in pack.fonts if f.global_index != new_font.global_index]
    out.append(new_font)
    out.sort(key=lambda f: f.global_index)
    return out


def merge_fonts(packs) -> list:
    """Merge the fonts of several packs into global ALL_FONTS priority order.

    Mirrors the firmware's `fontpack_assemble()` merge-sort: every present
    bundle's fonts are interleaved by their global index, so a front-to-back
    lookup over the result resolves overlapping ranges exactly as the keyboard
    does.  `packs` is any iterable of `Pack`.
    """
    allf = [f for p in packs for f in p.fonts]
    allf.sort(key=lambda f: f.global_index)
    return allf


def _stem(path) -> str:
    import os
    return os.path.splitext(os.path.basename(str(path)))[0]
