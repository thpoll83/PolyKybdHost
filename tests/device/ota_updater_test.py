"""Tests for polyhost.device.ota_updater.

All tests use a lightweight mock HID object; no real hardware is required.

Firmware fixture
----------------
Every valid RP2040 .bin starts with a 256-byte boot2 block whose last 4
bytes are the CRC32 of the preceding 252 bytes, followed by an ARM
Cortex-M0+ vector table (initial SP at offset 256, reset vector at 260).
The helper _make_fw() builds the smallest binary that passes
validate_rp2040_firmware() — 264 bytes, which spans 5 OTA chunks of 56 B.
"""
import binascii
import struct
import tempfile
import os
import unittest
from unittest.mock import MagicMock

from polyhost.device.ota_updater import (
    get_fw_version,
    flash_firmware,
    validate_rp2040_firmware,
    HID_POLYKYBD,
    CMD_OTA_GET_VERSION,
    CMD_OTA_BEGIN,
    CMD_OTA_CHUNK,
    CMD_OTA_COMMIT,
    OTA_CHUNK_SIZE,
    OTA_VERSION_LEN,
    OTA_MAX_FW_SIZE,
    _RP2040_BOOT2_SIZE,
    _RP2040_SRAM_BASE,
    _RP2040_SRAM_END,
)

ACK  = ord('.')
NACK = ord('!')

# ---------------------------------------------------------------------------
# Firmware fixture helpers
# ---------------------------------------------------------------------------

# Minimal valid boot2: 252 zero bytes + correct CRC32
_BOOT2_PAYLOAD = bytes(252)
_BOOT2_CRC     = struct.pack('<I', binascii.crc32(_BOOT2_PAYLOAD) & 0xFFFFFFFF)
# ARM Cortex-M0+ vector table: SP in SRAM, thumb reset vector in flash
_VECTOR_TABLE  = struct.pack('<II', 0x20010000, 0x10000101)
# 264-byte header that passes validate_rp2040_firmware()
_RP2040_HEADER = _BOOT2_PAYLOAD + _BOOT2_CRC + _VECTOR_TABLE


def _make_fw(extra: bytes = b'') -> bytes:
    """Return a valid RP2040 binary with optional extra payload appended."""
    return _RP2040_HEADER + extra


def _chunks(fw: bytes) -> int:
    return (len(fw) + OTA_CHUNK_SIZE - 1) // OTA_CHUNK_SIZE


def _write_bin(data: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix='.bin')
    os.write(fd, data)
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# HID mock helpers
# ---------------------------------------------------------------------------

def _ack_reply(cmd: int, extra: bytes = b'') -> bytearray:
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
    extra = bytearray(OTA_VERSION_LEN + 8)
    encoded = version.encode('utf-8')[:OTA_VERSION_LEN]
    extra[:len(encoded)] = encoded
    struct.pack_into('<I', extra, OTA_VERSION_LEN, fw_size)
    struct.pack_into('<I', extra, OTA_VERSION_LEN + 4, fw_crc)
    return _ack_reply(CMD_OTA_GET_VERSION, bytes(extra))


def _make_hid(side_effects):
    hid = MagicMock()
    hid.send_and_read.side_effect = side_effects
    return hid


def _flash_hid(fw: bytes):
    """Build a mock HID that ACKs the exact sequence for the given firmware."""
    n = _chunks(fw)
    return _make_hid(
        [(True, _ack_reply(CMD_OTA_BEGIN))] +
        [(True, _ack_reply(CMD_OTA_CHUNK))] * n +
        [(True, _ack_reply(CMD_OTA_COMMIT))]
    )


# ---------------------------------------------------------------------------
# validate_rp2040_firmware
# ---------------------------------------------------------------------------

