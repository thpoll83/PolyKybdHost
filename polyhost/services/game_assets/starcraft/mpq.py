"""A reader for MPQ archives, format version 1 (StarCraft 1.16.1 and earlier).

Only what the StarCraft reader needs: the header, the encrypted hash and block
tables, encrypted files (with the FIX_KEY adjustment), the sector offset
table, single-unit files, and the compressions that hold graphics: PKWARE DCL
implode (``explode.py``), zlib and bzip2. Huffman and ADPCM compress only
sound and are refused.

The format is documented by the StormLib project (Ladislav Zezula) and the
"Inside MoPaQ" description by Justin Olbrantz and Jean-Francois Roy; the code
here is written from those descriptions, nothing is copied.

The archives are the user's own and are only ever read.
"""
from __future__ import annotations

import bz2
import os
import struct
import zlib
from pathlib import Path

from polyhost.services.game_assets.starcraft.explode import explode

MAGIC = b"MPQ\x1a"
USER_DATA = b"MPQ\x1b"

# Block flags.
IMPLODE = 0x00000100
COMPRESS = 0x00000200
ENCRYPTED = 0x00010000
FIX_KEY = 0x00020000
SINGLE_UNIT = 0x01000000
EXISTS = 0x80000000

# Compression mask bits of a COMPRESS sector.
HUFFMAN, ZLIB, PKWARE, BZIP2, ADPCM_MONO, ADPCM_STEREO = 0x01, 0x02, 0x08, 0x10, 0x40, 0x80

HASH_OFFSET, HASH_A, HASH_B, HASH_KEY = 0, 1, 2, 3
EMPTY, DELETED = 0xFFFFFFFF, 0xFFFFFFFE

# The largest file read: far above any graphic in the StarCraft archives. A
# damaged block entry may claim 4 GiB.
MAX_FILE = 32 * 1024 * 1024
MASK = 0xFFFFFFFF


def _crypt_table() -> list[int]:
    seed = 0x00100001
    table = [0] * 0x500
    for i in range(0x100):
        idx = i
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            hi = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            table[idx] = hi | (seed & 0xFFFF)
            idx += 0x100
    return table


CRYPT = _crypt_table()


def hash_string(name: str, kind: int) -> int:
    """The MPQ name hash of `kind`. Names are upper case with backslashes."""
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    for ch in name.upper().replace("/", "\\").encode("latin-1"):
        seed1 = (CRYPT[(kind << 8) + ch] ^ (seed1 + seed2)) & MASK
        seed2 = (ch + seed1 + seed2 + (seed2 << 5) + 3) & MASK
    return seed1


def decrypt(data: bytes, key: int) -> bytes:
    """Decrypt the whole 32-bit words of `data`; a tail of 1 to 3 bytes is
    stored plain."""
    n = len(data) // 4
    words = struct.unpack_from(f"<{n}I", data)
    out = []
    seed = 0xEEEEEEEE
    for w in words:
        seed = (seed + CRYPT[0x400 + (key & 0xFF)]) & MASK
        v = w ^ ((key + seed) & MASK)
        out.append(v)
        key = ((((~key) << 0x15) + 0x11111111) & MASK) | (key >> 0x0B)
        seed = (v + seed + (seed << 5) + 3) & MASK
    return struct.pack(f"<{n}I", *out) + data[n * 4:]


def encrypt(data: bytes, key: int) -> bytes:
    """The inverse of decrypt(); used to build archives in the tests."""
    n = len(data) // 4
    words = struct.unpack_from(f"<{n}I", data)
    out = []
    seed = 0xEEEEEEEE
    for v in words:
        seed = (seed + CRYPT[0x400 + (key & 0xFF)]) & MASK
        out.append(v ^ ((key + seed) & MASK))
        key = ((((~key) << 0x15) + 0x11111111) & MASK) | (key >> 0x0B)
        seed = (v + seed + (seed << 5) + 3) & MASK
    return struct.pack(f"<{n}I", *out) + data[n * 4:]


def file_key(name: str, offset: int, size: int, flags: int) -> int:
    """The key of an encrypted file: the hash of its name without the folder,
    adjusted by its offset and size when the block has FIX_KEY."""
    plain = name.replace("/", "\\").rsplit("\\", 1)[-1]
    key = hash_string(plain, HASH_KEY)
    if flags & FIX_KEY:
        key = ((key + offset) & MASK) ^ size
    return key


def decompress_sector(data: bytes, size: int, flags: int) -> bytes:
    """One sector (or a single-unit file) whose stored size is below `size`."""
    if flags & IMPLODE:                     # the old flag: PKWARE only, no mask byte
        out = explode(data, size)
    else:
        mask, out = data[0], data[1:]
        unknown = mask & ~(ZLIB | PKWARE | BZIP2)
        if unknown:
            raise ValueError(f"MPQ compression 0x{mask:02x} is not supported "
                             "(Huffman and ADPCM hold only sound)")
        # Undone in StormLib's order: bzip2, PKWARE, zlib.
        # Only the last step's output size is known; earlier steps are capped
        # at MAX_FILE so a damaged sector cannot expand without limit.
        last = next((m for m in (ZLIB, PKWARE, BZIP2) if mask & m), 0)
        if mask & BZIP2:
            out = bz2.BZ2Decompressor().decompress(out, (size if last == BZIP2 else MAX_FILE) + 1)
        if mask & PKWARE:
            out = explode(out, size if last == PKWARE else MAX_FILE)
        if mask & ZLIB:
            out = zlib.decompressobj().decompress(out, size + 1)
    if len(out) != size:
        raise ValueError(f"sector decompresses to {len(out)} bytes, not {size}")
    return out


