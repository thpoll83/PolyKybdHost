"""Packing PRC overlay images into cmd 41 reports (protocol v19+).

A PRC-coded image averages ~28 bytes, so most fit one report and small ones
share it. :class:`PrcReportPacker` collects records until the next one would not
fit, then sends the report. The firmware parses records until a keycode byte of
0, so the zero padding the HID layer adds ends the list.

⚠️ A queued image is NOT on the device yet, but the MRU cache already records
its slot. Every path that gives up before :meth:`PrcReportPacker.flush` succeeds
must call :meth:`PrcReportPacker.discard`, or those slots become permanent stale
cache hits: the keycap shows whatever really occupies the slot and the image is
never re-sent.
"""
from __future__ import annotations

from typing import Callable

from polyhost.util import prc_codec


def prc_record(overlay, keycode: int, modifier: int, capacity: int) -> bytes | None:
    """The cmd 41 record for ``overlay``, or None if it does not fit one report.

    ``overlay`` is an OverlayData. The payload is computed once and cached on the
    object, since the same image is offered again on every cache miss."""
    payload = getattr(overlay, "_prc_payload", None)
    if payload is None:
        import numpy as np
        mask = np.unpackbits(np.frombuffer(overlay.all_bytes, dtype=np.uint8)).reshape(40, 72)
        roi = mask[overlay.top:overlay.bottom, overlay.left:overlay.right]
        payload = prc_codec.encode(roi)
        overlay._prc_payload = payload
    if prc_codec.RECORD_HDR + len(payload) > capacity or len(payload) > prc_codec.MAX_RECORD_PAYLOAD:
        return None
    return prc_codec.pack_record(keycode, modifier, overlay.top, overlay.left,
                                 overlay.bottom - overlay.top, overlay.right - overlay.left,
                                 payload)


class PrcReportPacker:
    """Fills cmd 41 reports with records and sends each one when it is full.

    ``send(payload) -> bool`` transmits one report's records (the caller adds
    the command header). ``cache`` is the OverlayMRUCache the slots came from."""

    def __init__(self, send: Callable[[bytes], bool], capacity: int, cache=None):
        self._send = send
        self._capacity = capacity
        self._cache = cache
        self._buf = bytearray()
        self._slots: list[int] = []
        self.reports = 0
        self.images = 0

    @property
    def pending(self) -> bool:
        return bool(self._buf)

    def holds(self, slot: int) -> bool:
        """Is an image for ``slot`` queued? A slot is reused only when the pool
        evicts inside one switch; an image sent the old way to such a slot must
        go AFTER the queued one, or the queued (older) image overwrites it."""
        return slot in self._slots

    def add(self, record: bytes, slot: int) -> int:
        """Queue ``record`` for pool slot ``slot``. Returns the reports sent to
        make room (0 or 1), or -1 if that send failed (the queue is discarded)."""
        sent = 0
        if len(self._buf) + len(record) > self._capacity:
            sent = self.flush()
            if sent < 0:
                return -1
        self._buf += record
        self._slots.append(slot)
        self.images += 1
        return sent

    def flush(self) -> int:
        """Send the queued records. Returns 1 for a report sent, 0 if nothing was
        queued, -1 if the send failed (the queue is discarded)."""
        if not self._buf:
            return 0
        if not self._send(bytes(self._buf)):
            self.discard()
            return -1
        self._buf = bytearray()
        self._slots = []
        self.reports += 1
        return 1

    def discard(self) -> None:
        """Drop the queued records and forget their cache slots, newest first so
        the cache can reclaim each index."""
        if self._cache is not None:
            for slot in reversed(self._slots):
                self._cache.forget_slot(slot)
        self._buf = bytearray()
        self._slots = []
