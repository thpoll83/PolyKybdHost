"""The bulk pipe probe (polyhost/device/bulk_pipe.py), without a keyboard.

* framing against the firmware's layout (poly_pipe.h);
* the port search by USB identity over a fake comports();
* probe()/detect() over a fake serial port: answers, stays mute, is busy;
* PolyKybd.probe_bulk_pipe caches the transport and forget_bulk_pipe drops it.
Every way the pipe can be unavailable must read as "hid", never raise: the
pipe is optional.
"""
import struct
import types
import unittest
import zlib

from polyhost.device import bulk_pipe as bp


class _Port:
    def __init__(self, device, vid, pid):
        self.device, self.vid, self.pid = device, vid, pid


class FakeSerial:
    """A pyserial-like port backed by a firmware stub that answers PING, RESET,
    SINK and STAT the way poly_pipe.c does. ``drop_frame`` loses one SINK frame
    (the count and CRC then disagree with the host's), ``clock_ms`` is the
    keyboard clock advanced per SINK frame."""

    def __init__(self, answer=True, fw="1.9.3", drop_frame=None, ms_per_frame=5):
        self.answer = answer
        self.fw = fw
        self.drop_frame = drop_frame
        self.ms_per_frame = ms_per_frame
        self.parser = bp.FrameParser()
        self.out = bytearray()
        self.closed = False
        self.sink_bytes = self.crc = self.first_ms = self.last_ms = self.seen = 0
        self.frames_ok = 0

    @property
    def in_waiting(self):
        return len(self.out)

    def write(self, data):
        for cmd, payload in self.parser.feed(bytes(data)):
            self.frames_ok += 1
            if cmd == bp.CMD_PING and self.answer:
                self.out += bp.pack_frame(cmd | bp.REPLY,
                                          struct.pack("<BHBB", 1, 512, 64, 8) + self.fw.encode() + b"\0")
            elif cmd == bp.CMD_RESET:
                self.sink_bytes = self.crc = self.first_ms = self.last_ms = self.seen = 0
                self.out += bp.pack_frame(cmd | bp.REPLY)
            elif cmd == bp.CMD_SINK:
                self.seen += 1
                if self.seen == self.drop_frame:
                    continue
                if not self.first_ms:
                    self.first_ms = 1000
                self.last_ms = self.first_ms + self.ms_per_frame * self.seen
                self.sink_bytes += len(payload)
                self.crc = zlib.crc32(payload, self.crc) & 0xFFFFFFFF
            elif cmd == bp.CMD_STAT:
                self.out += bp.pack_frame(cmd | bp.REPLY, struct.pack(
                    "<7I", self.sink_bytes, self.frames_ok, 0, 0, self.crc, self.first_ms, self.last_ms))
        return len(data)

    def read(self, n):
        chunk, self.out = bytes(self.out[:n]), self.out[n:]
        return chunk

    def close(self):
        self.closed = True


class FramingTest(unittest.TestCase):
    def test_layout(self):
        f = bp.pack_frame(bp.CMD_ECHO, b"ab")
        self.assertEqual(f[:2], b"PB")
        self.assertEqual(struct.unpack_from("<H", f, 3)[0], 2)
        self.assertEqual(struct.unpack_from("<I", f, 7)[0],
                         zlib.crc32(bytes([bp.CMD_ECHO, 2, 0]) + b"ab") & 0xFFFFFFFF)

    def test_parser_reassembles_behind_noise(self):
        reply = bp.pack_frame(bp.CMD_STAT | bp.REPLY, bytes(28))
        p = bp.FrameParser()
        self.assertEqual(p.feed(b"AT\r\n" + reply[:6]), [])
        self.assertEqual(p.feed(reply[6:]), [(bp.CMD_STAT | bp.REPLY, bytes(28))])
        self.assertEqual(p.dropped, 4)

    def test_parse_ping_and_stat(self):
        ping = bp.parse_ping(struct.pack("<BHBB", 1, 512, 64, 8) + b"1.9.3\0x")
        self.assertEqual(ping["fw"], "1.9.3")
        self.assertEqual(ping["epsize"], 64)
        with self.assertRaises(ValueError):
            bp.parse_ping(b"\1\0")
        st = bp.parse_stat(struct.pack("<7I", *range(7)))
        self.assertEqual(st["last_ms"], 6)
        self.assertEqual(bp.sink_crc_chain([b"ab", b"c"]), zlib.crc32(b"abc") & 0xFFFFFFFF)