# Bytes read at a time while looking for the header.
SCAN_CHUNK = 1024 * 1024


class Archive:
    """An MPQ archive: `get(name)` returns a file's bytes or None.

    `data` is the archive's bytes (the tests) or, from `open()`, its path. A
    path is read in parts: the header, the two tables, and each file asked
    for, so a 100 MB archive costs only its tables in memory. The file is
    opened for each read; no handle stays open."""

    def __init__(self, data, where: str = "MPQ"):
        if isinstance(data, (bytes, bytearray)):
            self.path, self.data, self.size = None, bytes(data), len(data)
        else:
            self.path, self.data = str(data), None
            self.size = os.path.getsize(self.path)
        self.where = where
        self.base = self._find_header()
        head = self._read(self.base, 32)
        if len(head) < 32:
            raise ValueError(f"{where}: the header runs past the end of the file")
        (_magic, _hsize, _asize, _version, shift, hash_pos, block_pos,
         hash_count, block_count) = struct.unpack_from("<4sIIHHIIII", head)
        self.sector = 512 << shift
        if hash_count == 0 or hash_count & (hash_count - 1):
            raise ValueError(f"{where}: hash table size {hash_count} is not a power of two")
        for pos, count in ((hash_pos, hash_count), (block_pos, block_count)):
            if self.base + pos + 16 * count > self.size:
                raise ValueError(f"{where}: a table runs past the end of the file")
        ht = decrypt(self._read(self.base + hash_pos, 16 * hash_count),
                     hash_string("(hash table)", HASH_KEY))
        bt = decrypt(self._read(self.base + block_pos, 16 * block_count),
                     hash_string("(block table)", HASH_KEY))
        self.hashes = [struct.unpack_from("<IIHHI", ht, 16 * i) for i in range(hash_count)]
        self.blocks = [struct.unpack_from("<IIII", bt, 16 * i) for i in range(block_count)]

    def _read(self, pos: int, n: int) -> bytes:
        """Up to `n` bytes at `pos`; fewer at the end of the archive."""
        if self.data is not None:
            return self.data[pos:pos + n]
        try:
            with open(self.path, "rb") as f:
                f.seek(pos)
                return f.read(n)
        except OSError as e:
            # A file that went away mid-build costs the key being drawn only.
            raise ValueError(f"{self.where}: {e}") from e

    def _find_header(self) -> int:
        """The archive's offset: at 0 or a multiple of 512 (an archive appended
        to a program), or where a user-data header points."""
        for start in range(0, max(self.size - 32, 0), SCAN_CHUNK):
            chunk = self._read(start, SCAN_CHUNK)
            for rel in range(0, len(chunk), 512):
                pos = start + rel
                if pos >= self.size - 32:
                    break
                magic = chunk[rel:rel + 4]
                if magic == MAGIC:
                    return pos
                if magic == USER_DATA and len(chunk) >= rel + 12:
                    (offset,) = struct.unpack_from("<I", chunk, rel + 8)
                    if self._read(pos + offset, 4) == MAGIC:
                        return pos + offset
        raise ValueError("not an MPQ archive")

    @classmethod
    def open(cls, path) -> Archive:
        return cls(Path(path), str(path))

    def _block(self, name: str):
        n = len(self.hashes)
        a, b = hash_string(name, HASH_A), hash_string(name, HASH_B)
        i = hash_string(name, HASH_OFFSET) & (n - 1)
        found = None
        for _ in range(n):
            ha, hb, locale, _platform, block = self.hashes[i]
            if block == EMPTY:
                break
            if block != DELETED and ha == a and hb == b and block < len(self.blocks):
                if locale == 0:
                    return self.blocks[block]
                found = found or self.blocks[block]   # another language: the fallback
            i = (i + 1) & (n - 1)
        return found

    def __contains__(self, name: str) -> bool:
        b = self._block(name)
        return b is not None and bool(b[3] & EXISTS)

    def get(self, name: str) -> bytes | None:
        block = self._block(name)
        if block is None or not block[3] & EXISTS:
            return None
        offset, csize, size, flags = block
        if size > MAX_FILE or csize > MAX_FILE:
            raise ValueError(f"{name} in {self.where} claims {size} bytes")
        start = self.base + offset
        raw = self._read(start, csize)
        if len(raw) != csize:
            raise ValueError(f"{name} runs past the end of {self.where}")
        key = file_key(name, offset, size, flags) if flags & ENCRYPTED else None
        if flags & SINGLE_UNIT:
            if key is not None:
                raw = decrypt(raw, key)
            return decompress_sector(raw, size, flags) if csize < size else raw[:size]
        count = -(-size // self.sector)
        if not flags & (COMPRESS | IMPLODE):
            out = bytearray()
            for i in range(count):
                s = raw[i * self.sector:(i + 1) * self.sector]
                out += decrypt(s, (key + i) & MASK) if key is not None else s
            return bytes(out[:size])
        table = raw[:4 * (count + 1)]
        if key is not None:
            table = decrypt(table, (key - 1) & MASK)
        offs = struct.unpack(f"<{count + 1}I", table)
        out = bytearray()
        for i in range(count):
            if not offs[i] <= offs[i + 1] <= csize:
                raise ValueError(f"{name} in {self.where}: bad sector table")
            s = raw[offs[i]:offs[i + 1]]
            if key is not None:
                s = decrypt(s, (key + i) & MASK)
            want = min(self.sector, size - i * self.sector)
            out += decompress_sector(s, want, flags) if len(s) < want else s[:want]
        return bytes(out)
