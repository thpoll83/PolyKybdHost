"""A reader for Unreal Engine 2 packages (UT2004 .utx textures, .u code).

Only what the UT2004 reader needs: the header, the name, import and export
tables, an export's tagged properties, the first mip of a texture, and the
default properties of a class found by their property tag.

The format is described by the Unreal Wiki ("Package File Format") and the
UTPT / UE Explorer documentation; the code here is written from those
descriptions, nothing is copied. Tested on UT2004 3369 files (package
version 128 for .u, 127 for .utx).

The packages are the user's own and are only ever read.
"""
from __future__ import annotations

import os
import struct
from pathlib import Path

TAG = 0x9E2A83C1

# The largest package read. HudContent.utx is about 0.8 MB and XWeapons.u
# about 5 MB; the biggest stock texture packages are near 60 MB.
MAX_PACKAGE = 128 * 1024 * 1024

# Property types (the low 4 bits of a tag's info byte).
BYTE, INT, BOOL, FLOAT, OBJECT, NAME, STRUCT = 1, 2, 3, 4, 5, 6, 10

# Texture formats (UT2004's ETextureFormat).
TEXF = {0: "P8", 1: "RGBA7", 2: "RGB16", 3: "DXT1", 4: "RGB8", 5: "RGBA8",
        7: "DXT3", 8: "DXT5", 9: "L8"}

RF_HAS_STACK = 0x02000000


def compact(b: bytes, p: int) -> tuple[int, int]:
    """The compact index at `p`: (value, position after it). The first byte
    holds the sign (bit 7), a continue flag (bit 6) and 6 value bits; each
    further byte a continue flag (bit 7) and 7 value bits."""
    first = b[p]
    p += 1
    v = first & 0x3F
    if first & 0x40:
        shift = 6
        for _ in range(4):
            x = b[p]
            p += 1
            v |= (x & 0x7F) << shift
            shift += 7
            if not x & 0x80:
                break
    return (-v if first & 0x80 else v), p


def encode_compact(v: int) -> bytes:
    """The inverse of compact(); used to search for a property tag and by the tests."""
    neg, v = v < 0, abs(v)
    out = bytearray([(v & 0x3F) | (0x80 if neg else 0) | (0x40 if v > 0x3F else 0)])
    v >>= 6
    while v:
        out.append((v & 0x7F) | (0x80 if v > 0x7F else 0))
        v >>= 7
    return bytes(out)


