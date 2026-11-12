"""The mock keyboard's bulk pipe (device/mock_pipe.py), driven by the unmodified
host code: bulk_pipe.probe with its rate measurement, the firmware update and
the font-pack flash streaming their chunks, and the fallbacks to HID.
"""
import os
import struct
import tempfile
import unittest
import unittest.mock as mock
import zlib

from polyhost.device import bulk_pipe as bp
from polyhost.device import hid_fontpack, hid_fw_up
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.mock_firmware import FaultPlan, MockFirmware, MockHidHelper
from polyhost.device.mock_pipe import PIPE_MIN_PROTOCOL, RIG_RATE_MBPS
from polyhost.device.poly_kybd_mock import PolyKybdMock
from polyhost.services.fontpack_bundle import load_bundle_manifest


def _image(n=20000):
    """A .bin hid_fw_up accepts (a valid boot2 CRC and vector table), padded to n."""
    from polyhost.device.hid_fw_up import _crc32_rp2040
    boot2 = bytes(252)
    head = (boot2 + struct.pack("<I", _crc32_rp2040(boot2))
            + struct.pack("<II", 0x20010000, 0x10000101) + "PolyKybd".encode("utf-16-le"))
    return head + bytes((i * 31 + 7) & 0xFF for i in range(n - len(head)))


def _keyboard(protocol=25, **faults):
    fw = MockFirmware(protocol, faults=FaultPlan(**faults))
    return fw, MockHidHelper(fw)


def _chunk_reports(fw, cmd):
    return sum(1 for w in fw.writes if len(w) > 1 and w[1] == cmd)


class ProbeTest(unittest.TestCase):

    def test_the_probe_finds_the_pipe_and_measures_the_modelled_rate(self):
        kb = PolyKybdMock(DeviceSettings())
        self.assertEqual(kb.probe_bulk_pipe(), bp.TRANSPORT_PIPE)
        info = kb.get_pipe_info()
        self.assertEqual(info["proto"], 2)
        self.assertEqual(info["fw"], kb.firmware.version)
        self.assertEqual(info["port"], kb.firmware.pipe.port_name)
        self.assertAlmostEqual(kb.get_link_rate_mbps(), RIG_RATE_MBPS, delta=0.01)
        self.assertEqual(kb.firmware.pipe.stats["frames_bad"], 0)

    def test_firmware_older_than_the_pipe_has_none(self):
        kb = PolyKybdMock(DeviceSettings(), protocol=PIPE_MIN_PROTOCOL - 1)
        self.assertFalse(kb.pipe_available)
        self.assertEqual(kb.probe_bulk_pipe(), bp.TRANSPORT_HID)
        self.assertIsNone(kb.get_link_rate_mbps())

    def test_a_busy_port_reads_as_hid_only(self):
        kb = PolyKybdMock(DeviceSettings(), faults=FaultPlan(pipe_busy=True))
        self.assertEqual(kb.probe_bulk_pipe(), bp.TRANSPORT_HID)

    def test_the_pipe_can_be_switched_off_and_on(self):
        kb = PolyKybdMock(DeviceSettings())
        kb.pipe_available = False
        self.assertEqual(kb.probe_bulk_pipe(), bp.TRANSPORT_HID)
        kb.pipe_available = True
        self.assertEqual(kb.probe_bulk_pipe(), bp.TRANSPORT_PIPE)


class FramingTest(unittest.TestCase):
    """The parser rules copied from poly_pipe.c."""

    def setUp(self):
        self.fw, _ = _keyboard()
        self.ser = bp.open_port(self.fw.pipe.port_name)

    def test_echo_comes_back_behind_noise(self):
        self.assertEqual(bp.request(self.ser, bp.CMD_ECHO, b"hello"), b"hello")
        self.ser.write(b"AT\r\n")
        self.assertEqual(bp.request(self.ser, bp.CMD_ECHO, b"x"), b"x")
        self.assertEqual(self.fw.pipe.stats["resync_bytes"], 4)

    def test_a_bad_crc_is_counted_and_never_answered(self):
        frame = bytearray(bp.pack_frame(bp.CMD_ECHO, b"abc"))
        frame[-1] ^= 0xFF
        self.ser.write(bytes(frame))
        self.assertEqual(self.ser.in_waiting, 0)
        self.assertEqual(self.fw.pipe.stats["frames_bad"], 1)

    def test_a_buffered_frame_over_512_bytes_is_bad(self):
        self.ser.write(bp.pack_frame(bp.CMD_ECHO, bytes(513)))
        self.assertEqual(self.ser.in_waiting, 0)
        self.assertEqual(self.fw.pipe.stats["frames_bad"], 1)

    def test_a_frame_split_across_writes_assembles(self):
        frame = bp.pack_frame(bp.CMD_ECHO, b"split")
        for b in frame:
            self.ser.write(bytes([b]))
        self.assertEqual(bp.FrameParser().feed(self.ser.read(100)),
                         [(bp.CMD_ECHO | bp.REPLY, b"split")])

    def test_sink_counts_and_chains_the_crc(self):
        bp.request(self.ser, bp.CMD_RESET)
        self.ser.write(bp.pack_frame(bp.CMD_SINK, b"ab") + bp.pack_frame(bp.CMD_SINK, b"c"))
        st = bp.parse_stat(bp.request(self.ser, bp.CMD_STAT))
        self.assertEqual(st["sink_bytes"], 3)
        self.assertEqual(st["sink_crc"], zlib.crc32(b"abc") & 0xFFFFFFFF)

    def test_fw_chunk_with_no_transfer_is_nacked(self):
        reply = bp.request(self.ser, bp.CMD_FW_CHUNK, struct.pack("<I", 0) + b"x")
        self.assertEqual(bp.parse_fw_chunk_reply(reply), (False, 0))

    def test_pipe_protocol_1_does_not_answer_fw_chunk(self):
        self.fw.pipe.proto = 1
        self.assertIsNone(bp.request(self.ser, bp.CMD_FW_CHUNK, b"", timeout=0.05))


