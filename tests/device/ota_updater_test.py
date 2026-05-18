"""Tests for polyhost.device.ota_updater.

All tests use a lightweight mock HID object; no real hardware is required.
"""
import binascii
import struct
import tempfile
import os
import unittest
from unittest.mock import MagicMock, call

from polyhost.device.ota_updater import (
    get_fw_version,
    flash_firmware,
    HID_POLYKYBD,
    CMD_OTA_GET_VERSION,
    CMD_OTA_BEGIN,
    CMD_OTA_CHUNK,
    CMD_OTA_COMMIT,
    OTA_CHUNK_SIZE,
    OTA_VERSION_LEN,
    OTA_MAX_FW_SIZE,
)

ACK = ord('.')
NACK = ord('!')


def _ack_reply(cmd: int, extra: bytes = b'') -> bytearray:
    """Build a 64-byte ACK reply for a given command."""
    buf = bytearray(64)
    buf[0] = HID_POLYKYBD
    buf[1] = cmd
    buf[2] = ACK
    buf[3:3 + len(extra)] = extra
    return buf


def _nack_reply(cmd: int) -> bytearray:
    buf = bytearray(64)
    buf[0] = HID_POLYKYBD
    buf[1] = cmd
    buf[2] = NACK
    return buf


def _version_reply(version: str, fw_size: int, fw_crc: int) -> bytearray:
    """Build a proper GET_FW_VERSION response."""
    extra = bytearray(OTA_VERSION_LEN + 8)
    encoded = version.encode('utf-8')[:OTA_VERSION_LEN]
    extra[:len(encoded)] = encoded
    struct.pack_into('<I', extra, OTA_VERSION_LEN, fw_size)
    struct.pack_into('<I', extra, OTA_VERSION_LEN + 4, fw_crc)
    return _ack_reply(CMD_OTA_GET_VERSION, bytes(extra))


def _make_hid(side_effects):
    """Return a mock HID whose send_and_read returns successive side_effects."""
    hid = MagicMock()
    hid.send_and_read.side_effect = side_effects
    return hid


def _write_bin(data: bytes) -> str:
    """Write data to a temp .bin file, return the path."""
    fd, path = tempfile.mkstemp(suffix='.bin')
    os.write(fd, data)
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# get_fw_version
# ---------------------------------------------------------------------------

class TestGetFwVersion(unittest.TestCase):

    def test_happy_path_parses_all_fields(self):
        version = "0.7.2"
        fw_size = 512 * 1024
        fw_crc  = 0xDEADBEEF
        hid = _make_hid([(True, _version_reply(version, fw_size, fw_crc))])

        ok, info = get_fw_version(hid)

        self.assertTrue(ok)
        self.assertEqual(info['version'], version)
        self.assertEqual(info['fw_size'], fw_size)
        self.assertEqual(info['fw_crc'], fw_crc)

    def test_request_packet_format(self):
        hid = _make_hid([(True, _version_reply("1.0", 0, 0))])
        get_fw_version(hid)
        sent_pkt = hid.send_and_read.call_args[0][0]
        self.assertEqual(sent_pkt[0], HID_POLYKYBD)
        self.assertEqual(sent_pkt[1], CMD_OTA_GET_VERSION)

    def test_request_uses_5000ms_timeout(self):
        hid = _make_hid([(True, _version_reply("1.0", 0, 0))])
        get_fw_version(hid)
        timeout = hid.send_and_read.call_args[1].get('timeout') or hid.send_and_read.call_args[0][1]
        self.assertEqual(timeout, 5000)

    def test_hid_failure_returns_false(self):
        hid = _make_hid([(False, bytearray(64))])
        ok, info = get_fw_version(hid)
        self.assertFalse(ok)
        self.assertEqual(info, {})

    def test_short_reply_returns_false(self):
        hid = _make_hid([(True, bytearray(10))])
        ok, info = get_fw_version(hid)
        self.assertFalse(ok)

    def test_nack_returns_false(self):
        hid = _make_hid([(True, _nack_reply(CMD_OTA_GET_VERSION))])
        ok, info = get_fw_version(hid)
        self.assertFalse(ok)

    def test_wrong_marker_byte_returns_false(self):
        reply = _version_reply("1.0", 0, 0)
        reply[0] = 0x00   # corrupt marker
        hid = _make_hid([(True, reply)])
        ok, info = get_fw_version(hid)
        self.assertFalse(ok)

    def test_wrong_command_echo_returns_false(self):
        reply = _version_reply("1.0", 0, 0)
        reply[1] = 0xFF   # wrong command echo
        hid = _make_hid([(True, reply)])
        ok, info = get_fw_version(hid)
        self.assertFalse(ok)

    def test_version_string_null_trimmed(self):
        hid = _make_hid([(True, _version_reply("0.7.1", 0, 0))])
        _, info = get_fw_version(hid)
        self.assertNotIn('\x00', info['version'])


