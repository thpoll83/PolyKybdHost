"""Tests for polyhost.device.hid_fw_up.

All tests use a lightweight mock HID object; no real hardware is required.

Firmware fixture
----------------
Every valid RP2040 .bin starts with a 256-byte boot2 block whose last 4
bytes are the CRC32 of the preceding 252 bytes, followed by an ARM
Cortex-M0+ vector table (initial SP at offset 256, reset vector at 260).
The helper _make_fw() builds the smallest binary that passes
validate_rp2040_firmware() -- 264 bytes.

For flash_firmware() tests, _make_polykybd_fw() is used instead:
it appends the UTF-16LE encoding of "PolyKybd" so the binary also passes
validate_polykybd_firmware().  _make_polykybd_fw() without extra args is
280 bytes (264 + 16), which is exactly 5 HID firmware-update chunks of 56 B.
"""
import binascii
import struct
import tempfile
import os
import unittest
from unittest.mock import MagicMock, patch

from polyhost.device.hid_fw_up import (
    get_fw_version,
    flash_firmware,
    apply_staged_firmware,
    validate_rp2040_firmware,
    validate_polykybd_firmware,
    HID_POLYKYBD,
    CMD_FW_UP_GET_VERSION,
    CMD_FW_UP_BEGIN,
    CMD_FW_UP_CHUNK,
    CMD_FW_UP_COMMIT,
    CMD_FW_UP_APPLY,
    FW_UP_CHUNK_SIZE,
    FW_UP_VERSION_LEN,
    FW_UP_MAX_SIZE,
    _RP2040_BOOT2_SIZE,
    _RP2040_SRAM_BASE,
    _RP2040_SRAM_END,
    _POLYKYBD_SIGNATURES,
    _crc32_rp2040,
)

ACK  = ord('.')
NACK = ord('!')

# ---------------------------------------------------------------------------
# Firmware fixture helpers
# ---------------------------------------------------------------------------

# Minimal valid boot2: 252 zero bytes + correct RP2040 boot ROM CRC32.
# Note: _crc32_rp2040 is NOT the same as binascii.crc32 — the RP2040 ROM
# uses a non-reflected MSB-first variant.
_BOOT2_PAYLOAD = bytes(252)
_BOOT2_CRC     = struct.pack('<I', _crc32_rp2040(_BOOT2_PAYLOAD))
# ARM Cortex-M0+ vector table: SP in SRAM, thumb reset vector in flash
_VECTOR_TABLE  = struct.pack('<II', 0x20010000, 0x10000101)
# 264-byte header that passes validate_rp2040_firmware()
_RP2040_HEADER = _BOOT2_PAYLOAD + _BOOT2_CRC + _VECTOR_TABLE

# UTF-16LE encoding of "PolyKybd" -- matches the product-string signature
_POLYKYBD_SIG = "PolyKybd".encode('utf-16-le')   # 16 bytes


def _make_fw(extra: bytes = b'') -> bytes:
    """Return a valid RP2040 binary with optional extra payload appended.
    Passes validate_rp2040_firmware(); does NOT contain a PolyKybd signature."""
    return _RP2040_HEADER + extra


def _make_polykybd_fw(extra: bytes = b'') -> bytes:
    """Return a valid RP2040 binary that also passes validate_polykybd_firmware().
    Without extra args: 280 bytes = exactly 5 HID firmware-update chunks of 56 B."""
    return _RP2040_HEADER + _POLYKYBD_SIG + extra


def _chunks(fw: bytes) -> int:
    return (len(fw) + FW_UP_CHUNK_SIZE - 1) // FW_UP_CHUNK_SIZE


def _write_bin(data: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix='.bin')
    os.write(fd, data)
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# HID mock helpers
# ---------------------------------------------------------------------------

POLL = ord('~')   # "still erasing, re-poll" reply byte


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


def _poll_reply(cmd: int) -> bytearray:
    """'~' reply: firmware signals 'still erasing, re-poll'."""
    buf = bytearray(64)
    buf[0] = HID_POLYKYBD
    buf[1] = cmd
    buf[2] = POLL
    return buf


