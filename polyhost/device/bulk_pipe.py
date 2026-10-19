"""The keyboard's bulk pipe: the CDC serial interface next to raw HID.

A ``POLYKYBD_BULK_PIPE`` firmware (qmk ``keyboards/polykybd/BULK_PIPE.md``)
enumerates a CDC-ACM function whose data endpoints are bulk, so the host can
stream 64-byte packets back to back instead of one HID report per 1 ms frame.
The OS binds its own serial driver, and the port carries the keyboard's
VID/PID. Raw HID stays the control channel; the pipe is a byte stream with
its own framing (``poly_pipe.h``)::

    'P' 'B'  cmd  len_lo len_hi  payload[len]  crc32 LE

crc32 is ``zlib.crc32`` over cmd, len and payload; a reply carries
``cmd | 0x80``.

The pipe is OPTIONAL. It is absent on older firmware, on a locked-down
machine that blocks the serial device class, behind a KVM that passes HID
only, and whenever another program holds the port. ``detect()`` folds every
one of those into "HID only"; nothing in the HID protocol announces the pipe,
so this probe is the only way the host learns about it.
"""
import logging
import struct
import time
import zlib

TRANSPORT_PIPE = "pipe"
TRANSPORT_HID = "hid"

MAGIC = b"PB"
CMD_PING, CMD_SINK, CMD_STAT, CMD_RESET, CMD_ECHO = 0x01, 0x02, 0x03, 0x04, 0x05
REPLY = 0x80
STAT_FIELDS = ("sink_bytes", "frames_ok", "frames_bad", "resync_bytes",
               "sink_crc", "first_ms", "last_ms")
PROBE_TIMEOUT_S = 0.5
# The probe streams this much after the PING and reads the keyboard's own byte
# count, CRC and clock back: the rate the user sees is measured on this
# machine, and a port that drops or corrupts bytes is treated as no link.
# 128 KB is ~0.2 s at the rig's 0.6 MB/s.
PROBE_STREAM_BYTES = 128 * 1024
PROBE_FRAME_BYTES = 4096
HID_LINK_KBPS = 64  # one 64-byte report per 1 ms USB frame: the HID channel's ceiling

log = logging.getLogger("PolyHost")


def pack_frame(cmd: int, payload: bytes = b"") -> bytes:
    """One wire frame. The CRC covers cmd, the length bytes and the payload."""
    body = bytes([cmd]) + struct.pack("<H", len(payload)) + payload
    return MAGIC + body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)


class FrameParser:
    """Incremental parser for the reply stream: the firmware's state machine
    mirrored, so a reply split across reads or behind noise still assembles."""

    def __init__(self):
        self.buf = bytearray()
        self.dropped = 0

    def feed(self, data: bytes) -> list:
        """Return the list of (cmd, payload) frames completed by ``data``."""
        self.buf += data
        frames = []
        while True:
            start = self.buf.find(MAGIC)
            if start < 0:
                # Keep a trailing 'P' in case the 'B' is still in flight.
                keep = 1 if self.buf.endswith(b"P") else 0
                self.dropped += len(self.buf) - keep
                del self.buf[:len(self.buf) - keep]
                return frames
            if start:
                self.dropped += start
                del self.buf[:start]
            if len(self.buf) < 5:
                return frames
            cmd = self.buf[2]
            length = struct.unpack_from("<H", self.buf, 3)[0]
            end = 5 + length + 4
            if len(self.buf) < end:
                return frames
            body = bytes(self.buf[2:5 + length])
            crc = struct.unpack_from("<I", self.buf, 5 + length)[0]
            if zlib.crc32(body) & 0xFFFFFFFF == crc:
                frames.append((cmd, body[3:]))
                del self.buf[:end]
            else:
                # Not a frame after all: skip the magic and hunt again.
                self.dropped += 2
                del self.buf[:2]


def sink_crc_chain(chunks) -> int:
    """The CRC the firmware reports in STAT: crc32 chained over every SINK byte."""
    crc = 0
    for chunk in chunks:
        crc = zlib.crc32(chunk, crc) & 0xFFFFFFFF
    return crc


def parse_stat(payload: bytes) -> dict:
    if len(payload) != 4 * len(STAT_FIELDS):
        raise ValueError(f"STAT reply has {len(payload)} bytes, expected {4 * len(STAT_FIELDS)}")
    return dict(zip(STAT_FIELDS, struct.unpack("<" + "I" * len(STAT_FIELDS), payload)))


def parse_ping(payload: bytes) -> dict:
    """The PING reply: pipe protocol, buffered-payload cap, packet size, OUT
    queue depth and the firmware version string."""
    if len(payload) < 5:
        raise ValueError(f"PING reply has {len(payload)} bytes, expected at least 5")
    proto, max_payload, epsize, out_cap = struct.unpack_from("<BHBB", payload)
    fw = payload[5:].split(b"\0", 1)[0].decode(errors="replace")
    return {"proto": proto, "max_payload": max_payload, "epsize": epsize,
            "out_capacity": out_cap, "fw": fw}


