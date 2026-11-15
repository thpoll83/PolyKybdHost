"""BIG archives of Command & Conquer Generals and Zero Hour (``BIGF``).

A header of ``BIGF`` (``BIG4`` in some releases), the archive size
(little-endian) and the entry count and first data offset (big-endian), then
one entry per file: its offset and size (big-endian) and its path, ended by a
zero byte. Paths use backslashes; the game compares them without regard to
case. Format as read by the game's ``Win32BIGFileSystem.cpp`` (EA's source
release of Generals and Zero Hour, 2025).
"""
from __future__ import annotations

import struct
from pathlib import Path

MAX_ENTRIES = 100_000            # the largest index read; a Zero Hour archive has under 20 000
MAX_INDEX = 16 * 1024 * 1024     # the largest index, in bytes


class Archive:
    def __init__(self, path, entries: dict):
        self.path = Path(path)
        self.entries = entries   # {lower-case path: (offset, size)}

    @classmethod
    def open(cls, path) -> Archive:
        """Read the index of the archive at `path`; ValueError when it is not one."""
        with open(path, "rb") as f:
            head = f.read(16)
            if len(head) < 16 or head[:4] not in (b"BIGF", b"BIG4"):
                raise ValueError(f"{Path(path).name} is not a BIG archive")
            count, first = struct.unpack(">II", head[8:16])
            if count > MAX_ENTRIES or not 16 <= first <= MAX_INDEX:
                raise ValueError(f"{Path(path).name} has an index this reader does not open")
            index = f.read(first - 16)
        entries, pos = {}, 0
        for _ in range(count):
            if pos + 8 > len(index):
                raise ValueError(f"{Path(path).name}: the index is cut off")
            offset, size = struct.unpack(">II", index[pos:pos + 8])
            end = index.find(b"\0", pos + 8)
            if end < 0:
                raise ValueError(f"{Path(path).name}: the index is cut off")
            name = index[pos + 8:end].decode("latin-1").replace("/", "\\").lower()
            entries.setdefault(name, (offset, size))
            pos = end + 1
        return cls(path, entries)

    def names(self) -> list[str]:
        return list(self.entries)

    def get(self, name: str, limit: int | None = None) -> bytes | None:
        """The bytes of `name` (any case, either slash), or None when it is not
        in the archive. ValueError for a file larger than `limit`."""
        entry = self.entries.get(name.replace("/", "\\").lower())
        if entry is None:
            return None
        offset, size = entry
        if limit is not None and size > limit:
            raise ValueError(f"{name} is larger than this reader opens")
        with open(self.path, "rb") as f:
            f.seek(offset)
            data = f.read(size)
        if len(data) != size:
            raise ValueError(f"{name} is cut off in {self.path.name}")
        return data