def _version_reply(version: str, fw_size: int, fw_crc: int) -> bytearray:
    extra = bytearray(FW_UP_VERSION_LEN + 8)
    encoded = version.encode('utf-8')[:FW_UP_VERSION_LEN]
    extra[:len(encoded)] = encoded
    struct.pack_into('<I', extra, FW_UP_VERSION_LEN, fw_size)
    struct.pack_into('<I', extra, FW_UP_VERSION_LEN + 4, fw_crc)
    return _ack_reply(CMD_FW_UP_GET_VERSION, bytes(extra))


def _make_hid(side_effects, reconnect=False):
    hid = MagicMock()
    hid.send_and_read.side_effect = side_effects
    hid.wait_for_reconnect.return_value = reconnect
    return hid


def _flash_hid(fw: bytes):
    """Build a mock HID that ACKs the exact sequence for the given firmware."""
    n = _chunks(fw)
    return _make_hid(
        [(True, _ack_reply(CMD_FW_UP_BEGIN))] +
        [(True, _ack_reply(CMD_FW_UP_CHUNK))] * n +
        [(True, _ack_reply(CMD_FW_UP_COMMIT))]
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
        uf2_magic = struct.pack('<II', 0x0A324655, 0x9E5D5157) + bytes(260)
        ok, msg = validate_rp2040_firmware(uf2_magic)
        self.assertFalse(ok)

    def test_random_data_fails(self):
        import hashlib
        rnd = hashlib.sha256(b'seed').digest() * 16  # 512 bytes
        ok, _ = validate_rp2040_firmware(rnd[:264])
        self.assertFalse(ok)

    def test_valid_large_firmware_passes(self):
        fw = _make_fw(b'\xAB' * (512 * 1024 - 264))
        ok, _ = validate_rp2040_firmware(fw)
        self.assertTrue(ok)

    def test_validate_only_inspects_first_264_bytes(self):
        fw = _make_fw(b'\xFF' * 1000)
        ok, _ = validate_rp2040_firmware(fw)
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# validate_polykybd_firmware
# ---------------------------------------------------------------------------

class TestValidatePolykybdFirmware(unittest.TestCase):
    """Two separate signature entries, each tested independently:
      - "PolyKybd" UTF-16LE  covers the USB product string "PolyKybd Split72"
      - "Poly" UTF-16LE      covers the USB manufacturer prefix "PolyFabriq"
    Either match is sufficient; tests verify each path independently.
    """

    def test_product_string_detected(self):
        # Simulates the USB product descriptor "PolyKybd Split72" in the binary
        ok, msg = validate_polykybd_firmware(_make_fw("PolyKybd".encode('utf-16-le')))
        self.assertTrue(ok)
        self.assertEqual(msg, '')

    def test_manufacturer_string_detected(self):
        # "PolyFabriq" UTF-16LE contains the "Poly" prefix, so it matches the
        # manufacturer signature entry
        ok, _ = validate_polykybd_firmware(_make_fw("PolyFabriq".encode('utf-16-le')))
        self.assertTrue(ok)

    def test_manufacturer_prefix_alone_is_sufficient(self):
        # A hypothetical manufacturer name change still passes as long as it
        # starts with "Poly"
        ok, _ = validate_polykybd_firmware(_make_fw("PolyNewName".encode('utf-16-le')))
        self.assertTrue(ok)

    def test_no_signature_fails(self):
        # A valid RP2040 binary with no "Poly" UTF-16LE anywhere
        ok, msg = validate_polykybd_firmware(_make_fw())
        self.assertFalse(ok)
        self.assertIn('PolyKybd', msg)

    def test_ascii_poly_string_does_not_pass(self):
        # Plain ASCII "PolyKybd" lacks the UTF-16LE interleaved zero bytes
        ok, _ = validate_polykybd_firmware(_make_fw(b'PolyKybd'))
        self.assertFalse(ok)

    def test_error_mentions_keyboard_path(self):
        _, msg = validate_polykybd_firmware(_make_fw())
        self.assertIn('handwired/polykybd', msg)

    def test_accepts_bytearray(self):
        ok, _ = validate_polykybd_firmware(bytearray(_make_fw("PolyKybd".encode('utf-16-le'))))
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
        self.assertEqual(pkt[1], CMD_FW_UP_GET_VERSION)

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
        hid = _make_hid([(True, _nack_reply(CMD_FW_UP_GET_VERSION))])
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
# flash_firmware -- input validation
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
        path = _write_bin(b'\x00' * (FW_UP_MAX_SIZE + 1))
        try:
            ok, msg = flash_firmware(MagicMock(), path)
            self.assertFalse(ok)
            self.assertIn('large', msg.lower())
        finally:
            os.unlink(path)

    def test_invalid_rp2040_binary_returns_false(self):
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

    def test_non_polykybd_rp2040_binary_rejected(self):
        # Passes validate_rp2040_firmware() but has no "Poly" UTF-16LE
        path = _write_bin(_make_fw())
        hid = MagicMock()
        try:
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn('PolyKybd', msg)
            hid.send_and_read.assert_not_called()
        finally:
            os.unlink(path)

    def test_valid_polykybd_binary_proceeds_to_hid(self):
        fw = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            # BEGIN fails -- proves we reached the HID stage
            hid = _make_hid([(False, bytearray(64))])
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn('BEGIN', msg)
            hid.send_and_read.assert_called_once()
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware -- FW_UP_BEGIN
# ---------------------------------------------------------------------------

class TestFlashFirmwareBegin(unittest.TestCase):

    def test_begin_packet_byte_layout(self):
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            expected_crc = binascii.crc32(fw) & 0xFFFFFFFF
            ok, msg = flash_firmware(_flash_hid(fw), path)
            self.assertTrue(ok)
        finally:
            os.unlink(path)

        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            begin_pkt = hid.send_and_read.call_args_list[0][0][0]
            self.assertEqual(begin_pkt[0], HID_POLYKYBD)
            self.assertEqual(begin_pkt[1], CMD_FW_UP_BEGIN)
            size_field = struct.unpack_from('<I', bytes(begin_pkt), 2)[0]
            crc_field  = struct.unpack_from('<I', bytes(begin_pkt), 6)[0]
            self.assertEqual(size_field, len(fw))
            self.assertEqual(crc_field, expected_crc)
        finally:
            os.unlink(path)

    def test_begin_timeout_is_15000ms(self):
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            c = hid.send_and_read.call_args_list[0]
            timeout = c[1].get('timeout') or c[0][1]
            self.assertEqual(timeout, 15000)
        finally:
            os.unlink(path)

    def test_begin_nack_returns_false(self):
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            hid = _make_hid([(True, _nack_reply(CMD_FW_UP_BEGIN))])
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn('BEGIN', msg)
        finally:
            os.unlink(path)

    def test_begin_hid_failure_returns_false(self):
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            hid = _make_hid([(False, bytearray(64))])
            ok, _ = flash_firmware(hid, path)
            self.assertFalse(ok)
        finally:
            os.unlink(path)

    def test_begin_usb_dropout_triggers_reconnect(self):
        # Simulate the RP2040 flash-erase USB dropout: send_and_read fails
        # (ok=False), wait_for_reconnect succeeds, host re-polls BEGIN and gets '.'.
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            n = _chunks(fw)
            hid = _make_hid(
                [(False, bytearray(64))] +                    # FW_UP_BEGIN dropout
                [(True, _ack_reply(CMD_FW_UP_BEGIN))] +       # re-poll after reconnect
                [(True, _ack_reply(CMD_FW_UP_CHUNK))] * n +
                [(True, _ack_reply(CMD_FW_UP_COMMIT))],
                reconnect=True,                               # reconnect succeeds
            )
            ok, msg = flash_firmware(hid, path)
            self.assertTrue(ok, msg)
            hid.wait_for_reconnect.assert_called_once_with(timeout_s=30)
        finally:
            os.unlink(path)

    def test_begin_windows_empty_reply_treated_as_dropout(self):
        # On Windows hidapi returns (True, empty_bytes) on USB disconnect instead
        # of raising an exception.  An empty reply must trigger the reconnect path.
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            n = _chunks(fw)
            hid = _make_hid(
                [(True, bytearray(0))] +                      # empty reply = Windows dropout
                [(True, _ack_reply(CMD_FW_UP_BEGIN))] +       # re-poll after reconnect
                [(True, _ack_reply(CMD_FW_UP_CHUNK))] * n +
                [(True, _ack_reply(CMD_FW_UP_COMMIT))],
                reconnect=True,
            )
            ok, msg = flash_firmware(hid, path)
            self.assertTrue(ok, msg)
            hid.wait_for_reconnect.assert_called_once_with(timeout_s=30)
        finally:
            os.unlink(path)

    def test_begin_usb_dropout_reconnect_timeout_fails(self):
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            hid = _make_hid([(False, bytearray(64))], reconnect=False)
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn('BEGIN', msg)
            self.assertIn('reconnect', msg)
            hid.wait_for_reconnect.assert_called_once_with(timeout_s=30)
        finally:
            os.unlink(path)

    def test_begin_poll_reply_causes_repoll_until_ready(self):
        # Firmware returns '~' twice (slave still erasing) then '.' (ready).
        # Host must re-send CMD_FW_UP_BEGIN each time and eventually succeed.
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        n    = _chunks(fw)
        try:
            hid = _make_hid(
                [(True, _poll_reply(CMD_FW_UP_BEGIN))] * 2 +  # 2 × '~' (still erasing)
                [(True, _ack_reply(CMD_FW_UP_BEGIN))] +        # '.' ready
                [(True, _ack_reply(CMD_FW_UP_CHUNK))] * n +
                [(True, _ack_reply(CMD_FW_UP_COMMIT))],
            )
            ok, msg = flash_firmware(hid, path)
            self.assertTrue(ok, msg)
            # All three BEGIN sends used CMD_FW_UP_BEGIN
            for i in range(3):
                pkt = hid.send_and_read.call_args_list[i][0][0]
                self.assertEqual(pkt[1], CMD_FW_UP_BEGIN)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware -- FW_UP_CHUNK
# ---------------------------------------------------------------------------

class TestFlashFirmwareChunks(unittest.TestCase):
    """_make_polykybd_fw() without extra args is 280 bytes = exactly 5 chunks.
    Chunk layout: all 5 chunks are full (56 B each) -- no padding on last chunk.
    """

    def test_minimal_firmware_sends_correct_chunk_count(self):
        fw   = _make_polykybd_fw()     # 280 bytes = 5 chunks
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
        # 280 + 56 = 336 bytes = 6 full chunks
        fw   = _make_polykybd_fw(b'\xCD' * FW_UP_CHUNK_SIZE)
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            ok, _ = flash_firmware(hid, path)
            self.assertTrue(ok)
            self.assertEqual(hid.send_and_read.call_count, 8)  # 1+6+1
        finally:
            os.unlink(path)

    def test_partial_last_chunk_padded_with_ff(self):
        # 280 + 1 = 281 bytes = 6 chunks; chunk 5 (offset 280) has 1 real byte
        # + 55 bytes of 0xFF padding
        fw   = _make_polykybd_fw(b'\xAB')
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            # call index 0=BEGIN, 1=chunk0 ... 6=chunk5 (last)
            last_chunk_call = hid.send_and_read.call_args_list[6]
            pkt = last_chunk_call[0][0]
            real_bytes = bytes(pkt[6:7])                         # 1 real byte
            pad_bytes  = bytes(pkt[7:6 + FW_UP_CHUNK_SIZE])     # 55 xFF bytes
            self.assertEqual(real_bytes, bytes(fw[280:281]))
            self.assertEqual(pad_bytes, b'\xff' * 55)
        finally:
            os.unlink(path)

    def test_chunk_packet_offset_fields(self):
        fw   = _make_polykybd_fw()   # 5 chunks
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            for i in range(5):
                call = hid.send_and_read.call_args_list[1 + i]
                pkt  = call[0][0]
                self.assertEqual(pkt[0], HID_POLYKYBD)
                self.assertEqual(pkt[1], CMD_FW_UP_CHUNK)
                offset = struct.unpack_from('<I', bytes(pkt), 2)[0]
                self.assertEqual(offset, i * FW_UP_CHUNK_SIZE)
        finally:
            os.unlink(path)

    def test_chunk_timeout_is_8000ms(self):
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            c = hid.send_and_read.call_args_list[1]  # first chunk
            timeout = c[1].get('timeout') or c[0][1]
            self.assertEqual(timeout, 8000)
        finally:
            os.unlink(path)

    def test_chunk_nack_retried_then_succeeds(self):
        # Explicit NACK (slave missed the split RPC) is retried — the firmware
        # keeps both write cursors un-advanced so re-sending the same offset is
        # safe (see hid_fw_up.c CMD_FW_UP_CHUNK).
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        n    = _chunks(fw)
        try:
            with patch('polyhost.device.hid_fw_up.time.sleep'):
                hid = _make_hid(
                    [(True, _ack_reply(CMD_FW_UP_BEGIN)),
                     (True, _nack_reply(CMD_FW_UP_CHUNK)),    # NACK → retry
                     (True, _ack_reply(CMD_FW_UP_CHUNK))] +   # retry succeeds
                    [(True, _ack_reply(CMD_FW_UP_CHUNK))] * (n - 1) +
                    [(True, _ack_reply(CMD_FW_UP_COMMIT))]
                )
                ok, _ = flash_firmware(hid, path)
                self.assertTrue(ok)
        finally:
            os.unlink(path)

    def test_chunk_nack_with_resume_offset_rewinds(self):
        # A NACK carrying a resume offset (bytes 3..6) rewinds the stream to
        # that offset: the keyboard reported the lower of its two halves' write
        # cursors after a desync, and duplicate chunks are ACK'd idempotently.
        fw   = _make_polykybd_fw()          # 280 bytes = 5 chunks
        path = _write_bin(fw)
        n    = _chunks(fw)
        sent_offsets = []

        def nack_with_resume(resume):
            buf = _nack_reply(CMD_FW_UP_CHUNK)
            struct.pack_into('<I', buf, 3, resume)
            return buf

        replies = (
            [(True, _ack_reply(CMD_FW_UP_BEGIN))] +
            [(True, _ack_reply(CMD_FW_UP_CHUNK))] * 3 +          # chunks 0,1,2
            [(True, nack_with_resume(1 * FW_UP_CHUNK_SIZE))] +   # chunk 3 → rewind to 1
            [(True, _ack_reply(CMD_FW_UP_CHUNK))] * (n - 1) +    # chunks 1..4 again
            [(True, _ack_reply(CMD_FW_UP_COMMIT))]
        )
        reply_iter = iter(replies)

        def side_effect(pkt, timeout):
            if pkt[1] == CMD_FW_UP_CHUNK:
                sent_offsets.append(struct.unpack_from('<I', pkt, 2)[0])
            return next(reply_iter)

        try:
            with patch('polyhost.device.hid_fw_up.time.sleep'):
                hid = MagicMock()
                hid.send_and_read.side_effect = side_effect
                ok, _ = flash_firmware(hid, path)
                self.assertTrue(ok)
                # 0,1,2,3 then rewind: 1,2,3,4
                expected = [0, 56, 112, 168, 56, 112, 168, 224]
                self.assertEqual(sent_offsets, expected)
        finally:
            os.unlink(path)

    def test_chunk_nack_fails_after_8_attempts_with_cleanup(self):
        # A chunk NACK'd on all 8 attempts aborts — and a cleanup COMMIT is sent
        # so both halves leave fw_up mode (core1 restart, housekeeping resumes).
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            with patch('polyhost.device.hid_fw_up.time.sleep'):
                hid = _make_hid(
                    [(True, _ack_reply(CMD_FW_UP_BEGIN))] +
                    [(True, _nack_reply(CMD_FW_UP_CHUNK))] * 8 +     # all attempts NACK
                    [(True, _nack_reply(CMD_FW_UP_COMMIT))]          # cleanup commit
                )
                ok, msg = flash_firmware(hid, path)
                self.assertFalse(ok)
                self.assertIn('CHUNK', msg)
                # 1 BEGIN + 8 chunk attempts + 1 cleanup COMMIT
                self.assertEqual(hid.send_and_read.call_count, 10)
                last_pkt = hid.send_and_read.call_args_list[-1][0][0]
                self.assertEqual(last_pkt[1], CMD_FW_UP_COMMIT)
        finally:
            os.unlink(path)

    def test_chunk_timeout_retried_8_times_then_fails(self):
        # Timeout (ok=False / empty reply) is retried up to 8 attempts total.
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            with patch('polyhost.device.hid_fw_up.time.sleep'):
                hid = _make_hid(
                    [(True, _ack_reply(CMD_FW_UP_BEGIN))] +
                    [(False, bytearray(64))] * 8 +                   # 8 timeouts → fail
                    [(True, _nack_reply(CMD_FW_UP_COMMIT))]          # cleanup commit
                )
                ok, msg = flash_firmware(hid, path)
                self.assertFalse(ok)
                self.assertIn('CHUNK', msg)
                # 1 BEGIN + 8 attempts + 1 cleanup COMMIT
                self.assertEqual(hid.send_and_read.call_count, 10)
        finally:
            os.unlink(path)

    def test_chunk_succeeds_on_second_attempt(self):
        # Transient timeout on first attempt; retry succeeds.
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        n    = _chunks(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_FW_UP_BEGIN)),
                 (False, bytearray(64)),                  # first attempt times out
                 (True, _ack_reply(CMD_FW_UP_CHUNK))] +   # retry succeeds
                [(True, _ack_reply(CMD_FW_UP_CHUNK))] * (n - 1) +
                [(True, _ack_reply(CMD_FW_UP_COMMIT))]
            )
            ok, _ = flash_firmware(hid, path)
            self.assertTrue(ok)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware -- FW_UP_COMMIT