def find_port(vid: int, pids, comports=None):
    """The serial port carrying the keyboard's VID and one of ``pids``, or None.

    ``comports`` is pyserial's ``list_ports.comports`` unless a test injects
    one. A port is found by its USB identity only: a device that is there but
    not openable is still "found" here and becomes HID-only in ``probe``."""
    if comports is None:
        from serial.tools import list_ports
        comports = list_ports.comports
    for port in comports():
        if getattr(port, "vid", None) == vid and getattr(port, "pid", None) in tuple(pids):
            return port.device
    return None


def request(ser, cmd: int, payload: bytes = b"", timeout: float = PROBE_TIMEOUT_S,
            clock=time.monotonic):
    """Send one frame on an open pyserial port and wait for its reply payload,
    or None on timeout. The port must be in raw mode (pyserial's default)."""
    ser.write(pack_frame(cmd, payload))
    parser = FrameParser()
    deadline = clock() + timeout
    while clock() < deadline:
        data = ser.read(max(1, getattr(ser, "in_waiting", 0) or 1))
        if not data:
            continue
        for got, body in parser.feed(data):
            if got == (cmd | REPLY):
                return body
    return None


def probe(port: str, timeout: float = PROBE_TIMEOUT_S, serial_open=None):
    """Open ``port`` raw, PING the pipe, close. Returns the parsed PING reply
    (a dict, see ``parse_ping``) or None when the port cannot be opened, is
    held by another program, or does not answer.

    Opening sets DTR, which the firmware ignores; ``dsrdtr``/``rtscts`` are
    off because no flow-control lines exist on the device side."""
    if serial_open is None:
        import serial

        def serial_open(p):
            return serial.Serial(p, baudrate=115200, timeout=0.05, write_timeout=1.0,
                                 dsrdtr=False, rtscts=False)
    try:
        ser = serial_open(port)
    except Exception as exc:  # noqa: BLE001 — "busy" and "no permission" both mean HID only
        log.info("Bulk pipe %s not openable (%s): HID only", port, exc)
        return None
    try:
        reply = request(ser, CMD_PING, timeout=timeout)
        if reply is None:
            log.info("Bulk pipe %s opened but did not answer PING: HID only", port)
            return None
        info = parse_ping(reply)
        rate = measure_rate(ser, timeout=timeout)
        if rate is None:
            log.warning("Bulk pipe %s answered PING but the stream did not arrive intact: HID only", port)
            return None
        info["rate_mbps"] = rate
    except Exception as exc:  # noqa: BLE001 — a malformed reply is "no pipe", not a crash
        log.warning("Bulk pipe %s answered garbage (%s): HID only", port, exc)
        return None
    finally:
        try:
            ser.close()
        except Exception:  # noqa: BLE001
            pass
    info["port"] = port
    return info


def measure_rate(ser, nbytes: int = PROBE_STREAM_BYTES, frame: int = PROBE_FRAME_BYTES,
                 timeout: float = PROBE_TIMEOUT_S):
    """Stream ``nbytes`` of SINK frames and return the rate in MB/s from the
    keyboard's clock, or None when the keyboard did not count every byte with
    the right CRC (or never answered RESET / STAT)."""
    if request(ser, CMD_RESET, timeout=timeout) is None:
        return None
    block = bytes((i * 7919 + 13) & 0xFF for i in range(frame))
    frames = max(1, nbytes // frame)
    wire = pack_frame(CMD_SINK, block) * frames
    expect = sink_crc_chain([block] * frames)
    t0 = time.perf_counter()
    for i in range(0, len(wire), 65536):
        ser.write(wire[i:i + 65536])
    reply = request(ser, CMD_STAT, timeout=max(timeout, 5.0))
    host_s = time.perf_counter() - t0
    if reply is None:
        return None
    st = parse_stat(reply)
    payload = frames * frame
    if st["sink_bytes"] != payload or st["sink_crc"] != expect or st["frames_bad"]:
        return None
    dev_s = (st["last_ms"] - st["first_ms"]) / 1000.0
    seconds = dev_s if dev_s > 0 else host_s
    return payload / seconds / 1e6 if seconds > 0 else None


def rate_label(rate_mbps) -> str:
    """"0.6 MB/s" / "1.2 MB/s" / "12 MB/s": one decimal below 10."""
    return f"{rate_mbps:.0f} MB/s" if rate_mbps >= 10 else f"{rate_mbps:.1f} MB/s"


def detect(vid: int, pids, comports=None, serial_open=None):
    """Find and PING the pipe in one step. Returns the PING info dict, or None
    for every way the pipe can be unavailable (absent, busy, mute)."""
    try:
        port = find_port(vid, pids, comports=comports)
    except Exception as exc:  # noqa: BLE001 — a broken port enumerator must not kill the probe
        log.debug("Serial port enumeration failed: %s", exc)
        return None
    if port is None:
        return None
    return probe(port, serial_open=serial_open)