class TestValidateRp2040Firmware(unittest.TestCase):

    def test_valid_header_passes(self):
        ok, msg = validate_rp2040_firmware(_make_fw())
        self.assertTrue(ok)
        self.assertEqual(msg, '')

    def test_accepts_bytearray(self):
        ok, _ = validate_rp2040_firmware(bytearray(_make_fw()))
        self.assertTrue(ok)

    def test_accepts_exactly_264_bytes(self):
        ok, _ = validate_rp2040_firmware(_make_fw())
        self.assertEqual(len(_make_fw()), 264)
        self.assertTrue(ok)

    def test_too_small_fails(self):
        ok, msg = validate_rp2040_firmware(b'\x00' * 263)
        self.assertFalse(ok)
        self.assertIn('too small', msg.lower())

    def test_empty_fails(self):
        ok, msg = validate_rp2040_firmware(b'')
        self.assertFalse(ok)

    def test_bad_boot2_crc_fails(self):
        fw = bytearray(_make_fw())
        fw[252] ^= 0xFF   # corrupt the stored CRC
        ok, msg = validate_rp2040_firmware(bytes(fw))
        self.assertFalse(ok)
        self.assertIn('CRC32', msg)
        self.assertIn('boot2', msg.lower())

    def test_error_message_mentions_bin_not_uf2(self):
        fw = bytearray(_make_fw())
        fw[252] ^= 0xFF
        _, msg = validate_rp2040_firmware(bytes(fw))
        self.assertIn('.bin', msg)
        self.assertIn('.uf2', msg)

    def test_sp_below_sram_fails(self):
        # SP just below SRAM base
        fw = bytearray(_make_fw())
        struct.pack_into('<I', fw, _RP2040_BOOT2_SIZE, _RP2040_SRAM_BASE - 4)
        ok, msg = validate_rp2040_firmware(bytes(fw))
        self.assertFalse(ok)
        self.assertIn('SP', msg)

    def test_sp_above_sram_fails(self):
        fw = bytearray(_make_fw())
        struct.pack_into('<I', fw, _RP2040_BOOT2_SIZE, _RP2040_SRAM_END + 4)
        ok, msg = validate_rp2040_firmware(bytes(fw))
        self.assertFalse(ok)
        self.assertIn('SP', msg)

    def test_sp_at_sram_base_passes(self):
        fw = bytearray(_make_fw())
        struct.pack_into('<I', fw, _RP2040_BOOT2_SIZE, _RP2040_SRAM_BASE)
        ok, _ = validate_rp2040_firmware(bytes(fw))
        self.assertTrue(ok)

    def test_sp_at_sram_end_passes(self):
        fw = bytearray(_make_fw())
        struct.pack_into('<I', fw, _RP2040_BOOT2_SIZE, _RP2040_SRAM_END)
        ok, _ = validate_rp2040_firmware(bytes(fw))
        self.assertTrue(ok)

    def test_uf2_magic_fails_boot2_check(self):
        # UF2 files start with 0x0A324655 and 0x9E5D5157 — no valid boot2 CRC
        uf2_magic = struct.pack('<II', 0x0A324655, 0x9E5D5157) + bytes(260)
        ok, msg = validate_rp2040_firmware(uf2_magic)
        self.assertFalse(ok)

    def test_random_data_fails(self):
        import hashlib
        # Use deterministic pseudo-random data (sha256 expansion)
        rnd = hashlib.sha256(b'seed').digest() * 16  # 512 bytes
        ok, _ = validate_rp2040_firmware(rnd[:264])
        self.assertFalse(ok)

    def test_valid_large_firmware_passes(self):
        fw = _make_fw(b'\xAB' * (512 * 1024 - 264))
        ok, _ = validate_rp2040_firmware(fw)
        self.assertTrue(ok)

    def test_validate_only_inspects_first_264_bytes(self):
        # Garbage appended after the header must not affect the result
        fw = _make_fw(b'\xFF' * 1000)
        ok, _ = validate_rp2040_firmware(fw)
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# get_fw_version
# ---------------------------------------------------------------------------