# ---------------------------------------------------------------------------

class TestFlashFirmwareCommit(unittest.TestCase):

    def test_commit_packet_format(self):
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            flash_firmware(hid, path)
            commit_pkt = hid.send_and_read.call_args_list[-1][0][0]
            self.assertEqual(commit_pkt[0], HID_POLYKYBD)
            self.assertEqual(commit_pkt[1], CMD_FW_UP_COMMIT)
        finally:
            os.unlink(path)

    def test_commit_nack_returns_false(self):
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        n    = _chunks(fw)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_FW_UP_BEGIN))] +
                [(True, _ack_reply(CMD_FW_UP_CHUNK))] * n +
                [(True, _nack_reply(CMD_FW_UP_COMMIT))]
            )
            ok, msg = flash_firmware(hid, path)
            self.assertFalse(ok)
            self.assertIn('COMMIT', msg)
        finally:
            os.unlink(path)

    def test_commit_timeout_is_5000ms(self):
        fw   = _make_polykybd_fw()
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
        fw   = _make_polykybd_fw()
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            ok, msg = flash_firmware(hid, path)
            self.assertTrue(ok)
            self.assertGreater(len(msg), 0)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware -- cancellation
# ---------------------------------------------------------------------------

class TestFlashFirmwareCancellation(unittest.TestCase):

    def test_cancel_before_first_chunk(self):
        fw   = _make_polykybd_fw(b'\x42' * (FW_UP_CHUNK_SIZE * 5))
        path = _write_bin(fw)
        try:
            cancel_flag = [False]
            calls = [0]

            def side_effect(pkt, timeout):
                calls[0] += 1
                if calls[0] == 1:   # BEGIN
                    cancel_flag[0] = True
                    return True, _ack_reply(CMD_FW_UP_BEGIN)
                return True, _ack_reply(CMD_FW_UP_CHUNK)

            hid = MagicMock()
            hid.send_and_read.side_effect = side_effect
            ok, msg = flash_firmware(hid, path, cancel_flag=cancel_flag)
            self.assertFalse(ok)
            self.assertIn('cancel', msg.lower())
            # BEGIN + the cleanup COMMIT that takes both halves out of fw_up mode
            self.assertEqual(calls[0], 2)
        finally:
            os.unlink(path)

    def test_cancel_mid_stream(self):
        fw   = _make_polykybd_fw(b'\x42' * (FW_UP_CHUNK_SIZE * 10))
        path = _write_bin(fw)
        try:
            cancel_flag = [False]
            calls = [0]

            def side_effect(pkt, timeout):
                calls[0] += 1
                if calls[0] == 1:
                    return True, _ack_reply(CMD_FW_UP_BEGIN)
                if calls[0] == 4:   # cancel after 3rd chunk
                    cancel_flag[0] = True
                return True, _ack_reply(CMD_FW_UP_CHUNK)

            hid = MagicMock()
            hid.send_and_read.side_effect = side_effect
            ok, msg = flash_firmware(hid, path, cancel_flag=cancel_flag)
            self.assertFalse(ok)
            self.assertIn('cancel', msg.lower())
            # BEGIN + 3 chunks + the cleanup COMMIT
            self.assertEqual(calls[0], 5)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_firmware -- progress callback