class StagingWriterTest(unittest.TestCase):
    """stage_block follows fw_staging_write_chunk(), for HID and pipe chunks alike."""

    def setUp(self):
        self.fw, self.hid = _keyboard()
        self.fw._begin(bytes([0, hid_fontpack.CMD_FONTPACK_BEGIN]), 0, 100, 0, None)

    def test_duplicate_overlap_gap_and_past_end(self):
        fw = self.fw
        self.assertEqual(fw.stage_block(0, b"a" * 40), (True, 40))
        self.assertEqual(fw.stage_block(0, b"a" * 40), (True, 40))     # duplicate: ACK
        self.assertEqual(fw.stage_block(20, b"b" * 40), (True, 60))    # overlap: tail written
        self.assertEqual(bytes(fw._active.data[40:60]), b"b" * 20)
        self.assertEqual(fw.stage_block(80, b"c"), (False, 60))        # ahead of the cursor
        self.assertEqual(fw.stage_block(60, b"d" * 56), (True, 100))   # clamped to the size
        self.assertEqual(fw.stage_block(100, b"e"), (False, 100))      # past the end


class FirmwareUpdateOverThePipeTest(unittest.TestCase):

    def setUp(self):
        self.image = _image()
        fd, self.path = tempfile.mkstemp(suffix=".bin")
        os.write(fd, self.image)
        os.close(fd)
        self.addCleanup(os.remove, self.path)
        p = mock.patch.object(hid_fw_up, "CONFIRM_POLL_INTERVAL_S", 0)
        p.start()
        self.addCleanup(p.stop)

    def _flash(self, fw, hid):
        with mock.patch("time.sleep", lambda s: None):
            return hid_fw_up.flash_firmware(hid, self.path, pipe_port=fw.pipe.port_name)

    def test_the_chunks_go_over_the_pipe_and_apply_boots_the_image(self):
        fw, hid = _keyboard()
        ok, msg = self._flash(fw, hid)
        self.assertTrue(ok, msg)
        self.assertEqual(_chunk_reports(fw, hid_fw_up.CMD_FW_UP_CHUNK), 0)
        self.assertEqual(fw.pipe.fw_chunk_frames, -(-len(self.image) // bp.FW_CHUNK_MAX))
        ok, msg = hid_fw_up.apply_staged_firmware(hid)
        self.assertTrue(ok, msg)
        self.assertEqual(fw.running_image, self.image)

    def test_a_frame_lost_on_the_wire_is_resent_from_the_cursor(self):
        # The lost frame's reply never comes, so the host waits out the drain
        # after the NACK of the frame behind it; shortened here.
        fw, hid = _keyboard(pipe_drop_chunks={236 * 3: 1})
        with mock.patch.object(bp, "FW_CHUNK_DRAIN_S", 0.1):
            ok, msg = self._flash(fw, hid)
        self.assertTrue(ok, msg)
        self.assertEqual(fw.pipe.stats["frames_bad"], 1)
        self.assertEqual(bytes(fw._fw_staging.data), self.image)

    def test_a_rejected_frame_rewinds_and_still_lands_every_byte(self):
        fw, hid = _keyboard(pipe_reject_chunks={236 * 5: 2})
        ok, msg = self._flash(fw, hid)
        self.assertTrue(ok, msg)
        self.assertEqual(bytes(fw._fw_staging.data), self.image)

    def test_a_busy_port_sends_the_whole_image_over_hid(self):
        fw, hid = _keyboard(pipe_busy=True)
        ok, msg = self._flash(fw, hid)
        self.assertTrue(ok, msg)
        self.assertEqual(fw.pipe.fw_chunk_frames, 0)
        self.assertGreater(_chunk_reports(fw, hid_fw_up.CMD_FW_UP_CHUNK), 0)
        self.assertEqual(bytes(fw._fw_staging.data), self.image)

    def test_a_pipe_that_stops_hands_the_rest_to_hid_from_its_cursor(self):
        # The pipe stops after the first window: HID continues at 4 * 236, which
        # is not a multiple of the 56-byte HID chunk.
        fw, hid = _keyboard()
        real = bp.stream_firmware

        def stop_early(ser, data, **kw):
            ok, offset, reason = real(ser, data[:4 * bp.FW_CHUNK_MAX], **kw)
            return False, offset, "port error"
        with mock.patch.object(bp, "stream_firmware", stop_early):
            ok, msg = self._flash(fw, hid)
        self.assertTrue(ok, msg)
        self.assertEqual(fw.pipe.fw_chunk_frames, 4)
        self.assertEqual(bytes(fw._fw_staging.data), self.image)


class FontPackOverThePipeTest(unittest.TestCase):

    def test_a_bundle_streams_over_the_pipe_and_lands(self):
        bundle = next(b for b in load_bundle_manifest()["bundles"] if b["index"] == 0)
        with open(bundle["path"], "rb") as f:
            data = f.read()
        fw, hid = _keyboard()
        ok, msg, status = hid_fontpack.flash_fontpack(hid, bundle["path"], bundle_id=0,
                                                      pipe_port=fw.pipe.port_name)
        self.assertTrue(ok, msg)
        self.assertEqual(status, hid_fontpack.COMMIT_OK)
        self.assertEqual(fw.bundle_data[0], data)
        self.assertEqual(_chunk_reports(fw, hid_fontpack.CMD_FONTPACK_CHUNK), 0)
        self.assertGreater(fw.pipe.fw_chunk_frames, 0)


if __name__ == "__main__":
    unittest.main()