class TestGetFwVersion(unittest.TestCase):

    def test_happy_path_parses_all_fields(self):
        version = '0.7.2'
        fw_size = 512 * 1024
        fw_crc  = 0xDEADBEEF
        hid = _make_hid([(True, _version_reply(version, fw_size, fw_crc))])
        ok, info = get_fw_version(hid)
        self.assertTrue(ok)
        self.assertEqual(info['version'], version)
        self.assertEqual(info['fw_size'], fw_size)
        self.assertEqual(info['fw_crc'], fw_crc)

    def test_request_packet_format(self):
        hid = _make_hid([(True, _version_reply('1.0', 0, 0))])
        get_fw_version(hid)
        pkt = hid.send_and_read.call_args[0][0]
        self.assertEqual(pkt[0], HID_POLYKYBD)
        self.assertEqual(pkt[1], CMD_OTA_GET_VERSION)

    def test_request_uses_5000ms_timeout(self):
        hid = _make_hid([(True, _version_reply('1.0', 0, 0))])
        get_fw_version(hid)
        c = hid.send_and_read.call_args
        timeout = c[1].get('timeout') or c[0][1]
        self.assertEqual(timeout, 5000)

    def test_hid_failure_returns_false(self):
        hid = _make_hid([(False, bytearray(64))])
        ok, info = get_fw_version(hid)
        self.assertFalse(ok)
        self.assertEqual(info, {})

    def test_short_reply_returns_false(self):
        hid = _make_hid([(True, bytearray(10))])
        ok, _ = get_fw_version(hid)
        self.assertFalse(ok)

    def test_nack_returns_false(self):
        hid = _make_hid([(True, _nack_reply(CMD_OTA_GET_VERSION))])
        ok, _ = get_fw_version(hid)
        self.assertFalse(ok)

    def test_wrong_marker_byte_returns_false(self):
        reply = bytearray(_version_reply('1.0', 0, 0))
        reply[0] = 0x00
        hid = _make_hid([(True, reply)])
        ok, _ = get_fw_version(hid)
        self.assertFalse(ok)

    def test_wrong_command_echo_returns_false(self):
        reply = bytearray(_version_reply('1.0', 0, 0))
        reply[1] = 0xFF
        hid = _make_hid([(True, reply)])
        ok, _ = get_fw_version(hid)
        self.assertFalse(ok)

    def test_version_string_null_trimmed(self):
        hid = _make_hid([(True, _version_reply('0.7.1', 0, 0))])
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
            self.assertIn('empty', msg.lower())
        finally:
            os.unlink(path)

    def test_file_too_large_returns_false(self):
        path = _write_bin(b'\x00' * (OTA_MAX_FW_SIZE + 1))
        try:
            ok, msg = flash_firmware(MagicMock(), path)
            self.assertFalse(ok)
            self.assertIn('large', msg.lower())
        finally:
            os.unlink(path)

    def test_invalid_rp2040_binary_returns_false(self):
        # Random bytes that won't have a valid boot2 CRC
        path = _write_bin(b'\xAB' * 300)
        try:
            ok, msg = flash_firmware(MagicMock(), path)
            self.assertFalse(ok)
            self.assertIn('CRC32', msg)
        finally:
            os.unlink(path)

    def test_uf2_file_rejected_before_hid_traffic(self):
        uf2_magic = struct.pack('<II', 0x0A324655, 0x9E5D5157) + bytes(300)
        path = _write_bin(uf2_magic)
        hid = MagicMock()
        try:
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            hid.send_and_read.assert_not_called()
        finally:
            os.unlink(path)

    def test_valid_rp2040_binary_proceeds_to_hid(self):
        fw = _make_fw()
        path = _write_bin(fw)
        try:
            # BEGIN fails — proves we reached the HID stage
            hid = _make_hid([(False, bytearray(64))])
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn('BEGIN', msg)
            hid.send_and_read.assert_called_once()
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware — OTA_BEGIN
# ---------------------------------------------------------------------------

