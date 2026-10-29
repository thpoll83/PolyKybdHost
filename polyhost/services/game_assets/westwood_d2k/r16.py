"""Dune 2000 (1998) R8 / R16 sprite files.

A file is a run of frames. A frame starts after any zero bytes with a type
byte, then width, height, x, y (32-bit), an image handle, a palette handle,
the bits per pixel (8 or 16), the frame height and width and a padding byte.
The pixels follow: palette indices at 8 bpp, RGB555 at 16 bpp. A type-1 frame
with a palette handle is followed by 8 bytes and its own 256-colour RGB555
palette, which later 8-bit frames use too. Index 0 is transparent, 1 the
shadow. The format is described by OpenRA's R8Loader; the code here is
written from that description.
"""
from __future__ import annotations

import struct

import numpy as np

HEADER = 1 + 24 + 4
MAX_FRAME_PIXELS = 640 * 400                    # as in westwood_td.westwood


def _rgb555(words: np.ndarray) -> np.ndarray:
    return (np.stack([(words >> 10) & 31, (words >> 5) & 31, words & 31], -1)
            .astype(np.uint16) * 255 // 31).astype(np.uint8)


class R16:
    """Frames by index. The file is indexed once; a frame is decoded when asked for."""

    def __init__(self, data: bytes, palette: bytes | None = None):
        self.data = data
        self.base_pal = None if palette is None else (
            np.frombuffer(palette[:768], np.uint8).reshape(256, 3).astype(np.uint16) * 255 // 63
        ).astype(np.uint8)
        self.index = []                         # (pixel offset, w, h, bpp, palette offset or None)
        pal_at, i, n = None, 0, len(data)
        while i < n:
            while i < n and data[i] == 0:
                i += 1
            if i + HEADER > n:
                break
            typ = data[i]
            w, h, _x, _y, _image, pal_handle = struct.unpack_from("<iiiiIi", data, i + 1)
            bpp = data[i + 25]
            if bpp not in (8, 16) or w < 0 or h < 0 or w * h > MAX_FRAME_PIXELS:
                raise ValueError(f"frame {len(self.index)}: {w}x{h} at {bpp} bpp")
            px = i + HEADER
            i = px + w * h * bpp // 8
            if typ == 1 and pal_handle != 0:
                pal_at = i + 8
                i = pal_at + 512
            if i > n:
                raise ValueError(f"frame {len(self.index)} runs past the end of the file")
            self.index.append((px, w, h, bpp, pal_at))

    def __len__(self):
        return len(self.index)

    def frame(self, k: int):
        """(rgb (h, w, 3) uint8, cover (h, w) bool) of frame `k`; IndexError past the end."""
        px, w, h, bpp, pal_at = self.index[k]
        if bpp == 16:
            words = np.frombuffer(self.data, "<u2", w * h, px).reshape(h, w)
            return _rgb555(words), words != 0
        idx = np.frombuffer(self.data, np.uint8, w * h, px).reshape(h, w)
        if pal_at is not None:
            pal = _rgb555(np.frombuffer(self.data, "<u2", 256, pal_at))
        elif self.base_pal is not None:
            pal = self.base_pal
        else:
            raise ValueError(f"frame {k} has no palette")
        return pal[idx], (idx != 0) & (idx != 1)