# ---------------------------------------------------------------------------

class TestFlashFirmwareProgress(unittest.TestCase):

    def test_progress_callback_called(self):
        fw   = _make_polykybd_fw(b'\xAA' * (FW_UP_CHUNK_SIZE * 3))
        path = _write_bin(fw)
        try:
            hid = _flash_hid(fw)
            calls = []
            flash_firmware(hid, path, progress_cb=lambda pct, m: calls.append(pct))
            self.assertGreater(len(calls), 0)
        finally:
            os.unlink(path)

    def test_progress_starts_at_0_and_ends_at_100(self):
        fw   = _make_polykybd_fw()
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
        fw   = _make_polykybd_fw(b'\xCC' * (FW_UP_CHUNK_SIZE * 200))
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
        fw   = _make_polykybd_fw(bytes(range(256)) * 4)
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


# ---------------------------------------------------------------------------
# Real firmware binary integration tests
# ---------------------------------------------------------------------------

_FIXTURE_BIN = os.path.join(os.path.dirname(__file__),
                             'fixtures', 'polykybd_split72_default.bin')

# Known-good values computed from the shipped binary at the time it was added
# as a test fixture.  Update these constants when a new firmware build is
# committed as the fixture.
_FIXTURE_SIZE    = 248160
_FIXTURE_FW_CRC  = 0x3D4BB6A1   # binascii.crc32(fw) & 0xFFFFFFFF  (HID firmware update protocol)


