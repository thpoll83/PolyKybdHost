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

    def __init__(self, answer=True, fw="1.9.3", drop_frame=None, ms_per_frame=5, proto=2,
                 image_size=None, drop_fw_frames=(), reject_fw_frames=()):
        self.answer = answer
        self.fw = fw
        self.proto = proto
        self.drop_frame = drop_frame
        self.ms_per_frame = ms_per_frame
        self.parser = bp.FrameParser()
        self.out = bytearray()
        self.closed = False
        self.sink_bytes = self.crc = self.first_ms = self.last_ms = self.seen = 0
        self.frames_ok = 0
        # FW_CHUNK: the firmware's staging cursor. A frame at the cursor is written
        # and ACKed, one behind it is a duplicate (ACKed, not written), anything
        # else is NACKed with the cursor. drop_fw_frames: 1-based FW_CHUNK frame
        # numbers the "wire" loses (no reply at all, like a bad CRC on the device);
        # reject_fw_frames: ones the firmware NACKs (a slave relay failure).
        self.image_size = image_size
        self.cursor = 0
        self.staged = bytearray()
        self.fw_frames = 0
        self.fw_max_frame = 0
        self.drop_fw_frames = set(drop_fw_frames)
        self.reject_fw_frames = set(reject_fw_frames)

    @property
    def in_waiting(self):
        return len(self.out)

    def write(self, data):
        for cmd, payload in self.parser.feed(bytes(data)):
            self.frames_ok += 1
            if cmd == bp.CMD_PING and self.answer:
                self.out += bp.pack_frame(cmd | bp.REPLY,
                                          struct.pack("<BHBB", self.proto, 512, 64, 8) + self.fw.encode() + b"\0")
            elif cmd == bp.CMD_FW_CHUNK:
                self.fw_frames += 1
                if self.fw_frames in self.drop_fw_frames:
                    continue
                acked = False
                if len(payload) >= 5 and len(payload) - 4 <= bp.FW_CHUNK_MAX:
                    self.fw_max_frame = max(self.fw_max_frame, len(payload) - 4)
                    offset = struct.unpack_from("<I", payload)[0]
                    data = payload[4:]
                    if self.fw_frames in self.reject_fw_frames:
                        acked = False
                    elif offset < self.cursor:
                        acked = True
                    elif offset == self.cursor:
                        if self.image_size is not None and offset + len(data) > self.image_size:
                            data = data[:self.image_size - offset]
                        self.staged += data
                        self.cursor += len(data)
                        acked = True
                self.out += bp.pack_frame(cmd | bp.REPLY,
                                          bytes([ord(".") if acked else ord("!")])
                                          + struct.pack("<I", self.cursor))
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




