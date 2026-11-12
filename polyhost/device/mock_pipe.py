"""The keyboard's side of the bulk pipe, in Python, for the mock keyboard.

`MockPipe` is ``poly_pipe.c`` (qmk_firmware, keyboards/polykybd/): the frame
parser behind ``virtser_recv()`` and the commands PING, SINK, STAT, RESET, ECHO
and FW_CHUNK. It registers itself with ``bulk_pipe.register_emulated_port``, so
``bulk_pipe.open_port(name)`` returns a pyserial-like port to it, and the
unmodified host code -- ``bulk_pipe.probe`` with its rate measurement,
``stream_firmware``, ``hid_fw_up.stream_over_pipe`` and the font-pack path --
runs against it as it runs against a keyboard.

FW_CHUNK writes through ``MockFirmware.stage_block``, the same writer the HID
chunk commands use, into the target the last HID BEGIN selected. A transfer can
therefore start on the pipe and finish over HID, as on the keyboard.

What it copies from the firmware: the frame layout and CRC, the parser's resync
and bad-frame counting (a frame with a bad CRC is counted and never answered),
the 512-byte cap on buffered commands, an unknown command counted as a good
frame with no reply, the PING reply layout, and FW_CHUNK's status byte plus
cursor. The keyboard clock in STAT advances with the bytes received at
``rate_mbps`` (default 0.6 MB/s, the rig's measured rate), so the host measures
that rate and the tray shows it. Faults: ``FaultPlan.pipe_busy``,
``pipe_drop_chunks`` and ``pipe_reject_chunks`` (mock_firmware.py).
"""
from __future__ import annotations

import struct
import threading
import time
import zlib

from polyhost.device import bulk_pipe as bp

# poly_pipe.h / config.h
POLY_PIPE_PROTOCOL = 2
POLY_PIPE_MAX_PAYLOAD = 512
CDC_EPSIZE = 64
CDC_OUT_CAPACITY = 8
# The HID PROTOCOL_VERSION of the first firmware with the pipe: pipe protocols 1
# and 2 shipped together in qmk_firmware#395 (FW 1.9.3, PROTOCOL_VERSION 23).
PIPE_MIN_PROTOCOL = 23
RIG_RATE_MBPS = 0.6

_MAGIC0, _MAGIC1, _CMD, _LEN0, _LEN1, _PAYLOAD, _CRC = range(7)


