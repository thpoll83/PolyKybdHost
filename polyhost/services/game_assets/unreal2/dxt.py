"""Decode the S3TC block formats DXT1, DXT3 and DXT5, and plain RGBA8, to RGBA.

Written from the format description in the DirectX documentation (BC1, BC2,
BC3); numpy only.
"""
from __future__ import annotations

import numpy as np


def _rgb565(c: np.ndarray) -> np.ndarray:
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return np.stack([r * 255 // 31, g * 255 // 63, b * 255 // 31], -1).astype(np.int32)


def _u16(a: np.ndarray, i: int) -> np.ndarray:
    return a[:, i].astype(np.int32) | (a[:, i + 1].astype(np.int32) << 8)


def _colour(col: np.ndarray, four: np.ndarray):
    """(rgb per pixel (n, 16, 3), index per pixel (n, 16)) of the 8-byte colour blocks."""
    c0, c1 = _u16(col, 0), _u16(col, 2)
    p0, p1 = _rgb565(c0), _rgb565(c1)
    four = four | (c0 > c1)
    p2 = np.where(four[:, None], (2 * p0 + p1) // 3, (p0 + p1) // 2)
    p3 = np.where(four[:, None], (p0 + 2 * p1) // 3, 0)
    pal = np.stack([p0, p1, p2, p3], 1)
    bits = sum(col[:, 4 + i].astype(np.uint32) << (8 * i) for i in range(4))
    idx = ((bits[:, None] >> (2 * np.arange(16, dtype=np.uint32))) & 3).astype(np.int64)
    return np.take_along_axis(pal, idx[:, :, None], 1), idx, four


def _alpha5(a: np.ndarray) -> np.ndarray:
    a0, a1 = a[:, 0].astype(np.int32), a[:, 1].astype(np.int32)
    bits = sum(a[:, 2 + i].astype(np.uint64) << np.uint64(8 * i) for i in range(6))
    idx = ((bits[:, None] >> (np.uint64(3) * np.arange(16, dtype=np.uint64))) & np.uint64(7)).astype(np.int64)
    eight = np.stack([a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)], 1)
    six = np.stack([a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)]
                   + [np.zeros_like(a0), np.full_like(a0, 255)], 1)
    return np.take_along_axis(np.where((a0 > a1)[:, None], eight, six), idx, 1)


def decode(fmt: str, w: int, h: int, data: bytes) -> np.ndarray:
    """An (h, w, 4) uint8 RGBA image."""
    if fmt == "RGBA8":                   # stored B, G, R, A
        need = w * h * 4
        if len(data) < need:
            raise ValueError(f"RGBA8 {w}x{h} needs {need} bytes, has {len(data)}")
        return np.frombuffer(data[:need], np.uint8).reshape(h, w, 4)[:, :, [2, 1, 0, 3]].copy()
    size = {"DXT1": 8, "DXT3": 16, "DXT5": 16}.get(fmt)
    if size is None:
        raise ValueError(f"texture format {fmt} is not read")
    bw, bh = (w + 3) // 4, (h + 3) // 4
    if len(data) < bw * bh * size:
        raise ValueError(f"{fmt} {w}x{h} needs {bw * bh * size} bytes, has {len(data)}")
    a = np.frombuffer(data[:bw * bh * size], np.uint8).reshape(bw * bh, size)
    rgb, idx, four = _colour(a[:, size - 8:], np.full(len(a), fmt != "DXT1"))
    if fmt == "DXT1":
        alpha = np.where(~four[:, None] & (idx == 3), 0, 255)
    elif fmt == "DXT3":
        nib = np.stack([a[:, :8] & 15, a[:, :8] >> 4], -1).reshape(len(a), 16)
        alpha = nib.astype(np.int32) * 17
    else:
        alpha = _alpha5(a)
    px = np.concatenate([rgb, alpha[:, :, None]], -1).astype(np.uint8)
    px = px.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
    return px[:h, :w].copy()
