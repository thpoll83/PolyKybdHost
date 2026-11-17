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
    """{label: text} of a csf file; ValueError when it is not one or is cut off."""
    try:
        return _csf(data)
    except struct.error as e:
        raise ValueError(f"csf: a record is cut off ({e})") from e


def _csf(data: bytes) -> dict:
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
            if pos + 8 + 2 * units > len(data):
                raise ValueError("csf: a string is cut off")
            raw = bytes(~b & 0xFF for b in data[pos + 8:pos + 8 + 2 * units])
            pos += 8 + 2 * units
            if kind == b"WRTS":
                extra = struct.unpack("<I", data[pos:pos + 4])[0]
                pos += 4 + extra
            if i == 0:
                out[name] = raw.decode("utf-16-le", errors="replace")
    return out


def str_file(text: str) -> dict:
    """{label: text} of a .str file. As the game's ``readToEndOfQuote``: a
    quoted value runs on over line ends until a quote that no backslash
    escapes, and each line end in it becomes a space. A label keeps its first
    string."""
    out, label = {}, None
    lines = text.lstrip("\ufeff").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("//"):
            continue
        if label is None:
            label = line
            continue
        if line.upper() == "END":
            label = None
            continue
        if not line.startswith('"'):
            continue
        rest, value, slash = line[1:], [], False
        while True:
            closed = False
            for ch in rest:
                if ch == '"' and not slash:
                    closed = True
                    break
                slash = ch == "\\" and not slash
                value.append(ch)
            if closed or i >= len(lines):
                break
            value.append(" ")
            rest, slash = lines[i], False
            i += 1
        out.setdefault(label, "".join(value))
    return out


def hotkey(text: str) -> str | None:
    """The letter or digit after the first ``&`` in `text`, in capitals, or None."""
    i = text.find("&")
    if i < 0 or i + 1 >= len(text) or not text[i + 1].isascii() or not text[i + 1].isalnum():
        return None
    return text[i + 1].upper()