class PortSearchTest(unittest.TestCase):
    def test_matches_vid_and_known_pid_only(self):
        ports = [_Port("/dev/ttyACM0", 0x2E8A, 0x000A), _Port("COM7", 0x2021, 0x2008)]
        self.assertEqual(bp.find_port(0x2021, (0x2007, 0x2008), comports=lambda: ports), "COM7")
        self.assertIsNone(bp.find_port(0x2021, (0x2007,), comports=lambda: ports))
        self.assertIsNone(bp.find_port(0x2021, (0x2007,), comports=lambda: []))


class ProbeTest(unittest.TestCase):
    def test_answering_port_is_the_pipe_with_a_measured_rate(self):
        ser = FakeSerial(ms_per_frame=5)   # 4096 B per 5 ms on the keyboard clock
        info = bp.probe("COM7", serial_open=lambda p: ser)
        self.assertEqual(info["fw"], "1.9.3")
        self.assertEqual(info["port"], "COM7")
        self.assertTrue(ser.closed)
        frames = bp.PROBE_STREAM_BYTES // bp.PROBE_FRAME_BYTES
        # first_ms is set at the first frame, last_ms after the last: (frames) x 5 ms
        expect = frames * bp.PROBE_FRAME_BYTES / (frames * 5 / 1000) / 1e6
        self.assertAlmostEqual(info["rate_mbps"], expect, places=3)

    def test_a_port_that_loses_bytes_is_no_link(self):
        # A fast channel that corrupts is worse than none: HID only, with a warning.
        ser = FakeSerial(drop_frame=3)
        self.assertIsNone(bp.probe("COM7", serial_open=lambda p: ser))
        self.assertTrue(ser.closed)

    def test_rate_label_rounding(self):
        self.assertEqual(bp.rate_label(0.597), "0.6 MB/s")
        self.assertEqual(bp.rate_label(1.25), "1.2 MB/s")
        self.assertEqual(bp.rate_label(12.4), "12 MB/s")

    def test_mute_port_is_hid_only(self):
        ser = FakeSerial(answer=False)
        self.assertIsNone(bp.probe("COM7", timeout=0.05, serial_open=lambda p: ser))
        self.assertTrue(ser.closed)

    def test_busy_or_forbidden_port_is_hid_only(self):
        def refuse(_p):
            raise PermissionError("busy")
        self.assertIsNone(bp.probe("COM7", serial_open=refuse))

    def test_detect_folds_absent_port(self):
        self.assertIsNone(bp.detect(0x2021, (0x2007,), comports=lambda: []))
        ports = [_Port("COM7", 0x2021, 0x2007)]
        info = bp.detect(0x2021, (0x2007,), comports=lambda: ports,
                         serial_open=lambda p: FakeSerial(fw="2.0.0"))
        self.assertEqual(info["fw"], "2.0.0")

    def test_broken_enumerator_is_hid_only(self):
        def boom():
            raise RuntimeError("WMI down")
        self.assertIsNone(bp.detect(0x2021, (0x2007,), comports=boom))


class KeyboardCacheTest(unittest.TestCase):
    def test_probe_caches_and_forget_drops(self):
        from polyhost.device.device_settings import DeviceSettings
        from polyhost.device.poly_kybd import PolyKybd

        class _Settings:
            def get(self, name):
                return {"hid_reconnect_retries": 1}.get(name)
        kb = PolyKybd(DeviceSettings(), _Settings())
        self.assertIsNone(kb.get_transport())
        calls = []

        def fake_detect(vid, pids, **_kw):
            calls.append((vid, tuple(pids)))
            return {"port": "COM7", "fw": "1.9.3", "epsize": 64, "out_capacity": 8, "rate_mbps": 0.6}
        orig = bp.detect
        bp.detect = fake_detect
        try:
            self.assertEqual(kb.probe_bulk_pipe(), bp.TRANSPORT_PIPE)
        finally:
            bp.detect = orig
        self.assertEqual(calls, [(0x2021, (0x2007, 0x2008))])
        self.assertEqual(kb.get_pipe_info()["port"], "COM7")
        self.assertEqual(kb.get_link_rate_mbps(), 0.6)
        kb.forget_bulk_pipe()
        self.assertIsNone(kb.get_link_rate_mbps())
        self.assertIsNone(kb.get_transport())
        self.assertIsNone(kb.get_pipe_info())
        bp.detect = lambda *a, **k: None
        try:
            self.assertEqual(kb.probe_bulk_pipe(), bp.TRANSPORT_HID)
        finally:
            bp.detect = orig


if __name__ == "__main__":
    unittest.main()