class Package:
    """One package, read whole (they are small). `where` names it in errors."""

    def __init__(self, data: bytes, where: str = "package"):
        self.b, self.where = data, where
        if len(data) < 36:
            raise ValueError(f"{where}: too short for a package header")
        (tag, self.version, _lic, _flags, nn, no, ne, eo, ni, io) = struct.unpack_from("<IHHIiiiiii", data)
        if tag != TAG:
            raise ValueError(f"{where}: not an Unreal package")
        for count, pos in ((nn, no), (ne, eo), (ni, io)):
            if count < 0 or not 0 <= pos <= len(data):
                raise ValueError(f"{where}: a table lies outside the file")
        try:
            self.names = self._names(nn, no)
            self.imports = self._imports(ni, io)
            self.exports = self._exports(ne, eo)
        except (IndexError, struct.error) as e:
            raise ValueError(f"{where}: a table runs past the end of the file") from e

    @classmethod
    def open(cls, path) -> Package:
        size = os.path.getsize(path)
        if size > MAX_PACKAGE:
            raise ValueError(f"{Path(path).name} is {size} bytes, more than a package this reader opens")
        with open(path, "rb") as f:
            return cls(f.read(), Path(path).name)

    # -- tables -------------------------------------------------------------- #

    def _names(self, n, p):
        out = []
        for _ in range(n):
            size, p = compact(self.b, p)
            if size <= 0:
                raise ValueError(f"{self.where}: bad name entry")
            out.append(self.b[p:p + size - 1].decode("latin-1"))
            p += size + 4                       # the text, its 0 byte, the flags
        return out

    def _imports(self, n, p):
        out = []
        for _ in range(n):
            _cls_pkg, p = compact(self.b, p)
            cls, p = compact(self.b, p)
            (outer,) = struct.unpack_from("<i", self.b, p)
            name, p = compact(self.b, p + 4)
            out.append((self.names[cls], outer, self.names[name]))
        return out

    def _exports(self, n, p):
        out = []
        for _ in range(n):
            cls, p = compact(self.b, p)
            _super, p = compact(self.b, p)
            (outer,) = struct.unpack_from("<i", self.b, p)
            name, p = compact(self.b, p + 4)
            (flags,) = struct.unpack_from("<I", self.b, p)
            size, p = compact(self.b, p + 4)
            off = 0
            if size > 0:
                off, p = compact(self.b, p)
                if off < 0 or off + size > len(self.b):
                    raise ValueError(f"{self.where}: an object lies outside the file")
            out.append({"cls": cls, "outer": outer, "name": self.names[name],
                        "flags": flags, "size": size, "off": off})
        return out

    # -- names of objects ---------------------------------------------------- #

    def ref_name(self, i: int) -> str | None:
        if i > 0:
            return self.exports[i - 1]["name"]
        if i < 0:
            return self.imports[-i - 1][2]
        return None

    def path(self, i: int) -> str:
        """The dotted path of an object reference, the package itself left out
        for an export (``Generic.HUD``) and kept for an import
        (``HUDContent.Generic.HUD``)."""
        parts = []
        for _ in range(64):                     # a damaged outer chain cannot loop for ever
            if i > 0:
                e = self.exports[i - 1]
                parts.append(e["name"])
                i = e["outer"]
            elif i < 0:
                _cls, outer, name = self.imports[-i - 1]
                parts.append(name)
                i = outer
            else:
                break
        return ".".join(reversed(parts))

    def class_of(self, e: dict) -> str:
        return self.ref_name(e["cls"]) or "Class"

    def export(self, path: str, cls: str | None = None) -> dict | None:
        """The export at `path` (case ignored), of class `cls` when given."""
        want = path.lower()
        for i, e in enumerate(self.exports):
            if self.path(i + 1).lower() == want and (cls is None or self.class_of(e) == cls):
                return e
        return None

    # -- properties ---------------------------------------------------------- #

    def properties(self, data: bytes, p: int, end: int) -> tuple[dict, int]:
        """The tagged properties at `p`, up to the None tag: ({name: value},
        position after the None tag). A struct of tagged properties (IntBox)
        is read as a dict; other structs stay bytes."""
        out = {}
        while True:
            if p >= end:
                raise ValueError(f"{self.where}: properties run past their object")
            ni, p = compact(data, p)
            name = self.names[ni]
            if name == "None":
                return out, p
            info = data[p]
            p += 1
            kind, size_code, flag = info & 0x0F, (info >> 4) & 7, info & 0x80
            if kind == STRUCT:
                _sn, p = compact(data, p)
            size = (1, 2, 4, 12, 16)[size_code] if size_code < 5 else None
            if size_code == 5:
                size, p = data[p], p + 1
            elif size_code == 6:
                (size,) = struct.unpack_from("<H", data, p)
                p += 2
            elif size_code == 7:
                (size,) = struct.unpack_from("<i", data, p)
                p += 4
            index = 0
            if flag and kind != BOOL:
                x = data[p]
                p += 1
                if x & 0xC0 == 0xC0:
                    index = ((x & 0x3F) << 24) | int.from_bytes(data[p:p + 3], "big")
                    p += 3
                elif x & 0x80:
                    index = ((x & 0x7F) << 8) | data[p]
                    p += 1
                else:
                    index = x
            raw = data[p:p + size]
            p += size
            if kind == BOOL:
                value = bool(flag)
            elif kind == BYTE:
                value = raw[0]
            elif kind == INT:
                (value,) = struct.unpack("<i", raw)
            elif kind == FLOAT:
                (value,) = struct.unpack("<f", raw)
            elif kind == OBJECT:
                value = self.path(compact(raw, 0)[0])
            elif kind == NAME:
                value = self.names[compact(raw, 0)[0]]
            elif kind == STRUCT:
                try:
                    value, used = self.properties(raw, 0, len(raw))
                    if used != len(raw):
                        value = raw
                except (ValueError, IndexError, struct.error):
                    value = raw
            else:
                value = raw
            out[f"{name}[{index}]" if index else name] = value

    def class_default(self, cls_name: str, prop: str):
        """One default property of class `cls_name`, or None.

        A class keeps its defaults after its compiled script, which this reader
        does not parse. The tag of `prop` (its name and a struct, int, byte or
        object type) is searched for in the class's data instead; the first
        tag that reads as a whole property is taken. Stock UT2004 weapon
        classes have one IconCoords tag each."""
        e = next((e for e in self.exports
                  if e["name"].lower() == cls_name.lower() and self.class_of(e) == "Class"), None)
        if e is None or prop not in self.names or "None" not in self.names:
            return None
        data = self.b[e["off"]:e["off"] + e["size"]]
        key = encode_compact(self.names.index(prop))
        start = 0
        while (p := data.find(key, start)) >= 0:
            start = p + 1
            if p + len(key) >= len(data):
                break
            info = data[p + len(key)]
            if info & 0x0F not in (BYTE, INT, OBJECT, STRUCT):
                continue
            try:
                props, _ = self.properties(data + encode_compact(self.names.index("None")), p,
                                           len(data) + 8)
            except (ValueError, IndexError, struct.error):
                continue
            if prop in props:
                return props[prop]
        return None

    # -- textures ------------------------------------------------------------ #

    def texture(self, path: str) -> tuple[str, int, int, bytes]:
        """(format, width, height, data) of the first mip of the texture at `path`."""
        e = self.export(path, "Texture")
        if e is None:
            raise KeyError(f"no texture {path} in {self.where}")
        p, end = e["off"], e["off"] + e["size"]
        if e["flags"] & RF_HAS_STACK:
            raise ValueError(f"{path} in {self.where} has a script stack")
        props, p = self.properties(self.b, p, end)
        fmt = TEXF.get(props.get("Format", 0), f"format {props.get('Format')}")
        count, p = compact(self.b, p)
        if not 1 <= count <= 16:
            raise ValueError(f"{path} in {self.where}: {count} mips")
        p += 4                                   # the offset just past the mip's data
        size, p = compact(self.b, p)
        if size < 0 or p + size + 8 > end:
            raise ValueError(f"{path} in {self.where}: the mip runs past its object")
        data = self.b[p:p + size]
        w, h = struct.unpack_from("<ii", self.b, p + size)
        if not (0 < w <= 4096 and 0 < h <= 4096):
            raise ValueError(f"{path} in {self.where}: mip size {w}x{h}")
        return fmt, w, h, data