@unittest.skipUnless(os.path.exists(_FIXTURE_BIN), 'fixture binary not present')
class TestRealFirmwareBinary(unittest.TestCase):
    """Integration tests against the real handwired/polykybd/split72 firmware.

    These tests load the actual .bin produced by 'make handwired/polykybd/split72:default'
    and confirm that all validation passes and expected metadata is stable.
    """

    @classmethod
    def setUpClass(cls):
        with open(_FIXTURE_BIN, 'rb') as fh:
            cls.fw = fh.read()

    def test_file_size_matches_expected(self):
        self.assertEqual(len(self.fw), _FIXTURE_SIZE)

    def test_validate_rp2040_passes(self):
        ok, msg = validate_rp2040_firmware(self.fw)
        self.assertTrue(ok, msg)

    def test_validate_polykybd_passes(self):
        ok, msg = validate_polykybd_firmware(self.fw)
        self.assertTrue(ok, msg)

    def test_boot2_crc_is_correct(self):
        stored   = struct.unpack_from('<I', self.fw, 252)[0]
        computed = _crc32_rp2040(self.fw[:252])
        self.assertEqual(computed, stored,
                         f"boot2 CRC mismatch: computed 0x{computed:08X}, stored 0x{stored:08X}")

    def test_initial_sp_in_sram(self):
        sp = struct.unpack_from('<I', self.fw, _RP2040_BOOT2_SIZE)[0]
        self.assertGreaterEqual(sp, _RP2040_SRAM_BASE)
        self.assertLessEqual(sp, _RP2040_SRAM_END)

    def test_fw_crc32_matches_expected(self):
        crc = binascii.crc32(self.fw) & 0xFFFFFFFF
        self.assertEqual(crc, _FIXTURE_FW_CRC,
                         f"Firmware CRC changed: expected 0x{_FIXTURE_FW_CRC:08X}, got 0x{crc:08X}. "
                         "Update _FIXTURE_FW_CRC if this is a new firmware version.")

    def test_product_string_present(self):
        sig = "PolyKybd".encode('utf-16-le')
        self.assertIn(sig, self.fw, "USB product string 'PolyKybd' not found in binary")

    def test_manufacturer_string_present(self):
        sig = "Poly".encode('utf-16-le')
        self.assertIn(sig, self.fw, "Manufacturer prefix 'Poly' UTF-16LE not found in binary")


