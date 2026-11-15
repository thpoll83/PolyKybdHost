"""The game's text: ``Generals.csf`` (compiled) and ``Generals.str`` (plain).

A csf file starts with `` FSC``, a version, the label and string counts, a
reserved value and a language code (six 32-bit little-endian values in all).
Each label is `` LBL``, its string count, its name length and its ASCII name;
each string `` RTS`` (or ``WRTS``, which adds an ASCII value after it), its
length in UTF-16 units and the UTF-16LE text with every byte inverted. A .str
file holds ``LABEL`` lines, each followed by a quoted string and ``END``.
Format as read by ``GameText.cpp`` (EA's source release, 2025).
"""
from __future__ import annotations

import struct


def csf(data: bytes) -> dict:
    """{label: text} of a csf file; ValueError when it is not one."""
    if data[:4] != b" FSC" or len(data) < 24:
        raise ValueError("not a csf file")
    labels = struct.unpack("<I", data[8:12])[0]
    out, pos = {}, 24
    for _ in range(labels):
        if data[pos:pos + 4] != b" LBL":
            raise ValueError("csf: a label is damaged")
        count, length = struct.unpack("<II", data[pos + 4:pos + 12])
        name = data[pos + 12:pos + 12 + length].decode("latin-1")
        pos += 12 + length
        for i in range(count):
            kind = data[pos:pos + 4]
            if kind not in (b" RTS", b"WRTS"):
                raise ValueError("csf: a string is damaged")
            units = struct.unpack("<I", data[pos + 4:pos + 8])[0]
            raw = bytes(~b & 0xFF for b in data[pos + 8:pos + 8 + 2 * units])
            pos += 8 + 2 * units
            if kind == b"WRTS":
                extra = struct.unpack("<I", data[pos:pos + 4])[0]
                pos += 4 + extra
            if i == 0:
                out[name] = raw.decode("utf-16-le", errors="replace")
    return out


def str_file(text: str) -> dict:
    """{label: text} of a .str file."""
    out, label, parts = {}, None, []
    for raw in text.lstrip("﻿").splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if label is None:
            label, parts = line, []
        elif line.upper() == "END":
            out.setdefault(label, "".join(parts))
            label = None
        elif line.startswith('"'):
            parts.append(line.strip('"').replace("\\n", "\n"))
    return out


def hotkey(text: str) -> str | None:
    """The letter or digit after the first ``&`` in `text`, in capitals, or None."""
    i = text.find("&")
    if i < 0 or i + 1 >= len(text) or not text[i + 1].isascii() or not text[i + 1].isalnum():
        return None
    return text[i + 1].upper()
