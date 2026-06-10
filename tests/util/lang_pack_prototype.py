#!/usr/bin/env python3
"""Prototype: shrinking the GET_LANG_LIST HID payload.

Compares three encodings of the keyboard's language list:
  1. current  - raw concatenated 4-char ASCII codes (what firmware cmd 0x08 sends)
  2. bit-RLE  - the EXISTING rle_compress() used for keycap bitmaps
  3. 5-bit    - pack each [a-z]/[A-Z] letter into 5 bits (proposed)

Reports the wire size and the number of 64-byte HID reports each needs, and
round-trips the 5-bit codec to prove it is lossless.

Run:  PolyKybdHost/.venv/bin/python tests/util/lang_pack_prototype.py
"""

import os
import sys

from polyhost.util.rle_util import rle_compress
from polyhost.services import iso_lang_country as iso  # frozen ISO index tables

# The full 81-code list, exactly as firmware hid_com.c case 0x08 emits it.
LANGS = (
    "enUS deDE frFR esES ptPT itIT trTR koKR jaJP arSA elGR ukUA ruRU beBY kkKZ "
    "bgBG plPL roRO zhCN nlNL heIL svSE fiFI nnNO daDK huHU csCZ hrHR skSK ltLT "
    "lvLV etEE ptBR srRS mkMK faIR hiIN mrIN neNP mnMN urPK enGB esMX deCH frBE "
    "frCA thTH bnIN teIN taIN zhTW kaGE hyAM idID azAZ isIS viVN zhHK enAU enNZ "
    "miNZ smWS fjFJ tlPH hwUS enZA afZA arEG swKE amET yoNG enNG arMA arIQ kuIQ "
    "msMY uzUZ enCA esAR enPG tyPF"
).split()

# HID framing: 64-byte report, 3-byte response header "P\x08." -> 61 payload bytes.
REPORT_SIZE = 64
HEADER = 3
PAYLOAD = REPORT_SIZE - HEADER


def reports_for(nbytes: int) -> int:
    return -(-nbytes // PAYLOAD)  # ceil


# ---------------------------------------------------------------------------
# 5-bit packer: each code is [a-z][a-z][A-Z][A-Z]; map letter->0..25, 5 bits each.
# Stream layout: 1 count byte, then count*20 bits, MSB-first, zero-padded.
# ---------------------------------------------------------------------------
def _letter_to_val(ch: str) -> int:
    if "a" <= ch <= "z":
        return ord(ch) - ord("a")
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A")
    raise ValueError(f"non-letter in code: {ch!r}")


def _val_to_letter(val: int, upper: bool) -> str:
    return chr(val + (ord("A") if upper else ord("a")))


def pack5(codes: list[str]) -> bytearray:
    bits = 0
    nbits = 0
    out = bytearray([len(codes)])
    for code in codes:
        assert len(code) == 4, code
        for i, ch in enumerate(code):
            bits = (bits << 5) | _letter_to_val(ch)
            nbits += 5
            while nbits >= 8:
                nbits -= 8
                out.append((bits >> nbits) & 0xFF)
    if nbits:
        out.append((bits << (8 - nbits)) & 0xFF)
    return out


def unpack5(buf: bytearray) -> list[str]:
    count = buf[0]
    bits = 0
    nbits = 0
    vals = []
    for byte in buf[1:]:
        bits = (bits << 8) | byte
        nbits += 8
        while nbits >= 5 and len(vals) < count * 4:
            nbits -= 5
            vals.append((bits >> nbits) & 0x1F)
    codes = []
    for i in range(count):
        v = vals[i * 4:i * 4 + 4]
        codes.append(
            _val_to_letter(v[0], False) + _val_to_letter(v[1], False)
            + _val_to_letter(v[2], True) + _val_to_letter(v[3], True)
        )
    return codes


# ---------------------------------------------------------------------------
# ISO-index: 1 count byte, then (lang_idx, country_idx) byte pair per code,
# using the frozen ISO 639-1 / ISO 3166-1 alpha-2 tables (single source of truth).
# ---------------------------------------------------------------------------
def main() -> None:
    n = len(LANGS)
    raw = "".join(LANGS).encode("ascii")

    rle = rle_compress(raw)
    packed = pack5(LANGS)
    isobuf = iso.encode_packed(LANGS)

    # correctness
    assert unpack5(packed) == LANGS, "5-bit round-trip FAILED"
    assert iso.decode_packed(isobuf) == LANGS, "ISO-index round-trip FAILED"

    print(f"languages: {n}\n")
    rows = [
        ("current (raw 4-char ASCII)", len(raw)),
        ("existing bit-RLE",           len(rle)),
        ("proposed 5-bit pack",        len(packed)),
        ("proposed ISO-index (2 B)",   len(isobuf)),
    ]
    print(f"{'scheme':<30}{'bytes':>8}{'reports':>9}{'vs raw':>9}")
    print("-" * 56)
    base = len(raw)
    for name, size in rows:
        print(f"{name:<30}{size:>8}{reports_for(size):>9}{size / base:>8.0%}")

    print("\n5-bit round-trip:     OK (lossless)")
    print("ISO-index round-trip: OK (lossless)")

    # Firmware side carries NO runtime table: each language emits 2 precomputed
    # index bytes instead of the 4 ASCII bytes it stores today -> .rodata shrinks.
    fw_now = n * 4
    fw_iso = n * 2
    print(f"\nfirmware payload .rodata: {fw_now} B -> {fw_iso} B "
          f"({fw_iso - fw_now:+d} B). Host decode table: "
          f"{len(iso.LANG_CODES)}+{len(iso.COUNTRY_CODES)} codes (frozen, shared).")


if __name__ == "__main__":
    main()