class TestFlashFirmwareBegin(unittest.TestCase):

    def test_begin_packet_byte_layout(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            expected_crc = binascii.crc32(fw) & 0xFFFFFFFF
            ok, msg = flash_firmware(_flash_hid(fw), path)
            self.assertTrue(ok)
            begin_pkt = MagicMock()   # re-flash to capture packet
        finally:
            os.unlink(path)

        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            begin_pkt = hid.send_and_read.call_args_list[0][0][0]
            self.assertEqual(begin_pkt[0], HID_POLYKYBD)
            self.assertEqual(begin_pkt[1], CMD_OTA_BEGIN)
            size_field = struct.unpack_from('<I', bytes(begin_pkt), 2)[0]
            crc_field  = struct.unpack_from('<I', bytes(begin_pkt), 6)[0]
            self.assertEqual(size_field, len(fw))
            self.assertEqual(crc_field, expected_crc)
        finally:
            os.unlink(path)

    def test_begin_timeout_is_5000ms(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            c = hid.send_and_read.call_args_list[0]
            timeout = c[1].get('timeout') or c[0][1]
            self.assertEqual(timeout, 5000)
        finally:
            os.unlink(path)

    def test_begin_nack_returns_false(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _make_hid([(True, _nack_reply(CMD_OTA_BEGIN))])
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn('BEGIN', msg)
        finally:
            os.unlink(path)

    def test_begin_hid_failure_returns_false(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _make_hid([(False, bytearray(64))])
            ok, _ = flash_firmware(hid, path)
            self.assertFalse(ok)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware — OTA_CHUNK
# ---------------------------------------------------------------------------

class TestFlashFirmwareChunks(unittest.TestCase):
    """The minimal valid RP2040 binary is 264 bytes = 5 chunks of 56 B.
    Chunk layout: chunks 0-3 are full (56 B each), chunk 4 has 40 real bytes
    plus 16 bytes of 0xFF padding.
    """

    def test_minimal_firmware_sends_correct_chunk_count(self):
        fw   = _make_fw()          # 264 bytes = 5 chunks
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            ok, _ = flash_firmware(hid, path)
            self.assertTrue(ok)
            # 1 BEGIN + 5 CHUNKS + 1 COMMIT
            self.assertEqual(hid.send_and_read.call_count, 7)
        finally:
            os.unlink(path)

    def test_firmware_with_extra_chunk(self):
        # 336 bytes = 6 chunks
        fw   = _make_fw(b'\xCD' * (6 * OTA_CHUNK_SIZE - 264))
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            ok, _ = flash_firmware(hid, path)
            self.assertTrue(ok)
            self.assertEqual(hid.send_and_read.call_count, 8)  # 1+6+1
        finally:
            os.unlink(path)

    def test_partial_last_chunk_padded_with_ff(self):
        # _make_fw() is 264 bytes; chunk 4 (offset 224) has 40 real bytes
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            # call index 0=BEGIN, 1=chunk0 ... 5=chunk4
            last_chunk_call = hid.send_and_read.call_args_list[5]
            pkt = last_chunk_call[0][0]
            real_bytes = bytes(pkt[6:6 + 40])
            pad_bytes  = bytes(pkt[6 + 40:6 + OTA_CHUNK_SIZE])
            self.assertEqual(real_bytes, bytes(fw[224:264]))
            self.assertEqual(pad_bytes, b'\xff' * 16)
        finally:
            os.unlink(path)

    def test_chunk_packet_offset_fields(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            for i in range(5):
                call = hid.send_and_read.call_args_list[1 + i]
                pkt  = call[0][0]
                self.assertEqual(pkt[0], HID_POLYKYBD)
                self.assertEqual(pkt[1], CMD_OTA_CHUNK)
                offset = struct.unpack_from('<I', bytes(pkt), 2)[0]
                self.assertEqual(offset, i * OTA_CHUNK_SIZE)
        finally:
            os.unlink(path)

    def test_chunk_timeout_is_5000ms(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            c = hid.send_and_read.call_args_list[1]  # first chunk
            timeout = c[1].get('timeout') or c[0][1]
            self.assertEqual(timeout, 5000)
        finally:
            os.unlink(path)

    def test_chunk_retried_3_times_on_nack_then_fails(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _nack_reply(CMD_OTA_CHUNK))] * 3
            )
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn('CHUNK', msg)
            self.assertEqual(hid.send_and_read.call_count, 4)  # 1 BEGIN + 3 attempts
        finally:
            os.unlink(path)

    def test_chunk_succeeds_on_second_attempt(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        n    = _chunks(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN)),
                 (True, _nack_reply(CMD_OTA_CHUNK)),   # first attempt on chunk 0 fails
                 (True, _ack_reply(CMD_OTA_CHUNK))] +  # retry succeeds
                [(True, _ack_reply(CMD_OTA_CHUNK))] * (n - 1) +
                [(True, _ack_reply(CMD_OTA_COMMIT))]
            )
            ok, _ = flash_firmware(hid, path)
            self.assertTrue(ok)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware — OTA_COMMIT
# ---------------------------------------------------------------------------

class TestFlashFirmwareCommit(unittest.TestCase):

    def test_commit_packet_format(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            commit_pkt = hid.send_and_read.call_args_list[-1][0][0]
            self.assertEqual(commit_pkt[0], HID_POLYKYBD)
            self.assertEqual(commit_pkt[1], CMD_OTA_COMMIT)
        finally:
            os.unlink(path)

    def test_commit_nack_returns_false(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        n    = _chunks(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_OTA_BEGIN))] +
                [(True, _ack_reply(CMD_OTA_CHUNK))] * n +
                [(True, _nack_reply(CMD_OTA_COMMIT))]
            )
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn('COMMIT', msg)
        finally:
            os.unlink(path)

    def test_commit_timeout_is_5000ms(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            c = hid.send_and_read.call_args_list[-1]
            timeout = c[1].get('timeout') or c[0][1]
            self.assertEqual(timeout, 5000)
        finally:
            os.unlink(path)

    def test_success_returns_true_with_message(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
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
        fw   = _make_fw(b'\x42' * (OTA_CHUNK_SIZE * 5))
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
            self.assertIn('cancel', msg.lower())
            self.assertEqual(calls[0], 1)  # only BEGIN was sent
        finally:
            os.unlink(path)

    def test_cancel_mid_stream(self):
        fw   = _make_fw(b'\x42' * (OTA_CHUNK_SIZE * 10))
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
            self.assertIn('cancel', msg.lower())
            self.assertEqual(calls[0], 4)  # BEGIN + 3 chunks
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware — progress callback
# ---------------------------------------------------------------------------

class TestFlashFirmwareProgress(unittest.TestCase):

    def test_progress_callback_called(self):
        fw   = _make_fw(b'\xAA' * (OTA_CHUNK_SIZE * 3))
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            calls = []
            flash_firmware(hid, path, progress_cb=lambda pct, m: calls.append(pct))
            self.assertGreater(len(calls), 0)
        finally:
            os.unlink(path)

    def test_progress_starts_at_0_and_ends_at_100(self):
        fw   = _make_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            pcts = []
            flash_firmware(hid, path, progress_cb=lambda pct, m: pcts.append(pct))
            self.assertEqual(pcts[0], 0)
            self.assertEqual(pcts[-1], 100)
        finally:
            os.unlink(path)

    def test_progress_never_decreases(self):
        fw   = _make_fw(b'\xCC' * (OTA_CHUNK_SIZE * 200))
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
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
        fw   = _make_fw(bytes(range(256)) * 4)
        path = _write_bin(fw)
        try:
            expected_crc = binascii.crc32(fw) & 0xFFFFFFFF
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            begin_pkt = hid.send_and_read.call_args_list[0][0][0]
            sent_crc = struct.unpack_from('<I', bytes(begin_pkt), 6)[0]
            self.assertEqual(sent_crc, expected_crc)
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
