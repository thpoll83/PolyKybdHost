"""Packing helpers for the overlay-mapping HID reports.

A mapping report is a flat LSB-first bit stream of equal-width values, read by
the firmware as alternating ``from, to, from, to, …``. ``from`` is a display
position (a flat *(keycode slot, modifier variant)* index) and ``to`` is a pool
slot, so the width a given pair NEEDS is ``max(bits(from), bits(to))``.

Two commands carry that stream:

* ``SEND_OVERLAY_MAPPING`` (cmd 21) — fixed 10 bits, the only form a pre-v12
  keyboard understands.
* ``SEND_OVERLAY_MAPPING_W`` (cmd 33, protocol v12+) — the width travels in the
  report, so the host can send each group of pairs at the narrowest width it
  fits in.

Mapping pairs are **order-independent** (each is a standalone assignment), which
is what lets :func:`plan_mapping_reports` partition them by required width
rather than by index order. Variants 0..10 all fit in 10 bits, so the common
case keeps the dense 10-bit form and only the high GUI combos pay for 11.
"""

import math

# Mirrors the firmware's OVERLAY_MAP_WIDTH_MIN/MAX (config.h).
WIDTH_MIN = 8
WIDTH_MAX = 16


def min_width(value: int) -> int:
    """Narrowest supported width that can carry ``value``."""
    return max(WIDTH_MIN, value.bit_length())


def pair_width(from_idx: int, to_idx: int) -> int:
    """Narrowest supported width that can carry both halves of one pair."""
    return max(min_width(from_idx), min_width(to_idx))


def values_per_report(data_bytes: int, width: int) -> int:
    """Values a ``data_bytes`` stream holds at ``width`` bits.

    ⚠️ This is the ONE definition the host and firmware must agree on. There is
    no count field in the report: the sender fills every value (padding by
    repeating the last pair), so a disagreement would leave trailing values the
    firmware decodes as real mappings.
    """
    return data_bytes * 8 // width


def pairs_per_report(data_bytes: int, width: int) -> int:
    return values_per_report(data_bytes, width) // 2


def pack_values(values: list[int], data_bytes: int, width: int) -> bytearray:
    """Pack ``values`` LSB-first at ``width`` bits into ``data_bytes`` bytes.

    Mirrors the firmware's pack_map_value()/set_packed_overlay_mapping() pair
    (fill_overlay.c) — value *i* occupies bits ``[i*width, i*width+width-1]``,
    little-endian. Values beyond what the stream holds are dropped by the
    caller, not here.
    """
    buf = bytearray(data_bytes)
    mask = (1 << width) - 1
    for idx, v in enumerate(values):
        start = idx * width
        b, s = divmod(start, 8)
        shifted = (v & mask) << s
        buf[b] |= shifted & 0xFF
        # Second and third byte only when the value really extends there, so a
        # narrow width at the tail of the buffer can't index past it.
        if s + width > 8:
            buf[b + 1] |= (shifted >> 8) & 0xFF
        if s + width > 16:
            buf[b + 2] |= (shifted >> 16) & 0xFF
    return buf


def pack_report(pairs: list[tuple[int, int]], data_bytes: int, width: int) -> bytearray:
    """One report's worth of pairs, padded to fill every value slot.

    Padding REPEATS THE LAST PAIR rather than using an out-of-range sentinel:
    re-applying a mapping is idempotent on the firmware side, so a duplicate is
    a semantic no-op and no reserved value is needed. That matters because a
    sentinel would have to exceed the flat index count (1440) and cannot be
    expressed at the narrower widths at all. Leaving slots zero is NOT an
    option — the firmware would read them as the real pair ``0 -> 0``.
    """
    if not pairs:
        return bytearray(data_bytes)
    slots = pairs_per_report(data_bytes, width)
    used = pairs[:slots]
    padded = used + [used[-1]] * (slots - len(used))
    values: list[int] = []
    for f, t in padded:
        values.append(f)
        values.append(t)
    return pack_values(values, data_bytes, width)


def plan_mapping_reports(mapping: dict[int, int], data_bytes: int,
                         max_width: int = 11) -> list[tuple[int, list[tuple[int, int]]]]:
    """Group ``mapping`` into ``(width, pairs)`` reports, narrowest width first.

    Greedy, widest-first: a pair needing 11 bits cannot travel in a 10-bit
    report, but any narrow pair can ride in a wide one — so the partially-filled
    last report at each width is topped up from the narrower buckets (widest
    narrower first). That report is being sent anyway, so those pairs ride free
    and the narrower buckets keep their denser reports.
    """
    buckets: dict[int, list[tuple[int, int]]] = {}
    for f, t in mapping.items():
        buckets.setdefault(min(pair_width(f, t), max_width), []).append((f, t))

    reports: list[tuple[int, list[tuple[int, int]]]] = []
    for width in sorted(buckets, reverse=True):
        bucket = buckets.pop(width, [])
        if not bucket:
            continue
        cap = pairs_per_report(data_bytes, width)
        while len(bucket) > cap:
            reports.append((width, bucket[:cap]))
            bucket = bucket[cap:]
        # Top the remainder up from narrower buckets — free capacity in a report
        # we are already paying for.
        for narrower in sorted((w for w in buckets if w < width), reverse=True):
            while len(bucket) < cap and buckets[narrower]:
                bucket.append(buckets[narrower].pop())
            if not buckets[narrower]:
                del buckets[narrower]
            if len(bucket) == cap:
                break
        reports.append((width, bucket))
    return reports


def pack_dict_10_bit(data_dict: dict[int, int]) -> bytearray:
    """Legacy fixed-10-bit packing for SEND_OVERLAY_MAPPING (cmd 21).

    Kept for the pre-v12 path, which is the only form an older keyboard
    understands. Byte-compatible with what the firmware's fixed-width decoder
    reads; the caller pads to a whole report.
    """
    values: list[int] = []
    for key, value in data_dict.items():
        values.append(key)
        values.append(value)
    num_bytes = math.ceil(len(values) * 10 / 8)
    return pack_values(values, num_bytes, 10)


def unpack_bytes_to_dict(packed_data: bytes, num_pairs: int, width: int = 10) -> dict[int, int]:
    """Inverse of :func:`pack_values` read as pairs — used by the tests/mock."""
    if not packed_data or num_pairs == 0:
        return {}
    mask = (1 << width) - 1
    out: dict[int, int] = {}
    for pair in range(num_pairs):
        vals = []
        for half in range(2):
            start = (pair * 2 + half) * width
            b, s = divmod(start, 8)
            acc = packed_data[b]
            if s + width > 8:
                acc |= packed_data[b + 1] << 8
            if s + width > 16:
                acc |= packed_data[b + 2] << 16
            vals.append((acc >> s) & mask)
        out[vals[0]] = vals[1]
    return out
