#!/usr/bin/env python3
"""Measure the keyboard's bulk pipe (the CDC serial interface next to raw HID).

The firmware's POLYKYBD_BULK_PIPE build adds a CDC-ACM interface whose data
endpoints are BULK, so the host can stream 64-byte packets back to back instead
of one 64-byte HID report per 1 ms USB frame. This tool answers the question the
prototype exists for: how many bytes per second reach the keyboard intact, and
how does that compare with the raw HID channel the host uses today.

    .venv/bin/python tools/pipe_bench.py                 # pipe: PING, 4 MB SINK, ECHO
    .venv/bin/python tools/pipe_bench.py --mb 16 --frame 8192
    .venv/bin/python tools/pipe_bench.py --hid           # also time raw-HID round trips
    .venv/bin/python tools/pipe_bench.py --port COM7     # skip the VID/PID port search

The pipe part needs nothing but pyserial (a polyhost dependency). On Linux the
port is /dev/ttyACM*; add the rules in polyhost/device/99-hid.rules so a user can
open it and ModemManager leaves it alone. `--hid` opens the raw-HID interface, so
stop the running host first (it owns the device).

Frame format (keyboards/polykybd/poly_pipe.h):
    'P' 'B'  cmd  len_lo len_hi  payload  crc32 LE
crc32 is zlib.crc32 over cmd, len and payload. Replies carry cmd | 0x80.
"""
import argparse
import struct
import sys
import time
import zlib

import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from polyhost.device.bulk_pipe import (  # noqa: E402  (framing lives with the host's probe)
    CMD_ECHO, CMD_PING, CMD_RESET, CMD_SINK, CMD_STAT, MAGIC, REPLY, STAT_FIELDS,
    FrameParser, pack_frame, parse_stat, sink_crc_chain)

VID = 0x2021
KNOWN_PIDS = (0x2007, 0x2008)


def find_port() -> str:
    import serial.tools.list_ports
    for port in serial.tools.list_ports.comports():
        if port.vid == VID and port.pid in KNOWN_PIDS:
            return port.device
    raise SystemExit("no PolyKybd serial port found (is the firmware a POLYKYBD_BULK_PIPE build?); "
                     "pass --port")


class Pipe:
    def __init__(self, port: str, timeout: float):
        import serial
        # Baud rate is meaningless on CDC-ACM; the flow-control lines are not
        # wired in the firmware, so leave DTR/RTS handshaking off.
        self.ser = serial.Serial(port, baudrate=115200, timeout=timeout,
                                 write_timeout=max(timeout, 10.0), dsrdtr=False, rtscts=False)
        self.parser = FrameParser()
        self.timeout = timeout

    def close(self):
        self.ser.close()

    def request(self, cmd: int, payload: bytes = b"") -> bytes:
        self.ser.write(pack_frame(cmd, payload))
        self.ser.flush()
        return self.wait_reply(cmd)

    def wait_reply(self, cmd: int) -> bytes:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            data = self.ser.read(max(1, self.ser.in_waiting or 1))
            if not data:
                continue
            for got, body in self.parser.feed(data):
                if got == (cmd | REPLY):
                    return body
        raise TimeoutError(f"no reply to command 0x{cmd:02x} within {self.timeout:.1f} s")


def bench_sink(pipe: Pipe, total_bytes: int, frame_payload: int, write_chunk: int) -> dict:
    """Stream `total_bytes` of SINK payload, then read the keyboard's own count."""
    stats0 = parse_stat(pipe.request(CMD_RESET) and pipe.request(CMD_STAT))
    assert stats0["sink_bytes"] == 0, stats0
    # Deterministic but incompressible-looking payload: a 64 KB pseudo-random block.
    import random
    rnd = random.Random(0x504B)
    block = bytes(rnd.getrandbits(8) for _ in range(65536))
    frames = []
    sent_chunks = []
    remaining = total_bytes
    off = 0
    while remaining > 0:
        n = min(frame_payload, remaining)
        chunk = block[off:off + n]
        if len(chunk) < n:
            off = 0
            chunk = block[:n]
        off = (off + n) % len(block)
        sent_chunks.append(chunk)
        frames.append(pack_frame(CMD_SINK, chunk))
        remaining -= n
    wire = b"".join(frames)
    t0 = time.perf_counter()
    for i in range(0, len(wire), write_chunk):
        pipe.ser.write(wire[i:i + write_chunk])
    pipe.ser.flush()
    t_host = time.perf_counter() - t0
    # STAT is answered after the last SINK byte was consumed, so its arrival
    # time bounds the real transfer end (write() can return before the device
    # took the last packets).
    t1 = time.perf_counter()
    stats = parse_stat(pipe.request(CMD_STAT))
    t_total = time.perf_counter() - t0
    expect_crc = sink_crc_chain(sent_chunks)
    dev_ms = stats["last_ms"] - stats["first_ms"]
    result = {
        "payload_bytes": total_bytes,
        "wire_bytes": len(wire),
        "frames": len(frames),
        "host_write_s": t_host,
        "host_total_s": t_total,
        "stat_latency_s": time.perf_counter() - t1,
        "device_ms": dev_ms,
        "ok": (stats["sink_bytes"] == total_bytes and stats["sink_crc"] == expect_crc
               and stats["frames_bad"] == 0 and stats["frames_ok"] >= len(frames)),
        "stats": stats,
        "expect_crc": expect_crc,
    }
    return result