class MockPipe:
    """The keyboard's pipe endpoint. Its state (counters, the parser) belongs to
    the keyboard and survives the host closing and reopening the port."""

    def __init__(self, firmware, proto: int = POLY_PIPE_PROTOCOL,
                 rate_mbps: float = RIG_RATE_MBPS):
        self.firmware = firmware
        self.proto = proto
        self.rate_mbps = rate_mbps
        self.port_name = f"mock-pipe-{id(self):x}"
        self.lock = threading.Lock()
        self.opens = 0
        self.fw_chunk_frames = 0      # FW_CHUNK frames answered (inspection)
        self._rx_bytes = 0
        self._state = _MAGIC0
        self._reset_stats()
        bp.register_emulated_port(self.port_name, self)

    def _reset_stats(self) -> None:
        self.stats = dict.fromkeys(bp.STAT_FIELDS, 0)

    def _now_ms(self) -> int:
        """The keyboard clock: bytes received at the modelled link rate. It starts
        at 1000 ms, because the firmware reads 0 in first_ms as "not started"."""
        return 1000 + int(self._rx_bytes / (self.rate_mbps * 1000.0))

    # -- the host side opens the port ----------------------------------------

    def open_port(self):
        faults = self.firmware.faults
        if faults.disconnected:
            raise OSError("device disconnected (injected fault)")
        if faults.pipe_busy:
            raise OSError("port busy (injected fault)")
        self.opens += 1
        return MockSerial(self)

    # -- virtser_recv(), one call per write ----------------------------------

    def receive(self, data: bytes) -> bytes:
        """Parse ``data`` the way virtser_recv() does byte by byte, and return the
        reply bytes the keyboard sends for the frames it completed."""
        out = bytearray()
        i, n = 0, len(data)
        with self.lock:
            while i < n:
                st = self._state
                if st == _PAYLOAD:
                    take = min(n - i, self._len - self._pos)
                    part = data[i:i + take]
                    self._crc = zlib.crc32(part, self._crc)
                    if self._stream:
                        self._sink_crc = zlib.crc32(part, self._sink_crc)
                    elif not self._oversize:
                        self._buf += part
                    self._pos += take
                    self._rx_bytes += take
                    i += take
                    if self._pos == self._len:
                        self._state = _CRC
                    continue
                c = data[i]
                i += 1
                self._rx_bytes += 1
                if st == _MAGIC0:
                    if c == ord("P"):
                        self._state = _MAGIC1
                    else:
                        self.stats["resync_bytes"] += 1
                elif st == _MAGIC1:
                    if c == ord("B"):
                        self._state = _CMD
                    elif c == ord("P"):
                        self.stats["resync_bytes"] += 1
                    else:
                        self.stats["resync_bytes"] += 2
                        self._state = _MAGIC0
                elif st == _CMD:
                    self._cmd = c
                    self._crc = zlib.crc32(bytes([c]))
                    self._state = _LEN0
                elif st == _LEN0:
                    self._len = c
                    self._crc = zlib.crc32(bytes([c]), self._crc)
                    self._state = _LEN1
                elif st == _LEN1:
                    self._len |= c << 8
                    self._crc = zlib.crc32(bytes([c]), self._crc)
                    self._pos = self._crc_pos = self._crc_wire = 0
                    self._buf = bytearray()
                    self._stream = self._cmd == bp.CMD_SINK
                    self._oversize = not self._stream and self._len > POLY_PIPE_MAX_PAYLOAD
                    if self._stream:
                        self._sink_crc = self.stats["sink_crc"]
                        if self.stats["first_ms"] == 0:
                            self.stats["first_ms"] = self._now_ms()
                    self._state = _PAYLOAD if self._len else _CRC
                elif st == _CRC:
                    self._crc_wire |= c << (8 * self._crc_pos)
                    self._crc_pos += 1
                    if self._crc_pos == 4:
                        self._state = _MAGIC0
                        out += self._frame_done()
        return bytes(out)

    # -- frame_done() ------------------------------------------------------------

    def _frame_done(self) -> bytes:
        s = self.stats
        if (self._crc & 0xFFFFFFFF) != self._crc_wire or self._oversize:
            s["frames_bad"] += 1
            return b""
        cmd, buf = self._cmd, bytes(self._buf)
        if cmd == bp.CMD_FW_CHUNK and len(buf) >= 5:
            # A frame lost or corrupted on the wire: the keyboard sees a bad CRC.
            offset = struct.unpack_from("<I", buf)[0]
            if self.firmware.faults.take(self.firmware.faults.pipe_drop_chunks, offset):
                s["frames_bad"] += 1
                return b""
        s["frames_ok"] += 1
        if cmd == bp.CMD_PING:
            ver = self.firmware.version.encode() + b"\0"
            return bp.pack_frame(cmd | bp.REPLY, struct.pack(
                "<BHBB", self.proto, POLY_PIPE_MAX_PAYLOAD, CDC_EPSIZE, CDC_OUT_CAPACITY) + ver)
        if cmd == bp.CMD_SINK:
            s["sink_bytes"] += self._len
            s["sink_crc"] = self._sink_crc & 0xFFFFFFFF
            s["last_ms"] = self._now_ms()
            return b""
        if cmd == bp.CMD_STAT:
            return bp.pack_frame(cmd | bp.REPLY, struct.pack(
                "<7I", *(s[k] & 0xFFFFFFFF for k in bp.STAT_FIELDS)))
        if cmd == bp.CMD_RESET:
            self._reset_stats()
            return bp.pack_frame(cmd | bp.REPLY)
        if cmd == bp.CMD_ECHO:
            return bp.pack_frame(cmd | bp.REPLY, buf)
        if cmd == bp.CMD_FW_CHUNK and self.proto >= bp.PIPE_PROTO_FW_CHUNK:
            return self._fw_chunk(buf)
        return b""      # unknown command: a good frame, no reply

    def _fw_chunk(self, buf: bytes) -> bytes:
        fw = self.firmware
        faults = fw.faults
        with fw.lock:
            active = fw._active
            ok, resume = False, active.cursor if active is not None else 0
            if 5 <= len(buf) <= 4 + bp.FW_CHUNK_MAX:
                offset = struct.unpack_from("<I", buf)[0]
                if faults.take(faults.pipe_reject_chunks, offset):
                    ok = False      # the slave relay failed: NACK with the cursor
                else:
                    ok, resume = fw.stage_block(offset, buf[4:])
        self.fw_chunk_frames += 1
        return bp.pack_frame(bp.CMD_FW_CHUNK | bp.REPLY,
                             bytes([ord("." if ok else "!")]) + struct.pack("<I", resume))


class MockSerial:
    """What pyserial's ``Serial`` is to the host: one open handle on the pipe.
    ``timeout`` is ``bulk_pipe.open_port``'s read timeout: a read with nothing
    waiting blocks that long, so a host loop waiting for a reply that will not
    come (a dropped frame) does not spin a CPU core."""

    def __init__(self, pipe: MockPipe, timeout: float = 0.05):
        self.pipe = pipe
        self.port = pipe.port_name
        self.timeout = timeout
        self.is_open = True
        self._out = bytearray()

    @property
    def in_waiting(self) -> int:
        return len(self._out)

    def write(self, data) -> int:
        if not self.is_open:
            raise OSError("port closed")
        if self.pipe.firmware.faults.disconnected:
            raise OSError("device disconnected (injected fault)")
        self._out += self.pipe.receive(bytes(data))
        return len(data)

    def read(self, size: int = 1) -> bytes:
        if not self.is_open:
            raise OSError("port closed")
        if not self._out and self.timeout:
            time.sleep(self.timeout)    # the replies are written synchronously: none will arrive
            return b""
        chunk = bytes(self._out[:size])
        del self._out[:size]
        return chunk

    def reset_input_buffer(self) -> None:
        self._out.clear()

    def close(self) -> None:
        self.is_open = False


__all__ = ["MockPipe", "MockSerial", "PIPE_MIN_PROTOCOL", "POLY_PIPE_PROTOCOL", "RIG_RATE_MBPS"]
