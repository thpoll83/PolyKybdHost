"""Dune II (1992) PAK archives.

A PAK is a table of (32-bit offset, zero-terminated name) entries ended by a
zero offset, then the files; each file runs to the next one's offset, the
last to the end of the archive. The format is documented by the OpenDUNE and
Dune Legacy projects; the code here is written from those descriptions.
"""
from __future__ import annotations

import struct

MAX_ENTRIES = 4096                              # the game's largest PAK holds a few hundred


class Pak:
    """Name lookup without regard to case, as DOS did."""

    def __init__(self, data: bytes):
        self.data = data
        names, offsets, i = [], [], 0
        while True:
            off, = struct.unpack_from("<I", data, i)
            i += 4
            if off == 0:
                break
            end = data.index(b"\0", i)
            names.append(data[i:end].decode("ascii", "replace").lower())
            offsets.append(off)
            i = end + 1
            if len(names) > MAX_ENTRIES:
                raise ValueError(f"PAK table longer than {MAX_ENTRIES} entries")
        if any(not i <= o <= len(data) for o in offsets):
            raise ValueError("PAK offset before its table or past the end of the file")
        # A file ends where the next file starts. Some sound PAKs list one file
        # twice, so the next larger offset counts, not the next entry.
        starts = sorted(set(offsets)) + [len(data)]
        ends = {o: starts[k + 1] for k, o in enumerate(starts[:-1])}
        self.entries = {n: (o, ends[o]) for n, o in zip(names, offsets)}

    @classmethod
    def open(cls, path) -> Pak:
        with open(path, "rb") as f:
            return cls(f.read())

    def get(self, name: str) -> bytes | None:
        entry = self.entries.get(name.lower())
        return None if entry is None else self.data[entry[0]:entry[1]]