def bench_echo(pipe: Pipe, count: int, size: int) -> dict:
    payload = bytes(range(256)) * (size // 256 + 1)
    payload = payload[:size]
    t0 = time.perf_counter()
    bad = 0
    for _ in range(count):
        if pipe.request(CMD_ECHO, payload) != payload:
            bad += 1
    dt = time.perf_counter() - t0
    return {"count": count, "size": size, "seconds": dt, "bad": bad}


def bench_hid(count: int) -> dict:
    """Time raw-HID request/response round trips (GET_ID, cmd 6): the shape of
    every per-chunk ACKed transfer the host does today (firmware update, font
    pack), 56 payload bytes per round trip."""
    import hid
    cands = [i for i in hid.enumerate(VID, 0)
             if i["product_id"] in KNOWN_PIDS and i["usage_page"] == 0xFF61 and i["usage"] == 0x62]
    if not cands:
        raise SystemExit("raw HID interface not found (stop the host app first)")
    dev = hid.Device(path=cands[0]["path"])
    try:
        req = bytes([0x00, 0x50, 0x06]) + bytes(62)
        # warm up
        dev.write(req)
        dev.read(64, timeout=1000)
        t0 = time.perf_counter()
        for _ in range(count):
            dev.write(req)
            if not dev.read(64, timeout=1000):
                raise SystemExit("HID read timed out")
        dt = time.perf_counter() - t0
    finally:
        dev.close()
    return {"count": count, "seconds": dt}


def mbs(nbytes: int, seconds: float) -> str:
    return f"{nbytes / seconds / 1e6:.3f} MB/s" if seconds > 0 else "n/a"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", help="serial port (default: search by VID/PID)")
    ap.add_argument("--mb", type=float, default=4.0, help="SINK payload to stream, in MB (default 4)")
    ap.add_argument("--frame", type=int, default=4096, help="SINK payload bytes per frame (default 4096)")
    ap.add_argument("--write-chunk", type=int, default=65536, help="bytes per serial write() call")
    ap.add_argument("--echo", type=int, default=200, help="ECHO round trips to time (0 skips)")
    ap.add_argument("--echo-size", type=int, default=512, help="ECHO payload bytes (firmware max 512)")
    ap.add_argument("--hid", action="store_true", help="also time raw-HID GET_ID round trips")
    ap.add_argument("--hid-count", type=int, default=500)
    ap.add_argument("--timeout", type=float, default=5.0)
    args = ap.parse_args(argv)

    port = args.port or find_port()
    print(f"pipe: {port}")
    pipe = Pipe(port, args.timeout)
    try:
        info = pipe.request(CMD_PING)
        proto, max_payload, epsize, out_cap = struct.unpack_from("<BHBB", info)
        fw = info[5:].split(b"\0", 1)[0].decode(errors="replace")
        print(f"  firmware {fw}, pipe protocol {proto}, max buffered payload {max_payload}, "
              f"packet {epsize} B, OUT queue {out_cap} packets")

        total = int(args.mb * 1_000_000)
        r = bench_sink(pipe, total, args.frame, args.write_chunk)
        s = r["stats"]
        print(f"  SINK host->keyboard: {r['payload_bytes']} B in {r['frames']} frames of {args.frame} B")
        print(f"    host write() time    {r['host_write_s']:.3f} s  -> {mbs(r['wire_bytes'], r['host_write_s'])} on the wire")
        print(f"    host total (to STAT) {r['host_total_s']:.3f} s  -> {mbs(r['payload_bytes'], r['host_total_s'])} payload")
        if r["device_ms"] > 0:
            print(f"    keyboard clock       {r['device_ms']} ms     -> {mbs(r['payload_bytes'], r['device_ms'] / 1000)} payload")
        print(f"    keyboard: {s['sink_bytes']} B, {s['frames_ok']} good frames, {s['frames_bad']} bad, "
              f"{s['resync_bytes']} resync bytes, crc 0x{s['sink_crc']:08x} (expected 0x{r['expect_crc']:08x})")
        print(f"    integrity: {'OK' if r['ok'] else 'MISMATCH'}")

        if args.echo:
            e = bench_echo(pipe, args.echo, args.echo_size)
            per = e["seconds"] / e["count"] * 1000
            print(f"  ECHO round trips: {e['count']} x {e['size']} B in {e['seconds']:.3f} s "
                  f"-> {per:.2f} ms each, {mbs(e['count'] * e['size'], e['seconds'])} each way, {e['bad']} bad")
    finally:
        pipe.close()

    if args.hid:
        h = bench_hid(args.hid_count)
        per = h["seconds"] / h["count"] * 1000
        print(f"  raw HID GET_ID round trips: {h['count']} in {h['seconds']:.3f} s -> {per:.2f} ms each, "
              f"{mbs(h['count'] * 56, h['seconds'])} at 56 payload bytes per ACKed report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
