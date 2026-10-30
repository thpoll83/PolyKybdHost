"""StarCraft 1 sprite (GRP) and palette (WPE) files.

A GRP file is a frame count, the largest frame width and height (u16 each),
then per frame an 8-byte entry: x and y offset of the frame inside that
largest box, width and height (u8 each) and the offset of the frame's line
table (u32). The line table holds one u16 per row, the offset of that row's
data from the line table. A row is run-length coded:

- a byte with bit 7 set skips (byte & 0x7F) transparent pixels;
- a byte with bit 6 set repeats the next byte (byte & 0x3F) times;
- any other byte copies that many following bytes.

A WPE file (``tileset\\*.wpe``) is a palette: 256 entries of red, green, blue
and an unused byte. OpenBW reads it the same way (ui/ui.h, ``Tileset/%s.wpe``).

The format is documented by the StarCraft modding community (the Staredit
Network wiki and the PyMS and OpenBW sources); the code here is written from
those descriptions, nothing is copied.
"""
from __future__ import annotations

import struct

import numpy as np

# The largest frame decoded. GRP frame sizes are u8, so 255 x 255 is the most a
# header can claim; a whole GRP may claim 65535 frames, so frames are decoded
# only when asked for.
MAX_FRAMES = 4096


def frame_count(data: bytes) -> int:
    return struct.unpack_from("<H", data, 0)[0]


def frame(data: bytes, index: int) -> np.ndarray:
    """Frame `index` as an (h, w) array of palette indices in the GRP's full
    box, 0 where transparent. IndexError past the last frame, ValueError on a
    damaged frame."""
    count, w, h = struct.unpack_from("<HHH", data, 0)
    if not 0 <= index < min(count, MAX_FRAMES):
        raise IndexError(f"frame {index} of {count}")
    x, y, fw, fh, off = struct.unpack_from("<BBBBI", data, 6 + 8 * index)
    out = np.zeros((max(h, y + fh), max(w, x + fw)), np.uint8)
    for row in range(fh):
        (rel,) = struct.unpack_from("<H", data, off + 2 * row)
        i, px = off + rel, 0
        line = bytearray(fw)
        while px < fw:
            if i >= len(data):
                raise ValueError(f"frame {index}: row {row} runs past the end of the file")
            b = data[i]
            i += 1
            if b & 0x80:                        # transparent run
                px += b & 0x7F
            elif b & 0x40:                      # one colour repeated
                n = b & 0x3F
                line[px:px + n] = bytes([data[i]]) * n
                i += 1
                px += n
            else:                               # literal pixels
                line[px:px + b] = data[i:i + b]
                i += b
                px += b
        if len(line) != fw:
            raise ValueError(f"frame {index}: row {row} is longer than the frame")
        out[y + row, x:x + fw] = np.frombuffer(bytes(line), np.uint8)
    return out


def wpe_palette(data: bytes) -> np.ndarray:
    """(256, 3) uint8 RGB from a WPE file."""
    if len(data) < 1024:
        raise ValueError(f"a WPE palette is 1024 bytes, not {len(data)}")
    return np.frombuffer(data[:1024], np.uint8).reshape(256, 4)[:, :3].copy()
