"""Shared fake HID device + HidHelper factory for device-layer tests.

FakeHidDevice stands in for hid.Device underneath a REAL HidHelper, so the
helper's locking, stale-reply draining, and error paths are exercised for
real instead of being mocked away. This is the characterization harness for
the planned HID worker-thread / command-queue refactoring: behavior pinned
here must survive the refactor.

Replies are served from a scripted queue. With auto_ack=True the device
answers like the firmware instead when the queue is empty:
  - PolyKybd commands (payload[0] == 0x50): reply "P" + cmd + "." (ACK)
  - VIA requests: echo the request payload back
"""
import threading
from collections import deque

import polyhost.util.log_util  # noqa: F401 — registers Logger.debug_detailed
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.hid_helper import HidHelper

POLY_ID = 0x50  # HidId.ID_POLYKYBD


def pad(data: bytes, size: int = 64) -> bytes:
    return bytes(data) + b'\x00' * (size - len(data))


def ack(cmd: int, extra: bytes = b'') -> bytes:
    """Firmware ACK for a PolyKybd command: 'P' + cmd byte + '.' + payload."""
    return pad(b'P' + bytes([cmd]) + b'.' + extra)


def nack(cmd: int) -> bytes:
    return pad(b'P' + bytes([cmd]) + b'!')


class FakeHidDevice:
    """Drop-in for hid.Device: records writes, serves scripted reads."""

    def __init__(self, replies=None, auto_ack=False):
        self.replies = deque(replies or [])
        self.auto_ack = auto_ack
        self.writes = []            # raw bytes passed to write(), incl. report-ID byte
        self.write_exception = None
        self.read_exception = None
        self.closed = False

    # -- hid.Device interface -------------------------------------------------

    def write(self, report) -> int:
        if self.write_exception:
            raise self.write_exception
        self.writes.append(bytes(report))
        return len(report)

    def read(self, size, timeout=0) -> bytes:
        if self.read_exception:
            raise self.read_exception
        if self.replies:
            reply = self.replies.popleft()
            if callable(reply):
                reply = reply(self.last_payload())
            return bytes(reply)
        if self.auto_ack and self.writes:
            payload = self.last_payload()
            if payload and payload[0] == POLY_ID:
                return ack(payload[1])
            return pad(payload)     # VIA request: echo back
        return b''                  # nothing queued -> read timeout

    def close(self):
        self.closed = True

    # -- test inspection helpers ----------------------------------------------

    def last_payload(self) -> bytes:
        """Last written report without the leading report-ID byte."""
        return self.writes[-1][1:] if self.writes else b''

    def payloads(self) -> list:
        """All written reports without the leading report-ID byte."""
        return [w[1:] for w in self.writes]


def make_hid_helper(device: FakeHidDevice, settings: DeviceSettings = None,
                    console: FakeHidDevice = None) -> HidHelper:
    """Real HidHelper wired to a fake device, bypassing USB enumeration."""
    helper = HidHelper.__new__(HidHelper)
    helper.settings = settings or DeviceSettings()
    helper.lock = threading.Lock()
    helper.interface = device
    helper.remote_console = console
    return helper