# ---------------------------------------------------------------------------
# flash_firmware — input validation
# ---------------------------------------------------------------------------

class TestFlashFirmwareValidation(unittest.TestCase):

    def test_empty_file_returns_false(self):
        path = _write_bin(b'')
        try:
            ok, msg = flash_firmware(MagicMock(), path)
            self.assertFalse(ok)
            self.assertIn("empty", msg.lower())
        finally:
            os.unlink(path)

    def test_file_too_large_returns_false(self):
        path = _write_bin(b'\x00' * (OTA_MAX_FW_SIZE + 1))
        try:
            ok, msg = flash_firmware(MagicMock(), path)
            self.assertFalse(ok)
            self.assertIn("large", msg.lower())
        finally:
            os.unlink(path)

    def test_exactly_max_size_is_accepted_by_validation(self):
        # Passes size check — BEGIN would fail without a real HID, but that
        # means we get past the validation gate.
        fw = b'\xAB' * OTA_MAX_FW_SIZE
        path = _write_bin(fw)
        try:
            hid = _make_hid([(False, bytearray(64))])
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn("BEGIN", msg)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware — OTA_BEGIN
# ---------------------------------------------------------------------------

class TestFlashFirmwareBegin(unittest.TestCase):

    def _fw_and_path(self, size=112):
        fw = bytes(range(size % 256)) * (size // 256 + 1)
        fw = fw[:size]
        return fw, _write_bin(fw)

    def test_begin_packet_byte_layout(self):
        fw, path = self._fw_and_path(112)
        try:
            fw_crc = binascii.crc32(fw) & 0xFFFFFFFF
            chunks = (len(fw) + OTA_CHUNK_SIZE - 1) // OTA_CHUNK_SIZE
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _ack_reply(CMD_OTA_CHUNK))] * chunks +
                [(True, _ack_reply(CMD_OTA_COMMIT))]
            )
            flash_firmware(hid, path)
            begin_pkt = hid.send_and_read.call_args_list[0][0][0]
            self.assertEqual(begin_pkt[0], HID_POLYKYBD)
            self.assertEqual(begin_pkt[1], CMD_OTA_BEGIN)
            size_field = struct.unpack_from('<I', bytes(begin_pkt), 2)[0]
            crc_field  = struct.unpack_from('<I', bytes(begin_pkt), 6)[0]
            self.assertEqual(size_field, len(fw))
            self.assertEqual(crc_field, fw_crc)
        finally:
            os.unlink(path)

    def test_begin_timeout_is_5000ms(self):
        fw, path = self._fw_and_path(56)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _ack_reply(CMD_OTA_CHUNK))] +
                [(True, _ack_reply(CMD_OTA_COMMIT))]
            )
            flash_firmware(hid, path)
            begin_call = hid.send_and_read.call_args_list[0]
            timeout = begin_call[1].get('timeout') or begin_call[0][1]
            self.assertEqual(timeout, 5000)
        finally:
            os.unlink(path)

    def test_begin_nack_returns_false(self):
        fw, path = self._fw_and_path(56)
        try:
            hid = _make_hid([(True, _nack_reply(CMD_OTA_BEGIN))])
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn("BEGIN", msg)
        finally:
            os.unlink(path)

    def test_begin_hid_failure_returns_false(self):
        fw, path = self._fw_and_path(56)
        try:
            hid = _make_hid([(False, bytearray(64))])
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware — OTA_CHUNK
# ---------------------------------------------------------------------------

