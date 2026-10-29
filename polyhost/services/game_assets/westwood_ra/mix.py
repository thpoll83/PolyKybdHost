"""Red Alert (1996) MIX archives, as OpenRA installs them.

A Red Alert MIX starts with a zero word and a flags word. With flag 0x20000 the
header (count, body size, entries) is Blowfish-encrypted. The Blowfish key is
the 80 bytes after the flags, decrypted with Westwood's public RSA key (two
40-byte blocks, 39 bytes each). The body is not encrypted. A file without the
zero word is a Tiberian Dawn MIX. File names use the Tiberian Dawn hash.

The formats are documented by the OpenRA and XCC projects; the code here is
written from those descriptions. Blowfish's initial tables are the hexadecimal
digits of pi, computed here instead of being written out.
"""
from __future__ import annotations

import base64
import functools
import struct

from polyhost.services.game_assets.westwood_td import westwood

ENCRYPTED = 0x20000
# Westwood's public key: a DER-style length byte, then the modulus; e = 0x10001.
PUBLIC_KEY = base64.b64decode("AihRvNoIbTn85FZRYNZRcT+i6KpU+maCsEqr3Q5q+LDB5tH7Tz2qQ38V")
KEY_SOURCE = 80                                 # encrypted key bytes after the flags


@functools.lru_cache(maxsize=1)
def _pi_words() -> tuple:
    """The first 18 + 4 * 256 32-bit words of the fraction of pi (Machin's formula),
    Blowfish's initial P-array and S-boxes."""
    n = 18 + 4 * 256
    bits = 32 * n + 64                          # 64 guard bits

    def atan_inv(x):
        one = 1 << bits
        total, term, k, x2 = 0, one // x, 1, x * x
        while term:
            total += term // k if k % 4 == 1 else -(term // k)
            term //= x2
            k += 2
        return total

    pi = 4 * (4 * atan_inv(5) - atan_inv(239))
    frac = (pi - (3 << bits)) >> 64
    words = tuple((frac >> (32 * (n - 1 - i))) & 0xFFFFFFFF for i in range(n))
    if words[0] != 0x243F6A88 or words[17] != 0x8979FB1B or words[18] != 0xD1310BA6:
        raise ArithmeticError("pi digits do not match the Blowfish tables")
    return words


class Blowfish:
    """Blowfish decryption, 32-bit words read big-endian (as Red Alert does)."""

    def __init__(self, key: bytes):
        w = _pi_words()
        self.P = list(w[:18])
        self.S = [list(w[18 + 256 * i:18 + 256 * (i + 1)]) for i in range(4)]
        k = (key * (72 // len(key) + 1))[:72]
        for i in range(18):
            self.P[i] ^= struct.unpack_from(">I", k, 4 * i)[0]
        left = right = 0
        for i in range(0, 18, 2):
            left, right = self._encrypt(left, right)
            self.P[i], self.P[i + 1] = left, right
        for box in self.S:
            for i in range(0, 256, 2):
                left, right = self._encrypt(left, right)
                box[i], box[i + 1] = left, right

    def _f(self, x):
        s = self.S
        return ((((s[0][x >> 24] + s[1][(x >> 16) & 255]) & 0xFFFFFFFF) ^ s[2][(x >> 8) & 255])
                + s[3][x & 255]) & 0xFFFFFFFF

    def _encrypt(self, left, right):
        for i in range(16):
            left ^= self.P[i]
            right ^= self._f(left)
            left, right = right, left
        return right ^ self.P[17], left ^ self.P[16]

    def _decrypt(self, left, right):
        for i in range(17, 1, -1):
            left ^= self.P[i]
            right ^= self._f(left)
            left, right = right, left
        return right ^ self.P[0], left ^ self.P[1]

    def decrypt(self, data: bytes) -> bytes:
        out = bytearray()
        for i in range(0, len(data) - 7, 8):
            out += struct.pack(">II", *self._decrypt(*struct.unpack_from(">II", data, i)))
        return bytes(out)


def blowfish_key(source: bytes) -> bytes:
    """The 56-byte Blowfish key from the 80 encrypted bytes after the flags."""
    n = int.from_bytes(PUBLIC_KEY[2:2 + PUBLIC_KEY[1]], "big")
    out = b""
    for i in range(0, KEY_SOURCE, 40):
        block = pow(int.from_bytes(source[i:i + 40], "little"), 0x10001, n)
        if block >> (8 * 39):
            raise ValueError("MIX key block does not decrypt to 39 bytes")
        out += block.to_bytes(39, "little")
    return out[:56]


class Mix(westwood.Mix):
    """A Red Alert MIX archive, encrypted or not; a Tiberian Dawn MIX is read too."""

    def __init__(self, data: bytes):
        if len(data) < 6 or data[:2] != b"\0\0":
            super().__init__(data)              # a Tiberian Dawn MIX
            return
        flags, = struct.unpack_from("<I", data, 0)
        if not flags & ENCRYPTED:
            super().__init__(data[4:])
            self.data, self.body = data, self.body + 4
            return
        start = 4 + KEY_SOURCE
        if len(data) < start + 8:
            raise ValueError("MIX header ends early")
        bf = Blowfish(blowfish_key(data[4:start]))
        count, = struct.unpack_from("<H", bf.decrypt(data[start:start + 8]))
        size = 6 + 12 * count
        padded = -(-size // 8) * 8
        if start + padded > len(data):
            raise ValueError(f"MIX header of {count} entries is longer than the file")
        super().__init__(bf.decrypt(data[start:start + padded])[:size])
        self.data, self.body = data, start + padded