# ---------------------------------------------------------------------------
# apply_staged_firmware
# ---------------------------------------------------------------------------

class TestApplyStagedFirmware(unittest.TestCase):

    def test_apply_packet_format_and_timeout(self):
        hid = _make_hid([(True, _ack_reply(CMD_FW_UP_APPLY))], reconnect=True)
        apply_staged_firmware(hid)
        pkt, kwargs = hid.send_and_read.call_args[0][0], hid.send_and_read.call_args[1]
        self.assertEqual(bytes(pkt), bytes([HID_POLYKYBD, CMD_FW_UP_APPLY]))
        self.assertEqual(kwargs['timeout'], 5000)

    def test_ack_then_reconnect_succeeds(self):
        hid = _make_hid([(True, _ack_reply(CMD_FW_UP_APPLY))], reconnect=True)
        ok, msg = apply_staged_firmware(hid)
        self.assertTrue(ok)
        self.assertIn("reconnected", msg)
        hid.wait_for_reconnect.assert_called_once_with(timeout_s=30)

    def test_nack_is_safe_noop_without_reconnect_wait(self):
        # '!' means "no valid staged image / in-app apply not built in":
        # the keyboard did NOT reboot, so we must not sit in a 30 s wait.
        hid = _make_hid([(True, _nack_reply(CMD_FW_UP_APPLY))], reconnect=True)
        ok, msg = apply_staged_firmware(hid)
        self.assertFalse(ok)
        self.assertIn("not available", msg)
        hid.wait_for_reconnect.assert_not_called()

    def test_no_reply_treated_as_rebooting(self):
        # USB torn down right after accepting the command — empty reply,
        # proceed to the reconnect wait.
        hid = _make_hid([(True, bytearray())], reconnect=True)
        ok, _ = apply_staged_firmware(hid)
        self.assertTrue(ok)
        hid.wait_for_reconnect.assert_called_once()

    def test_hid_failure_still_waits_for_reconnect(self):
        # A failed send (device already re-enumerating) is not a NACK —
        # the apply may well be in progress, so wait for the device.
        hid = _make_hid([(False, bytearray())], reconnect=True)
        ok, _ = apply_staged_firmware(hid)
        self.assertTrue(ok)
        hid.wait_for_reconnect.assert_called_once()

    def test_reconnect_timeout_fails_with_recovery_hint(self):
        hid = _make_hid([(True, _ack_reply(CMD_FW_UP_APPLY))], reconnect=False)
        ok, msg = apply_staged_firmware(hid)
        self.assertFalse(ok)
        self.assertIn("BOOTSEL", msg)

    def test_drains_replies_before_send_and_after_reconnect(self):
        hid = _make_hid([(True, _ack_reply(CMD_FW_UP_APPLY))], reconnect=True)
        apply_staged_firmware(hid)
        self.assertEqual(hid.drain_replies.call_count, 2)

    def test_nack_drains_only_once(self):
        hid = _make_hid([(True, _nack_reply(CMD_FW_UP_APPLY))], reconnect=True)
        apply_staged_firmware(hid)
        self.assertEqual(hid.drain_replies.call_count, 1)

    def test_progress_reports_start_mid_end(self):
        hid = _make_hid([(True, _ack_reply(CMD_FW_UP_APPLY))], reconnect=True)
        percents = []
        apply_staged_firmware(hid, progress_cb=lambda pct, msg: percents.append(pct))
        self.assertEqual(percents, [0, 50, 100])

    def test_progress_callback_optional(self):
        hid = _make_hid([(True, _ack_reply(CMD_FW_UP_APPLY))], reconnect=True)
        ok, _ = apply_staged_firmware(hid)   # no callback — must not raise
        self.assertTrue(ok)


if __name__ == '__main__':
    unittest.main()