class TestFlashFirmwareChunks(unittest.TestCase):

    def _simple_flash(self, fw: bytes):
        path = _write_bin(fw)
        chunks = (len(fw) + OTA_CHUNK_SIZE - 1) // OTA_CHUNK_SIZE
        hid = _make_hid(
            [(True, _ack_reply(CMD_OTA_BEGIN))] +
            [(True, _ack_reply(CMD_OTA_CHUNK))] * chunks +
            [(True, _ack_reply(CMD_OTA_COMMIT))]
        )
        ok, msg = flash_firmware(hid, path)
        os.unlink(path)
        return ok, msg, hid, chunks

    def test_single_chunk_firmware(self):
        ok, msg, hid, chunks = self._simple_flash(b'\xAB' * OTA_CHUNK_SIZE)
        self.assertTrue(ok)
        self.assertEqual(chunks, 1)
        self.assertEqual(hid.send_and_read.call_count, 3)  # BEGIN + 1 CHUNK + COMMIT

    def test_exact_two_chunks(self):
        ok, _, hid, chunks = self._simple_flash(b'\xCD' * (OTA_CHUNK_SIZE * 2))
        self.assertTrue(ok)
        self.assertEqual(chunks, 2)
        self.assertEqual(hid.send_and_read.call_count, 4)  # BEGIN + 2 CHUNKS + COMMIT

    def test_partial_last_chunk_padded_with_ff(self):
        fw = b'\x11' * (OTA_CHUNK_SIZE + 3)   # 3 bytes in second chunk
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _ack_reply(CMD_OTA_CHUNK))] * 2 +
                [(True, _ack_reply(CMD_OTA_COMMIT))]
            )
            flash_firmware(hid, path)
            last_chunk_call = hid.send_and_read.call_args_list[2]  # 0=BEGIN,1=chunk0,2=chunk1
            pkt = last_chunk_call[0][0]
            # bytes [6..8] are the 3 real bytes; [9..61] should be 0xFF padding
            real_data = bytes(pkt[6:9])
            pad_data  = bytes(pkt[9:6 + OTA_CHUNK_SIZE])
            self.assertEqual(real_data, b'\x11' * 3)
            self.assertEqual(pad_data, b'\xff' * (OTA_CHUNK_SIZE - 3))
        finally:
            os.unlink(path)

    def test_chunk_packet_offset_field(self):
        fw = b'\x55' * (OTA_CHUNK_SIZE * 3)
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _ack_reply(CMD_OTA_CHUNK))] * 3 +
                [(True, _ack_reply(CMD_OTA_COMMIT))]
            )
            flash_firmware(hid, path)
            for i in range(3):
                chunk_call = hid.send_and_read.call_args_list[1 + i]
                pkt = chunk_call[0][0]
                self.assertEqual(pkt[0], HID_POLYKYBD)
                self.assertEqual(pkt[1], CMD_OTA_CHUNK)
                offset = struct.unpack_from('<I', bytes(pkt), 2)[0]
                self.assertEqual(offset, i * OTA_CHUNK_SIZE)
        finally:
            os.unlink(path)

    def test_chunk_timeout_is_5000ms(self):
        fw = b'\xAA' * OTA_CHUNK_SIZE
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _ack_reply(CMD_OTA_CHUNK))] +
                [(True, _ack_reply(CMD_OTA_COMMIT))]
            )
            flash_firmware(hid, path)
            chunk_call = hid.send_and_read.call_args_list[1]
            timeout = chunk_call[1].get('timeout') or chunk_call[0][1]
            self.assertEqual(timeout, 5000)
        finally:
            os.unlink(path)

    def test_chunk_retried_up_to_3_times_on_nack(self):
        fw = b'\xBB' * OTA_CHUNK_SIZE
        path = _write_bin(fw)
        try:
            # 3 NACKs for the single chunk → should fail
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _nack_reply(CMD_OTA_CHUNK))] * 3
            )
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn("CHUNK", msg)
            # 1 BEGIN + 3 CHUNK attempts
            self.assertEqual(hid.send_and_read.call_count, 4)
        finally:
            os.unlink(path)

    def test_chunk_succeeds_on_second_attempt(self):
        fw = b'\xCC' * OTA_CHUNK_SIZE
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN)),
                 (True, _nack_reply(CMD_OTA_CHUNK)),   # first attempt fails
                 (True, _ack_reply(CMD_OTA_CHUNK)),    # second attempt succeeds
                 (True, _ack_reply(CMD_OTA_COMMIT))]
            )
            ok, msg = flash_firmware(hid, path)
            self.assertTrue(ok)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware — OTA_COMMIT
# ---------------------------------------------------------------------------

class TestFlashFirmwareCommit(unittest.TestCase):

    def test_commit_packet_format(self):
        fw = b'\x01' * OTA_CHUNK_SIZE
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN)),
                 (True, _ack_reply(CMD_OTA_CHUNK)),
                 (True, _ack_reply(CMD_OTA_COMMIT))]
            )
            flash_firmware(hid, path)
            commit_pkt = hid.send_and_read.call_args_list[-1][0][0]
            self.assertEqual(commit_pkt[0], HID_POLYKYBD)
            self.assertEqual(commit_pkt[1], CMD_OTA_COMMIT)
        finally:
            os.unlink(path)

    def test_commit_nack_returns_false(self):
        fw = b'\x01' * OTA_CHUNK_SIZE
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN)),
                 (True, _ack_reply(CMD_OTA_CHUNK)),
                 (True, _nack_reply(CMD_OTA_COMMIT))]
            )
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn("COMMIT", msg)
        finally:
            os.unlink(path)

    def test_commit_timeout_is_5000ms(self):
        fw = b'\x01' * OTA_CHUNK_SIZE
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN)),
                 (True, _ack_reply(CMD_OTA_CHUNK)),
                 (True, _ack_reply(CMD_OTA_COMMIT))]
            )
            flash_firmware(hid, path)
            commit_call = hid.send_and_read.call_args_list[-1]
            timeout = commit_call[1].get('timeout') or commit_call[0][1]
            self.assertEqual(timeout, 5000)
        finally:
            os.unlink(path)

    def test_success_returns_true_with_message(self):
        fw = b'\x01' * OTA_CHUNK_SIZE
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN)),
                 (True, _ack_reply(CMD_OTA_CHUNK)),
                 (True, _ack_reply(CMD_OTA_COMMIT))]
            )
            ok, msg = flash_firmware(hid, path)
            self.assertTrue(ok)
            self.assertGreater(len(msg), 0)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware — cancellation