class FirmwareStreamTest(unittest.TestCase):
    """stream_firmware against the FakeSerial firmware stub: the frames, the
    window, and the two recovery paths (a lost frame, a rejected one)."""

    IMAGE = bytes((i * 31 + 7) & 0xFF for i in range(236 * 9 + 100))   # 10 frames, last partial

    def test_streams_the_whole_image_in_236_byte_frames(self):
        ser = FakeSerial(image_size=len(self.IMAGE))
        seen = []
        ok, offset, reason = bp.stream_firmware(ser, self.IMAGE, progress=seen.append)
        self.assertEqual((ok, offset, reason), (True, len(self.IMAGE), None))
        self.assertEqual(bytes(ser.staged), self.IMAGE)
        self.assertEqual(ser.fw_frames, 10)
        self.assertEqual(ser.fw_max_frame, bp.FW_CHUNK_MAX)
        self.assertEqual(seen[-1], len(self.IMAGE))
        self.assertEqual(seen, sorted(seen))

    def test_starts_from_an_offset(self):
        ser = FakeSerial(image_size=len(self.IMAGE))
        ser.cursor = 300
        ser.staged += self.IMAGE[:300]
        ok, offset, _ = bp.stream_firmware(ser, self.IMAGE, start=300)
        self.assertTrue(ok)
        self.assertEqual(bytes(ser.staged), self.IMAGE)
        self.assertEqual(ser.fw_frames, 9)   # 1924 bytes from 300: 8 full frames + 1 partial

    def test_a_port_error_mid_stream_keeps_the_confirmed_cursor(self):
        # The port vanishes after the first replies: the stream ends with the
        # keyboard's cursor, not 0, so HID continues without re-sending the
        # chunks the keyboard already acknowledged.
        ser = FakeSerial(image_size=len(self.IMAGE))
        real_read = ser.read

        def read(n):
            if ser.fw_frames >= 6:
                raise OSError("device reports readiness to read but returned no data")
            return real_read(n)

        ser.read = read
        ok, offset, reason = bp.stream_firmware(ser, self.IMAGE)
        self.assertFalse(ok)
        self.assertEqual(reason, "port error")
        self.assertGreater(offset, 0)
        self.assertEqual(offset, ser.cursor if ser.cursor <= offset else offset)
        self.assertEqual(self.IMAGE[:offset], bytes(ser.staged[:offset]))

    def test_a_lost_frame_is_recovered_from_the_cursor(self):
        # Frame 3 never reaches the keyboard: frames 4.. are NACKed with the
        # cursor, the drain ends after the short wait, and the stream resumes.
        clock = [0.0]

        def fake_clock():
            clock[0] += 0.01
            return clock[0]

        ser = FakeSerial(image_size=len(self.IMAGE), drop_fw_frames={3})
        ok, offset, reason = bp.stream_firmware(ser, self.IMAGE, clock=fake_clock)
        self.assertEqual((ok, offset, reason), (True, len(self.IMAGE), None))
        self.assertEqual(bytes(ser.staged), self.IMAGE)

    def test_a_rejected_frame_is_resent_from_the_cursor(self):
        ser = FakeSerial(image_size=len(self.IMAGE), reject_fw_frames={2})
        ok, offset, reason = bp.stream_firmware(ser, self.IMAGE)
        self.assertEqual((ok, offset, reason), (True, len(self.IMAGE), None))
        self.assertEqual(bytes(ser.staged), self.IMAGE)

    def test_a_silent_keyboard_reports_where_it_stopped(self):
        clock = [0.0]

        def fake_clock():
            clock[0] += 0.5
            return clock[0]

        ser = FakeSerial(image_size=len(self.IMAGE), drop_fw_frames=set(range(3, 200)))
        ok, offset, reason = bp.stream_firmware(ser, self.IMAGE, clock=fake_clock)
        self.assertFalse(ok)
        self.assertEqual(offset, 2 * 236)
        self.assertEqual(reason, "no reply from the keyboard")

    def test_cancel_stops_the_stream(self):
        ser = FakeSerial(image_size=len(self.IMAGE))
        calls = [0]

        def cancelled():
            calls[0] += 1
            return calls[0] > 2

        ok, offset, reason = bp.stream_firmware(ser, self.IMAGE, cancelled=cancelled)
        self.assertEqual((ok, reason), (False, "cancelled"))
        self.assertLess(offset, len(self.IMAGE))

    def test_frame_layout(self):
        f = bp.fw_chunk_frame(0x01020304, b"xyz")
        self.assertEqual(f[2], bp.CMD_FW_CHUNK)
        self.assertEqual(f[5:9], struct.pack("<I", 0x01020304))
        self.assertEqual(f[9:12], b"xyz")
        self.assertEqual(bp.parse_fw_chunk_reply(b"." + struct.pack("<I", 7)), (True, 7))
        self.assertEqual(bp.parse_fw_chunk_reply(b"!" + struct.pack("<I", 9)), (False, 9))
        self.assertIsNone(bp.parse_fw_chunk_reply(b"."))

if __name__ == "__main__":
    unittest.main()
