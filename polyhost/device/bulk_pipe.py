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
CMD_FW_CHUNK = 0x10  # pipe protocol 2: one firmware-update chunk (poly_pipe.h)
REPLY = 0x80
# The pipe protocol version a PING reply must report for each command. The HID
# PROTOCOL_VERSION does not cover the pipe, so this is the only gate.
PIPE_PROTO_FW_CHUNK = 2
# Firmware chunk on the pipe: the firmware relays one frame to the slave half in
# one split RPC, whose length field is a byte (qmk FW_UP_RELAY_CHUNK_MAX).
FW_CHUNK_MAX = 236
# Frames sent ahead of their replies. The firmware handles a frame inside its USB
# drain and answers at the end of that pass, so the window keeps the keyboard busy
# across the host's reply turnaround without letting the OUT queue grow past a few
# frames (poly_pipe.h explains why an unpaced stream is harmful).
FW_CHUNK_WINDOW = 4
FW_CHUNK_TIMEOUT_S = 8.0   # a reply this late means the keyboard is gone (HID uses the same)
FW_CHUNK_DRAIN_S = 1.0     # how long to wait for the replies of frames in flight after a NACK
FW_CHUNK_ATTEMPTS = 8      # cursor probes without progress before giving up
FW_CHUNK_MAX_REWINDS = 100
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


def open_port(port: str):
    """The pyserial port for the pipe, raw. Opening sets DTR, which the firmware
    ignores; ``dsrdtr``/``rtscts`` are off because no flow-control lines exist on
    the device side. The baud rate is nominal: a CDC-ACM device ignores it."""
    import serial
    return serial.Serial(port, baudrate=115200, timeout=0.05, write_timeout=1.0,
                         dsrdtr=False, rtscts=False)


def probe(port: str, timeout: float = PROBE_TIMEOUT_S, serial_open=None):
    """Open ``port`` raw, PING the pipe, close. Returns the parsed PING reply
    (a dict, see ``parse_ping``) or None when the port cannot be opened, is
    held by another program, or does not answer."""
    if serial_open is None:
        serial_open = open_port
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


def fw_chunk_frame(offset: int, data: bytes) -> bytes:
    """One FW_CHUNK frame: the offset (u32 LE) and 1..FW_CHUNK_MAX data bytes."""
    return pack_frame(CMD_FW_CHUNK, struct.pack("<I", offset) + data)


def parse_fw_chunk_reply(payload: bytes):
    """``(acked, resume)`` from a FW_CHUNK reply, or None for a malformed one.
    ``resume`` is the keyboard's cursor: where the host continues from."""
    if len(payload) < 5:
        return None
    return payload[0] == ord("."), struct.unpack_from("<I", payload, 1)[0]


def stream_firmware(ser, fw_bytes: bytes, start: int = 0, chunk: int = FW_CHUNK_MAX,
                    window: int = FW_CHUNK_WINDOW, timeout: float = FW_CHUNK_TIMEOUT_S,
                    progress=None, cancelled=None, clock=time.monotonic):
    """Send ``fw_bytes[start:]`` to the keyboard as FW_CHUNK frames, up to
    ``window`` frames ahead of their replies, after FW_UP_BEGIN was ACKed over
    HID. Returns ``(ok, offset, reason)``: ``ok`` when the keyboard's cursor
    reached the end of the image; otherwise ``offset`` is the keyboard's cursor
    (a sender continues from there, on this channel or over HID) and ``reason``
    says why in English (device-layer text, see hid_fw_up).

    Every reply carries the keyboard's cursor, so the host never needs to
    attribute a reply to a frame: an ACK moves the confirmed offset to the
    cursor; a NACK (the keyboard rejected a frame, or a frame arrived out of
    order after a loss) rewinds the stream to the cursor once the replies for
    the frames still in flight have drained. A frame the keyboard dropped
    silently (bad CRC on the wire) never gets a reply, so a quiet window is
    resolved by a cursor probe: an empty FW_CHUNK, which the firmware always
    answers with a NACK and its cursor. ``progress(offset)`` is called as the
    confirmed offset moves; ``cancelled()`` is polled between reads."""
    total = len(fw_bytes)
    offset = confirmed = start      # offset: next byte to send; confirmed: the keyboard's cursor
    in_flight = 0                   # frames sent whose reply has not arrived
    drain = 0                       # replies to ignore after a rewind
    attempts = rewinds = 0
    parser = FrameParser()
    last_reply = clock()
    while True:
        if cancelled is not None and cancelled():
            return False, confirmed, "cancelled"
        if confirmed >= total:
            return True, total, None
        if drain == 0:
            while in_flight < window and offset < total:
                n = min(chunk, total - offset)
                ser.write(fw_chunk_frame(offset, fw_bytes[offset:offset + n]))
                offset += n
                in_flight += 1
        data = ser.read(max(1, getattr(ser, "in_waiting", 0) or 1))
        if data:
            for cmd, body in parser.feed(data):
                if cmd != (CMD_FW_CHUNK | REPLY):
                    continue
                parsed = parse_fw_chunk_reply(body)
                if parsed is None:
                    continue
                last_reply = clock()
                acked, cursor = parsed
                if drain:
                    drain -= 1
                    in_flight = max(0, in_flight - 1)
                    confirmed = max(confirmed, min(cursor, total))
                    if drain == 0:
                        offset = confirmed
                        in_flight = 0
                    continue
                in_flight = max(0, in_flight - 1)
                if acked:
                    if cursor > confirmed:
                        confirmed = cursor
                        attempts = 0
                        if progress is not None:
                            progress(confirmed)
                    continue
                # NACK: the keyboard's cursor is authoritative. Let the replies to
                # the other in-flight frames pass, then restart from the cursor.
                rewinds += 1
                if rewinds > FW_CHUNK_MAX_REWINDS:
                    return False, cursor, "keyboard rejected the chunk"
                if cursor <= confirmed:
                    attempts += 1
                    if attempts >= FW_CHUNK_ATTEMPTS:
                        return False, cursor, "keyboard rejected the chunk"
                confirmed = max(confirmed, cursor) if cursor <= total else confirmed
                if in_flight:
                    drain = in_flight
                else:
                    offset = cursor
            continue
        quiet = clock() - last_reply
        if drain and quiet >= FW_CHUNK_DRAIN_S:
            # A frame the keyboard dropped never gets a reply, so a drain can wait
            # for one that is not coming. The NACK already gave the cursor.
            drain = in_flight = 0
            offset = confirmed
            last_reply = clock()
            continue
        if quiet < timeout:
            continue
        # Quiet for the whole timeout with frames outstanding: a dropped frame or
        # a gone keyboard. Probe the cursor; no answer means the keyboard is gone.
        attempts += 1
        if attempts >= FW_CHUNK_ATTEMPTS:
            return False, confirmed, "no reply from the keyboard"
        reply = request(ser, CMD_FW_CHUNK, b"", timeout=timeout, clock=clock)
        parsed = parse_fw_chunk_reply(reply) if reply is not None else None
        if parsed is None:
            return False, confirmed, "no reply from the keyboard"
        last_reply = clock()
        offset = confirmed = max(confirmed, parsed[1])
        in_flight = drain = 0