# ---------------------------------------------------------------------------

class TestFlashFirmwareCancellation(unittest.TestCase):

    def test_cancel_before_first_chunk(self):
        fw = b'\x42' * (OTA_CHUNK_SIZE * 5)
        path = _write_bin(fw)
        try:
            cancel_flag = [False]
            calls = [0]

            def side_effect(pkt, timeout):
                calls[0] += 1
                if calls[0] == 1:   # BEGIN
                    cancel_flag[0] = True
                    return True, _ack_reply(CMD_OTA_BEGIN)
                return True, _ack_reply(CMD_OTA_CHUNK)

            hid = MagicMock()
            hid.send_and_read.side_effect = side_effect

            ok, msg = flash_firmware(hid, path, cancel_flag=cancel_flag)
            self.assertFalse(ok)
            self.assertIn("cancel", msg.lower())
            # Only BEGIN was sent, no chunks
            self.assertEqual(calls[0], 1)
        finally:
            os.unlink(path)

    def test_cancel_mid_stream(self):
        fw = b'\x42' * (OTA_CHUNK_SIZE * 10)
        path = _write_bin(fw)
        try:
            cancel_flag = [False]
            calls = [0]

            def side_effect(pkt, timeout):
                calls[0] += 1
                if calls[0] == 1:
                    return True, _ack_reply(CMD_OTA_BEGIN)
                if calls[0] == 4:   # cancel after 3rd chunk
                    cancel_flag[0] = True
                return True, _ack_reply(CMD_OTA_CHUNK)

            hid = MagicMock()
            hid.send_and_read.side_effect = side_effect

            ok, msg = flash_firmware(hid, path, cancel_flag=cancel_flag)
            self.assertFalse(ok)
            self.assertIn("cancel", msg.lower())
            # BEGIN + 3 chunks, then cancel check stops the loop
            self.assertEqual(calls[0], 4)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware — progress callback
# ---------------------------------------------------------------------------

class TestFlashFirmwareProgress(unittest.TestCase):

    def test_progress_callback_called(self):
        fw = b'\xAA' * (OTA_CHUNK_SIZE * 3)
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _ack_reply(CMD_OTA_CHUNK))] * 3 +
                [(True, _ack_reply(CMD_OTA_COMMIT))]
            )
            progress_calls = []
            flash_firmware(hid, path, progress_cb=lambda pct, m: progress_calls.append(pct))
            self.assertGreater(len(progress_calls), 0)
        finally:
            os.unlink(path)

    def test_progress_starts_at_0_and_ends_at_100(self):
        fw = b'\xBB' * OTA_CHUNK_SIZE
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN)),
                 (True, _ack_reply(CMD_OTA_CHUNK)),
                 (True, _ack_reply(CMD_OTA_COMMIT))]
            )
            pcts = []
            flash_firmware(hid, path, progress_cb=lambda pct, m: pcts.append(pct))
            self.assertEqual(pcts[0], 0)
            self.assertEqual(pcts[-1], 100)
        finally:
            os.unlink(path)

    def test_progress_never_decreases(self):
        fw = b'\xCC' * (OTA_CHUNK_SIZE * 200)
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _ack_reply(CMD_OTA_CHUNK))] * 200 +
                [(True, _ack_reply(CMD_OTA_COMMIT))]
            )
            pcts = []
            flash_firmware(hid, path, progress_cb=lambda pct, m: pcts.append(pct))
            for a, b in zip(pcts, pcts[1:]):
                self.assertLessEqual(a, b)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# CRC32 correctness
# ---------------------------------------------------------------------------

class TestCrc32(unittest.TestCase):

    def test_crc32_sent_in_begin_matches_python_binascii(self):
        fw = bytes(range(256)) * 4
        path = _write_bin(fw)
        try:
            expected_crc = binascii.crc32(fw) & 0xFFFFFFFF
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _ack_reply(CMD_OTA_CHUNK))] * ((len(fw) + OTA_CHUNK_SIZE - 1) // OTA_CHUNK_SIZE) +
                [(True, _ack_reply(CMD_OTA_COMMIT))]
            )
            flash_firmware(hid, path)
            begin_pkt = hid.send_and_read.call_args_list[0][0][0]
            sent_crc = struct.unpack_from('<I', bytes(begin_pkt), 6)[0]
            self.assertEqual(sent_crc, expected_crc)
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
